# VPS Zero To Production Guide

Last verified: 2026-03-20 (Asia/Bangkok)

This guide is for either:

- a completely empty VPS
- or the current `ai-influencer` VPS described in `Docs/VPS.md`

Use this guide if:

- the server has no repo checked out yet
- Docker is not installed yet
- nginx is not configured yet
- only `ai-influencer.tripc.ai` exists today and you still need to create `api.ai-influencer.tripc.ai` and `connector.ai-influencer.tripc.ai`

If you cannot create the extra hostnames, stop here and use `Docs/SINGLE_DOMAIN_VPS_DEPLOY.md` instead.

## Current Known VPS State From `Docs/VPS.md`

If you are using the existing `ai-influencer` host, the repo already has a server report for it.

Known state from that report:

- hostname: `ai-influencer`
- OS: Ubuntu 22.04 LTS
- platform: Proxmox container
- RAM: `16 GB`
- disk free: about `73 GB`
- nginx is already installed and running
- current enabled site is a static HTTP site for `ai-influencer.tripc.ai`
- current nginx site file is `/etc/nginx/sites-available/ai-influencer.tripc.ai`
- an existing Let's Encrypt certificate already exists for `ai-influencer.tripc.ai`
- only ports `22` and `80` are publicly open in the report
- UFW is currently disabled in the report
- SSH root login is currently enabled in the report
- postfix is installed and localhost-only

What this means for deployment:

- you do not need to invent a host layout; use the current server as the deployment target
- you should back up the existing nginx site config before replacing it
- you likely only need new certificates for `api.ai-influencer.tripc.ai` and `connector.ai-influencer.tripc.ai`
- do not publish the private `10.10.10.13` address from the report into public DNS unless your environment explicitly routes that address publicly

## Target Production Layout

Public HTTPS hosts:

- `https://ai-influencer.tripc.ai` -> frontend
- `https://api.ai-influencer.tripc.ai` -> FastAPI backend
- `https://connector.ai-influencer.tripc.ai` -> ChatGPT connector

Private or localhost-only services:

- OpenClaw
- OpenClaw control UI
- Temporal
- Postiz
- GrowChief
- Postgres
- Redis

## Step 0: What You Need Before Starting

- one clean Ubuntu 22.04 or 24.04 VPS
- one public IPv4 address for that VPS
- SSH access to the VPS
- control over the DNS zone for `tripc.ai`
- the git URL for this repo
- real secrets for Supabase, OpenAI/Anthropic, Telegram, Postiz, GrowChief, proxies, and media providers

If you are using the current `ai-influencer` server, check these first:

```bash
hostnamectl
sudo systemctl status nginx --no-pager
sudo certbot certificates
sudo ss -tlnp
```

## Step 1: Create The Missing DNS Records

Go to the DNS provider that manages `tripc.ai`.

Use the same public IP that already serves `ai-influencer.tripc.ai`.

If you are unsure what that public IP is, check from your local machine:

```bash
nslookup ai-influencer.tripc.ai 1.1.1.1
```

Use that resolved public IP for the new records.

Create these records:

- `A` record for `ai-influencer` -> `<YOUR_VPS_PUBLIC_IP>`
- `A` record for `api.ai-influencer` -> `<YOUR_VPS_PUBLIC_IP>`
- `A` record for `connector.ai-influencer` -> `<YOUR_VPS_PUBLIC_IP>`

If your DNS UI wants only the host portion, use:

- `ai-influencer`
- `api.ai-influencer`
- `connector.ai-influencer`

Recommended TTL:

- `300`

Verify from your local machine:

```bash
nslookup ai-influencer.tripc.ai 1.1.1.1
nslookup api.ai-influencer.tripc.ai 1.1.1.1
nslookup connector.ai-influencer.tripc.ai 1.1.1.1
```

Only continue once all three resolve to the same public IP.

## Step 2: Create A Safe SSH Admin User

If you currently only have root access, create a normal sudo user first.

On the VPS:

```bash
adduser deploy
usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys
```

From your local machine, confirm you can log in before doing anything that hardens SSH:

```bash
ssh deploy@<YOUR_VPS_PUBLIC_IP>
```

## Step 3: Clone The Repo Onto The VPS

On the VPS:

```bash
sudo apt-get update
sudo apt-get install -y git
sudo mkdir -p /opt/ai-influencer
sudo chown -R $USER:$USER /opt/ai-influencer
git clone <YOUR_REPO_URL> /opt/ai-influencer/repo
cd /opt/ai-influencer/repo
chmod +x setup-vps.sh deploy/vps/*.sh
```

## Step 4: Bootstrap The Host

Run the checked-in host bootstrap:

```bash
cd /opt/ai-influencer/repo
sudo bash setup-vps.sh
```

What this does:

- installs Docker and Docker Compose
- installs nginx and certbot
- enables UFW for `22`, `80`, and `443`
- creates `/opt/ai-influencer` and backup directories
- changes SSH root login from password-based to key-only

Important:

- if you have not verified key-based login for a sudo user yet, do that before running this step
- on the current `ai-influencer` host, nginx and postfix already exist, so this step is mostly adding Docker, certbot helpers, UFW, and the hardened defaults

## Step 5: Create The Production Env File

Copy the env template:

```bash
cd /opt/ai-influencer/repo
cp Project/.env.example Project/.env.production
```

Edit it:

```bash
nano Project/.env.production
```

Set at least these values:

```env
POSTGRES_PASSWORD=CHANGE_THIS

FRONTEND_PUBLIC_URL=https://ai-influencer.tripc.ai
BACKEND_PUBLIC_URL=https://api.ai-influencer.tripc.ai
CHATGPT_CONNECTOR_PUBLIC_URL=https://connector.ai-influencer.tripc.ai
NEXT_PUBLIC_API_URL=https://ai-influencer.tripc.ai
PYTHON_BACKEND_URL=http://backend:8000
OPENAI_OAUTH_REDIRECT_URI=https://connector.ai-influencer.tripc.ai/oauth/callback
CORS_ORIGINS=https://ai-influencer.tripc.ai,https://api.ai-influencer.tripc.ai,https://connector.ai-influencer.tripc.ai

DATABASE_URL=postgresql://postgres:CHANGE_THIS@127.0.0.1:5432/ai_influencer
CHATGPT_CONNECTOR_DATABASE_URL=postgresql://postgres:CHANGE_THIS@127.0.0.1:5432/ai_influencer

OPENCLAW_API_KEY=CHANGE_THIS
OPENAI_API_KEY=CHANGE_THIS
ANTHROPIC_API_KEY=CHANGE_THIS

SUPABASE_URL=CHANGE_THIS
SUPABASE_KEY=CHANGE_THIS
SUPABASE_SERVICE_ROLE_KEY=CHANGE_THIS

POSTIZ_API_KEY=CHANGE_THIS
POSTIZ_WEBHOOK_SECRET=CHANGE_THIS
GROWCHIEF_API_KEY=CHANGE_THIS
GROWCHIEF_WEBHOOK_SECRET=CHANGE_THIS

CHATGPT_CONNECTOR_SESSION_SECRET=CHANGE_THIS
OPENAI_OAUTH_CLIENT_ID=CHANGE_THIS
OPENAI_OAUTH_CLIENT_SECRET=CHANGE_THIS

TELEGRAM_BOT_TOKEN=CHANGE_THIS
TELEGRAM_CHAT_ID=CHANGE_THIS

IPROYAL_USERNAME=CHANGE_THIS
IPROYAL_PASSWORD=CHANGE_THIS

FAL_AI_API_KEY=CHANGE_THIS
GOOGLE_AI_API_KEY=CHANGE_THIS
GOOGLE_TTS_API_KEY=CHANGE_THIS
HEYGEN_API_KEY=CHANGE_THIS
```

## Step 6: Issue TLS Certificates

First inspect what already exists:

```bash
sudo certbot certificates
```

If the current VPS still has a valid certificate for `ai-influencer.tripc.ai`, you usually only need the two missing subdomains.

Stop nginx first so Certbot can bind port `80` cleanly:

```bash
sudo systemctl stop nginx
sudo certbot certonly --standalone -d api.ai-influencer.tripc.ai
sudo certbot certonly --standalone -d connector.ai-influencer.tripc.ai
sudo systemctl start nginx
```

If the main-domain certificate is missing or expired, issue all three:

```bash
sudo systemctl stop nginx
sudo certbot certonly --standalone -d ai-influencer.tripc.ai
sudo certbot certonly --standalone -d api.ai-influencer.tripc.ai
sudo certbot certonly --standalone -d connector.ai-influencer.tripc.ai
sudo systemctl start nginx
```

If one of the subdomain certificate commands fails, the usual cause is DNS not fully propagated yet.

## Step 7: Install The nginx Reverse Proxy

Use the checked-in config:

```bash
cd /opt/ai-influencer/repo
sudo cp /etc/nginx/sites-available/ai-influencer.tripc.ai /etc/nginx/sites-available/ai-influencer.tripc.ai.bak.$(date +%Y%m%d-%H%M%S) || true
sudo rm -f /etc/nginx/sites-enabled/ai-influencer.tripc.ai
sudo cp deploy/nginx/ai-influencer.reverse-proxy.conf /etc/nginx/sites-available/ai-influencer.conf
sudo ln -sf /etc/nginx/sites-available/ai-influencer.conf /etc/nginx/sites-enabled/ai-influencer.conf
sudo nginx -t
sudo systemctl reload nginx
```

Verify cert renewal still works:

```bash
sudo certbot renew --dry-run
```

## Step 8: Deploy The Full Stack

Run the checked-in deploy helper:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/deploy-production.sh
```

This starts:

- Postgres
- Temporal
- Redis
- OpenClaw
- OpenClaw control UI
- ChatGPT connector
- Postiz
- GrowChief
- backend
- worker
- frontend

## Step 9: Apply The Connector Migration

```bash
cd /opt/ai-influencer/repo
./deploy/vps/apply-chatgpt-connector-migration.sh
```

## Step 10: Run Smoke Checks

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/healthcheck.sh
curl -I https://ai-influencer.tripc.ai
curl https://api.ai-influencer.tripc.ai/health
curl https://connector.ai-influencer.tripc.ai/health
```

If anything is unhealthy, inspect logs:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production docker compose -f docker-compose.production.yml ps
PROJECT_ENV_FILE=./Project/.env.production docker compose -f docker-compose.production.yml logs -f backend openclaw chatgpt_connector temporal_worker frontend
```

On the current VPS, it is also worth verifying the host-level state changed from the old static-site baseline:

```bash
sudo ss -tlnp
sudo systemctl status nginx ssh postfix --no-pager
```

Expected direction after deployment:

- `80` and `443` should be open publicly through nginx
- app containers should be bound to `127.0.0.1` only
- postfix can remain localhost-only

## Step 11: Access OpenClaw And Other Private UIs

These services are intentionally not public.

Create an SSH tunnel from your local machine:

```bash
ssh -L 8081:127.0.0.1:8081 -L 8080:127.0.0.1:8080 -L 3100:127.0.0.1:3100 -L 3200:127.0.0.1:3200 deploy@<YOUR_VPS_PUBLIC_IP>
```

Then open locally:

- `http://localhost:8081` -> OpenClaw Control UI
- `http://localhost:8080` -> Temporal UI
- `http://localhost:3100` -> Postiz
- `http://localhost:3200` -> GrowChief

## Step 12: Manual External Setup After The Server Is Live

Still required outside the repo:

1. Register the ChatGPT/OpenAI connector with:
   - public URL: `https://connector.ai-influencer.tripc.ai`
   - callback URL: `https://connector.ai-influencer.tripc.ai/oauth/callback`
2. Configure provider webhooks:
   - Postiz -> `https://api.ai-influencer.tripc.ai/api/webhooks/postiz`
   - GrowChief -> `https://api.ai-influencer.tripc.ai/api/webhooks/growchief`
3. Run one full workflow with real credentials and verify:
   - Telegram approval
   - media generation
   - publish
   - webhook reconciliation
   - dashboard updates
4. Run one real Facebook onboarding flow with the proxy-backed account setup

## Troubleshooting The Missing Subdomains

If `api.ai-influencer.tripc.ai` or `connector.ai-influencer.tripc.ai` do not resolve:

- confirm the DNS zone is really hosted where you are editing it
- confirm you created `A` records, not CNAMEs to a hostname that does not resolve
- confirm the records point to the VPS public IP, not a private IP
- wait for TTL and resolver cache to expire
- test against a public resolver:

```bash
nslookup api.ai-influencer.tripc.ai 1.1.1.1
nslookup connector.ai-influencer.tripc.ai 1.1.1.1
```

If `ai-influencer.tripc.ai` already works but the other two do not, that almost always means the new `A` records were never created in the active DNS zone, or were created in the wrong zone/provider account.

If the records resolve publicly but Certbot still fails:

- make sure ports `80` and `443` are open in any cloud firewall or provider firewall
- make sure nginx is stopped during the `certbot certonly --standalone` step
- make sure no other service is already listening on port `80`

If nginx fails after you swap the config:

- restore the backup site file you created from `/etc/nginx/sites-available/ai-influencer.tripc.ai.bak.*`
- run `sudo nginx -t`
- reload nginx only after config test passes

## Routine Commands

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
