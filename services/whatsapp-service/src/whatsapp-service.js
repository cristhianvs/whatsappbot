import { makeWASocket, DisconnectReason, useMultiFileAuthState, fetchLatestBaileysVersion } from
  '@whiskeysockets/baileys';
  import { createClient } from 'redis';
  import path from 'path';
  import fs from 'fs';
  import logger from './utils/logger.js';
  import config from './utils/config.js';
  import ServiceMetrics from './utils/service-metrics.js';
  import MessageHandler from './handlers/message-handler.js';
  import ConnectionHandler from './handlers/connection-handler.js';
  import OutboundHandler from './handlers/outbound-handler.js';

  class WhatsAppService {
      constructor() {
          this.socket = null;
          this.redisClient = null;
          this.metrics = new ServiceMetrics();
          this.messageHandler = new MessageHandler();
          this.connectionHandler = new ConnectionHandler();
          this.outboundHandler = new OutboundHandler();
          this.isInitialized = false;
          this.sessionPath = config.get('whatsapp.sessionPath') || './sessions';
          this.sessionName = config.get('whatsapp.sessionName') || 'bot-session';
      }

      async initialize() {
          try {
              logger.info('Initializing WhatsApp Service...');
              await this.initializeRedis();
              this.connectionHandler.initialize(this.metrics);
              this.connectionHandler.setReconnectCallback(() => this.reconnect());
              await this.connectWhatsApp();
              this.isInitialized = true;
              logger.info('WhatsApp Service initialized successfully');
          } catch (error) {
              logger.error('Failed to initialize WhatsApp Service:', error);
              throw error;
          }
      }

      async initializeRedis() {
          try {
              const redisConfig = config.getRedisConfig();
              logger.info('Connecting to Redis...');
              this.redisClient = createClient(redisConfig);
              this.redisClient.on('error', (error) => { logger.error('Redis client error:', error);
  this.metrics.incrementErrors(); });
              this.redisClient.on('connect', () => { logger.logRedisEvent('connected'); });
              this.redisClient.on('reconnecting', () => { logger.logRedisEvent('reconnecting'); });
              await this.redisClient.connect();
              logger.info('Redis connection established');
          } catch (error) {
              logger.error('Failed to initialize Redis:', error);
              throw error;
          }
      }

      async connectWhatsApp() {
          try {
              const fullSessionPath = path.join(this.sessionPath, this.sessionName);
              if (!fs.existsSync(fullSessionPath)) {
                  fs.mkdirSync(fullSessionPath, { recursive: true });
                  logger.info('Created session directory:', { path: fullSessionPath });
              }
              const { state, saveCreds } = await useMultiFileAuthState(fullSessionPath);
              const { version } = await fetchLatestBaileysVersion();
              logger.info('Using Baileys version:', { version });
              const baileysLogger = {
                  level: 'silent',
                  trace: () => {},
                  debug: () => {},
                  info: (msg) => logger.debug('Baileys:', { msg }),
                  warn: (msg) => logger.warn('Baileys:', { msg }),
                  error: (msg) => logger.error('Baileys:', { msg }),
                  fatal: (msg) => logger.error('Baileys FATAL:', { msg }),
                  child: () => baileysLogger
              };
              this.socket = makeWASocket({
                  version,
                  auth: state,
                  printQRInTerminal: config.get('whatsapp.printQR') !== false,
                  logger: baileysLogger,
                  markOnlineOnConnect: config.get('whatsapp.markOnline') || false,
                  syncFullHistory: false,
                  defaultQueryTimeoutMs: config.get('whatsapp.queryTimeout') || 60000
              });
              this.setupEventHandlers(saveCreds);
              logger.info('WhatsApp socket created');
          } catch (error) {
              logger.error('Failed to connect to WhatsApp:', error);
              throw error;
          }
      }

      setupEventHandlers(saveCreds) {
          this.socket.ev.on('connection.update', async (update) => {
              this.connectionHandler.handleConnectionUpdate(update);
              const { connection, lastDisconnect } = update;
              if (connection === 'open') {
                  logger.info('WhatsApp connection established');
                  this.initializeHandlersWithSocket();
                  await this.publishStatus('connected');
              }
              if (connection === 'close') {
                  const statusCode = lastDisconnect?.error?.output?.statusCode;
                  const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
                  logger.info('WhatsApp connection closed', { statusCode, shouldReconnect, reason:
  this.getDisconnectReasonName(statusCode) });
                  await this.publishStatus('disconnected', { reason: this.getDisconnectReasonName(statusCode),
  willReconnect: shouldReconnect });
              }
          });
          this.socket.ev.on('creds.update', saveCreds);
          this.socket.ev.on('messages.upsert', async ({ messages, type }) => {
              if (type !== 'notify') return;
              for (const message of messages) {
                  try {
                      if (message.key.fromMe) continue;
                      await this.messageHandler.handleMessage(message);
                  } catch (error) {
                      logger.error('Error processing message:', error);
                      this.metrics.incrementErrors();
                  }
              }
          });
          this.socket.ev.on('messages.update', (updates) => {
              for (const update of updates) {
                  logger.debug('Message update received', { messageId: update.key.id, status: update.update?.status
  });
              }
          });
          this.socket.ev.on('presence.update', (presence) => {
              logger.debug('Presence update', { id: presence.id, presences: Object.keys(presence.presences || {})
  });
          });
          logger.info('Event handlers configured');
      }

      initializeHandlersWithSocket() {
          this.messageHandler.initialize(this.redisClient, this.metrics, this.socket);
          this.outboundHandler.initialize(this.socket, this.redisClient, this.metrics);
          this.outboundHandler.listenForOutboundMessages().catch(error => { logger.error('Failed to setup outbound message listener:', error); });
          logger.info('Handlers initialized with socket');
      }

      async reconnect() {
          try {
              logger.info('Attempting to reconnect...');
              await this.backupSession();
              await this.delay(3000);
              await this.connectWhatsApp();
          } catch (error) {
              logger.error('Reconnection failed:', error);
              this.metrics.incrementErrors();
          }
      }

      async backupSession() {
          try {
              const fullSessionPath = path.join(this.sessionPath, this.sessionName);
              const backupPath = path.join(this.sessionPath, this.sessionName + '_backup_' + Date.now());
              if (fs.existsSync(fullSessionPath)) {
                  fs.cpSync(fullSessionPath, backupPath, { recursive: true });
                  logger.info('Session backed up', { backupPath });
                  this.cleanOldBackups();
              }
          } catch (error) {
              logger.warn('Failed to backup session:', error);
          }
      }

      cleanOldBackups() {
          try {
              const files = fs.readdirSync(this.sessionPath);
              const backups = files.filter(f => f.startsWith(this.sessionName + '_backup_')).sort().reverse();
              for (let i = 3; i < backups.length; i++) {
                  const backupPath = path.join(this.sessionPath, backups[i]);
                  fs.rmSync(backupPath, { recursive: true, force: true });
                  logger.debug('Removed old backup:', { path: backupPath });
              }
          } catch (error) {
              logger.warn('Failed to clean old backups:', error);
          }
      }

      getDisconnectReasonName(statusCode) {
          const reasons = {
              [DisconnectReason.badSession]: 'bad_session',
              [DisconnectReason.connectionClosed]: 'connection_closed',
              [DisconnectReason.connectionLost]: 'connection_lost',
              [DisconnectReason.connectionReplaced]: 'connection_replaced',
              [DisconnectReason.loggedOut]: 'logged_out',
              [DisconnectReason.restartRequired]: 'restart_required',
              [DisconnectReason.timedOut]: 'timed_out'
          };
          return reasons[statusCode] || 'unknown_' + statusCode;
      }

      async publishStatus(status, details = {}) {
          try {
              if (!this.redisClient || !this.redisClient.isOpen) {
                  logger.warn('Redis not connected, cannot publish status');
                  return;
              }
              const channel = config.get('redis.channels.status');
              const statusData = { service: 'whatsapp-service', status, timestamp: new Date().toISOString(),
  ...details };
              await this.redisClient.publish(channel, JSON.stringify(statusData));
              logger.debug('Status published', { channel, status });
          } catch (error) {
              logger.error('Failed to publish status:', error);
          }
      }

      async sendMessage(jid, text, options = {}) {
          if (!this.socket || !this.connectionHandler.isConnected) {
              throw new Error('WhatsApp not connected');
          }
          try {
              const messageContent = { text, ...(options.mentions && { mentions: options.mentions }),
  ...(options.quoted && { quoted: options.quoted }) };
              const result = await this.socket.sendMessage(jid, messageContent);
              this.metrics.incrementSent();
              logger.logMessageSent(result.key.id, jid, true);
              return result;
          } catch (error) {
              logger.error('Failed to send message:', error);
              logger.logMessageSent('failed', jid, false);
              this.metrics.incrementErrors();
              throw error;
          }
      }

      async getConnectionStatus() {
          return {
              whatsapp: this.connectionHandler.getConnectionStatus(),
              redis: { connected: this.redisClient?.isOpen || false },
              service: { initialized: this.isInitialized, metrics: this.metrics.toJSON() }
          };
      }

      async getHealth() {
          const whatsappHealth = this.connectionHandler.getConnectionHealth();
          const messageHandlerHealth = await this.messageHandler.getHealthStatus();
          const outboundHealth = await this.outboundHandler.getHealthStatus();
          const isHealthy = whatsappHealth.status === 'healthy' && messageHandlerHealth.overall_healthy &&
  outboundHealth.healthy;
          return {
              healthy: isHealthy,
              components: { whatsapp: whatsappHealth, message_handler: messageHandlerHealth, outbound_handler:
  outboundHealth, redis: { connected: this.redisClient?.isOpen || false } },
              metrics: this.metrics.getHealthSummary()
          };
      }

      delay(ms) {
          return new Promise(resolve => setTimeout(resolve, ms));
      }

      async shutdown() {
          try {
              logger.info('Shutting down WhatsApp Service...');
              await this.publishStatus('shutting_down');
              if (this.messageHandler) { await this.messageHandler.shutdown(); }
              if (this.outboundHandler) { await this.outboundHandler.shutdown(); }
              if (this.socket) { try { await this.socket.logout(); } catch (error) { logger.warn('Error during socket logout:', error); } this.socket = null; }
              if (this.redisClient) { await this.redisClient.quit(); this.redisClient = null; }
              logger.info('WhatsApp Service shut down successfully');
          } catch (error) {
              logger.error('Error during shutdown:', error);
              throw error;
          }
      }
  }

  export default WhatsAppService;