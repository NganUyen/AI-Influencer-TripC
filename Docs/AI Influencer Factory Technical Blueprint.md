### **AI Influencer Factory Technical Blueprint**

- **Core Orchestration:** Temporal.io manages the weekly marketing workflows and guarantees durable execution, allowing operations to pause indefinitely for human-in-the-loop approvals.
  - **Estimated Cost:** Self-host ($0).
- **Cognitive Engine:** OpenClaw serves as the intelligence layer, executing shell commands, controlling browser automation, and handling asynchronous user confirmations natively.
  - **Estimated Cost:** Self-host ($0).
- **Operator Surface**: The current public OpenClaw upstream exposes a single gateway with an integrated control UI, giving operators one localhost-admin surface for sessions, approvals, and gateway-aware orchestration.
  - **Estimated Cost**: Self-host ($0).
- **Compute Infrastructure:** A VPS via AWS (Amazon Web Services) EC2. An absolute minimum of 8 vCPUs and 16GB of RAM is required, though 32GB is the optimal target to handle the Temporal cluster, backend, and headless browsers.
  - **Estimated Cost:** Provided ($0).
- **Database State:** Supabase (Pro Tier) deployed in the target region. This fulfills Temporal's background polling requirements and provides built-in authentication with real-time frontend notifications.
  - **Estimated Cost:** \~$25.00/month.
- **Publishing Pipeline (Main Influencer Accounts):** Postiz handles the official, platform-approved OAuth distribution of your generated media to Twitter, Facebook, LinkedIn, TikTok, and YouTube.
  - **Estimated Cost:** Self-host ($0)
- **Engagement Syndicate (Stealth Accounts):** GrowChief manages the artificial engagement layer. It routes perfectly into your centralized Temporal cluster and PostgreSQL (Supabase) database to safely pace the stealth actions of your secondary bot accounts over time.
  - **Estimated Cost:** Self-host ($0).
- **Stealth Engine:** The Camoufox stealth browser executes the raw automation tasks across the social platforms by spoofing critical detection vectors at the C++ level before JavaScript executes.
  - **Estimated Cost:** Self-host ($0).
- **Network Identity:** IPRoyal residential proxies route active posting and engagement, handling the long-term sticky sessions needed to maintain algorithmic trust from consistent IP addresses.
  - **Estimated Cost:** \~$10.00 \- \~$20.00/month.
- **Media Generation APIs:**
  - **Images / Videos:** fal.ai via official OpenClaw integration provides access to over 600 models (such as Flux.1 Pro/Schnell and SDXL) with highly cost-effective pay-per-image pricing. A prebuilt skill can be deployed using the command openclaw skills fal-ai.
    - **Estimated Cost:** \~$10.00 \- \~$30.00/month.
  - **Audio Synthesis: PlayHT (REST API):** Provides access to an extensive library of over 900 natural-sounding AI voices across 142 languages and accents. It features instant voice cloning requiring only 30 seconds of reference audio, which is a strict requirement for generating isolated, unique vocal identities for each persona within your GrowChief engagement syndicate. Its high-volume API pricing structure bypasses the premium costs of ultra-low latency streaming, making it economically optimized for the asynchronous, heavy batch processing required by a 24/7 content factory. **Blaze** would be a good alternative.
    - **Estimated Cost:** \~$39.00/month.
  - **Video Avatars (Optional):** The API generates standard audio payloads that your Python backend can seamlessly catch and pass directly to HeyGen within the exact same Temporal Activity block.
    - **Estimated Cost:** \~$29.00/month (Excluded from base totals below).
- **Object Storage:** Cloudflare R2 stores all generated media assets. Its zero egress fees prevent massive bandwidth bills when agents repeatedly fetch video assets for cross-platform distribution.
  - **Estimated Cost:** \~$0.00 \- \~$5.00/month.

---

### **Total Estimated Project Costs**

**_(Note: These totals exclude the AWS infrastructure costs and the optional HeyGen subscription)_**

| Metric                 | Low-End Estimate | High-End Estimate |
| :--------------------- | :--------------- | :---------------- |
| **Total Monthly Cost** | **\~$84.00**     | **\~$119.00**     |
| **Total Weekly Cost**  | **\~$19.38**     | **\~$26.9**       |
