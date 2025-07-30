# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a multi-microservice WhatsApp support bot system that integrates with Zoho Desk for ticket management. The system uses AI-powered message classification to automatically process support incidents from WhatsApp groups.

**Architecture**: Microservices with FastAPI (Python) and Node.js, Redis messaging, Docker deployment

## Development Environment Setup

### Prerequisites
- Docker and Docker Compose
- Node.js 18+ (for local WhatsApp service development)
- Python 3.8+ (for local AI services development)
- Redis (included in Docker Compose)

### Quick Start
```bash
# Clone and navigate to project
cd whatsappbot

# Copy and configure environment files
cp .env.example .env
cp services/whatsapp-service/.env.example services/whatsapp-service/.env
cp services/classifier-service/.env.example services/classifier-service/.env
cp services/ticket-service/.env.example services/ticket-service/.env

# Start all services with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f
```

### Local Development
```bash
# WhatsApp Service (Node.js)
cd services/whatsapp-service
npm install
npm run dev

# Classifier Service (Python)
cd services/classifier-service
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# Ticket Service (Python)
cd services/ticket-service
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```

## Service Architecture

### Current Services

#### 1. WhatsApp Service (Port 3001) - Node.js
- **Purpose**: WhatsApp integration using Baileys library
- **Key Components**:
  - `src/whatsapp-service.js` - Core Baileys integration and message handling
  - `src/api/routes.js` - REST API endpoints for external communication
  - `src/handlers/responseHandler.js` - Redis subscriber for agent responses
- **Redis Channels**: 
  - Publishes to: `whatsapp:messages:inbound`
  - Subscribes to: `agents:responses`, `tickets:created`, `tickets:updated`

#### 2. Classifier Service (Port 8001) - Python FastAPI
- **Purpose**: AI-powered message classification for support incidents
- **Key Components**:
  - `app/ai/model_manager.py` - Multi-model AI integration (OpenAI, Google, Anthropic)
  - `app/agents/classifier.py` - Message classification logic with fallback
  - `app/main.py` - FastAPI app with Redis subscriber
- **AI Integration**: Direct API clients (no LangChain dependency)
- **Models Supported**: GPT-4o-mini (primary), Gemini (fallback), Claude (fallback)
- **Redis Channels**:
  - Subscribes to: `whatsapp:messages:inbound`
  - Publishes to: `tickets:classify:result`, `agents:responses`

#### 3. Ticket Service (Port 8003) - Python FastAPI
- **Purpose**: Zoho Desk integration and ticket management
- **Key Components**:
  - `app/services/zoho_client.py` - Zoho Desk API integration
  - `app/services/ticket_queue.py` - Queue management for ticket processing
- **Redis Channels**:
  - Subscribes to: `tickets:classify:result`
  - Publishes to: `tickets:created`, `tickets:updated`

### Message Flow
1. **WhatsApp** → `whatsapp:messages:inbound` → **Classifier Service**
2. **Classifier** → `tickets:classify:result` → **Ticket Service** (if support incident)
3. **Classifier** → `agents:responses` → **WhatsApp Service** (immediate responses)
4. **Ticket Service** → `tickets:created`/`tickets:updated` → **WhatsApp Service**

## Configuration Requirements

### WhatsApp Service (.env)
```env
PORT=3001
WHATSAPP_GROUP_ID=120363xxxxxx@g.us  # Target WhatsApp group
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Classifier Service (.env)
```env
PORT=8001
PRIMARY_AI_MODEL=openai
FALLBACK_AI_MODEL=google
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
MODEL_TEMPERATURE=0.1
MAX_TOKENS=1000
```

### Ticket Service (.env)
```env
PORT=8003
ZOHO_CLIENT_ID=...
ZOHO_CLIENT_SECRET=...
ZOHO_ORG_ID=...
ZOHO_REFRESH_TOKEN=...
```

## Development Commands

### Docker Operations
```bash
# Build and start all services
docker-compose up --build

# Start specific service
docker-compose up whatsapp-service

# View service logs
docker-compose logs -f classifier-service

# Restart service
docker-compose restart ticket-service

# Stop all services
docker-compose down
```

### Testing Services
```bash
# Test WhatsApp service health
curl http://localhost:3001/health

# Test classifier service
curl -X POST http://localhost:8001/classify \
  -H "Content-Type: application/json" \
  -d '{"message": {"id": "test", "text": "El sistema POS no funciona", "from_user": "test", "timestamp": "2024-01-01T00:00:00Z"}}'

# Test ticket service health
curl http://localhost:8003/health
```

### Code Quality
```bash
# Python services
black services/classifier-service/app --line-length 88
black services/ticket-service/app --line-length 88
flake8 services/classifier-service/app
flake8 services/ticket-service/app

# Node.js service
cd services/whatsapp-service
npm run lint # (if configured)
```

## API Endpoints

### WhatsApp Service (Port 3001)
- `GET /health` - Health check
- `POST /api/send-message` - Send WhatsApp message
- `GET /api/status` - Connection status

### Classifier Service (Port 8001)
- `GET /health` - Health check with AI models status
- `POST /classify` - Manual message classification
- `GET /metrics` - Prometheus metrics

### Ticket Service (Port 8003)
- `GET /health` - Health check with Zoho connection status
- `POST /tickets` - Create ticket manually
- `GET /tickets/{id}` - Get ticket status

## Error Handling Patterns

### Circuit Breaker Pattern
- Implemented in ticket service for Zoho API failures
- Automatic fallback to Redis queue when Zoho is unavailable

### AI Model Fallback
- Primary model fails → Try fallback model → Use keyword-based classification
- All classification results include confidence scores

### Redis Connection Recovery
- All services implement Redis reconnection logic
- Message processing continues after Redis reconnection

## Monitoring and Debugging

### Logs
```bash
# View all service logs
docker-compose logs -f

# View specific service logs with timestamps
docker-compose logs -f --timestamps classifier-service

# Filter logs by level
docker-compose logs -f | grep ERROR
```

### Redis Monitoring
```bash
# Connect to Redis container
docker-compose exec redis redis-cli

# Monitor Redis pub/sub messages
MONITOR

# Check active channels
PUBSUB CHANNELS *
```

### Health Checks
All services provide detailed health endpoints that include:
- Service status
- Dependencies status (Redis, AI APIs, Zoho)
- Version information
- Startup time

## Future Enhancements

The system is designed for easy extension:
- **Conversation Service**: For complex multi-turn conversations
- **Vector Search Service**: For RAG and knowledge base queries  
- **Analytics Service**: For metrics and reporting
- **Admin Dashboard**: React/Next.js frontend
- **Multi-tenant Support**: For multiple WhatsApp groups/organizations