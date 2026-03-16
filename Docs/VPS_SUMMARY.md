# AWS VPS Configuration - Executive Summary

## Quick Reference

**Project:** AI Influencer Factory  
**Analysis Date:** March 11, 2026  
**Recommended Instance:** AWS EC2 c6i.4xlarge  
**Estimated Monthly Cost:** $544-$700 (total infrastructure)

---

## 📋 Top Recommendation

### AWS EC2 c6i.4xlarge (Compute Optimized)

| Specification    | Value                                  | Justification                                                           |
| ---------------- | -------------------------------------- | ----------------------------------------------------------------------- |
| **vCPUs**        | 16                                     | Sufficient for 10+ concurrent browser sessions + Temporal orchestration |
| **Memory**       | 32 GB                                  | Handles 5-7 AI personas with browser automation comfortably             |
| **Storage**      | 100 GB GP3 SSD                         | Docker images, databases, browser profiles, logs                        |
| **Network**      | 12.5 Gbps                              | Critical for high-volume proxy-routed traffic                           |
| **Monthly Cost** | $544 (on-demand) <br> $326 (1-year RI) | Best price/performance ratio                                            |

**Supports:**

- ✅ 5-7 AI influencer personas simultaneously
- ✅ 10-25 stealth engagement accounts
- ✅ 30-80 posts per day
- ✅ 8-12 concurrent browser sessions
- ✅ 24/7 stable operation with growth headroom

---

## 📦 What Runs on This VPS

The AI Influencer Factory consists of **10 containerized services**:

### Core Services

1. **Temporal Server** - Workflow orchestration engine (3 vCPU, 4GB)
2. **Temporal Worker** - Activity execution (3 vCPU, 4GB)
3. **PostgreSQL** - Primary database (2 vCPU, 4GB)
4. **Redis** - Caching and queues (1 vCPU, 1GB)

### AI & Automation

5. **OpenClaw** - AI cognitive engine + browser automation (6 vCPU, 12GB)
6. **OpenClaw Mission Control** - Agent orchestration (1 vCPU, 2GB)
7. **GrowChief** - Engagement syndicate manager (3 vCPU, 6GB)

### Application Layer

8. **Python Backend (FastAPI)** - REST API server (2 vCPU, 2GB)
9. **Next.js Frontend** - Web dashboard (1 vCPU, 2GB)
10. **Postiz** - OAuth publishing service (1 vCPU, 2GB)

**Total Resource Requirements:** 23 vCPU limits (14 vCPU reserved), 39GB limits (25GB reserved)

---

## 💰 Complete Cost Breakdown

### Infrastructure Costs (Monthly)

| Component                   | Cost     | Notes                                  |
| --------------------------- | -------- | -------------------------------------- |
| **AWS EC2 (c6i.4xlarge)**   | $544     | On-demand pricing                      |
| **EBS Storage (100GB GP3)** | $8       | SSD with 3,000 IOPS                    |
| **Data Transfer (500GB)**   | $45      | Typical monthly usage                  |
| **Elastic IP**              | $0       | Free when attached to running instance |
| **AWS SUBTOTAL**            | **$597** |                                        |

### External Services (Monthly)

| Service                | Cost    | Purpose                    |
| ---------------------- | ------- | -------------------------- |
| **Supabase Pro**       | $25     | PostgreSQL database + Auth |
| **IPRoyal Proxies**    | $15     | Residential IP rotation    |
| **fal.ai (Media Gen)** | $20     | Image/video generation     |
| **PlayHT (Audio)**     | $39     | Voice synthesis            |
| **SERVICES SUBTOTAL**  | **$99** |                            |

### **GRAND TOTAL: ~$696/month**

---

## 💡 Cost Optimization Strategies

### 1. Reserved Instances (Recommended)

**1-Year Commitment:**

- Saves ~40% on EC2 cost
- **New EC2 Cost:** $326/month (was $544)
- **New Total:** $478/month (~31% overall savings)

**3-Year Commitment:**

- Saves ~60% on EC2 cost
- **New EC2 Cost:** $218/month (was $544)
- **New Total:** $370/month (~47% overall savings)

### 2. Optimized Configuration

**For 1-2 personas only:** Use c6i.2xlarge instead

- **Savings:** $272/month vs $544/month
- **Trade-off:** Limited to 2-4 concurrent browser sessions

### 3. Service Optimization

- **Self-host Supabase:** Save $25/month (requires additional 4GB RAM)
- **Bundle AI API calls:** Negotiate volume discounts with fal.ai/PlayHT
- **Optimize proxy usage:** Use proxies only for engagement, not content generation

---

## 📊 Performance Benchmarks

Based on the c6i.4xlarge configuration:

| Metric                       | Expected Performance              |
| ---------------------------- | --------------------------------- |
| **Concurrent AI Personas**   | 5-7 (optimal), up to 10 (peak)    |
| **Stealth Browser Sessions** | 8-12 simultaneous                 |
| **Content Generation**       | 10 pieces in parallel             |
| **Daily Post Volume**        | 30-80 posts across all personas   |
| **API Response Time**        | <100ms (average)                  |
| **Temporal Workflows**       | 20+ active workflows              |
| **Database Connections**     | 100+ concurrent                   |
| **Uptime Target**            | 99.9% (43 minutes downtime/month) |

---

## 🚀 Deployment Timeline

### Phase 1: Initial Setup (Day 1)

- Launch EC2 instance
- Attach Elastic IP
- Run setup script (automated)
- **Duration:** 1-2 hours

### Phase 2: Application Deployment (Day 1-2)

- Clone repository
- Configure environment variables
- Start Docker containers
- **Duration:** 2-4 hours

### Phase 3: Testing & Validation (Day 2-3)

- Test all service endpoints
- Configure first AI persona
- Generate test content
- **Duration:** 4-8 hours

### Phase 4: Production Launch (Day 3+)

- Connect social media accounts
- Set up monitoring and alerts
- Deploy first workflows
- **Duration:** Ongoing

**Total Time to Production:** 2-3 days

---

## ⚠️ Critical Considerations

### Must-Haves Before Deployment

1. **API Keys Ready:**
   - OpenAI API key (GPT-4o)
   - Anthropic API key (Claude 3.5)
   - fal.ai API key
   - Supabase credentials
   - IPRoyal proxy credentials

2. **AWS Prerequisites:**
   - SSH key pair created
   - Security groups configured
   - Elastic IP allocated

3. **External Services:**
   - Supabase project created
   - Cloudflare R2 bucket set up
   - Telegram bot created (optional)

### Security Checklist

- [ ] SSH key-based authentication only (disable passwords)
- [ ] Security groups restrict access to your IP
- [ ] PostgreSQL password changed from default
- [ ] All API keys stored securely in .env.local
- [ ] UFW firewall enabled
- [ ] CloudWatch alarms configured
- [ ] Automated backups enabled

---

## 🎯 Use Case Fit Analysis

### ✅ Perfect For:

- **Solo Founders:** Building an AI influencer brand
- **Small Agencies:** Managing 3-7 client brands
- **Content Creators:** Automating multi-platform distribution
- **Marketing Teams:** Coordinating cross-channel campaigns

### ⚠️ Potential Limitations:

- **Large Agencies (15+ brands):** Consider c6i.8xlarge or horizontal scaling
- **Ultra-High Volume (200+ posts/day):** May need multiple instances
- **Real-Time Video Processing:** External GPU services recommended (Replicate, RunPod)

### ❌ Not Suitable For:

- **Individual posts (no automation needed):** Manual posting is more cost-effective
- **Strict compliance industries:** May require dedicated tenancy (+$2,000/month)
- **Video editing heavy workflows:** Local GPU workstation recommended

---

## 📈 Scaling Roadmap

### Current Capacity (c6i.4xlarge)

- **Personas:** 5-7
- **Posts/Day:** 30-80
- **Engagement Accounts:** 10-25

### Growth Path 1: Vertical Scaling

**When to upgrade to c6i.8xlarge:**

- Managing 8+ personas
- 100+ posts/day
- 30+ engagement accounts
- **Cost Impact:** +$544/month (double EC2 cost)

### Growth Path 2: Horizontal Scaling

**When to add worker instances:**

- Need fault isolation
- Specific components bottlenecked
- Using Spot Instances for cost savings
- **Cost Impact:** +$272-544/month per worker

### Growth Path 3: Hybrid Architecture

**When you reach 15+ personas:**

- Primary: c6i.4xlarge (Temporal, DB, API)
- Workers: 2x c6i.2xlarge Spot ($50-100/month instead of $272)
- **Total Cost:** ~$650/month AWS (40% savings vs single c6i.8xlarge)

---

## 📚 Complete Documentation Index

This analysis generated the following comprehensive documentation:

1. **[AWS_VPS_CONFIGURATION.md](AWS_VPS_CONFIGURATION.md)** (Main Document)
   - Detailed technical specifications
   - Resource allocation breakdown
   - Performance optimization guides
   - Monitoring recommendations

2. **[INSTANCE_COMPARISON.md](INSTANCE_COMPARISON.md)** (Decision Matrix)
   - Side-by-side instance comparisons
   - Use case fit analysis
   - Regional pricing differences
   - Cost analysis by scenario

3. **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** (Step-by-Step)
   - Pre-deployment checklist
   - Automated setup instructions
   - Service verification procedures
   - Troubleshooting guide

4. **[docker-compose.production.yml](docker-compose.production.yml)** (Configuration)
   - Resource limits for each service
   - PostgreSQL optimization settings
   - Health checks and restart policies
   - Production-ready settings

5. **[setup-vps.sh](setup-vps.sh)** (Automation Script)
   - Automated system setup
   - Docker installation
   - Firewall configuration
   - Swap and kernel optimization

6. **[monitor.sh](monitor.sh)** (Monitoring Tool)
   - Real-time resource monitoring
   - Container health checks
   - Error detection
   - Network statistics

---

## 🎓 Quick Start Commands

### Launch EC2 Instance (AWS CLI)

```bash
aws ec2 run-instances \
  --image-id ami-0c7217cdde317cfec \
  --instance-type c6i.4xlarge \
  --key-name YourKeyPair \
  --security-group-ids sg-xxxxxxxxx \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":100,"VolumeType":"gp3","Iops":3000}}]'
```

### Connect and Setup

```bash
ssh -i your-key.pem ubuntu@YOUR_ELASTIC_IP
sudo bash setup-vps.sh
```

### Deploy Application

```bash
cd /opt/ai-influencer
git clone https://github.com/YourUsername/AI-Influencer-TripC.git
cd AI-Influencer-TripC/Project
cp .env.example .env.local
nano .env.local  # Add your API keys
cd ..
docker compose -f docker-compose.production.yml up -d
```

### Monitor System

```bash
./monitor.sh --continuous --interval 5
```

---

## 🤝 Support Resources

### AWS Documentation

- EC2 Instance Types: https://aws.amazon.com/ec2/instance-types/
- EBS Pricing: https://aws.amazon.com/ebs/pricing/
- Cost Calculator: https://calculator.aws/

### Project Documentation

- Technical Blueprint: [AI Influencer Factory Technical Blueprint.md](AI%20Influencer%20Factory%20Technical%20Blueprint.md)
- Project Structure: [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
- Getting Started: [GETTING_STARTED.md](GETTING_STARTED.md)

### External Services

- Temporal.io Docs: https://docs.temporal.io/
- OpenClaw Docs: https://openclaw.com/docs
- Supabase Docs: https://supabase.com/docs

---

## ✅ Final Verdict

**For 90% of users, the ideal configuration is:**

```
┌─────────────────────────────────────────────┐
│  AWS EC2 c6i.4xlarge                        │
│  • 16 vCPU, 32 GB RAM                       │
│  • 100 GB GP3 SSD (3,000 IOPS)             │
│  • $544/month on-demand                     │
│  • $326/month with 1-year RI (~40% off)    │
│                                             │
│  Supports: 5-7 AI personas                  │
│  Posts: 30-80/day                           │
│  Growth headroom: 2x capacity available    │
└─────────────────────────────────────────────┘
```

This configuration provides:

- ✅ Production-ready reliability
- ✅ Comfortable performance headroom
- ✅ Best price-to-performance ratio
- ✅ Room to grow without migration
- ✅ 24/7 stable operation

**Estimated ROI:** If generating $3-5 per post in value, break-even is at 20-25 posts/day. Capacity is 30-80 posts/day.

---

## 📞 Next Steps

1. **Review** [INSTANCE_COMPARISON.md](INSTANCE_COMPARISON.md) to confirm c6i.4xlarge fits your use case
2. **Gather** all required API keys and credentials
3. **Launch** EC2 instance using [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
4. **Deploy** application using provided docker-compose.production.yml
5. **Monitor** system health with monitor.sh
6. **Scale** as needed following the documented growth paths

---

**Document Version:** 1.0  
**Confidence Level:** High (based on comprehensive codebase analysis)  
**Last Updated:** March 11, 2026  
**Analysis Methodology:** Static code analysis, docker-compose inspection, service dependency mapping
