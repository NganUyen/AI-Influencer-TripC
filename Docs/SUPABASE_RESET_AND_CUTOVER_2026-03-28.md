# Supabase Reset And Cutover

Date: 2026-03-28

## Summary

This document records the full reset and cutover of the customer-facing app
database onto the existing Supabase project.

End state:

- the Supabase app database was reset and rebuilt from the canonical snapshot
- the production app services now connect to Supabase through the session
  pooler
- the stack was redeployed successfully
- the bundled smoke test passed
- a DB-backed backend request succeeded after the cutover

## Why This Was Needed

The existing Supabase project database was in a legacy partial state that did
not match the current repo schema.

Problems observed before the reset:

- missing core tables such as `public.content`, `public.chatgpt_oauth_links`,
  and `public.analytics_events`
- legacy table shapes for app tables such as `campaigns` and `media_assets`
- later incremental migrations could not be safely applied on top of the old
  shape

Because a new Supabase project was not available, the existing project was
fully reset and rebuilt in place.

## Files Used

- `Project/supabase/reset_app_schema.sql`
- `Project/supabase/schema.sql`
- `Project/.env.production`
- `deploy/vps/deploy-production.sh`
- `deploy/vps/healthcheck.sh`

Related backup created during the cutover:

- `Project/.env.production.bak.20260327160647`

## What Was Done

### 1. Reset The App-Owned Public Schema

The reset helper was added and used to drop the app-owned tables and legacy
types from the `public` schema without touching Supabase-managed schemas like
`auth` and `storage`.

Reset artifact:

- `Project/supabase/reset_app_schema.sql`

This reset intentionally left these areas alone:

- `auth.users`
- storage bucket contents
- non-public Supabase-managed schemas

### 2. Rebuild The Database From The Canonical Snapshot

After the reset, the database was rebuilt from:

- `Project/supabase/schema.sql`

Important rule:

- after a full reset plus `schema.sql`, no additional repo migration file needed
  to be run immediately
- `20260327_supabase_canonical_consolidation.sql` is already reflected in the
  current steady-state snapshot

### 3. Update Production App DSNs

The app-facing DSNs in `Project/.env.production` were moved from local Docker
Postgres to Supabase.

Initial attempt:

- used the direct host form `db.<project-ref>.supabase.co`

Result:

- this failed from inside Docker because the direct host resolved to an
  IPv6-only address in this VPS/container network
- DB-backed code paths hit `Network is unreachable`

Final fix:

- switched `DATABASE_URL` and `CHATGPT_CONNECTOR_DATABASE_URL` to the Supabase
  session pooler DSN
- the working host is `aws-1-ap-northeast-1.pooler.supabase.com:5432`
- the actual password is intentionally not recorded in this document

Fields updated:

- `Project/.env.production`
  - `DATABASE_URL`
  - `CHATGPT_CONNECTOR_DATABASE_URL`

## Redeploy Sequence

The stack was redeployed with:

- `deploy/vps/deploy-production.sh`

After the pooler DSN was applied, the following app-facing containers were
recreated and came back successfully:

- `ai-influencer-backend`
- `ai-influencer-chatgpt-connector`
- `ai-influencer-temporal-worker`
- `ai-influencer-frontend`

The supporting service containers remained in place as expected:

- local `postgres` for service databases
- `redis`
- `temporal`
- `openclaw`
- `postiz`
- `growchief`

## Verification Performed

### Service-Level Verification

The bundled smoke script was run successfully:

- `deploy/vps/healthcheck.sh`

Checks that passed:

- docker services healthy
- public frontend, backend, and connector endpoints
- localhost admin endpoints
- Postiz API probe
- GrowChief API probe
- Telegram webhook readiness
- OpenClaw readiness

One transient issue occurred during verification:

- the first healthcheck attempt saw a `502`
- root cause was frontend startup timing while Next.js was still finishing its
  production build and startup
- once the frontend reached ready state, the healthcheck passed in full

### Database-Level Verification

These DB-facing checks succeeded after the pooler switch:

- `psql "$DATABASE_URL"` from inside the backend container connected
- `select current_database(), current_user;` returned `postgres|postgres`
- a DB-backed backend API request succeeded:
  - `GET /api/personas?user_id=00000000-0000-0000-0000-000000000001`
  - returned `200`

Confirmed core tables present in Supabase:

- `users`
- `content`
- `personas`
- `media_assets`
- `chatgpt_oauth_links`
- `analytics_events`
- `telegram_link_tokens`
- `telegram_user_links`

## Current Runtime State

The customer-facing app runtime is now using Supabase Postgres through the
session pooler.

The local Docker Postgres container still exists and this is expected. It
continues to support service-local databases and surrounding infrastructure.

Current intended topology:

- Supabase Postgres:
  - customer-facing app tables
- local Docker Postgres:
  - service databases and supporting stack pieces that still depend on the
    local Compose topology

## Remaining Manual Items

The core cutover is complete. These are only optional cleanup items depending
on the intended business state:

- delete Supabase Auth users manually if a truly blank auth state is desired
- remove old objects from the `media` bucket manually if a truly blank storage
  state is desired
- create a fresh real user and run a product-level check:
  - signup/signin
  - persona creation
  - media upload
  - Telegram link flow

## Important Notes For Future Work

- for this VPS, the Supabase direct database host was not usable from Docker
  because it resolved to IPv6 only
- the correct connection strategy here is the Supabase session pooler
- if the project is reset again in the future, use:
  1. `Project/supabase/reset_app_schema.sql`
  2. `Project/supabase/schema.sql`
  3. update DSNs if needed
  4. `deploy/vps/deploy-production.sh`
  5. `deploy/vps/healthcheck.sh`
