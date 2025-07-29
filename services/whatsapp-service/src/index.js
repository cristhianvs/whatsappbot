const express = require('express');
const cors = require('cors');
require('dotenv').config();

const WhatsAppService = require('./whatsapp-service');
const logger = require('./utils/logger');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ 
    status: 'healthy',
    service: 'whatsapp-service',
    timestamp: new Date().toISOString()
  });
});

// Initialize WhatsApp service
const whatsappService = new WhatsAppService();

// Start server
app.listen(PORT, async () => {
  logger.info(`WhatsApp service running on port ${PORT}`);
  
  try {
    await whatsappService.initialize();
    logger.info('WhatsApp service initialized successfully');
  } catch (error) {
    logger.error('Failed to initialize WhatsApp service:', error);
    process.exit(1);
  }
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  logger.info('Shutting down WhatsApp service...');
  await whatsappService.disconnect();
  process.exit(0);
});