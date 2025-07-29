from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
import structlog
import os
from dotenv import load_dotenv

from .services.zoho_client import ZohoClient
from .services.ticket_queue import TicketQueue
from .utils.redis_client import RedisClient
from .models.schemas import TicketRequest, TicketResponse, TicketStatus

load_dotenv()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

app = FastAPI(title="Ticket Service", version="1.0.0")

# Initialize services
redis_client = RedisClient()
zoho_client = ZohoClient()
ticket_queue = TicketQueue(redis_client)

@app.on_event("startup")
async def startup_event():
    await redis_client.connect()
    await zoho_client.initialize()
    logger.info("Ticket service started")

@app.on_event("shutdown")
async def shutdown_event():
    await redis_client.disconnect()
    logger.info("Ticket service shutdown")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ticket-service",
        "version": "1.0.0",
        "zoho_connected": zoho_client.is_connected()
    }

@app.post("/tickets", response_model=TicketResponse)
async def create_ticket(request: TicketRequest):
    try:
        logger.info("Creating ticket", subject=request.subject, priority=request.priority)
        
        # Try to create ticket directly first
        try:
            ticket_id = await zoho_client.create_ticket(request)
            
            # Publish success event
            await redis_client.publish("tickets:created", {
                "ticket_id": ticket_id,
                "subject": request.subject,
                "priority": request.priority,
                "contact_id": request.contact_id
            })
            
            logger.info("Ticket created successfully", ticket_id=ticket_id)
            
            return TicketResponse(
                ticket_id=ticket_id,
                status="created",
                message="Ticket created successfully"
            )
            
        except Exception as zoho_error:
            logger.warning("Zoho unavailable, queuing ticket", error=str(zoho_error))
            
            # Queue the ticket for later processing
            queue_id = await ticket_queue.add_ticket(request)
            
            return TicketResponse(
                ticket_id=queue_id,
                status="queued",
                message="Zoho is unavailable. Ticket queued for processing."
            )
            
    except Exception as e:
        logger.error("Failed to process ticket request", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tickets/{ticket_id}/status", response_model=TicketStatus)
async def get_ticket_status(ticket_id: str):
    try:
        # Check if it's a queued ticket first
        if ticket_id.startswith("queue_"):
            queue_status = await ticket_queue.get_ticket_status(ticket_id)
            return TicketStatus(
                ticket_id=ticket_id,
                status=queue_status["status"],
                last_updated=queue_status["last_updated"]
            )
        
        # Get status from Zoho
        status = await zoho_client.get_ticket_status(ticket_id)
        
        return TicketStatus(
            ticket_id=ticket_id,
            status=status,
            last_updated=None  # Zoho doesn't provide this in basic status
        )
        
    except Exception as e:
        logger.error("Failed to get ticket status", error=str(e), ticket_id=ticket_id)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/departments")
async def list_departments():
    try:
        departments = await zoho_client.list_departments()
        return {"departments": departments}
    except Exception as e:
        logger.error("Failed to get departments", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/contacts")
async def create_contact(email: str, name: str = "Cliente"):
    try:
        contact_id = await zoho_client.create_contact(email, name)
        return {"contact_id": contact_id}
    except Exception as e:
        logger.error("Failed to create contact", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/queue/process")
async def process_queue():
    """Manual endpoint to process queued tickets"""
    try:
        processed_count = await ticket_queue.process_queue()
        return {"processed": processed_count}
    except Exception as e:
        logger.error("Failed to process queue", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
async def get_metrics():
    # Prometheus metrics endpoint
    return {"message": "Metrics endpoint - integrate with prometheus_client"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)