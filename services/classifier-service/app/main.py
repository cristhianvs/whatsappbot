from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import structlog
import os
from dotenv import load_dotenv

from .agents.classifier import MessageClassifier
from .utils.redis_client import RedisClient
from .models.schemas import ClassificationRequest, ClassificationResponse

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

app = FastAPI(title="Message Classifier Service", version="1.0.0")

# Initialize services
redis_client = RedisClient()
classifier = MessageClassifier()

@app.on_event("startup")
async def startup_event():
    await redis_client.connect()
    logger.info("Classifier service started")

@app.on_event("shutdown") 
async def shutdown_event():
    await redis_client.disconnect()
    logger.info("Classifier service shutdown")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "classifier-service",
        "version": "1.0.0"
    }

@app.post("/classify", response_model=ClassificationResponse)
async def classify_message(request: ClassificationRequest):
    try:
        logger.info("Classifying message", message_id=request.message_id)
        
        result = await classifier.classify(
            text=request.text,
            context=request.context
        )
        
        logger.info(
            "Classification completed",
            message_id=request.message_id,
            is_incident=result.is_incident,
            confidence=result.confidence
        )
        
        return result
        
    except Exception as e:
        logger.error("Classification failed", error=str(e), message_id=request.message_id)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
async def get_metrics():
    # Prometheus metrics endpoint
    return {"message": "Metrics endpoint - integrate with prometheus_client"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)