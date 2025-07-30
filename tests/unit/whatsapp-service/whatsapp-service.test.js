const { jest } = require('@jest/globals');
const WhatsAppService = require('../../../services/whatsapp-service/src/whatsapp-service');

// Mock dependencies
jest.mock('@whiskeysockets/baileys');
jest.mock('redis');

const mockRedis = {
  connect: jest.fn().mockResolvedValue(true),
  publish: jest.fn().mockResolvedValue(1),
  disconnect: jest.fn().mockResolvedValue(true)
};

const mockSocket = {
  ev: {
    on: jest.fn()
  },
  sendMessage: jest.fn().mockResolvedValue(true),
  logout: jest.fn().mockResolvedValue(true)
};

// Mock Baileys
const { makeWASocket, useMultiFileAuthState } = require('@whiskeysockets/baileys');
makeWASocket.mockReturnValue(mockSocket);
useMultiFileAuthState.mockResolvedValue({
  state: {},
  saveCreds: jest.fn()
});

// Mock Redis
const { createClient } = require('redis');
createClient.mockReturnValue(mockRedis);

describe('WhatsAppService', () => {
  let whatsappService;

  beforeEach(() => {
    jest.clearAllMocks();
    whatsappService = new WhatsAppService();
  });

  describe('Initialization', () => {
    test('should initialize successfully', async () => {
      await whatsappService.initialize();

      expect(createClient).toHaveBeenCalled();
      expect(mockRedis.connect).toHaveBeenCalled();
      expect(makeWASocket).toHaveBeenCalled();
    });

    test('should handle Redis connection failure', async () => {
      mockRedis.connect.mockRejectedValueOnce(new Error('Redis connection failed'));

      await expect(whatsappService.initialize()).rejects.toThrow('Redis connection failed');
    });
  });

  describe('Message Processing', () => {
    beforeEach(async () => {
      await whatsappService.initialize();
    });

    test('should process group message correctly', async () => {
      const mockMessage = {
        key: {
          id: 'test-message-123',
          participant: '+573001234567@c.us',
          remoteJid: '120363123456@g.us',
          fromMe: false
        },
        message: {
          conversation: 'El sistema POS no funciona'
        },
        messageTimestamp: 1640995200
      };

      await whatsappService.processGroupMessage(mockMessage);

      expect(mockRedis.publish).toHaveBeenCalledWith(
        'whatsapp:messages:inbound',
        expect.stringContaining('El sistema POS no funciona')
      );
    });

    test('should skip messages from self', async () => {
      const mockMessage = {
        key: {
          id: 'test-message-123',
          remoteJid: '120363123456@g.us',
          fromMe: true
        },
        message: {
          conversation: 'Test message'
        }
      };

      // Process through handleIncomingMessages to test the fromMe filter
      await whatsappService.handleIncomingMessages({
        messages: [mockMessage],
        type: 'notify'
      });

      expect(mockRedis.publish).not.toHaveBeenCalled();
    });

    test('should skip empty messages', async () => {
      const mockMessage = {
        key: {
          id: 'test-message-123',
          participant: '+573001234567@c.us',
          remoteJid: '120363123456@g.us',
          fromMe: false
        },
        message: {},
        messageTimestamp: 1640995200
      };

      await whatsappService.processGroupMessage(mockMessage);

      expect(mockRedis.publish).not.toHaveBeenCalled();
    });

    test('should filter by target group ID when configured', async () => {
      process.env.WHATSAPP_GROUP_ID = '120363999999@g.us';
      
      const mockMessage = {
        key: {
          id: 'test-message-123',
          participant: '+573001234567@c.us',
          remoteJid: '120363123456@g.us', // Different group
          fromMe: false
        },
        message: {
          conversation: 'Test message'
        },
        messageTimestamp: 1640995200
      };

      await whatsappService.processGroupMessage(mockMessage);

      expect(mockRedis.publish).not.toHaveBeenCalled();
      
      // Cleanup
      delete process.env.WHATSAPP_GROUP_ID;
    });

    test('should detect message types correctly', () => {
      const textMessage = { conversation: 'Hello' };
      const extendedTextMessage = { extendedTextMessage: { text: 'Hello' } };
      const imageMessage = { imageMessage: { url: 'image.jpg' } };

      expect(whatsappService.getMessageType(textMessage)).toBe('text');
      expect(whatsappService.getMessageType(extendedTextMessage)).toBe('extended_text');
      expect(whatsappService.getMessageType(imageMessage)).toBe('image');
    });
  });

  describe('Connection Handling', () => {
    beforeEach(async () => {
      await whatsappService.initialize();
    });

    test('should handle connection open event', () => {
      whatsappService.handleConnectionUpdate({ connection: 'open' });
      expect(whatsappService.isConnected).toBe(true);
    });

    test('should handle connection close with reconnect', () => {
      const mockReconnect = jest.spyOn(whatsappService, 'connectWhatsApp').mockResolvedValue();
      
      whatsappService.handleConnectionUpdate({ 
        connection: 'close',
        lastDisconnect: {
          error: {
            output: { statusCode: 428 } // Not logged out
          }
        }
      });

      expect(whatsappService.isConnected).toBe(false);
      expect(mockReconnect).toHaveBeenCalled();
    });

    test('should not reconnect when logged out', () => {
      const mockReconnect = jest.spyOn(whatsappService, 'connectWhatsApp');
      
      whatsappService.handleConnectionUpdate({ 
        connection: 'close',
        lastDisconnect: {
          error: {
            output: { statusCode: 401 } // Logged out
          }
        }
      });

      expect(whatsappService.isConnected).toBe(false);
      expect(mockReconnect).not.toHaveBeenCalled();
    });
  });

  describe('Message Sending', () => {
    beforeEach(async () => {
      await whatsappService.initialize();
      whatsappService.isConnected = true;
    });

    test('should send message successfully', async () => {
      const jid = '120363123456@g.us';
      const text = 'Test response message';

      await whatsappService.sendMessage(jid, text);

      expect(mockSocket.sendMessage).toHaveBeenCalledWith(jid, {
        text,
        mentions: []
      });
    });

    test('should throw error when not connected', async () => {
      whatsappService.isConnected = false;

      await expect(
        whatsappService.sendMessage('test@g.us', 'test')
      ).rejects.toThrow('WhatsApp not connected');
    });

    test('should handle send message failure', async () => {
      mockSocket.sendMessage.mockRejectedValueOnce(new Error('Send failed'));

      await expect(
        whatsappService.sendMessage('test@g.us', 'test')
      ).rejects.toThrow('Send failed');
    });
  });

  describe('Cleanup', () => {
    test('should disconnect properly', async () => {
      await whatsappService.initialize();
      await whatsappService.disconnect();

      expect(mockSocket.logout).toHaveBeenCalled();
      expect(mockRedis.disconnect).toHaveBeenCalled();
    });
  });
});