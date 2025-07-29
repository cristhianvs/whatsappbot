# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python project for integrating with Zoho Desk API using Self Client OAuth2 authentication. The project is currently a proof-of-concept that demonstrates creating tickets and managing contacts in Zoho Desk. The specifications document (`whatsapp-bot-specs.md`) outlines a future multi-agent WhatsApp support bot system, but the current implementation is a simple Zoho API client.

## Development Environment Setup

### Using uv (recommended)
```bash
# Install dependencies
uv sync

# Run the main script
uv run prueba.py
```

### Using pip
```bash
# Install dependencies
pip install -r requirements.txt

# Run the main script
python prueba.py
```

## Development Commands

### Testing
```bash
# Run tests (when available)
pytest

# Run with coverage (when pytest is configured)
pytest --cov
```

### Code Quality
```bash
# Format code
black . --line-length 88

# Lint code
flake8 .
```

## Project Structure

### Current Implementation
- `prueba.py` - Main script demonstrating Zoho Desk API integration
- `requirements.txt` - Basic dependencies (requests)
- `pyproject.toml` - Project configuration with dev dependencies
- `self_client.json` - OAuth2 credentials storage (not tracked in git)

### Key Components in prueba.py

**Authentication Flow:**
- `obtener_tokens_desde_code()` - Exchanges authorization code for access/refresh tokens
- `refrescar_access_token()` - Refreshes expired access tokens
- `generar_url_authorization()` - Generates OAuth2 authorization URL

**Zoho Desk Operations:**
- `obtener_org_id()` - Gets organization ID
- `listar_departamentos()` - Lists available departments
- `crear_contacto_simple()` - Creates contacts in Zoho Desk
- `crear_ticket()` - Creates support tickets
- `obtener_estado_ticket()` - Monitors ticket status

## Configuration Requirements

Before running the script, update the following in `prueba.py`:
- `CLIENT_ID` - Zoho Self Client ID
- `CLIENT_SECRET` - Zoho Self Client Secret  
- `AUTHORIZATION_CODE` - OAuth2 authorization code (expires quickly)
- `REDIRECT_URI` - Must match the registered URI in Zoho Developer Console

## API Integration Details

**Zoho Desk API Endpoints Used:**
- Organizations: `https://desk.zoho.com/api/v1/organizations`
- Departments: `https://desk.zoho.com/api/v1/departments`
- Contacts: `https://desk.zoho.com/api/v1/contacts`
- Tickets: `https://desk.zoho.com/api/v1/tickets`

**Authentication Headers:**
- Authorization: `Zoho-oauthtoken {access_token}`
- orgId: Required in headers for all API calls

## Error Handling Patterns

The script includes basic error handling for:
- Expired authorization codes - generates new authorization URL
- Token expiration - automatic token refresh using refresh_token
- API errors - HTTP status code checking and detailed error logging

## Future Architecture (from specifications)

The specifications document outlines a comprehensive multi-agent WhatsApp bot system with:
- **Microservices**: WhatsApp service (Node.js), AI agents (Python/FastAPI), ticket management
- **AI Framework**: Multi-agent system using LangChain with GPT-4o-mini/Gemini/Grok
- **Message Queue**: Redis for handling system downtime
- **Vector Database**: ChromaDB for RAG and knowledge management
- **Frontend**: React/Next.js admin dashboard

This represents a significant architectural expansion from the current simple API client.