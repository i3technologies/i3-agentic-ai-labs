# ---- builder ----
FROM node:20-alpine AS builder
WORKDIR /app

RUN apk add --no-cache libc6-compat

COPY package.json ./
RUN npm install

COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
# Stub secrets so build does not fail — real values injected at runtime
ENV NEXTAUTH_SECRET=build-placeholder
ENV NEXTAUTH_URL=https://evalos.i3technologies.co.ke
ENV KEYCLOAK_ISSUER=https://sso.i3technologies.co.ke/auth/realms/i3
ENV KEYCLOAK_CLIENT_ID=evalos-spa
ENV DATABASE_URL=postgresql://evalos:placeholder@localhost:5432/evalos_db

RUN npm run build

# ---- runner ----
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000

RUN addgroup --system --gid 1001 nodejs && \
    adduser  --system --uid  1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static     ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public           ./public

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD wget -qO- http://localhost:3000/api/health || exit 1

CMD ["node", "server.js"]
