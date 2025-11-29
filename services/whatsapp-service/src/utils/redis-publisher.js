import logger from './logger.js';
import config from './config.js';

class RedisPublisher {
    constructor() {
        this.redisClient = null;
        this.publishQueue = [];
        this.isProcessingQueue = false;
        this.retryAttempts = new Map();
        this.publishStats = {
            total_published: 0,
            failed_publishes: 0,
            retry_attempts: 0,
            last_publish: null
        };
        
        // Configuration
        this.maxRetries = 3;
        this.retryDelay = 1000; // 1 second
        this.maxRetryDelay = 10000; // 10 seconds
        this.queueMaxSize = 1000;
    }

    initialize(redisClient) {
        this.redisClient = redisClient;
        this.startQueueProcessor();
        
        logger.info('RedisPublisher initialized', {
            max_retries: this.maxRetries,
            queue_max_size: this.queueMaxSize
        });
    }

    async publish(channel, data, options = {}) {
        try {
            const publishItem = {
                id: this.generatePublishId(),
                channel,
                data,
                timestamp: new Date().toISOString(),
                priority: options.priority || 'normal',
                retries: 0,
                maxRetries: options.maxRetries || this.maxRetries,
                metadata: options.metadata || {}
            };

            // Add to queue for processing
            await this.addToQueue(publishItem);
            
            return publishItem.id;
            
        } catch (error) {
            logger.error('Error queuing message for publish:', error);
            this.publishStats.failed_publishes++;
            throw error;
        }
    }

    async addToQueue(publishItem) {
        if (this.publishQueue.length >= this.queueMaxSize) {
            // Remove oldest item if queue is full
            const removed = this.publishQueue.shift();
            logger.warn('Publish queue full, removed oldest item', {
                removed_id: removed.id,
                queue_size: this.publishQueue.length
            });
        }

        // Insert based on priority
        if (publishItem.priority === 'high') {
            this.publishQueue.unshift(publishItem);
        } else {
            this.publishQueue.push(publishItem);
        }

        logger.debug('Added item to publish queue', {
            id: publishItem.id,
            channel: publishItem.channel,
            priority: publishItem.priority,
            queue_size: this.publishQueue.length
        });
    }

    async startQueueProcessor() {
        if (this.isProcessingQueue) return;
        
        this.isProcessingQueue = true;
        
        while (this.isProcessingQueue) {
            if (this.publishQueue.length > 0) {
                const item = this.publishQueue.shift();
                try {
                    await this.processPublishItem(item);
                } catch (error) {
                    logger.error('Error processing publish item:', error);
                    await this.handlePublishError(item, error);
                }
            } else {
                // Wait before checking queue again
                await this.sleep(100);
            }
        }
    }

    async processPublishItem(item) {
        if (!this.redisClient || !this.redisClient.isOpen) {
            throw new Error('Redis client not available');
        }

        const startTime = Date.now();
        
        try {
            // Serialize data
            const serializedData = typeof item.data === 'string' 
                ? item.data 
                : JSON.stringify(item.data);

            // Publish to Redis
            const result = await this.redisClient.publish(item.channel, serializedData);
            
            const duration = Date.now() - startTime;
            
            // Update statistics
            this.publishStats.total_published++;
            this.publishStats.last_publish = new Date().toISOString();
            
            logger.info('Message published to Redis', {
                id: item.id,
                channel: item.channel,
                subscribers: result,
                duration_ms: duration,
                data_size: serializedData.length,
                retries: item.retries
            });

            // Publish success notification if metadata indicates it's needed
            if (item.metadata.notify_success) {
                await this.publishNotification('publish_success', {
                    publish_id: item.id,
                    channel: item.channel,
                    duration_ms: duration
                });
            }

        } catch (error) {
            logger.error('Error publishing to Redis:', error);
            throw error;
        }
    }

    async handlePublishError(item, error) {
        item.retries++;
        this.publishStats.retry_attempts++;

        if (item.retries <= item.maxRetries) {
            // Calculate retry delay with exponential backoff
            const delay = Math.min(
                this.retryDelay * Math.pow(2, item.retries - 1),
                this.maxRetryDelay
            );

            logger.warn('Retrying publish after error', {
                id: item.id,
                channel: item.channel,
                retry: item.retries,
                max_retries: item.maxRetries,
                delay_ms: delay,
                error: error.message
            });

            // Schedule retry
            setTimeout(() => {
                this.publishQueue.unshift(item); // Add to front for priority
            }, delay);

        } else {
            // Max retries exceeded
            this.publishStats.failed_publishes++;
            
            logger.error('Max retries exceeded for publish', {
                id: item.id,
                channel: item.channel,
                retries: item.retries,
                error: error.message
            });

            // Publish failure notification
            await this.publishNotification('publish_failed', {
                publish_id: item.id,
                channel: item.channel,
                error: error.message,
                retries: item.retries
            }).catch(() => {}); // Ignore notification errors
        }
    }

    async publishNotification(event, data) {
        try {
            const notificationChannel = config.get('redis.channels.notifications');
            const notification = {
                event,
                service: 'redis-publisher',
                timestamp: new Date().toISOString(),
                data
            };

            // Direct publish without queuing to avoid infinite loops
            if (this.redisClient && this.redisClient.isOpen) {
                await this.redisClient.publish(notificationChannel, JSON.stringify(notification));
            }
        } catch (error) {
            logger.error('Error publishing notification:', error);
        }
    }

    // Batch publishing for high-throughput scenarios
    async publishBatch(items) {
        const batchId = this.generatePublishId();
        const startTime = Date.now();
        
        logger.info('Starting batch publish', {
            batch_id: batchId,
            item_count: items.length
        });

        const results = [];
        
        for (const item of items) {
            try {
                const publishId = await this.publish(item.channel, item.data, {
                    ...item.options,
                    metadata: { ...item.options?.metadata, batch_id: batchId }
                });
                results.push({ success: true, id: publishId });
            } catch (error) {
                results.push({ success: false, error: error.message });
            }
        }

        const duration = Date.now() - startTime;
        const successCount = results.filter(r => r.success).length;
        
        logger.info('Batch publish completed', {
            batch_id: batchId,
            total_items: items.length,
            successful: successCount,
            failed: items.length - successCount,
            duration_ms: duration
        });

        return {
            batch_id: batchId,
            results,
            summary: {
                total: items.length,
                successful: successCount,
                failed: items.length - successCount,
                duration_ms: duration
            }
        };
    }

    // Health check and monitoring
    async healthCheck() {
        try {
            if (!this.redisClient || !this.redisClient.isOpen) {
                return {
                    healthy: false,
                    reason: 'Redis client not connected'
                };
            }

            const startTime = Date.now();
            await this.redisClient.ping();
            const latency = Date.now() - startTime;

            return {
                healthy: true,
                latency_ms: latency,
                queue_size: this.publishQueue.length,
                stats: this.getStats()
            };

        } catch (error) {
            return {
                healthy: false,
                reason: error.message
            };
        }
    }

    getStats() {
        return {
            ...this.publishStats,
            queue_size: this.publishQueue.length,
            is_processing: this.isProcessingQueue,
            uptime_ms: Date.now() - (this.startTime || Date.now())
        };
    }

    // Utility methods
    generatePublishId() {
        return `pub_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
    }

    async sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // Queue management
    clearQueue() {
        const clearedCount = this.publishQueue.length;
        this.publishQueue = [];
        
        logger.info('Publish queue cleared', {
            cleared_items: clearedCount
        });
        
        return clearedCount;
    }

    getQueueInfo() {
        const priorityCounts = this.publishQueue.reduce((counts, item) => {
            counts[item.priority] = (counts[item.priority] || 0) + 1;
            return counts;
        }, {});

        return {
            total_items: this.publishQueue.length,
            priority_breakdown: priorityCounts,
            oldest_item: this.publishQueue.length > 0 ? this.publishQueue[0].timestamp : null
        };
    }

    // Graceful shutdown
    async shutdown() {
        logger.info('Shutting down RedisPublisher...');
        
        this.isProcessingQueue = false;
        
        // Process remaining items in queue
        const remainingItems = this.publishQueue.length;
        if (remainingItems > 0) {
            logger.info(`Processing ${remainingItems} remaining items...`);
            
            while (this.publishQueue.length > 0) {
                const item = this.publishQueue.shift();
                try {
                    await this.processPublishItem(item);
                } catch (error) {
                    logger.error('Error processing item during shutdown:', error);
                }
            }
        }
        
        logger.info('RedisPublisher shutdown completed', {
            final_stats: this.getStats()
        });
    }
}

export default RedisPublisher;