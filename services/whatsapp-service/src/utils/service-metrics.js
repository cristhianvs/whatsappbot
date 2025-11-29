class ServiceMetrics {
    constructor() {
        this.messagesSent = 0;
        this.messagesReceived = 0;
        this.errors = 0;
        this.startTime = new Date();
        this.lastActivity = new Date();
        this.connectionUptime = 0;
        this.lastConnected = null;
    }

    incrementSent() {
        this.messagesSent++;
        this.updateLastActivity();
    }

    incrementReceived() {
        this.messagesReceived++;
        this.updateLastActivity();
    }

    incrementErrors() {
        this.errors++;
    }

    updateLastActivity() {
        this.lastActivity = new Date();
    }

    setConnected() {
        this.lastConnected = new Date();
    }

    setDisconnected() {
        if (this.lastConnected) {
            this.connectionUptime += Date.now() - this.lastConnected.getTime();
            this.lastConnected = null;
        }
    }

    getUptime() {
        return Date.now() - this.startTime.getTime();
    }

    getConnectionUptime() {
        let uptime = this.connectionUptime;
        if (this.lastConnected) {
            uptime += Date.now() - this.lastConnected.getTime();
        }
        return uptime;
    }

    getUptimePercentage() {
        const totalUptime = this.getUptime();
        const connectionUptime = this.getConnectionUptime();
        return totalUptime > 0 ? (connectionUptime / totalUptime) * 100 : 0;
    }

    getMessagesPerMinute() {
        const uptimeMinutes = this.getUptime() / (1000 * 60);
        return uptimeMinutes > 0 ? {
            sent: this.messagesSent / uptimeMinutes,
            received: this.messagesReceived / uptimeMinutes
        } : { sent: 0, received: 0 };
    }

    reset() {
        this.messagesSent = 0;
        this.messagesReceived = 0;
        this.errors = 0;
        this.startTime = new Date();
        this.lastActivity = new Date();
        this.connectionUptime = 0;
        this.lastConnected = null;
    }

    toJSON() {
        const now = Date.now();
        const uptimeMs = this.getUptime();
        const connectionUptimeMs = this.getConnectionUptime();
        const messagesPerMinute = this.getMessagesPerMinute();

        return {
            messages: {
                sent: this.messagesSent,
                received: this.messagesReceived,
                total: this.messagesSent + this.messagesReceived
            },
            errors: this.errors,
            uptime: {
                service_uptime_ms: uptimeMs,
                service_uptime_seconds: Math.floor(uptimeMs / 1000),
                connection_uptime_ms: connectionUptimeMs,
                connection_uptime_seconds: Math.floor(connectionUptimeMs / 1000),
                uptime_percentage: this.getUptimePercentage()
            },
            performance: {
                messages_per_minute: messagesPerMinute,
                last_activity: this.lastActivity.toISOString(),
                start_time: this.startTime.toISOString()
            },
            timestamps: {
                start_time: this.startTime.toISOString(),
                last_activity: this.lastActivity.toISOString(),
                last_connected: this.lastConnected ? this.lastConnected.toISOString() : null,
                current_time: new Date(now).toISOString()
            }
        };
    }

    // Get summary for health checks
    getHealthSummary() {
        const uptime = this.getUptime();
        const connectionUptime = this.getConnectionUptime();
        
        return {
            status: this.lastConnected ? 'connected' : 'disconnected',
            uptime_seconds: Math.floor(uptime / 1000),
            connection_uptime_percentage: this.getUptimePercentage(),
            messages_total: this.messagesSent + this.messagesReceived,
            errors: this.errors,
            last_activity: this.lastActivity.toISOString()
        };
    }
}

export default ServiceMetrics;