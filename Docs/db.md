# Database Model

Last verified: 2026-03-24 (UTC)

This repo uses a one-database-plus-Supabase-Auth model.

## Runtime Contract

- one canonical PostgreSQL application database: `ai_influencer`
- Supabase Auth for customer sign-in, session validation, and JWT identity
- checked-in SQL in `Project/supabase/` as the source of truth for schema and migrations

This document is an architecture and operations summary. For exact DDL, use `Project/supabase/schema.sql` and `Project/supabase/migrations/*.sql`.

## What Lives In The Primary App Database

`DATABASE_URL` points at the primary application database. Unless intentionally overridden, `CHATGPT_CONNECTOR_DATABASE_URL` points there too.

First-party application state lives in that database, including:

- customers and brand setup
- AI backbone settings
- connected social accounts and token references
- campaigns, content, approvals, and workflows
- assistant threads, messages, and artifacts
- personas, media assets, analytics, and Telegram subscriber state

The repo also creates service-specific databases for:

- `postiz`
- `growchief`
- Temporal internals

Those are service databases, not the canonical product data model.

## SQL Sources

The checked-in SQL lives under `Project/supabase/`:

- `schema.sql`: full bootstrap schema for a fresh database
- `migrations/*.sql`: incremental upgrades for existing databases
- `seed.sql`: optional disposable seed data
- `README.md`: SQL workflow notes

The compose stacks mount both:

- `docker/postgres/init/00_create_service_databases.sql`
- `Project/supabase/schema.sql`

That means a fresh Postgres volume gets the base app schema automatically.

## Auth And Ownership Model

Supabase Auth is the identity provider, but the repo keeps its own `public.users` row as the relational anchor.

Typical flow:

1. the frontend gets a Supabase session
2. the backend validates the bearer token against Supabase
3. the backend upserts `public.users`
4. application tables reference the user UUID through `user_id`
5. row-level security policies use `auth.uid()` ownership checks

`schema.sql` includes an `auth.uid()` compatibility shim so the same SQL works on plain Postgres and on Supabase-hosted Postgres.

## Table Inventory By Domain

### Identity And Setup

- `public.users`: app-local customer row keyed by auth UUID
- `public.brand_profiles`: brand, audience, cadence, and onboarding state
- `public.customer_ai_backbone_settings`: platform-managed versus customer-managed AI access settings
- `public.chatgpt_oauth_links`: connector identity and session link state

### Campaigns, Content, And Approval

- `public.campaigns`: campaign plans, workflow linkage, approval state, target platforms, and artifacts
- `public.content`: generated or drafted content
- `public.approvals`: approval records and feedback
- `public.postiz_schedules`: schedule and publishing bridge state

### Assistant Experience

- `public.assistant_threads`
- `public.assistant_messages`
- `public.assistant_artifacts`

These back the customer-facing strategy and assistant workflow.

### Personas, Accounts, And Operations

- `public.personas`: persona registry
- `public.social_accounts`: connected account metadata, token refs, scopes, and connection health
- `public.media_assets`: stored media references
- `public.workflows`: orchestration state plus approval metadata
- `public.engagement_actions`: engagement tasks
- `public.engagement_action_logs`: engagement execution logs
- `public.analytics_events`: analytics event storage
- `public.telegram_subscribers`: Telegram subscription and callback state

## RLS Model

Row-level security is enabled on the customer-facing tables.

The default pattern is:

- foreign key to `public.users(id)` where appropriate
- RLS enabled
- policies tied to `auth.uid()`

If you add a new customer-owned table, follow that same pattern.

## Bootstrap And Migration Workflow

Fresh local bootstrap on an empty volume:

```bash
cd /opt/ai-influencer/repo
docker compose up -d postgres
```

Manual bootstrap on an empty database:

```bash
cd /opt/ai-influencer/repo
docker exec -i ai-influencer-postgres psql -U postgres -d ai_influencer < Project/supabase/schema.sql
```

Optional seed data:

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

- use `schema.sql` only for empty-database bootstrap
- use `migrations/*.sql` for upgrades on long-lived environments
- back up Postgres before schema-changing deploys
- keep `schema.sql` in sync with the latest migrated shape

## Change Process

When the data model changes:

1. add or update a migration in `Project/supabase/migrations/`
2. fold the new steady-state shape back into `Project/supabase/schema.sql`
3. update `seed.sql` if fixtures depend on the change
4. update app types, services, and tests if contracts changed
5. update docs only when the architecture or operational model changed

## Bottom Line

The database model to assume today is:

- PostgreSQL is the primary first-party application store
- Supabase Auth provides customer identity
- ownership is UUID-based and enforced through RLS

That is the default assumption new schema work should follow.
