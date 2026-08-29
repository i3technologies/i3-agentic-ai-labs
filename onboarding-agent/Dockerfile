# ──────────────────────────────────────────────────────────────────────────────
# i3 Onboarding Agent — Dockerfile
# Multi-stage build: builder → runtime
# Reuses the same pattern as platform/admissions (ROKS FIPS-compatible base)
# ──────────────────────────────────────────────────────────────────────────────

# Stage 1: Builder
FROM registry.access.redhat.com/ubi9/nodejs-20:latest AS builder

WORKDIR /app

# Copy dependency manifests first for Docker layer caching
COPY package.json package-lock.json tsconfig.json ./

# Install all deps (including devDependencies for build)
RUN npm ci --prefer-offline

# Copy source
COPY src/ ./src/

# Compile TypeScript → dist/
RUN npm run build

# ──────────────────────────────────────────────────────────────────────────────
# Stage 2: Runtime (minimal image, production deps only)
# ──────────────────────────────────────────────────────────────────────────────
FROM registry.access.redhat.com/ubi9/nodejs-20-minimal:latest AS runtime

WORKDIR /app

# Copy compiled output and runtime package manifest
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package.json /app/package-lock.json ./

# Install only production deps
RUN npm ci --omit=dev --prefer-offline

# Non-root user (OpenShift drops root by default; be explicit)
USER 1001

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000/health',(r)=>process.exit(r.statusCode===200?0:1))"

EXPOSE 3000

CMD ["node", "dist/server.js"]
