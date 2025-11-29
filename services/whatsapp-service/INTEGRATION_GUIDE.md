# WhatsApp Service - Guía de Integración

## 🎯 Cómo Integrar este Servicio en tu Proyecto

### **Opción 1: Copia Directa (Desarrollo Rápido)**

La forma más simple es copiar toda la carpeta del servicio:

```bash
# 1. Copiar la carpeta completa
cp -r whatsapp-service /ruta/a/tu/proyecto/services/

# 2. Instalar dependencias
cd /ruta/a/tu/proyecto/services/whatsapp-service
npm install

# 3. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus configuraciones específicas

# 4. Ejecutar el servicio
npm run dev
```

**Ventajas:**
- ✅ Rápido de implementar
- ✅ Control total sobre el código
- ✅ Fácil de modificar

**Desventajas:**
- ❌ Duplicación de código
- ❌ Difícil de mantener actualizaciones

---

### **Opción 2: Como Microservicio Docker (Recomendado)**

#### **Estructura de Proyecto Recomendada:**
```
mi-proyecto/
├── services/
│   ├── whatsapp-service/     # Servicio WhatsApp
│   ├── api-gateway/          # Tu API principal
│   └── other-services/       # Otros microservicios
├── docker-compose.yml        # Orquestación de servicios
└── .env                     # Variables globales
```

#### **Docker Compose para Integración:**

```yaml
# docker-compose.yml en tu proyecto principal
version: '3.8'

services:
  # Redis compartido
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  # WhatsApp Service
  whatsapp-service:
    build: ./services/whatsapp-service
    ports:
      - "3001:3001"
    environment:
      - NODE_ENV=production
      - REDIS_URL=redis://redis:6379
      - PORT=3001
    depends_on:
      - redis
    volumes:
      - whatsapp_sessions:/app/sessions

  # Tu aplicación principal
  main-app:
    build: .
    ports:
      - "3000:3000"
    environment:
      - WHATSAPP_SERVICE_URL=http://whatsapp-service:3001
      - REDIS_URL=redis://redis:6379
    depends_on:
      - whatsapp-service
      - redis

volumes:
  redis_data:
  whatsapp_sessions:
```

---

### **Opción 3: Integración via API REST**

#### **En tu aplicación principal:**

```javascript
// services/whatsapp-client.js
class WhatsAppClient {
    constructor(baseUrl = 'http://localhost:3001') {
        this.baseUrl = baseUrl;
    }

    async sendMessage(to, message, type = 'text') {
        const response = await fetch(`${this.baseUrl}/api/send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ to, message, type })
        });
        return response.json();
    }

    async getStatus() {
        const response = await fetch(`${this.baseUrl}/api/status`);
        return response.json();
    }

    async getHealth() {
        const response = await fetch(`${this.baseUrl}/api/health`);
        return response.json();
    }
}

module.exports = WhatsAppClient;
```

#### **Uso en tu aplicación:**

```javascript
// En tu aplicación principal
const WhatsAppClient = require('./services/whatsapp-client');

const whatsapp = new WhatsAppClient('http://whatsapp-service:3001');

// Enviar mensaje
app.post('/send-whatsapp', async (req, res) => {
    try {
        const { to, message } = req.body;
        const result = await whatsapp.sendMessage(to, message);
        res.json(result);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});
```

---

### **Opción 4: Integración via Redis Pub/Sub**

#### **Escuchar mensajes entrantes:**

```javascript
// message-listener.js en tu aplicación principal
const Redis = require('redis');

class WhatsAppMessageListener {
    constructor() {
        this.subscriber = Redis.createClient({
            url: process.env.REDIS_URL || 'redis://localhost:6379'
        });
    }

    async start() {
        await this.subscriber.connect();
        
        // Escuchar mensajes entrantes de WhatsApp
        await this.subscriber.subscribe('whatsapp:messages:inbound', (message) => {
            const messageData = JSON.parse(message);
            this.handleIncomingMessage(messageData);
        });
    }

    handleIncomingMessage(messageData) {
        console.log('Mensaje recibido:', messageData);
        // Procesar el mensaje en tu aplicación
        // Ejemplo: guardar en base de datos, enviar notificación, etc.
    }
}

// Uso
const listener = new WhatsAppMessageListener();
listener.start();
```

#### **Enviar mensajes via Redis:**

```javascript
// whatsapp-publisher.js en tu aplicación principal
const Redis = require('redis');

class WhatsAppPublisher {
    constructor() {
        this.publisher = Redis.createClient({
            url: process.env.REDIS_URL || 'redis://localhost:6379'
        });
    }

    async sendMessage(to, message, type = 'text') {
        const messageData = {
            to,
            message,
            type,
            timestamp: new Date().toISOString(),
            id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
        };

        await this.publisher.publish('whatsapp:messages:outbound', JSON.stringify(messageData));
        return messageData.id;
    }
}
```

---

## 🔧 **Configuración de Variables de Entorno**

### **Variables Requeridas:**

```env
# .env en tu proyecto principal
NODE_ENV=production
REDIS_URL=redis://localhost:6379

# WhatsApp Service específicas
WHATSAPP_SERVICE_URL=http://localhost:3001
WHATSAPP_SESSION_NAME=mi-proyecto-session
```

### **Variables del WhatsApp Service:**

```env
# .env en whatsapp-service/
NODE_ENV=production
PORT=3001
SERVICE_NAME=whatsapp-service
REDIS_URL=redis://localhost:6379
LOG_LEVEL=info
WHATSAPP_SESSION_NAME=mi-proyecto-session
WHATSAPP_PRINT_QR=true
```

---

## 🚀 **Scripts de Inicio**

### **Script de inicio completo:**

```bash
#!/bin/bash
# start-services.sh

echo "🚀 Iniciando servicios..."

# Iniciar Redis
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Iniciar WhatsApp Service
cd services/whatsapp-service
npm run start:prod &

# Iniciar aplicación principal
cd ../..
npm start

echo "✅ Todos los servicios iniciados"
```

---

## 📋 **Checklist de Integración**

### **Antes de Integrar:**
- [ ] Redis instalado y ejecutándose
- [ ] Node.js 18+ instalado
- [ ] Variables de entorno configuradas
- [ ] Puertos disponibles (3001 para WhatsApp Service)

### **Después de Integrar:**
- [ ] WhatsApp Service responde en `/api/health`
- [ ] Conexión WhatsApp establecida (QR escaneado)
- [ ] Redis pub/sub funcionando
- [ ] Mensajes de prueba enviados exitosamente

---

## 🔍 **Verificación de Funcionamiento**

```bash
# Verificar que el servicio esté ejecutándose
curl http://localhost:3001/api/health

# Verificar conexión WhatsApp
curl http://localhost:3001/api/status

# Enviar mensaje de prueba
curl -X POST http://localhost:3001/api/send \
  -H "Content-Type: application/json" \
  -d '{"to":"+1234567890","message":"Prueba desde mi proyecto","type":"text"}'
```

---

## 💡 **Recomendaciones**

### **Para Desarrollo:**
- Usa la **Opción 1** (copia directa) para prototipado rápido
- Configura variables de entorno específicas para tu proyecto

### **Para Producción:**
- Usa la **Opción 2** (Docker) para mejor aislamiento
- Implementa monitoreo y logs centralizados
- Configura backups de sesiones WhatsApp

### **Para Escalabilidad:**
- Usa **Redis Pub/Sub** para comunicación asíncrona
- Implementa múltiples instancias del servicio si es necesario
- Considera usar un API Gateway para enrutamiento

---

## 🆘 **Soporte y Troubleshooting**

### **Problemas Comunes:**

1. **Puerto ocupado:**
   ```bash
   # Cambiar puerto en .env
   PORT=3002
   ```

2. **Redis no conecta:**
   ```bash
   # Verificar Redis
   redis-cli ping
   ```

3. **WhatsApp no conecta:**
   - Escanear QR nuevamente
   - Verificar sesiones en `/sessions`

### **Logs Útiles:**
```bash
# Ver logs del servicio
docker logs whatsapp-service

# Ver logs de Redis
docker logs redis
```

¡El servicio está listo para ser integrado en cualquier proyecto! 🎉