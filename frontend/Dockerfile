# syntax=docker/dockerfile:1
# Multi-stage: `dev` (hot-reload, usado por docker-compose.dev.yml) e `runner`
# (build de produção standalone, alvo padrão usado por docker-compose.yml).

# ---- deps: dependências (inclui dev, necessárias para build/dev) ----
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install

# ---- dev: servidor Next em modo desenvolvimento (hot-reload) ----
FROM node:22-alpine AS dev
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

# ---- builder: build de produção (output: standalone no next.config) ----
FROM node:22-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* é inlined no bundle do browser em BUILD-TIME. '/api/v2' é
# same-origin (nginx faz proxy) — funciona no servidor e no local via :8090.
ARG NEXT_PUBLIC_API_URL=/api/v2
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

# ---- runner: imagem final mínima de produção ----
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
