# Multi-stage Dockerfile for WhatsApp Service - Optimized Production Build
FROM node:20-alpine AS builder

WORKDIR /app

# Install build dependencies with latest versions
RUN apk add --no-cache \
    chromium \
    nss \
    freetype \
    freetype-dev \
    harfbuzz \
    ca-certificates \
    ttf-freefont \
    python3 \
    make \
    g++ \
    && rm -rf /var/cache/apk/*

# Set Puppeteer environment variables
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser

# Copy package files for dependency installation
COPY package*.json ./

# Install dependencies with security optimizations
RUN npm ci --omit=dev --no-audit --no-fund && \
    npm cache clean --force && \
    rm -rf ~/.npm

# Production stage - Minimal runtime image
FROM node:20-alpine AS production

WORKDIR /app

# Install only runtime dependencies with latest versions
RUN apk add --no-cache \
    chromium \
    nss \
    freetype \
    harfbuzz \
    ca-certificates \
    ttf-freefont \
    dumb-init \
    curl \
    && rm -rf /var/cache/apk/* \
    && addgroup -g 1001 -S nodejs \
    && adduser -S whatsapp -u 1001 -G nodejs

# Set security and performance environment variables
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser \
    NODE_ENV=production \
    NODE_OPTIONS="--max-old-space-size=512 --enable-source-maps" \
    UV_THREADPOOL_SIZE=4

# Copy dependencies from builder stage
COPY --from=builder --chown=whatsapp:nodejs /app/node_modules ./node_modules

# Copy application source code
COPY --chown=whatsapp:nodejs src/ ./src/
COPY --chown=whatsapp:nodejs package*.json ./

# Create necessary directories with proper permissions
RUN mkdir -p sessions logs tmp && \
    chown -R whatsapp:nodejs sessions logs tmp && \
    chmod 755 sessions logs tmp

# Copy configuration files
COPY --chown=whatsapp:nodejs .env.example ./

# Switch to non-root user for security
USER whatsapp

# Expose application port
EXPOSE 3001

# Optimized health check with faster response
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:3001/api/health || exit 1

# Use dumb-init for proper signal handling
ENTRYPOINT ["dumb-init", "--"]

# Start the application with optimized settings
CMD ["node", "--max-old-space-size=512", "src/whatsapp-service.js"]