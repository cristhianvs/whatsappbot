# Configuracion WhatsApp - Numero Nicaragua

## Resumen

**Fecha de configuracion:** 2025-11-27
**Numero vinculado:** +505 7886 6744 (Nicaragua)
**Estado:** Activo y funcional

## Detalles de la Configuracion

### Numero Anterior
- **Numero:** +52 1 558 561 0345 (Mexico)
- **Estado:** Reemplazado

### Numero Actual
- **Numero:** +505 7886 6744 (Nicaragua)
- **Codigo de pais:** +505
- **Formato WhatsApp:** `50578866744@s.whatsapp.net`
- **Metodo de autenticacion:** Codigo QR
- **Sesion almacenada en:** `sessions/bot-session/`

## Pruebas Realizadas

### Prueba de Envio de Mensajes

| Campo | Valor |
|-------|-------|
| Fecha/Hora | 2025-11-28 02:41:00 UTC |
| Destinatario | 5215632308515 (Marcelo) |
| Mensaje | "Hola Marcelo soy Cristhian" |
| Estado | Enviado exitosamente |
| Message ID | `msg_1764297659319_kjhibv` |

**Comando utilizado:**
```bash
curl -X POST http://localhost:3002/api/send \
  -H "Content-Type: application/json" \
  -d '{"to": "5215632308515", "message": "Hola Marcelo soy Cristhian"}'
```

**Respuesta del servidor:**
```json
{
  "success": true,
  "message": "Message queued for sending",
  "message_id": "msg_1764297659319_kjhibv",
  "to": "5215632308515@s.whatsapp.net",
  "timestamp": "2025-11-28T02:40:59.319Z"
}
```

### Prueba de Recepcion de Mensajes

| Hora (UTC) | Direccion | Numero | Contenido |
|------------|-----------|--------|-----------|
| 02:39:11 | INBOUND | 50578866744 | *(mensaje inicial de vinculacion)* |
| 02:41:12 | INBOUND | 5215632308515 | "Excelente" |
| 02:41:40 | INBOUND | 5215632308515 | "Me copia del otro lado Doctor?" |

## Estado del Servicio

**Health Check:** `http://localhost:3002/api/health`

```json
{
  "status": "healthy",
  "service": "whatsapp-service",
  "version": "1.0.0",
  "whatsapp_connected": true,
  "uptime": 201.59
}
```

## Persistencia de Sesion

La sesion de WhatsApp se guarda automaticamente en:
```
services/whatsapp-service/sessions/bot-session/
```

### Comportamiento al Reiniciar
- **NO es necesario volver a escanear QR** al reiniciar el servicio
- Las credenciales se cargan automaticamente
- El servicio reconecta en segundos

### Casos que Requieren Re-vinculacion
1. Borrar la carpeta `sessions/bot-session/`
2. Desvincular desde WhatsApp movil (Ajustes > Dispositivos vinculados)
3. Corrupcion de sesion (raro)

## Comandos Utiles

### Iniciar servicio
```bash
cd services/whatsapp-service
npm start
```

### Verificar estado
```bash
curl http://localhost:3002/api/health
```

### Enviar mensaje
```bash
curl -X POST http://localhost:3002/api/send \
  -H "Content-Type: application/json" \
  -d '{"to": "NUMERO", "message": "TEXTO"}'
```

### Ver logs de mensajes
```bash
curl http://localhost:3002/api/messages/logs
```

### Monitoreo en tiempo real
```bash
tail -f services/whatsapp-service/logs/messages/messages_$(date +%Y-%m-%d).txt
```

## Configuracion Actual (.env)

```env
# WhatsApp Configuration
WHATSAPP_SESSION_NAME=bot-session
WHATSAPP_PHONE_NUMBER=50578866744
WHATSAPP_PRINT_QR=true
WHATSAPP_MARK_ONLINE=false

# Service Configuration
PORT=3002
NODE_ENV=development
SERVICE_NAME=whatsapp-service

# Redis Configuration
REDIS_URL=redis://localhost:6379
```

## Proximos Pasos Sugeridos

1. [ ] Actualizar `.env` con el nuevo numero si no se ha hecho
2. [ ] Probar integracion con classifier-service
3. [ ] Probar creacion automatica de tickets en Zoho
4. [ ] Configurar monitoreo de mensajes entrantes

## Notas Adicionales

- El numero de Nicaragua esta listo para recibir mensajes de soporte
- La integracion con el sistema de tickets esta disponible
- Los logs de mensajes incluyen soporte completo para caracteres en espanol (UTF-8)
