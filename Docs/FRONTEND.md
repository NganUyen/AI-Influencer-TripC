# Frontend

Last verified: 2026-03-24 (UTC)

The frontend is a Next.js App Router application that serves both the customer workspace and the internal operator console.

## Stack

- Next.js App Router
- TypeScript
- Tailwind CSS
- Zustand
- Axios
- Supabase browser auth helpers
- Jest + Testing Library

## Main Routes

- `/`: product landing page
- `/auth`: customer sign-in and sign-up
- `/dashboard`: customer workspace
- `/ops/login`: operator login
- `/ops`: operator console
- `/app/api/*`: proxy routes that shield the browser from direct FastAPI access

## Customer Surface

The customer app is centered on `components/customer-dashboard.tsx`.

Implemented panels and actions:

- brand profile editing
- social account list plus OAuth start/callback scaffolding
- assistant thread creation and message exchange
- AI backbone configuration, including ChatGPT connector link state
- campaign creation
- campaign approval or rejection
- campaign launch
- customer content listing
- customer approval listing

Core backend calls made by the dashboard:

- `/api/customer/brand`
- `/api/customer/social-accounts`
- `/api/customer/assistant/threads`
- `/api/customer/campaigns`
- `/api/customer/approvals`
- `/api/customer/content`
- `/api/customer/ai-backbone`

## Internal Ops Surface

The ops app is centered on `components/ops-console.tsx`.

Implemented views and actions:

- recent workflow list
- workflow status polling
- approval submission for workflows
- content retry actions
- content stats
- analytics summary
- quota summary

Core backend calls made by the ops console:

- `/api/workflows/list`
- `/api/workflows/status/{workflowId}`
- `/api/workflows/approve/{workflowId}`
- `/api/content/stats`
- `/api/content/retry/{contentId}`
- `/api/analytics/summary`
- `/api/quota/summary`

## Auth Model

### Customer auth

- handled by `store/customer-auth-store.ts`
- backed by Supabase browser sessions
- stores the current user and access token
- the access token is forwarded to the Next.js customer proxy and then to FastAPI

### Operator auth

- handled by `store/auth-store.ts`
- uses a token-based local login model for the internal console
- the stored token is attached by `lib/api-client.ts` as the `Authorization` header
- Next.js admin proxy routes validate that token against `APP_ADMIN_TOKEN`

## Proxy Layer

The browser generally talks to Next.js, not directly to FastAPI.

### Customer proxy

`app/api/customer/[...path]/route.ts`:

- forwards `Authorization` and `Accept` headers
- preserves redirect `Location` headers for OAuth callback flows
- proxies `GET`, `POST`, `PUT`, and `PATCH`

### Ops/admin proxies

Routes like `app/api/workflows/list/route.ts` and `app/api/content/stats/route.ts`:

- require admin auth at the Next.js layer
- inject `x-internal-api-token` for backend internal routes
- use structured fallbacks for read-only endpoints when the backend is unavailable

That fallback contract includes an `_meta` block with:

- `backend_available`
- `reason`
- `message`
- optional `backend_status`

## Frontend State And Helpers

- `lib/api-client.ts`: Axios client for internal ops traffic
- `lib/customer-api.ts`: fetch helper for customer traffic
- `lib/supabase.ts`: Supabase client bootstrap
- `store/customer-auth-store.ts`: customer auth/session state
- `store/auth-store.ts`: operator auth state
- `store/content-store.ts`: workflow/content state model used by the ops surface
- `config/features.ts`: frontend feature flags
- `config/platforms.ts`: supported platform metadata
- `config/constants.ts`: shared app constants and API defaults

## Important Frontend Constraints

- the customer dashboard assumes Supabase browser config is present for real auth
- the ops surface assumes `APP_ADMIN_TOKEN` is configured
- richer customer publishing still depends on backend/provider readiness
- some flows are intentionally scaffolded for future live OAuth and publishing integrations

## Tests

Current frontend tests cover:

- customer dashboard rendering
- API proxy routes
- Zustand content-store behavior

Run them with:

```bash
cd /opt/ai-influencer/repo/Project
npm test
```
