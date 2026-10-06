# Production Dockerfile for IPL Auction Server
FROM node:20-alpine AS runner

WORKDIR /app

# Set production environment
ENV NODE_ENV=production
ENV PORT=3000

# Install dependencies (only 'pg' is required)
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev

# Copy application code and catalogs
COPY server.js ./
COPY lib/ ./lib/
COPY public/ ./public/
COPY data/ ./data/

# Expose HTTP port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/healthz || exit 1

# Start server
CMD ["node", "server.js"]
