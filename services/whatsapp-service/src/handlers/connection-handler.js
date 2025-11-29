import logger from '../utils/logger.js';

class ConnectionHandler {
    constructor() {
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.baseReconnectDelay = 1000; // 1 second
        this.maxReconnectDelay = 30000; // 30 seconds
        this.metrics = null;
        this.isConnected = false;
        this.lastConnectionTime = null;
        this.connectionHistory = [];
        this.isPairingMode = false; // Track if we're waiting for pairing code authentication
        this.hasBeenConnectedBefore = false; // Track if we've ever had a successful connection
    }

    initialize(metrics) {
        this.metrics = metrics;
        logger.info('ConnectionHandler initialized');
    }

    handleConnectionUpdate(update) {
        const { connection, lastDisconnect, qr } = update;
        
        try {
            if (qr) {
                this.handleQRCode(qr);
            }
            
            if (connection === 'close') {
                this.handleDisconnection(lastDisconnect);
            } else if (connection === 'open') {
                this.handleConnection();
            } else if (connection === 'connecting') {
                this.handleConnecting();
            }
            
        } catch (error) {
            logger.error('Error handling connection update:', error);
            if (this.metrics) {
                this.metrics.incrementErrors();
            }
        }
    }

    handleQRCode(qr) {
        logger.logConnectionEvent('qr_generated', {
            qr_length: qr.length,
            timestamp: new Date().toISOString()
        });
        
        // Store QR generation event
        this.addConnectionEvent('qr_generated', {
            timestamp: new Date().toISOString()
        });
    }

    handleConnection() {
        this.isConnected = true;
        this.lastConnectionTime = new Date();
        this.reconnectAttempts = 0;
        this.hasBeenConnectedBefore = true;
        this.isPairingMode = false; // Clear pairing mode on successful connection

        if (this.metrics) {
            this.metrics.setConnected();
        }

        logger.logConnectionEvent('established', {
            reconnect_attempts: this.reconnectAttempts,
            timestamp: this.lastConnectionTime.toISOString()
        });

        this.addConnectionEvent('connected', {
            timestamp: this.lastConnectionTime.toISOString(),
            reconnect_attempts: this.reconnectAttempts
        });
    }

    handleDisconnection(lastDisconnect) {
        this.isConnected = false;
        
        if (this.metrics) {
            this.metrics.setDisconnected();
        }
        
        const disconnectReason = this.getDisconnectReason(lastDisconnect);
        const shouldReconnect = this.shouldReconnect(lastDisconnect);
        
        logger.logConnectionEvent('disconnected', {
            reason: disconnectReason,
            should_reconnect: shouldReconnect,
            reconnect_attempts: this.reconnectAttempts,
            timestamp: new Date().toISOString()
        });
        
        this.addConnectionEvent('disconnected', {
            reason: disconnectReason,
            should_reconnect: shouldReconnect,
            timestamp: new Date().toISOString()
        });
        
        if (shouldReconnect) {
            this.scheduleReconnect();
        }
    }

    handleConnecting() {
        logger.logConnectionEvent('connecting', {
            attempt: this.reconnectAttempts + 1,
            timestamp: new Date().toISOString()
        });
        
        this.addConnectionEvent('connecting', {
            attempt: this.reconnectAttempts + 1,
            timestamp: new Date().toISOString()
        });
    }

    getDisconnectReason(lastDisconnect) {
        if (!lastDisconnect?.error) {
            return 'unknown';
        }
        
        const error = lastDisconnect.error;
        
        // Map Baileys disconnect reasons
        const reasonMap = {
            401: 'logged_out',
            403: 'forbidden',
            408: 'timeout',
            428: 'connection_replaced',
            440: 'connection_lost',
            500: 'internal_error',
            503: 'service_unavailable'
        };
        
        if (error.output?.statusCode) {
            return reasonMap[error.output.statusCode] || `status_${error.output.statusCode}`;
        }
        
        if (error.code) {
            return error.code.toLowerCase();
        }
        
        return 'unknown';
    }

    shouldReconnect(lastDisconnect) {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            logger.warn('Max reconnect attempts reached, stopping reconnection');
            return false;
        }

        if (!lastDisconnect?.error) {
            return true;
        }

        const error = lastDisconnect.error;

        // Handle 515 (restart required) during initial authentication
        // This is normal after QR scan - credentials are saved, need to reconnect
        if (error.output?.statusCode === 515) {
            if (!this.hasBeenConnectedBefore) {
                logger.info('Restart required after authentication - credentials saved, reconnecting...');
                return true;
            }
        }

        // Handle 503 (service unavailable) during initial authentication
        // May occur during initial sync, should retry
        if (error.output?.statusCode === 503) {
            if (!this.hasBeenConnectedBefore) {
                logger.info('Service unavailable during initial connection, will retry');
                return true;
            }
        }

        // Handle 401 errors based on authentication state
        if (error.output?.statusCode === 401) {
            // During pairing mode (initial authentication), 401 errors are expected
            // Keep reconnecting while waiting for user to enter pairing code
            if (this.isPairingMode) {
                logger.info('401 error during pairing mode, will retry connection (waiting for pairing code entry)');
                return true;
            }

            // If we've had a successful connection before, treat 401 as a real logout
            if (this.hasBeenConnectedBefore) {
                logger.warn('Logged out from established session, not attempting to reconnect');
                return false;
            }

            // For other cases during initial setup, allow retry
            logger.info('401 error during initial setup, will retry connection');
            return true;
        }

        // Don't reconnect if forbidden
        if (error.output?.statusCode === 403) {
            logger.warn('Forbidden, not attempting to reconnect');
            return false;
        }

        return true;
    }

    scheduleReconnect() {
        const delay = this.calculateReconnectDelay();
        
        logger.info(`Scheduling reconnect in ${delay}ms (attempt ${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`);
        
        this.reconnectTimeout = setTimeout(() => {
            this.reconnectAttempts++;
            this.triggerReconnect();
        }, delay);
    }

    triggerReconnect() {
        logger.info('Triggering reconnection attempt', {
            attempt: this.reconnectAttempts,
            max_attempts: this.maxReconnectAttempts
        });
        
        // Emit reconnect event that the main service can listen to
        if (this.onReconnectRequested) {
            this.onReconnectRequested();
        }
    }

    setReconnectCallback(callback) {
        this.onReconnectRequested = callback;
    }

    cancelScheduledReconnect() {
        if (this.reconnectTimeout) {
            clearTimeout(this.reconnectTimeout);
            this.reconnectTimeout = null;
            logger.info('Cancelled scheduled reconnect');
        }
    }

    calculateReconnectDelay() {
        // Exponential backoff with jitter
        const exponentialDelay = Math.min(
            this.baseReconnectDelay * Math.pow(2, this.reconnectAttempts),
            this.maxReconnectDelay
        );
        
        // Add jitter (±25%)
        const jitter = exponentialDelay * 0.25 * (Math.random() - 0.5);
        
        return Math.max(exponentialDelay + jitter, this.baseReconnectDelay);
    }

    resetReconnectAttempts() {
        this.reconnectAttempts = 0;
        logger.info('Reconnect attempts reset');
    }

    incrementReconnectAttempts() {
        this.reconnectAttempts++;
    }

    addConnectionEvent(event, data) {
        const eventData = {
            event,
            timestamp: new Date().toISOString(),
            ...data
        };
        
        this.connectionHistory.push(eventData);
        
        // Keep only last 50 events
        if (this.connectionHistory.length > 50) {
            this.connectionHistory = this.connectionHistory.slice(-50);
        }
    }

    getConnectionStatus() {
        return {
            connected: this.isConnected,
            last_connection_time: this.lastConnectionTime ? this.lastConnectionTime.toISOString() : null,
            reconnect_attempts: this.reconnectAttempts,
            max_reconnect_attempts: this.maxReconnectAttempts,
            connection_history: this.connectionHistory.slice(-10) // Last 10 events
        };
    }

    getConnectionHealth() {
        const now = new Date();
        const timeSinceLastConnection = this.lastConnectionTime 
            ? now.getTime() - this.lastConnectionTime.getTime()
            : null;
        
        let healthStatus = 'unknown';
        
        if (this.isConnected) {
            healthStatus = 'healthy';
        } else if (this.reconnectAttempts < this.maxReconnectAttempts) {
            healthStatus = 'reconnecting';
        } else {
            healthStatus = 'unhealthy';
        }
        
        return {
            status: healthStatus,
            connected: this.isConnected,
            reconnect_attempts: this.reconnectAttempts,
            time_since_last_connection_ms: timeSinceLastConnection,
            recent_events: this.connectionHistory.slice(-5)
        };
    }

    // Set pairing mode (called when pairing code is requested)
    setPairingMode() {
        this.isPairingMode = true;
        logger.info('Pairing mode enabled - will retry connections during authentication');
    }

    // Clear pairing mode
    clearPairingMode() {
        this.isPairingMode = false;
        logger.info('Pairing mode disabled');
    }

    // Reset connection state (useful for testing)
    reset() {
        this.reconnectAttempts = 0;
        this.isConnected = false;
        this.lastConnectionTime = null;
        this.connectionHistory = [];
        this.isPairingMode = false;
        this.hasBeenConnectedBefore = false;
        logger.info('ConnectionHandler state reset');
    }
}

export default ConnectionHandler;