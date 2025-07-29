# Functional Specifications: WhatsApp Support Bot with Multi-Agent AI System

## 1. Executive Summary

### 1.1 Project Overview
Development of an intelligent WhatsApp bot that monitors a group chat, classifies support incidents using multiple AI agents, collects necessary information through natural conversation, and automatically creates tickets in Zoho Desk.

### 1.2 Key Technologies
- **WhatsApp Integration**: Baileys library (WhatsApp Web) via Node.js microservice
- **AI Backend**: Python with FastAPI
- **AI Framework**: Multi-agent system (GPT-4o-mini, Gemini, or Grok) via LangChain
- **Ticket System**: Zoho Desk API
- **Vector Database**: ChromaDB/Pinecone for RAG and knowledge management
- **Message Queue**: Redis for handling Zoho downtime
- **Frontend**: React/Next.js admin dashboard

## 2. System Architecture

### 2.1 Microservices Architecture

The system follows a microservices architecture pattern for scalability, maintainability, and technology flexibility.

#### Service Decomposition
```yaml
microservices:
  api-gateway:
    purpose: "Single entry point, routing, authentication"
    technology: "Kong/Traefik"
    instances: 2-3
    
  whatsapp-service:
    purpose: "WhatsApp connection and message handling"
    technology: "Node.js + Baileys"
    instances: 1-2 (stateful sessions)
    communication: "Publishes to message queue"
    
  classifier-service:
    purpose: "Message classification and incident detection"
    technology: "Python FastAPI"
    instances: 3-5 (auto-scaling)
    ai-model: "Configurable (GPT-4o-mini/Gemini/Grok)"
    
  extractor-service:
    purpose: "Information extraction from text and images"
    technology: "Python FastAPI"
    instances: 3-5 (auto-scaling)
    
  conversation-service:
    purpose: "Natural language responses and thread management"
    technology: "Python FastAPI"
    instances: 3-5 (auto-scaling)
    state: "Redis for thread state"
    
  ticket-service:
    purpose: "Zoho Desk integration and ticket management"
    technology: "Python FastAPI"
    instances: 2-3
    features: "Circuit breaker for Zoho downtime"
    
  vector-search-service:
    purpose: "RAG operations and knowledge base"
    technology: "Python FastAPI + ChromaDB"
    instances: 2-3
    
  analytics-service:
    purpose: "Metrics, logging, and cost tracking"
    technology: "Python FastAPI"
    instances: 1-2
    storage: "TimescaleDB"
```

#### Communication Patterns
```yaml
communication:
  async_messaging:
    broker: "Redis Pub/Sub"
    channels:
      - whatsapp:messages:inbound
      - tickets:created
      - tickets:updated
      - agents:responses
      - metrics:events
    persistence: "Redis Streams for critical messages"
      
  sync_communication:
    protocol: "REST (FastAPI)"
    fallback: "gRPC for high-performance needs"
    
  event_sourcing:
    store: "Redis Streams"
    retention: "30 days"
    backup: "PostgreSQL for long-term storage"
```

### 2.2 Multi-Agent Design
```yaml
agents:
  message_classifier:
    purpose: "Determine if message is support incident"
    model: "gpt-4o-mini"
    fallback: ["gemini-1.5-flash", "grok-beta"]
    
  information_extractor:
    purpose: "Parse and extract ticket data from messages"
    model: "gpt-4o-mini"
    includes_vision: true
    
  ticket_manager:
    purpose: "Create and update Zoho tickets"
    model: "gpt-4o-mini"
    
  conversation_agent:
    purpose: "Natural language interaction in WhatsApp"
    model: "gpt-4o-mini"
    tone: "formal"
    industry: "retail"
```

### 2.3 Service Contracts and Interfaces

```python
# Service Interface Definitions (Protocol Buffers / OpenAPI)

# classifier.proto
service ClassifierService {
  rpc ClassifyMessage(MessageRequest) returns (ClassificationResponse);
  rpc HealthCheck(Empty) returns (HealthStatus);
}

message ClassificationResponse {
  bool is_incident = 1;
  float confidence = 2;
  string category = 3;
  repeated string trigger_words = 4;
}

# Common API Response Format
class APIResponse:
    success: bool
    data: Optional[Dict]
    error: Optional[str]
    trace_id: str
    timestamp: datetime
```

### 2.4 Scalability Patterns

```yaml
scalability:
  horizontal_scaling:
    services: [classifier, extractor, conversation, vector-search]
    method: "Kubernetes HPA based on CPU/Memory"
    min_replicas: 2
    max_replicas: 10
    
  vertical_scaling:
    services: [ticket-service]  # Stateful operations
    method: "Manual resource adjustment"
    
  caching:
    - level1: "Redis for hot data"
    - level2: "Service-level caching"
    - ttl: "Configurable per data type"
    
  database_scaling:
    - read_replicas: true
    - sharding: "By tenant/workspace"
    - connection_pooling: true
```

### 2.5 Service Replaceability

```yaml
replaceability:
  ai_providers:
    interface: "AbstractLLMProvider"
    implementations:
      - OpenAIProvider
      - GeminiProvider  
      - GrokProvider
      - CustomProvider
    switching: "Environment variable / Runtime config"
    
  message_brokers:
    interface: "MessageBrokerInterface"
    implementations:
      - KafkaBroker
      - RabbitMQBroker
      - RedisPubSub
    
  storage_backends:
    interface: "StorageInterface"
    implementations:
      - PostgreSQL
      - MongoDB
      - DynamoDB
```

### 2.3 Data Flow
```mermaid
graph TD
    A[WhatsApp Message] --> B[Node.js Baileys Service]
    B --> C[Python Message Classifier Agent]
    C -->|Not Incident| D[Store in Vector DB]
    C -->|Is Incident| E[Information Extractor Agent]
    E --> F{Info Complete?}
    F -->|No| G[Conversation Agent]
    G --> H[Request Missing Info via WhatsApp]
    H --> I[Wait 30min for response]
    I -->|No Response| J[Retry up to 3x]
    J -->|Failed| K[Escalate to Human]
    F -->|Yes| L[Ticket Manager Agent]
    L --> M[Create Zoho Ticket]
    M --> N[Notify in WhatsApp]
    M --> O[Update Dashboard]
    M --> P[Store in Vector DB]
```

## 3. Functional Requirements

### 3.1 Message Classification (Python/LangChain)
```python
from langchain.agents import Agent
from typing import Dict, List

class MessageClassificationResult:
    is_incident: bool
    confidence: float
    category: str  # 'technical' | 'operational' | 'urgent'
    trigger_words: List[str]  # ["urgente", "no funciona", "cerrado"]

# Classification agent configuration
classification_agent = Agent(
    name="IncidentClassifier",
    llm=ChatOpenAI(model="gpt-4o-mini"),
    system_prompt="""
    Analyze WhatsApp messages for retail support incidents.
    Industry context: Retail stores
    Keywords: urgente, no funciona, cerrado, error, ayuda, problema
    Return structured classification with confidence score.
    """
)
```

### 3.2 Information Extraction
```python
from pydantic import BaseModel
from typing import Optional, List

class TicketInformation(BaseModel):
    # Required fields
    subject: str           # Clear problem title
    description: str       # Detailed explanation
    priority: str         # 'urgent' | 'normal' (Store not operating = urgent)
    classification: str    # Request type
    contact_id: str       # Reporter ID
    department_id: str    # Target department
    
    # Optional fields
    location: Optional[str] = None      # Store/location
    affected_system: Optional[str] = None
    error_messages: List[str] = []
    attachments: List[Dict] = []
    mentioned_users: List[str] = []     # @mentions
    
    # Metadata
    reporter_id: str      # Who reports
    affected_id: Optional[str] = None   # Who is affected (if different)

# Extraction agent with vision capabilities
extraction_agent = Agent(
    name="InformationExtractor",
    llm=ChatOpenAI(model="gpt-4o-mini"),
    tools=[ImageAnalysisTool()],
    system_prompt="""
    Extract ticket information from conversations and images.
    Analyze screenshots for error messages.
    Differentiate between reporter and affected person.
    """
)
```

### 3.3 Ticket Management Functions
```python
class ZohoTicketManager:
    async def create_ticket(self, data: TicketInformation) -> Dict:
        """Create ticket with automatic priority assignment"""
        # Priority rules
        if any(word in data.description.lower() for word in [
            "tienda no opera", "sistema caído", "no pueden vender", "urgente"
        ]):
            data.priority = "urgent"
        
        return await self.zoho_api.create_ticket(data.dict())
    
    async def update_ticket(self, ticket_id: str, updates: Dict) -> Dict:
        return await self.zoho_api.update_ticket(ticket_id, updates)
    
    async def get_ticket_status(self, ticket_id: str) -> Dict:
        return await self.zoho_api.get_ticket(ticket_id)
    
    async def search_similar_tickets(self, keywords: List[str]) -> List[Dict]:
        return await self.vector_db.similarity_search(keywords)
    
    async def upload_attachment(self, ticket_id: str, file: bytes) -> Dict:
        return await self.zoho_api.upload_attachment(ticket_id, file)
```

### 3.4 Conversation Management
```python
from datetime import datetime, timedelta
from enum import Enum

class ThreadStatus(Enum):
    COLLECTING = "collecting"
    COMPLETE = "complete"
    ESCALATED = "escalated"

class ConversationThread:
    thread_id: str         # One per incident
    incident_id: str
    participants: List[str]
    messages: List[Dict]
    missing_info: List[str]
    retry_count: int = 0   # Max 3
    status: ThreadStatus
    created_at: datetime
    last_activity: datetime
    
    # Thread lifecycle: 24 hours suggested for auto-close
    THREAD_TIMEOUT = timedelta(hours=24)
    MAX_MESSAGES_PER_INCIDENT = 10
    RETRY_WAIT_TIME = timedelta(minutes=30)
```

### 3.5 WhatsApp Integration (Node.js Bridge)
```javascript
// Node.js Baileys Service
const { makeWASocket, DisconnectReason } = require('@whiskeysockets/baileys');

class WhatsAppBridge {
    constructor(pythonBackendUrl) {
        this.pythonBackend = pythonBackendUrl;
        this.socket = null;
    }
    
    async initialize() {
        this.socket = makeWASocket({
            // Configuration
        });
        
        this.socket.ev.on('messages.upsert', async (m) => {
            // Forward to Python backend
            await this.forwardToPython(m);
        });
    }
    
    async sendToGroup(message, mentions = []) {
        // Send message with mentions
    }
    
    async sendPrivate(userId, message) {
        // Send private message
    }
    
    async downloadMedia(message) {
        // Download and return media buffer
    }
}
```

### 3.6 Response Templates
```python
RESPONSE_TEMPLATES = {
    "ticket_created": "He creado el ticket #{ticket_id} con prioridad {priority}. Un técnico lo atenderá pronto. Te notificaré cuando haya actualizaciones.",
    
    "missing_info": """Para crear el ticket necesito la siguiente información:
{missing_fields}""",
    
    "status_update": "@{user} El ticket #{ticket_id} está en estado: {status}",
    
    "escalation": "@{human_support} Se requiere intervención manual para el incidente reportado por @{user}",
    
    "zoho_down": "Zoho no está disponible. El ticket se creará automáticamente cuando el servicio se restablezca."
}
```

## 4. Data Persistence

### 4.1 Vector Database Schema
```python
from chromadb import Collection
from datetime import datetime

class VectorDocument:
    id: str
    type: str  # 'message' | 'ticket' | 'solution'
    content: str
    embedding: List[float]
    metadata: Dict = {
        'user_id': str,
        'timestamp': datetime,
        'ticket_id': Optional[str],
        'classification': Optional[str],
        'resolved': bool
    }

class RAGManager:
    def __init__(self, collection: Collection):
        self.collection = collection
    
    async def find_similar_incidents(self, description: str) -> List[VectorDocument]:
        return self.collection.query(
            query_texts=[description],
            n_results=5
        )
    
    async def get_user_history(self, user_id: str) -> List[VectorDocument]:
        return self.collection.get(
            where={"user_id": user_id}
        )
    
    async def store_conversation(self, thread: ConversationThread) -> None:
        # Vectorize and store conversation
        pass
```

### 4.2 Fallback Queue System
```python
from redis import Redis
from datetime import datetime

class TicketQueue:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.queue_key = "pending_tickets"
        
    async def add_ticket(self, ticket_data: TicketInformation) -> str:
        queue_item = {
            'id': str(uuid4()),
            'ticket_data': ticket_data.dict(),
            'attempts': 0,
            'created_at': datetime.now().isoformat(),
            'error': None
        }
        
        self.redis.lpush(self.queue_key, json.dumps(queue_item))
        return queue_item['id']
    
    async def process_queue(self):
        """Process pending tickets every 5 minutes"""
        while item := self.redis.rpop(self.queue_key):
            ticket_data = json.loads(item)
            if ticket_data['attempts'] < 10:
                try:
                    await self.create_ticket(ticket_data['ticket_data'])
                except Exception as e:
                    ticket_data['attempts'] += 1
                    ticket_data['error'] = str(e)
                    self.redis.lpush(self.queue_key, json.dumps(ticket_data))
```

## 5. Frontend Admin Dashboard

### 5.1 Dashboard Components
```typescript
// React/Next.js Dashboard Structure
interface DashboardComponents {
  // Real-time Monitoring
  MetricsOverview: {
    activeIncidents: number;
    ticketsToday: number;
    avgResponseTime: number;
    aiCosts: number;
  };
  
  // Agent Status
  AgentMonitor: {
    agentName: string;
    status: 'active' | 'error' | 'idle';
    lastActivity: Date;
    successRate: number;
  }[];
  
  // Conversation Logs
  ConversationViewer: {
    threadId: string;
    messages: Message[];
    classification: string;
    ticketId?: string;
  };
  
  // Configuration
  PromptManager: {
    agentName: string;
    prompt: string;
    version: number;
  }[];
}
```

### 5.2 WebSocket Integration
```typescript
// Real-time updates
const useDashboardSocket = () => {
  const [metrics, setMetrics] = useState<Metrics>();
  
  useEffect(() => {
    const ws = new WebSocket('ws://backend/dashboard');
    
    ws.on('metrics:update', (data) => {
      setMetrics(data);
    });
    
    ws.on('ticket:created', (ticket) => {
      // Update UI
    });
    
    return () => ws.close();
  }, []);
  
  return metrics;
};
```

## 6. Agent Configuration

### 6.1 Multi-Model Support
```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, prompt: str) -> str:
        pass

class OpenAIProvider(LLMProvider):
    def __init__(self, model="gpt-4o-mini"):
        self.client = OpenAI()
        self.model = model
    
    async def complete(self, prompt: str) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

class GeminiProvider(LLMProvider):
    # Gemini implementation
    pass

class GrokProvider(LLMProvider):
    # Grok implementation
    pass

# Factory pattern for model selection
class ModelFactory:
    providers = {
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
        "grok": GrokProvider
    }
    
    @classmethod
    def get_provider(cls, provider_name: str) -> LLMProvider:
        return cls.providers[provider_name]()
```

### 6.2 System Prompts
```python
SYSTEM_PROMPTS = {
    "master": """You are a formal support bot for a retail company.
Industry: Retail
Tone: Formal, professional
Language: Spanish
Max attempts before escalation: 3
Never create tickets without complete required information.""",
    
    "classifier": """Analyze WhatsApp messages to identify support incidents.
Focus on retail operations: stores, POS systems, inventory.
Classify urgency based on operational impact.""",
    
    "extractor": """Extract structured ticket information.
Required: subject, description, priority, classification, contactId, departmentId
Analyze images for error messages.
Identify reporter vs affected person.""",
    
    "conversation": """Collect missing ticket information politely.
Ask one question at a time.
Be specific and clear.
Retry after 30 minutes if no response (max 3 times)."""
}
```

## 7. Implementation Timeline

### Phase 1: Core Infrastructure (Week 1-2)
- [ ] Node.js Baileys service setup
- [ ] Python FastAPI backend
- [ ] Basic message classification
- [ ] Zoho API integration
- [ ] Redis queue setup

### Phase 2: Multi-Agent System (Week 3)
- [ ] LangChain agent orchestration
- [ ] Information extraction with vision
- [ ] Conversation management
- [ ] Vector database setup
- [ ] RAG implementation

### Phase 3: Frontend Dashboard (Week 4)
- [ ] React/Next.js setup
- [ ] Real-time metrics dashboard
- [ ] Agent monitoring UI
- [ ] Conversation viewer
- [ ] Prompt configuration UI

### Phase 4: Production Ready (Week 5)
- [ ] Error handling refinement
- [ ] Performance optimization
- [ ] Security hardening
- [ ] Deployment scripts
- [ ] Documentation

### Future Enhancements
- [ ] Solution suggestions from KB
- [ ] PDF ticket summaries
- [ ] Advanced analytics
- [ ] Multi-language support
- [ ] Voice message transcription

## 8. Error Handling

```python
class ErrorHandler:
    strategies = {
        "zoho_unavailable": {
            "action": "queue_ticket",
            "user_message": RESPONSE_TEMPLATES["zoho_down"],
            "retry_interval": timedelta(minutes=5)
        },
        
        "classification_failure": {
            "action": "escalate_after_retries",
            "max_retries": 3,
            "escalation_message": RESPONSE_TEMPLATES["escalation"]
        },
        
        "conversation_timeout": {
            "action": "close_thread",
            "timeout": timedelta(hours=24),
            "final_message": "El ticket no pudo completarse por falta de información."
        },
        
        "rate_limit": {
            "action": "throttle",
            "max_messages_per_minute": 20,
            "cooldown": timedelta(seconds=60)
        }
    }
```

## 9. Performance & Cost Management

### 9.1 Token Management
```python
TOKEN_LIMITS = {
    "per_conversation": 4000,      # Initial suggestion
    "max_context_window": 8000,
    "cost_alert_threshold": 0.10,  # USD per ticket
    "monthly_budget_alert": 500.00 # USD
}

class TokenManager:
    async def estimate_cost(self, messages: List[str], model: str) -> float:
        # Token counting and cost estimation
        pass
    
    async def optimize_context(self, messages: List[str]) -> List[str]:
        # Remove redundant messages, summarize if needed
        pass
```

### 9.2 Metrics Collection
```python
from prometheus_client import Counter, Histogram, Gauge

# Prometheus metrics
ticket_created = Counter('tickets_created_total', 'Total tickets created')
classification_success = Counter('classification_success_total', 'Successful classifications')
response_time = Histogram('response_time_seconds', 'Time to create ticket')
active_threads = Gauge('active_threads', 'Currently active conversation threads')
ai_cost = Counter('ai_cost_usd', 'AI API costs in USD')
```

## 10. Security & Compliance

### 10.1 Authentication
```python
class SecurityConfig:
    # OAuth2 for Zoho
    zoho_oauth = {
        "client_id": env("ZOHO_CLIENT_ID"),
        "client_secret": env("ZOHO_CLIENT_SECRET"),
        "redirect_uri": "https://api.yourcompany.com/callback",
        "scope": "Desk.tickets.ALL"
    }
    
    # WhatsApp session
    whatsapp_session = {
        "storage": "encrypted_file",
        "session_timeout": timedelta(days=30)
    }
    
    # API Keys
    api_keys = {
        "openai": env("OPENAI_API_KEY"),
        "vector_db": env("CHROMA_API_KEY")
    }
```

### 10.2 Data Privacy
```python
class DataPrivacy:
    # PII masking
    @staticmethod
    def mask_phone(phone: str) -> str:
        return phone[:3] + "****" + phone[-2:]
    
    # Data retention
    RETENTION_DAYS = 90
    
    # Encryption at rest
    ENCRYPTION_ENABLED = True
```

## 11. Development Best Practices

### 11.1 Code Organization
```
/backend
  /agents
    classifier.py
    extractor.py
    ticket_manager.py
    conversation.py
  /api
    main.py
    routers/
    middleware/
  /integrations
    zoho.py
    vector_db.py
  /models
    schemas.py
    database.py
  /utils
    prompts.py
    metrics.py
  /tests
    test_agents.py
    test_api.py

/whatsapp-bridge
  /src
    index.js
    baileys-service.js
    message-handler.js
  /tests
    test-connection.js

/frontend
  /app
    dashboard/
    config/
    logs/
  /components
    metrics/
    agents/
    conversations/
  /hooks
    useWebSocket.ts
    useMetrics.ts
  /lib
    api.ts
    utils.ts
```

### 11.2 Testing Strategy
```python
# Unit tests for each agent
async def test_classifier_agent():
    agent = MessageClassifier()
    result = await agent.classify("La impresora no funciona")
    assert result.is_incident == True
    assert result.confidence > 0.8

# Integration tests
async def test_full_flow():
    # Simulate WhatsApp message
    # Verify ticket creation
    # Check notifications
    pass

# Load testing
async def test_concurrent_messages():
    # Simulate 100 concurrent messages
    # Measure response times
    # Check resource usage
    pass
```

### 11.3 Monitoring & Logging
```python
import structlog

logger = structlog.get_logger()

# Structured logging
logger.info(
    "ticket_created",
    ticket_id=ticket.id,
    user_id=user.id,
    processing_time=time.elapsed,
    ai_cost=cost
)

# Correlation IDs for tracing
@contextmanager
def trace_request(request_id: str):
    structlog.contextvars.bind_contextvars(
        request_id=request_id
    )
```

## 12. Deployment Configuration

### 12.1 Docker Compose (Development)
```yaml
version: '3.8'

services:
  # Infrastructure Services
  kafka:
    image: confluentinc/cp-kafka:latest
    environment:
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
    depends_on:
      - zookeeper

  zookeeper:
    image: confluentinc/cp-zookeeper:latest
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: support_bot
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: ${DB_PASSWORD}

  # Microservices
  api-gateway:
    image: kong:latest
    ports:
      - "8000:8000"
      - "8001:8001"
    environment:
      KONG_DATABASE: "off"
      KONG_DECLARATIVE_CONFIG: /kong/config.yml

  whatsapp-service:
    build: ./services/whatsapp-service
    ports:
      - "3000:3000"
    volumes:
      - ./sessions:/app/sessions
    environment:
      KAFKA_BROKERS: kafka:9092
      REDIS_URL: redis://redis:6379

  classifier-service:
    build: ./services/classifier-service
    deploy:
      replicas: 3
    environment:
      AI_PROVIDER: ${AI_PROVIDER:-openai}
      KAFKA_BROKERS: kafka:9092
      REDIS_URL: redis://redis:6379

  extractor-service:
    build: ./services/extractor-service
    deploy:
      replicas: 2
    environment:
      AI_PROVIDER: ${AI_PROVIDER:-openai}
      KAFKA_BROKERS: kafka:9092

  conversation-service:
    build: ./services/conversation-service
    deploy:
      replicas: 2
    environment:
      AI_PROVIDER: ${AI_PROVIDER:-openai}
      REDIS_URL: redis://redis:6379

  ticket-service:
    build: ./services/ticket-service
    environment:
      ZOHO_CLIENT_ID: ${ZOHO_CLIENT_ID}
      ZOHO_CLIENT_SECRET: ${ZOHO_CLIENT_SECRET}
      POSTGRES_URL: postgres://admin:${DB_PASSWORD}@postgres:5432/support_bot
      KAFKA_BROKERS: kafka:9092

  vector-search-service:
    build: ./services/vector-search-service
    environment:
      CHROMA_HOST: chromadb
      KAFKA_BROKERS: kafka:9092

  analytics-service:
    build: ./services/analytics-service
    environment:
      POSTGRES_URL: postgres://admin:${DB_PASSWORD}@postgres:5432/support_bot
      KAFKA_BROKERS: kafka:9092

  # Frontend
  dashboard:
    build: ./frontend
    ports:
      - "3001:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://api-gateway:8000

  # Vector Database
  chromadb:
    image: chromadb/chroma
    ports:
      - "8002:8000"

  # Monitoring
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports:
      - "3002:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}

  jaeger:
    image: jaegertracing/all-in-one
    ports:
      - "16686:16686"
      - "14268:14268"
```

### 12.2 Environment Variables
```bash
# .env.example
# WhatsApp
WHATSAPP_SESSION_NAME=support-bot

# AI Providers
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
GROK_API_KEY=...

# Zoho
ZOHO_CLIENT_ID=...
ZOHO_CLIENT_SECRET=...
ZOHO_ORG_ID=...

# Database
DB_PASSWORD=...
REDIS_URL=redis://localhost:6379

# Vector DB
CHROMA_API_KEY=...
CHROMA_HOST=localhost

# Monitoring
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
```

## 14. Service Deployment and Orchestration

### 14.1 Kubernetes Configuration

```yaml
# Example: Classifier Service Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: classifier-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: classifier-service
  template:
    spec:
      containers:
      - name: classifier
        image: your-registry/classifier-service:latest
        env:
        - name: AI_PROVIDER
          valueFrom:
            configMapKeyRef:
              name: ai-config
              key: provider
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
---
apiVersion: v1
kind: Service
metadata:
  name: classifier-service
spec:
  selector:
    app: classifier-service
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
```

### 14.2 Service Mesh Configuration (Istio)

```yaml
# Traffic Management
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: classifier-service
spec:
  hosts:
  - classifier-service
  http:
  - match:
    - headers:
        x-version:
          exact: v2
    route:
    - destination:
        host: classifier-service
        subset: v2
      weight: 20  # Canary deployment
    - destination:
        host: classifier-service
        subset: v1
      weight: 80
  - timeout: 30s
    retries:
      attempts: 3
      perTryTimeout: 10s
```

### 14.3 Circuit Breaker Pattern

```python
# Resilience patterns for inter-service communication
from circuit_breaker import CircuitBreaker

class ZohoServiceClient:
    def __init__(self):
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=ZohoAPIException
        )
    
    @circuit_breaker
    async def create_ticket(self, data: Dict) -> Dict:
        # If circuit is open, this will raise CircuitBreakerError
        return await self._call_zoho_api(data)
    
    async def handle_circuit_open(self, data: Dict):
        # Fallback: Queue the ticket
        await self.queue_service.add_ticket(data)
        return {"queued": True, "message": "Ticket queued for processing"}
```

## 15. Monitoring and Observability

### 15.1 Distributed Tracing

```yaml
tracing:
  provider: "Jaeger/Zipkin"
  sampling_rate: 0.1  # 10% in production
  
  instrumentation:
    - automatic: "OpenTelemetry agents"
    - manual: "Critical business flows"
    
  trace_points:
    - "Message reception"
    - "Classification decision"
    - "AI API calls"
    - "Ticket creation"
    - "User notification"
```

### 15.2 Service Metrics

```python
# Prometheus metrics per service
SERVICE_METRICS = {
    "classifier_service": [
        "classification_requests_total",
        "classification_duration_seconds",
        "classification_errors_total",
        "model_inference_time_seconds"
    ],
    
    "ticket_service": [
        "tickets_created_total",
        "tickets_failed_total", 
        "zoho_api_latency_seconds",
        "queue_depth"
    ],
    
    "whatsapp_service": [
        "messages_received_total",
        "messages_sent_total",
        "connection_status",
        "media_downloads_total"
    ]
}
```

### 15.3 Health Checks

```python
# Standardized health check endpoint for all services
from fastapi import FastAPI
from typing import Dict

app = FastAPI()

@app.get("/health")
async def health_check() -> Dict:
    return {
        "status": "healthy",
        "service": "classifier-service",
        "version": "1.2.0",
        "dependencies": {
            "redis": check_redis_connection(),
            "ai_provider": check_ai_provider(),
            "message_queue": check_queue_connection()
        },
        "metrics": {
            "requests_per_minute": get_rpm(),
            "error_rate": get_error_rate(),
            "avg_response_time": get_avg_response_time()
        }
    }

@app.get("/ready")
async def readiness_check() -> Dict:
    # Kubernetes readiness probe
    return {"ready": all_dependencies_ready()}
```