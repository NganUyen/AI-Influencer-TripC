# AWS VPS Deployment Quick Start Guide

## Pre-Deployment Checklist

### 1. AWS Account Setup

- [ ] AWS account created and verified
- [ ] IAM user with EC2 full access created
- [ ] AWS CLI installed locally (optional)
- [ ] SSH key pair generated in AWS EC2 console

### 2. Required API Keys & Credentials

Gather these before deployment:

- [ ] Supabase Project URL and Keys
  - `NEXT_PUBLIC_SUPABASE_URL`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
  - `SUPABASE_SERVICE_ROLE_KEY`

- [ ] AI Model API Keys
  - `OPENAI_API_KEY` (GPT-4o for reasoning)
  - `ANTHROPIC_API_KEY` (Claude 3.5 Sonnet)

- [ ] Media Generation
  - `FAL_AI_API_KEY` (Images/Videos via fal.ai)
  - `PLAYHT_API_KEY` (Voice synthesis)

- [ ] Cloud Storage (Cloudflare R2)
  - `R2_ACCOUNT_ID`
  - `R2_ACCESS_KEY_ID`
  - `R2_SECRET_ACCESS_KEY`
  - `R2_BUCKET_NAME`
  - `R2_PUBLIC_URL`

- [ ] Proxy Service (IPRoyal)
  - `PROXY_SERVER` (e.g., `geo.iproyal.com:12321`)
  - `PROXY_USERNAME`
  - `PROXY_PASSWORD`

- [ ] Telegram Bot (Optional)
  - `TELEGRAM_BOT_TOKEN`

---

## Step 1: Launch EC2 Instance

### Via AWS Console

1. Go to **EC2 Dashboard** → **Launch Instance**

2. **Configure Instance:**
   - **Name:** `ai-influencer-production`
   - **AMI:** Ubuntu Server 22.04 LTS (64-bit x86)
   - **Instance Type:** `c6i.4xlarge` (16 vCPU, 32 GB RAM)
   - **Key Pair:** Select existing or create new
   - **Firewall (Security Group):**
     - SSH: Port 22 (Your IP only)
     - HTTP: Port 80 (0.0.0.0/0)
     - HTTPS: Port 443 (0.0.0.0/0)
     - Custom TCP: 3000 (0.0.0.0/0) - Frontend
     - Custom TCP: 8000 (Your IP only) - Backend API
     - Custom TCP: 8080 (Your IP only) - Temporal UI

3. **Configure Storage:**
   - **Root Volume:** 100 GB, GP3 SSD
   - **IOPS:** 3000
   - **Throughput:** 125 MB/s

4. **Advanced Details:**
   - Enable: **Detailed CloudWatch monitoring**
   - Enable: **Termination protection**

5. Click **Launch Instance**

### Via AWS CLI

```bash
aws ec2 run-instances \
  --image-id ami-0c7217cdde317cfec \
  --instance-type c6i.4xlarge \
  --key-name YourKeyPair \
  --security-group-ids sg-xxxxxxxxx \
  --subnet-id subnet-xxxxxxxxx \
  --block-device-mappings '[{
    "DeviceName": "/dev/sda1",
    "Ebs": {
      "VolumeSize": 100,
      "VolumeType": "gp3",
      "Iops": 3000,
      "Throughput": 125,
      "DeleteOnTermination": true
    }
  }]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=ai-influencer-production}]'
```

---

## Step 2: Allocate and Attach Elastic IP

```bash
# Allocate Elastic IP
aws ec2 allocate-address --domain vpc

# Note the AllocationId and public IP address

# Associate with instance (replace IDs)
aws ec2 associate-address \
  --instance-id i-1234567890abcdef0 \
  --allocation-id eipalloc-12345678
```

**Important:** Update your DNS records to point to this Elastic IP.

---

## Step 3: Connect to Instance

```bash
# Update permissions on your private key
chmod 400 ~/path/to/your-key.pem

# Connect via SSH
ssh -i ~/path/to/your-key.pem ubuntu@YOUR_ELASTIC_IP
```

---

## Step 4: Run Setup Script

```bash
# Switch to root
sudo su

# Download setup script
wget https://raw.githubusercontent.com/YourUsername/AI-Influencer-TripC/main/setup-vps.sh

# Make executable
chmod +x setup-vps.sh

# Run setup
./setup-vps.sh
```

The script will:

- Update system packages
- Install Docker and Docker Compose
- Configure swap space (8GB)
- Optimize kernel parameters
- Set up firewall
- Create application directories

**Expected Duration:** 5-10 minutes

---

## Step 5: Deploy Application

### 5.1 Clone Repository

```bash
cd /opt/ai-influencer
git clone https://github.com/YourUsername/AI-Influencer-TripC.git
cd AI-Influencer-TripC
```

### 5.2 Configure Environment Variables

```bash
cd Project
cp .env.example .env.local
nano .env.local
```

**Paste your API keys and credentials** (from Pre-Deployment Checklist):

```env
# Database
POSTGRES_PASSWORD=your_secure_password_here

# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# AI APIs
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...

# Media Generation
FAL_AI_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
PLAYHT_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Cloud Storage (Cloudflare R2)
R2_ACCOUNT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
R2_ACCESS_KEY_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
R2_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
R2_BUCKET_NAME=ai-influencer-media
R2_PUBLIC_URL=https://media.yourdomain.com

# Proxies (IPRoyal)
PROXY_SERVER=geo.iproyal.com:12321
PROXY_USERNAME=your_username
PROXY_PASSWORD=your_password

# Telegram
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# API URL (use your Elastic IP or domain)
API_URL=http://YOUR_ELASTIC_IP:8000
```

Save and exit (`Ctrl+X`, `Y`, `Enter`)

### 5.3 Initialize Supabase Database

1. Go to your Supabase Dashboard → SQL Editor
2. Copy contents of `Project/supabase/schema.sql`
3. Paste and run in SQL Editor
4. (Optional) Run `Project/supabase/seed.sql` for sample data

### 5.4 Build and Start Services

```bash
cd /opt/ai-influencer/AI-Influencer-TripC

# Pull required Docker images
docker compose -f docker-compose.production.yml pull

# Build custom images (backend, frontend)
docker compose -f docker-compose.production.yml build

# Start all services in detached mode
docker compose -f docker-compose.production.yml up -d

# Check status
docker compose -f docker-compose.production.yml ps
```

**Expected Output:**

```
NAME                             STATUS    PORTS
ai-influencer-backend            Running   0.0.0.0:8000->8000/tcp
ai-influencer-frontend           Running   0.0.0.0:3000->3000/tcp
ai-influencer-growchief          Running   0.0.0.0:3200->3200/tcp
ai-influencer-openclaw           Running   0.0.0.0:8082->8080/tcp
ai-influencer-postgres           Running   0.0.0.0:5432->5432/tcp
ai-influencer-postiz             Running   0.0.0.0:3100->3100/tcp
ai-influencer-redis              Running   0.0.0.0:6379->6379/tcp
ai-influencer-temporal           Running   0.0.0.0:7233->7233/tcp, 0.0.0.0:8080->8080/tcp
ai-influencer-temporal-worker    Running
```

---

## Step 6: Verify Deployment

### 6.1 Check Service Health

```bash
# Backend API health
curl http://localhost:8000/health

# Expected output:
# {"status":"healthy","temporal":"connected"}
```

### 6.2 View Logs

```bash
# All services
docker compose -f docker-compose.production.yml logs -f

# Specific service
docker compose -f docker-compose.production.yml logs -f backend
docker compose -f docker-compose.production.yml logs -f temporal_worker
```

### 6.3 Access Web Interfaces

Open in your browser:

- **Frontend Dashboard:** `http://YOUR_ELASTIC_IP:3000`
- **Backend API Docs:** `http://YOUR_ELASTIC_IP:8000/docs`
- **Temporal UI:** `http://YOUR_ELASTIC_IP:8080`

---

## Step 7: Set Up HTTPS (Optional but Recommended)

### Using Nginx + Let's Encrypt

```bash
# Install Nginx
sudo apt-get install -y nginx certbot python3-certbot-nginx

# Configure Nginx reverse proxy
sudo nano /etc/nginx/sites-available/ai-influencer

# Paste configuration:
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Enable site
sudo ln -s /etc/nginx/sites-available/ai-influencer /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Obtain SSL certificate
sudo certbot --nginx -d yourdomain.com
```

---

## Step 8: Enable Automated Backups

### PostgreSQL Backup Script

Create `/opt/ai-influencer/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/opt/ai-influencer/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Backup PostgreSQL
docker exec ai-influencer-postgres pg_dumpall -U postgres | gzip > "$BACKUP_DIR/postgres_$TIMESTAMP.sql.gz"

# Keep only last 7 days
find "$BACKUP_DIR" -name "postgres_*.sql.gz" -mtime +7 -delete

echo "Backup completed: postgres_$TIMESTAMP.sql.gz"
```

```bash
chmod +x /opt/ai-influencer/backup.sh

# Add to crontab (daily at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/ai-influencer/backup.sh") | crontab -
```

### AWS EBS Snapshots

```bash
# Create snapshot via AWS CLI (run from local machine)
aws ec2 create-snapshot \
  --volume-id vol-xxxxxxxxxxxxxxxxx \
  --description "AI Influencer Daily Backup $(date +%Y-%m-%d)" \
  --tag-specifications 'ResourceType=snapshot,Tags=[{Key=Name,Value=ai-influencer-backup}]'
```

**Recommendation:** Use AWS Data Lifecycle Manager for automated daily snapshots.

---

## Step 9: Monitoring Setup

### Install Monitoring Script

Create `/opt/ai-influencer/monitor.sh`:

```bash
#!/bin/bash
# See monitor.sh in repository
```

```bash
chmod +x /opt/ai-influencer/monitor.sh
./monitor.sh
```

### CloudWatch Alarms

Set up in AWS Console:

1. **CPU Utilization > 85%** for 10 minutes
2. **Memory Utilization > 90%** for 5 minutes
3. **Disk Space < 10%** free
4. **Status Check Failed** (any)

---

## Common Commands

### Service Management

```bash
# View status
docker compose -f docker-compose.production.yml ps

# Stop all services
docker compose -f docker-compose.production.yml stop

# Start all services
docker compose -f docker-compose.production.yml start

# Restart specific service
docker compose -f docker-compose.production.yml restart backend

# View logs
docker compose -f docker-compose.production.yml logs -f [service-name]

# Execute command in container
docker compose -f docker-compose.production.yml exec backend bash
```

### System Health

```bash
# Resource usage
htop

# Disk usage
df -h
ncdu /

# Network connections
netstat -tulpn

# Docker stats
docker stats

# Check swap usage
free -h
```

### Update Application

```bash
cd /opt/ai-influencer/AI-Influencer-TripC
git pull origin main
docker compose -f docker-compose.production.yml build
docker compose -f docker-compose.production.yml up -d
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker compose -f docker-compose.production.yml logs [service-name]

# Verify environment variables
docker compose -f docker-compose.production.yml config

# Check disk space
df -h
```

### High Memory Usage

```bash
# Check per-container usage
docker stats

# Restart memory-intensive services
docker compose -f docker-compose.production.yml restart openclaw growchief
```

### Browser Automation Failing

```bash
# Check browser profiles directory
ls -lah /mnt/data/browser_profiles

# Check proxy connectivity
docker compose -f docker-compose.production.yml exec backend ping geo.iproyal.com

# Restart browser-dependent services
docker compose -f docker-compose.production.yml restart openclaw growchief
```

---

## Cost Tracking

### Monthly Breakdown (c6i.4xlarge On-Demand)

| Component                  | Cost            |
| -------------------------- | --------------- |
| EC2 Instance (c6i.4xlarge) | ~$544/month     |
| EBS Storage (100 GB GP3)   | ~$8/month       |
| Elastic IP (active)        | $0              |
| Data Transfer (est. 500GB) | ~$45/month      |
| **Total AWS**              | **~$597/month** |
| Supabase Pro               | $25/month       |
| IPRoyal Proxies            | $15/month       |
| fal.ai (Media)             | $20/month       |
| PlayHT (Audio)             | $39/month       |
| **Grand Total**            | **~$696/month** |

### Savings Options

- **1-year Reserved Instance:** Save ~40% → **$358/month AWS**
- **3-year Reserved Instance:** Save ~60% → **$218/month AWS**

---

## Next Steps

1. **Test Content Generation:**
   - Create AI persona in dashboard
   - Trigger weekly strategy generation
   - Approve via Telegram
   - Monitor workflow execution in Temporal UI

2. **Configure Social Accounts:**
   - Connect platforms via Postiz
   - Add stealth accounts to GrowChief
   - Test posting workflow

3. **Set Up Analytics:**
   - Configure engagement tracking
   - Set up custom CloudWatch dashboards
   - Enable Temporal workflow metrics

4. **Security Hardening:**
   - Disable password authentication (SSH keys only)
   - Enable AWS GuardDuty
   - Set up AWS WAF for frontend
   - Regular security updates: `apt-get update && apt-get upgrade`

---

**Documentation Version:** 1.0  
**Last Updated:** March 11, 2026  
**Support:** Check logs and GitHub issues
