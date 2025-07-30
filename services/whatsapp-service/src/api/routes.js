const express = require('express');
const router = express.Router();
const logger = require('../utils/logger');

class WhatsAppRoutes {
  constructor(whatsappService) {
    this.whatsappService = whatsappService;
    this.setupRoutes();
  }

  setupRoutes() {
    // Send message endpoint
    router.post('/send-message', async (req, res) => {
      try {
        const { jid, text, mentions } = req.body;
        
        if (!jid || !text) {
          return res.status(400).json({
            error: 'Missing required fields: jid and text'
          });
        }

        await this.whatsappService.sendMessage(jid, text, mentions);
        
        res.json({
          success: true,
          message: 'Message sent successfully'
        });
      } catch (error) {
        logger.error('Failed to send message via API:', error);
        res.status(500).json({
          error: 'Failed to send message',
          details: error.message
        });
      }
    });

    // Get connection status
    router.get('/status', (req, res) => {
      res.json({
        connected: this.whatsappService.isConnected,
        service: 'whatsapp-service',
        timestamp: new Date().toISOString()
      });
    });

    // Download media endpoint
    router.post('/download-media', async (req, res) => {
      try {
        const { message } = req.body;
        
        if (!message) {
          return res.status(400).json({
            error: 'Missing message data'
          });
        }

        const buffer = await this.whatsappService.downloadMedia(message);
        
        res.json({
          success: true,
          mediaBuffer: buffer.toString('base64')
        });
      } catch (error) {
        logger.error('Failed to download media via API:', error);
        res.status(500).json({
          error: 'Failed to download media',
          details: error.message
        });
      }
    });
  }

  getRouter() {
    return router;
  }
}

module.exports = WhatsAppRoutes;