#!/usr/bin/env bash

##############################################################################
# AI Influencer Factory VPS bootstrap
#
# Target host:
# - Ubuntu 22.04+
# - Docker Compose deployment
# - Host nginx terminating TLS and proxying only 3 public entrypoints
#
# Usage:
#   sudo bash setup-vps.sh
##############################################################################

set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this script as root or with sudo."
    exit 1
fi

APP_ROOT="/opt/ai-influencer"
BACKUP_ROOT="${APP_ROOT}/backups"
DATA_ROOT="/mnt/data/ai-influencer"

echo "[1/9] Updating system packages..."
apt-get update
apt-get upgrade -y

echo "[2/9] Installing base packages..."
apt-get install -y \
    ca-certificates \
    certbot \
    curl \
    git \
    gnupg \
    htop \
    jq \
    nginx \
    python3-certbot-nginx \
    software-properties-common \
    ufw \
    unzip \
    vim

echo "[3/9] Installing Docker..."
apt-get remove -y docker docker-engine docker.io containerd runc || true
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --batch --yes --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker

echo "[4/9] Configuring Docker logging..."
mkdir -p /etc/docker
cat >/etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "live-restore": true
}
EOF
systemctl restart docker

echo "[5/9] Configuring firewall..."
ufw --force enable
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw reload

echo "[6/9] Hardening SSH defaults..."
if grep -q '^#\?PermitRootLogin' /etc/ssh/sshd_config; then
    sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
else
    echo 'PermitRootLogin prohibit-password' >> /etc/ssh/sshd_config
fi
systemctl restart ssh

echo "[7/9] Creating application directories..."
mkdir -p "${APP_ROOT}"/{logs,releases}
mkdir -p "${BACKUP_ROOT}"/{postgres,browser_profiles}
mkdir -p "${DATA_ROOT}"/{postgres,redis,openclaw,browser_profiles}

echo "[8/9] Enabling nginx..."
rm -f /etc/nginx/sites-enabled/default
systemctl enable --now nginx

echo "[9/9] Bootstrap complete."
echo
echo "Next steps:"
echo "1. Clone the repo into ${APP_ROOT}/repo"
echo "2. Copy Project/.env.example to Project/.env.production and fill in real secrets"
echo "3. Copy either deploy/nginx/ai-influencer.reverse-proxy.conf or deploy/nginx/ai-influencer.single-domain.conf into /etc/nginx/sites-available/"
echo "4. Link the nginx config, run nginx -t, and reload nginx"
echo "5. Run deploy/vps/deploy-production.sh from the repo root"
echo "6. Run deploy/vps/apply-chatgpt-connector-migration.sh"
echo "7. Optionally install the weekly Docker cleanup timer with sudo ./deploy/vps/install-docker-maintenance-timer.sh"
echo "8. Run deploy/vps/healthcheck.sh"
