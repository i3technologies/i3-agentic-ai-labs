FROM node:20-alpine AS builder
WORKDIR /app
# Copy source first (excluding node_modules via .dockerignore)
COPY . .
# Install deps fresh on Linux so binaries have correct execute bits
RUN npm install --legacy-peer-deps
# Build using node directly — no reliance on .bin symlink permissions
RUN node node_modules/next/dist/bin/next build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
# Create public dir in case the source tree has none (Next.js standalone still expects it)
RUN mkdir -p ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
# Copy public assets only if they exist (harmless if empty)
RUN if [ -d /app/public ] && [ "$(ls -A /app/public 2>/dev/null)" ]; then cp -r /app/public/. ./public/; fi || true
USER nextjs
EXPOSE 3000
ENV PORT 3000
ENV HOSTNAME "0.0.0.0"
CMD ["node", "server.js"]
