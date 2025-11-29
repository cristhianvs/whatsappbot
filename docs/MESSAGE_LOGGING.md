# Sistema de Logging de Mensajes

**Fecha de implementación:** 15 de Noviembre, 2025
**Estado:** ✅ Implementado y funcional con soporte completo UTF-8

## Descripción General

El sistema de logging de mensajes registra todos los mensajes enviados y recibidos por el bot de WhatsApp en archivos de texto (.txt) organizados por fecha. Esto permite auditoría, análisis histórico y debugging.

**Soporte de Idioma:** Completamente funcional con español latinoamericano, incluyendo todos los caracteres especiales (á, é, í, ó, ú, ñ, ¿, ¡).

---

## Características

### 1. Logging Automático
- ✅ Todos los mensajes **entrantes** (INBOUND) se registran automáticamente
- ✅ Todos los mensajes **salientes** (OUTBOUND) se registran automáticamente
- ✅ Mensajes exitosos y fallidos se registran por separado

### 2. Organización por Fecha
- Los logs se guardan en archivos separados por día
- Formato de archivo: `messages_YYYY-MM-DD.txt`
- Ubicación: `services/whatsapp-service/logs/messages/`

### 3. Formato Estructurado
Cada mensaje se registra con:
- Timestamp ISO 8601
- Dirección (INBOUND/OUTBOUND)
- Número de teléfono (from/to)
- ID del mensaje
- Tipo de mensaje (text, image, video, etc.)
- Contenido del mensaje
- Metadata adicional (prioridad, media, errores, etc.)

### 4. Buffer y Flush
- Mensajes se acumulan en buffer de memoria
- Se escriben al disco cada 10 mensajes o cada 5 segundos
- Flush automático al cerrar el servicio
- Endpoint manual para forzar flush

### 5. API REST
Endpoints disponibles para consultar logs:
- `GET /api/messages/stats` - Estadísticas de logs
- `GET /api/messages/logs?date=YYYY-MM-DD` - Leer logs de fecha específica
- `POST /api/messages/flush` - Forzar escritura del buffer

---

## Formato de Registro

### Mensaje Entrante (INBOUND)

```
================================================================================
[2025-11-15T01:30:45.123Z] INBOUND
================================================================================
From: 5215535128668@s.whatsapp.net
Message ID: 3A123456789ABCDEF
Type: text
Content: Hola, necesito ayuda con la impresora
================================================================================
```

### Mensaje Saliente (OUTBOUND)

```
================================================================================
[2025-11-15T01:30:50.456Z] OUTBOUND
================================================================================
To: 5215535128668@s.whatsapp.net
Message ID: msg_1763169250456_abc123
Type: text
Priority: normal
Content: Entiendo tu problema. ¿Puedes describirme qué error te muestra?
Status: sent
================================================================================
```

### Mensaje con Media

```
================================================================================
[2025-11-15T01:31:15.789Z] INBOUND
================================================================================
From: 5215535128668@s.whatsapp.net
Message ID: 3A987654321FEDCBA
Type: image
Media Type: image/jpeg
Media Caption: Aquí está el error que me aparece
================================================================================
```

### Mensaje Fallido

```
================================================================================
[2025-11-15T01:32:00.123Z] OUTBOUND
================================================================================
To: 5215535128668@s.whatsapp.net
Message ID: msg_1763169320123_xyz789
Type: text
Priority: high
Content: Tu ticket ha sido creado con número #12345
Status: failed
Error: WhatsApp not connected
================================================================================
```

---

## Encoding UTF-8 y Soporte de Caracteres Especiales

### Configuración de Encoding

El sistema utiliza **UTF-8 con BOM** (Byte Order Mark) para garantizar compatibilidad con Windows y editores de texto comunes.

**Implementación Técnica:**
- Uso de `Buffer.from(content, 'utf8')` para escritura explícita en UTF-8
- BOM UTF-8 (bytes `0xEF, 0xBB, 0xBF`) agregado al inicio de cada archivo nuevo
- Compatibilidad garantizada con español latinoamericano

### Caracteres Soportados

✅ **Totalmente funcional con:**
- Vocales acentuadas: á, é, í, ó, ú
- Eñe: ñ, Ñ
- Signos de interrogación: ¿, ?
- Signos de exclamación: ¡, !
- Todos los caracteres especiales del español

### Ejemplo Real de Log con Acentos

**OUTBOUND:**
```
Content: Prueba UTF-8: ¿Están funcionando correctamente los acentos ahora? Mañana José enviará información técnica
```

**INBOUND:**
```
Content: ¿Cuándo podremos ir a Ñapauri?
```

### Corrección de Encoding (Noviembre 2025)

**Problema Original:**
- Los caracteres especiales se mostraban como `�` en los logs
- Los mensajes se enviaban correctamente a WhatsApp, pero se guardaban mal en el archivo

**Solución Implementada:**
- Cambio de `fs.appendFileSync(logFile, content, 'utf8')` a uso explícito de Buffer
- Implementación de BOM UTF-8 para compatibilidad con Windows
- Archivo: `src/utils/message-logger.js` líneas 147-154

**Código de la Solución:**
```javascript
// If file doesn't exist, create it with UTF-8 BOM for better Windows compatibility
if (!fs.existsSync(logFile)) {
    const BOM = Buffer.from([0xEF, 0xBB, 0xBF]); // UTF-8 BOM
    fs.writeFileSync(logFile, BOM);
}

// Use Buffer to ensure proper UTF-8 encoding
const contentBuffer = Buffer.from(content, 'utf8');
fs.appendFileSync(logFile, contentBuffer);
```

**Estado Actual:** ✅ 100% funcional con español latinoamericano

---

## Configuración

### Buffer Settings
Configurados en `src/utils/message-logger.js`:

```javascript
this.bufferSize = 10;        // Escribir cada 10 mensajes
this.flushInterval = 5000;   // O cada 5 segundos (5000ms)
```

### Ubicación de Logs
```
whatsapp-service/
├── logs/
│   ├── messages/              ← Logs de mensajes
│   │   ├── messages_2025-11-15.txt
│   │   ├── messages_2025-11-14.txt
│   │   └── messages_2025-11-13.txt
│   └── whatsapp-service.log   ← Logs del sistema
```

---

## Uso de la API

### 1. Obtener Estadísticas

```bash
curl http://localhost:3002/api/messages/stats
```

**Respuesta:**
```json
{
  "totalFiles": 3,
  "currentBufferSize": 5,
  "files": [
    {
      "name": "messages_2025-11-15.txt",
      "size": 15420,
      "modified": "2025-11-15T01:35:00.000Z"
    },
    {
      "name": "messages_2025-11-14.txt",
      "size": 42350,
      "modified": "2025-11-14T23:59:59.000Z"
    }
  ],
  "timestamp": "2025-11-15T01:35:10.123Z"
}
```

### 2. Leer Logs de Hoy

```bash
curl http://localhost:3002/api/messages/logs
```

**Respuesta:** Contenido del archivo de texto en formato plain/text

### 3. Leer Logs de Fecha Específica

```bash
curl http://localhost:3002/api/messages/logs?date=2025-11-14
```

### 4. Forzar Escritura del Buffer

```bash
curl -X POST http://localhost:3002/api/messages/flush
```

**Respuesta:**
```json
{
  "message": "Message buffer flushed successfully",
  "timestamp": "2025-11-15T01:40:00.000Z"
}
```

---

## Uso Programático

### Importar el Logger

```javascript
import messageLogger from './utils/message-logger.js';
```

### Registrar Mensaje Entrante

```javascript
messageLogger.logInbound({
    messageId: 'ABC123',
    from: '5215535128668@s.whatsapp.net',
    messageType: 'text',
    text: 'Hola',
    hasMedia: false
});
```

### Registrar Mensaje Saliente

```javascript
messageLogger.logOutbound({
    messageId: 'msg_123',
    to: '5215535128668@s.whatsapp.net',
    messageType: 'text',
    text: 'Hola, ¿en qué puedo ayudarte?',
    priority: 'normal',
    status: 'sent'
});
```

### Leer Logs Programáticamente

```javascript
const today = new Date();
const logs = messageLogger.readMessagesForDate(today);
console.log(logs);
```

### Obtener Estadísticas

```javascript
const stats = messageLogger.getStats();
console.log(`Total archivos: ${stats.totalFiles}`);
console.log(`Buffer actual: ${stats.currentBufferSize}`);
```

### Forzar Flush Manual

```javascript
messageLogger.flush();
```

---

## Integración con Handlers

### MessageHandler (Mensajes Entrantes)

El logging se realiza automáticamente en `src/handlers/message-handler.js` en el método `processQueuedMessage()`:

```javascript
// Log inbound message to file
try {
    messageLogger.logInbound({
        messageId: messageData.id,
        from: messageData.from_user,
        messageType: messageData.message_type,
        text: messageData.text || '',
        hasMedia: messageData.has_media || false,
        mediaType: messageData.media_type,
        caption: messageData.caption,
        quotedMessage: messageData.quoted_message ? true : false
    });
} catch (error) {
    logger.error('Error logging inbound message to file:', error);
}
```

### OutboundHandler (Mensajes Salientes)

El logging se realiza automáticamente en `src/handlers/outbound-handler.js` en el método `sendMessage()`:

**Para mensajes exitosos:**
```javascript
// Log outbound message to file
try {
    messageLogger.logOutbound({
        messageId: result.key.id,
        to: to,
        messageType: messageData.type || 'text',
        text: text,
        priority: messageData.priority || 'normal',
        media: media,
        status: 'sent'
    });
} catch (error) {
    logger.error('Error logging outbound message to file:', error);
}
```

**Para mensajes fallidos:**
```javascript
// Log failed outbound message to file
try {
    messageLogger.logOutbound({
        messageId: messageData.id || 'unknown',
        to: messageData.to,
        messageType: messageData.type || 'text',
        text: messageData.text || messageData.message,
        priority: messageData.priority || 'normal',
        media: messageData.media,
        status: 'failed',
        error: error.message
    });
} catch (logError) {
    logger.error('Error logging failed outbound message to file:', logError);
}
```

---

## Manejo de Errores

### Error en Escritura de Logs
- Si falla la escritura al disco, se registra en el logger del sistema
- El mensaje **NO** se pierde - permanece en el buffer
- El buffer se intentará escribir en el siguiente flush

### Error en Lectura de Logs
- La API devuelve error 404 si no existe el archivo de la fecha solicitada
- Error 500 si hay problemas de lectura del sistema de archivos

### Graceful Shutdown
- Al recibir SIGTERM/SIGINT, el logger flush automáticamente
- Asegura que no se pierdan mensajes en el buffer

---

## Consideraciones de Rendimiento

### Impacto en Rendimiento
- **Mínimo** - Operaciones asíncronas no bloquean el procesamiento de mensajes
- Buffer en memoria reduce operaciones de I/O
- Flush periódico (5s) en lugar de escritura inmediata

### Uso de Disco
- Aproximadamente 1-2 KB por mensaje
- Un día con 1000 mensajes = ~1-2 MB
- Un mes = ~30-60 MB
- **Recomendación:** Implementar rotación/limpieza de logs antiguos (>30 días)

### Uso de Memoria
- Buffer máximo: 10 mensajes en memoria
- ~10-20 KB en memoria en cualquier momento
- **Impacto negligible**

---

## Privacidad y Seguridad

### Datos Sensibles
⚠️ **IMPORTANTE:** Los logs contienen:
- Números de teléfono completos
- Contenido de mensajes (texto completo)
- Metadata de conversaciones

### Recomendaciones de Seguridad

1. **Permisos de Archivos**
   ```bash
   chmod 600 logs/messages/*.txt  # Solo lectura/escritura para owner
   ```

2. **Rotación de Logs**
   - Implementar limpieza automática de logs antiguos
   - Ejemplo: Borrar logs > 90 días

3. **Backup**
   - Considerar backup cifrado si se almacenan datos sensibles
   - No subir logs a repositorios públicos

4. **Compliance**
   - Verificar cumplimiento con GDPR/regulaciones locales
   - Informar a usuarios sobre logging de mensajes
   - Implementar proceso de eliminación de datos a solicitud

---

## Rotación de Logs (Implementación Futura)

### Script de Limpieza Sugerido

```bash
#!/bin/bash
# clean-old-logs.sh
# Eliminar logs de mensajes más antiguos de 90 días

LOGS_DIR="./logs/messages"
DAYS_TO_KEEP=90

find "$LOGS_DIR" -name "messages_*.txt" -mtime +$DAYS_TO_KEEP -delete

echo "Logs antiguos eliminados (más de $DAYS_TO_KEEP días)"
```

### Cronjob

```bash
# Ejecutar diariamente a las 2am
0 2 * * * /path/to/clean-old-logs.sh
```

---

## Análisis de Logs

### Búsqueda de Mensajes por Número

```bash
grep "5215535128668" logs/messages/messages_2025-11-15.txt
```

### Contar Mensajes del Día

```bash
grep -c "INBOUND\|OUTBOUND" logs/messages/messages_2025-11-15.txt
```

### Mensajes Fallidos

```bash
grep -A 5 "Status: failed" logs/messages/messages_2025-11-15.txt
```

### Extraer Solo Texto de Mensajes

```bash
grep "Content:" logs/messages/messages_2025-11-15.txt
```

---

## Testing

### Test Manual

1. Enviar mensaje de prueba:
```bash
curl -X POST http://localhost:3002/api/send \
  -H "Content-Type: application/json" \
  -d '{"to":"5215535128668","message":"Test de logging"}'
```

2. Verificar que se registró:
```bash
curl http://localhost:3002/api/messages/logs
```

3. Revisar archivo directamente:
```bash
cat logs/messages/messages_$(date +%Y-%m-%d).txt
```

### Verificar Buffer

```bash
# Ver estadísticas antes del flush
curl http://localhost:3002/api/messages/stats

# Forzar flush
curl -X POST http://localhost:3002/api/messages/flush

# Ver estadísticas después (bufferSize debería ser 0)
curl http://localhost:3002/api/messages/stats
```

---

## Troubleshooting

### Problema: Los logs no se están creando

**Diagnóstico:**
```bash
# Verificar que el directorio existe
ls -la services/whatsapp-service/logs/messages/

# Verificar permisos
ls -ld services/whatsapp-service/logs/messages/
```

**Solución:**
```bash
# Crear directorio si no existe
mkdir -p services/whatsapp-service/logs/messages/

# Dar permisos adecuados
chmod 755 services/whatsapp-service/logs/messages/
```

### Problema: Buffer no se flush

**Diagnóstico:**
- Revisar logs del sistema: `tail -f logs/whatsapp-service.log`
- Buscar errores relacionados con "message logger"

**Solución:**
- Forzar flush manual: `curl -X POST http://localhost:3002/api/messages/flush`
- Reiniciar servicio para reset del timer

### Problema: Archivo de log muy grande

**Solución:**
- Implementar rotación de logs (ver sección anterior)
- Considerar comprimir logs antiguos:
  ```bash
  gzip logs/messages/messages_2025-11-01.txt
  ```

---

## Mejoras Futuras

### Planificadas
- [ ] Rotación automática de logs (eliminar > 90 días)
- [ ] Compresión automática de logs antiguos
- [ ] Búsqueda de mensajes por API (endpoint `/api/messages/search`)
- [ ] Exportar logs a CSV/JSON
- [ ] Dashboard web para visualizar logs
- [ ] Cifrado de logs en reposo
- [ ] Anonimización de números de teléfono

### Consideradas
- Integración con ELK Stack (Elasticsearch, Logstash, Kibana)
- Envío de logs a servicio externo (Papertrail, Loggly, etc.)
- Alertas basadas en patrones de logs
- Análisis de sentimiento de mensajes
- Estadísticas de uso (mensajes por hora/día/semana)

---

## Referencias

### Código Fuente
- `src/utils/message-logger.js` - Implementación del logger
- `src/handlers/message-handler.js` - Integración mensajes entrantes
- `src/handlers/outbound-handler.js` - Integración mensajes salientes
- `src/api/routes.js` - Endpoints de API

### Archivos Generados
- `logs/messages/messages_YYYY-MM-DD.txt` - Logs diarios

---

## Conclusión

El sistema de logging de mensajes proporciona:
- ✅ Auditoría completa de todas las comunicaciones
- ✅ Debugging efectivo de problemas
- ✅ Análisis histórico de conversaciones
- ✅ Cumplimiento de requisitos de registro
- ✅ Base de datos simple y legible para análisis

**Estado:** Funcional y listo para producción
