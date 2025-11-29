/**
 * WhatsApp Service Client
 * Cliente para integrar el WhatsApp Service en tu aplicación
 */

class WhatsAppClient {
    constructor(options = {}) {
        this.baseUrl = options.baseUrl || process.env.WHATSAPP_SERVICE_URL || 'http://localhost:3001';
        this.timeout = options.timeout || 10000;
    }

    /**
     * Enviar mensaje de texto
     * @param {string} to - Número de teléfono (ej: +5215512345678)
     * @param {string} message - Mensaje a enviar
     * @param {string} type - Tipo de mensaje (default: 'text')
     * @returns {Promise<Object>} Respuesta del servicio
     */
    async sendMessage(to, message, type = 'text') {
        try {
            const response = await this.makeRequest('/api/send', {
                method: 'POST',
                body: JSON.stringify({ to, message, type })
            });
            return response;
        } catch (error) {
            throw new Error(`Error enviando mensaje: ${error.message}`);
        }
    }

    /**
     * Obtener estado de conexión WhatsApp
     * @returns {Promise<Object>} Estado de la conexión
     */
    async getConnectionStatus() {
        try {
            return await this.makeRequest('/api/status');
        } catch (error) {
            throw new Error(`Error obteniendo estado: ${error.message}`);
        }
    }

    /**
     * Verificar salud del servicio
     * @returns {Promise<Object>} Estado de salud
     */
    async getHealth() {
        try {
            return await this.makeRequest('/api/health');
        } catch (error) {
            throw new Error(`Error verificando salud: ${error.message}`);
        }
    }

    /**
     * Verificar si el servicio está disponible
     * @returns {Promise<boolean>} True si está disponible
     */
    async isAvailable() {
        try {
            const health = await this.getHealth();
            return health.status === 'healthy';
        } catch (error) {
            return false;
        }
    }

    /**
     * Esperar a que el servicio esté disponible
     * @param {number} maxAttempts - Máximo número de intentos
     * @param {number} delay - Delay entre intentos en ms
     * @returns {Promise<boolean>} True si se conectó
     */
    async waitForService(maxAttempts = 30, delay = 1000) {
        for (let i = 0; i < maxAttempts; i++) {
            if (await this.isAvailable()) {
                return true;
            }
            await new Promise(resolve => setTimeout(resolve, delay));
        }
        return false;
    }

    /**
     * Realizar petición HTTP al servicio
     * @private
     */
    async makeRequest(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            timeout: this.timeout,
            ...options
        };

        const response = await fetch(url, config);
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }

        return await response.json();
    }
}

module.exports = WhatsAppClient;