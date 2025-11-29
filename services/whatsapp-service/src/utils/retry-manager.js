import logger from './logger.js';
import { WhatsAppServiceError } from './error-handler.js';

class RetryManager {
    constructor(options = {}) {
        this.defaultOptions = {
            maxAttempts: 3,
            baseDelay: 1000,
            maxDelay: 30000,
            backoffFactor: 2,
            jitter: true,
            retryCondition: (error) => this.isRetryableError(error)
        };
        
        this.options = { ...this.defaultOptions, ...options };
        this.activeRetries = new Map();
    }

    /**
     * Execute function with retry logic
     */
    async execute(fn, options = {}) {
        const config = { ...this.options, ...options };
        const operationId = this.generateOperationId();
        
        let lastError;
        let attempt = 0;

        while (attempt < config.maxAttempts) {
            attempt++;
            
            try {
                logger.debug(`Executing operation ${operationId}, attempt ${attempt}/${config.maxAttempts}`);
                
                const result = await fn();
                
                // Success - clean up and return
                this.activeRetries.delete(operationId);
                
                if (attempt > 1) {
                    logger.info(`Operation ${operationId} succeeded after ${attempt} attempts`);
                }
                
                return result;
                
            } catch (error) {
                lastError = error;
                
                // Check if we should retry
                if (!config.retryCondition(error)) {
                    logger.warn(`Operation ${operationId} failed with non-retryable error`, {
                        error: error.message,
                        attempt,
                        operation_id: operationId
                    });
                    break;
                }
                
                // Check if we have more attempts
                if (attempt >= config.maxAttempts) {
                    logger.error(`Operation ${operationId} failed after ${attempt} attempts`, {
                        error: error.message,
                        operation_id: operationId
                    });
                    break;
                }
                
                // Calculate delay for next attempt
                const delay = this.calculateDelay(attempt, config);
                
                logger.warn(`Operation ${operationId} failed, retrying in ${delay}ms`, {
                    error: error.message,
                    attempt,
                    max_attempts: config.maxAttempts,
                    delay,
                    operation_id: operationId
                });
                
                // Track active retry
                this.activeRetries.set(operationId, {
                    attempt,
                    maxAttempts: config.maxAttempts,
                    nextRetryAt: Date.now() + delay,
                    lastError: error.message
                });
                
                // Wait before next attempt
                await this.delay(delay);
            }
        }
        
        // All attempts failed
        this.activeRetries.delete(operationId);
        throw new WhatsAppServiceError(
            `Operation failed after ${attempt} attempts: ${lastError.message}`,
            'RETRY_EXHAUSTED',
            500,
            {
                attempts: attempt,
                maxAttempts: config.maxAttempts,
                lastError: lastError.message,
                operationId
            }
        );
    }

    /**
     * Execute with exponential backoff
     */
    async executeWithBackoff(fn, options = {}) {
        return this.execute(fn, {
            ...options,
            backoffFactor: options.backoffFactor || 2,
            jitter: options.jitter !== false
        });
    }

    /**
     * Execute with linear backoff
     */
    async executeWithLinearBackoff(fn, options = {}) {
        return this.execute(fn, {
            ...options,
            backoffFactor: 1,
            jitter: options.jitter !== false
        });
    }

    /**
     * Execute with fixed delay
     */
    async executeWithFixedDelay(fn, delay = 1000, options = {}) {
        return this.execute(fn, {
            ...options,
            baseDelay: delay,
            backoffFactor: 1,
            jitter: false
        });
    }

    /**
     * Calculate delay for next retry attempt
     */
    calculateDelay(attempt, config) {
        let delay;
        
        if (config.backoffFactor === 1) {
            // Linear backoff
            delay = config.baseDelay * attempt;
        } else {
            // Exponential backoff
            delay = config.baseDelay * Math.pow(config.backoffFactor, attempt - 1);
        }
        
        // Apply maximum delay limit
        delay = Math.min(delay, config.maxDelay);
        
        // Add jitter to prevent thundering herd
        if (config.jitter) {
            const jitterAmount = delay * 0.1; // 10% jitter
            delay += (Math.random() - 0.5) * 2 * jitterAmount;
        }
        
        return Math.max(delay, 0);
    }

    /**
     * Check if error is retryable
     */
    isRetryableError(error) {
        // Network and connection errors are usually retryable
        const retryableCodes = [
            'ECONNREFUSED',
            'ECONNRESET',
            'ETIMEDOUT',
            'ENOTFOUND',
            'CONNECTION_ERROR',
            'REDIS_ERROR',
            'TIMEOUT_ERROR'
        ];
        
        // HTTP status codes that are retryable
        const retryableStatusCodes = [408, 429, 500, 502, 503, 504];
        
        // Check error code
        if (error.code && retryableCodes.includes(error.code)) {
            return true;
        }
        
        // Check HTTP status code
        if (error.statusCode && retryableStatusCodes.includes(error.statusCode)) {
            return true;
        }
        
        // Check error message for common retryable patterns
        const retryablePatterns = [
            /ECONNREFUSED/i,
            /ECONNRESET/i,
            /ETIMEDOUT/i,
            /connection.*refused/i,
            /connection.*reset/i,
            /timeout/i,
            /temporary.*failure/i,
            /service.*unavailable/i
        ];
        
        const message = error.message || '';
        return retryablePatterns.some(pattern => pattern.test(message));
    }

    /**
     * Create a delay promise
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Generate unique operation ID
     */
    generateOperationId() {
        const timestamp = Date.now().toString(36);
        const random = Math.random().toString(36).substring(2, 6);
        return `op_${timestamp}_${random}`;
    }

    /**
     * Get active retry operations
     */
    getActiveRetries() {
        const now = Date.now();
        const active = [];
        
        for (const [operationId, info] of this.activeRetries.entries()) {
            active.push({
                operationId,
                attempt: info.attempt,
                maxAttempts: info.maxAttempts,
                nextRetryIn: Math.max(0, info.nextRetryAt - now),
                lastError: info.lastError
            });
        }
        
        return active;
    }

    /**
     * Cancel all active retries
     */
    cancelAllRetries() {
        const count = this.activeRetries.size;
        this.activeRetries.clear();
        
        if (count > 0) {
            logger.info(`Cancelled ${count} active retry operations`);
        }
        
        return count;
    }

    /**
     * Get retry statistics
     */
    getStats() {
        return {
            activeRetries: this.activeRetries.size,
            defaultOptions: this.defaultOptions
        };
    }

    /**
     * Create a retry wrapper for a function
     */
    wrap(fn, options = {}) {
        return async (...args) => {
            return this.execute(() => fn(...args), options);
        };
    }

    /**
     * Create specialized retry functions for common operations
     */
    createRedisRetry(options = {}) {
        return this.wrap(async (operation) => operation(), {
            maxAttempts: 5,
            baseDelay: 1000,
            maxDelay: 10000,
            retryCondition: (error) => {
                return error.code === 'ECONNREFUSED' || 
                       error.code === 'REDIS_ERROR' ||
                       error.message?.includes('Redis');
            },
            ...options
        });
    }

    createWhatsAppRetry(options = {}) {
        return this.wrap(async (operation) => operation(), {
            maxAttempts: 3,
            baseDelay: 2000,
            maxDelay: 30000,
            retryCondition: (error) => {
                // Don't retry authentication errors
                if (error.code === 'AUTHENTICATION_ERROR' || error.statusCode === 401) {
                    return false;
                }
                
                return error.code === 'CONNECTION_ERROR' ||
                       error.message?.includes('connection') ||
                       error.message?.includes('timeout');
            },
            ...options
        });
    }

    createApiRetry(options = {}) {
        return this.wrap(async (operation) => operation(), {
            maxAttempts: 3,
            baseDelay: 500,
            maxDelay: 5000,
            retryCondition: (error) => {
                // Don't retry client errors (4xx except 408, 429)
                if (error.statusCode >= 400 && error.statusCode < 500) {
                    return error.statusCode === 408 || error.statusCode === 429;
                }
                
                // Retry server errors (5xx)
                return error.statusCode >= 500;
            },
            ...options
        });
    }
}

// Export singleton instance
const retryManager = new RetryManager();

export {
    RetryManager,
    retryManager
};