#!/bin/bash

##############################################################################
# AWS EC2 VPS Setup Script for AI Influencer Factory
# Instance: c6i.4xlarge (16 vCPU, 32 GB RAM, Ubuntu 22.04 LTS)
#
# This script automates the initial setup of your AWS EC2 instance
# Run this script as root or with sudo privileges
#
# Usage: sudo bash setup-vps.sh
##############################################################################

set -e  # Exit on error

echo "=================================================="
echo "  AI Influencer Factory - AWS VPS Setup"
echo "=================================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
   echo -e "${RED}Error: This script must be run as root or with sudo${NC}"
   exit 1
fi

echo -e "${GREEN}[1/10] Updating system packages...${NC}"
apt-get update
apt-get upgrade -y

echo -e "${GREEN}[2/10] Installing essential packages...${NC}"
apt-get install -y \
    curl \
    wget \
    git \
    unzip \
    htop \
    vim \
    build-essential \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release

echo -e "${GREEN}[3/10] Installing Docker...${NC}"
# Remove old Docker versions
apt-get remove -y docker docker-engine docker.io containerd runc || true

# Add Docker's official GPG key
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# Set up Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start and enable Docker
systemctl start docker
systemctl enable docker

echo -e "${GREEN}[4/10] Configuring Docker daemon...${NC}"
# Create Docker daemon config for performance optimization
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "live-restore": true,
  "max-concurrent-downloads": 10,
  "max-concurrent-uploads": 5
}
EOF

systemctl restart docker

echo -e "${GREEN}[5/10] Installing Docker Compose...${NC}"
# Docker Compose v2 is already included with Docker Engine via plugin
docker compose version

echo -e "${GREEN}[6/10] Configuring swap space (8GB)...${NC}"
# Create swap file for memory stability
if [ ! -f /swapfile ]; then
    fallocate -l 8G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    
    # Set swappiness to 10 (prefer RAM over swap)
    sysctl vm.swappiness=10
    echo 'vm.swappiness=10' >> /etc/sysctl.conf
    
    echo "Swap configured successfully"
else
    echo "Swap file already exists, skipping..."
fi

echo -e "${GREEN}[7/10] Optimizing system parameters...${NC}"
# Increase file descriptor limits for browser automation
cat >> /etc/security/limits.conf <<EOF
* soft nofile 65536
* hard nofile 65536
* soft nproc 32768
* hard nproc 32768
EOF

# Kernel network optimizations
cat >> /etc/sysctl.conf <<EOF
# Network optimizations for high-concurrency proxy traffic
net.core.somaxconn = 4096
net.ipv4.tcp_max_syn_backlog = 8192
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_keepalive_probes = 5
net.ipv4.tcp_keepalive_intvl = 15

# Memory management
vm.overcommit_memory = 1
vm.max_map_count = 262144
EOF

sysctl -p

echo -e "${GREEN}[8/10] Setting up firewall (UFW)...${NC}"
# Configure UFW firewall
ufw --force enable
ufw default deny incoming
ufw default allow outgoing

# Allow SSH
ufw allow 22/tcp comment 'SSH'

# Allow HTTP/HTTPS
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'

# Allow application ports (accessible from anywhere for now - restrict as needed)
ufw allow 3000/tcp comment 'Next.js Frontend'
ufw allow 8000/tcp comment 'FastAPI Backend'
ufw allow 8080/tcp comment 'Temporal UI'

ufw reload
ufw status

echo -e "${GREEN}[9/10] Installing monitoring tools...${NC}"
# Install system monitoring tools
apt-get install -y sysstat ncdu iotop nethogs

echo -e "${GREEN}[10/10] Creating application directory structure...${NC}"
# Create application directories
mkdir -p /opt/ai-influencer
mkdir -p /opt/ai-influencer/logs
mkdir -p /opt/ai-influencer/backups
mkdir -p /mnt/data/postgres_data
mkdir -p /mnt/data/browser_profiles
mkdir -p /mnt/data/media_cache

# Set permissions
chown -R 1000:1000 /opt/ai-influencer
chmod -R 755 /opt/ai-influencer

echo ""
echo "=================================================="
echo -e "${GREEN}✓ VPS Setup Complete!${NC}"
echo "=================================================="
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. Clone your repository:"
echo "   cd /opt/ai-influencer"
echo "   git clone https://github.com/YourUsername/AI-Influencer-TripC.git"
echo ""
echo "2. Create and configure .env file:"
echo "   cd AI-Influencer-TripC/Project"
echo "   cp .env.example .env.local"
echo "   nano .env.local  # Add your API keys"
echo ""
echo "3. Start the services:"
echo "   cd /opt/ai-influencer/AI-Influencer-TripC"
echo "   docker compose -f docker-compose.production.yml up -d"
echo ""
echo "4. Check service status:"
echo "   docker compose -f docker-compose.production.yml ps"
echo ""
echo "5. View logs:"
echo "   docker compose -f docker-compose.production.yml logs -f"
echo ""
echo -e "${YELLOW}Important Security Notes:${NC}"
echo "- Update PostgreSQL password in .env.local"
echo "- Set up SSH key authentication and disable password login"
echo "- Configure AWS Security Groups to restrict access"
echo "- Set up CloudWatch monitoring and alarms"
echo "- Enable automatic EBS snapshots"
echo ""
echo -e "${GREEN}System Information:${NC}"
echo "  CPU Cores: $(nproc)"
echo "  Total RAM: $(free -h | awk '/^Mem:/ {print $2}')"
echo "  Swap Space: $(free -h | awk '/^Swap:/ {print $2}')"
echo "  Disk Space: $(df -h / | awk 'NR==2 {print $4}') available"
echo "  Docker Version: $(docker --version)"
echo "  Docker Compose Version: $(docker compose version)"
echo ""
echo "=================================================="
