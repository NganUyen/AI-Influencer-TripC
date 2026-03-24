# Database SQL Base

This directory holds the checked-in SQL source for the application database.

The current repo intentionally splits responsibilities:

- app data lives in PostgreSQL and is accessed through `DATABASE_URL`
- customer sign-in and session validation use Supabase Auth
- generated media defaults to a public Supabase Storage bucket named `ai-influencer-media`
- the same SQL assets can be used against local Postgres or a Supabase-hosted Postgres database

## Files

```text
supabase/
|-- schema.sql                    Full base schema for a fresh database
|-- seed.sql                      Optional development seed data
`-- migrations/
    |-- 20260310_initial_schema.sql
    |-- 20260316_mvp_integrations.sql
    |-- 20260320_chatgpt_connector_links.sql
    |-- 20260324_customer_product_v1.sql
    |-- 20260324_live_db_backfill.sql
    `-- 20260324_zz_supabase_storage_bucket.sql
```

## Runtime Model

Use this mental model when wiring environments:

- `DATABASE_URL` points at the primary application database
- `SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_URL`, and related keys are still required for customer auth/session flows
- `SUPABASE_STORAGE_BUCKET` defaults to `ai-influencer-media`; if you change it, create the bucket to match and update your env
- `schema.sql` includes an `auth.uid()` compatibility shim so the same base SQL works on plain Postgres and on Supabase-hosted Postgres
- `migrations/*.sql` are for upgrading existing databases; `schema.sql` is for bootstrapping a fresh one

## Fresh Local Postgres

The local Docker stack bootstraps `schema.sql` automatically on the first run of an empty `postgres_data` volume.

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

- treat `schema.sql` as the empty-database bootstrap
- use the migration files for long-lived databases instead of replaying the base file on top of active data

## Existing Local Or Production Database

For an already-initialized database, apply the incremental migrations in order.

Production uses the helper script documented in the runbook:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/apply-db-migrations.sh
```

For a local direct-Postgres database, apply the same files with `psql` in sorted order.

## Supabase-Hosted Postgres

If you want Supabase to host the application tables as well as auth:

1. start from an empty project database
2. apply `schema.sql`
3. apply the incremental migrations for any environments created before the latest base file
4. keep the frontend/backend auth env vars pointed at that Supabase project

When the project is actually hosted on Supabase, the checked-in migration
`migrations/20260324_zz_supabase_storage_bucket.sql` also provisions the default
public media bucket used by the backend upload pipeline. The migration is a no-op
on plain PostgreSQL because the `storage` schema does not exist there.

You can use Supabase CLI if you prefer:

```bash
supabase db push
```

Or run the SQL directly in the Supabase SQL editor.

## Development Seed Contents

`seed.sql` now matches the current product shape and includes:

- a demo customer user
- a completed brand profile
- a demo persona registry record
- a connected social account
- an assistant thread, messages, and artifact
- a draft campaign and scheduled content row
- a Telegram subscriber fixture

It is intended only for disposable local or staging-style environments.
