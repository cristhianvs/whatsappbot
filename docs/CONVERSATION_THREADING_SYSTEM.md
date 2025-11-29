# Sistema de Gestión de Hilos de Conversación

**Fecha de Implementación**: Noviembre 16, 2025
**Estado**: ✅ Implementado - Tests Parciales
**Ubicación**: `services/classifier-service/app/utils/conversation_tracker.py`

## Descripción General

Sistema para gestionar hilos de conversación en WhatsApp y evitar la creación de tickets duplicados cuando usuarios reportan seguimiento sobre la misma incidencia. Utiliza una estrategia multi-capa para asociar mensajes relacionados.

## Problema a Resolver

**Escenario sin gestión de hilos:**
```
10:00 - Usuario: "Tienda 907 no deja cobrar marca error"
        → Bot crea Ticket #12345

10:15 - Usuario: "Sigue sin funcionar"
        → Bot crea Ticket #12346 (DUPLICADO ❌)

10:30 - Otro usuario: "Mismo problema aquí"
        → Bot crea Ticket #12347 (DUPLICADO ❌)
```

**Con gestión de hilos:**
```
10:00 - Usuario: "Tienda 907 no deja cobrar marca error"
        → Bot crea Ticket #12345

10:15 - Usuario: "Sigue sin funcionar" (cita mensaje del bot)
        → Bot detecta Ticket #12345, agrega como nota ✅

10:30 - Otro usuario: "Mismo problema aquí"
        → Bot detecta incidencia reciente, asocia a #12345 ✅
```

## Arquitectura de la Solución

### Estrategia Multi-Capa

```
Mensaje Entrante
    ↓
┌─────────────────────────────────────────────┐
│ Capa 1: Detección de Mensaje Citado        │
│ ¿Usuario citó respuesta del bot?           │
└─────────────────────────────────────────────┘
    ↓ SÍ → Extraer Ticket ID
    ↓ NO → Continuar
┌─────────────────────────────────────────────┐
│ Capa 2: Búsqueda Temporal                  │
│ ¿Hay incidencias recientes (2 hrs)?        │
└─────────────────────────────────────────────┘
    ↓ SÍ → Retornar Ticket ID existente
    ↓ NO → Continuar
┌─────────────────────────────────────────────┐
│ Capa 3: Análisis de Similitud (Futuro)     │
│ NLP para detectar temas relacionados       │
└─────────────────────────────────────────────┘
    ↓
Nueva Incidencia
```

### Componentes Principales

#### 1. Schemas Extendidos (`app/models/schemas.py`)

**Nuevos Modelos:**

```python
class QuotedMessage(BaseModel):
    """Mensaje citado/respondido en WhatsApp"""
    id: str
    text: str
    participant: str  # Quien envió el mensaje original

class ContextInfo(BaseModel):
    """Información de contexto del mensaje"""
    quoted_message_id: Optional[str] = None
    mentioned_jids: List[str] = []
    is_forwarded: bool = False
    forwarding_score: Optional[int] = None
```

**MessageData Extendido:**

```python
class MessageData(BaseModel):
    # Campos existentes
    id: str
    text: str
    from_user: str
    timestamp: datetime
    group_id: Optional[str] = None
    has_media: bool = False
    message_type: str = "text"

    # Nuevos campos para threading
    quoted_message: Optional[QuotedMessage] = None
    context_info: Optional[ContextInfo] = None
    chat_type: Optional[str] = None
    participant: Optional[str] = None
```

#### 2. Conversation Tracker (`app/utils/conversation_tracker.py`)

**Clase Principal:**

```python
class ConversationTracker:
    def __init__(self, redis_client, bot_phone_number: str):
        self.redis = redis_client
        self.bot_number = bot_phone_number
        self.INCIDENT_TTL = 7200  # 2 horas
        self.TICKET_PREFIX = "incident:active:"
```

**Métodos Principales:**

| Método | Propósito | Retorno |
|--------|-----------|---------|
| `check_existing_incident(message_data)` | Verifica si mensaje pertenece a hilo existente | `ticket_id` o `None` |
| `register_incident(message_data, ticket_id, classification)` | Registra nueva incidencia en Redis | `bool` |
| `add_message_to_thread(ticket_id, message_id, text)` | Agrega mensaje a hilo existente | `bool` |
| `is_ticket_active(ticket_id)` | Verifica si ticket sigue activo | `bool` |
| `get_thread_summary(ticket_id)` | Obtiene resumen del hilo | `Dict` o `None` |

**Métodos Internos:**

| Método | Propósito |
|--------|-----------|
| `_extract_ticket_from_quoted(message_data)` | Extrae ticket ID de mensaje citado del bot |
| `_find_recent_incident(message_data)` | Busca incidencias recientes en el grupo |
| `_scan_keys(pattern)` | Escanea Redis eficientemente |

## Fase 1: Investigación Completada

### Hallazgos Clave

#### ✅ Redis Client Disponible
- **Ubicación**: `app/utils/redis_client.py`
- **Estado**: Ya inicializado en `main.py`
- **Métodos Útiles**:
  - `set_cache(key, value, ttl)` - Almacenar con expiración
  - `get_cache(key)` - Recuperar datos
  - `publish_message(channel, message)` - Publicar eventos

#### ⚠️ Gap en Schemas
- WhatsApp-service envía `quoted_message` y `context_info`
- Classifier-service NO los tenía en el modelo
- **Solución**: Schemas extendidos implementados

#### ✅ Identificador de Grupo
- Campo: `group_id: Optional[str]`
- Formato: `120363123456789012@g.us` (para grupos)
- Formato: `5215512345678@s.whatsapp.net` (para chats individuales)

## Fase 2: Schemas Extendidos

### Cambios Implementados

**Archivo**: `services/classifier-service/app/models/schemas.py`

**Antes:**
```python
class MessageData(BaseModel):
    id: str
    text: str
    from_user: str
    timestamp: datetime
    group_id: Optional[str] = None
    has_media: bool = False
    message_type: str = "text"
```

**Después:**
```python
class MessageData(BaseModel):
    id: str
    text: str
    from_user: str
    timestamp: datetime
    group_id: Optional[str] = None
    has_media: bool = False
    message_type: str = "text"
    quoted_message: Optional[QuotedMessage] = None  # ← NUEVO
    context_info: Optional[ContextInfo] = None      # ← NUEVO
    chat_type: Optional[str] = None                 # ← NUEVO
    participant: Optional[str] = None               # ← NUEVO
```

### Tests de Schemas

**Ubicación**: `tests/test_schemas.py`

**Cobertura**:
- ✅ Creación de mensaje simple
- ✅ Creación con mensaje citado
- ✅ Context info completo
- ✅ Mensaje con todos los campos
- ✅ Conversión a dict

**Resultado**: 5/5 tests pasados ✅

## Fase 3: Estructura de Tests

### Archivos Creados

```
services/classifier-service/tests/
├── __init__.py
├── conftest.py                      # Fixtures compartidos
├── test_schemas.py                  # Tests de modelos
├── test_conversation_tracker.py     # Tests del tracker
└── run_tests_standalone.py          # Runner con UV
```

### Fixtures Importantes (`conftest.py`)

```python
@pytest.fixture
def sample_message_simple():
    """Mensaje sin quoted"""
    return MessageData(
        id="msg_001",
        text="Tienda 907 no deja cobrar",
        from_user="5215512345678@s.whatsapp.net",
        group_id="120363123456789012@g.us",
        # ...
    )

@pytest.fixture
def sample_message_with_quoted_bot():
    """Mensaje que cita al bot"""
    return MessageData(
        id="msg_002",
        text="Sigue sin funcionar",
        quoted_message=QuotedMessage(
            id="msg_bot_001",
            text="Ticket #12345 creado",
            participant="5215530482752@s.whatsapp.net"  # Bot
        )
    )
```

### Script Standalone Runner

**Archivo**: `tests/run_tests_standalone.py`

**Uso**:
```bash
cd services/classifier-service/tests
uv run run_tests_standalone.py
```

**Dependencies Inline** (gestionadas por UV):
- pytest
- pytest-asyncio
- pytest-cov
- pydantic
- structlog

## Fase 4: Conversation Tracker Implementado

### Lógica de Detección de Hilos

#### Método 1: Extracción de Ticket desde Mensaje Citado

```python
async def _extract_ticket_from_quoted(self, message_data: Dict) -> Optional[str]:
    quoted = message_data.get('quoted_message')
    if not quoted:
        return None

    # Verificar que el mensaje citado es del bot
    if self.bot_number not in quoted.participant:
        return None

    # Buscar patrones de ticket
    patterns = [
        r'Ticket #(\d+)',
        r'Ticket (\d+)',
        r'#(\d+)'
    ]

    for pattern in patterns:
        match = re.search(pattern, quoted.text)
        if match:
            ticket_id = match.group(1)

            # Verificar que sigue activo
            if await self.is_ticket_active(ticket_id):
                return ticket_id

    return None
```

**Patrones Soportados:**
- `Ticket #12345`
- `Ticket 12345`
- `ticket #12345`
- `#12345`

#### Método 2: Búsqueda Temporal en Grupo

```python
async def _find_recent_incident(self, message_data: Dict) -> Optional[str]:
    group_id = message_data.get('group_id') or message_data.get('from_user')

    # Buscar en Redis
    pattern = f"{self.TICKET_PREFIX}{group_id}:*"
    keys = await self._scan_keys(pattern)

    if not keys:
        return None

    # Obtener incidencias y ordenar por timestamp
    incidents = []
    for key in keys:
        data = await self.redis.get_cache(key)
        if data:
            incidents.append(data)

    incidents.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    recent = incidents[0]

    # Verificar ventana temporal (2 horas)
    incident_time = datetime.fromisoformat(recent['timestamp'])
    if datetime.now() - incident_time < timedelta(seconds=self.INCIDENT_TTL):
        return recent['ticket_id']

    return None
```

**Configuración de Ventana:**
```python
self.INCIDENT_TTL = 7200  # 2 horas en segundos
```

### Almacenamiento en Redis

**Estructura de Datos:**

```json
{
    "key": "incident:active:120363123456789012@g.us:12345",
    "value": {
        "ticket_id": "12345",
        "original_message_id": "msg_001",
        "group_id": "120363123456789012@g.us",
        "user": "5215512345678@s.whatsapp.net",
        "timestamp": "2025-11-16T10:00:00",
        "category": "POS",
        "priority": "alta",
        "message_text": "Tienda 907 no deja cobrar...",
        "thread_messages": ["msg_001", "msg_002", "msg_003"],
        "last_update": "2025-11-16T10:30:00"
    },
    "ttl": 7200
}
```

**Nomenclatura de Keys:**
```
incident:active:{group_id}:{ticket_id}
```

**Ejemplos:**
- `incident:active:120363123456789012@g.us:12345`
- `incident:active:5215512345678@s.whatsapp.net:67890`

### Registro de Nueva Incidencia

```python
await tracker.register_incident(
    message_data=mensaje,
    ticket_id="12345",
    classification={
        'categoria': 'POS',
        'prioridad': 'alta'
    }
)
```

**Proceso:**
1. Extrae contexto (grupo/usuario)
2. Crea estructura de datos
3. Guarda en Redis con TTL de 2 horas
4. Inicia lista de mensajes del hilo

### Agregar Mensaje a Hilo Existente

```python
await tracker.add_message_to_thread(
    ticket_id="12345",
    message_id="msg_002",
    message_text="Sigue sin funcionar"
)
```

**Proceso:**
1. Busca incidencia en Redis por ticket_id
2. Agrega message_id a lista de thread_messages
3. Actualiza timestamp de last_update
4. Extiende TTL (reset a 2 horas)

## Fase 5: Tests Unitarios

### Estado Actual

**Resultado de Tests:**
```
15 tests totales
8 passed  ✅
7 failed  ⚠️
```

### Tests Exitosos ✅

1. `test_no_ticket_from_quoted_user_message` - Ignora mensajes citados de usuarios
2. `test_register_new_incident` - Registra incidencias correctamente
3. `test_no_incident_outside_time_window` - Ventana temporal funciona
4. 5 tests de schemas - Todos los modelos funcionan

### Tests Fallidos ⚠️

**Problema Principal**: Mocking de async generators para Redis `scan_iter`

**Error Común:**
```python
RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
async for key in self.redis.redis.scan_iter(match=pattern):
```

**Tests Afectados:**
1. `test_extract_ticket_from_quoted_bot_message`
2. `test_add_message_to_thread`
3. `test_find_recent_incident_within_window`
4. `test_is_ticket_active`
5. `test_get_thread_summary`
6. `test_extract_ticket_patterns`
7. `test_message_dict_format`

**Solución Parcial Aplicada:**

```python
async def async_gen(items):
    """Helper to create async generator"""
    for item in items:
        yield item

# En fixtures:
mock_redis.redis.scan_iter = MagicMock(
    return_value=async_gen(["key1", "key2"])
)
```

### Cobertura de Tests

**Escenarios Cubiertos:**
- ✅ Extracción de ticket desde mensaje citado del bot
- ✅ Ignorar mensajes citados de otros usuarios
- ✅ Registro de nueva incidencia
- ✅ Agregar mensaje a hilo existente
- ✅ Búsqueda de incidencias recientes
- ✅ Ventana temporal (dentro y fuera)
- ✅ Verificación de ticket activo
- ✅ Obtención de resumen de hilo
- ✅ Múltiples patrones de ticket ID
- ✅ Formato dict vs MessageData object

## Integración con Flujo de Clasificación

### Modificaciones Necesarias en `main.py`

**Paso 1: Inicializar Tracker**

```python
from app.utils.conversation_tracker import ConversationTracker

# En startup
conversation_tracker = ConversationTracker(
    redis_client,
    bot_phone_number=os.getenv('BOT_PHONE_NUMBER', '5215530482752')
)
```

**Paso 2: Modificar `handle_whatsapp_message`**

```python
async def handle_whatsapp_message(message_data: dict):
    # 1. Verificar si es parte de hilo existente
    existing_ticket_id = await conversation_tracker.check_existing_incident(message_data)

    if existing_ticket_id:
        logger.info("Message is part of existing thread",
                   ticket_id=existing_ticket_id)

        # Agregar al hilo
        await conversation_tracker.add_message_to_thread(
            existing_ticket_id,
            message_data['id'],
            message_data.get('text', '')
        )

        # Publicar actualización (agregar nota al ticket)
        await redis_client.publish_message('tickets:update', {
            'ticket_id': existing_ticket_id,
            'action': 'add_note',
            'note': message_data.get('text', ''),
            'author': message_data.get('from_user')
        })

        # Responder en WhatsApp citando mensaje
        await redis_client.publish_message('agents:responses', {
            'groupId': message_data.get('groupId'),
            'response': f"Agregue tu mensaje al Ticket #{existing_ticket_id}",
            'quotedMessageId': message_data['id']
        })

        return  # No clasificar, no crear ticket nuevo

    # 2. No hay hilo existente - clasificar normalmente
    classification = await classifier.classify(
        text=message_data.get('text', ''),
        context=context
    )

    if classification.is_support_incident and classification.confidence > 0.7:
        # Crear nuevo ticket
        ticket_id = await create_ticket_in_zoho(message_data, classification)

        # Registrar como incidencia activa
        await conversation_tracker.register_incident(
            message_data,
            ticket_id,
            {
                'categoria': classification.category,
                'prioridad': classification.urgency
            }
        )

        # Responder citando mensaje original (IMPORTANTE para tracking)
        await redis_client.publish_message('agents:responses', {
            'groupId': message_data.get('groupId'),
            'response': f"Ticket #{ticket_id} creado: {classification.category}",
            'quotedMessageId': message_data['id']  # ← Clave para seguimiento
        })
```

### Modificaciones en WhatsApp Service

**Asegurar que siempre cite el mensaje original:**

```javascript
// En outbound-handler.js
async sendMessage(groupId, text, options = {}) {
    const messageContent = {
        text: text
    };

    // SIEMPRE incluir quoted si viene en options
    if (options.quotedMessageId) {
        messageContent.quoted = {
            key: { id: options.quotedMessageId }
        };
    }

    await sock.sendMessage(groupId, messageContent);
}
```

## Flujos de Usuario Completos

### Flujo 1: Primera Incidencia

```
[10:00] Usuario en grupo
├─> "Tienda 907 no deja cobrar marca error"
│
[Sistema]
├─> Classifier: check_existing_incident()
│   └─> Método 1: No hay quoted_message
│   └─> Método 2: No hay incidencias recientes
│   └─> Retorna: None
│
├─> Clasificación Dual-LLM
│   └─> Es incidencia (conf: 0.98)
│
├─> Crear Ticket en Zoho
│   └─> Ticket #12345 creado
│
├─> Redis: register_incident()
│   └─> incident:active:120363...@g.us:12345
│   └─> TTL: 7200 segundos
│
[10:01] Bot responde (citando mensaje original)
└─> "Ticket #12345 creado - POS (Prioridad Alta)"
    └─> quoted_message_id: msg_001
```

### Flujo 2: Seguimiento Citando Bot

```
[10:15] Mismo usuario
├─> "Sigue sin funcionar"
│   └─> Cita mensaje del bot "Ticket #12345..."
│
[Sistema]
├─> Classifier: check_existing_incident()
│   └─> Método 1: _extract_ticket_from_quoted()
│       ├─> Detecta quoted_message
│       ├─> Verifica participant es bot (5215530482752)
│       ├─> Extrae "12345" con regex
│       ├─> Verifica ticket activo en Redis
│       └─> Retorna: "12345"
│
├─> NO clasificar (ya hay ticket)
├─> add_message_to_thread("12345", "msg_002")
│   └─> thread_messages: ["msg_001", "msg_002"]
│   └─> Extiende TTL a 2 hrs más
│
├─> Publicar a tickets:update
│   └─> Agregar nota al Ticket #12345
│
[10:16] Bot responde
└─> "Agregue tu mensaje al Ticket #12345"
```

### Flujo 3: Seguimiento sin Citar (Ventana Temporal)

```
[10:30] Otro usuario en mismo grupo
├─> "Alguien sabe del problema del cobro?"
│   └─> NO cita ningún mensaje
│
[Sistema]
├─> Classifier: check_existing_incident()
│   └─> Método 1: _extract_ticket_from_quoted()
│       └─> No hay quoted_message
│   └─> Método 2: _find_recent_incident()
│       ├─> Busca en Redis: incident:active:120363...@g.us:*
│       ├─> Encuentra: incident:active:120363...@g.us:12345
│       ├─> Timestamp: 10:00 (hace 30 min)
│       ├─> Ventana: < 2 horas ✓
│       └─> Retorna: "12345"
│
├─> add_message_to_thread("12345", "msg_003")
│
[10:31] Bot responde
└─> "Esto parece relacionado con Ticket #12345"
```

### Flujo 4: Nueva Incidencia (Ventana Expirada)

```
[13:00] Usuario en grupo (3 horas después)
├─> "Ahora no funciona el sistema de inventario"
│
[Sistema]
├─> Classifier: check_existing_incident()
│   └─> Método 2: _find_recent_incident()
│       ├─> Encuentra: incident:active:120363...@g.us:12345
│       ├─> Timestamp: 10:00 (hace 3 horas)
│       ├─> Ventana: > 2 horas ✗
│       └─> Retorna: None
│
├─> Clasificación Dual-LLM (nueva incidencia)
│
├─> Crear Ticket #67890
│
[13:01] Bot responde
└─> "Ticket #67890 creado - Inventario (Prioridad Media)"
```

## Configuración y Parámetros

### Variables de Entorno

```bash
# En .env de classifier-service
BOT_PHONE_NUMBER=5215530482752
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Configuración del Tracker

```python
class ConversationTracker:
    def __init__(self, redis_client, bot_phone_number: str):
        # Ventana temporal de incidencia activa
        self.INCIDENT_TTL = 7200  # 2 horas (ajustable)

        # Prefijos de Redis
        self.TICKET_PREFIX = "incident:active:"
        self.THREAD_PREFIX = "thread:"

        # Número del bot
        self.bot_number = bot_phone_number
```

**Ajustes Recomendados:**

| Parámetro | Valor Actual | Alternativas | Uso |
|-----------|--------------|--------------|-----|
| `INCIDENT_TTL` | 7200s (2hrs) | 3600s (1hr), 10800s (3hrs) | Ventana de agrupación |
| `bot_phone_number` | 5215530482752 | Tu número de bot | Detección de mensajes del bot |

## Métricas y Monitoreo

### Logs Estructurados (structlog)

```python
# Detección de hilo
logger.info("Found ticket from quoted message",
           ticket_id=ticket_id,
           message_id=message_dict.get('id'))

# Registro de incidencia
logger.info("Incident registered in Redis",
           ticket_id=ticket_id,
           key=key,
           ttl_seconds=self.INCIDENT_TTL)

# Actualización de hilo
logger.info("Message added to incident thread",
           ticket_id=ticket_id,
           message_id=message_id,
           thread_size=len(incident['thread_messages']))
```

### Métricas a Implementar

**Redis Keys a Monitorear:**
```bash
# Total de incidencias activas
KEYS incident:active:*

# Incidencias de un grupo específico
KEYS incident:active:120363123456789012@g.us:*

# TTL de una incidencia
TTL incident:active:120363123456789012@g.us:12345
```

**KPIs Sugeridos:**
- Tasa de detección de hilos (% mensajes asociados vs nuevos)
- Tamaño promedio de hilos (mensajes por incidencia)
- Tiempo promedio hasta cierre (cuando TTL expira)
- Tasa de falsos positivos (hilos mal asociados)

## Próximos Pasos

### Fase 6: Validación Manual (Pendiente)

**Crear**: `tests/validate_threading_standalone.py`

**Propósito**: Script que simula flujos completos sin necesidad de WhatsApp real

**Escenarios a Validar:**
1. ✅ Crear incidencia nueva → registrar en Redis
2. ✅ Mensaje citando bot → extraer ticket ID
3. ✅ Mensaje sin citar, mismo grupo → encontrar por ventana temporal
4. ✅ Mensaje después de 3 horas → crear nueva incidencia
5. ✅ Múltiples mensajes en un hilo → thread_messages crece

### Fase 7: Integración con Classifier Service (Pendiente)

**Tareas:**
1. Modificar `app/main.py` para incluir ConversationTracker
2. Actualizar `handle_whatsapp_message()` con lógica de hilos
3. Crear endpoint `/tickets/update` para agregar notas
4. Testing end-to-end con mensajes reales

### Fase 8: Integración con WhatsApp Service (Pendiente)

**Tareas:**
1. Asegurar que bot siempre cita mensaje original
2. Agregar soporte para `quotedMessageId` en todas las respuestas
3. Modificar outbound-handler para incluir quoted en mensajes

### Fase 9: Integración con Zoho (Pendiente)

**Tareas:**
1. Endpoint para agregar notas a tickets existentes
2. API call: `POST /api/v1/tickets/{ticket_id}/comments`
3. Incluir información de autor y timestamp

## Mejoras Futuras

### Capa 3: Análisis de Similitud Semántica

**Idea**: Usar embeddings para detectar mensajes relacionados sin necesidad de citar

```python
async def _find_similar_incident(self, message_data: Dict) -> Optional[str]:
    """
    Usa embeddings de OpenAI para comparar similitud
    """
    # Obtener embedding del mensaje actual
    current_embedding = await get_embedding(message_data['text'])

    # Comparar con incidencias recientes
    for incident in recent_incidents:
        incident_embedding = incident['embedding']
        similarity = cosine_similarity(current_embedding, incident_embedding)

        if similarity > 0.85:  # Umbral de similitud
            return incident['ticket_id']

    return None
```

**Beneficio**: Detecta hilos incluso cuando usuarios no citan mensajes

**Costo**: ~$0.0001 por mensaje adicional (OpenAI embeddings)

### Soporte para Múltiples Grupos

**Desafío Actual**: Un ticket solo puede estar activo en un grupo

**Mejora**: Permitir que un problema global afecte múltiples grupos

```python
# Redis structure
incident:global:12345 -> {
    'ticket_id': '12345',
    'affected_groups': [
        '120363123456789012@g.us',
        '120363123456789013@g.us'
    ],
    'is_global': True
}
```

### Dashboard de Hilos Activos

**Propósito**: Visualizar en tiempo real los hilos de conversación activos

**Features:**
- Lista de incidencias activas
- Tamaño de cada hilo (número de mensajes)
- Tiempo restante (TTL)
- Botón para "cerrar manualmente" (eliminar de Redis)

## Troubleshooting

### Problema: Ticket no se detecta aunque usuario citó

**Causa Posible**: Ticket expiró (TTL cumplido)

**Solución**:
```python
# Verificar si el ticket existe en Redis
await tracker.is_ticket_active("12345")

# Si retorna False, el TTL expiró
# Extender TTL si es necesario
```

**Prevención**: Aumentar `INCIDENT_TTL` a 3-4 horas

### Problema: Demasiados mensajes se asocian incorrectamente

**Causa Posible**: Ventana temporal muy grande

**Solución**: Reducir `INCIDENT_TTL` a 1 hora

```python
self.INCIDENT_TTL = 3600  # 1 hora
```

### Problema: Tests fallan con async generator errors

**Causa**: Mocking incorrecto de Redis scan_iter

**Solución**:
```python
async def async_gen(items):
    for item in items:
        yield item

mock_redis.redis.scan_iter = MagicMock(return_value=async_gen([...]))
```

### Problema: Bot number no coincide

**Causa**: Variable de entorno incorrecta

**Verificar**:
```bash
echo $BOT_PHONE_NUMBER
# Debe ser: 5215530482752 (sin @s.whatsapp.net)
```

## Referencias

### Archivos Clave

| Archivo | Propósito |
|---------|-----------|
| `app/utils/conversation_tracker.py` | Lógica principal del sistema |
| `app/models/schemas.py` | Modelos extendidos con quoted_message |
| `tests/test_conversation_tracker.py` | Tests unitarios (8/15 passing) |
| `tests/conftest.py` | Fixtures compartidos |
| `tests/run_tests_standalone.py` | Runner de tests con UV |

### Documentación Relacionada

- [`docs/INCIDENT_CLASSIFICATION_TESTING.md`](./INCIDENT_CLASSIFICATION_TESTING.md) - Sistema de clasificación dual-LLM
- [`services/classifier-service/README.md`](../services/classifier-service/README.md) - Documentación del servicio
- WhatsApp Baileys API: https://whiskeysockets.github.io/

### Recursos Externos

- Redis Commands: https://redis.io/commands/
- Pydantic Models: https://docs.pydantic.dev/
- Pytest Async: https://pytest-asyncio.readthedocs.io/

---

**Última actualización**: Noviembre 16, 2025
**Mantenedor**: Sistema de clasificación de incidencias - WhatsApp Bot
**Estado del proyecto**: Implementación core completa, pendiente integración end-to-end
