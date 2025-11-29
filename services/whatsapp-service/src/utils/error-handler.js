import logger from './logger.js';

// Custom error classes
class WhatsAppServiceError extends Error {
    constructor(message, code = 'WHATSAPP_SERVICE_ERROR', statusCode = 500, details = {}) {
        super(message);
        this.name = 'WhatsAppServiceError';
        this.code = code;
        this.statusCode = statusCode;
        this.details = details;
        this.timestamp = new Date().toISOString();
        
        // Capture stack trace
        Error.captureStackTrace(this, this.constructor);
    }

    toJSON() {
        return {
            name: this.name,
            message: this.message,
            code: this.code,
            statusCode: this.statusCode,
            details: this.details,
            timestamp: this.timestamp,
            stack: this.stack
        };
    }
}

class ConnectionError extends WhatsAppServiceError {
    constructor(message, details = {}) {
        super(message, 'CONNECTION_ERROR', 503, details);
        this.name = 'ConnectionError';
    }
}

class AuthenticationError extends WhatsAppServiceError {
    constructor(message, details = {}) {
        super(message, 'AUTHENTICATION_ERROR', 401, details);
        this.name = 'AuthenticationError';
    }
}

class ValidationError extends WhatsAppServiceError {
    constructor(message, details = {}) {
        super(message, 'VALIDATION_ERROR', 400, details);
        this.name = 'ValidationError';
    }
}

class RedisError extends WhatsAppServiceError {
    constructor(message, details = {}) {
        super(message, 'REDIS_ERROR', 503, details);
        this.name = 'RedisError';
    }
}

class SessionError extends WhatsAppServiceError {
    constructor(message, details = {}) {
        super(message, 'SESSION_ERROR', 500, details);
        this.name = 'SessionError';
    }
}

class RateLimitError extends WhatsAppServiceError {
    constructor(message, details = {}) {
        super(message, 'RATE_LIMIT_ERROR', 429, details);
        this.name = 'RateLimitError';
    }
}

// Error handler class
class ErrorHandler {
    constructor() {
        this.errorCounts = new Map();
        this.errorHistory = [];
        this.maxHistorySize = 100;
        
        // Error categorization
        this.errorCategories = {
            CRITICAL: ['CONNECTION_ERROR', 'REDIS_ERROR', 'SESSION_ERROR'],
            WARNING: ['AUTHENTICATION_ERROR', 'VALIDATION_ERROR'],
            INFO: ['RATE_LIMIT_ERROR']
        };
    }

    /**
     * Handle and log errors with appropriate categorization
     */
    handleError(error, context = {}) {
        const errorInfo = this.categorizeError(error);
        const errorEntry = {
            ...errorInfo,
            context,
            timestamp: new Date().toISOString(),
            id: this.generateErrorId()
        };

        // Add to history
        this.addToHistory(errorEntry);
        
        // Update error counts
        this.updateErrorCounts(errorInfo.code);
        
        // Log based on severity
        this.logError(errorEntry);
        
        // Check if we need to trigger alerts
        this.checkErrorThresholds(errorInfo.code);
        
        return errorEntry;
    }

    /**
     * Categorize error and extract relevant information
     */
    categorizeError(error) {
        let errorInfo = {
            name: error.name || 'Error',
            message: error.message || 'Unknown error',
            code: error.code || 'UNKNOWN_ERROR',
            statusCode: error.statusCode || 500,
            details: error.details || {},
            stack: error.stack,
            severity: 'ERROR'
        };

        // Determine severity based on error code
        if (this.errorCategories.CRITICAL.includes(errorInfo.code)) {
            errorInfo.severity = 'CRITICAL';
        } else if (this.errorCategories.WARNING.includes(errorInfo.code)) {
            errorInfo.severity = 'WARNING';
        } else if (this.errorCategories.INFO.includes(errorInfo.code)) {
            errorInfo.severity = 'INFO';
        }

        // Special handling for specific error types
        if (error.name === 'ValidationError') {
            errorInfo.severity = 'WARNING';
        } else if (error.name === 'ConnectionError') {
            errorInfo.severity = 'CRITICAL';
        }

        return errorInfo;
    }

    /**
     * Log error with appropriate level
     */
    logError(errorEntry) {
        const logData = {
            error_id: errorEntry.id,
            error_code: errorEntry.code,
            error_name: errorEntry.name,
            severity: errorEntry.severity,
            context: errorEntry.context,
            details: errorEntry.details
        };

        switch (errorEntry.severity) {
            case 'CRITICAL':
                logger.error(`CRITICAL ERROR: ${errorEntry.message}`, {
                    ...logData,
                    stack: errorEntry.stack
                });
                break;
            case 'WARNING':
                logger.warn(`WARNING: ${errorEntry.message}`, logData);
                break;
            case 'INFO':
                logger.info(`INFO: ${errorEntry.message}`, logData);
                break;
            default:
                logger.error(`ERROR: ${errorEntry.message}`, {
                    ...logData,
                    stack: errorEntry.stack
                });
        }
    }

    /**
     * Add error to history
     */
    addToHistory(errorEntry) {
        this.errorHistory.unshift(errorEntry);
        
        // Keep only recent errors
        if (this.errorHistory.length > this.maxHistorySize) {
            this.errorHistory = this.errorHistory.slice(0, this.maxHistorySize);
        }
    }

    /**
     * Update error counts for monitoring
     */
    updateErrorCounts(errorCode) {
        const count = this.errorCounts.get(errorCode) || 0;
        this.errorCounts.set(errorCode, count + 1);
    }

    /**
     * Check if error thresholds are exceeded
     */
    checkErrorThresholds(errorCode) {
        const count = this.errorCounts.get(errorCode) || 0;
        const timeWindow = 5 * 60 * 1000; // 5 minutes
        
        // Count recent errors of this type
        const recentErrors = this.errorHistory.filter(error => 
            error.code === errorCode && 
            Date.now() - new Date(error.timestamp).getTime() < timeWindow
        );

        // Define thresholds
        const thresholds = {
            CONNECTION_ERROR: 5,
            REDIS_ERROR: 10,
            VALIDATION_ERROR: 50,
            RATE_LIMIT_ERROR: 100
        };

        const threshold = thresholds[errorCode] || 20;
        
        if (recentErrors.length >= threshold) {
            logger.error(`Error threshold exceeded for ${errorCode}`, {
                error_code: errorCode,
                count: recentErrors.length,
                threshold,
                time_window_minutes: timeWindow / 60000
            });
        }
    }

    /**
     * Generate unique error ID
     */
    generateErrorId() {
        const timestamp = Date.now().toString(36);
        const random = Math.random().toString(36).substring(2, 8);
        return `err_${timestamp}_${random}`;
    }

    /**
     * Get error statistics
     */
    getErrorStats() {
        const now = Date.now();
        const timeWindows = {
            '1h': 60 * 60 * 1000,
            '24h': 24 * 60 * 60 * 1000,
            '7d': 7 * 24 * 60 * 60 * 1000
        };

        const stats = {
            total_errors: this.errorHistory.length,
            error_counts: Object.fromEntries(this.errorCounts),
            by_severity: {},
            by_time_window: {}
        };

        // Count by severity
        for (const error of this.errorHistory) {
            stats.by_severity[error.severity] = (stats.by_severity[error.severity] || 0) + 1;
        }

        // Count by time window
        for (const [window, duration] of Object.entries(timeWindows)) {
            const cutoff = now - duration;
            stats.by_time_window[window] = this.errorHistory.filter(error => 
                new Date(error.timestamp).getTime() > cutoff
            ).length;
        }

        return stats;
    }

    /**
     * Get recent errors
     */
    getRecentErrors(limit = 10) {
        return this.errorHistory.slice(0, limit).map(error => ({
            id: error.id,
            code: error.code,
            message: error.message,
            severity: error.severity,
            timestamp: error.timestamp,
            context: error.context
        }));
    }

    /**
     * Clear error history (for testing or maintenance)
     */
    clearHistory() {
        this.errorHistory = [];
        this.errorCounts.clear();
        logger.info('Error history cleared');
    }

    /**
     * Express error middleware
     */
    expressErrorHandler() {
        return (error, req, res, next) => {
            const errorEntry = this.handleError(error, {
                method: req.method,
                url: req.url,
                user_agent: req.get('User-Agent'),
                ip: req.ip
            });

            // Don't expose internal error details in production
            const isProduction = process.env.NODE_ENV === 'production';
            const response = {
                error: true,
                message: isProduction ? 'Internal server error' : error.message,
                code: error.code || 'INTERNAL_ERROR',
                error_id: errorEntry.id,
                timestamp: errorEntry.timestamp
            };

            // Include details in development
            if (!isProduction) {
                response.details = error.details || {};
                response.stack = error.stack;
            }

            res.status(error.statusCode || 500).json(response);
        };
    }

    /**
     * Process uncaught exceptions
     */
    handleUncaughtException(error) {
        const errorEntry = this.handleError(error, {
            type: 'uncaught_exception',
            fatal: true
        });

        logger.error('Uncaught exception - shutting down', {
            error_id: errorEntry.id,
            stack: error.stack
        });

        // Give time for logs to flush
        setTimeout(() => {
            process.exit(1);
        }, 1000);
    }

    /**
     * Process unhandled promise rejections
     */
    handleUnhandledRejection(reason, promise) {
        const error = reason instanceof Error ? reason : new Error(String(reason));
        
        const errorEntry = this.handleError(error, {
            type: 'unhandled_rejection',
            promise: promise.toString()
        });

        logger.error('Unhandled promise rejection', {
            error_id: errorEntry.id,
            reason: String(reason)
        });
    }

    /**
     * Setup global error handlers
     */
    setupGlobalHandlers() {
        process.on('uncaughtException', (error) => {
            this.handleUncaughtException(error);
        });

        process.on('unhandledRejection', (reason, promise) => {
            this.handleUnhandledRejection(reason, promise);
        });

        logger.info('Global error handlers setup complete');
    }
}

// Export singleton instance and error classes
const errorHandler = new ErrorHandler();

export {
    ErrorHandler,
    errorHandler,
    WhatsAppServiceError,
    ConnectionError,
    AuthenticationError,
    ValidationError,
    RedisError,
    SessionError,
    RateLimitError
};