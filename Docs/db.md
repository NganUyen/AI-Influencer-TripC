# Database Model

Last verified: 2026-04-18 (UTC)

This repo now uses a Supabase-centered application database model.

## Runtime Contract

- Supabase Postgres is the canonical database for customer-facing application tables
- Supabase Auth remains the identity provider for customer sign-in and JWT identity
- local Docker Postgres in the production stack is reserved for service databases such as `postiz`, `growchief`, and Temporal internals
- checked-in SQL under `Project/supabase/` remains the schema source, but ordered migrations are the authority for long-lived environments

For exact DDL, use:

- `Project/supabase/migrations/*.sql` for migration authority
- `Project/supabase/schema.sql` for the latest disposable bootstrap snapshot
- `Project/supabase/migrations/latest.sql` only as a psql-oriented convenience wrapper around `schema.sql`

## What Lives In The Canonical App Database

`DATABASE_URL` points at the canonical application database. Unless intentionally overridden, `CHATGPT_CONNECTOR_DATABASE_URL` points there too.

First-party application state lives in that database, including:

- `public.users` and customer ownership anchors
- brand setup and `public.customer_ai_backbone_settings`
- connected social accounts and ChatGPT connector identity links
- campaigns, content, approvals, workflows, and assistant state
- personas, media assets, analytics, and Telegram ownership links

Local service databases still exist for:

- `postiz`
- `growchief`
- Temporal internals

Those databases are not the customer-facing product source of truth.

## SQL Sources

The checked-in SQL lives under `Project/supabase/`:

- `migrations/*.sql`: ordered upgrades for existing databases and the source of truth for long-lived environments
- `schema.sql`: rebuilt steady-state bootstrap snapshot for empty databases
- `migrations/latest.sql`: disposable wrapper for psql-based snapshot use
- `seed.sql`: optional disposable seed data
- `README.md`: workflow notes

## Auth And Ownership Model

Supabase Auth is the identity provider, but the repo keeps its own `public.users` row as the relational anchor.

The current flow is:

1. the frontend gets a Supabase session
2. the backend validates the bearer token against Supabase
3. Supabase-side trigger sync keeps `public.users` aligned with `auth.users`
4. application tables reference the customer UUID through `user_id`
5. row-level security policies use `auth.uid()` ownership checks

`schema.sql` still includes an `auth.uid()` compatibility shim so the bootstrap works on plain Postgres as well as Supabase-hosted Postgres.

The core ownership rule is:

- `user_id` is authoritative for customer-owned rows
- `owner_key` is auxiliary source context, mainly for Telegram-originated media/persona flows
- new production-like code paths must not invent synthetic customer users when ownership is missing

## Table Inventory By Domain

### Identity And Setup

- `public.users`
- `public.brand_profiles`
- `public.customer_ai_backbone_settings`
- `public.chatgpt_oauth_links`
- `public.telegram_link_tokens`
- `public.telegram_user_links`

### Campaigns, Content, And Approval

- `public.campaigns`
- `public.content`
- `public.approvals`
- `public.postiz_schedules`
- `public.video_render_plans`

### Assistant Experience

- `public.assistant_threads`
- `public.assistant_messages`
- `public.assistant_artifacts`

### Personas, Accounts, And Operations

- `public.personas`
- `public.social_accounts`
- `public.media_assets`
- `public.workflows`
- `public.engagement_actions`
- `public.engagement_action_logs`
- `public.analytics_events`
- `public.telegram_subscribers`

## Storage Contract

Generated media lives in the public Supabase Storage bucket `media`.

The canonical object path for new writes is:

`users/<user_id>/personas/<persona_id>/<asset_kind>/<yyyy-mm>/<file>`

Legacy top-level prefixes such as `image/`, `video/`, `persona/`, and `smoke_test/` should be treated as cleanup/backfill inventory, not as valid new production destinations.

`public.media_assets` is the canonical registry for:

- `user_id`
- `persona_id`
- `bucket_name`
- `storage_path`
- `storage_provider`
- lifecycle/status metadata

Operational notes:

- new writes should carry a real `user_id` whenever the customer owner is known
- Telegram-originated persona/media flows should also pass `owner_key=telegram:<chat_id>` and `persona_id` so media lands in the correct owner/persona scope
- if owner context cannot be resolved safely, the system may skip writing a misleading `media_assets` row rather than inventing ownership
- provider URL fallback is a valid degraded mode when storage persistence fails, but it is not the steady-state source of truth; the steady-state source of truth remains the stored object plus the `public.media_assets` row

## RLS Model

Customer-facing tables use RLS tied to `auth.uid()` ownership checks.

The default pattern is:

- `user_id UUID REFERENCES public.users(id)` for directly customer-owned tables
- RLS enabled
- policy bound to `auth.uid() = user_id`

For indirect ownership tables such as assistant messages or Postiz schedules, policies follow the owning parent row.

## Bootstrap And Migration Workflow

Fresh disposable local bootstrap:

```bash
cd /opt/ai-influencer/repo
docker compose up -d postgres
docker exec -i ai-influencer-postgres psql -U postgres -d ai_influencer < Project/supabase/schema.sql
```

Production/staging migration path:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/apply-db-migrations.sh
```

That script now connects directly to `DATABASE_URL`, so in staging/production it should target Supabase Postgres.

Rules of thumb:

- use ordered migration files for long-lived environments
- use `schema.sql` only for empty-database bootstrap
- skip `latest.sql` during production-style migration runs
- back up the canonical app database before schema-changing deploys

## Recent Operational Data Corrections

### 2026-04-20 (UTC) - Global Persona Ownership Correction

Issue:

- `global-cn-wei` and `global-in-arjun` did not appear under `System Personas`
- both rows existed in `public.personas`, but their `user_id` had drifted to `ecfafcde-45c3-5a00-9711-34246e451cf7`
- the product groups system personas under the reserved system owner `00000000-0000-0000-0000-000000000001`

Live data correction applied:

```sql
UPDATE public.personas
SET user_id = '00000000-0000-0000-0000-000000000001',
    updated_at = NOW()
WHERE persona_id IN ('global-cn-wei', 'global-in-arjun')
  AND user_id = 'ecfafcde-45c3-5a00-9711-34246e451cf7';
```

Expected result after correction:

- `Wei Chen` and `Arjun Sharma` return to the shared system-persona pool
- the canonical global set becomes:
  `global-us-alex`, `global-cn-wei`, `global-ru-natasha`, `global-in-arjun`, `global-mx-valeria`

Verification query:

```sql
SELECT persona_id, display_name, user_id, status
FROM public.personas
WHERE persona_id IN (
  'global-us-alex',
  'global-cn-wei',
  'global-ru-natasha',
  'global-in-arjun',
  'global-mx-valeria'
)
ORDER BY persona_id;
```

Operational note:

- this was a live data correction, not a schema migration
- backend and frontend were also hardened so reserved `global-*` personas still classify as system personas if ownership drifts again

## Change Process

When the data model changes:

1. add a new ordered migration in `Project/supabase/migrations/`
2. fold the steady-state result into `Project/supabase/schema.sql`
3. update app services and tests when contracts changed
4. update docs when the runtime or operational model changed

## Bottom Line

The default assumption for new work is:

- Supabase Postgres is the canonical app database
- local Docker Postgres is only for service databases in production
- ownership is UUID-based and enforced through RLS
- new production data must resolve to a real `public.users` owner
