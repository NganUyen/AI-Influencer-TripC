# AWS EC2 Instance Type Comparison Matrix

## For AI Influencer Factory Deployment

This document provides a detailed comparison of suitable AWS EC2 instance types to help you choose the optimal configuration for your specific use case.

---

## Quick Decision Tree

```
How many AI personas will you run simultaneously?
│
├─ 1-2 personas → c6i.2xlarge (8 vCPU, 16GB) - Minimum
│
├─ 3-7 personas → c6i.4xlarge (16 vCPU, 32GB) - RECOMMENDED
│
├─ 8-15 personas → c6i.8xlarge (32 vCPU, 64GB) - Scale
│
└─ 15+ personas → Consider horizontal scaling (multiple instances)
```

---

## Detailed Instance Comparison

### Option 1: c6i.2xlarge (Minimum Configuration)

| Specification      | Value                     |
| ------------------ | ------------------------- |
| **vCPUs**          | 8                         |
| **Memory**         | 16 GB                     |
| **Network**        | Up to 12.5 Gbps           |
| **EBS Bandwidth**  | Up to 10 Gbps             |
| **On-Demand Cost** | ~$0.34/hour (~$272/month) |
| **1-Year RI**      | ~$163/month (40% savings) |
| **3-Year RI**      | ~$109/month (60% savings) |

**Performance Profile:**

- ✅ Meets stated minimum requirements (8 vCPU, 16GB RAM)
- ✅ Suitable for early development and testing
- ⚠️ Limited to 2-4 concurrent browser sessions
- ⚠️ May experience performance degradation under load
- ⚠️ Little headroom for traffic spikes

**Best For:**

- Single AI influencer persona
- 3-5 stealth engagement accounts
- Development/staging environments
- Budget-constrained deployments
- Proof of concept phase

**Not Recommended For:**

- Production deployments with SLA requirements
- Multiple personas (>2)
- High-volume content generation (>20 posts/day)
- Large engagement syndicates (>10 accounts)

**Resource Allocation:**

```
Available: 8 vCPU, 16 GB RAM
Usage with all services:
  - Temporal + Worker:     3 vCPU,  4 GB
  - OpenClaw + Browsers:   3 vCPU,  6 GB
  - GrowChief:             2 vCPU,  3 GB
  - Backend + Frontend:    2 vCPU,  3 GB
  - PostgreSQL + Redis:    2 vCPU,  2.5 GB
  - System Overhead:      ~1 vCPU,  1.5 GB
  ----------------------------------------
  Total Reserved:          13 vCPU, 20 GB ⚠️ OVERCOMMITTED
```

**Verdict:** ⚠️ Not recommended for production. Use only for testing.

---

### Option 2: c6i.4xlarge (RECOMMENDED - Production Standard)

| Specification      | Value                     |
| ------------------ | ------------------------- |
| **vCPUs**          | 16                        |
| **Memory**         | 32 GB                     |
| **Network**        | Up to 12.5 Gbps           |
| **EBS Bandwidth**  | Up to 10 Gbps             |
| **On-Demand Cost** | ~$0.68/hour (~$544/month) |
| **1-Year RI**      | ~$326/month (40% savings) |
| **3-Year RI**      | ~$218/month (60% savings) |

**Performance Profile:**

- ✅ Excellent balance of performance and cost
- ✅ Handles 5-10 concurrent browser sessions comfortably
- ✅ Sufficient headroom for Temporal state management
- ✅ Stable under 24/7 continuous operation
- ✅ Room for growth without migration

**Best For:**

- **2-7 AI influencer personas** (sweet spot: 4-5)
- **10-25 stealth engagement accounts**
- **30-80 posts per day**
- Production deployments with reliability requirements
- Small to medium marketing agencies
- Solo founders scaling beyond MVP

**Performance Benchmarks:**

- **Content Generation:** Can generate 10 pieces of content simultaneously
- **Browser Sessions:** 8-12 concurrent stealth browsers without performance loss
- **Workflow Execution:** Handles 20+ active Temporal workflows
- **API Response Time:** <100ms average under normal load

**Resource Allocation:**

```
Available: 16 vCPU, 32 GB RAM
Optimal allocation:
  - Temporal Server:          3 vCPU,  4 GB
  - Temporal Worker:          3 vCPU,  4 GB
  - OpenClaw + Browsers:      6 vCPU, 12 GB  (10 concurrent sessions)
  - GrowChief:                3 vCPU,  6 GB  (8 stealth accounts)
  - Backend (FastAPI):        2 vCPU,  2 GB
  - Frontend (Next.js):       1 vCPU,  2 GB
  - PostgreSQL:               2 vCPU,  4 GB
  - Redis + Others:           1 vCPU,  2 GB
  - System Buffer:            2 vCPU,  3 GB
  ----------------------------------------
  Total Reserved:            23 vCPU, 39 GB (uses soft limits for bursting)
```

**Verdict:** ✅ **RECOMMENDED** - Best price/performance for most users.

---

### Option 3: c6i.8xlarge (Enterprise/High-Volume)

| Specification      | Value                       |
| ------------------ | --------------------------- |
| **vCPUs**          | 32                          |
| **Memory**         | 64 GB                       |
| **Network**        | 12.5 Gbps                   |
| **EBS Bandwidth**  | 10 Gbps                     |
| **On-Demand Cost** | ~$1.36/hour (~$1,088/month) |
| **1-Year RI**      | ~$653/month (40% savings)   |
| **3-Year RI**      | ~$435/month (60% savings)   |

**Performance Profile:**

- ✅ Enterprise-grade performance
- ✅ 20+ concurrent browser sessions
- ✅ Significant headroom for traffic spikes
- ✅ Can handle 3x normal load without degradation
- ✅ Future-proof for feature expansion

**Best For:**

- **8-15 AI influencer personas**
- **30-60 stealth engagement accounts**
- **100-200+ posts per day**
- Marketing agencies managing multiple brands
- High-volume content operations
- Multi-tenant SaaS deployments

**Performance Benchmarks:**

- **Content Generation:** 25+ simultaneous generation tasks
- **Browser Sessions:** 20-30 concurrent stealth browsers
- **Workflow Execution:** 50+ active workflows
- **API Response Time:** <50ms even under high load

**Resource Allocation:**

```
Available: 32 vCPU, 64 GB RAM
Generous allocation:
  - Temporal Server:          4 vCPU,  8 GB
  - Temporal Worker:          6 vCPU,  8 GB
  - OpenClaw + Browsers:     12 vCPU, 24 GB  (25 concurrent sessions)
  - GrowChief:                6 vCPU, 12 GB  (20 stealth accounts)
  - Backend (FastAPI):        4 vCPU,  4 GB
  - Frontend (Next.js):       2 vCPU,  4 GB
  - PostgreSQL:               4 vCPU,  8 GB
  - Redis + Others:           2 vCPU,  2 GB
  - System Buffer:            4 vCPU,  6 GB
  ----------------------------------------
  Total Reserved:            44 vCPU, 76 GB (uses bursting)
```

**Verdict:** ✅ Excellent for agencies and high-volume operations. Consider horizontal scaling instead if budget is a concern.

---

## Alternative Instance Types Considered

### c6i Family (Compute Optimized) ✅ RECOMMENDED

- **Optimized for:** CPU-intensive workloads
- **Why chosen:** Browser automation and Temporal orchestration are CPU-bound
- **Network:** Up to 12.5 Gbps (critical for proxy traffic)

### m6i Family (General Purpose) 🤔 ALTERNATIVE

- **Examples:** m6i.2xlarge (8 vCPU, 32GB), m6i.4xlarge (16 vCPU, 64GB)
- **Cost:** Similar to c6i (~$0.384/hr for 2xlarge, ~$0.768/hr for 4xlarge)
- **Pros:** More memory per vCPU (4GB vs 2GB)
- **Cons:** Fewer CPU cores for the same price
- **Verdict:** Better for memory-intensive workloads, but AI Influencer Factory is CPU-bound

### t3 Family (Burstable) ❌ NOT RECOMMENDED

- **Examples:** t3.2xlarge (8 vCPU, 32GB)
- **Cost:** Cheaper (~$0.3328/hour)
- **Pros:** Cost-effective for low utilization
- **Cons:** CPU credits system - poor for 24/7 workloads
- **Verdict:** ❌ Avoid for production. Designed for bursty workloads, not continuous operation.

### r6i Family (Memory Optimized) ❌ NOT SUITABLE

- **Examples:** r6i.2xlarge (8 vCPU, 64GB)
- **Cost:** More expensive (~$0.504/hour)
- **Pros:** High memory-to-CPU ratio (8GB per vCPU)
- **Cons:** Overkill for this workload, wastes budget on unused RAM
- **Verdict:** ❌ Not cost-effective for AI Influencer Factory

---

## Storage Configuration Comparison

### GP3 SSD (General Purpose) ✅ RECOMMENDED

| Size   | IOPS   | Throughput | Cost/Month |
| ------ | ------ | ---------- | ---------- |
| 100 GB | 3,000  | 125 MB/s   | ~$8        |
| 200 GB | 3,000  | 125 MB/s   | ~$16       |
| 100 GB | 16,000 | 250 MB/s   | ~$20       |

**Recommendation:** 100 GB at 3,000 IOPS for most use cases

### GP2 SSD (Previous Generation) ⚠️ LEGACY

- More expensive than GP3 for same performance
- IOPS scales with volume size (3 IOPS per GB)
- **Verdict:** Use GP3 instead

### io2 SSD (Provisioned IOPS) 💰 EXPENSIVE

- Ultra-high performance (up to 64,000 IOPS)
- ~$125/month for 100GB with 10,000 IOPS
- **Verdict:** Overkill and expensive. Only for mission-critical databases.

---

## Cost Analysis by Use Case

### Use Case 1: Solo Founder (1-2 Personas)

**Configuration:** c6i.4xlarge + 100GB GP3 (on-demand)

| Component             | Monthly Cost   |
| --------------------- | -------------- |
| EC2 Instance          | $544           |
| Storage (100GB GP3)   | $8             |
| Data Transfer (200GB) | $18            |
| **AWS Subtotal**      | **$570**       |
| Supabase Pro          | $25            |
| IPRoyal Proxies       | $15            |
| fal.ai (Media)        | $15            |
| PlayHT (Audio)        | $39            |
| **Total**             | **$664/month** |

**Posts per Day:** 15-25  
**Cost per Post:** ~$0.88

---

### Use Case 2: Small Agency (5-7 Personas)

**Configuration:** c6i.4xlarge + 200GB GP3 (1-year RI)

| Component                | Monthly Cost   |
| ------------------------ | -------------- |
| EC2 Instance (1-year RI) | $326           |
| Storage (200GB GP3)      | $16            |
| Data Transfer (500GB)    | $45            |
| **AWS Subtotal**         | **$387**       |
| Supabase Pro             | $25            |
| IPRoyal Proxies          | $25            |
| fal.ai (Media)           | $30            |
| PlayHT (Audio)           | $49            |
| **Total**                | **$516/month** |

**Posts per Day:** 50-80  
**Cost per Post:** ~$0.22

---

### Use Case 3: Marketing Agency (10-15 Personas)

**Configuration:** c6i.8xlarge + 200GB GP3 (1-year RI)

| Component                | Monthly Cost   |
| ------------------------ | -------------- |
| EC2 Instance (1-year RI) | $653           |
| Storage (200GB GP3)      | $16            |
| Data Transfer (1TB)      | $90            |
| **AWS Subtotal**         | **$759**       |
| Supabase Pro             | $25            |
| IPRoyal Proxies          | $40            |
| fal.ai (Media)           | $60            |
| PlayHT (Audio)           | $99            |
| **Total**                | **$983/month** |

**Posts per Day:** 120-200  
**Cost per Post:** ~$0.16

---

## Scaling Strategies

### Vertical Scaling (Single Instance)

**Path:** c6i.2xlarge → c6i.4xlarge → c6i.8xlarge

**Pros:**

- ✅ Simple architecture
- ✅ No network latency between services
- ✅ Easier to manage

**Cons:**

- ⚠️ Single point of failure
- ⚠️ Downtime during upgrades
- ⚠️ Eventually hits instance size limits

**Best For:** Most users (up to 15 personas)

---

### Horizontal Scaling (Multiple Instances)

**Architecture:**

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
- GrowChief

**Total Cost:** ~$816/month (on-demand)

**Pros:**

- ✅ Fault isolation
- ✅ Scale specific components independently
- ✅ Can use Spot Instances for workers (50-70% savings)
- ✅ Better resource utilization

**Cons:**

- ⚠️ Increased complexity
- ⚠️ Network latency between services (5-10ms)
- ⚠️ Higher total cost if not using Spot

**Best For:** 15+ personas, or when reliability > cost

---

## Regional Pricing Differences

AWS pricing varies by region. Here's c6i.4xlarge comparison:

| Region                       | On-Demand ($/hr) | Monthly Cost | Latency Consideration            |
| ---------------------------- | ---------------- | ------------ | -------------------------------- |
| **US East (N. Virginia)**    | $0.68            | $544         | ✅ Lowest cost, US-based APIs    |
| **US West (Oregon)**         | $0.68            | $544         | ✅ Same cost, West Coast latency |
| **EU (Ireland)**             | $0.748           | $599         | EU data residency, +10% cost     |
| **EU (Frankfurt)**           | $0.783           | $627         | Central EU, +15% cost            |
| **Asia Pacific (Singapore)** | $0.850           | $680         | APAC market, +25% cost           |
| **Asia Pacific (Sydney)**    | $0.884           | $708         | AU/NZ market, +30% cost          |

**Recommendation:** Choose region closest to:

1. Your target social media audience
2. Your external API providers (OpenAI, Anthropic, fal.ai)
3. Your Supabase instance

For global reach, US East (N. Virginia) is typically optimal.

---

## Final Recommendation Summary

### 🥇 Best for Most Users: **c6i.4xlarge**

- **Cost:** $544/month (on-demand), $326/month (1-year RI)
- **Use Cases:** 2-7 personas, 30-80 posts/day
- **Why:** Best balance of performance, cost, and growth headroom

### 🥈 Budget Option: **c6i.2xlarge**

- **Cost:** $272/month (on-demand), $163/month (1-year RI)
- **Use Cases:** 1-2 personas, testing, development
- **Why:** Meets minimum requirements, lowest cost
- **Warning:** Limited production capability

### 🥉 High-Volume Option: **c6i.8xlarge**

- **Cost:** $1,088/month (on-demand), $653/month (1-year RI)
- **Use Cases:** 8-15 personas, agency operations
- **Why:** Enterprise performance, high concurrency
- **Alternative:** Consider horizontal scaling for same cost

---

## Migration Path

### Phase 1: Start Small (Weeks 1-4)

- **Instance:** c6i.2xlarge
- **Goal:** Test architecture, validate workflows
- **Cost:** ~$272/month

### Phase 2: Production Launch (Months 2-3)

- **Instance:** c6i.4xlarge
- **Goal:** Support 3-5 personas, stable operations
- **Cost:** ~$544/month (or commit to 1-year RI for $326/month)

### Phase 3: Scale (Month 4+)

- **Option A:** Stay on c6i.4xlarge (sufficient for most)
- **Option B:** Upgrade to c6i.8xlarge (high-volume needs)
- **Option C:** Horizontal scaling (15+ personas)

**Migration Downtime:** <5 minutes (with proper planning)

---

## Decision Checklist

Use this checklist to determine your ideal configuration:

- [ ] How many AI personas do you plan to run? **\_\_\_**
- [ ] Expected posts per day across all personas? **\_\_\_**
- [ ] Number of stealth engagement accounts? **\_\_\_**
- [ ] Is this for development/testing or production? **\_\_\_**
- [ ] What's your monthly infrastructure budget? $**\_\_\_**
- [ ] Do you need 24/7 uptime with SLA? Yes / No
- [ ] Are you willing to commit to 1-year RI for savings? Yes / No
- [ ] Do you expect rapid growth (3x) within 6 months? Yes / No

**If you answered:**

- 1-2 personas, testing → **c6i.2xlarge**
- 3-7 personas, production → **c6i.4xlarge** ✅
- 8-15 personas, agency → **c6i.8xlarge**
- 15+ personas → **Horizontal scaling**

---

**Document Version:** 1.0  
**Last Updated:** March 11, 2026  
**AWS Pricing:** Subject to change, verify at [aws.amazon.com/ec2/pricing](https://aws.amazon.com/ec2/pricing/)
