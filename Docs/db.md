# Database Model

Last verified: 2026-03-24 (UTC)

This repo now uses a one-database-plus-Supabase-Auth model.

The important split is:

- one canonical PostgreSQL application database: `ai_influencer`
- Supabase Auth for customer sign-in, session validation, and JWT identity
- checked-in SQL in `Project/supabase/` as the source of truth for schema and migrations

This document is an architecture and operations summary. It is not the canonical DDL. For exact table definitions, use `Project/supabase/schema.sql` and `Project/supabase/migrations/*.sql`.

## Canonical Runtime Contract

Use this mental model when wiring or debugging environments:

- `DATABASE_URL` points at the primary application database
- `CHATGPT_CONNECTOR_DATABASE_URL` points at the same database unless intentionally overridden
- `SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_URL`, and the related keys are still required for customer auth/session flows
- Supabase is not the primary app data API in this setup; PostgreSQL is

In other words, customer identity comes from Supabase Auth, but the product's operational state lives in the app database.

## What "One Database" Means Here

For first-party product data, there is one source of truth: the `ai_influencer` PostgreSQL database.

That includes:

- customer records in `public.users`
- customer brand setup and AI settings
- campaigns, content, approvals, and publishing state
- assistant threads and artifacts
- personas, social accounts, workflows, and Telegram subscriber state

The repo still boots a few service-specific databases for third-party or infrastructure components:

- `postiz`
- `growchief`
- Temporal-related stores

Those are service internals, not the canonical application data model. When we say "one DB" in project docs, we mean one primary app database for our own product state.

## Canonical SQL Sources

The checked-in SQL lives under `Project/supabase/`:

- `schema.sql`: full bootstrap schema for a fresh empty app database
- `migrations/*.sql`: incremental upgrades for existing databases
- `seed.sql`: optional disposable dev/staging seed data
- `README.md`: current database workflow notes

The local and production Docker stacks mount the bootstrap schema into Postgres init:

- `docker/postgres/init/00_create_service_databases.sql`
- `Project/supabase/schema.sql`

That means a brand-new `postgres_data` volume gets the app schema automatically on first boot.

## Auth And Identity Model

Supabase Auth remains the customer identity provider, but the app keeps its own `public.users` table as the relational anchor for product data.

The flow is:

1. the frontend obtains a Supabase session
2. the backend validates the bearer token against Supabase Auth
3. the backend upserts the corresponding row in `public.users`
4. application tables reference that UUID through `user_id`
5. row-level security policies use `auth.uid()` to restrict access to a customer's own rows

Important implementation detail:

- `Project/supabase/schema.sql` includes an `auth.uid()` compatibility shim

That shim lets the same schema work in both modes:

- plain PostgreSQL with app-managed JWT claims
- Supabase-hosted Postgres with the native `auth` schema

So the repo can use Supabase Auth without requiring Supabase to host all application tables.

## Current Application Schema Shape

The current schema is centered around these domains.

### Customer Identity And Setup

- `public.users`: app-local customer profile row keyed by the auth UUID
- `public.brand_profiles`: customer product, audience, cadence, and onboarding state
- `public.customer_ai_backbone_settings`: platform-managed vs customer-managed AI access mode, connector session metadata, and related settings
- `public.chatgpt_oauth_links`: ChatGPT connector identity/session link records

### Strategy, Content, And Approval

- `public.campaigns`: campaign plans, approval state, workflow linkage, and target platforms
- `public.content`: generated or drafted customer content
- `public.approvals`: review trail for workflow/content approvals
- `public.postiz_schedules`: publishing state and Postiz schedule linkage

### Assistant Experience

- `public.assistant_threads`
- `public.assistant_messages`
- `public.assistant_artifacts`

These tables back the customer-facing strategy/chat surface.

### Personas, Accounts, And Operations

- `public.personas`: persona registry used by the newer persona API/service layer
- `public.social_accounts`: connected customer accounts plus connection and token metadata
- `public.media_assets`: stored media references
- `public.workflows`: orchestration state
- `public.engagement_actions`: direct engagement tracking
- `public.engagement_action_logs`: provider/job-level engagement logs
- `public.analytics_events`: content analytics event storage
- `public.telegram_subscribers`: Telegram webhook/operator subscriber state

## RLS Model

Row-level security is enabled on the customer-facing tables.

The common rule is simple:

- a customer can only read or mutate rows whose `user_id` (or owning relationship) matches `auth.uid()`

That policy pattern is already baked into `schema.sql` and the later migration files. If you add a new customer-owned table, it should follow the same structure:

- foreign key to `public.users(id)` when appropriate
- RLS enabled
- a policy tied to `auth.uid()`

## Bootstrap And Migration Workflow

Fresh local bootstrap on an empty `postgres_data` volume happens automatically:

```bash
cd /opt/ai-influencer/repo
docker compose up -d postgres
```

If you want to apply the bootstrap schema manually to an empty database:

```bash
cd /opt/ai-influencer/repo
docker exec -i ai-influencer-postgres psql -U postgres -d ai_influencer < Project/supabase/schema.sql
```

Optional seed:

```bash
cd /opt/ai-influencer/repo
docker exec -i ai-influencer-postgres psql -U postgres -d ai_influencer < Project/supabase/seed.sql
```

Production migration path:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/apply-db-migrations.sh
```

Rules of thumb:

- use `schema.sql` for empty-database bootstrap
- use `migrations/*.sql` for upgrades on long-lived environments
- back up Postgres before schema-changing deploys
- do not treat `Docs/db.md` as the place to define schema changes

## Change Process

When the data model changes:

1. add or update a migration under `Project/supabase/migrations/`
2. fold the latest shape back into `Project/supabase/schema.sql`
3. update `seed.sql` if local fixtures depend on the new columns/tables
4. update app types or service code if the contract changed
5. update this doc only if the architecture or operating model changed

## Bottom Line

The current architecture is:

- one primary PostgreSQL database for first-party application data
- Supabase Auth for customer authentication and identity
- shared UUID-based ownership with RLS enforced through `auth.uid()`

That is the model new schema work should assume unless the architecture changes again.
