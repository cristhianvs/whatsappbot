const { createClient } = require('redis');
const logger = require('../utils/logger');

class ResponseHandler {
  constructor(whatsappService) {
    this.whatsappService = whatsappService;
    this.redis = null;
    this.isListening = false;
  }

  async initialize() {
    try {
      // Initialize Redis connection for response handling
      const redisHost = process.env.REDIS_HOST || 'localhost';
      const redisPort = process.env.REDIS_PORT || 6379;
      const redisPassword = process.env.REDIS_PASSWORD;
      
      let redisUrl = `redis://${redisHost}:${redisPort}`;
      if (redisPassword) {
        redisUrl = `redis://:${redisPassword}@${redisHost}:${redisPort}`;
      }
      
      this.redis = createClient({ url: redisUrl });
      await this.redis.connect();
      
      logger.info('Response handler Redis connection established');
      
      // Start listening for responses
      await this.startListening();
      
    } catch (error) {
      logger.error('Failed to initialize response handler:', error);
      throw error;
    }
  }

  async startListening() {
    if (this.isListening) return;
    
    try {
      // Subscribe to response channels
      const subscriber = this.redis.duplicate();
      await subscriber.connect();
      
      await subscriber.subscribe('agents:responses', async (message) => {
        await this.handleAgentResponse(JSON.parse(message));
      });
      
      await subscriber.subscribe('tickets:created', async (message) => {
        await this.handleTicketCreated(JSON.parse(message));
      });
      
      await subscriber.subscribe('tickets:updated', async (message) => {
        await this.handleTicketUpdated(JSON.parse(message));
      });
      
      this.isListening = true;
      logger.info('Response handler started listening to Redis channels');
      
    } catch (error) {
      logger.error('Failed to start response handler listening:', error);
      throw error;
    }
  }

  async handleAgentResponse(responseData) {
    try {
      const { groupId, messageId, response, responseType } = responseData;
      
      if (!groupId || !response) {
        logger.warn('Invalid agent response data received');
        return;
      }

      // Send response back to WhatsApp group
      await this.whatsappService.sendMessage(groupId, response);
      
      logger.info('Agent response sent to WhatsApp:', {
        groupId,
        originalMessageId: messageId,
        responseType,
        responseLength: response.length
      });
      
    } catch (error) {
      logger.error('Failed to handle agent response:', error);
    }
  }

  async handleTicketCreated(ticketData) {
    try {
      const { groupId, ticketId, ticketNumber, summary } = ticketData;
      
      if (!groupId || !ticketId) {
        logger.warn('Invalid ticket created data received');
        return;
      }

      const message = `✅ *Ticket creado exitosamente*\n\n` +
                     `🎫 *Número:* ${ticketNumber}\n` +
                     `📋 *Resumen:* ${summary}\n\n` +
                     `Tu solicitud ha sido registrada y será atendida por nuestro equipo de soporte.`;

      await this.whatsappService.sendMessage(groupId, message);
      
      logger.info('Ticket creation confirmation sent:', {
        groupId,
        ticketId,
        ticketNumber
      });
      
    } catch (error) {
      logger.error('Failed to handle ticket created notification:', error);
    }
  }

  async handleTicketUpdated(ticketData) {
    try {
      const { groupId, ticketNumber, status, comment } = ticketData;
      
      if (!groupId || !ticketNumber) {
        logger.warn('Invalid ticket updated data received');
        return;
      }

      let message = `🔄 *Actualización de ticket #${ticketNumber}*\n\n`;
      message += `📊 *Estado:* ${status}\n`;
      
      if (comment) {
        message += `💬 *Comentario:* ${comment}\n`;
      }

      await this.whatsappService.sendMessage(groupId, message);
      
      logger.info('Ticket update notification sent:', {
        groupId,
        ticketNumber,
        status
      });
      
    } catch (error) {
      logger.error('Failed to handle ticket updated notification:', error);
    }
  }

  async disconnect() {
    this.isListening = false;
    if (this.redis) {
      await this.redis.disconnect();
      logger.info('Response handler disconnected from Redis');
    }
  }
}

module.exports = ResponseHandler;