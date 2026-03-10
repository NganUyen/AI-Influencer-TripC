# AI Influencer Factory - Frontend

This is the Next.js frontend application for the AI Influencer Factory platform.

## Tech Stack

- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS
- **State Management:** Zustand
- **Database & Auth:** Supabase
- **API Client:** Axios

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn
- Supabase account
- Python backend running (see python_services/)

### Installation

1. Install dependencies:

```bash
npm install
```

2. Copy `.env.example` to `.env.local` and fill in your environment variables:

```bash
cp .env.example .env.local
```

3. Run the development server:

```bash
npm run dev
```

4. Open [http://localhost:3000](http://localhost:3000) in your browser.

## Project Structure

```
├── app/                 # Next.js 14 app directory (routes & pages)
├── components/          # Reusable React components
├── config/              # Configuration files
├── context/             # React context providers
├── lib/                 # Utility functions & libraries
├── public/              # Static assets
├── python_services/     # Python backend services
├── store/               # Zustand state management
├── styles/              # Global styles & CSS modules
├── supabase/            # Supabase migrations & schemas
└── types/               # TypeScript type definitions
```

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run lint` - Run ESLint
- `npm run type-check` - Run TypeScript type checking

## Features

- 🤖 AI-powered content generation
- 📅 Weekly marketing workflow orchestration
- 🔄 Multi-platform content distribution
- 📱 Telegram approval interface
- 📊 Analytics dashboard
- 🎨 Media generation (images, videos, audio)
- 🌐 IP-rotated engagement network
- 🔐 Supabase authentication

## Learn More

See the root-level documentation for the complete technical blueprint and project proposal.
