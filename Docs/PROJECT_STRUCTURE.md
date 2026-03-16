# AI Influencer Factory - Updated Structure

## Overview

This project has been restructured to align with the technical blueprint and implement the full AI Influencer Factory architecture.

## 📁 Project Structure

```
AI-Influencer-TripC/
├── docker-compose.yml          # Full stack orchestration
├── Project/
│   ├── .env.example            # Environment configuration template
│   ├── .env.local              # Your local configuration (create from .env.example)
│   │
│   ├── python_services/        # Backend Services
│   │   ├── main.py             # FastAPI application
│   │   ├── worker.py           # Temporal worker
│   │   ├── requirements.txt    # Python dependencies
│   │   ├── Dockerfile          # Backend container
│   │   │
│   │   ├── workflows/          # Temporal Workflows
│   │   │   ├── weekly_marketing_workflow.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── activities/         # Temporal Activities
│   │   │   ├── strategy_activities.py
│   │   │   ├── media_activities.py
│   │   │   ├── distribution_activities.py
│   │   │   ├── approval_activities.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── services/           # Service Integrations
│   │   │   ├── openclaw_service.py      # AI agent orchestration
│   │   │   ├── postiz_service.py        # OAuth publishing
│   │   │   ├── growchief_service.py     # Engagement syndicate
│   │   │   ├── fal_service.py           # Image/video generation
│   │   │   ├── playht_service.py        # Audio synthesis
│   │   │   ├── storage_service.py       # Cloudflare R2
│   │   │   ├── telegram_service.py      # Approval bot
│   │   │   ├── ai_service.py            # AI model wrapper
│   │   │   ├── browser_automation.py    # Stealth browser
│   │   │   └── __init__.py
│   │   │
│   │   ├── api/                # API Routes
│   │   │   ├── workflows.py    # Workflow management
│   │   │   ├── media.py        # Media generation
│   │   │   ├── accounts.py     # Account management
│   │   │   ├── analytics.py    # Analytics & metrics
│   │   │   └── __init__.py
│   │   │
│   │   └── config/             # Configuration
│   │       └── settings.py     # Application settings
│   │
│   ├── app/                    # Next.js Frontend
│   ├── components/             # React components
│   ├── supabase/               # Database schemas
│   └── ...
```

## 🏗️ Architecture Components

### Core Stack (as per Technical Blueprint)

1. **Temporal.io** - Workflow orchestration
2. **OpenClaw** - Cognitive engine & agent orchestration
3. **Supabase/PostgreSQL** - Database state
4. **Postiz** - Official OAuth publishing
5. **GrowChief** - Engagement syndicate
6. **Camoufox** - Stealth browser automation
7. **IPRoyal** - Residential proxies
8. **fal.ai** - Image/video generation
9. **PlayHT** - Audio synthesis
10. **Cloudflare R2** - Media storage

### Services Running in Docker

- `postgres` - PostgreSQL database
- `temporal` - Temporal server + Web UI
- `redis` - Caching and queues
- `openclaw` - AI cognitive engine
- `openclaw_mission_control` - Agent orchestration platform
- `postiz` - Multi-platform publishing
- `growchief` - Engagement management
- `backend` - FastAPI application
- `temporal_worker` - Workflow processor
- `frontend` - Next.js web UI

## 🚀 Getting Started

### Prerequisites

- Docker Desktop
- Node.js 18+
- Python 3.11+
- AWS EC2 or VPS (for production deployment)

### Local Development Setup

1. **Clone and configure environment:**

   ```bash
   cd Project
   cp .env.example .env.local
   # Edit .env.local with your API keys
   ```

2. **Start the full stack:**

   ```bash
   docker-compose up -d
   ```

3. **Access services:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - Temporal UI: http://localhost:8080
   - OpenClaw: http://localhost:8080
   - Postiz: http://localhost:3100
   - GrowChief: http://localhost:3200

### Configuration Required

#### Essential API Keys

1. **AI Models:**
   - OpenAI API key (GPT-4)
   - Anthropic API key (Claude)

2. **Media Generation:**
   - fal.ai API key
   - PlayHT API key + User ID

3. **Storage:**
   - Cloudflare R2 credentials
   - Configure public domain for media URLs

4. **Proxies:**
   - IPRoyal residential proxy credentials

5. **Telegram:**
   - Bot token from @BotFather
   - Your Telegram chat ID

6. **Database:**
   - Supabase project credentials

## 📊 Workflow System

### Weekly Marketing Workflow

The main orchestration workflow:

1. **Strategy Generation** - OpenClaw generates 7-day content plan
2. **Human Approval** - Telegram approval request (waits indefinitely)
3. **Media Production** - Parallel generation of images, videos, audio
4. **Cloud Storage** - Upload to Cloudflare R2
5. **Scheduling** - Create daily post schedule
6. **Publishing** - Distribute via Postiz/browser automation
7. **Engagement** - GrowChief triggers stealth account interactions

### Starting a Workflow

```bash
curl -X POST http://localhost:8000/api/workflows/start-weekly \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "brand_config": {
      "voice": "professional and engaging",
      "platforms": ["twitter", "linkedin", "instagram"],
      "content_pillars": ["AI", "automation", "marketing"]
    }
  }'
```

## 🔧 Development

### Backend Development

```bash
cd Project/python_services
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend Development

```bash
cd Project
npm install
npm run dev
```

### Run Temporal Worker

```bash
cd Project/python_services
python worker.py
```

## 📦 Deployment

### Production Deployment (AWS EC2/VPS)

1. **Server Requirements:**
   - 8+ vCPUs
   - 16-32GB RAM
   - Ubuntu 22.04 LTS

2. **Install Docker:**

   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   ```

3. **Clone and configure:**

   ```bash
   git clone <repository>
   cd AI-Influencer-TripC
   cp Project/.env.example Project/.env.local
   # Configure production values
   ```

4. **Deploy:**

   ```bash
   docker-compose up -d --build
   ```

5. **Configure domain & SSL:**
   - Point domain to server IP
   - Setup Nginx reverse proxy
   - Configure Let's Encrypt SSL

## 💰 Cost Estimates

Based on the technical blueprint:

| Service            | Monthly Cost  |
| ------------------ | ------------- |
| Supabase Pro       | ~$25          |
| IPRoyal Proxies    | $10-$20       |
| fal.ai (Media Gen) | $10-$30       |
| PlayHT (Audio)     | ~$39          |
| Cloudflare R2      | $0-$5         |
| **Total**          | **~$84-$119** |

_Excludes AWS infrastructure and optional HeyGen subscription_

## 🔐 Security Notes

- All API keys in `.env.local` (never commit!)
- Use strong JWT secret in production
- Enable HTTPS for all public endpoints
- Implement rate limiting on API routes
- Rotate proxy IPs regularly
- Use unique browser profiles per account

## 📚 API Documentation

Once running, visit:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## 🐛 Troubleshooting

### Services won't start

```bash
docker-compose down -v
docker-compose up -d --build
```

### Temporal worker not processing

- Check worker logs: `docker logs ai-influencer-temporal-worker`
- Verify Temporal connection in backend logs
- Ensure task queue name matches configuration

### Browser automation fails

- Check Camoufox installation
- Verify proxy credentials
- Ensure browser profiles directory exists

## 📖 Further Reading

- [Temporal Documentation](https://docs.temporal.io/)
- [OpenClaw Documentation](https://openclaw.ai/docs)
- [Postiz API Reference](https://postiz.com/docs)
- [fal.ai Models](https://fal.ai/models)
- [PlayHT Voice Library](https://play.ht/voices)

## 🤝 Support

For issues or questions, check:

- Project documentation in `/docs`
- Technical blueprint: `AI Influencer Factory Technical Blueprint.md`
- Development notes: `Ally Dev - Note.md`

---

**Built with the AI Influencer Factory Technical Blueprint**
