/**
 * Listener para mensajes entrantes de WhatsApp via Redis
 * Úsalo en tu aplicación principal para recibir mensajes
 */

const Redis = require('redis');

class WhatsAppMessageListener {
    constructor(options = {}) {
        this.redisUrl = options.redisUrl || process.env.REDIS_URL || 'redis://localhost:6379';
        this.subscriber = null;
        this.messageHandlers = new Map();
        this.isConnected = false;
    }

    /**
     * Conectar al Redis y empezar a escuchar
     */
    async connect() {
        try {
            this.subscriber = Redis.createClient({ url: this.redisUrl });
            
            this.subscriber.on('error', (error) => {
                console.error('Redis error:', error);
                this.isConnected = false;
            });

            this.subscriber.on('connect', () => {
                console.log('✅ Conectado a Redis para escuchar mensajes WhatsApp');
                this.isConnected = true;
            });

            await this.subscriber.connect();
            
            // Suscribirse al canal de mensajes entrantes
            await this.subscriber.subscribe('whatsapp:messages:inbound', (message) => {
                this.handleIncomingMessage(message);
            });

            // Suscribirse a notificaciones del servicio
            await this.subscriber.subscribe('whatsapp:notifications', (notification) => {
                this.handleServiceNotification(notification);
            });

            console.log('🎧 Escuchando mensajes de WhatsApp...');

        } catch (error) {
            console.error('❌ Error conectando a Redis:', error);
            throw error;
        }
    }

    /**
     * Desconectar del Redis
     */
    async disconnect() {
        if (this.subscriber) {
            await this.subscriber.quit();
            this.isConnected = false;
            console.log('🔌 Desconectado de Redis');
        }
    }

    /**
     * Registrar handler para tipos específicos de mensajes
     * @param {string} type - Tipo de mensaje ('text', 'image', 'all')
     * @param {function} handler - Función que maneja el mensaje
     */
    onMessage(type, handler) {
        if (!this.messageHandlers.has(type)) {
            this.messageHandlers.set(type, []);
        }
        this.messageHandlers.get(type).push(handler);
    }

    /**
     * Manejar mensaje entrante
     * @private
     */
    handleIncomingMessage(rawMessage) {
        try {
            const messageData = JSON.parse(rawMessage);
            
            console.log('📨 Mensaje recibido:', {
                from: messageData.from_user,
                type: messageData.message_type,
                text: messageData.text?.substring(0, 50) + '...'
            });

            // Ejecutar handlers específicos del tipo
            const typeHandlers = this.messageHandlers.get(messageData.message_type) || [];
            const allHandlers = this.messageHandlers.get('all') || [];
            
            [...typeHandlers, ...allHandlers].forEach(handler => {
                try {
                    handler(messageData);
                } catch (error) {
                    console.error('Error en handler de mensaje:', error);
                }
            });

        } catch (error) {
            console.error('Error procesando mensaje:', error);
        }
    }

    /**
     * Manejar notificaciones del servicio
     * @private
     */
    handleServiceNotification(rawNotification) {
        try {
            const notification = JSON.parse(rawNotification);
            
            console.log('🔔 Notificación del servicio:', notification.event);

            // Manejar eventos específicos
            switch (notification.event) {
                case 'connection_established':
                    console.log('✅ WhatsApp conectado');
                    break;
                case 'connection_lost':
                    console.log('❌ WhatsApp desconectado');
                    break;
                case 'service_started':
                    console.log('🚀 Servicio WhatsApp iniciado');
                    break;
                case 'service_shutdown':
                    console.log('🛑 Servicio WhatsApp detenido');
                    break;
            }

        } catch (error) {
            console.error('Error procesando notificación:', error);
        }
    }

    /**
     * Verificar si está conectado
     */
    isListening() {
        return this.isConnected;
    }
}

module.exports = WhatsAppMessageListener;