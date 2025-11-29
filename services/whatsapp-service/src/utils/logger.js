import winston from 'winston';
import path from 'path';

// Create logs directory if it doesn't exist
import fs from 'fs';
const logsDir = './logs';
if (!fs.existsSync(logsDir)) {
    fs.mkdirSync(logsDir, { recursive: true });
}

// Custom format for structured logging
const logFormat = winston.format.combine(
    winston.format.timestamp({
        format: 'YYYY-MM-DD HH:mm:ss'
    }),
    winston.format.errors({ stack: true }),
    winston.format.json(),
    winston.format.printf(({ timestamp, level, message, service = 'whatsapp-service', ...meta }) => {
        const logEntry = {
            timestamp,
            level,
            service,
            message,
            ...meta
        };
        try {
            return JSON.stringify(logEntry);
        } catch (error) {
            // Handle circular references by creating a safe copy
            const safeLogEntry = {
                timestamp: logEntry.timestamp,
                level: logEntry.level,
                service: logEntry.service,
                message: logEntry.message,
                meta: '[Circular Reference Detected]'
            };
            return JSON.stringify(safeLogEntry);
        }
    })
);

// Console format for development
const consoleFormat = winston.format.combine(
    winston.format.colorize(),
    winston.format.timestamp({
        format: 'HH:mm:ss'
    }),
    winston.format.printf(({ timestamp, level, message, ...meta }) => {
        const metaStr = Object.keys(meta).length ? JSON.stringify(meta, null, 2) : '';
        return `${timestamp} [${level}]: ${message} ${metaStr}`;
    })
);

// Create logger instance
const logger = winston.createLogger({
    level: process.env.LOG_LEVEL || 'info',
    format: logFormat,
    defaultMeta: {
        service: process.env.SERVICE_NAME || 'whatsapp-service'
    },
    transports: [
        // File transport for all logs
        new winston.transports.File({
            filename: process.env.LOG_FILE || './logs/whatsapp-service.log',
            maxsize: 10 * 1024 * 1024, // 10MB
            maxFiles: 5,
            tailable: true
        }),
        
        // Separate file for errors
        new winston.transports.File({
            filename: './logs/error.log',
            level: 'error',
            maxsize: 10 * 1024 * 1024, // 10MB
            maxFiles: 3,
            tailable: true
        })
    ],
    
    // Handle uncaught exceptions
    exceptionHandlers: [
        new winston.transports.File({
            filename: './logs/exceptions.log'
        })
    ],
    
    // Handle unhandled promise rejections
    rejectionHandlers: [
        new winston.transports.File({
            filename: './logs/rejections.log'
        })
    ]
});

// Add console transport for development
if (process.env.NODE_ENV !== 'production') {
    logger.add(new winston.transports.Console({
        format: consoleFormat
    }));
}

// Add console transport for production with JSON format
if (process.env.NODE_ENV === 'production') {
    logger.add(new winston.transports.Console({
        format: logFormat
    }));
}

// Helper methods for structured logging
logger.logMessageReceived = (messageId, fromUser, textLength, hasMedia = false) => {
    logger.info('Message received', {
        event: 'message_received',
        message_id: messageId,
        from_user_hash: fromUser ? Buffer.from(fromUser).toString('base64').substring(0, 8) : null,
        text_length: textLength,
        has_media: hasMedia
    });
};

logger.logMessageSent = (messageId, toUser, success = true) => {
    logger.info('Message sent', {
        event: 'message_sent',
        message_id: messageId,
        to_user_hash: toUser ? Buffer.from(toUser).toString('base64').substring(0, 8) : null,
        success
    });
};

logger.logConnectionEvent = (event, details = {}) => {
    logger.info(`Connection ${event}`, {
        event: `connection_${event}`,
        ...details
    });
};

logger.logRedisEvent = (event, channel = null, error = null) => {
    const logLevel = error ? 'error' : 'info';
    logger[logLevel](`Redis ${event}`, {
        event: `redis_${event}`,
        channel,
        error: error ? error.message : null
    });
};

logger.logAPIRequest = (method, path, statusCode, responseTime, userAgent = null) => {
    logger.info('API request', {
        event: 'api_request',
        method,
        path,
        status_code: statusCode,
        response_time_ms: responseTime,
        user_agent: userAgent
    });
};

export default logger;