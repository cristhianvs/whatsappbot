const { jest } = require('@jest/globals');
const ResponseHandler = require('../../../services/whatsapp-service/src/handlers/responseHandler');

// Mock dependencies
jest.mock('redis');

const mockRedis = {
  connect: jest.fn().mockResolvedValue(true),
  duplicate: jest.fn().mockReturnThis(),
  subscribe: jest.fn().mockResolvedValue(true),
  disconnect: jest.fn().mockResolvedValue(true)
};

const mockWhatsAppService = {
  sendMessage: jest.fn().mockResolvedValue(true)
};

// Mock Redis
const { createClient } = require('redis');
createClient.mockReturnValue(mockRedis);

describe('ResponseHandler', () => {
  let responseHandler;

  beforeEach(() => {
    jest.clearAllMocks();
    responseHandler = new ResponseHandler(mockWhatsAppService);
  });

  describe('Initialization', () => {
    test('should initialize successfully', async () => {
      await responseHandler.initialize();

      expect(createClient).toHaveBeenCalled();
      expect(mockRedis.connect).toHaveBeenCalled();
      expect(mockRedis.duplicate).toHaveBeenCalled();
      expect(mockRedis.subscribe).toHaveBeenCalledWith('agents:responses', expect.any(Function));
      expect(mockRedis.subscribe).toHaveBeenCalledWith('tickets:created', expect.any(Function));
      expect(mockRedis.subscribe).toHaveBeenCalledWith('tickets:updated', expect.any(Function));
    });

    test('should handle initialization failure', async () => {
      mockRedis.connect.mockRejectedValueOnce(new Error('Connection failed'));

      await expect(responseHandler.initialize()).rejects.toThrow('Connection failed');
    });
  });

  describe('Agent Response Handling', () => {
    beforeEach(async () => {
      await responseHandler.initialize();
    });

    test('should handle agent response correctly', async () => {
      const responseData = {
        groupId: '120363123456@g.us',
        messageId: 'test-123',
        response: 'Gracias por tu mensaje. Hemos registrado tu solicitud.',
        responseType: 'classification_response'
      };

      await responseHandler.handleAgentResponse(responseData);

      expect(mockWhatsAppService.sendMessage).toHaveBeenCalledWith(
        '120363123456@g.us',
        'Gracias por tu mensaje. Hemos registrado tu solicitud.'
      );
    });

    test('should ignore invalid agent response data', async () => {
      const invalidData = {
        messageId: 'test-123',
        responseType: 'classification_response'
        // Missing groupId and response
      };

      await responseHandler.handleAgentResponse(invalidData);

      expect(mockWhatsAppService.sendMessage).not.toHaveBeenCalled();
    });

    test('should handle WhatsApp send message failure', async () => {
      mockWhatsAppService.sendMessage.mockRejectedValueOnce(new Error('Send failed'));

      const responseData = {
        groupId: '120363123456@g.us',
        messageId: 'test-123',
        response: 'Test response',
        responseType: 'classification_response'
      };

      // Should not throw, just log error
      await expect(responseHandler.handleAgentResponse(responseData)).resolves.toBeUndefined();
    });
  });

  describe('Ticket Created Handling', () => {
    beforeEach(async () => {
      await responseHandler.initialize();
    });

    test('should handle ticket created notification', async () => {
      const ticketData = {
        groupId: '120363123456@g.us',
        ticketId: 'TICKET-123',
        ticketNumber: '#12345',
        summary: 'Sistema POS no funciona'
      };

      await responseHandler.handleTicketCreated(ticketData);

      expect(mockWhatsAppService.sendMessage).toHaveBeenCalledWith(
        '120363123456@g.us',
        expect.stringContaining('✅ *Ticket creado exitosamente*')
      );
      expect(mockWhatsAppService.sendMessage).toHaveBeenCalledWith(
        '120363123456@g.us',
        expect.stringContaining('#12345')
      );
      expect(mockWhatsAppService.sendMessage).toHaveBeenCalledWith(
        '120363123456@g.us',
        expect.stringContaining('Sistema POS no funciona')
      );
    });

    test('should ignore invalid ticket created data', async () => {
      const invalidData = {
        summary: 'Test ticket'
        // Missing groupId and ticketId
      };

      await responseHandler.handleTicketCreated(invalidData);

      expect(mockWhatsAppService.sendMessage).not.toHaveBeenCalled();
    });
  });

  describe('Ticket Updated Handling', () => {
    beforeEach(async () => {
      await responseHandler.initialize();
    });

    test('should handle ticket updated notification', async () => {
      const ticketData = {
        groupId: '120363123456@g.us',
        ticketNumber: '#12345',
        status: 'En Progreso',
        comment: 'Técnico asignado al caso'
      };

      await responseHandler.handleTicketUpdated(ticketData);

      expect(mockWhatsAppService.sendMessage).toHaveBeenCalledWith(
        '120363123456@g.us',
        expect.stringContaining('🔄 *Actualización de ticket #12345*')
      );
      expect(mockWhatsAppService.sendMessage).toHaveBeenCalledWith(
        '120363123456@g.us',
        expect.stringContaining('En Progreso')
      );
      expect(mockWhatsAppService.sendMessage).toHaveBeenCalledWith(
        '120363123456@g.us',
        expect.stringContaining('Técnico asignado al caso')
      );
    });

    test('should handle ticket update without comment', async () => {
      const ticketData = {
        groupId: '120363123456@g.us',
        ticketNumber: '#12345',
        status: 'Resuelto'
      };

      await responseHandler.handleTicketUpdated(ticketData);

      expect(mockWhatsAppService.sendMessage).toHaveBeenCalledWith(
        '120363123456@g.us',
        expect.stringContaining('🔄 *Actualización de ticket #12345*')
      );
      expect(mockWhatsAppService.sendMessage).toHaveBeenCalledWith(
        '120363123456@g.us',
        expect.stringContaining('Resuelto')
      );
    });

    test('should ignore invalid ticket updated data', async () => {
      const invalidData = {
        status: 'Resuelto'
        // Missing groupId and ticketNumber
      };

      await responseHandler.handleTicketUpdated(invalidData);

      expect(mockWhatsAppService.sendMessage).not.toHaveBeenCalled();
    });
  });

  describe('Cleanup', () => {
    test('should disconnect properly', async () => {
      await responseHandler.initialize();
      await responseHandler.disconnect();

      expect(mockRedis.disconnect).toHaveBeenCalled();
      expect(responseHandler.isListening).toBe(false);
    });
  });
});