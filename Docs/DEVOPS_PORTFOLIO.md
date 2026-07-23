# DevOps Portfolio Walkthrough

Last reviewed: 2026-07-23

This document is a recruiter- and interview-friendly map of the DevOps work demonstrated by AI Influencer Factory. Every claim below links to an implementation artifact in the repository.

> Use the CV wording at the end only for work you personally performed or can confidently explain in an interview.

## The Operations Problem

The application is not a single web container. It combines:

- a Next.js frontend
- a FastAPI API
- a Temporal worker with browser and media dependencies
- a separate ChatGPT connector
- two Temporal clusters
- PostgreSQL, Redis and Elasticsearch
- OpenClaw, Postiz and GrowChief
- external authentication, storage, AI, media and messaging providers

The DevOps challenge is to make this integration-heavy system repeatable, observable and recoverable on a private VPS without exposing internal control-plane services to the internet.

## Delivery Design

### Pull-request quality gates

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs independent gates for:

- frontend type checking, tests and production build
- a 74-test backend regression selection covering customer APIs, authentication, review-engine planning, workflow failure handling, analytics, webhooks and the connector
- Python compilation
- shell-script syntax
- local and production Docker Compose rendering

The workflow uses read-only repository permissions, dependency caching, job timeouts and concurrency cancellation for superseded branch runs.

### Production image publication

[`.github/workflows/publish-production-images.yml`](../.github/workflows/publish-production-images.yml):

1. installs the production/test dependency set
2. executes the 74-test backend quality gate and import smoke test
3. builds five application images with Docker Buildx
4. tags each image with the Git commit SHA and `latest`
5. pushes images to GHCR
6. enforces image-size budgets for the frontend, API and worker

The API and worker intentionally use separate runtime targets. Browser automation, Chromium and full media assets stay in the worker image rather than inflating the API image.

### Deployment and promotion

[`deploy/vps/deploy-production.sh`](../deploy/vps/deploy-production.sh) implements a pull-first deployment:

- optionally fast-forwards a configured deployment branch
- derives or accepts an immutable image tag
- verifies that required GHCR image manifests exist
- refuses to guess missing artifacts
- pulls registry-backed images
- supports an explicit emergency local-build path
- starts the stack through Docker Compose

This separates image creation from runtime deployment and makes a release reproducible by commit SHA.

## Production Runtime Controls

The production topology is defined in [`docker-compose.production.yml`](../docker-compose.production.yml).

| Control | Repository evidence |
|---|---|
| Dependency ordering | Compose `depends_on` with health conditions for stateful dependencies |
| Liveness/readiness | Eight service health checks plus public/private smoke probes |
| Self-healing | `restart: unless-stopped` across all 14 services |
| Resource governance | CPU and memory limits on application and stateful workloads |
| Disk protection | JSON log rotation plus scheduled image/build-cache cleanup |
| Network exposure | Published service ports bound to `127.0.0.1` |
| Image traceability | GHCR image tag selected through `IMAGE_TAG` |
| Persistent state | Named volumes for databases, Redis, profiles, configuration and uploads |

## Network and Security Model

[`deploy/nginx/ai-influencer.reverse-proxy.conf`](../deploy/nginx/ai-influencer.reverse-proxy.conf) and [`deploy/nginx/ai-influencer.single-domain.conf`](../deploy/nginx/ai-influencer.single-domain.conf) support:

- multi-host and single-domain production layouts
- TLS termination with Let's Encrypt certificates
- HTTP-to-HTTPS redirection
- HSTS and browser security headers
- forwarding of original scheme, host and client IP
- public routing only to the frontend, API and connector

Internal control services are not intended for public routing. Postiz, GrowChief, Temporal UI and OpenClaw are accessed through SSH tunnels during operations.

The backend settings contract in [`Project/python_services/config/settings.py`](../Project/python_services/config/settings.py) also fails startup for unsafe production configuration, including:

- placeholder or missing application secrets
- missing provider keys
- wildcard CORS while credentials are enabled
- invalid storage configuration
- a non-canonical Supabase production bucket

## Database Change Management

The application uses Supabase PostgreSQL as its canonical product database. Ordered migrations live in [`Project/supabase/migrations/`](../Project/supabase/migrations/).

[`deploy/vps/apply-db-migrations.sh`](../deploy/vps/apply-db-migrations.sh):

- requires an explicit `DATABASE_URL`
- uses `psql -X` and `ON_ERROR_STOP=1`
- applies ordered migration files
- excludes bootstrap-only snapshot files
- stops immediately when a migration fails

The operational runbook requires backing up the application database before schema-changing deployments.

## Observability and Day-Two Operations

The project uses pragmatic VPS-level observability:

- [`monitor.sh`](../monitor.sh): container state, health, CPU, memory, network, PostgreSQL connections, Redis status and recent errors
- [`deploy/vps/healthcheck.sh`](../deploy/vps/healthcheck.sh): public frontend/API/connector checks and private provider checks
- [`deploy/vps/check-provider-apis.sh`](../deploy/vps/check-provider-apis.sh): Postiz and GrowChief contract probes
- [`deploy/vps/check-telegram-openclaw.sh`](../deploy/vps/check-telegram-openclaw.sh): Telegram webhook and OpenClaw execution diagnostics
- container JSON log rotation in the production Compose definition
- [`deploy/vps/docker-cleanup.sh`](../deploy/vps/docker-cleanup.sh) plus a systemd timer for disk-pressure prevention

FastAPI can start in a degraded state when Temporal is unavailable, allowing health endpoints and non-workflow features to remain observable.

## Failure and Recovery Matrix

| Failure scenario | Detection/control | Recovery path |
|---|---|---|
| Required image tag was never published | Deployment manifest preflight | Select a known SHA tag or intentionally invoke emergency local build |
| Application or dependency is unhealthy | Compose health checks and `healthcheck.sh` | Inspect logs, restart the affected service, or roll back |
| Bad application release | Post-deploy smoke checks | [`rollback-release.sh`](../deploy/vps/rollback-release.sh) restores a previous Git/image tag |
| Database or provider-service data loss | Backup inventory and validation | [`restore-stack.sh`](../deploy/vps/restore-stack.sh) restores SQL dumps and browser profiles |
| VPS disk pressure | Log size limits and cleanup timer | Prune unused images/build cache without removing running containers |
| External provider degradation | Provider probes and structured degraded responses | Preserve core API visibility and retry after provider recovery |
| Temporal unavailable during API startup | Backend degraded health state | Restore Temporal while keeping diagnostic endpoints available |

## Design Tradeoffs

### Why Docker Compose

For a single private VPS, Compose keeps the platform understandable and inexpensive while still expressing health, dependencies, volumes, networks and resource limits. Kubernetes would add operational cost without proving a current scaling requirement.

### Why build once and deploy by SHA

Building in CI provides a known artifact. Deploying by commit SHA prevents the VPS from producing a subtly different release and makes rollback deterministic. The `latest` tag is retained for convenience, but production commands can pin a SHA.

### Why API and worker images are separate

The worker needs Chromium, Playwright, FFmpeg, Tesseract and media assets. The API does not. Separate targets reduce the API runtime footprint and isolate the more privileged browser workload.

### Why manual deployment remains

Production deployment is operator-triggered because the current VPS environment has no GitHub Environment approval and secret-delivery integration. This is an explicit current limitation, not hidden automation.

## Improvements I Would Implement Next

1. Provision the VPS, firewall, DNS and nginx using Terraform plus configuration management.
2. Add GitHub Environment approvals and short-lived deployment credentials.
3. Promote immutable tags between staging and production instead of rebuilding or relying on `latest`.
4. Add container and dependency vulnerability scanning with policy thresholds.
5. Export metrics to Prometheus/Grafana and centralize logs.
6. Define and test RPO/RTO targets with automated restore drills.
7. Reconcile schema snapshots with the complete migration chain and add migration tests.
8. Reconcile stale historical media and Telegram tests, then promote the complete backend suite into the release gate.
9. Add canary or blue/green deployment when traffic and infrastructure justify it.

## Interview Talking Points

Be ready to explain:

- why the worker and API use different Docker targets
- how commit-SHA tags enable deterministic rollback
- why only three entry points are public
- how the release fails safely when an image tag is missing
- how health checks differ from a full post-deployment smoke test
- how database migrations and backups fit into the release order
- why Compose was selected and when you would move to Kubernetes
- what remains manual and how you would automate it safely

## CV-Ready Bullet Templates

Adapt these to your exact ownership and measured results:

- Designed and operated a 14-service Docker Compose platform integrating Next.js, FastAPI, Temporal, PostgreSQL, Redis and third-party automation services behind an nginx TLS reverse proxy.
- Built GitHub Actions quality gates for TypeScript, Jest, pytest, shell and Compose validation, then published five multi-stage Docker images to GHCR using immutable commit-SHA tags.
- Implemented release safeguards including image-manifest preflight, resource limits, health checks, log rotation, post-deployment smoke tests and deterministic rollback.
- Automated database migrations, multi-database backup/restore, provider diagnostics and scheduled Docker cleanup for day-two VPS operations.
- Hardened production configuration with localhost-only control services, least-privilege CI permissions, secret validation, CORS checks and security headers.

Avoid claiming uptime, deployment-frequency, cost savings or incident-recovery improvements unless you have measured evidence.
