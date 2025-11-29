import logger from './logger.js';

class Config {
    constructor() {
        this.loadConfiguration();
        this.validateConfiguration();
    }

    loadConfiguration() {
        this.config = {
            service: {
                port: parseInt(process.env.PORT) || 3001,
                name: process.env.SERVICE_NAME || 'whatsapp-service',
                environment: process.env.NODE_ENV || 'development',
                version: '1.0.0'
            },
            
            redis: {
                url: process.env.REDIS_URL || 'redis://localhost:6379',
                password: process.env.REDIS_PASSWORD || undefined,
                channels: {
                    inbound: process.env.REDIS_CHANNEL_INBOUND || 'whatsapp:messages:inbound',
                    outbound: process.env.REDIS_CHANNEL_OUTBOUND || 'whatsapp:messages:outbound',
                    notifications: process.env.REDIS_CHANNEL_NOTIFICATIONS || 'whatsapp:notifications',
                    status: process.env.REDIS_CHANNEL_STATUS || 'whatsapp:status'
                },
                reconnectAttempts: parseInt(process.env.REDIS_RECONNECT_ATTEMPTS) || 10,
                reconnectDelay: parseInt(process.env.REDIS_RECONNECT_DELAY) || 1000
            },
            
            whatsapp: {
                sessionName: process.env.WHATSAPP_SESSION_NAME || 'support-bot-session',
                sessionPath: './sessions',
                printQR: process.env.WHATSAPP_PRINT_QR === 'true',
                markOnline: process.env.WHATSAPP_MARK_ONLINE === 'true',
                phoneNumber: process.env.WHATSAPP_PHONE_NUMBER || null,
                queryTimeout: parseInt(process.env.WHATSAPP_QUERY_TIMEOUT) || 60000,
                keepAliveInterval: parseInt(process.env.WHATSAPP_KEEPALIVE_INTERVAL) || 10000,
                maxReconnectAttempts: parseInt(process.env.WHATSAPP_MAX_RECONNECT_ATTEMPTS) || 10,
                reconnectBaseDelay: parseInt(process.env.WHATSAPP_RECONNECT_BASE_DELAY) || 1000,
                reconnectMaxDelay: parseInt(process.env.WHATSAPP_RECONNECT_MAX_DELAY) || 30000
            },
            
            logging: {
                level: process.env.LOG_LEVEL || 'info',
                file: process.env.LOG_FILE || './logs/whatsapp-service.log',
                maxSize: process.env.LOG_MAX_SIZE || '10MB',
                maxFiles: parseInt(process.env.LOG_MAX_FILES) || 5,
                enableConsole: process.env.NODE_ENV !== 'production' || process.env.LOG_CONSOLE === 'true'
            },
            
            api: {
                rateLimit: parseInt(process.env.API_RATE_LIMIT) || 100,
                rateLimitWindow: parseInt(process.env.API_RATE_WINDOW) || 900000, // 15 minutes
                maxMessageLength: parseInt(process.env.API_MAX_MESSAGE_LENGTH) || 4096,
                enableCors: process.env.API_ENABLE_CORS !== 'false',
                requestTimeout: parseInt(process.env.API_REQUEST_TIMEOUT) || 30000
            },
            
            health: {
                checkInterval: parseInt(process.env.HEALTH_CHECK_INTERVAL) || 30000,
                maxErrorRate: parseFloat(process.env.HEALTH_MAX_ERROR_RATE) || 0.1,
                redisTimeout: parseInt(process.env.HEALTH_REDIS_TIMEOUT) || 5000
            },
            
            security: {
                enableAuth: process.env.SECURITY_ENABLE_AUTH === 'true',
                apiKey: process.env.SECURITY_API_KEY || null,
                allowedOrigins: process.env.SECURITY_ALLOWED_ORIGINS ? 
                    process.env.SECURITY_ALLOWED_ORIGINS.split(',') : ['*'],
                enableHttps: process.env.SECURITY_ENABLE_HTTPS === 'true'
            }
        };
    }

    validateConfiguration() {
        const errors = [];

        // Validate required fields
        if (!this.config.redis.url) {
            errors.push('REDIS_URL is required');
        }

        if (!this.config.whatsapp.sessionName) {
            errors.push('WHATSAPP_SESSION_NAME is required');
        }

        // Validate Redis URL format
        try {
            new URL(this.config.redis.url);
        } catch (error) {
            errors.push(`Invalid REDIS_URL format: ${this.config.redis.url}`);
        }

        // Validate port range
        if (this.config.service.port < 1 || this.config.service.port > 65535) {
            errors.push(`Invalid PORT: ${this.config.service.port} (must be 1-65535)`);
        }

        // Validate numeric values
        if (this.config.whatsapp.queryTimeout < 1000) {
            errors.push('WHATSAPP_QUERY_TIMEOUT must be at least 1000ms');
        }

        if (this.config.whatsapp.maxReconnectAttempts < 1) {
            errors.push('WHATSAPP_MAX_RECONNECT_ATTEMPTS must be at least 1');
        }

        // Validate log level
        const validLogLevels = ['error', 'warn', 'info', 'debug'];
        if (!validLogLevels.includes(this.config.logging.level)) {
            errors.push(`Invalid LOG_LEVEL: ${this.config.logging.level} (must be one of: ${validLogLevels.join(', ')})`);
        }

        // Validate API settings
        if (this.config.api.maxMessageLength < 1 || this.config.api.maxMessageLength > 65536) {
            errors.push('API_MAX_MESSAGE_LENGTH must be between 1 and 65536');
        }

        if (errors.length > 0) {
            throw new Error(`Configuration validation failed:\n${errors.join('\n')}`);
        }

        logger.info('Configuration validation passed', {
            service_name: this.config.service.name,
            environment: this.config.service.environment,
            redis_url: this.config.redis.url.replace(/\/\/.*@/, '//***@'), // Hide credentials
            session_name: this.config.whatsapp.sessionName
        });
    }

    get(path) {
        return path.split('.').reduce((obj, key) => obj?.[key], this.config);
    }

    getAll() {
        return { ...this.config };
    }

    // Helper methods for common configurations
    getRedisConfig() {
        return {
            url: this.config.redis.url,
            password: this.config.redis.password,
            socket: {
                reconnectStrategy: (retries) => {
                    if (retries > this.config.redis.reconnectAttempts) {
                        return false;
                    }
                    return Math.min(retries * this.config.redis.reconnectDelay, 30000);
                }
            }
        };
    }

    getWhatsAppConfig() {
        return {
            sessionName: this.config.whatsapp.sessionName,
            sessionPath: this.config.whatsapp.sessionPath,
            printQR: this.config.whatsapp.printQR,
            markOnline: this.config.whatsapp.markOnline,
            queryTimeout: this.config.whatsapp.queryTimeout,
            keepAliveInterval: this.config.whatsapp.keepAliveInterval
        };
    }

    getApiConfig() {
        return {
            port: this.config.service.port,
            rateLimit: this.config.api.rateLimit,
            rateLimitWindow: this.config.api.rateLimitWindow,
            maxMessageLength: this.config.api.maxMessageLength,
            enableCors: this.config.api.enableCors,
            requestTimeout: this.config.api.requestTimeout
        };
    }

    // Environment-specific configurations
    isDevelopment() {
        return this.config.service.environment === 'development';
    }

    isProduction() {
        return this.config.service.environment === 'production';
    }

    isTest() {
        return this.config.service.environment === 'test';
    }

    // Update configuration at runtime (for specific cases)
    updateConfig(path, value) {
        const keys = path.split('.');
        let obj = this.config;
        
        for (let i = 0; i < keys.length - 1; i++) {
            if (!obj[keys[i]]) {
                obj[keys[i]] = {};
            }
            obj = obj[keys[i]];
        }
        
        obj[keys[keys.length - 1]] = value;
        
        logger.info(`Configuration updated: ${path} = ${value}`);
    }

    // Get configuration summary for logging/debugging
    getSummary() {
        return {
            service: {
                name: this.config.service.name,
                version: this.config.service.version,
                environment: this.config.service.environment,
                port: this.config.service.port
            },
            redis: {
                url: this.config.redis.url.replace(/\/\/.*@/, '//***@'),
                channels: this.config.redis.channels
            },
            whatsapp: {
                sessionName: this.config.whatsapp.sessionName,
                printQR: this.config.whatsapp.printQR,
                markOnline: this.config.whatsapp.markOnline
            },
            logging: {
                level: this.config.logging.level,
                file: this.config.logging.file
            }
        };
    }
}

// Export singleton instance
export default new Config();