FROM node:24-bookworm

RUN apt-get update && apt-get install -y git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN corepack enable
RUN git clone --depth 1 https://github.com/openclaw/openclaw.git /app
RUN pnpm install --frozen-lockfile
RUN pnpm build
RUN pnpm ui:install
RUN pnpm ui:build
RUN pnpm exec playwright install chromium

ENV NODE_ENV=production
ENV HOME=/home/node
ENV PLAYWRIGHT_BROWSERS_PATH=/home/node/.cache/ms-playwright

USER node

CMD ["node", "dist/index.js"]
