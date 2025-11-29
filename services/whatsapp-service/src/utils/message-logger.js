import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import logger from './logger.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

class MessageLogger {
    constructor() {
        this.logsDir = path.join(__dirname, '../../logs/messages');
        this.buffer = [];
        this.bufferSize = 10; // Write every 10 messages
        this.flushInterval = 5000; // Or every 5 seconds
        this.flushTimer = null;

        // Ensure logs directory exists
        this.ensureLogsDirectory();

        // Start periodic flush
        this.startPeriodicFlush();

        // Graceful shutdown handling
        this.setupGracefulShutdown();
    }

    ensureLogsDirectory() {
        try {
            if (!fs.existsSync(this.logsDir)) {
                fs.mkdirSync(this.logsDir, { recursive: true });
                logger.info('Message logs directory created', { path: this.logsDir });
            }
        } catch (error) {
            logger.error('Error creating message logs directory:', error);
        }
    }

    getCurrentLogFile() {
        const date = new Date();
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');

        const filename = `messages_${year}-${month}-${day}.txt`;
        return path.join(this.logsDir, filename);
    }

    formatMessage(direction, data) {
        const timestamp = new Date().toISOString();
        const separator = '='.repeat(80);

        let formattedMessage = `\n${separator}\n`;
        formattedMessage += `[${timestamp}] ${direction}\n`;
        formattedMessage += `${separator}\n`;

        if (direction === 'INBOUND') {
            formattedMessage += `From: ${data.from || 'Unknown'}\n`;
            formattedMessage += `Message ID: ${data.messageId || 'N/A'}\n`;
            formattedMessage += `Type: ${data.messageType || 'text'}\n`;

            if (data.text) {
                formattedMessage += `Content: ${data.text}\n`;
            }

            if (data.hasMedia) {
                formattedMessage += `Media Type: ${data.mediaType || 'unknown'}\n`;
                formattedMessage += `Media Caption: ${data.caption || 'N/A'}\n`;
            }

            if (data.quotedMessage) {
                formattedMessage += `Quoted Message: Yes\n`;
            }

        } else if (direction === 'OUTBOUND') {
            formattedMessage += `To: ${data.to || 'Unknown'}\n`;
            formattedMessage += `Message ID: ${data.messageId || 'N/A'}\n`;
            formattedMessage += `Type: ${data.messageType || 'text'}\n`;
            formattedMessage += `Priority: ${data.priority || 'normal'}\n`;

            if (data.text || data.message) {
                formattedMessage += `Content: ${data.text || data.message}\n`;
            }

            if (data.media) {
                formattedMessage += `Media Type: ${data.media.type || 'unknown'}\n`;
                formattedMessage += `Media URL: ${data.media.url || 'N/A'}\n`;
            }

            formattedMessage += `Status: ${data.status || 'queued'}\n`;

            if (data.error) {
                formattedMessage += `Error: ${data.error}\n`;
            }
        }

        formattedMessage += `${separator}\n`;

        return formattedMessage;
    }

    logInbound(messageData) {
        try {
            const formattedMessage = this.formatMessage('INBOUND', messageData);
            this.buffer.push(formattedMessage);

            if (this.buffer.length >= this.bufferSize) {
                this.flush();
            }

            logger.debug('Inbound message logged to buffer', {
                messageId: messageData.messageId,
                bufferSize: this.buffer.length
            });
        } catch (error) {
            logger.error('Error logging inbound message:', error);
        }
    }

    logOutbound(messageData) {
        try {
            const formattedMessage = this.formatMessage('OUTBOUND', messageData);
            this.buffer.push(formattedMessage);

            if (this.buffer.length >= this.bufferSize) {
                this.flush();
            }

            logger.debug('Outbound message logged to buffer', {
                messageId: messageData.messageId,
                bufferSize: this.buffer.length
            });
        } catch (error) {
            logger.error('Error logging outbound message:', error);
        }
    }

    flush() {
        if (this.buffer.length === 0) {
            return;
        }

        try {
            const logFile = this.getCurrentLogFile();
            const content = this.buffer.join('');

            // If file doesn't exist, create it with UTF-8 BOM for better Windows compatibility
            if (!fs.existsSync(logFile)) {
                const BOM = Buffer.from([0xEF, 0xBB, 0xBF]); // UTF-8 BOM
                fs.writeFileSync(logFile, BOM);
            }

            // Use Buffer to ensure proper UTF-8 encoding
            const contentBuffer = Buffer.from(content, 'utf8');
            fs.appendFileSync(logFile, contentBuffer);

            const messageCount = this.buffer.length;
            this.buffer = [];

            logger.debug('Message buffer flushed to disk', {
                file: logFile,
                messageCount
            });
        } catch (error) {
            logger.error('Error flushing message buffer:', error);
        }
    }

    startPeriodicFlush() {
        this.flushTimer = setInterval(() => {
            this.flush();
        }, this.flushInterval);

        logger.info('Message logger periodic flush started', {
            interval: this.flushInterval
        });
    }

    stopPeriodicFlush() {
        if (this.flushTimer) {
            clearInterval(this.flushTimer);
            this.flushTimer = null;
            logger.info('Message logger periodic flush stopped');
        }
    }

    setupGracefulShutdown() {
        const shutdown = () => {
            logger.info('Message logger shutting down, flushing buffer...');
            this.stopPeriodicFlush();
            this.flush();
        };

        process.on('SIGTERM', shutdown);
        process.on('SIGINT', shutdown);
        process.on('beforeExit', shutdown);
    }

    // Method to get statistics
    getStats() {
        try {
            const files = fs.readdirSync(this.logsDir);
            const messageFiles = files.filter(f => f.startsWith('messages_') && f.endsWith('.txt'));

            const stats = {
                totalFiles: messageFiles.length,
                currentBufferSize: this.buffer.length,
                files: []
            };

            messageFiles.forEach(file => {
                const filePath = path.join(this.logsDir, file);
                const stat = fs.statSync(filePath);
                stats.files.push({
                    name: file,
                    size: stat.size,
                    modified: stat.mtime
                });
            });

            return stats;
        } catch (error) {
            logger.error('Error getting message logger stats:', error);
            return null;
        }
    }

    // Method to read messages from a specific date
    readMessagesForDate(date) {
        try {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');

            const filename = `messages_${year}-${month}-${day}.txt`;
            const filePath = path.join(this.logsDir, filename);

            if (fs.existsSync(filePath)) {
                return fs.readFileSync(filePath, 'utf8');
            } else {
                return null;
            }
        } catch (error) {
            logger.error('Error reading messages for date:', error);
            return null;
        }
    }
}

// Create singleton instance
const messageLogger = new MessageLogger();

export default messageLogger;
