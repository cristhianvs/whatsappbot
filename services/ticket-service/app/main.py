from fastapi import FastAPI, HTTPException, BackgroundTasks
from contextlib import asynccontextmanager
import structlog
import os
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv

from .services.zoho_client import ZohoClient
from .services.ticket_queue import TicketQueue
from .utils.redis_client import RedisClient
from .models.schemas import TicketRequest, TicketResponse, TicketStatus, HealthResponse

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
        structlog.dev.ConsoleRenderer() if os.getenv('ENVIRONMENT') == 'development' else structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Global services
redis_client = RedisClient()
zoho_client = ZohoClient()
ticket_queue = TicketQueue(redis_client)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await redis_client.connect()
    
    try:
        await zoho_client.initialize()
    except Exception as e:
        logger.warning("Zoho client initialization failed, will retry later", error=str(e))
    
    # Start classification result subscriber
    subscriber_task = await start_classification_subscriber()
    
    # Start queue processor
    queue_processor_task = await start_queue_processor()
    
    logger.info("Ticket service started")
    yield
    
    # Shutdown
    if subscriber_task:
        subscriber_task.cancel()
    if queue_processor_task:
        queue_processor_task.cancel()
    await redis_client.disconnect()
    logger.info("Ticket service shutdown")

app = FastAPI(
    title="Ticket Service", 
    version="1.0.0",
    lifespan=lifespan
)

async def start_classification_subscriber():
    """Start Redis subscriber for classification results"""
    try:
        pubsub = await redis_client.subscribe_to_channel('tickets:classify:result')
        if pubsub:
            task = asyncio.create_task(process_classification_results(pubsub))
            return task
    except Exception as e:
        logger.error("Failed to start classification subscriber", error=str(e))
        return None

async def start_queue_processor():
    """Start background queue processor"""
    try:
        task = asyncio.create_task(queue_processor_background())
        return task
    except Exception as e:
        logger.error("Failed to start queue processor", error=str(e))
        return None

async def process_classification_results(pubsub):
    """Process classification results from classifier service"""
    try:
        async for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    data = json.loads(message['data'])
                    await handle_classification_result(data)
                except Exception as e:
                    logger.error("Failed to process classification result", error=str(e))
    except Exception as e:
        logger.error("Classification subscriber error", error=str(e))

async def handle_classification_result(data: dict):
    """Handle classification result and create ticket if needed"""
    try:
        classification = data.get('classification', {})
        
        if not classification.get('is_support_incident'):
            return
        
        # Extract information for ticket creation
        message_id = data.get('message_id', '')
        group_id = data.get('group_id', '')
        
        # Build ticket request from classification
        ticket_request = await build_ticket_from_classification(classification, message_id, group_id)
        
        if ticket_request:
            await create_ticket_from_classification(ticket_request, group_id)
            
    except Exception as e:
        logger.error("Failed to handle classification result", error=str(e))

async def build_ticket_from_classification(classification: dict, message_id: str, group_id: str) -> TicketRequest:
    """Build ticket request from classification data"""
    try:
        # Map urgency to priority
        urgency = classification.get('urgency', 'low')
        if urgency == 'critical':
            priority = 'urgent'
        elif urgency in ['high', 'medium']:
            priority = 'normal'
        else:
            priority = 'low'
            
        # Get or create contact
        contact_email = f"whatsapp+{group_id.replace('@g.us', '')}@support.com"
        contact_id = await get_or_create_contact(contact_email, "Cliente WhatsApp")
        
        return TicketRequest(
            subject=classification.get('summary', 'Incidente desde WhatsApp')[:100],
            description=f"""
Incidente reportado desde WhatsApp:

**Resumen:** {classification.get('summary', 'Sin resumen')}

**Categoría:** {classification.get('category', 'general_inquiry')}
**Urgencia:** {urgency}
**Confianza:** {classification.get('confidence', 0.0):.2f}

**Mensaje ID:** {message_id}
**Grupo:** {group_id}

**Información extraída:**
{json.dumps(classification.get('extracted_info', {}), indent=2, ensure_ascii=False)}

**Respuesta sugerida:**
{classification.get('suggested_response', 'Sin respuesta sugerida')}
            """.strip(),
            priority=priority,
            contact_id=contact_id,
            classification=classification.get('category', 'technical'),
            department_id=await get_default_department_id()
        )
        
    except Exception as e:
        logger.error("Failed to build ticket from classification", error=str(e))
        return None

async def get_or_create_contact(email: str, name: str) -> str:
    """Get existing contact or create new one"""
    try:
        # For now, just create a new contact each time
        # In production, you'd want to check if contact exists first
        contact_id = await zoho_client.create_contact(email, name)
        return contact_id
    except Exception as e:
        logger.error("Failed to get/create contact", error=str(e), email=email)
        # Return a default contact ID or raise
        raise

async def get_default_department_id() -> str:
    """Get default department ID for tickets"""
    try:
        departments = await zoho_client.list_departments()
        if departments:
            # Return first department or look for 'Support' department
            for dept in departments:
                if 'support' in dept.name.lower() or 'soporte' in dept.name.lower():
                    return dept.id
            return departments[0].id
        else:
            raise ValueError("No departments found")
    except Exception as e:
        logger.error("Failed to get default department", error=str(e))
        # Return a hardcoded fallback or raise
        raise

async def create_ticket_from_classification(ticket_request: TicketRequest, group_id: str):
    """Create ticket and publish notifications"""
    try:
        # Try to create ticket
        ticket_id = await zoho_client.create_ticket(ticket_request)
        
        # Publish ticket created event
        notification_data = {
            "ticket_id": ticket_id,
            "group_id": group_id,
            "ticket_number": f"#{ticket_id}",
            "summary": ticket_request.subject,
            "priority": ticket_request.priority,
            "timestamp": datetime.now().isoformat()
        }
        
        await redis_client.publish_message('tickets:created', notification_data)
        
        logger.info("Ticket created from classification", 
                   ticket_id=ticket_id, 
                   group_id=group_id)
        
    except Exception as e:
        logger.warning("Failed to create ticket, adding to queue", error=str(e))
        # Add to queue for later processing
        await ticket_queue.add_ticket(ticket_request)

async def queue_processor_background():
    """Background task to process queued tickets"""
    while True:
        try:
            await asyncio.sleep(30)  # Process every 30 seconds
            if zoho_client.is_connected():
                processed = await ticket_queue.process_queue()
                if processed > 0:
                    logger.info("Processed queued tickets", count=processed)
        except Exception as e:
            logger.error("Queue processor error", error=str(e))
            await asyncio.sleep(60)  # Wait longer on error

@app.get("/health", response_model=HealthResponse)
async def health_check():
    queue_length = await ticket_queue.get_queue_length()
    
    return HealthResponse(
        status="healthy",
        service="ticket-service",
        timestamp=datetime.now(),
        zoho_connected=zoho_client.is_connected(),
        redis_connected=redis_client.redis is not None,
        queue_length=queue_length
    )

@app.post("/tickets", response_model=TicketResponse)
async def create_ticket(request: TicketRequest):
    try:
        logger.info("Creating ticket", subject=request.subject, priority=request.priority)
        
        # Try to create ticket directly first
        try:
            ticket_id = await zoho_client.create_ticket(request)
            
            # Publish success event
            await redis_client.publish_message("tickets:created", {
                "ticket_id": ticket_id,
                "ticket_number": f"#{ticket_id}",
                "subject": request.subject,
                "priority": request.priority.value,
                "contact_id": request.contact_id,
                "timestamp": datetime.now().isoformat()
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
    port = int(os.getenv('PORT', 8003))
    host = os.getenv('HOST', '0.0.0.0')
    uvicorn.run(app, host=host, port=port)