import logger from '../utils/logger.js';
import { downloadMediaMessage } from '@whiskeysockets/baileys';
import config from '../utils/config.js';
import RedisPublisher from '../utils/redis-publisher.js';
import messageLogger from '../utils/message-logger.js';
import crypto from 'crypto';
import { promises as fs } from 'fs';
import path from 'path';

class MessageHandler {
    constructor() {
        this.redisClient = null;
        this.metrics = null;
        this.redisPublisher = new RedisPublisher();
        this.messageQueue = [];
        this.processingQueue = false;
        this.messageFilters = [];
        this.messageProcessors = new Map();
        this.duplicateMessageCache = new Map();
        this.rateLimitCache = new Map();
        this.socket = null;
        this.mediaBasePath = "./media";

        
        // Initialize default processors
        this.initializeDefaultProcessors();
        
        // Cleanup cache periodically
        setInterval(() => this.cleanupCaches(), 300000); // 5 minutes
    }

    initialize(redisClient, metrics, socket = null) {
        this.socket = socket;
        this.redisClient = redisClient;
        this.metrics = metrics;
        
        // Initialize Redis publisher
        this.redisPublisher.initialize(redisClient);
        
        // Initialize message processing queue
        this.startMessageProcessor();
        
        logger.info('MessageHandler initialized', {
            processors: this.messageProcessors.size,
            filters: this.messageFilters.length,
            redis_publisher: 'initialized'
        });
    }

    initializeDefaultProcessors() {
        // Register default message processors
        this.registerProcessor('text', this.processTextMessage.bind(this));
        this.registerProcessor('image', this.processImageMessage.bind(this));
        this.registerProcessor('video', this.processVideoMessage.bind(this));
        this.registerProcessor('audio', this.processAudioMessage.bind(this));
        this.registerProcessor('document', this.processDocumentMessage.bind(this));
        this.registerProcessor('sticker', this.processStickerMessage.bind(this));
        this.registerProcessor('location', this.processLocationMessage.bind(this));
        this.registerProcessor('contact', this.processContactMessage.bind(this));
        
        // Register default filters
        this.addFilter('duplicate', this.filterDuplicateMessages.bind(this));
        this.addFilter('rate_limit', this.filterRateLimit.bind(this));
        this.addFilter('spam', this.filterSpamMessages.bind(this));
    }

    registerProcessor(messageType, processor) {
        this.messageProcessors.set(messageType, processor);
        logger.debug(`Registered processor for message type: ${messageType}`);
    }

    addFilter(name, filter) {
        this.messageFilters.push({ name, filter });
        logger.debug(`Added message filter: ${name}`);
    }

    async startMessageProcessor() {
        if (this.processingQueue) return;
        
        this.processingQueue = true;
        
        while (this.processingQueue) {
            if (this.messageQueue.length > 0) {
                const message = this.messageQueue.shift();
                try {
                    await this.processQueuedMessage(message);
                } catch (error) {
                    logger.error('Error processing queued message:', error);
                    if (this.metrics) {
                        this.metrics.incrementErrors();
                    }
                }
            } else {
                // Wait a bit before checking again
                await new Promise(resolve => setTimeout(resolve, 100));
            }
        }
    }

    async processQueuedMessage(message) {
        const messageData = this.extractMessageData(message);

        // Apply filters
        const shouldProcess = await this.applyFilters(messageData, message);
        if (!shouldProcess) {
            logger.debug(`Message filtered out: ${messageData.id}`);
            return;
        }

        // Log inbound message to file
        try {
            messageLogger.logInbound({
                messageId: messageData.id,
                from: messageData.from_user,
                messageType: messageData.message_type,
                text: messageData.text || '',
                hasMedia: messageData.has_media || false,
                mediaType: messageData.media_type,
                caption: messageData.caption,
                quotedMessage: messageData.quoted_message ? true : false
            });
        } catch (error) {
            logger.error('Error logging inbound message to file:', error);
        }

        // Process with specific processor
        const processor = this.messageProcessors.get(messageData.message_type);
        if (processor) {
            await processor(messageData, message);
        }

        // Publish to Redis
        await this.publishMessage(messageData);

        // Update metrics
        if (this.metrics) {
            this.metrics.incrementReceived();
            this.metrics.updateLastActivity();
        }
    }

    async handleMessage(message) {
        try {
            // Add to processing queue for async handling
            this.messageQueue.push(message);
            
            // Log message received immediately
            const basicData = {
                id: message.key.id,
                from_user: message.key.remoteJid,
                timestamp: new Date(message.messageTimestamp * 1000).toISOString()
            };
            

            
            logger.logMessageReceived(
                basicData.id,
                basicData.from_user,
                message.message?.conversation?.length || 0,
                this.hasMedia(message)
            );
            
        } catch (error) {
            logger.error('Error handling message:', error);
            if (this.metrics) {
                this.metrics.incrementErrors();
            }
            throw error;
        }
    }

    async applyFilters(messageData, originalMessage) {
        for (const { name, filter } of this.messageFilters) {
            try {
                const shouldContinue = await filter(messageData, originalMessage);
                if (!shouldContinue) {
                    logger.debug(`Message blocked by filter: ${name}`, {
                        message_id: messageData.id,
                        filter: name
                    });
                    return false;
                }
            } catch (error) {
                logger.error(`Error in filter ${name}:`, error);
                // Continue processing if filter fails
            }
        }
        return true;
    }

    // Filter implementations
    async filterDuplicateMessages(messageData) {
        const messageHash = this.generateMessageHash(messageData);
        const now = Date.now();
        
        if (this.duplicateMessageCache.has(messageHash)) {
            const lastSeen = this.duplicateMessageCache.get(messageHash);
            if (now - lastSeen < 5000) { // 5 seconds window
                return false; // Duplicate message
            }
        }
        
        this.duplicateMessageCache.set(messageHash, now);
        return true;
    }

    async filterRateLimit(messageData) {
        const userId = messageData.from_user;
        const now = Date.now();
        const windowMs = 60000; // 1 minute
        const maxMessages = 30; // Max 30 messages per minute per user
        
        if (!this.rateLimitCache.has(userId)) {
            this.rateLimitCache.set(userId, []);
        }
        
        const userMessages = this.rateLimitCache.get(userId);
        
        // Remove old messages outside the window
        const recentMessages = userMessages.filter(timestamp => now - timestamp < windowMs);
        
        if (recentMessages.length >= maxMessages) {
            logger.warn(`Rate limit exceeded for user: ${userId}`, {
                message_count: recentMessages.length,
                window_ms: windowMs
            });
            return false;
        }
        
        recentMessages.push(now);
        this.rateLimitCache.set(userId, recentMessages);
        return true;
    }

    async filterSpamMessages(messageData) {
        // Basic spam detection
        const text = messageData.text.toLowerCase();
        const spamKeywords = ['spam', 'click here', 'free money', 'urgent', 'winner'];
        
        const spamScore = spamKeywords.reduce((score, keyword) => {
            return score + (text.includes(keyword) ? 1 : 0);
        }, 0);
        
        if (spamScore >= 2) {
            logger.warn(`Potential spam message detected: ${messageData.id}`, {
                spam_score: spamScore,
                from_user: messageData.from_user
            });
            // For now, just log but don't block
        }
        
        return true; // Allow message through
    }

    generateMessageHash(messageData) {
        const hashData = `${messageData.from_user}:${messageData.text}:${messageData.message_type}`;
        return crypto.createHash('md5').update(hashData).digest('hex');
    }

    cleanupCaches() {
        const now = Date.now();
        const maxAge = 300000; // 5 minutes
        
        // Cleanup duplicate message cache
        for (const [hash, timestamp] of this.duplicateMessageCache.entries()) {
            if (now - timestamp > maxAge) {
                this.duplicateMessageCache.delete(hash);
            }
        }
        
        // Cleanup rate limit cache
        for (const [userId, timestamps] of this.rateLimitCache.entries()) {
            const recentTimestamps = timestamps.filter(ts => now - ts < 60000);
            if (recentTimestamps.length === 0) {
                this.rateLimitCache.delete(userId);
            } else {
                this.rateLimitCache.set(userId, recentTimestamps);
            }
        }
        
        logger.debug('Message caches cleaned up', {
            duplicate_cache_size: this.duplicateMessageCache.size,
            rate_limit_cache_size: this.rateLimitCache.size
        });
    }

    extractMessageData(message) {
        try {
            const messageData = {
                id: message.key.id,
                from_user: message.key.remoteJid,
                text: this.extractText(message),
                timestamp: new Date(message.messageTimestamp * 1000).toISOString(),
                message_type: this.getMessageType(message),
                media_url: null,
                media_type: null,
                media_size: null,
                media_mimetype: null,
                mentions: this.extractMentions(message),
                quoted_message: this.extractQuotedMessage(message),
                chat_type: this.getChatType(message.key.remoteJid),
                participant: message.key.participant || null,
                is_forwarded: this.isForwardedMessage(message),
                context_info: this.extractContextInfo(message),
                raw_message: this.sanitizeRawMessage(message)
            };

            // Process media if present
            if (this.hasMedia(message)) {
                const mediaInfo = this.extractMediaInfo(message);
                messageData.media_url = mediaInfo.url;
                messageData.media_type = mediaInfo.type;
                messageData.media_size = mediaInfo.size;
                messageData.media_mimetype = mediaInfo.mimetype;
            }

            // Validate extracted data
            this.validateMessageData(messageData);

            return messageData;

        } catch (error) {
            logger.error('Error extracting message data:', error);
            throw error;
        }
    }

    // Message type processors
    async processTextMessage(messageData, originalMessage) {
        // Enhanced text processing
        messageData.text_analysis = {
            word_count: messageData.text.split(/\s+/).length,
            char_count: messageData.text.length,
            has_urls: /https?:\/\/[^\s]+/gi.test(messageData.text),
            has_mentions: messageData.mentions.length > 0,
            language: this.detectLanguage(messageData.text)
        };
        
        logger.debug('Processed text message', {
            message_id: messageData.id,
            word_count: messageData.text_analysis.word_count,
            has_urls: messageData.text_analysis.has_urls
        });
    }

    async processImageMessage(messageData, originalMessage) {
        const imageMsg = originalMessage.message.imageMessage;

        messageData.image_info = {
            width: imageMsg.width,
            height: imageMsg.height,
            caption: imageMsg.caption || '',
            is_animated: imageMsg.gifPlayback || false
        };

        // Download and save image
        try {
            const savedPath = await this.downloadAndSaveMedia(originalMessage, 'image');
            if (savedPath) {
                messageData.image_info.local_path = savedPath;
                messageData.media_local_path = savedPath;
                logger.info('Image saved successfully', {
                    message_id: messageData.id,
                    path: savedPath
                });
            }
        } catch (error) {
            logger.error('Failed to download image', {
                message_id: messageData.id,
                error: error.message
            });
        }

        logger.debug('Processed image message', {
            message_id: messageData.id,
            dimensions: `${imageMsg.width}x${imageMsg.height}`,
            has_caption: !!imageMsg.caption,
            saved: !!messageData.image_info.local_path
        });
    }

    async downloadAndSaveMedia(message, mediaType) {
        if (!this.socket) {
            logger.warn('Socket not available for media download');
            return null;
        }

        try {
            const buffer = await downloadMediaMessage(
                message,
                'buffer',
                {},
                {
                    logger: console,
                    reuploadRequest: this.socket.updateMediaMessage
                }
            );

            if (!buffer || buffer.length === 0) {
                logger.warn('Empty buffer received for media download');
                return null;
            }

            const ext = this.getFileExtension(message, mediaType);
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
            const filename = `${timestamp}_${message.key.id}${ext}`;
            const folder = this.getMediaFolder(mediaType);
            const folderPath = path.join(this.mediaBasePath, folder);

            await fs.mkdir(folderPath, { recursive: true });
            const filePath = path.join(folderPath, filename);
            await fs.writeFile(filePath, buffer);

            logger.info('Media saved', {
                type: mediaType,
                path: filePath,
                size: buffer.length
            });

            return filePath;

        } catch (error) {
            logger.error('Error downloading media', {
                type: mediaType,
                message_id: message.key.id,
                error: error.message
            });
            return null;
        }
    }

    getFileExtension(message, mediaType) {
        const msg = message.message;
        let mimetype = '';

        switch (mediaType) {
            case 'image':
                mimetype = msg.imageMessage?.mimetype || 'image/jpeg';
                break;
            case 'video':
                mimetype = msg.videoMessage?.mimetype || 'video/mp4';
                break;
            case 'audio':
                mimetype = msg.audioMessage?.mimetype || 'audio/ogg';
                break;
            case 'document':
                mimetype = msg.documentMessage?.mimetype || 'application/octet-stream';
                const docFilename = msg.documentMessage?.fileName;
                if (docFilename && docFilename.includes('.')) {
                    return '.' + docFilename.split('.').pop();
                }
                break;
            case 'sticker':
                mimetype = msg.stickerMessage?.mimetype || 'image/webp';
                break;
        }

        const mimeToExt = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp',
            'video/mp4': '.mp4',
            'video/3gpp': '.3gp',
            'audio/ogg': '.ogg',
            'audio/mpeg': '.mp3',
            'audio/mp4': '.m4a',
            'application/pdf': '.pdf',
            'application/msword': '.doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx'
        };

        return mimeToExt[mimetype] || '.bin';
    }

    getMediaFolder(mediaType) {
        const folders = {
            'image': 'images',
            'video': 'videos',
            'audio': 'audio',
            'document': 'documents',
            'sticker': 'stickers'
        };
        return folders[mediaType] || 'other';
    }

    async processVideoMessage(messageData, originalMessage) {
        const videoMsg = originalMessage.message.videoMessage;
        
        messageData.video_info = {
            duration: videoMsg.seconds,
            width: videoMsg.width,
            height: videoMsg.height,
            caption: videoMsg.caption || '',
            is_gif: videoMsg.gifPlayback || false
        };
        

        // Download and save video
        try {
            const savedPath = await this.downloadAndSaveMedia(originalMessage, 'video');
            if (savedPath) {
                messageData.video_info.local_path = savedPath;
                messageData.media_local_path = savedPath;
                logger.info('Video saved successfully', { message_id: messageData.id, path: savedPath });
            }
        } catch (error) {
            logger.error('Failed to download video', { message_id: messageData.id, error: error.message });
        }

        logger.debug('Processed video message', {
            message_id: messageData.id,
            duration: videoMsg.seconds,
            dimensions: `${videoMsg.width}x${videoMsg.height}`
        });
    }

    async processAudioMessage(messageData, originalMessage) {
        const audioMsg = originalMessage.message.audioMessage;
        
        messageData.audio_info = {
            duration: audioMsg.seconds,
            is_voice_note: audioMsg.ptt || false,
            waveform: audioMsg.waveform
        };
        
        // TODO: Implement speech-to-text if needed

        // Download and save audio
        try {
            const savedPath = await this.downloadAndSaveMedia(originalMessage, 'audio');
            if (savedPath) {
                messageData.audio_info.local_path = savedPath;
                messageData.media_local_path = savedPath;
                logger.info('Audio saved successfully', { message_id: messageData.id, path: savedPath });
            }
        } catch (error) {
            logger.error('Failed to download audio', { message_id: messageData.id, error: error.message });
        }

        logger.debug('Processed audio message', {
            message_id: messageData.id,
            duration: audioMsg.seconds,
            is_voice_note: audioMsg.ptt
        });
    }

    async processDocumentMessage(messageData, originalMessage) {
        const docMsg = originalMessage.message.documentMessage;
        
        messageData.document_info = {
            filename: docMsg.fileName,
            page_count: docMsg.pageCount,
            title: docMsg.title,
            caption: docMsg.caption || ''
        };
        

        // Download and save document
        try {
            const savedPath = await this.downloadAndSaveMedia(originalMessage, 'document');
            if (savedPath) {
                messageData.document_info.local_path = savedPath;
                messageData.media_local_path = savedPath;
                logger.info('Document saved successfully', { message_id: messageData.id, path: savedPath });
            }
        } catch (error) {
            logger.error('Failed to download document', { message_id: messageData.id, error: error.message });
        }

        logger.debug('Processed document message', {
            message_id: messageData.id,
            filename: docMsg.fileName,
            mimetype: docMsg.mimetype
        });
    }

    async processStickerMessage(messageData, originalMessage) {
        const stickerMsg = originalMessage.message.stickerMessage;
        
        messageData.sticker_info = {
            width: stickerMsg.width,
            height: stickerMsg.height,
            is_animated: stickerMsg.isAnimated || false
        };
        

        // Download and save sticker
        try {
            const savedPath = await this.downloadAndSaveMedia(originalMessage, 'sticker');
            if (savedPath) {
                messageData.sticker_info.local_path = savedPath;
                messageData.media_local_path = savedPath;
                logger.info('Sticker saved successfully', { message_id: messageData.id, path: savedPath });
            }
        } catch (error) {
            logger.error('Failed to download sticker', { message_id: messageData.id, error: error.message });
        }

        logger.debug('Processed sticker message', {
            message_id: messageData.id,
            is_animated: stickerMsg.isAnimated
        });
    }

    async processLocationMessage(messageData, originalMessage) {
        const locationMsg = originalMessage.message.locationMessage;
        
        messageData.location_info = {
            latitude: locationMsg.degreesLatitude,
            longitude: locationMsg.degreesLongitude,
            name: locationMsg.name,
            address: locationMsg.address,
            live_location: !!locationMsg.isLive
        };
        
        logger.debug('Processed location message', {
            message_id: messageData.id,
            coordinates: `${locationMsg.degreesLatitude},${locationMsg.degreesLongitude}`,
            is_live: locationMsg.isLive
        });
    }

    async processContactMessage(messageData, originalMessage) {
        const contactMsg = originalMessage.message.contactMessage;
        
        messageData.contact_info = {
            display_name: contactMsg.displayName,
            vcard: contactMsg.vcard
        };
        
        logger.debug('Processed contact message', {
            message_id: messageData.id,
            contact_name: contactMsg.displayName
        });
    }

    // Helper methods for enhanced extraction
    extractMediaInfo(message) {
        const mediaTypes = ['imageMessage', 'videoMessage', 'audioMessage', 'documentMessage', 'stickerMessage'];
        
        for (const type of mediaTypes) {
            const mediaMsg = message.message[type];
            if (mediaMsg) {
                return {
                    type: type.replace('Message', ''),
                    url: this.generateMediaUrl(message.key.id, type),
                    size: mediaMsg.fileLength,
                    mimetype: mediaMsg.mimetype,
                    sha256: mediaMsg.fileSha256,
                    enc_sha256: mediaMsg.fileEncSha256
                };
            }
        }
        
        return null;
    }

    generateMediaUrl(messageId, mediaType) {
        // Generate a URL for media access
        // In production, this would be a proper media server URL
        return `media://${messageId}.${mediaType.replace('Message', '')}`;
    }

    isForwardedMessage(message) {
        return !!(message.message?.extendedTextMessage?.contextInfo?.forwardingScore ||
                 message.message?.imageMessage?.contextInfo?.forwardingScore ||
                 message.message?.videoMessage?.contextInfo?.forwardingScore);
    }

    extractContextInfo(message) {
        const contextInfo = message.message?.extendedTextMessage?.contextInfo ||
                           message.message?.imageMessage?.contextInfo ||
                           message.message?.videoMessage?.contextInfo ||
                           message.message?.documentMessage?.contextInfo;
        
        if (!contextInfo) return null;
        
        return {
            forwarding_score: contextInfo.forwardingScore,
            is_forwarded: contextInfo.isForwarded,
            quoted_message_id: contextInfo.stanzaId,
            mentioned_jids: contextInfo.mentionedJid || []
        };
    }

    sanitizeRawMessage(message) {
        // Return a sanitized version of the raw message for debugging
        return {
            key: message.key,
            message_timestamp: message.messageTimestamp,
            status: message.status,
            message_type: this.getMessageType(message)
        };
    }

    detectLanguage(text) {
        // Simple language detection based on character patterns
        // In production, you might use a proper language detection library
        if (/[а-яё]/i.test(text)) return 'ru';
        if (/[àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]/i.test(text)) return 'es';
        if (/[äöüß]/i.test(text)) return 'de';
        if (/[àâäçéèêëïîôùûüÿ]/i.test(text)) return 'fr';
        return 'en'; // Default to English
    }

    extractText(message) {
        // Handle different message types
        if (message.message?.conversation) {
            return message.message.conversation;
        }
        
        if (message.message?.extendedTextMessage?.text) {
            return message.message.extendedTextMessage.text;
        }
        
        if (message.message?.imageMessage?.caption) {
            return message.message.imageMessage.caption;
        }
        
        if (message.message?.videoMessage?.caption) {
            return message.message.videoMessage.caption;
        }
        
        if (message.message?.documentMessage?.caption) {
            return message.message.documentMessage.caption;
        }

        // For media messages without text
        if (this.hasMedia(message)) {
            return `[${this.getMediaType(message).toUpperCase()}]`;
        }
        
        return '';
    }

    getMessageType(message) {
        const msg = message.message;
        
        if (msg?.conversation || msg?.extendedTextMessage) {
            return 'text';
        }
        
        if (msg?.imageMessage) {
            return 'image';
        }
        
        if (msg?.videoMessage) {
            return 'video';
        }
        
        if (msg?.audioMessage) {
            return 'audio';
        }
        
        if (msg?.documentMessage) {
            return 'document';
        }
        
        if (msg?.stickerMessage) {
            return 'sticker';
        }
        
        if (msg?.locationMessage) {
            return 'location';
        }
        
        if (msg?.contactMessage) {
            return 'contact';
        }
        
        return 'unknown';
    }

    hasMedia(message) {
        const msg = message.message;
        return !!(msg?.imageMessage || msg?.videoMessage || msg?.audioMessage || 
                 msg?.documentMessage || msg?.stickerMessage);
    }

    getMediaType(message) {
        const msg = message.message;
        
        if (msg?.imageMessage) return 'image';
        if (msg?.videoMessage) return 'video';
        if (msg?.audioMessage) return 'audio';
        if (msg?.documentMessage) return 'document';
        if (msg?.stickerMessage) return 'sticker';
        
        return 'unknown';
    }

    extractMediaUrl(message) {
        // In a real implementation, you would download and store the media
        // For now, we'll return a placeholder
        const mediaType = this.getMediaType(message);
        return `media://${message.key.id}.${mediaType}`;
    }

    extractMentions(message) {
        const mentions = message.message?.extendedTextMessage?.contextInfo?.mentionedJid || [];
        return mentions;
    }

    extractQuotedMessage(message) {
        const quotedMessage = message.message?.extendedTextMessage?.contextInfo?.quotedMessage;
        
        if (quotedMessage) {
            return {
                id: message.message.extendedTextMessage.contextInfo.stanzaId,
                text: quotedMessage.conversation || quotedMessage.extendedTextMessage?.text || '',
                participant: message.message.extendedTextMessage.contextInfo.participant
            };
        }
        
        return null;
    }

    getChatType(remoteJid) {
        if (remoteJid.endsWith('@g.us')) {
            return 'group';
        } else if (remoteJid.endsWith('@s.whatsapp.net')) {
            return 'individual';
        } else if (remoteJid.endsWith('@broadcast')) {
            return 'broadcast';
        }
        return 'unknown';
    }

    async publishMessage(messageData) {
        try {
            const channel = config.get('redis.channels.inbound');
            
            // Add processing metadata
            const enrichedMessageData = {
                ...messageData,
                processing: {
                    received_at: new Date().toISOString(),
                    service: config.get('service.name'),
                    version: config.get('service.version'),
                    processed_by: 'message-handler',
                    handler_stats: this.getHandlerStats()
                }
            };
            
            // Determine priority based on message characteristics
            const priority = this.determineMessagePriority(messageData);
            
            // Publish using RedisPublisher with retry logic
            const publishId = await this.redisPublisher.publish(channel, enrichedMessageData, {
                priority,
                maxRetries: 3,
                metadata: {
                    message_id: messageData.id,
                    message_type: messageData.message_type,
                    chat_type: messageData.chat_type,
                    from_user_hash: this.hashUserId(messageData.from_user),
                    notify_success: false // Don't notify for every message
                }
            });
            
            logger.info(`Message queued for Redis publish: ${channel}`, {
                publish_id: publishId,
                message_id: messageData.id,
                message_type: messageData.message_type,
                chat_type: messageData.chat_type,
                priority,
                channel,
                from_user_hash: this.hashUserId(messageData.from_user),
                text_length: messageData.text.length,
                has_media: !!messageData.media_url
            });
            
            // Update metrics
            if (this.metrics) {
                this.metrics.updateLastActivity();
            }
            
            return publishId;
            
        } catch (error) {
            logger.error('Error publishing message to Redis:', error);
            if (this.metrics) {
                this.metrics.incrementErrors();
            }
            throw error;
        }
    }

    determineMessagePriority(messageData) {
        // High priority for certain message types or conditions
        if (messageData.message_type === 'location' && messageData.location_info?.live_location) {
            return 'high'; // Live location updates are time-sensitive
        }
        
        if (messageData.text && messageData.text.toLowerCase().includes('urgent')) {
            return 'high'; // Messages marked as urgent
        }
        
        if (messageData.chat_type === 'group' && messageData.mentions.length > 0) {
            return 'high'; // Group messages with mentions
        }
        
        return 'normal';
    }

    // Batch publishing for high-volume scenarios
    async publishMessageBatch(messages) {
        try {
            const channel = config.get('redis.channels.inbound');
            const batchItems = messages.map(messageData => ({
                channel,
                data: {
                    ...messageData,
                    processing: {
                        received_at: new Date().toISOString(),
                        service: config.get('service.name'),
                        version: config.get('service.version'),
                        processed_by: 'message-handler-batch'
                    }
                },
                options: {
                    priority: this.determineMessagePriority(messageData),
                    metadata: {
                        message_id: messageData.id,
                        batch_processing: true
                    }
                }
            }));

            const result = await this.redisPublisher.publishBatch(batchItems);
            
            logger.info('Message batch published', {
                batch_id: result.batch_id,
                total_messages: result.summary.total,
                successful: result.summary.successful,
                failed: result.summary.failed,
                duration_ms: result.summary.duration_ms
            });

            return result;

        } catch (error) {
            logger.error('Error publishing message batch:', error);
            if (this.metrics) {
                this.metrics.incrementErrors();
            }
            throw error;
        }
    }

    hashUserId(userId) {
        return crypto.createHash('sha256').update(userId).digest('hex').substring(0, 8);
    }

    // Enhanced validation with more comprehensive checks
    validateMessageData(messageData) {
        const required = ['id', 'from_user', 'timestamp', 'message_type'];
        
        for (const field of required) {
            if (!messageData[field]) {
                throw new Error(`Missing required field: ${field}`);
            }
        }
        
        // Validate timestamp format
        if (isNaN(Date.parse(messageData.timestamp))) {
            throw new Error('Invalid timestamp format');
        }
        
        // Validate message type
        const validTypes = ['text', 'image', 'video', 'audio', 'document', 'sticker', 'location', 'contact', 'unknown'];
        if (!validTypes.includes(messageData.message_type)) {
            throw new Error(`Invalid message type: ${messageData.message_type}`);
        }
        
        // Validate chat type
        const validChatTypes = ['individual', 'group', 'broadcast', 'unknown'];
        if (!validChatTypes.includes(messageData.chat_type)) {
            throw new Error(`Invalid chat type: ${messageData.chat_type}`);
        }
        
        // Validate user ID format
        if (!messageData.from_user.includes('@')) {
            throw new Error('Invalid user ID format');
        }
        
        // Validate text length
        if (messageData.text && messageData.text.length > 65536) {
            throw new Error('Message text too long');
        }
        
        return true;
    }

    // Statistics and monitoring methods
    getHandlerStats() {
        return {
            message_handler: {
                queue_length: this.messageQueue.length,
                processing: this.processingQueue,
                processors: this.messageProcessors.size,
                filters: this.messageFilters.length,
                cache_sizes: {
                    duplicate_messages: this.duplicateMessageCache.size,
                    rate_limits: this.rateLimitCache.size
                }
            },
            redis_publisher: this.redisPublisher ? this.redisPublisher.getStats() : null
        };
    }

    async getHealthStatus() {
        const handlerHealth = {
            healthy: this.processingQueue,
            queue_size: this.messageQueue.length,
            cache_sizes: {
                duplicates: this.duplicateMessageCache.size,
                rate_limits: this.rateLimitCache.size
            }
        };

        const publisherHealth = this.redisPublisher 
            ? await this.redisPublisher.healthCheck()
            : { healthy: false, reason: 'Publisher not initialized' };

        return {
            message_handler: handlerHealth,
            redis_publisher: publisherHealth,
            overall_healthy: handlerHealth.healthy && publisherHealth.healthy
        };
    }

    async shutdown() {
        logger.info('Shutting down MessageHandler...');
        
        this.processingQueue = false;
        
        // Process remaining messages in queue
        const remainingMessages = this.messageQueue.length;
        if (remainingMessages > 0) {
            logger.info(`Processing ${remainingMessages} remaining messages...`);
            
            while (this.messageQueue.length > 0) {
                const message = this.messageQueue.shift();
                try {
                    await this.processQueuedMessage(message);
                } catch (error) {
                    logger.error('Error processing message during shutdown:', error);
                }
            }
        }
        
        // Shutdown Redis publisher
        if (this.redisPublisher) {
            await this.redisPublisher.shutdown();
        }
        
        // Clear caches
        this.duplicateMessageCache.clear();
        this.rateLimitCache.clear();
        
        logger.info('MessageHandler shutdown completed', {
            processed_during_shutdown: remainingMessages
        });
    }

    // Validate message data structure
    validateMessageData(messageData) {
        const required = ['id', 'from_user', 'timestamp', 'message_type'];
        
        for (const field of required) {
            if (!messageData[field]) {
                throw new Error(`Missing required field: ${field}`);
            }
        }
        
        // Validate timestamp format
        if (isNaN(Date.parse(messageData.timestamp))) {
            throw new Error('Invalid timestamp format');
        }
        
        // Validate message type
        const validTypes = ['text', 'image', 'video', 'audio', 'document', 'sticker', 'location', 'contact', 'unknown'];
        if (!validTypes.includes(messageData.message_type)) {
            throw new Error(`Invalid message type: ${messageData.message_type}`);
        }
        
        return true;
    }


}

export default MessageHandler;