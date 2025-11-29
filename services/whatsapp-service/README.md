# WhatsApp Service

Real-time WhatsApp integration service using Baileys library for the WhatsApp Support Bot system.

## Overview

This service handles all WhatsApp communication, including:
- Message reception and processing
- Session management and authentication
- Redis pub/sub integration
- Health monitoring and metrics

## Current Status (Phase 1 Complete - August 2025)

✅ **Production Ready** - Successfully processing real WhatsApp messages
- Real-time message reception working
- Redis publishing to classifier service
- Session persistence and backup
- Automatic reconnection handling
- Processing messages from phone number: +5215535128668

## Architecture

```
WhatsApp Web ←→ Baileys ←→ WhatsApp Service ←→ Redis Pub/Sub ←→ Other Services
```

### Redis Channels
- **Publishes to**: `whatsapp:messages:inbound` - Incoming WhatsApp messages
- **Subscribes to**: `whatsapp:messages:outbound` - Outgoing message requests (Phase 2)
- **Status channels**: `whatsapp:status`, `whatsapp:notifications`

## Quick Start

### Local Development
```bash
# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env with your configuration

# Start service
npm start
```

### Docker
```bash
# Build image
docker build -t whatsapp-service .

# Run container
docker run -p 3001:3001 whatsapp-service
```

**Note**: Currently experiencing initialization issues in Docker. Run locally for production.

## Configuration

### Environment Variables (.env)
```bash
# Service Configuration
PORT=3002
NODE_ENV=development
SERVICE_NAME=whatsapp-service

# Redis Configuration
REDIS_URL=redis://localhost:6379  # Use redis://redis:6379 for Docker

# WhatsApp Configuration
WHATSAPP_SESSION_NAME=bot-session
WHATSAPP_PHONE_NUMBER=5215530482752:1
WHATSAPP_PRINT_QR=true
WHATSAPP_MARK_ONLINE=false

# Logging
LOG_LEVEL=info
LOG_FILE=./logs/whatsapp-service.log
```

## API Endpoints

### Health Check
```bash
GET /api/health
```
Response:
```json
{
  "status": "healthy",
  "service": "whatsapp-service",
  "whatsapp_connected": true,
  "uptime": 93.09,
  "memory": {...}
}
```

### WhatsApp Status
```bash
GET /api/status
```
Returns current WhatsApp connection status and session info.

### Send Message (Phase 2)
```bash
POST /api/send
Content-Type: application/json

{
  "to": "5215535128668@s.whatsapp.net",
  "message": "Hello from bot"
}
```

### Session Management
```bash
# Get session info
GET /api/session

# Create backup
POST /api/session/backup

# Restart connection
POST /api/restart
```

## Message Flow

1. **Incoming Message**: WhatsApp → Baileys → Message Handler → Redis Publish
2. **Message Structure** published to Redis:
```json
{
  "id": "3A5F7272DCE691613281",
  "text": "La impresora no funciona",
  "from": "5215535128668@s.whatsapp.net",
  "timestamp": "2025-08-04T06:08:37.000Z",
  "type": "text",
  "pushName": "User Name"
}
```

## Session Management

### Initial Setup
1. Start the service
2. Scan QR code displayed in console (if WHATSAPP_PRINT_QR=true)
3. Session files saved to `sessions/bot-session/`

### Session Backup
- Automatic backups on critical events
- Manual backup via API endpoint
- Backups stored in `sessions/backups/`

### Session Recovery
```bash
# If session corrupted
rm -rf sessions/bot-session/*
npm start  # Scan new QR code
```

## Production Deployment

### Current Production Setup
- Running locally on port 3002
- Redis connection to Docker container
- Session files persisted locally
- Logs in `whatsapp.log`

### Environment Considerations
- Use `NODE_ENV=production`
- Set appropriate log levels
- Configure session backup strategy
- Monitor health endpoints

### Known Issues
- Docker container has initialization loop (investigating)
- Workaround: Run locally with localhost Redis configuration

## Monitoring

### Health Checks
```bash
# Simple health check
curl http://localhost:3002/api/health

# Detailed status
curl http://localhost:3002/api/status
```

### Logs
- Application logs: `logs/whatsapp-service.log`
- Console output with structured logging
- Redis pub/sub events logged with timestamps

### Real-Time Message Monitoring
```bash
# View incoming messages
tail -f whatsapp.log | grep "Message received"

# Monitor Redis publishing
tail -f whatsapp.log | grep "Message published to Redis"
```

## Troubleshooting

### Connection Issues
```bash
# Check logs
tail -f whatsapp.log

# Restart service
npm start

# Clear session
rm -rf sessions/bot-session/*
```

### Redis Connection
```bash
# Verify Redis is running
docker ps | grep redis

# Check Redis URL in .env
REDIS_URL=redis://localhost:6379
```

### WhatsApp Not Connecting
1. Delete session files
2. Restart service
3. Scan new QR code
4. Check network connectivity

## Development

### Project Structure
```
whatsapp-service/
├── src/
│   ├── index.js              # Express server
│   ├── whatsapp-service.js   # Main service logic
│   ├── handlers/
│   │   ├── message-handler.js    # Process messages
│   │   ├── connection-handler.js # Connection events
│   │   └── outbound-handler.js   # Send messages
│   ├── utils/
│   │   ├── logger.js         # Winston logging
│   │   ├── config.js         # Configuration
│   │   └── redis-publisher.js # Redis integration
│   └── api/
│       └── routes.js         # REST endpoints
├── sessions/                 # WhatsApp sessions
├── logs/                     # Application logs
└── package.json
```

### Production Messages Processed
Recent real WhatsApp messages successfully processed:
- "No funciona la impresora" - 00:08:37
- Multiple test messages with technical keywords
- All messages published to Redis with 3-4 subscribers

## Integration with Other Services

### Classifier Service
- Subscribes to `whatsapp:messages:inbound`
- Classifies messages as support incidents
- Publishes to `tickets:classify:result`

### Ticket Service
- Receives classified incidents
- Creates tickets in Zoho Desk
- Manages customer contacts

## Next Steps (Phase 2)

1. **Two-way messaging**: Implement outbound message handling
2. **Media support**: Process images and documents
3. **Typing indicators**: Show bot is processing
4. **Message templates**: Quick replies and buttons
5. **Fix Docker deployment**: Resolve initialization loop

## Testing

### Manual Testing
```bash
# Start service
npm start

# Send test message via WhatsApp
# Monitor logs for processing

# Check message in logs
tail -f whatsapp.log | grep "3A5F7272DCE691613281"
```

### Integration Testing
```bash
# Run complete flow test
cd services/ticket-service
uv run python ../../whatsapp_to_zoho_integration.py

# Send WhatsApp message with keywords
# Verify ticket creation in Zoho
```

## Support

For issues or questions:
- Check logs in `whatsapp.log`
- Review Redis connectivity
- Ensure WhatsApp session is valid
- Contact: cvelazco@turistore.com