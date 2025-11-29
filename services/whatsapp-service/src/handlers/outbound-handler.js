import logger from '../utils/logger.js';
import config from '../utils/config.js';
import messageLogger from '../utils/message-logger.js';
import crypto from 'crypto';

class OutboundHandler {
    constructor() {
        this.socket = null;
        this.redisClient = null;
        this.metrics = null;
        this.subscriber = null;
        this.isListening = false;
        this.messageQueue = [];
        this.processingQueue = false;
        this.retryQueue = [];
        this.scheduledMessages = new Map();
        this.messageTemplates = new Map();
        this.rateLimiter = new Map();
        this.sendingStats = {
            total_sent: 0,
            total_failed: 0,
            total_retries: 0,
            last_sent: null
        };
        
        // Configuration
        this.maxQueueSize = 10000;
        this.maxRetries = 3;
        this.baseRetryDelay = 1000;
        this.maxRetryDelay = 30000;
        this.rateLimitWindow = 60000; // 1 minute
        this.rateLimitMax = 20; // Max 20 messages per minute per recipient
        
        // Initialize message templates
        this.initializeTemplates();
        
        // Start retry processor
        this.startRetryProcessor();
    }

    initialize(socket, redisClient, metrics) {
        this.socket = socket;
        this.redisClient = redisClient;
        this.metrics = metrics;
        
        logger.info('OutboundHandler initialized', {
            max_queue_size: this.maxQueueSize,
            max_retries: this.maxRetries,
            rate_limit: `${this.rateLimitMax} messages per ${this.rateLimitWindow}ms`,
            templates: this.messageTemplates.size
        });
    }

    initializeTemplates() {
        // Register common message templates
        this.registerTemplate('welcome', {
            text: 'Welcome to our service! How can we help you today?',
            type: 'greeting'
        });
        
        this.registerTemplate('error', {
            text: 'Sorry, there was an error processing your request. Please try again later.',
            type: 'error'
        });
        
        this.registerTemplate('confirmation', {
            text: 'Your request has been received and is being processed.',
            type: 'confirmation'
        });
        
        logger.debug('Message templates initialized', {
            template_count: this.messageTemplates.size
        });
    }

    registerTemplate(name, template) {
        this.messageTemplates.set(name, {
            ...template,
            created_at: new Date().toISOString(),
            usage_count: 0
        });
    }

    startRetryProcessor() {
        // Process retry queue every 5 seconds
        setInterval(() => {
            this.processRetryQueue();
        }, 5000);
    }

    async listenForOutboundMessages() {
        try {
            if (this.isListening) {
                logger.warn('Already listening for outbound messages');
                return;
            }

            if (!this.redisClient) {
                logger.warn('Redis client not initialized, skipping outbound message listener setup');
                return;
            }

            // Close existing subscriber if it exists
            if (this.subscriber) {
                logger.info('Closing existing subscriber before creating new one');
                try {
                    await this.subscriber.quit();
                } catch (error) {
                    logger.warn('Error closing existing subscriber:', error);
                }
                this.subscriber = null;
            }

            // Create a separate Redis client for subscription
            this.subscriber = this.redisClient.duplicate();
            await this.subscriber.connect();

            const channel = config.get('redis.channels.outbound');

            await this.subscriber.subscribe(channel, (message) => {
                this.handleOutboundMessage(message);
            });

            this.isListening = true;

            // Start message queue processor
            this.startMessageProcessor();

            logger.info(`Listening for outbound messages on channel: ${channel}`, {
                channel,
                queue_processor: 'started'
            });

        } catch (error) {
            logger.error('Error setting up outbound message listener:', error);
            if (this.metrics) {
                this.metrics.incrementErrors();
            }
            throw error;
        }
    }

    async startMessageProcessor() {
        if (this.processingQueue) return;
        
        this.processingQueue = true;
        
        while (this.processingQueue) {
            try {
                if (this.messageQueue.length > 0) {
                    const messageData = this.messageQueue.shift();
                    await this.processMessage(messageData);
                } else {
                    // Wait before checking queue again
                    await this.delay(100);
                }
            } catch (error) {
                logger.error('Error in message processor:', error);
                if (this.metrics) {
                    this.metrics.incrementErrors();
                }
            }
        }
    }

    async handleOutboundMessage(message) {
        try {
            const messageData = JSON.parse(message);
            
            // Add processing metadata
            messageData.received_at = new Date().toISOString();
            messageData.id = messageData.id || this.generateMessageId();
            
            logger.info('Received outbound message', {
                message_id: messageData.id,
                to_hash: messageData.to ? this.hashRecipient(messageData.to) : 'unknown',
                message_type: messageData.type || 'text',
                priority: messageData.priority || 'normal',
                scheduled: !!messageData.schedule_at
            });

            // Validate message data
            this.validateOutboundMessage(messageData);

            // Check rate limiting
            if (!this.checkRateLimit(messageData.to)) {
                logger.warn('Rate limit exceeded for recipient', {
                    message_id: messageData.id,
                    to_hash: this.hashRecipient(messageData.to)
                });
                
                await this.publishSendResult(messageData, null, false, 'Rate limit exceeded');
                return;
            }

            // Handle scheduled messages
            if (messageData.schedule_at) {
                this.scheduleMessage(messageData);
                return;
            }

            // Add to appropriate queue based on priority
            this.addToQueue(messageData);
            
        } catch (error) {
            logger.error('Error handling outbound message:', error);
            if (this.metrics) {
                this.metrics.incrementErrors();
            }
            
            // Try to publish error result if we have message data
            try {
                const messageData = JSON.parse(message);
                await this.publishSendResult(messageData, null, false, error.message);
            } catch (publishError) {
                logger.error('Error publishing error result:', publishError);
            }
        }
    }

    addToQueue(messageData) {
        // Check queue size limit
        if (this.messageQueue.length >= this.maxQueueSize) {
            logger.warn('Message queue full, dropping oldest message', {
                queue_size: this.messageQueue.length,
                max_size: this.maxQueueSize
            });
            
            const dropped = this.messageQueue.shift();
            this.publishSendResult(dropped, null, false, 'Queue overflow').catch(() => {});
        }

        // Add to queue based on priority
        if (messageData.priority === 'high') {
            this.messageQueue.unshift(messageData);
        } else {
            this.messageQueue.push(messageData);
        }

        logger.debug('Message added to queue', {
            message_id: messageData.id,
            priority: messageData.priority || 'normal',
            queue_size: this.messageQueue.length
        });
    }

    checkRateLimit(recipient) {
        const now = Date.now();
        const recipientKey = this.hashRecipient(recipient);
        
        if (!this.rateLimiter.has(recipientKey)) {
            this.rateLimiter.set(recipientKey, []);
        }
        
        const timestamps = this.rateLimiter.get(recipientKey);
        
        // Remove old timestamps outside the window
        const recentTimestamps = timestamps.filter(ts => now - ts < this.rateLimitWindow);
        
        if (recentTimestamps.length >= this.rateLimitMax) {
            return false; // Rate limit exceeded
        }
        
        recentTimestamps.push(now);
        this.rateLimiter.set(recipientKey, recentTimestamps);
        
        return true;
    }

    scheduleMessage(messageData) {
        const scheduleTime = new Date(messageData.schedule_at).getTime();
        const now = Date.now();
        
        if (scheduleTime <= now) {
            // Schedule time is in the past, send immediately
            this.addToQueue(messageData);
            return;
        }
        
        const delay = scheduleTime - now;
        
        logger.info('Message scheduled for future delivery', {
            message_id: messageData.id,
            schedule_at: messageData.schedule_at,
            delay_ms: delay
        });
        
        const timeoutId = setTimeout(() => {
            this.scheduledMessages.delete(messageData.id);
            this.addToQueue(messageData);
        }, delay);
        
        this.scheduledMessages.set(messageData.id, {
            timeoutId,
            messageData,
            scheduledAt: new Date().toISOString()
        });
    }

    async processMessage(messageData) {
        try {
            // Apply message template if specified
            if (messageData.template) {
                messageData = this.applyTemplate(messageData);
            }
            
            // Normalize recipient
            messageData.to = this.normalizePhoneNumber(messageData.to);
            
            // Send the message
            await this.sendMessage(messageData);
            
            // Small delay between messages to avoid rate limiting
            await this.delay(100);
            
        } catch (error) {
            logger.error('Error processing message:', error);
            
            // Handle retry logic
            if (this.shouldRetry(error, messageData)) {
                this.addToRetryQueue(messageData, error);
            } else {
                await this.publishSendResult(messageData, null, false, error.message);
            }
        }
    }

    applyTemplate(messageData) {
        const template = this.messageTemplates.get(messageData.template);
        
        if (!template) {
            logger.warn('Template not found', {
                template: messageData.template,
                message_id: messageData.id
            });
            return messageData;
        }
        
        // Update usage count
        template.usage_count++;
        
        // Apply template with variable substitution
        let text = template.text;
        
        if (messageData.variables) {
            for (const [key, value] of Object.entries(messageData.variables)) {
                text = text.replace(new RegExp(`{{${key}}}`, 'g'), value);
            }
        }
        
        return {
            ...messageData,
            text,
            template_applied: messageData.template,
            original_text: messageData.text
        };
    }

    async processRetryQueue() {
        const now = Date.now();
        const readyToRetry = [];
        
        // Find messages ready for retry
        this.retryQueue = this.retryQueue.filter(item => {
            if (now >= item.retryAt) {
                readyToRetry.push(item.messageData);
                return false; // Remove from retry queue
            }
            return true; // Keep in retry queue
        });
        
        // Add ready messages back to main queue
        for (const messageData of readyToRetry) {
            logger.info('Retrying message', {
                message_id: messageData.id,
                retry_count: messageData.retryCount,
                to_hash: this.hashRecipient(messageData.to)
            });
            
            this.addToQueue(messageData);
        }
    }

    async sendMessage(messageData) {
        const startTime = Date.now();
        
        try {
            if (!this.socket || !this.socket.user) {
                throw new Error('WhatsApp not connected');
            }

            const { to, text, mentions = [], media, options = {} } = messageData;

            // Prepare message content based on type
            let messageContent;
            
            if (media) {
                messageContent = await this.prepareMediaMessage(messageData);
            } else {
                messageContent = this.prepareTextMessage(messageData);
            }

            // Send message through Baileys
            const result = await this.socket.sendMessage(to, messageContent);
            
            const duration = Date.now() - startTime;
            
            // Update statistics
            this.sendingStats.total_sent++;
            this.sendingStats.last_sent = new Date().toISOString();
            
            // Log successful send
            logger.logMessageSent(result.key.id, to, true);

            // Log outbound message to file
            try {
                messageLogger.logOutbound({
                    messageId: result.key.id,
                    to: to,
                    messageType: messageData.type || 'text',
                    text: text,
                    priority: messageData.priority || 'normal',
                    media: media,
                    status: 'sent'
                });
            } catch (error) {
                logger.error('Error logging outbound message to file:', error);
            }

            logger.info('Message sent successfully', {
                message_id: messageData.id,
                sent_message_id: result.key.id,
                to_hash: this.hashRecipient(to),
                message_type: messageData.type || 'text',
                duration_ms: duration,
                retry_count: messageData.retryCount || 0
            });

            if (this.metrics) {
                this.metrics.incrementSent();
                this.metrics.updateLastActivity();
            }

            // Publish success notification
            await this.publishSendResult(messageData, result, true);

            return result;
            
        } catch (error) {
            const duration = Date.now() - startTime;

            this.sendingStats.total_failed++;

            // Log failed outbound message to file
            try {
                messageLogger.logOutbound({
                    messageId: messageData.id || 'unknown',
                    to: messageData.to,
                    messageType: messageData.type || 'text',
                    text: messageData.text || messageData.message,
                    priority: messageData.priority || 'normal',
                    media: messageData.media,
                    status: 'failed',
                    error: error.message
                });
            } catch (logError) {
                logger.error('Error logging failed outbound message to file:', logError);
            }

            logger.error('Error sending message:', {
                message_id: messageData.id,
                to_hash: this.hashRecipient(messageData.to),
                error: error.message,
                duration_ms: duration,
                retry_count: messageData.retryCount || 0
            });

            if (this.metrics) {
                this.metrics.incrementErrors();
            }

            // Log failed send
            logger.logMessageSent(messageData.id || 'unknown', messageData.to, false);

            throw error;
        }
    }

    prepareTextMessage(messageData) {
        const { text, mentions = [], options = {} } = messageData;
        
        const messageContent = { text };

        // Add mentions if provided
        if (mentions && mentions.length > 0) {
            messageContent.mentions = mentions;
        }

        // Add quoted message if specified
        if (options.quotedMessageId) {
            messageContent.quoted = {
                key: { id: options.quotedMessageId }
            };
        }

        return messageContent;
    }

    async prepareMediaMessage(messageData) {
        const { media, text, mentions = [] } = messageData;
        
        // This would be expanded to handle different media types
        // For now, basic implementation
        const messageContent = {
            caption: text || '',
            mentions: mentions
        };

        // Handle different media types
        switch (media.type) {
            case 'image':
                messageContent.image = media.data;
                break;
            case 'video':
                messageContent.video = media.data;
                break;
            case 'audio':
                messageContent.audio = media.data;
                messageContent.ptt = media.isVoiceNote || false;
                break;
            case 'document':
                messageContent.document = media.data;
                messageContent.fileName = media.filename;
                break;
            default:
                throw new Error(`Unsupported media type: ${media.type}`);
        }

        return messageContent;
    }

    addToRetryQueue(messageData, error) {
        const retryCount = (messageData.retryCount || 0) + 1;
        const retryDelay = Math.min(
            this.baseRetryDelay * Math.pow(2, retryCount - 1),
            this.maxRetryDelay
        );
        
        const retryAt = Date.now() + retryDelay;
        
        this.sendingStats.total_retries++;
        
        logger.info('Adding message to retry queue', {
            message_id: messageData.id,
            retry_count: retryCount,
            retry_delay_ms: retryDelay,
            retry_at: new Date(retryAt).toISOString(),
            error: error.message
        });
        
        this.retryQueue.push({
            messageData: {
                ...messageData,
                retryCount,
                lastError: error.message,
                retryHistory: [
                    ...(messageData.retryHistory || []),
                    {
                        attempt: retryCount,
                        error: error.message,
                        timestamp: new Date().toISOString()
                    }
                ]
            },
            retryAt
        });
    }

    validateOutboundMessage(messageData) {
        // Required fields
        if (!messageData.to) {
            throw new Error('Missing required field: to');
        }

        if (!messageData.text && !messageData.media) {
            throw new Error('Missing required field: text or media');
        }

        // Validate phone number format
        if (!this.isValidPhoneNumber(messageData.to)) {
            throw new Error(`Invalid phone number format: ${messageData.to}`);
        }

        // Validate text length
        if (messageData.text && messageData.text.length > 4096) {
            throw new Error('Message text too long (max 4096 characters)');
        }

        // Validate mentions format
        if (messageData.mentions && !Array.isArray(messageData.mentions)) {
            throw new Error('Mentions must be an array');
        }

        return true;
    }

    isValidPhoneNumber(phoneNumber) {
        // Check if it's already in WhatsApp format
        if (phoneNumber.endsWith('@s.whatsapp.net') || phoneNumber.endsWith('@g.us')) {
            return true;
        }

        // Check if it's a valid phone number (basic validation)
        const phoneRegex = /^\+?[1-9]\d{1,14}$/;
        return phoneRegex.test(phoneNumber);
    }

    normalizePhoneNumber(phoneNumber) {
        // If already in WhatsApp format, return as is
        if (phoneNumber.endsWith('@s.whatsapp.net') || phoneNumber.endsWith('@g.us')) {
            return phoneNumber;
        }

        // Remove any non-digit characters except +
        const cleaned = phoneNumber.replace(/[^\d+]/g, '');
        
        // Remove leading + if present
        const number = cleaned.startsWith('+') ? cleaned.substring(1) : cleaned;
        
        // Add WhatsApp suffix
        return `${number}@s.whatsapp.net`;
    }

    shouldRetry(error, messageData) {
        const currentRetries = messageData.retryCount || 0;
        
        if (currentRetries >= this.maxRetries) {
            logger.warn(`Max retries reached for message to ${messageData.to}`, {
                message_id: messageData.id,
                retry_count: currentRetries,
                max_retries: this.maxRetries
            });
            return false;
        }

        // Don't retry for certain error types
        const nonRetryableErrors = [
            'invalid phone number',
            'blocked',
            'not found',
            'forbidden',
            'rate limit exceeded',
            'queue overflow'
        ];

        const errorMessage = error.message.toLowerCase();
        for (const nonRetryable of nonRetryableErrors) {
            if (errorMessage.includes(nonRetryable)) {
                logger.warn(`Non-retryable error for message to ${messageData.to}: ${error.message}`, {
                    message_id: messageData.id,
                    error_type: nonRetryable
                });
                return false;
            }
        }

        return true;
    }

    // Utility methods
    generateMessageId() {
        return `out_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
    }

    hashRecipient(recipient) {
        return crypto.createHash('sha256').update(recipient).digest('hex').substring(0, 8);
    }

    async scheduleRetry(messageData) {
        const retryCount = (messageData.retryCount || 0) + 1;
        const retryDelay = Math.min(1000 * Math.pow(2, retryCount), 30000); // Exponential backoff, max 30s

        logger.info(`Scheduling retry ${retryCount} for message to ${messageData.to} in ${retryDelay}ms`);

        setTimeout(() => {
            const retryMessage = {
                ...messageData,
                retryCount: retryCount,
                originalTimestamp: messageData.originalTimestamp || new Date().toISOString(),
                retryTimestamp: new Date().toISOString()
            };

            this.messageQueue.push(retryMessage);
            
            if (!this.processingQueue) {
                this.processMessageQueue();
            }
        }, retryDelay);
    }

    async publishSendResult(originalMessage, result, success, errorMessage = null) {
        try {
            const resultData = {
                original_message_id: originalMessage.id,
                to_hash: this.hashRecipient(originalMessage.to),
                success: success,
                timestamp: new Date().toISOString(),
                sent_message_id: result ? result.key.id : null,
                error_message: errorMessage,
                retry_count: originalMessage.retryCount || 0,
                template_used: originalMessage.template_applied || null,
                message_type: originalMessage.type || 'text',
                processing_time_ms: originalMessage.received_at 
                    ? Date.now() - new Date(originalMessage.received_at).getTime() 
                    : null
            };

            const channel = config.get('redis.channels.notifications');
            
            await this.redisClient.publish(
                channel,
                JSON.stringify({
                    event: 'message_send_result',
                    service: 'outbound-handler',
                    data: resultData
                })
            );

        } catch (error) {
            logger.error('Error publishing send result:', error);
        }
    }

    async delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    getQueueStatus() {
        return {
            main_queue: {
                length: this.messageQueue.length,
                max_size: this.maxQueueSize
            },
            retry_queue: {
                length: this.retryQueue.length
            },
            scheduled_messages: {
                count: this.scheduledMessages.size
            },
            processing: this.processingQueue,
            listening: this.isListening,
            rate_limiter: {
                active_recipients: this.rateLimiter.size
            }
        };
    }

    getHandlerStats() {
        return {
            sending_stats: this.sendingStats,
            queue_status: this.getQueueStatus(),
            templates: {
                total: this.messageTemplates.size,
                usage: Array.from(this.messageTemplates.entries()).map(([name, template]) => ({
                    name,
                    usage_count: template.usage_count,
                    type: template.type
                }))
            },
            configuration: {
                max_retries: this.maxRetries,
                rate_limit_max: this.rateLimitMax,
                rate_limit_window_ms: this.rateLimitWindow
            }
        };
    }

    async getHealthStatus() {
        const queueHealth = this.messageQueue.length < this.maxQueueSize * 0.9; // Healthy if queue < 90% full
        const retryHealth = this.retryQueue.length < 100; // Healthy if retry queue < 100
        
        return {
            healthy: queueHealth && retryHealth && this.isListening,
            details: {
                queue_healthy: queueHealth,
                retry_queue_healthy: retryHealth,
                listening: this.isListening,
                queue_usage_percent: (this.messageQueue.length / this.maxQueueSize) * 100,
                retry_queue_size: this.retryQueue.length
            },
            stats: this.sendingStats
        };
    }

    // Message management methods
    cancelScheduledMessage(messageId) {
        const scheduled = this.scheduledMessages.get(messageId);
        if (scheduled) {
            clearTimeout(scheduled.timeoutId);
            this.scheduledMessages.delete(messageId);
            
            logger.info('Scheduled message cancelled', {
                message_id: messageId
            });
            
            return true;
        }
        return false;
    }

    clearQueue() {
        const clearedCount = this.messageQueue.length;
        this.messageQueue = [];
        
        logger.info('Message queue cleared', {
            cleared_messages: clearedCount
        });
        
        return clearedCount;
    }

    clearRetryQueue() {
        const clearedCount = this.retryQueue.length;
        this.retryQueue = [];
        
        logger.info('Retry queue cleared', {
            cleared_messages: clearedCount
        });
        
        return clearedCount;
    }

    async shutdown() {
        try {
            logger.info('Shutting down OutboundHandler...', {
                main_queue_size: this.messageQueue.length,
                retry_queue_size: this.retryQueue.length,
                scheduled_messages: this.scheduledMessages.size
            });

            this.isListening = false;
            this.processingQueue = false;

            // Cancel all scheduled messages
            for (const [messageId, scheduled] of this.scheduledMessages.entries()) {
                clearTimeout(scheduled.timeoutId);
                logger.debug('Cancelled scheduled message during shutdown', {
                    message_id: messageId
                });
            }
            this.scheduledMessages.clear();

            // Close Redis subscriber
            if (this.subscriber) {
                await this.subscriber.quit();
                this.subscriber = null;
            }
            
            // Process remaining messages in main queue
            const remainingMessages = this.messageQueue.length;
            if (remainingMessages > 0) {
                logger.info(`Processing ${remainingMessages} remaining messages...`);
                
                while (this.messageQueue.length > 0) {
                    const messageData = this.messageQueue.shift();
                    try {
                        await this.processMessage(messageData);
                    } catch (error) {
                        logger.error('Error processing message during shutdown:', error);
                        await this.publishSendResult(messageData, null, false, 'Service shutdown');
                    }
                }
            }
            
            // Clear all queues and caches
            this.retryQueue = [];
            this.rateLimiter.clear();
            
            logger.info('OutboundHandler shutdown completed', {
                final_stats: this.sendingStats,
                processed_during_shutdown: remainingMessages
            });
            
        } catch (error) {
            logger.error('Error during OutboundHandler shutdown:', error);
        }
    }
}

export default OutboundHandler;