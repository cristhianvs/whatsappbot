const { makeWASocket, DisconnectReason, useMultiFileAuthState } = require('@whiskeysockets/baileys');
const { createClient } = require('redis');
const logger = require('./utils/logger');

class WhatsAppService {
  constructor() {
    this.socket = null;
    this.redis = null;
    this.isConnected = false;
  }

  async initialize() {
    try {
      // Initialize Redis connection
      this.redis = createClient({
        url: process.env.REDIS_URL || 'redis://localhost:6379'
      });
      
      await this.redis.connect();
      logger.info('Connected to Redis');

      // Initialize WhatsApp connection
      await this.connectWhatsApp();
      
    } catch (error) {
      logger.error('Failed to initialize WhatsApp service:', error);
      throw error;
    }
  }

  async connectWhatsApp() {
    try {
      const { state, saveCreds } = await useMultiFileAuthState('./sessions');
      
      this.socket = makeWASocket({
        auth: state,
        printQRInTerminal: true,
        logger: logger.child({ module: 'baileys' })
      });

      this.socket.ev.on('connection.update', this.handleConnectionUpdate.bind(this));
      this.socket.ev.on('creds.update', saveCreds);
      this.socket.ev.on('messages.upsert', this.handleIncomingMessages.bind(this));
      
      logger.info('WhatsApp socket initialized');
      
    } catch (error) {
      logger.error('Failed to connect to WhatsApp:', error);
      throw error;
    }
  }

  handleConnectionUpdate({ connection, lastDisconnect }) {
    if (connection === 'close') {
      const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
      
      logger.info('Connection closed. Reconnecting:', shouldReconnect);
      
      if (shouldReconnect) {
        this.connectWhatsApp();
      }
      
      this.isConnected = false;
    } else if (connection === 'open') {
      logger.info('WhatsApp connection established');
      this.isConnected = true;
    }
  }

  async handleIncomingMessages({ messages, type }) {
    if (type !== 'notify') return;

    for (const message of messages) {
      try {
        // Skip messages from self
        if (message.key.fromMe) continue;

        // Process group messages only
        if (message.key.remoteJid?.endsWith('@g.us')) {
          await this.processGroupMessage(message);
        }
        
      } catch (error) {
        logger.error('Error processing message:', error);
      }
    }
  }

  async processGroupMessage(message) {
    const messageData = {
      id: message.key.id,
      from: message.key.participant || message.key.remoteJid,
      groupId: message.key.remoteJid,
      text: message.message?.conversation || 
            message.message?.extendedTextMessage?.text || '',
      timestamp: message.messageTimestamp,
      hasMedia: !!(message.message?.imageMessage || 
                   message.message?.documentMessage ||
                   message.message?.videoMessage)
    };

    // Publish to Redis for processing by other services
    await this.redis.publish('whatsapp:messages:inbound', JSON.stringify(messageData));
    
    logger.info('Message forwarded to processing queue:', {
      messageId: messageData.id,
      from: messageData.from,
      hasText: !!messageData.text,
      hasMedia: messageData.hasMedia
    });
  }

  async sendMessage(jid, text, mentions = []) {
    if (!this.isConnected) {
      throw new Error('WhatsApp not connected');
    }

    try {
      await this.socket.sendMessage(jid, {
        text,
        mentions
      });
      
      logger.info('Message sent successfully', { to: jid });
    } catch (error) {
      logger.error('Failed to send message:', error);
      throw error;
    }
  }

  async downloadMedia(message) {
    try {
      const buffer = await downloadMediaMessage(message, 'buffer', {});
      return buffer;
    } catch (error) {
      logger.error('Failed to download media:', error);
      throw error;
    }
  }

  async disconnect() {
    if (this.socket) {
      await this.socket.logout();
    }
    
    if (this.redis) {
      await this.redis.disconnect();
    }
    
    logger.info('WhatsApp service disconnected');
  }
}

module.exports = WhatsAppService;