from fastapi import FastAPI, HTTPException, BackgroundTasks
from contextlib import asynccontextmanager
import structlog
import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv

from .agents.classifier import classifier
from .utils.redis_client import RedisClient
from .models.schemas import ClassificationRequest, ClassificationResponse, HealthResponse, MessageData, MessageContext

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
message_subscriber = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await redis_client.connect()
    
    # Start Redis message subscriber
    subscriber_task = await start_message_subscriber()
    
    logger.info("Classifier service started")
    yield
    
    # Shutdown
    if subscriber_task:
        subscriber_task.cancel()
    await redis_client.disconnect()
    logger.info("Classifier service shutdown")

app = FastAPI(
    title="Message Classifier Service", 
    version="1.0.0",
    lifespan=lifespan
)

async def start_message_subscriber():
    """Start Redis subscriber for incoming WhatsApp messages"""
    try:
        pubsub = await redis_client.subscribe_to_channel('whatsapp:messages:inbound')
        if pubsub:
            import asyncio
            task = asyncio.create_task(process_incoming_messages(pubsub))
            return task
    except Exception as e:
        logger.error("Failed to start message subscriber", error=str(e))
        return None

async def process_incoming_messages(pubsub):
    """Process incoming messages from WhatsApp service"""
    try:
        async for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    data = json.loads(message['data'])
                    await handle_whatsapp_message(data)
                except Exception as e:
                    logger.error("Failed to process message", error=str(e), raw_data=message.get('data', ''))
    except Exception as e:
        logger.error("Message subscriber error", error=str(e))

async def handle_whatsapp_message(message_data: dict):
    """Handle incoming WhatsApp message for classification"""
    try:
        start_time = time.time()
        
        # Create message context
        context = MessageContext(
            message_id=message_data.get('id', ''),
            sender=message_data.get('from', ''),
            group_id=message_data.get('groupId', ''),
            timestamp=datetime.fromtimestamp(message_data.get('timestamp', 0)),
            has_media=message_data.get('hasMedia', False),
            message_type=message_data.get('messageType', 'text')
        )
        
        # Classify the message
        classification = await classifier.classify(
            text=message_data.get('text', ''),
            context=context
        )
        
        # Set processing time
        classification.processing_time = time.time() - start_time
        
        # Prepare response data
        response_data = {
            "message_id": message_data.get('id'),
            "group_id": message_data.get('groupId'),
            "classification": classification.dict(),
            "timestamp": datetime.now().isoformat()
        }
        
        # Publish classification result
        if classification.is_support_incident:
            # Send to ticket service for incident processing
            await redis_client.publish_message('tickets:classify:result', response_data)
            
            # If high confidence, send suggested response back to WhatsApp
            if classification.confidence > 0.7 and classification.suggested_response:
                response_msg = {
                    "messageId": message_data.get('id'),
                    "groupId": message_data.get('groupId'),
                    "response": classification.suggested_response,
                    "responseType": "classification_response"
                }
                await redis_client.publish_message('agents:responses', response_msg)
        else:
            # Non-incident, log and optionally respond
            logger.info("Non-incident message classified", 
                       message_id=message_data.get('id'),
                       category=classification.category)
        
        logger.info("Message classification completed",
                   message_id=message_data.get('id'),
                   is_incident=classification.is_support_incident,
                   confidence=classification.confidence,
                   processing_time=classification.processing_time)
        
    except Exception as e:
        logger.error("Failed to handle WhatsApp message", 
                    message_id=message_data.get('id', 'unknown'),
                    error=str(e))

@app.get("/health", response_model=HealthResponse)
async def health_check():
    models_available = []
    if os.getenv('OPENAI_API_KEY'):
        models_available.append('openai')
    if os.getenv('GOOGLE_API_KEY'):
        models_available.append('google')
    if os.getenv('ANTHROPIC_API_KEY'):
        models_available.append('anthropic')
    
    return HealthResponse(
        status="healthy",
        service="classifier-service",
        timestamp=datetime.now(),
        models_available=models_available,
        redis_connected=redis_client.redis is not None
    )

@app.post("/classify", response_model=ClassificationResponse)
async def classify_message_endpoint(request: ClassificationRequest):
    """Manual classification endpoint for testing"""
    try:
        start_time = time.time()
        
        logger.info("Manual classification request", message_id=request.message.id)
        
        # Create context from request
        context = MessageContext(
            message_id=request.message.id,
            sender=request.message.from_user,
            group_id=request.message.group_id or "",
            timestamp=request.message.timestamp,
            has_media=request.message.has_media,
            message_type=request.message.message_type
        )
        
        result = await classifier.classify(
            text=request.message.text,
            context=context
        )
        
        result.processing_time = time.time() - start_time
        
        logger.info("Manual classification completed",
                   message_id=request.message.id,
                   is_incident=result.is_support_incident,
                   confidence=result.confidence)
        
        return result
        
    except Exception as e:
        logger.error("Manual classification failed", 
                    message_id=request.message.id,
                    error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    # TODO: Implement proper metrics collection
    return {
        "service": "classifier-service",
        "metrics_endpoint": "placeholder",
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', 8001))
    host = os.getenv('HOST', '0.0.0.0')
    uvicorn.run(app, host=host, port=port)