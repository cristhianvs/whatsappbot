# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **multi-agent WhatsApp support bot** with microservices architecture for automated ticket creation in Zoho Desk. The project has evolved from a simple proof-of-concept (`prueba.py`) into a comprehensive microservices system implementing Phase 1 of the specifications outlined in `whatsapp-bot-specs.md`.

## Current Implementation Status (Phase 1 Complete)

### ✅ Completed Components:
- **Microservices Architecture**: Complete Docker Compose setup with service isolation
- **WhatsApp Service** (Node.js + Baileys): Message handling and Redis pub/sub integration
- **Classifier Service** (Python FastAPI + LangChain): AI-powered incident classification using GPT-4o-mini
- **Ticket Service** (Python FastAPI): Complete Zoho Desk integration with circuit breaker pattern
- **Redis Integration**: Message queuing, caching, and inter-service communication
- **Environment Configuration**: Secure credential management with `.env` files
- **Docker Containerization**: All services containerized with health checks

### 🔄 Current Capabilities:
- WhatsApp message reception and forwarding
- AI-powered message classification for support incidents
- Automatic ticket creation in Zoho Desk with fallback queuing
- Token management with automatic refresh
- Error handling and retry mechanisms
- Structured logging across all services

## Development Environment Setup

### Docker Compose (Recommended for Development)
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your API keys and credentials
# Required: ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_AUTHORIZATION_CODE, OPENAI_API_KEY

# Start all services
docker-compose up -d

# Check service health
curl http://localhost:3000/health  # WhatsApp service
curl http://localhost:8001/health  # Classifier service  
curl http://localhost:8002/health  # Ticket service

# View logs
docker-compose logs -f
```

### Legacy Script (Original Proof of Concept)
```bash
# Install dependencies
pip install -r requirements.txt

# Run the original script
python prueba.py
```

## Development Commands

### Service Management
```bash
# Start specific service
docker-compose up whatsapp-service -d
docker-compose up classifier-service -d  
docker-compose up ticket-service -d

# Rebuild services after code changes
docker-compose build
docker-compose up -d

# Stop all services
docker-compose down

# View service logs
docker-compose logs -f [service-name]
```

### API Testing
```bash
# Test classifier service
curl -X POST http://localhost:8001/classify \
  -H "Content-Type: application/json" \
  -d '{"message_id":"test","text":"La impresora no funciona","user_id":"user123"}'

# Test ticket creation
curl -X POST http://localhost:8002/tickets \
  -H "Content-Type: application/json" \
  -d '{"subject":"Test","description":"Test ticket","priority":"normal","classification":"technical","contact_id":"123","department_id":"456","reporter_id":"user123"}'

# Get departments from Zoho
curl http://localhost:8002/departments
```

### Code Quality (for Python services)
```bash
# Format code
black services/*/app/ --line-length 88

# Lint code  
flake8 services/*/app/
```

## Project Structure

### Microservices Architecture
```
/
├── services/
│   ├── whatsapp-service/          # Node.js + Baileys WhatsApp integration
│   │   ├── src/
│   │   │   ├── index.js           # Main server
│   │   │   ├── whatsapp-service.js # WhatsApp connection logic
│   │   │   └── utils/logger.js    # Winston logging
│   │   ├── package.json           # Node.js dependencies
│   │   └── Dockerfile
│   │
│   ├── classifier-service/        # Python FastAPI + LangChain
│   │   ├── app/
│   │   │   ├── main.py           # FastAPI application
│   │   │   ├── agents/classifier.py # LangChain classification agent
│   │   │   ├── models/schemas.py  # Pydantic models
│   │   │   └── utils/redis_client.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   └── ticket-service/            # Python FastAPI + Zoho integration
│       ├── app/
│       │   ├── main.py           # FastAPI application
│       │   ├── services/
│       │   │   ├── zoho_client.py # Migrated from prueba.py
│       │   │   └── ticket_queue.py # Redis queue management
│       │   ├── models/schemas.py  # Ticket data models
│       │   └── utils/redis_client.py
│       ├── requirements.txt
│       └── Dockerfile
│
├── docker-compose.yml             # Service orchestration
├── .env.example                   # Environment template
├── .gitignore                     # Git ignore rules
├── CLAUDE.md                      # This documentation
├── README.md                      # Project documentation
├── whatsapp-bot-specs.md          # Full system specifications
└── prueba.py                      # Legacy proof-of-concept script

## Configuration Requirements

### Environment Variables (.env file)
```bash
# Required for all services
REDIS_URL=redis://localhost:6379

# WhatsApp Service
NODE_ENV=development
LOG_LEVEL=info

# AI Classification (OpenAI)
OPENAI_API_KEY=sk-your-openai-key-here
OPENAI_MODEL=gpt-4o-mini

# Zoho Desk Integration
ZOHO_CLIENT_ID=1000.XXXXX
ZOHO_CLIENT_SECRET=xxxxx
ZOHO_REDIRECT_URI=https://www.zoho.com
ZOHO_AUTHORIZATION_CODE=1000.xxxxx  # Expires every ~10 minutes, needs refresh

# Optional: Alternative AI providers
GEMINI_API_KEY=your-gemini-key-here
GROK_API_KEY=your-grok-key-here
```

### Getting Zoho Authorization Code
If the authorization code expires, use the ticket service endpoint:
```bash
# Get new authorization URL
curl http://localhost:8002/auth/url

# Or run the legacy script function
python -c "from prueba import generar_url_authorization; generar_url_authorization()"
```

## Service Communication Flow

### Current Message Processing Pipeline:
1. **WhatsApp Service** receives messages via Baileys
2. Publishes to Redis channel `whatsapp:messages:inbound`
3. **Classifier Service** processes message for incident detection
4. If incident detected, **Ticket Service** creates Zoho ticket
5. Success/failure events published to `tickets:created` channel

### API Integration Details

**Zoho Desk API Integration (services/ticket-service):**
- OAuth2 Self Client authentication with automatic token refresh
- Circuit breaker pattern for Zoho downtime
- Redis queue fallback when Zoho is unavailable
- Complete CRUD operations for tickets, contacts, departments

**LangChain AI Integration (services/classifier-service):**
- GPT-4o-mini for message classification
- Retail-specific incident detection keywords
- Confidence scoring and priority assignment
- Fallback classification logic

## Next Phase Implementation (Phase 2)

### Immediate Next Steps:
1. **Create conversation-service** for missing information collection
2. **Add information extractor agent** with vision capabilities for screenshots
3. **Implement vector database (ChromaDB)** for RAG and knowledge management
4. **Create basic frontend dashboard** for monitoring and configuration

### Missing Components from Full Specification:
- **Vector Database Service**: ChromaDB for conversation history and RAG
- **Conversation Management**: Thread tracking and missing info collection
- **Information Extractor**: Vision-capable agent for screenshot analysis
- **Frontend Dashboard**: React/Next.js admin interface
- **Advanced Features**: Voice transcription, multi-language support, analytics

### Development Priority Order:
1. Test current Phase 1 services end-to-end
2. Implement conversation-service for interactive info collection
3. Add ChromaDB vector database service
4. Create information extractor with vision capabilities
5. Build basic React dashboard for monitoring
6. Add advanced features and optimizations

This microservices foundation provides the infrastructure needed to implement the remaining components from the full specification document.