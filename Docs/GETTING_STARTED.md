# Getting Started with AI Influencer Factory

Welcome! This guide will help you set up and run the AI Influencer Factory platform.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Node.js 18+** - [Download](https://nodejs.org/)
- **Python 3.11+** - [Download](https://www.python.org/)
- **Docker Desktop** - [Download](https://www.docker.com/products/docker-desktop/)
- **Git** - [Download](https://git-scm.com/)

## Step 1: Environment Setup

### 1.1 Configure Environment Variables

Navigate to the Project directory and copy the example environment file:

```bash
cd Project
cp .env.example .env.local
```

Edit `.env.local` and add your API keys and configuration:

```env
# Required: Supabase
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# Required: AI APIs
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Required: Media Generation
FAL_AI_API_KEY=your_fal_ai_key

# Required: Storage
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET_NAME=ai-influencer-media
R2_PUBLIC_URL=https://your-bucket.r2.dev

# Optional: Additional services
PLAYHT_API_KEY=your_playht_key
TELEGRAM_BOT_TOKEN=your_bot_token
```

## Step 2: Database Setup

### 2.1 Create Supabase Project

1. Go to [Supabase](https://supabase.com/) and create a new project
2. Copy your project URL and API keys to `.env.local`
3. In Supabase Dashboard, go to SQL Editor
4. Run the schema from `Project/supabase/schema.sql`
5. Optionally run seed data from `Project/supabase/seed.sql`

## Step 3: Install Dependencies

### 3.1 Frontend Dependencies

```bash
cd Project
npm install
```

### 3.2 Backend Dependencies

```bash
cd Project/python_services
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

## Step 4: Start Services with Docker

From the **root directory**:

```bash
docker-compose up -d
```

This will start:

- Temporal Server (port 7233)
- Temporal UI (port 8080)
- PostgreSQL (port 5432)
- Redis (port 6379)

Verify services are running:

```bash
docker-compose ps
```

## Step 5: Run Development Servers

### 5.1 Start Frontend (Terminal 1)

```bash
cd Project
npm run dev
```

The Next.js app will be available at: http://localhost:3000

### 5.2 Start Backend (Terminal 2)

```bash
cd Project/python_services
# Activate venv if not already activated
uvicorn main:app --reload --port 8000
```

The FastAPI backend will be available at: http://localhost:8000
API documentation: http://localhost:8000/docs

## Step 6: Verify Installation

### 6.1 Check Frontend

Open http://localhost:3000 in your browser. You should see the AI Influencer Factory homepage.

### 6.2 Check Backend

Open http://localhost:8000/api/health. You should see a JSON response with service status.

### 6.3 Check Temporal

Open http://localhost:8080. You should see the Temporal UI.

## Common Issues & Solutions

### Issue: Port Already in Use

**Error:** `Port 3000 is already in use`

**Solution:** Kill the process using the port:

```bash
# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# macOS/Linux
lsof -ti:3000 | xargs kill -9
```

### Issue: Docker Services Won't Start

**Error:** Docker containers fail to start

**Solution:**

```bash
# Stop all containers
docker-compose down

# Remove volumes and restart
docker-compose down -v
docker-compose up -d
```

### Issue: Python Dependencies Fail

**Error:** `pip install` fails

**Solution:**

```bash
# Upgrade pip first
python -m pip install --upgrade pip

# Try installing again
pip install -r requirements.txt
```

### Issue: Database Connection Failed

**Error:** Cannot connect to Supabase

**Solution:**

1. Verify your Supabase project is active
2. Check that `.env.local` has correct credentials
3. Ensure your IP is allowed in Supabase settings
4. Test the connection URL in your browser

## Next Steps

Once everything is running:

1. **Explore the Dashboard** - Navigate to http://localhost:3000/dashboard
2. **Check API Docs** - Review endpoints at http://localhost:8000/docs
3. **Review Documentation** - Read the technical blueprint and development notes
4. **Set Up Temporal Workflows** - Configure your first marketing workflow
5. **Connect Social Accounts** - Add your social media accounts via Postiz

## Development Workflow

### Running Tests

```bash
# Frontend tests (when added)
cd Project
npm test

# Backend tests (when added)
cd Project/python_services
pytest
```

### Type Checking

```bash
cd Project
npm run type-check
```

### Linting

```bash
cd Project
npm run lint
```

### Building for Production

```bash
# Frontend
cd Project
npm run build
npm run start

# Backend (production mode)
cd Project/python_services
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Useful Commands

```bash
# View Docker logs
docker-compose logs -f [service_name]

# Restart a service
docker-compose restart [service_name]

# Stop all services
docker-compose down

# Rebuild containers
docker-compose up -d --build

# Access database
docker exec -it ai-influencer-postgres psql -U temporal
```

## Getting Help

If you encounter issues:

1. Check the logs: `docker-compose logs`
2. Review the documentation in the root README
3. Verify all environment variables are set correctly
4. Ensure all prerequisites are installed

## Resources

- [Project README](../README.md)
- [Technical Blueprint](../AI%20Influencer%20Factory%20Technical%20Blueprint.md)
- [Development Notes](../Ally%20Dev%20-%20Note.md)
- [Frontend Documentation](Project/README.md)
- [Backend Documentation](Project/python_services/README.md)

---

**Ready to build AI influencers? Let's go! 🚀**
