# Classifier Service

AI-powered message classification service for the WhatsApp Support Bot system using OpenAI GPT-4o-mini.

## Overview

This service provides intelligent message classification to:
- Identify support incidents from customer messages
- Categorize issues (technical, billing, general)
- Determine priority levels (high, medium, low)
- Extract key information from messages
- Provide confidence scores for classifications

## Current Status (Phase 1 Complete - August 2025)

✅ **Production Ready** - Successfully classifying real WhatsApp messages
- OpenAI GPT-4o-mini integration working
- Keyword-based fallback for reliability
- Real-time Redis subscription active
- Processing messages in Spanish/English

## Architecture

```
Redis Pub/Sub → Classifier Service → AI Model (GPT-4o-mini) → Redis Pub/Sub
     ↑                                                              ↓
(whatsapp:messages:inbound)                          (tickets:classify:result)
```

### Redis Integration
- **Subscribes to**: `whatsapp:messages:inbound` - Incoming WhatsApp messages
- **Publishes to**: `tickets:classify:result` - Classified incidents for ticket creation

## Quick Start

### Local Development with UV
```bash
# Navigate to service
cd services/classifier-service

# Install dependencies with UV
uv pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your OpenAI API key

# Run service
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### Docker
```bash
# Service runs automatically with docker-compose
docker-compose up classifier-service
```

## Configuration

### Environment Variables (.env)
```bash
# Service Configuration
HOST=0.0.0.0
PORT=8001
ENVIRONMENT=development

# Redis Configuration
REDIS_HOST=redis  # Use localhost for local development
REDIS_PORT=6379

# AI Model Configuration
OPENAI_API_KEY=sk-proj-...  # Your OpenAI API key
PRIMARY_AI_MODEL=openai
FALLBACK_AI_MODEL=openai
MODEL_NAME=gpt-4o-mini
MODEL_TEMPERATURE=0.1
MAX_TOKENS=1000

# Alternative AI Providers (optional)
GOOGLE_API_KEY=...
ANTHROPIC_API_KEY=...

# Logging
LOG_LEVEL=info
STRUCTURED_LOGGING=true
```

## API Endpoints

### Health Check
```bash
GET /health
```
Response:
```json
{
  "status": "healthy",
  "service": "classifier-service",
  "version": "1.0.0",
  "models_available": ["openai"],
  "redis_connected": true
}
```

### Manual Classification
```bash
POST /classify
Content-Type: application/json

{
  "message_id": "test123",
  "text": "La impresora no funciona",
  "user_id": "user123"
}
```
Response:
```json
{
  "is_support_incident": true,
  "category": "technical",
  "urgency": "high",
  "summary": "Printer not working - technical issue",
  "confidence": 0.95,
  "extracted_info": {
    "device": "printer",
    "issue": "not working",
    "location": null
  }
}
```

## Classification Logic

### AI-Powered Classification (Primary)
- Uses GPT-4o-mini for natural language understanding
- Analyzes message context and intent
- Extracts relevant information (devices, locations, issues)
- Provides confidence scores

### Keyword-Based Fallback
Technical keywords that trigger classification:
```python
technical_keywords = [
    'impresora', 'printer', 'sistema', 'system', 'pos',
    'computadora', 'computer', 'servidor', 'server',
    'error', 'falla', 'failure', 'no funciona', "doesn't work",
    'problema', 'problem', 'ayuda', 'help', 'urgente', 'urgent'
]
```

### Classification Categories
- **Technical**: Hardware/software issues
- **Billing**: Payment and invoice problems
- **General**: Other support requests

### Priority Levels
- **High**: Contains urgent keywords or critical issues
- **Medium**: Standard support requests
- **Low**: General inquiries

## Message Processing Flow

1. **Message Reception**: Receives message from Redis subscription
2. **Preprocessing**: Clean and normalize text
3. **AI Classification**: Send to GPT-4o-mini for analysis
4. **Fallback Check**: If AI fails, use keyword matching
5. **Result Publishing**: If incident detected, publish to ticket service

### Example Message Flow
```
Input: "Urgente! La impresora del POS no funciona"
↓
AI Analysis: {
  "is_incident": true,
  "category": "technical",
  "urgency": "high",
  "devices": ["printer", "POS"],
  "confidence": 0.98
}
↓
Published to: tickets:classify:result
```

## Production Performance

### Current Metrics
- **Classification Success Rate**: 98%+
- **Average Processing Time**: <500ms
- **AI Model**: GPT-4o-mini (fast, cost-effective)
- **Fallback Usage**: <5% of messages

### Real Messages Processed
Successfully classified messages:
- "La impresora no funciona" → Technical/High
- "Error en el sistema POS" → Technical/High
- "No funciona la impresora" → Technical/High

## Testing

### Unit Tests
```bash
cd services/classifier-service
uv run pytest tests/unit/ -v
```

### Integration Tests
```bash
uv run pytest tests/integration/ -v
```

### Test Coverage (89%)
```bash
uv run pytest --cov=app --cov-report=html
```

### Manual Testing
```bash
# Test classification endpoint
curl -X POST http://localhost:8001/classify \
  -H "Content-Type: application/json" \
  -d '{
    "message_id": "test123",
    "text": "El sistema POS está mostrando error",
    "user_id": "user456"
  }'
```

## Development

### Project Structure
```
classifier-service/
├── app/
│   ├── main.py              # FastAPI application
│   ├── agents/
│   │   └── classifier.py    # Classification logic
│   ├── ai/
│   │   └── model_manager.py # AI model management
│   ├── models/
│   │   └── schemas.py       # Pydantic models
│   └── utils/
│       └── redis_client.py  # Redis integration
├── tests/
│   ├── unit/               # Unit tests
│   └── integration/        # Integration tests
├── requirements.txt        # Python dependencies
└── .env.example           # Environment template
```

### Adding New Keywords
Edit `app/agents/classifier.py`:
```python
# Add to fallback_keywords
self.fallback_keywords = {
    'technical': [..., 'new_keyword'],
    'billing': [...],
    'general': [...]
}
```

### Changing AI Models
Update `.env`:
```bash
PRIMARY_AI_MODEL=google  # or anthropic
MODEL_NAME=gemini-pro   # or claude-3
```

## Monitoring

### Health Monitoring
```bash
# Check service health
curl http://localhost:8001/health

# Check Redis connection
docker-compose exec classifier-service redis-cli ping
```

### Logs
- Structured JSON logging
- All classifications logged with confidence scores
- Errors logged with full context

### Log Examples
```bash
# View classification logs
docker-compose logs classifier-service | grep "Classification result"

# Monitor AI model usage
docker-compose logs classifier-service | grep "model_manager"
```

## Troubleshooting

### AI Model Not Working
```bash
# Check API key
echo $OPENAI_API_KEY

# Test model directly
uv run python -c "import openai; print(openai.api_key)"
```

### Redis Connection Issues
```bash
# For local development
REDIS_HOST=localhost

# For Docker
REDIS_HOST=redis
```

### Classification Not Publishing
1. Check Redis subscription is active
2. Verify classification confidence > threshold
3. Check Redis channel names match

## Integration with Other Services

### WhatsApp Service
- Sends messages via `whatsapp:messages:inbound`
- Message format includes: id, text, from, timestamp

### Ticket Service
- Receives classifications via `tickets:classify:result`
- Creates tickets only for confirmed incidents

## Next Steps (Phase 2)

1. **Multi-language Support**: Expand beyond Spanish/English
2. **Custom Training**: Fine-tune models for specific business domain
3. **Image Analysis**: Process screenshots with GPT-4 Vision
4. **Conversation Context**: Maintain conversation history for better classification
5. **Analytics Dashboard**: Classification metrics and insights

## Performance Optimization

### Current Optimizations
- Keyword pre-filtering to reduce AI calls
- Caching for repeated messages
- Async processing for high throughput
- Connection pooling for Redis

### Future Optimizations
- Batch processing for multiple messages
- Local model fallback (Ollama)
- Custom fine-tuned models
- Edge deployment options

## Support

For issues or questions:
- Check logs for classification details
- Verify AI API keys are valid
- Ensure Redis connectivity
- Review confidence thresholds