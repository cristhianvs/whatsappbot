const express = require('express');
const cors = require('cors');
require('dotenv').config();

const WhatsAppService = require('./whatsapp-service');
const WhatsAppRoutes = require('./api/routes');
const ResponseHandler = require('./handlers/responseHandler');
const logger = require('./utils/logger');

const app = express();
const PORT = process.env.PORT || 3001;

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

// Initialize response handler
const responseHandler = new ResponseHandler(whatsappService);

// Setup API routes
const apiRoutes = new WhatsAppRoutes(whatsappService);
app.use('/api', apiRoutes.getRouter());

// Start server
app.listen(PORT, async () => {
  logger.info(`WhatsApp service running on port ${PORT}`);
  
  try {
    await whatsappService.initialize();
    await responseHandler.initialize();
    logger.info('WhatsApp service initialized successfully');
  } catch (error) {
    logger.error('Failed to initialize WhatsApp service:', error);
    process.exit(1);
  }
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  logger.info('Shutting down WhatsApp service...');
  await responseHandler.disconnect();
  await whatsappService.disconnect();
  process.exit(0);
});

process.on('SIGINT', async () => {
  logger.info('Received SIGINT, shutting down gracefully...');
  await responseHandler.disconnect();
  await whatsappService.disconnect();
  process.exit(0);
});