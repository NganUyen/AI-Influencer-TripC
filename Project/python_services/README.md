# Python Backend for AI Influencer Factory

This directory contains the Python/FastAPI backend services for the AI Influencer Factory platform.

## Structure

```
python_services/
├── api/              # FastAPI routes and endpoints
├── workflows/        # Temporal.io workflow definitions
├── agents/           # OpenClaw agent configurations
├── config/           # Configuration files
├── main.py          # FastAPI application entry point
├── requirements.txt  # Python dependencies
└── Dockerfile       # Docker container definition
```

## Tech Stack

- **Framework:** FastAPI
- **Orchestration:** Temporal.io
- **AI Agent Platform:** OpenClaw
- **Database:** PostgreSQL (via Supabase)
- **Media APIs:** fal.ai, PlayHT, HeyGen
- **Social Media:** Postiz, GrowChief

## Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Temporal Server running

### Installation

1. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set up environment variables:

```bash
cp ../.env.example .env
```

4. Run the development server:

```bash
uvicorn main:app --reload --port 8000
```

## Temporal Workflows

The system uses Temporal for orchestrating long-running marketing workflows:

- **WeeklyMarketingWorkflow:** Generates weekly content calendars and waits for human approval
- **ContentGenerationWorkflow:** Handles media generation (images, videos, audio)
- **DistributionWorkflow:** Publishes content across multiple platforms
- **EngagementWorkflow:** Coordinates AI persona interactions

## OpenClaw Agents

OpenClaw manages the AI intelligence layer:

- **Strategist Agent:** Generates content strategy and calendars
- **Media Director Agent:** Creates prompts for media generation
- **Distribution Agent:** Handles cross-platform posting
- **Engagement Agent:** Manages the influencer proxy network

## API Endpoints

- `GET /api/health` - Health check
- `POST /api/workflows/start` - Start a new workflow
- `GET /api/workflows/{id}` - Get workflow status
- `POST /api/content/generate` - Generate content
- `POST /api/media/generate` - Generate media assets
- `GET /api/personas` - List AI personas
- `POST /api/personas` - Create new persona

## Docker Deployment

Build and run with Docker:

```bash
docker build -t ai-influencer-backend .
docker run -p 8000:8000 --env-file .env ai-influencer-backend
```

Or use docker-compose from the root directory.
