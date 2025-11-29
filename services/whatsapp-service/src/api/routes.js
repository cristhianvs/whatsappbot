import express from 'express';
const router = express.Router();
import logger from '../utils/logger.js';
import messageLogger from '../utils/message-logger.js';

// Middleware for request timing
router.use((req, res, next) => {
    req.startTime = Date.now();
    next();
});

// Middleware for response logging
router.use((req, res, next) => {
    const originalSend = res.send;
    
    res.send = function(data) {
        const responseTime = Date.now() - req.startTime;
        
        logger.logAPIRequest(
            req.method,
            req.path,
            res.statusCode,
            responseTime,
            req.get('User-Agent')
        );
        
        return originalSend.call(this, data);
    };
    
    next();
});

// Health check endpoint
router.get('/health', (req, res) => {
    try {
        const whatsappService = req.app.locals.whatsappService;
        
        const healthData = {
            status: 'healthy',
            service: process.env.SERVICE_NAME || 'whatsapp-service',
            version: '1.0.0',
            timestamp: new Date().toISOString(),
            uptime: process.uptime(),
            environment: process.env.NODE_ENV || 'development',
            memory: process.memoryUsage(),
            whatsapp_connected: whatsappService ? (whatsappService.socket && whatsappService.socket.user ? true : false) : false
        };
        
        res.json(healthData);
        
    } catch (error) {
        logger.error('Health check error:', error);
        res.status(500).json({
            status: 'unhealthy',
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// WhatsApp connection status endpoint
router.get('/status', (req, res) => {
    try {
        const whatsappService = req.app.locals.whatsappService;
        
        if (!whatsappService) {
            return res.status(503).json({
                error: 'WhatsApp service not initialized',
                connected: false,
                timestamp: new Date().toISOString()
            });
        }
        
        const connectionStatus = whatsappService.getConnectionStatus();
        const connectionHealth = whatsappService.connectionHandler.getConnectionHealth();
        
        res.json({
            ...connectionStatus,
            health: connectionHealth,
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        logger.error('Status check error:', error);
        res.status(500).json({
            error: error.message,
            connected: false,
            timestamp: new Date().toISOString()
        });
    }
});


// Send message endpoint
router.post('/send', async (req, res) => {
    try {
        const { to, message, mentions } = req.body;
        
        // Validate required fields
        if (!to || !message) {
            return res.status(400).json({
                error: 'Missing required fields',
                required: ['to', 'message'],
                received: Object.keys(req.body),
                timestamp: new Date().toISOString()
            });
        }
        
        // Validate message length
        if (message.length > 4096) {
            return res.status(400).json({
                error: 'Message too long',
                max_length: 4096,
                received_length: message.length,
                timestamp: new Date().toISOString()
            });
        }
        
        const redisClient = req.app.locals.redisClient;
        
        if (!redisClient) {
            return res.status(503).json({
                error: 'Redis client not available',
                timestamp: new Date().toISOString()
            });
        }
        
        // Normalize phone number
        const normalizedTo = normalizePhoneNumber(to);
        
        // Create message data
        const messageData = {
            id: generateMessageId(),
            to: normalizedTo,
            text: message,
            mentions: mentions || [],
            timestamp: new Date().toISOString(),
            source: 'api'
        };
        
        // Publish to Redis outbound channel
        const channel = process.env.REDIS_CHANNEL_OUTBOUND || 'whatsapp:messages:outbound';
        
        await redisClient.publish(
            channel,
            JSON.stringify(messageData)
        );
        
        logger.info('Message queued for sending', {
            message_id: messageData.id,
            to_hash: Buffer.from(normalizedTo).toString('base64').substring(0, 8),
            channel
        });
        
        res.json({
            success: true,
            message: 'Message queued for sending',
            message_id: messageData.id,
            to: normalizedTo,
            timestamp: messageData.timestamp
        });
        
    } catch (error) {
        logger.error('Send message error:', error);
        res.status(500).json({
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// Get service metrics endpoint
router.get('/metrics', (req, res) => {
    try {
        const whatsappService = req.app.locals.whatsappService;
        
        if (!whatsappService) {
            return res.status(503).json({
                error: 'WhatsApp service not initialized',
                timestamp: new Date().toISOString()
            });
        }
        
        const metrics = whatsappService.getMetrics();
        const connectionStatus = whatsappService.getConnectionStatus();
        const queueStatus = whatsappService.outboundHandler.getQueueStatus();
        
        res.json({
            service_metrics: metrics,
            connection_status: connectionStatus,
            queue_status: queueStatus,
            system_metrics: {
                memory: process.memoryUsage(),
                uptime: process.uptime(),
                cpu_usage: process.cpuUsage()
            },
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        logger.error('Metrics error:', error);
        res.status(500).json({
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// Get recent logs endpoint (for debugging)
router.get('/logs', (req, res) => {
    try {
        const limit = parseInt(req.query.limit) || 100;
        const level = req.query.level || 'info';
        
        // In a real implementation, you would read from log files
        // For now, return a placeholder response
        res.json({
            message: 'Log endpoint not fully implemented',
            note: 'Check log files directly or implement log aggregation',
            log_file: process.env.LOG_FILE || './logs/whatsapp-service.log',
            requested_limit: limit,
            requested_level: level,
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        logger.error('Logs endpoint error:', error);
        res.status(500).json({
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// Session management endpoints
router.get('/session', (req, res) => {
    try {
        const whatsappService = req.app.locals.whatsappService;
        
        if (!whatsappService) {
            return res.status(503).json({
                error: 'WhatsApp service not initialized',
                timestamp: new Date().toISOString()
            });
        }
        
        const sessionInfo = whatsappService.getSessionInfo();
        
        res.json({
            session: sessionInfo,
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        logger.error('Session info error:', error);
        res.status(500).json({
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

router.post('/session/backup', async (req, res) => {
    try {
        const whatsappService = req.app.locals.whatsappService;
        
        if (!whatsappService) {
            return res.status(503).json({
                error: 'WhatsApp service not initialized',
                timestamp: new Date().toISOString()
            });
        }
        
        const { reason } = req.body;
        const result = await whatsappService.createSessionBackup(reason || 'api_request');
        
        if (result.success) {
            res.json({
                success: true,
                message: 'Session backup created successfully',
                backup: result,
                timestamp: new Date().toISOString()
            });
        } else {
            res.status(500).json({
                success: false,
                error: result.error,
                timestamp: new Date().toISOString()
            });
        }
        
    } catch (error) {
        logger.error('Session backup error:', error);
        res.status(500).json({
            success: false,
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

router.get('/session/backups', (req, res) => {
    try {
        const whatsappService = req.app.locals.whatsappService;
        
        if (!whatsappService) {
            return res.status(503).json({
                error: 'WhatsApp service not initialized',
                timestamp: new Date().toISOString()
            });
        }
        
        const backups = whatsappService.getAvailableBackups();
        
        res.json({
            backups,
            count: backups.length,
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        logger.error('Session backups list error:', error);
        res.status(500).json({
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

router.post('/session/restore', async (req, res) => {
    try {
        const whatsappService = req.app.locals.whatsappService;
        
        if (!whatsappService) {
            return res.status(503).json({
                error: 'WhatsApp service not initialized',
                timestamp: new Date().toISOString()
            });
        }
        
        const { backup_name } = req.body;
        
        if (!backup_name) {
            return res.status(400).json({
                error: 'Missing required field: backup_name',
                timestamp: new Date().toISOString()
            });
        }
        
        const result = await whatsappService.restoreSessionFromBackup(backup_name);
        
        if (result.success) {
            res.json({
                success: true,
                message: 'Session restored successfully. Service restart may be required.',
                restore_info: result,
                timestamp: new Date().toISOString()
            });
        } else {
            res.status(500).json({
                success: false,
                error: result.error,
                timestamp: new Date().toISOString()
            });
        }
        
    } catch (error) {
        logger.error('Session restore error:', error);
        res.status(500).json({
            success: false,
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// Error monitoring endpoints
router.get('/errors', (req, res) => {
    try {
        const whatsappService = req.app.locals.whatsappService;
        
        if (!whatsappService) {
            return res.status(503).json({
                error: 'WhatsApp service not initialized',
                timestamp: new Date().toISOString()
            });
        }
        
        const limit = parseInt(req.query.limit) || 10;
        const errorHandler = whatsappService.errorHandler;
        
        const stats = errorHandler.getErrorStats();
        const recentErrors = errorHandler.getRecentErrors(limit);
        
        res.json({
            stats,
            recent_errors: recentErrors,
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        logger.error('Error monitoring endpoint error:', error);
        res.status(500).json({
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

router.get('/retries', (req, res) => {
    try {
        const whatsappService = req.app.locals.whatsappService;
        
        if (!whatsappService) {
            return res.status(503).json({
                error: 'WhatsApp service not initialized',
                timestamp: new Date().toISOString()
            });
        }
        
        const retryManager = whatsappService.retryManager;
        const activeRetries = retryManager.getActiveRetries();
        const stats = retryManager.getStats();
        
        res.json({
            active_retries: activeRetries,
            stats,
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        logger.error('Retry monitoring endpoint error:', error);
        res.status(500).json({
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// Restart connection endpoint (for admin use)
router.post('/restart', async (req, res) => {
    try {
        const whatsappService = req.app.locals.whatsappService;
        
        if (!whatsappService) {
            return res.status(503).json({
                error: 'WhatsApp service not initialized',
                timestamp: new Date().toISOString()
            });
        }
        
        logger.info('Connection restart requested via API');
        
        // This would trigger a reconnection
        // Implementation depends on how you want to handle restarts
        res.json({
            message: 'Connection restart initiated',
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        logger.error('Restart endpoint error:', error);
        res.status(500).json({
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// Message logs endpoints
router.get('/messages/stats', (req, res) => {
    try {
        const stats = messageLogger.getStats();

        if (!stats) {
            return res.status(500).json({
                error: 'Error retrieving message stats',
                timestamp: new Date().toISOString()
            });
        }

        res.json({
            ...stats,
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        logger.error('Error getting message stats:', error);
        res.status(500).json({
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

router.get('/messages/logs', (req, res) => {
    try {
        const { date } = req.query;

        let targetDate;
        if (date) {
            targetDate = new Date(date);
            if (isNaN(targetDate.getTime())) {
                return res.status(400).json({
                    error: 'Invalid date format. Use YYYY-MM-DD',
                    timestamp: new Date().toISOString()
                });
            }
        } else {
            targetDate = new Date();
        }

        const logs = messageLogger.readMessagesForDate(targetDate);

        if (!logs) {
            return res.status(404).json({
                error: 'No logs found for the specified date',
                date: targetDate.toISOString().split('T')[0],
                timestamp: new Date().toISOString()
            });
        }

        res.type('text/plain').send(logs);

    } catch (error) {
        logger.error('Error reading message logs:', error);
        res.status(500).json({
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

router.post('/messages/flush', (req, res) => {
    try {
        messageLogger.flush();

        res.json({
            message: 'Message buffer flushed successfully',
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        logger.error('Error flushing message buffer:', error);
        res.status(500).json({
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// Helper functions
function normalizePhoneNumber(phoneNumber) {
    // If already in WhatsApp format, return as is
    if (phoneNumber.endsWith('@s.whatsapp.net') || phoneNumber.endsWith('@g.us')) {
        return phoneNumber;
    }
    
    // Remove any non-digit characters except +
    const cleaned = phoneNumber.replace(/[^\d+]/g, '');
    
    // Remove leading + if present
    const number = cleaned.startsWith('+') ? cleaned.substring(1) : cleaned;
    
    // Add WhatsApp suffix for individual chats
    return `${number}@s.whatsapp.net`;
}

function generateMessageId() {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substring(2, 8);
    return `msg_${timestamp}_${random}`;
}

// 404 handler for undefined routes
router.use('*', (req, res) => {
    res.status(404).json({
        error: 'Not found',
        path: req.originalUrl,
        method: req.method,
        timestamp: new Date().toISOString()
    });
});

// Error handling middleware for this router
router.use((error, req, res, next) => {
    logger.error('API route error:', error);

    res.status(500).json({
        error: 'Internal server error',
        message: process.env.NODE_ENV === 'development' ? error.message : 'Something went wrong',
        timestamp: new Date().toISOString()
    });
});

export default router;