# Database SQL Base

This directory holds the checked-in SQL source for the application database.

The current repo intentionally splits responsibilities:

- customer-facing app data lives in PostgreSQL and is accessed through `DATABASE_URL`
- staging/production should point `DATABASE_URL` at Supabase Postgres
- customer sign-in and session validation use Supabase Auth
- generated media defaults to a public Supabase Storage bucket named `media`
- local plain Postgres remains useful for disposable dev/CI bootstraps

## Files

```text
supabase/
|-- schema.sql                    Disposable full bootstrap snapshot
|-- seed.sql                      Optional development seed data
`-- migrations/
    |-- 20260310_initial_schema.sql
    |-- 20260316_mvp_integrations.sql
    |-- 20260320_chatgpt_connector_links.sql
    |-- 20260324_customer_product_v1.sql
    |-- 20260324_live_db_backfill.sql
    |-- 20260324_zz_customer_ai_backbone_settings.sql
    |-- 20260324_zz_supabase_storage_bucket.sql
    |-- 20260326_persona_media_contract.sql
    |-- 20260326_personas_user_scoped_unique.sql
    |-- 20260326_telegram_owner_links_and_avatar_assets.sql
    |-- 20260327_supabase_canonical_consolidation.sql
    `-- latest.sql
```

## Runtime Model

Use this mental model when wiring environments:

- `DATABASE_URL` points at the canonical application database
- in staging/production that canonical app database should be Supabase Postgres
- `SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_URL`, and related keys are still required for customer auth/session flows
- `SUPABASE_STORAGE_BUCKET` must be `media` in production-like environments
- ordered `migrations/*.sql` files are the source of truth for long-lived environments
- `schema.sql` and `migrations/latest.sql` are disposable snapshot/bootstrap assets rebuilt to the latest migrated shape
- new canonical media writes must use `users/<user_id>/personas/<persona_id>/<asset_kind>/<yyyy-mm>/<file>`
- `public.users` is synced from `auth.users` by a Supabase-side trigger in the latest consolidation migration

## Fresh Local Postgres

Disposable local Postgres can still bootstrap from `schema.sql`.

If you want to apply the schema yourself to an empty local database:

```bash
cd /opt/ai-influencer/repo
docker compose up -d postgres
docker exec -i ai-influencer-postgres psql -U postgres -d ai_influencer < Project/supabase/schema.sql
```

Optional development seed:

```bash
cd /opt/ai-influencer/repo
docker exec -i ai-influencer-postgres psql -U postgres -d ai_influencer < Project/supabase/seed.sql
```

Important:

- treat `schema.sql` as an empty-database bootstrap only
- do not replay `schema.sql` on top of a long-lived environment
- do not use `migrations/latest.sql` as a production migration file

## Existing Local Or Production Database

For an already-initialized database, apply the incremental migrations in order.

Production uses the helper script documented in the runbook:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/apply-db-migrations.sh
```

The helper script now connects directly to `DATABASE_URL` with `psql`, so in staging/production that means Supabase Postgres.

It automatically skips:

- `20260310_initial_schema.sql`
- `latest.sql`

## Supabase-Hosted Postgres

Supabase-hosted Postgres is now the intended home for the customer-facing app tables in staging/production.

For a fresh Supabase project database:

1. start from an empty project database
2. apply `schema.sql`
3. point `DATABASE_URL` at that Supabase Postgres instance
4. keep the frontend/backend auth env vars pointed at the same Supabase project

When the project is actually hosted on Supabase, the checked-in storage migrations provision the public media bucket used by the backend upload pipeline. The preferred bucket is `media`. These storage migrations are no-ops on plain PostgreSQL because the `storage` schema does not exist there.

You can use Supabase CLI if you prefer:

```bash
supabase db push
```

`migrations/latest.sql` is only a psql-oriented convenience snapshot that delegates to `schema.sql`; do not paste it into the Supabase SQL editor.

## Development Seed Contents

`seed.sql` matches the current product shape and includes:

- a demo customer user
- a completed brand profile
- a demo persona registry record
- a connected social account
- an assistant thread, messages, and artifact
- a draft campaign and scheduled content row
- a Telegram subscriber fixture

It is intended only for disposable local or staging-style environments.
