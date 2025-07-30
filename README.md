# WhatsApp Support Bot

Multi-agent WhatsApp support bot with microservices architecture for automated ticket creation in Zoho Desk.

## 🚀 Features

- **WhatsApp Integration**: Receives and processes messages via Baileys library
- **AI-Powered Classification**: Uses LangChain + GPT-4o-mini to detect support incidents
- **Automated Ticket Creation**: Creates tickets in Zoho Desk with fallback queuing
- **Microservices Architecture**: Scalable, containerized services with Docker
- **Redis Integration**: Message queuing and inter-service communication
- **Error Handling**: Circuit breaker patterns and automatic retry logic

## 📋 Prerequisites

- Docker and Docker Compose
- OpenAI API key
- Zoho Desk Self Client credentials
- Redis (included in docker-compose)

## 🛠️ Quick Start

### 1. Clone and Setup
```bash
git clone https://github.com/cristhianvs/whatsappbot.git
cd whatsappbot

# Copy environment template
cp .env.example .env
```

### 2. Configure Environment
Edit `.env` file with your credentials:
```bash
# Required
OPENAI_API_KEY=sk-your-openai-key-here
ZOHO_CLIENT_ID=1000.XXXXX
ZOHO_CLIENT_SECRET=xxxxx
ZOHO_AUTHORIZATION_CODE=1000.xxxxx
```

### 3. Start Services
```bash
# Start all services
docker-compose up -d

# Check service health
curl http://localhost:3000/health  # WhatsApp service
curl http://localhost:8001/health  # Classifier service  
curl http://localhost:8002/health  # Ticket service

# View logs
docker-compose logs -f
```

## 🏗️ Architecture

### Current Services (Phase 1)
- **whatsapp-service** (Node.js + Baileys): WhatsApp message handling
- **classifier-service** (Python FastAPI + LangChain): AI incident classification
- **ticket-service** (Python FastAPI): Zoho Desk integration with queuing
- **Redis**: Message broker and caching

### Message Flow
1. WhatsApp receives message → 2. AI classifies as incident → 3. Creates Zoho ticket → 4. Notifications sent

## 🧪 Testing

### API Endpoints
```bash
# Test message classification
curl -X POST http://localhost:8001/classify \
  -H "Content-Type: application/json" \
  -d '{"message_id":"test","text":"La impresora no funciona","user_id":"user123"}'

# Test ticket creation
curl -X POST http://localhost:8002/tickets \
  -H "Content-Type: application/json" \
  -d '{"subject":"Test","description":"Test ticket","priority":"normal","classification":"technical","contact_id":"123","department_id":"456","reporter_id":"user123"}'

# List Zoho departments
curl http://localhost:8002/departments
```

## 📚 Documentation

- **[CLAUDE.md](CLAUDE.md)**: Comprehensive development guide for Claude Code
- **[whatsapp-bot-specs.md](whatsapp-bot-specs.md)**: Full system specifications and future roadmap
- **Legacy Script**: `prueba.py` - Original proof-of-concept Zoho API client

## 🔄 Development Status

**✅ Phase 1 Complete:**
- Microservices architecture with Docker
- WhatsApp integration (Baileys)
- AI classification (LangChain + GPT-4o-mini)
- Zoho ticket creation with queuing
- Redis message broker

**🚧 Phase 2 Next Steps:**
- Conversation management service
- Information extractor with vision capabilities
- Vector database (ChromaDB) for RAG
- Frontend dashboard (React/Next.js)

## 🔧 Development

### Service Management
```bash
# Rebuild after code changes  
docker-compose build
docker-compose up -d

# View specific service logs
docker-compose logs -f whatsapp-service

# Stop all services
docker-compose down
```

### Code Quality
```bash
# Format Python code
black services/*/app/ --line-length 88

# Lint code
flake8 services/*/app/
```

## 📄 License

MIT License - see LICENSE file for details

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📞 Support

For issues and questions:
- Create an issue on GitHub
- Check the [CLAUDE.md](CLAUDE.md) documentation
- Review the [specifications document](whatsapp-bot-specs.md) 