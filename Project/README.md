# AI Influencer Factory Frontend

This directory contains the Next.js application for both customer-facing and internal operator workflows.

## Current Frontend Surface

Implemented routes and UI areas:

- `/` landing page describing the product split
- `/auth` customer sign-in flow
- `/dashboard` customer workspace
- `/ops/login` operator login
- `/ops` internal console
- `app/api/...` proxy routes for backend and customer API traffic

The customer workspace is now the primary product surface. It includes:

- brand onboarding and profile editing
- official social account connection flow scaffolding
- persistent assistant threads and artifacts
- campaign draft, approval, and launch actions
- customer content and approval views

The ops console remains the internal surface for:

- workflow monitoring
- approval handling
- publish retry actions
- analytics summary
- quota visibility

## Stack

- Next.js App Router
- TypeScript
- Tailwind CSS
- Zustand
- Axios
- Jest + Testing Library

## Environment Variables

Copy `Project/.env.example` to `Project/.env.local` and fill in the values needed for your environment.

Most important frontend-side values:

- `NEXT_PUBLIC_API_URL`
- `PYTHON_BACKEND_URL`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_STORAGE_BUCKET`
- `STORAGE_PROVIDER`
- `APP_ADMIN_TOKEN`
- `INTERNAL_API_TOKEN`

Notes:

- `lib/api-client.ts` is used by the internal ops console and backend proxy routes.
- `lib/customer-api.ts` is used by the customer dashboard.
- customer auth/session resolution depends on the Supabase-related env values plus the backend customer auth service.
- ordered files in `Project/supabase/migrations/` are the migration authority; `Project/supabase/schema.sql` is the rebuilt bootstrap snapshot for empty databases, while Supabase handles customer auth/session and the default media storage bucket.
- the browser should usually talk to the Next.js app, not directly to FastAPI.

## Install And Run

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

Production packaging notes:

- `Dockerfile.frontend` now emits a multi-stage standalone runtime image for production.
- local development still uses the `dev` Docker target through `docker-compose.yml`.

## Project Structure

```text
Project/
|-- app/                 Routes and Next.js API handlers
|-- components/          Customer and ops UI
|-- config/              Feature flags and platform metadata
|-- lib/                 API clients and helpers
|-- store/               Zustand stores
|-- supabase/            Base SQL, migrations, and dev seed data
`-- types/               Shared frontend types
```

## Tests

Current frontend coverage includes:

- customer dashboard rendering
- API proxy routes
- Zustand content-store behavior

Run them with:

```bash
cd Project
npm test
```

## Current Limitations

- real customer OAuth connections still depend on external provider app registration and secrets
- some customer publishing flows still route through the internal Postiz-backed execution layer
- richer customer analytics and deeper scheduled-content management are still thinner than the core planning/review flow

## Related Docs

- [../Docs/README.md](../Docs/README.md)
- [../Docs/START_HERE.md](../Docs/START_HERE.md)
- [../Docs/CURRENT_REPO_STATUS.md](../Docs/CURRENT_REPO_STATUS.md)
- [../Docs/ARCHITECTURE.md](../Docs/ARCHITECTURE.md)
- [../Docs/REPOSITORY_MAP.md](../Docs/REPOSITORY_MAP.md)
- [../Docs/FRONTEND.md](../Docs/FRONTEND.md)
- [../Docs/BACKEND_API.md](../Docs/BACKEND_API.md)
- [../Docs/WORKFLOWS_AND_AUTOMATION.md](../Docs/WORKFLOWS_AND_AUTOMATION.md)
- [../Docs/INTEGRATIONS.md](../Docs/INTEGRATIONS.md)
- [../Docs/db.md](../Docs/db.md)
- [../Docs/ENVIRONMENT_REFERENCE.md](../Docs/ENVIRONMENT_REFERENCE.md)
- [python_services/README.md](./python_services/README.md)
