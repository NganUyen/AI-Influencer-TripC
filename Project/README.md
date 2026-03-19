# AI Influencer Factory Frontend

This directory contains the Next.js frontend for the project dashboard, workflow controls, and API proxy routes used by the UI.

## Scope

Current frontend surfaces:

- `/` landing page
- `/dashboard` workflow monitor and approval UI
- `/auth` sign-in screen shell
- `app/api/...` proxy routes for workflow and content requests

The dashboard is the most functional area today. It polls workflow status, reads content summary data, and can send approval or rejection actions for workflows waiting on human review.

## Stack

- Next.js 14 App Router
- TypeScript
- Tailwind CSS
- Zustand
- Axios
- Jest + Testing Library

## Prerequisites

- Node.js 18+
- npm
- A running backend at `http://localhost:8000` or another configured URL

## Environment Variables

Copy `Project/.env.example` to `Project/.env.local` and adjust as needed.

Frontend-relevant values include:

- `NEXT_PUBLIC_API_URL`
- `PYTHON_BACKEND_URL`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_SECRET_KEY`

Notes:

- `lib/api-client.ts` uses `NEXT_PUBLIC_API_URL` as the Axios base URL and falls back to `http://localhost:3000`.
- `app/api/_helpers/backend.ts` uses `PYTHON_BACKEND_URL` for server-side proxying to the FastAPI backend.
- `lib/supabase.ts` accepts either the `NEXT_PUBLIC_*` names or the plain `SUPABASE_*` aliases, so the browser client stays compatible with the backend env layout.
- If you want the browser to use the Next.js proxy routes, keep requests relative or point `NEXT_PUBLIC_API_URL` at the frontend origin.
- `DATABASE_URL` is still required for any direct Postgres access from the Python services; the Supabase API keys do not replace it.

## Install and Run

```bash
cd Project
npm install
npm run dev
```

Open `http://localhost:3000`.

## Useful Commands

```bash
cd Project
npm run dev
npm run build
npm run start
npm run lint
npm run type-check
npm test
```

## Project Structure

```text
Project/
|-- app/                 App Router pages and Next.js API routes
|-- components/          Shared UI components
|-- config/              Constants, feature flags, platform metadata
|-- context/             React context providers
|-- lib/                 API client, Supabase client, utilities
|-- public/              Static assets
|-- store/               Zustand stores
|-- styles/              Global styling
|-- supabase/            Database schema and migration assets
`-- types/               Shared TypeScript types
```

## Testing

The frontend currently includes:

- dashboard rendering and approval action tests
- Next.js API proxy route tests

Run them with:

```bash
cd Project
npm test
```

## Current Limitations

- The auth page is presentational and not yet wired into a full auth flow.
- The dashboard shows workflow/content status but richer scheduled-post and analytics detail is still limited.
- Some backend-backed features depend on external services and may not work without the full local stack.

## Related Docs

- `../README.md`
- `python_services/README.md`
- `supabase/README.md`
