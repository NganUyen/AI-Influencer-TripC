# AI Influencer Factory

> **AI-driven marketing orchestration platform with autonomous content generation and multi-platform distribution**

## 📋 Overview

The AI Influencer Factory is a comprehensive platform that acts as an autonomous digital marketing team and virtual influencer roster. It autonomously generates cross-platform strategies, creates multimedia content, waits for human approval via Telegram, and executes distribution across multiple social networks.

## 🎯 Key Features

- **🤖 AI-Powered Content Generation** - GPT-4o and Claude 3.5 for intelligent content creation
- **📅 Temporal Orchestration** - Reliable, durable workflow execution with human-in-the-loop approval
- **🎨 Multi-Modal Media Generation** - Images (fal.ai), Videos (HeyGen), Audio (PlayHT)
- **🌐 Multi-Platform Distribution** - Twitter, LinkedIn, Facebook, Instagram, TikTok, YouTube
- **👥 AI Persona Network** - Multiple AI influencers with unique voices and engagement patterns
- **🔄 IP-Rotated Engagement Syndicate** - Coordinated cross-account engagement for organic reach
- **📱 Telegram Approval Interface** - Low-friction content approval workflow
- **📊 Analytics Dashboard** - Track performance across all platforms

## 🏗️ Architecture

**Updated:** The project has been fully restructured to align with the [Technical Blueprint](AI%20Influencer%20Factory%20Technical%20Blueprint.md). See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for detailed documentation.

```
AI-Influencer-TripC/
├── Project/
│   ├── app/                         # Next.js 14 app directory
│   ├── components/                  # React components
│   ├── python_services/             # Backend services
│   │   ├── workflows/              # ✨ Temporal workflows
│   │   │   └── weekly_marketing_workflow.py
│   │   ├── activities/             # ✨ Workflow activities
│   │   │   ├── strategy_activities.py
│   │   │   ├── media_activities.py
│   │   │   ├── distribution_activities.py
│   │   │   └── approval_activities.py
│   │   ├── services/               # ✨ Service integrations
│   │   │   ├── openclaw_service.py      # AI cognitive engine
│   │   │   ├── postiz_service.py        # OAuth publishing
│   │   │   ├── growchief_service.py     # Engagement syndicate
│   │   │   ├── fal_service.py           # Image/video generation
│   │   │   ├── playht_service.py        # Audio synthesis
│   │   │   ├── storage_service.py       # Cloudflare R2
│   │   │   ├── telegram_service.py      # Approval interface
│   │   │   ├── ai_service.py            # AI model wrapper
│   │   │   └── browser_automation.py    # Stealth browser
│   │   ├── api/                    # API endpoints
│   │   └── config/                 # Configuration
│   ├── supabase/                    # Database schemas & migrations
│   └── ...
├── docker-compose.yml               # ✨ Full stack orchestration
└── Documentation/
    ├── AI Influencer Factory Technical Blueprint.md
    ├── Ally Dev - Note.md
    └── PROJECT_STRUCTURE.md        # ✨ Detailed structure guide
```

### 🔄 Workflow System

The platform uses **Temporal.io** for durable workflow orchestration:

1. **Weekly Marketing Workflow** - Main orchestration loop
   - Generate 7-day content strategy via OpenClaw
   - Send Telegram approval request (waits indefinitely)
   - Generate media assets in parallel (images, videos, audio)
   - Upload to Cloudflare R2 storage
   - Schedule daily posts
   - Publish via Postiz (OAuth) or browser automation
   - Trigger GrowChief engagement syndicate

2. **Post Publishing Workflow** - Individual post distribution
3. **Engagement Syndicate Workflow** - Coordinated stealth interactions

## 🛠️ Tech Stack

### Frontend

- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS
- **State:** Zustand
- **Auth & DB:** Supabase

### Backend

- **API:** FastAPI (Python)
- **Orchestration:** Temporal.io (durable workflows)
- **AI Brain:** OpenClaw (cognitive engine + Mission Control)
- **Database:** PostgreSQL (Supabase)
- **Cache:** Redis
- **Worker:** Temporal worker for activity execution

### Infrastructure

- **Deployment:** Docker & Docker Compose
- **Storage:** Cloudflare R2 (zero egress fees)
- **Proxies:** IPRoyal Residential (sticky sessions)
- **Publishing:** Postiz (official OAuth APIs)
- **Engagement:** GrowChief (stealth account manager)
- **Browser:** Camoufox (stealth automation)

### AI & Media APIs

- **Text AI:** OpenAI GPT-4o, Anthropic Claude 3.5
- **Images/Video:** fal.ai (600+ models)
- **Audio:** PlayHT (900+ voices)
- **Avatars:** HeyGen (optional)

## 🚀 Quick Start

### Prerequisites

- Node.js 18+
- Python 3.11+
- Docker & Docker Compose
- Supabase account
- API keys for AI services

### Installation

1. **Clone the repository**

```bash
git clone <repository-url>
cd AI-Influencer-TripC
```

2. **Set up environment variables**

```bash
cd Project
cp .env.example .env.local
# Edit .env.local with your API keys and configuration
```

3. **Start services with Docker**

# From project root

docker-compose up -d

````

This starts:
- PostgreSQL database
- Temporal server + Web UI (localhost:8080)
- Redis cache
- OpenClaw + Mission Control
- Postiz (multi-platform publisher)
- GrowChief (engagement manager)
- Python backend (FastAPI)
- Temporal worker
- Next.js frontend

4. **Access the services**

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000 (Swagger docs: /docs)
- **Temporal UI:** http://localhost:8080
- **OpenClaw:** http://localhost:8080
- **Postiz:** http://localhost:3100
- **GrowChief:** http://localhost:3200

## 📖 Documentation

- **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** - Detailed project structure and setup guide
- **[AI Influencer Factory Technical Blueprint.md](AI%20Influencer%20Factory%20Technical%20Blueprint.md)** - Architecture and cost breakdown
- **[Ally Dev - Note.md](Ally%20Dev%20-%20Note.md)** - Development roadmap and strategy

## 🔧 Development Workflow

### Starting a Weekly Workflow

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
````

### Approving Content via API

```bash
curl -X POST http://localhost:8000/api/workflows/approve/{workflow_id} \
  -H "Content-Type: application/json" \
  -d '{"approved": true, "feedback": ""}'
```

### Generating Media

```bash
# Generate image
curl -X POST http://localhost:8000/api/media/generate/image \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Modern tech workspace", "aspect_ratio": "16:9"}'

# Generate audio
curl -X POST http://localhost:8000/api/media/generate/audio \
  -H "Content-Type: application/json" \
  -d '{"text": "Welcome to AI Influencer Factory", "voice_id": "your-voice-id"}'
```

## 💰 Monthly Cost Breakdown

Based on technical blueprint:

| Service         | Cost               |
| --------------- | ------------------ |
| Supabase Pro    | ~$25               |
| IPRoyal Proxies | $10-$20            |
| fal.ai (Media)  | $10-$30            |
| PlayHT (Audio)  | ~$39               |
| Cloudflare R2   | $0-$5              |
| **Total**       | **$84-$119/month** |

_Self-hosted services (Temporal, OpenClaw, Postiz, GrowChief) = $0_
_Excludes AWS infrastructure_

## 🔐 Security & Best Practices

- All API keys stored in `.env.local` (never commit!)
- Use strong `JWT_SECRET_KEY` in production
- Enable HTTPS for all public endpoints
- Implement rate limiting on API routes
- Rotate proxy IPs regularly
- Unique browser profiles per stealth account
- Regular backups of PostgreSQL database

## 🐛 Troubleshooting

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md#-troubleshooting) for common issues and solutions.

### Quick Fixes

**Services won't start:**

```bash
docker-compose down -v
docker-compose up -d --build
```

**Check logs:**

```bash
docker logs ai-influencer-backend
docker logs ai-influencer-temporal-worker
docker logs ai-influencer-temporal
```

## 📚 API Reference

Once running, access interactive API documentation:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## 🤝 Contributing

This is a private project. For questions or issues, refer to documentation files.

## 📄 License

Proprietary - All rights reserved.

---

**Built with the AI Influencer Factory Technical Blueprint**

For detailed setup instructions, see [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Temporal UI: http://localhost:8080

## 📖 Documentation

- **[Technical Blueprint](./AI%20Influencer%20Factory%20Technical%20Blueprint.md)** - Complete technical architecture and cost estimates
- **[Development Notes](./Ally%20Dev%20-%20Note.md)** - Project proposal and implementation strategy
- **[Project README](./Project/README.md)** - Frontend application documentation
- **[Backend README](./Project/python_services/README.md)** - Python services documentation

## 💰 Estimated Monthly Costs

| Service           | Cost Range         |
| ----------------- | ------------------ |
| Supabase Pro      | ~$25               |
| fal.ai (Media)    | $10-$30            |
| PlayHT (Audio)    | $39                |
| IPRoyal (Proxies) | $10-$20            |
| Cloudflare R2     | $0-$5              |
| **Total**         | **$84-$119/month** |

_AWS EC2 infrastructure costs not included (provided separately)_

## 🔧 Development

### Frontend Development

```bash
cd Project
npm run dev          # Start dev server
npm run build        # Build for production
npm run lint         # Run linter
npm run type-check   # Check TypeScript types
```

### Backend Development

```bash
cd Project/python_services
uvicorn main:app --reload  # Start with hot reload
pytest                      # Run tests (when added)
```

### Database Migrations

```bash
# Create new migration
supabase migration new <migration_name>

# Apply migrations
supabase db push
```

## 📝 Roadmap

### Phase 1: Foundation (Weeks 1-2) ✅

- [x] Project initialization
- [x] Core folder structure
- [x] Basic UI components
- [x] Database schema

### Phase 2: Orchestration (Weeks 3-4)

- [ ] Temporal workflow setup
- [ ] OpenClaw agent integration
- [ ] Telegram bot implementation

### Phase 3: Content Generation (Weeks 5-6)

- [ ] AI content generation
- [ ] Media API integrations
- [ ] Cloudflare R2 storage

### Phase 4: Distribution (Weeks 7-9)

- [ ] Postiz integration
- [ ] GrowChief setup
- [ ] Engagement syndicate

### Phase 5: Production (Weeks 10-12)

- [ ] Full dashboard UI
- [ ] Analytics implementation
- [ ] Production deployment

## 🤝 Contributing

This is a private project. For questions or discussions, please reach out to the project maintainers.

## 📄 License

Proprietary - All rights reserved

## 🔗 Resources

- [Temporal Documentation](https://docs.temporal.io/)
- [Next.js Documentation](https://nextjs.org/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Supabase Documentation](https://supabase.com/docs)
- [OpenClaw Documentation](https://openclaw.ai/docs)
- [fal.ai API](https://fal.ai/docs)
- [PlayHT API](https://docs.play.ht/)

---

**Built with ❤️ for autonomous AI-driven marketing**
