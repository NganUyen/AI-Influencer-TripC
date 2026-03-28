# 2026-03-28 Docker Optimization And Deploy Branch Rollout

Last updated: 2026-03-28 08:37:41 UTC

This note records the Docker footprint reduction work, the production rollout that followed, the fixes required during rollout, and the later review/push of the remaining local Supabase/media changes.

## Scope

This work covered four related tracks:

1. converting production delivery from VPS-side Docker builds to pull-only GHCR images
2. shrinking the frontend and Python service images with multi-stage builds and dependency splitting
3. recovering the live VPS from critical disk pressure and completing a healthy production deploy
4. reviewing the remaining modified/untracked local files and pushing the important ones to `deploy`

## Commit Timeline

- `43b0d8b` `Optimize production Docker delivery pipeline`
- `7899961` `Enable deploy branch image publishing`
- `c26aaff` `Fix CI env for production image publishing`
- `6c6b258` `Use backend smoke suite for image publishing`
- `77a5fa1` `Fix slim API runtime imports`
- `bac5fa2` `Tighten Supabase ownership and media migration flow`

At the time this document was written:

- live production was running the custom service images tagged with `77a5fa1e34044211d0ff073808ab78c5240b3800`
- `origin/deploy` had advanced to `bac5fa2`

## Repo Changes Introduced

### Docker Delivery And Image Size Work

The initial Docker optimization implementation introduced:

- production compose changes in `docker-compose.production.yml` so custom services pull GHCR images instead of building on-host
- a pull-first deploy path in `deploy/vps/deploy-production.sh`
- weekly Docker cleanup support in `deploy/vps/docker-cleanup.sh`, `deploy/vps/install-docker-maintenance-timer.sh`, and the accompanying systemd unit/timer
- `.dockerignore` coverage for the repo, frontend, and Python service build contexts
- a standalone multi-stage Next.js production image in `Project/Dockerfile.frontend`
- split Python dependency sets and multi-stage runtime targets in `Project/python_services/Dockerfile`
- the image-publish GitHub Actions workflow in `.github/workflows/publish-production-images.yml`

### Runtime Hotfix During Live Rollout

The production rollout exposed one regression in the slim API image:

- `Project/python_services/services/browser_automation.py` imported Playwright at module import time
- the slim API image intentionally excluded worker-only browser dependencies
- the backend process crashed before `/health` because `playwright` was not installed

`77a5fa1` fixed this by:

- making the Playwright import optional in slim runtimes
- raising a runtime error only when browser automation is actually invoked
- keeping the browser-capable path intact for the worker image

The same hotfix also updated `docker-compose.production.yml` to pin the working upstream OpenClaw digest:

- `ghcr.io/openclaw/openclaw@sha256:7091859602df6b8cdd59b38adbaed723a6d94806fdd4274d488400dd2fcf0fb6`

### Reviewed Local Changes That Were Later Pushed

After the production rollout, the repo still had a coherent local batch of uncommitted work affecting:

- stricter production ownership behavior in `media_storage_service.py`, `persona_registry_service.py`, and `telegram_link_service.py`
- canonical media storage-path enforcement for production-like environments
- analytics event inserts that now write `user_id`
- media/video activity writes routed through canonical media persistence paths
- new and updated tests for the ownership/media changes
- a large Supabase consolidation migration plus a schema reset helper
- migration docs and `deploy/vps/apply-db-migrations.sh` changes so production-style migration runs target `DATABASE_URL` directly and skip snapshot/bootstrap-only files

Those files were reviewed, compile-checked, and then committed as `bac5fa2`.

## Production Rollout Summary

### Initial VPS State

Before cleanup and redeploy:

- root filesystem free space was about `588MB`
- `docker system df` reported:
  - images: `59.87GB`
  - build cache: `44.27GB`
  - reclaimable image space: `38.28GB`

This caused the first attempt to pull the new image set to fail with:

- `write /var/lib/docker/tmp/GetImageBlob...: no space left on device`

### Safe Space Recovery

To recover space without disturbing running containers:

- `docker image prune -f`
- `docker builder prune -af`

Results:

- image prune reclaimed about `8.553GB`
- builder prune reclaimed about `44.27GB`
- free disk rose from about `588MB` to about `39GB`

### First Full Deploy Attempt

After cleanup, the registry-backed deploy for image tag `6c6b2588a087fe438912c2a244464e337f588a8f` succeeded far enough to recreate most services, but then blocked on OpenClaw health.

Root cause:

- the pinned OpenClaw digest was older than the on-disk OpenClaw config format
- logs showed: `Config was last written by a newer OpenClaw (2026.3.14); current version is 2026.3.13.`

Recovery:

- a redeploy was run with `OPENCLAW_IMAGE=ghcr.io/openclaw/openclaw:latest`
- that allowed OpenClaw to become healthy
- the exact working digest was then captured and pinned for future production deploys

### Backend Regression Found After Recovery

Once OpenClaw was healthy, public frontend traffic returned, but backend health still failed.

Root cause:

- backend startup imported `services.browser_automation`
- `services.browser_automation` imported `playwright.async_api`
- the slim API image excluded Playwright on purpose

Fix path:

- patch `browser_automation.py`
- commit `77a5fa1`
- push to `deploy`
- wait for GHCR images for `77a5fa1`
- redeploy `backend`, `chatgpt_connector`, `frontend`, and `temporal_worker`
- later run a full consistent deploy so `postiz` and `growchief` also moved to the same SHA

## Validation Performed

### Repo/Script Validation

The following checks were completed during implementation and review:

- `docker compose config` for production and local compose files
- `bash -n` for the changed deploy scripts
- `git diff --check`
- `python3 -m py_compile` for the changed Python modules

For the later Supabase/media ownership batch:

- `bash -n deploy/vps/apply-db-migrations.sh`
- `git diff --check`
- `python3 -m py_compile` on the changed Python modules

Host limitation:

- `pytest` was not installed on this VPS host, so host-side pytest execution for the reviewed local batch was not available

### Production Smoke Checks

Final production smoke checks passed after the full `77a5fa1` rollout:

- backend health: `http://127.0.0.1:8000/health`
- connector health: `http://127.0.0.1:8010/health`
- frontend on localhost: `http://127.0.0.1:3000/`
- public HTTPS entrypoint: `https://ai-influencer.tripc.ai/`
- provider API reachability:
  - Postiz `200`
  - GrowChief `200`
- OpenClaw readiness:
  - health endpoint reachable
  - Telegram webhook configured
  - pending updates `0`

The final run of `deploy/vps/healthcheck.sh` completed with:

- `All smoke checks passed.`

## Current Live Production State

As of this document:

- `frontend` runs `ghcr.io/nganuyen/ai-influencer-frontend:77a5fa1e34044211d0ff073808ab78c5240b3800`
- `backend` runs `ghcr.io/nganuyen/ai-influencer-python-api:77a5fa1e34044211d0ff073808ab78c5240b3800`
- `chatgpt_connector` runs `ghcr.io/nganuyen/ai-influencer-python-api:77a5fa1e34044211d0ff073808ab78c5240b3800`
- `temporal_worker` runs `ghcr.io/nganuyen/ai-influencer-python-worker:77a5fa1e34044211d0ff073808ab78c5240b3800`
- `postiz` runs `ghcr.io/nganuyen/ai-influencer-postiz:77a5fa1e34044211d0ff073808ab78c5240b3800`
- `growchief` runs `ghcr.io/nganuyen/ai-influencer-growchief:77a5fa1e34044211d0ff073808ab78c5240b3800`
- `openclaw` runs from the pinned digest `sha256:7091859602df6b8cdd59b38adbaed723a6d94806fdd4274d488400dd2fcf0fb6`

Final VPS footprint snapshot:

- filesystem used: about `40GB` of `79GB`
- filesystem free: about `35GB`
- `docker system df`:
  - images: `30.08GB`
  - active images: `12`
  - reclaimable image space: `17.3GB`
  - build cache: `0B`

## Deploy Branch State After Review Push

After the later review of the remaining local files:

- `bac5fa2` was pushed to `deploy`
- that push started GitHub Actions run `23681420190`
- workflow URL:
  - `https://github.com/NganUyen/AI-Influencer-TripC/actions/runs/23681420190`

As of `2026-03-28 08:37:41 UTC`, that run was still `in_progress`.

Important distinction:

- `bac5fa2` was pushed to `deploy`
- `bac5fa2` was not deployed to the live VPS during this session
- the database migration changes inside `bac5fa2` were not applied to production during this session

## Sensitive Material Handling

Temporary credentials used for GitHub push and GHCR login were cleaned up after use:

- `/tmp/codex-gh-credentials` removed
- `/tmp/docker-ghcr` removed

## Recommended Next Step

If `bac5fa2` is intended to go live, the next production promotion should be:

1. wait for the `deploy` workflow for `bac5fa2` to complete successfully
2. deploy with `IMAGE_TAG=bac5fa2258c2c44a926e300061090d926f5fbabe`
3. run `deploy/vps/apply-db-migrations.sh`
4. run `deploy/vps/healthcheck.sh`

Until that happens, live production should be considered healthy on `77a5fa1`, with `bac5fa2` staged on the `deploy` branch only.
