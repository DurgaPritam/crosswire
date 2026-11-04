FROM node:22-bookworm-slim AS deps
RUN apt-get update && apt-get install -y --no-install-recommends python3 make g++ && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

FROM node:22-bookworm-slim
WORKDIR /srv
COPY --from=deps /srv/node_modules ./node_modules
COPY package.json ./
COPY lib ./lib
COPY server.js worker.js ./
ENV SHOPCO_DB=/data/shopco/jobs.db PORT=3000
EXPOSE 3000
CMD ["node", "server.js"]
