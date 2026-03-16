# AWS VPS Configuration Recommendations for AI Influencer Factory

## Executive Summary

Based on comprehensive analysis of the AI Influencer Factory architecture, this document provides optimal AWS EC2 configurations for different deployment scenarios.

## Project Resource Analysis

### Services Running on VPS

The platform runs 10+ containerized services simultaneously:

1. **PostgreSQL** (15-alpine) - Primary database
2. **Temporal Server** - Workflow orchestration engine
3. **Temporal Worker** - Activity execution
4. **Redis** - Caching and queues
5. **OpenClaw** - AI cognitive engine + browser automation
6. **OpenClaw Mission Control** - Agent orchestration platform
7. **Postiz** - OAuth publishing service
8. **GrowChief** - Engagement syndicate manager
9. **Python Backend** (FastAPI) - REST API server
10. **Next.js Frontend** - Web dashboard

### Critical Resource Considerations

#### CPU-Intensive Operations

- **Browser Automation**: Multiple concurrent Camoufox (stealth browser) instances
- **Temporal Orchestration**: Workflow state management and execution
- **AI Processing**: OpenClaw agent coordination
- **Media Processing**: Image/video handling before upload to R2
- **Engagement Syndicate**: Multiple parallel browser sessions with unique IPs

#### Memory-Intensive Operations

- **Browser Profiles**: Each stealth browser instance requires 500MB-1GB per session
- **Temporal State**: Maintains workflow state and activity history
- **PostgreSQL**: Database connections, query buffers, and caching
- **OpenClaw**: In-memory agent state and browser contexts
- **GrowChief**: Multiple account profiles and session management

#### Storage Requirements

- Docker images: ~12-18 GB
- Database: 10-20 GB (growing)
- Browser profiles: 5-15 GB (multiple account fingerprints)
- Application logs: 3-5 GB
- Media cache: 5-10 GB (temporary before R2 upload)

---

## Recommended Configurations

### 🟢 Option 1: Production-Ready Configuration (RECOMMENDED)

**Instance Type:** `c6i.4xlarge` (Compute Optimized)

**Specifications:**

- **vCPUs:** 16
- **Memory:** 32 GB
- **Storage:** 100 GB GP3 SSD (3,000 IOPS, 125 MB/s throughput)
- **Network:** Up to 12.5 Gbps (critical for proxy-routed traffic)
- **Cost:** ~$544/month (~$0.68/hour)

**Why This Configuration:**

- ✅ Handles 5-10 concurrent browser sessions comfortably
- ✅ Sufficient headroom for Temporal's background polling
- ✅ Can run full engagement syndicate (10-20 stealth accounts)
- ✅ Stable performance under continuous 24/7 load
- ✅ Supports future scaling without migration

**Resource Allocation:**

```
Temporal Server:        3 vCPUs, 4 GB RAM
Temporal Worker:        3 vCPUs, 4 GB RAM
OpenClaw + Browsers:    6 vCPUs, 12 GB RAM
GrowChief + Browsers:   3 vCPUs, 6 GB RAM
Postiz:                 1 vCPU, 2 GB RAM
Backend (FastAPI):      2 vCPUs, 2 GB RAM
Frontend (Next.js):     1 vCPU, 2 GB RAM
PostgreSQL:             2 vCPUs, 4 GB RAM
Redis:                  1 vCPU, 1 GB RAM
System/Buffer:          2 vCPUs, 3 GB RAM
```

**Best For:**

- Running 2-5 AI influencer personas simultaneously
- 10-20 stealth engagement accounts
- Processing 30-50 posts per day
- Production workloads with SLA requirements

---

### 🟡 Option 2: Minimum Viable Configuration

**Instance Type:** `c6i.2xlarge` (Compute Optimized)

**Specifications:**

- **vCPUs:** 8
- **Memory:** 16 GB
- **Storage:** 80 GB GP3 SSD (3,000 IOPS)
- **Network:** Up to 12.5 Gbps
- **Cost:** ~$272/month (~$0.34/hour)

**Why This Configuration:**

- ✅ Meets the absolute minimum stated in Technical Blueprint
- ⚠️ Limited concurrent browser sessions (2-4 max)
- ⚠️ Requires aggressive resource limits in docker-compose.yml
- ⚠️ May experience performance degradation under peak load

**Resource Allocation:**

```
Temporal Server:        2 vCPUs, 2 GB RAM
Temporal Worker:        2 vCPUs, 2 GB RAM
OpenClaw + Browsers:    3 vCPUs, 6 GB RAM
GrowChief + Browsers:   2 vCPUs, 3 GB RAM
Backend + Postiz:       1 vCPU, 2 GB RAM
Frontend:               1 vCPU, 1 GB RAM
PostgreSQL:             1 vCPU, 2 GB RAM
Redis:                  1 vCPU, 512 MB RAM
System/Buffer:          1 vCPU, 1.5 GB RAM
```

**Best For:**

- Single AI influencer persona
- 3-5 stealth engagement accounts
- Development/testing environments
- Budget-constrained early-stage deployments

---

### 🔵 Option 3: Enterprise/Scale Configuration

**Instance Type:** `c6i.8xlarge` (Compute Optimized)

**Specifications:**

- **vCPUs:** 32
- **Memory:** 64 GB
- **Storage:** 200 GB GP3 SSD (4,000 IOPS, 250 MB/s throughput)
- **Network:** 12.5 Gbps
- **Cost:** ~$1,088/month (~$1.36/hour)

**Why This Configuration:**

- ✅ Enterprise-grade performance and reliability
- ✅ Supports 10+ AI influencer personas
- ✅ Can run 40-60 concurrent stealth browser sessions
- ✅ Significant headroom for traffic spikes
- ✅ Future-proof for additional features

**Best For:**

- Agency managing multiple client brands
- High-volume content operations (100+ posts/day)
- 30-50 stealth engagement accounts per influencer
- Multi-tenant SaaS deployment

---

## Storage Configuration Recommendations

### Root Volume (GP3 SSD)

**Recommended Specs:**

- **Size:** 100 GB (minimum), 200 GB (recommended)
- **IOPS:** 3,000 (baseline) to 16,000 (high-load)
- **Throughput:** 125 MB/s (baseline) to 250 MB/s (high-load)

**Rationale:**

- GP3 provides better price/performance than GP2
- Docker containers generate significant I/O from logs and browser cache
- Temporal requires consistent disk performance for state persistence

### Optional: Separate Data Volume

For production deployments, consider mounting a separate EBS volume:

```
/mnt/data (500 GB GP3)
  ├── /postgres_data      (PostgreSQL database)
  ├── /browser_profiles   (Stealth browser fingerprints)
  └── /media_cache        (Temporary media storage)
```

**Benefits:**

- Easier backup and snapshot management
- Isolate I/O impact from system volume
- Can be expanded independently

---

## Network Configuration

### Security Group Rules

**Inbound Rules:**

```
SSH (22)                    → Your IP only
HTTP (80)                   → 0.0.0.0/0 (frontend)
HTTPS (443)                 → 0.0.0.0/0 (frontend)
Backend API (8000)          → VPC only (internal)
Temporal gRPC (7233)        → VPC only (internal)
Temporal UI (8080)          → Your IP only (admin)
PostgreSQL (5432)           → VPC only (internal)
```

**Outbound Rules:**

```
All traffic                 → 0.0.0.0/0 (required for APIs/proxies)
```

### Elastic IP

**Strongly Recommended:**

- Attach an Elastic IP to prevent IP changes on restarts
- Critical for maintaining platform OAuth callbacks (Twitter, LinkedIn, etc.)
- Simplifies DNS management

### Enhanced Networking

Enable **Enhanced Networking (SR-IOV)** for:

- Lower latency
- Higher packets per second (PPS)
- Reduced jitter
- **Critical for proxy-routed traffic through IPRoyal**

---

## Performance Optimization Tips

### 1. Docker Resource Limits

Create `.env` file with resource constraints:

```env
# Memory limits (docker-compose.yml)
POSTGRES_MEM_LIMIT=4g
TEMPORAL_MEM_LIMIT=4g
OPENCLAW_MEM_LIMIT=12g
GROWCHIEF_MEM_LIMIT=6g
REDIS_MEM_LIMIT=1g
```

### 2. PostgreSQL Tuning

Add to `docker-compose.yml` PostgreSQL service:

```yaml
command: >
  postgres
  -c shared_buffers=2GB
  -c effective_cache_size=6GB
  -c maintenance_work_mem=512MB
  -c checkpoint_completion_target=0.9
  -c wal_buffers=16MB
  -c default_statistics_target=100
  -c random_page_cost=1.1
  -c effective_io_concurrency=200
  -c work_mem=10MB
  -c min_wal_size=1GB
  -c max_wal_size=4GB
  -c max_connections=200
```

### 3. Browser Session Management

Limit concurrent browsers in `config/settings.py`:

**For c6i.2xlarge (16GB):**

```python
MAX_CONCURRENT_BROWSERS = 4
BROWSER_MEMORY_LIMIT_MB = 800
```

**For c6i.4xlarge (32GB):**

```python
MAX_CONCURRENT_BROWSERS = 10
BROWSER_MEMORY_LIMIT_MB = 1000
```

### 4. Log Rotation

Configure log rotation in `docker-compose.yml`:

```yaml
services:
  backend:
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"
```

### 5. Swap Configuration

Even with sufficient RAM, configure swap for stability:

```bash
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
sudo sysctl vm.swappiness=10
```

---

## Monitoring & Alerting

### Essential Metrics to Monitor

1. **CPU Utilization**
   - Alert at: >85% sustained for >10 minutes
   - Action: Scale up or optimize workflows

2. **Memory Utilization**
   - Alert at: >90%
   - Action: Restart containers or scale up

3. **Disk IOPS**
   - Alert at: >80% of provisioned IOPS
   - Action: Increase GP3 IOPS

4. **Network Throughput**
   - Monitor proxy traffic patterns
   - Ensure within instance bandwidth limits

5. **Docker Container Health**
   - Use healthcheck endpoints
   - Auto-restart unhealthy containers

### Recommended Tools

- **CloudWatch** (native AWS monitoring)
- **Prometheus + Grafana** (detailed metrics)
- **cAdvisor** (container-level metrics)
- **Temporal UI** (workflow execution insights)

---

## Cost Optimization Strategies

### 1. Reserved Instances

For long-term deployments (1-3 years):

- **1-year RI:** ~40% savings
- **3-year RI:** ~60% savings

**Example:** c6i.4xlarge

- On-Demand: $544/month
- 1-year RI: ~$326/month
- 3-year RI: ~$218/month

### 2. Savings Plans

More flexible than Reserved Instances:

- Compute Savings Plans: ~66% savings
- EC2 Instance Savings Plans: ~72% savings

### 3. Spot Instances (NOT RECOMMENDED)

**Do NOT use Spot Instances for:**

- Temporal Server (risk of workflow interruption)
- PostgreSQL (data integrity concerns)
- Live browser automation sessions

**Can use Spot for:**

- Separate media processing worker (fault-tolerant)
- Batch engagement tasks (retriable)

---

## Migration Path

### Phase 1: Start with Minimum (c6i.2xlarge)

- Deploy full stack
- Test with 1-2 influencer personas
- Monitor resource usage patterns
- **Duration:** 1-2 weeks

### Phase 2: Scale to Production (c6i.4xlarge)

- Create AMI snapshot of current instance
- Launch c6i.4xlarge from AMI
- Transfer Elastic IP
- Update DNS (if applicable)
- **Downtime:** <5 minutes

### Phase 3: Enterprise (c6i.8xlarge)

- Only if managing 10+ AI personas
- Consider horizontal scaling instead (multiple c6i.4xlarge)

---

## Alternative: Horizontal Scaling

Instead of a single large instance, consider:

**Primary Instance** (c6i.4xlarge):

- Temporal Server
- PostgreSQL
- Redis
- Backend API
- Frontend

**Worker Instance 1** (c6i.2xlarge):

- Temporal Worker (content generation)
- OpenClaw

**Worker Instance 2** (c6i.2xlarge):

- Temporal Worker (engagement)
- GrowChief + Browsers

**Benefits:**

- Fault isolation
- Easier to scale specific components
- Can use Spot Instances for workers

**Drawbacks:**

- Increased network latency between services
- More complex deployment
- Higher total cost

---

## Final Recommendation

### For Most Users: **c6i.4xlarge (16 vCPU, 32 GB RAM)**

This configuration provides the best balance of:

- ✅ Performance headroom for growth
- ✅ Stability under 24/7 workload
- ✅ Cost efficiency (~$544/month)
- ✅ Room for 5-10 concurrent AI personas
- ✅ Reliable browser automation performance

### Deployment Checklist

- [ ] Launch c6i.4xlarge with 100 GB GP3 SSD
- [ ] Attach Elastic IP
- [ ] Configure Security Groups
- [ ] Enable Enhanced Networking
- [ ] Install Docker & Docker Compose
- [ ] Clone repository and configure `.env`
- [ ] Run `docker-compose up -d`
- [ ] Configure PostgreSQL tuning
- [ ] Set up CloudWatch alarms
- [ ] Configure log rotation
- [ ] Enable automated EBS snapshots (daily)
- [ ] Document admin credentials securely

---

## Additional Resources

- [AWS EC2 Instance Types](https://aws.amazon.com/ec2/instance-types/)
- [AWS EBS Volume Types](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-volume-types.html)
- [Docker Resource Constraints](https://docs.docker.com/config/containers/resource_constraints/)
- [Temporal Best Practices](https://docs.temporal.io/best-practices)

---

**Document Version:** 1.0  
**Last Updated:** March 11, 2026  
**Reviewed By:** AI Architecture Analysis
