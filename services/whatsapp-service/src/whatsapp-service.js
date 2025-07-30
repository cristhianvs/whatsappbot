const { makeWASocket, DisconnectReason, useMultiFileAuthState, downloadMediaMessage } = require('@whiskeysockets/baileys');
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
      const redisHost = process.env.REDIS_HOST || 'localhost';
      const redisPort = process.env.REDIS_PORT || 6379;
      const redisPassword = process.env.REDIS_PASSWORD;
      
      let redisUrl = `redis://${redisHost}:${redisPort}`;
      if (redisPassword) {
        redisUrl = `redis://:${redisPassword}@${redisHost}:${redisPort}`;
      }
      
      this.redis = createClient({ url: redisUrl });
      
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
    // Only process messages from configured group
    const targetGroupId = process.env.WHATSAPP_GROUP_ID;
    if (targetGroupId && message.key.remoteJid !== targetGroupId) {
      return;
    }

    const messageData = {
      id: message.key.id,
      from: message.key.participant || message.key.remoteJid,
      groupId: message.key.remoteJid,
      text: message.message?.conversation || 
            message.message?.extendedTextMessage?.text || '',
      timestamp: message.messageTimestamp,
      hasMedia: !!(message.message?.imageMessage || 
                   message.message?.documentMessage ||
                   message.message?.videoMessage),
      messageType: this.getMessageType(message.message),
      rawMessage: message.message
    };

    // Skip empty messages
    if (!messageData.text && !messageData.hasMedia) {
      return;
    }

    try {
      // Publish to Redis for processing by other services
      await this.redis.publish('whatsapp:messages:inbound', JSON.stringify(messageData));
      
      logger.info('Message forwarded to processing queue:', {
        messageId: messageData.id,
        from: messageData.from,
        hasText: !!messageData.text,
        hasMedia: messageData.hasMedia,
        type: messageData.messageType
      });
    } catch (error) {
      logger.error('Failed to publish message to Redis:', error);
    }
  }

  getMessageType(message) {
    if (message.conversation) return 'text';
    if (message.extendedTextMessage) return 'extended_text';
    if (message.imageMessage) return 'image';
    if (message.documentMessage) return 'document';
    if (message.videoMessage) return 'video';
    if (message.audioMessage) return 'audio';
    return 'unknown';
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