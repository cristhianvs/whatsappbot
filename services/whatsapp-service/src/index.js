import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import WhatsAppService from './whatsapp-service.js';
import apiRoutes from './api/routes.js';
import logger from './utils/logger.js';

const app = express();
const port = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// Request logging middleware
app.use((req, res, next) => {
    logger.info(`${req.method} ${req.path}`, {
        ip: req.ip,
        userAgent: req.get('User-Agent')
    });
    next();
});

async function startServer() {
    try {
        logger.info('Starting WhatsApp Service...', {
            port,
            nodeEnv: process.env.NODE_ENV,
            serviceName: process.env.SERVICE_NAME
        });

        // Initialize WhatsApp Service
        const whatsappService = new WhatsAppService();
        await whatsappService.initialize();
        
        // Make services available to routes
        app.locals.whatsappService = whatsappService;
        app.locals.redisClient = whatsappService.redisClient;
        app.locals.logger = logger;
        
        // Configure routes
        app.use('/api', apiRoutes);
        
        // Global error handler
        app.use((error, req, res, next) => {
            logger.error('Unhandled API error:', error);
            res.status(500).json({
                error: 'Internal server error',
                message: process.env.NODE_ENV === 'development' ? error.message : 'Something went wrong'
            });
        });
        
        // 404 handler
        app.use('*', (req, res) => {
            res.status(404).json({
                error: 'Not found',
                message: `Route ${req.originalUrl} not found`
            });
        });
        
        // Start server
        const server = app.listen(port, () => {
            logger.info(`WhatsApp Service running on port ${port}`, {
                port,
                environment: process.env.NODE_ENV
            });
        });

        // Graceful shutdown handling
        const gracefulShutdown = async (signal) => {
            logger.info(`Received ${signal}, shutting down gracefully...`);
            
            server.close(async () => {
                try {
                    if (whatsappService) {
                        await whatsappService.shutdown();
                    }
                    logger.info('WhatsApp Service shut down successfully');
                    process.exit(0);
                } catch (error) {
                    logger.error('Error during shutdown:', error);
                    process.exit(1);
                }
            });
        };

        process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
        process.on('SIGINT', () => gracefulShutdown('SIGINT'));
        
    } catch (error) {
        logger.error('Error starting WhatsApp Service:', error);
        process.exit(1);
    }
}

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
    logger.error('Uncaught Exception:', error);
    process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
    logger.error('Unhandled Rejection at:', promise, 'reason:', reason);
    process.exit(1);
});

startServer();