# Single-Domain VPS Deployment Guide

Last verified: 2026-03-20 (Asia/Bangkok)

This guide is for the case where only `ai-influencer.tripc.ai` is available.

Instead of using three hostnames, the deployment exposes:

- `https://ai-influencer.tripc.ai/` -> Next.js frontend
- `https://ai-influencer.tripc.ai/connector/` -> ChatGPT/OpenClaw connector
- `https://ai-influencer.tripc.ai/backend/` -> direct FastAPI backend access for health/docs/admin checks

Important:

- the frontend still uses its own Next.js `/api/...` proxy routes for normal app traffic
- do not proxy `/api/` directly to FastAPI in nginx or you will bypass the existing Next.js route layer
- the backend public path is mainly for health checks, docs, webhooks, and direct operator troubleshooting

## Files You Will Use

- [setup-vps.sh](/e:/Projects/Works/AI-Influencer-TripC/setup-vps.sh)
- [docker-compose.production.yml](/e:/Projects/Works/AI-Influencer-TripC/docker-compose.production.yml)
- [Project/.env.example](/e:/Projects/Works/AI-Influencer-TripC/Project/.env.example)
- [deploy/nginx/ai-influencer.single-domain.conf](/e:/Projects/Works/AI-Influencer-TripC/deploy/nginx/ai-influencer.single-domain.conf)
- [deploy/vps/deploy-production.sh](/e:/Projects/Works/AI-Influencer-TripC/deploy/vps/deploy-production.sh)
- [deploy/vps/apply-chatgpt-connector-migration.sh](/e:/Projects/Works/AI-Influencer-TripC/deploy/vps/apply-chatgpt-connector-migration.sh)
- [deploy/vps/healthcheck.sh](/e:/Projects/Works/AI-Influencer-TripC/deploy/vps/healthcheck.sh)

## Public Topology

Use these production values:

- `FRONTEND_PUBLIC_URL=https://ai-influencer.tripc.ai`
- `BACKEND_PUBLIC_URL=https://ai-influencer.tripc.ai/backend`
- `CHATGPT_CONNECTOR_PUBLIC_URL=https://ai-influencer.tripc.ai/connector`
- `OPENAI_OAUTH_REDIRECT_URI=https://ai-influencer.tripc.ai/connector/oauth/callback`
- `NEXT_PUBLIC_API_URL=https://ai-influencer.tripc.ai`
- `PYTHON_BACKEND_URL=http://backend:8000`
- `CORS_ORIGINS=https://ai-influencer.tripc.ai`

## Fresh VPS Setup

### 1. Prepare DNS

Point `ai-influencer.tripc.ai` to the VPS public IP and wait for propagation.

Verify:

```bash
nslookup ai-influencer.tripc.ai
```

### 2. Create a real deploy user

If you only have root access, create a sudo user and copy your SSH key:

```bash
adduser deploy
usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys
```

Open a new terminal and verify you can log in as `deploy` before continuing.

### 3. Clone the repo

```bash
ssh deploy@YOUR_VPS_IP
sudo apt-get update
sudo apt-get install -y git
sudo mkdir -p /opt/ai-influencer
sudo chown -R $USER:$USER /opt/ai-influencer
git clone <YOUR_REPO_URL> /opt/ai-influencer/repo
cd /opt/ai-influencer/repo
chmod +x setup-vps.sh deploy/vps/*.sh
```

### 4. Bootstrap the host

```bash
cd /opt/ai-influencer/repo
sudo bash setup-vps.sh
```

This installs Docker, nginx, certbot, UFW, and the basic filesystem layout.

### 5. Create the production env file

```bash
cd /opt/ai-influencer/repo
cp Project/.env.example Project/.env.production
nano Project/.env.production
```

Set at least these values:

```env
POSTGRES_PASSWORD=CHANGE_THIS_POSTGRES_PASSWORD

FRONTEND_PUBLIC_URL=https://ai-influencer.tripc.ai
BACKEND_PUBLIC_URL=https://ai-influencer.tripc.ai/backend
CHATGPT_CONNECTOR_PUBLIC_URL=https://ai-influencer.tripc.ai/connector
OPENAI_OAUTH_REDIRECT_URI=https://ai-influencer.tripc.ai/connector/oauth/callback

NEXT_PUBLIC_API_URL=https://ai-influencer.tripc.ai
PYTHON_BACKEND_URL=http://backend:8000
CORS_ORIGINS=https://ai-influencer.tripc.ai

DATABASE_URL=postgresql://postgres:CHANGE_THIS_POSTGRES_PASSWORD@127.0.0.1:5432/ai_influencer
CHATGPT_CONNECTOR_DATABASE_URL=postgresql://postgres:CHANGE_THIS_POSTGRES_PASSWORD@127.0.0.1:5432/ai_influencer

OPENCLAW_API_KEY=CHANGE_THIS
OPENAI_API_KEY=CHANGE_THIS
ANTHROPIC_API_KEY=CHANGE_THIS

CHATGPT_CONNECTOR_SESSION_SECRET=CHANGE_THIS
OPENAI_OAUTH_CLIENT_ID=CHANGE_THIS
OPENAI_OAUTH_CLIENT_SECRET=CHANGE_THIS

SUPABASE_URL=CHANGE_THIS
SUPABASE_KEY=CHANGE_THIS
SUPABASE_SERVICE_ROLE_KEY=CHANGE_THIS

POSTIZ_API_KEY=CHANGE_THIS
POSTIZ_WEBHOOK_SECRET=CHANGE_THIS
GROWCHIEF_API_KEY=CHANGE_THIS
GROWCHIEF_WEBHOOK_SECRET=CHANGE_THIS

TELEGRAM_BOT_TOKEN=CHANGE_THIS
TELEGRAM_CHAT_ID=CHANGE_THIS

IPROYAL_USERNAME=CHANGE_THIS
IPROYAL_PASSWORD=CHANGE_THIS

FAL_AI_API_KEY=CHANGE_THIS
GOOGLE_AI_API_KEY=CHANGE_THIS
GOOGLE_TTS_API_KEY=CHANGE_THIS
HEYGEN_API_KEY=CHANGE_THIS
```

### 6. Issue the TLS certificate

Only one certificate is needed in this topology.

```bash
sudo systemctl stop nginx
sudo certbot certonly --standalone -d ai-influencer.tripc.ai
sudo systemctl start nginx
```

### 7. Install the single-domain nginx config

```bash
cd /opt/ai-influencer/repo
sudo cp deploy/nginx/ai-influencer.single-domain.conf /etc/nginx/sites-available/ai-influencer.conf
sudo ln -sf /etc/nginx/sites-available/ai-influencer.conf /etc/nginx/sites-enabled/ai-influencer.conf
sudo nginx -t
sudo systemctl reload nginx
```

### 8. Deploy the stack

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/deploy-production.sh
```

### 9. Apply the connector migration

```bash
cd /opt/ai-influencer/repo
./deploy/vps/apply-chatgpt-connector-migration.sh
```

### 10. Run smoke checks

Because the public URLs are path-based, make sure the env file still has:

- `BACKEND_PUBLIC_URL=https://ai-influencer.tripc.ai/backend`
- `CHATGPT_CONNECTOR_PUBLIC_URL=https://ai-influencer.tripc.ai/connector`

Then run:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/healthcheck.sh
```

## What Will Be Public

Public:

- `https://ai-influencer.tripc.ai`
- `https://ai-influencer.tripc.ai/connector/health`
- `https://ai-influencer.tripc.ai/backend/health`
- `https://ai-influencer.tripc.ai/backend/docs`

Private to the VPS:

- OpenClaw runtime
- OpenClaw control UI
- Temporal UI
- Postiz
- GrowChief
- Postgres
- Redis

## How To Reach OpenClaw And Admin UIs

Use SSH tunnels from your laptop:

```bash
ssh -L 8081:127.0.0.1:8081 -L 8080:127.0.0.1:8080 -L 3100:127.0.0.1:3100 -L 3200:127.0.0.1:3200 deploy@YOUR_VPS_IP
```

Then open locally:

- `http://localhost:8081` -> OpenClaw Control UI
- `http://localhost:8080` -> Temporal UI
- `http://localhost:3100` -> Postiz
- `http://localhost:3200` -> GrowChief

## Connector Registration

When registering the ChatGPT/OpenAI connector, use:

- public base URL: `https://ai-influencer.tripc.ai/connector`
- redirect URI: `https://ai-influencer.tripc.ai/connector/oauth/callback`

This must match the env file exactly.

## Webhook Targets

With the single-domain setup, point providers to:

- Postiz webhook: `https://ai-influencer.tripc.ai/backend/api/webhooks/postiz`
- GrowChief webhook: `https://ai-influencer.tripc.ai/backend/api/webhooks/growchief`

## First Live Validation

After deployment:

1. Visit `https://ai-influencer.tripc.ai`
2. Visit `https://ai-influencer.tripc.ai/backend/health`
3. Visit `https://ai-influencer.tripc.ai/connector/health`
4. Confirm `docker compose -f docker-compose.production.yml ps` shows healthy services
5. Run one real weekly workflow end-to-end
6. Confirm Telegram approval, provider publish, webhook reconciliation, and dashboard updates

## Ongoing Operations

Backup:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/backup-stack.sh
```

Rollback:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/rollback-release.sh <git-ref>
```

Recreate the stack after major config changes:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production docker compose -f docker-compose.production.yml down --remove-orphans
PROJECT_ENV_FILE=./Project/.env.production docker compose -f docker-compose.production.yml up -d --build
```
