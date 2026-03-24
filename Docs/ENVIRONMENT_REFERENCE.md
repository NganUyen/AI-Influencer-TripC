# Environment Reference

Last verified: 2026-03-24 (UTC)

The source of truth for the env contract is `Project/.env.example`. This document groups the variables by runtime purpose and explains what each group does.

## URLs And Routing

- `FRONTEND_PUBLIC_URL`: public URL for the Next.js app
- `BACKEND_PUBLIC_URL`: public URL for the FastAPI app
- `CHATGPT_CONNECTOR_PUBLIC_URL`: public URL for the connector service
- `NEXT_PUBLIC_API_URL`: browser-facing base URL for the app
- `PYTHON_BACKEND_URL`: internal URL that Next.js uses to reach FastAPI
- `CORS_ORIGINS`: allowed browser origins for FastAPI

## Frontend And Supabase

- `NEXT_PUBLIC_SUPABASE_URL`: browser Supabase project URL
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`: browser anon key
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`: browser publishable key
- `SUPABASE_URL`: server-side Supabase project URL
- `SUPABASE_ANON_KEY`: server-side anon key when needed
- `SUPABASE_KEY`: current backend auth-validation key input
- `SUPABASE_SERVICE_ROLE_KEY`: service-role key for server-side privileged actions
- `SUPABASE_PUBLISHABLE_KEY`: non-browser publishable key variant
- `SUPABASE_SECRET_KEY`: server-side Supabase secret key
- `CUSTOMER_TOKEN_ENCRYPTION_KEY`: encryption key for customer token vault state

## Database

- `POSTGRES_PASSWORD`: password for the local or production Postgres container
- `DATABASE_URL`: primary application database DSN
- `CHATGPT_CONNECTOR_DATABASE_URL`: connector database DSN, usually the same as `DATABASE_URL`

## AI Provider Keys

- `OPENAI_API_KEY`: OpenAI access key
- `ANTHROPIC_API_KEY`: Anthropic access key
- `FAL_AI_API_KEY`: fal.ai access key
- `GOOGLE_AI_API_KEY`: Google AI access key
- `GOOGLE_TTS_API_KEY`: Google TTS access key
- `HEYGEN_API_KEY`: HeyGen access key
- `DEFAULT_AI_MODEL`: default model name used by app logic

## Storage

- `STORAGE_PROVIDER`: `supabase` or `s3`
- `SUPABASE_STORAGE_BUCKET`: default Supabase Storage bucket
- `STORAGE_CACHE_CONTROL_SECONDS`: cache-control seconds for uploaded assets
- `STORAGE_SIGNED_URL_TTL_SECONDS`: signed-URL lifetime
- `STORAGE_HTTP_TIMEOUT_SECONDS`: storage HTTP timeout
- `STORAGE_UPSERT`: whether uploads overwrite existing keys

### S3-Compatible Storage Extras

- `R2_ACCOUNT_ID`: Cloudflare account identifier
- `R2_ACCESS_KEY_ID`: S3-compatible access key
- `R2_SECRET_ACCESS_KEY`: S3-compatible secret
- `R2_BUCKET_NAME`: S3-compatible bucket name
- `R2_PUBLIC_URL`: public base URL for objects
- `R2_ENDPOINT_URL`: S3-compatible endpoint URL
- `R2_PUBLIC_DOMAIN`: public CDN or custom domain for assets

## Proxies And Browser Profiles

- `IPROYAL_USERNAME`: proxy username
- `IPROYAL_PASSWORD`: proxy password
- `IPROYAL_PROXY_HOST`: proxy hostname
- `IPROYAL_PROXY_PORT`: proxy port
- `PROXY_ENABLED`: turns proxy usage on or off
- `PROXY_SERVER`: host:port shorthand used by provider services
- `PROXY_INVENTORY`: optional serialized inventory override
- `BROWSER_PROFILE_ROOT`: browser profile storage path
- `DEFAULT_PROXY_REGION_CODE`: default proxy geography
- `DEFAULT_PROXY_LOCALE`: default locale used in browser flows
- `DEFAULT_PROXY_TIMEZONE`: default timezone used in browser flows

## Telegram

- `TELEGRAM_BOT_TOKEN`: Telegram bot token
- `TELEGRAM_WEBHOOK_SECRET`: secret token Telegram sends back to the webhook endpoint

## Temporal

- `TEMPORAL_ADDRESS`: Temporal server address
- `TEMPORAL_NAMESPACE`: Temporal namespace
- `TEMPORAL_TASK_QUEUE`: worker task queue
- `WORKER_CONCURRENCY`: worker poll concurrency

## OpenClaw And Connector

- `OPENCLAW_API_URL`: OpenClaw gateway URL
- `OPENCLAW_API_KEY`: OpenClaw API key
- `OPENCLAW_AGENT_ID`: default OpenClaw agent id
- `OPENCLAW_MISSION_CONTROL_URL`: OpenClaw mission-control URL
- `CHATGPT_CONNECTOR_SESSION_SECRET`: connector session signing secret
- `OPENAI_OAUTH_CLIENT_ID`: OpenAI OAuth client id for connector registration
- `OPENAI_OAUTH_CLIENT_SECRET`: OpenAI OAuth client secret
- `OPENAI_OAUTH_REDIRECT_URI`: connector OAuth callback URL

## Publishing Providers

- `POSTIZ_API_URL`: Postiz base URL
- `POSTIZ_API_KEY`: Postiz API key
- `CUSTOMER_POSTIZ_FALLBACK_ENABLED`: allow customer publishing to fall back to the Postiz bridge
- `POSTIZ_INTEGRATION_MAP`: optional explicit provider-to-integration mapping
- `POSTIZ_WEBHOOK_SECRET`: Postiz webhook verification secret
- `GROWCHIEF_API_URL`: GrowChief base URL
- `GROWCHIEF_API_KEY`: GrowChief API key
- `GROWCHIEF_WORKFLOW_MAP`: optional explicit provider-to-workflow mapping
- `GROWCHIEF_WEBHOOK_SECRET`: GrowChief webhook verification secret

## Customer OAuth Providers

- `LINKEDIN_OAUTH_CLIENT_ID`
- `LINKEDIN_OAUTH_CLIENT_SECRET`
- `FACEBOOK_OAUTH_CLIENT_ID`
- `FACEBOOK_OAUTH_CLIENT_SECRET`
- `TWITTER_OAUTH_CLIENT_ID`
- `TWITTER_OAUTH_CLIENT_SECRET`
- `YOUTUBE_OAUTH_CLIENT_ID`
- `YOUTUBE_OAUTH_CLIENT_SECRET`

These are used by the account-connection scaffolding and must be registered outside the repo.

## App Runtime And Security

- `DEBUG`: dev or production-like mode switch
- `LOG_LEVEL`: backend log level
- `ENVIRONMENT`: environment name
- `JWT_SECRET_KEY`: shared app JWT secret
- `APP_ADMIN_TOKEN`: operator token used at the Next.js edge
- `INTERNAL_API_TOKEN`: service-to-service token used from Next.js to FastAPI

## Workflow Tuning

- `WEEKLY_WORKFLOW_ENABLED`: toggle for the weekly workflow lane
- `APPROVAL_TIMEOUT_DAYS`: approval timeout used by workflow logic
- `ENGAGEMENT_DELAY_HOURS`: delay before engagement follow-up
- `STEALTH_ACCOUNT_COUNT`: default stealth-account count target

## Quota Tracking

- `API_QUOTA_LOOKBACK_DAYS`: quota lookback window
- `API_QUOTA_ALERT_THRESHOLD`: alert threshold percentage
- `API_QUOTA_REFRESH_TTL_SECONDS`: cache TTL for quota summaries
- `OPENAI_MONTHLY_TOKEN_LIMIT`: optional provider limit override
- `ANTHROPIC_MONTHLY_TOKEN_LIMIT`: optional provider limit override
- `GOOGLE_AI_MONTHLY_TOKEN_LIMIT`: optional provider limit override
- `GOOGLE_TTS_MONTHLY_CHAR_LIMIT`: optional provider limit override
- `FAL_AI_MONTHLY_REQUEST_LIMIT`: optional provider limit override
- `HEYGEN_MONTHLY_JOB_LIMIT`: optional provider limit override

## Production-Critical Secrets

In production-like environments, the settings loader expects real non-placeholder values for:

- `JWT_SECRET_KEY`
- `CHATGPT_CONNECTOR_SESSION_SECRET`
- `INTERNAL_API_TOKEN`
- `APP_ADMIN_TOKEN`
- `POSTIZ_WEBHOOK_SECRET`
- `GROWCHIEF_WEBHOOK_SECRET`
- `CUSTOMER_TOKEN_ENCRYPTION_KEY`
- `POSTIZ_API_KEY`
- `GROWCHIEF_API_KEY`

## Practical Usage

- use `Project/.env.local` for local development
- use `Project/.env.production` for VPS deployment
- keep `Project/.env.example` updated whenever the runtime contract changes
