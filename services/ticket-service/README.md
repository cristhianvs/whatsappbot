# Ticket Service

Complete Zoho Desk integration service with OAuth2 authentication, customer management, and Redis queue fallback.

## Overview

This service handles all Zoho Desk operations including:
- OAuth2 authentication with automatic token refresh
- Customer contact search and creation
- Ticket creation with proper categorization
- Circuit breaker pattern with Redis queue fallback
- Comprehensive error handling and logging

## Current Status (Phase 1 Complete - August 2025)

✅ **Production Ready** - Successfully creating tickets from real WhatsApp messages
- OAuth2 Server-based Application working
- Customer contact management implemented
- Multiple tickets created successfully
- Redis queue fallback tested
- Processing real customer messages

## Quick Start with UV

### Prerequisites
- Python 3.9+
- [UV package manager](https://docs.astral.sh/uv/)
- Redis server
- Zoho Desk account with API access

### Installation
```bash
# Install UV if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
cd services/ticket-service
uv sync
```

### Zoho OAuth Setup (One-time)
```bash
# Automated setup (recommended)
uv run python setup_zoho_auth.py

# This will:
# 1. Start local callback server on port 8888
# 2. Generate authorization URL
# 3. Open browser for authorization
# 4. Capture and save authorization code
# 5. Update .env file automatically
```

### Running the Service
```bash
# Development mode with auto-reload
uv run uvicorn app.main:app --host 0.0.0.0 --port 8005 --reload

# Or using the dev script
uv run python scripts/dev.py serve
```

## Configuration

### Environment Variables (.env)
```bash
# Service Configuration
HOST=0.0.0.0
PORT=8003  # Use 8005 for local development
ENVIRONMENT=development

# Redis Configuration
REDIS_URL=redis://localhost:6379  # Use redis://redis:6379 for Docker

# Zoho OAuth Configuration
ZOHO_CLIENT_ID=1000.BIRTN2HYM9VW8MKKDGC0ACKLX34LGD
ZOHO_CLIENT_SECRET=515db890ead9e733c0600f1ea499c66da5b1041cde
ZOHO_REDIRECT_URI=http://localhost:8888/callback
ZOHO_SCOPE=Desk.tickets.ALL,Desk.contacts.ALL,Desk.basic.ALL
ZOHO_AUTHORIZATION_CODE=1000.xxx  # Auto-managed by service

# Default Contact (Optional)
DEFAULT_CONTACT_ID=813934000001132001
DEFAULT_CONTACT_EMAIL=cvelazco@turistore.com

# Circuit Breaker Configuration
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_TIMEOUT=30
TICKET_QUEUE_NAME=tickets:pending
```

## API Endpoints

### Health & Status
```bash
GET /health
```
Response:
```json
{
  "status": "healthy",
  "service": "ticket-service",
  "zoho_connected": true,
  "redis_connected": true,
  "queue_length": 0
}
```

### Customer Workflow (Production Ready)
```bash
POST /tickets/customer
  ?customer_email={email}
  &customer_name={name}
  &subject={subject}
  &description={description}
  &priority={High|Medium|Low}
```

This endpoint:
1. Searches for existing contact by email
2. Creates new contact if not found
3. Creates ticket under customer's contact
4. Customer receives email notifications

### Other Endpoints
- `GET /departments` - List Zoho departments
- `GET /auth/url` - Get new authorization URL
- `POST /tickets` - Create ticket (admin contact)
- `POST /queue/process` - Process queued tickets

## Production Features

### Customer Contact Management
```python
# Automatic contact workflow
1. Search by email → Found? Use existing
2. Not found? → Create new contact
3. Create ticket → Assign to customer contact
4. Result → Customer gets email notifications
```

### Successfully Created Tickets
- Ticket `813934000024065112` - WhatsApp User 8668
- Multiple customer tickets with proper contact assignment
- All customers receive email notifications

### OAuth2 Token Management
- Server-based Application (not Self Client)
- Automatic token refresh with 5-minute buffer
- Token persistence in `.env` file
- Comprehensive error handling

### Circuit Breaker Pattern
- Automatically queues tickets when Zoho is down
- Background processor runs every 30 seconds
- Preserves all ticket data during outages
- Automatic retry when service recovers

## Architecture

```
Classifier Result → Ticket Service → Zoho Desk API
                         ↓                ↑
                    Redis Queue ←─────────┘
                  (Fallback when Zoho unavailable)
```

### Redis Integration
- **Subscribes to**: `tickets:classify:result` - Classified incidents
- **Publishes to**: `tickets:created` - Successful ticket creation
- **Queue**: `tickets:pending` - Failed tickets for retry

## Testing

### Unit Tests
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app --cov-report=html

# Run specific test
uv run pytest tests/test_zoho_client.py -v
```

### Integration Testing
```bash
# Test customer workflow
uv run python test_customer_workflow.py

# Test direct ticket creation
uv run python test_direct_ticket.py

# Test with real WhatsApp data
uv run python whatsapp_to_zoho_integration.py
```

## Development Tools

### Helper Scripts
```bash
# OAuth setup
uv run python setup_zoho_auth.py

# Find your contact ID
uv run python get_my_id.py

# Development commands
uv run python scripts/dev.py test    # Run tests
uv run python scripts/dev.py format  # Format code
uv run python scripts/dev.py lint    # Lint code
```

### Debugging
```bash
# Check service health
curl http://localhost:8005/health

# Test ticket creation
curl -X POST "http://localhost:8005/tickets/customer" \
  -d "customer_email=test@example.com" \
  -d "customer_name=Test User" \
  -d "subject=Test Issue" \
  -d "description=Testing" \
  -d "priority=High"

# Get departments
curl http://localhost:8005/departments
```

## Troubleshooting

### Common Issues

**"Invalid authorization code"**
```bash
# Authorization codes expire in ~10 minutes
uv run python setup_zoho_auth.py
```

**"HTTP 422 errors"**
- Ensure department ID is valid
- Check contact email format
- Verify all required fields

**Redis connection errors**
```bash
# For local development
REDIS_URL=redis://localhost:6379

# For Docker
REDIS_URL=redis://redis:6379
```

**Queue not processing**
```bash
# Check queue status
curl http://localhost:8005/health

# Manual process
curl -X POST http://localhost:8005/queue/process
```

## Production Deployment

### Current Production Setup
- Running locally on port 8005
- Connected to Docker Redis
- OAuth tokens persisted
- Logs in `local_ticket.log`

### Docker Deployment
```bash
# Build and run
docker-compose up ticket-service
```

### Environment Best Practices
- Use `ENVIRONMENT=production`
- Secure OAuth credentials
- Regular token rotation
- Monitor queue length

## File Structure

```
ticket-service/
├── app/
│   ├── main.py              # FastAPI application
│   ├── services/
│   │   ├── zoho_client.py   # Complete Zoho API client
│   │   └── ticket_queue.py  # Redis queue management
│   ├── models/
│   │   └── schemas.py       # Data models
│   ├── utils/
│   │   └── redis_client.py  # Redis utilities
│   └── auth_server.py       # OAuth callback server
├── tests/                   # Test suite
├── scripts/
│   └── dev.py              # Development helpers
├── setup_zoho_auth.py      # OAuth setup script
├── test_customer_workflow.py # Customer testing
├── pyproject.toml          # UV configuration
└── README.md              # This file
```

## Integration with Other Services

### Classifier Service
- Sends classified incidents via Redis
- Includes category, priority, and confidence

### WhatsApp Service
- Original messages from customers
- Phone numbers converted to email format

## Next Steps (Phase 2)

1. **Conversation Service**: Collect customer emails via WhatsApp
2. **Ticket Updates**: Two-way sync with Zoho
3. **Attachments**: Support for images/documents
4. **Analytics**: Ticket metrics and reporting
5. **Multi-tenant**: Support multiple Zoho accounts

## Support

For issues or questions:
- Check logs for detailed errors
- Verify OAuth token is valid
- Ensure Redis connectivity
- Review Zoho API documentation
- Contact: cvelazco@turistore.com