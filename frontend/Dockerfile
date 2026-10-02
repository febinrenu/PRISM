# PRISM frontend — Next.js 14 standalone (Module F).
FROM node:22-alpine AS builder
WORKDIR /app

# postinstall copies the pdf.js worker into public/, which must exist before
# `npm ci` runs (only package files have been copied at this point).
COPY package.json package-lock.json ./
RUN mkdir -p public && npm ci

COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
# NEXT_PUBLIC_* values are inlined at build time, so the API URL must be a
# build argument; setting it only at runtime has no effect.
ARG NEXT_PUBLIC_API_URL=
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1

# Next standalone output keeps the runtime image tiny.
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
