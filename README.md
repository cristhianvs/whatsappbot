# WhatsApp Support Bot with AI Classification

Sistema de bot de soporte inteligente que integra WhatsApp con Zoho Desk usando clasificación AI multi-modelo para procesamiento automático de incidentes.

## 🏗️ Arquitectura del Sistema

### Microservicios
- **WhatsApp Service** (Node.js): Integración con WhatsApp usando Baileys
- **Classifier Service** (Python/FastAPI): Clasificación IA de mensajes
- **Ticket Service** (Python/FastAPI): Integración con Zoho Desk
- **Redis**: Message broker y sistema de colas
- **Docker Compose**: Orquestación de servicios

### Flujo de Datos
```
WhatsApp → WhatsApp Service → Redis → Classifier Service → Ticket Service → Zoho Desk
                                        ↓
                                   Response Handler → WhatsApp
```

## 🚀 Instalación y Configuración

### Prerrequisitos
- Docker y Docker Compose
- Node.js 18+ (desarrollo local)
- Python 3.8+ (desarrollo local)
- Cuenta Zoho Desk con API habilitada
- API Keys de OpenAI/Google/Anthropic

### Configuración Rápida

1. **Clonar el repositorio**
```bash
git clone <repository-url>
cd whatsappbot
```

2. **Configurar variables de entorno**
```bash
# Copiar archivos de ejemplo
cp .env.example .env
cp services/whatsapp-service/.env.example services/whatsapp-service/.env
cp services/classifier-service/.env.example services/classifier-service/.env
cp services/ticket-service/.env.example services/ticket-service/.env
```

3. **Configurar credenciales en los archivos .env**

#### WhatsApp Service (.env)
```env
PORT=3001
WHATSAPP_GROUP_ID=120363xxxxxx@g.us  # ID del grupo de WhatsApp
REDIS_HOST=localhost
REDIS_PORT=6379
CLASSIFIER_SERVICE_URL=http://localhost:8001
TICKET_SERVICE_URL=http://localhost:8003
```

#### Classifier Service (.env)
```env
PORT=8001
PRIMARY_AI_MODEL=openai
FALLBACK_AI_MODEL=google
OPENAI_API_KEY=sk-proj-xxxxx
GOOGLE_API_KEY=AIzaSyxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxx
MODEL_TEMPERATURE=0.1
MAX_TOKENS=1000
```

#### Ticket Service (.env)
```env
PORT=8003
ZOHO_CLIENT_ID=1000.XXXXXXXXXXXXXXXX
ZOHO_CLIENT_SECRET=xxxxxxxxxxxxxxxx
ZOHO_REDIRECT_URI=http://localhost:8003/auth/callback
ZOHO_AUTHORIZATION_CODE=1000.xxxxxxxx  # Temporal, se obtiene del flujo OAuth
ZOHO_ORG_ID=123456789
```

### Configuración de Zoho Desk

1. **Crear Self Client en Zoho Developer Console**
   - Ir a https://api-console.zoho.com/
   - Crear nueva aplicación → Self Client
   - Configurar scopes: `Desk.tickets.ALL,Desk.contacts.ALL,Desk.basic.READ`
   - Obtener Client ID y Client Secret

2. **Obtener Authorization Code**
```bash
# Generar URL de autorización (ejecutar prueba.py o usar endpoint del servicio)
https://accounts.zoho.com/oauth/v2/auth?response_type=code&client_id=CLIENT_ID&redirect_uri=REDIRECT_URI&scope=Desk.tickets.ALL,Desk.contacts.ALL,Desk.basic.READ
```

3. **Obtener Organization ID**
   - En Zoho Desk: Settings → Developer Space → API → Organization ID

## 🐳 Despliegue con Docker

### Iniciar todos los servicios
```bash
# Construir e iniciar
docker-compose up --build -d

# Ver logs
docker-compose logs -f

# Ver logs de servicio específico
docker-compose logs -f whatsapp-service
```

### Comandos útiles
```bash
# Detener servicios
docker-compose down

# Reiniciar servicio específico
docker-compose restart classifier-service

# Verificar estado
docker-compose ps

# Conectar a Redis
docker-compose exec redis redis-cli
```

## 🛠️ Desarrollo Local

### WhatsApp Service (Node.js)
```bash
cd services/whatsapp-service
npm install
npm run dev
```

### Classifier Service (Python)
```bash
cd services/classifier-service
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### Ticket Service (Python)
```bash
cd services/ticket-service
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```

## 🧪 Testing y Verificación

### Health Checks
```bash
# WhatsApp Service
curl http://localhost:3001/health

# Classifier Service
curl http://localhost:8001/health

# Ticket Service
curl http://localhost:8003/health
```

### Testing Manual

#### Clasificación de Mensajes
```bash
curl -X POST http://localhost:8001/classify \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "id": "test-123",
      "text": "El sistema POS no funciona en la tienda",
      "from_user": "+573001234567",
      "timestamp": "2024-01-01T10:00:00Z",
      "group_id": "120363xxxxxx@g.us",
      "has_media": false,
      "message_type": "text"
    }
  }'
```

#### Creación Manual de Tickets
```bash
curl -X POST http://localhost:8003/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Sistema POS no funciona",
    "description": "El sistema POS de la tienda principal no está funcionando",
    "priority": "urgent",
    "classification": "technical",
    "contact_id": "123456789",
    "department_id": "987654321"
  }'
```

### Monitoreo Redis
```bash
# Conectar a Redis
docker-compose exec redis redis-cli

# Monitorear mensajes pub/sub
MONITOR

# Ver canales activos
PUBSUB CHANNELS *

# Ver longitud de colas
LLEN pending_tickets
```

## 📊 API Endpoints

### WhatsApp Service (Puerto 3001)
- `GET /health` - Estado del servicio
- `GET /api/status` - Estado de conexión WhatsApp
- `POST /api/send-message` - Enviar mensaje
  ```json
  {
    "jid": "120363xxxxxx@g.us",
    "text": "Mensaje a enviar",
    "mentions": []
  }
  ```

### Classifier Service (Puerto 8001)
- `GET /health` - Estado del servicio y modelos AI
- `POST /classify` - Clasificar mensaje manualmente
- `GET /metrics` - Métricas Prometheus

### Ticket Service (Puerto 8003)
- `GET /health` - Estado del servicio y conexión Zoho
- `POST /tickets` - Crear ticket manualmente
- `GET /tickets/{id}/status` - Estado de ticket
- `GET /departments` - Listar departamentos Zoho
- `POST /contacts` - Crear contacto
- `POST /queue/process` - Procesar cola manualmente

## 🔧 Configuración Avanzada

### Modelos AI Soportados
- **OpenAI**: GPT-4o-mini (recomendado para producción)
- **Google**: Gemini Pro (alternativa rápida)
- **Anthropic**: Claude Haiku (alternativa premium)

### Configuración de Fallback
El sistema implementa fallback automático:
1. Modelo primario (OpenAI)
2. Modelo secundario (Google/Anthropic)  
3. Clasificación por palabras clave

### Circuit Breaker
- Zoho API failures → Ticket queue
- AI API failures → Keyword classification
- Redis failures → Local logging

## 📁 Estructura del Proyecto

```
whatsappbot/
├── services/
│   ├── whatsapp-service/          # Node.js - Baileys integration
│   │   ├── src/
│   │   │   ├── whatsapp-service.js
│   │   │   ├── api/routes.js
│   │   │   └── handlers/responseHandler.js
│   │   └── package.json
│   ├── classifier-service/        # Python - AI classification
│   │   ├── app/
│   │   │   ├── ai/model_manager.py
│   │   │   ├── agents/classifier.py
│   │   │   └── main.py
│   │   └── requirements.txt
│   └── ticket-service/            # Python - Zoho integration
│       ├── app/
│       │   ├── services/zoho_client.py
│       │   ├── services/ticket_queue.py
│       │   └── main.py
│       └── requirements.txt
├── docker-compose.yml
├── .env
└── README.md
```

## 🚨 Troubleshooting

### Problemas Comunes

#### WhatsApp no conecta
- Verificar QR code en logs: `docker-compose logs whatsapp-service`
- Escanear QR con WhatsApp → Dispositivos Vinculados
- Verificar permisos de sesión en `services/whatsapp-service/sessions/`

#### Zoho Authentication Failed
```bash
# Obtener nueva authorization code
curl "https://accounts.zoho.com/oauth/v2/auth?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=YOUR_REDIRECT_URI&scope=Desk.tickets.ALL,Desk.contacts.ALL,Desk.basic.READ"
```

#### AI Models No Response
- Verificar API keys en `.env`
- Revisar logs: `docker-compose logs classifier-service`
- Probar endpoint manualmente: `curl localhost:8001/health`

#### Redis Connection Issues
```bash
# Reiniciar Redis
docker-compose restart redis

# Verificar logs
docker-compose logs redis
```

### Logs y Monitoreo
```bash
# Ver todos los logs
docker-compose logs -f

# Filtrar por nivel
docker-compose logs -f | grep ERROR

# Logs con timestamps
docker-compose logs -f --timestamps

# Seguir logs específicos
docker-compose logs -f whatsapp-service classifier-service
```

## 🔒 Seguridad

- API keys cifradas en variables de entorno
- Tokens OAuth2 con refresh automático
- Validación de entrada en todos los endpoints
- Rate limiting en servicios públicos
- Logs sin información sensible

## 📈 Monitoreo y Métricas

- Health checks en todos los servicios
- Métricas Prometheus en puertos 9001, 9003
- Structured logging con correlación de requests
- Queue monitoring para tickets pendientes
- Error tracking con alertas

## 🤝 Contribución

1. Fork del repositorio
2. Crear branch feature: `git checkout -b feature/nueva-funcionalidad`
3. Commit cambios: `git commit -am 'Agregar nueva funcionalidad'`
4. Push al branch: `git push origin feature/nueva-funcionalidad`
5. Crear Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver `LICENSE` para más detalles. 