-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.analytics_events (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  content_id uuid,
  event_type text NOT NULL,
  platform text NOT NULL,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  user_id uuid NOT NULL,
  CONSTRAINT analytics_events_pkey PRIMARY KEY (id),
  CONSTRAINT analytics_events_content_id_fkey FOREIGN KEY (content_id) REFERENCES public.content(id),
  CONSTRAINT analytics_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
CREATE TABLE public.approvals (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  content_id uuid,
  workflow_id text,
  approver_id uuid NOT NULL,
  channel text NOT NULL DEFAULT 'telegram'::text,
  request_key text,
  telegram_message_ref jsonb,
  status text NOT NULL DEFAULT 'pending'::text CHECK (status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text, 'save'::text, 'discard'::text])),
  feedback text,
  decision_source text,
  decision_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  approved_at timestamp with time zone,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT approvals_pkey PRIMARY KEY (id),
  CONSTRAINT approvals_content_id_fkey FOREIGN KEY (content_id) REFERENCES public.content(id),
  CONSTRAINT approvals_workflow_id_fkey FOREIGN KEY (workflow_id) REFERENCES public.workflows(workflow_id),
  CONSTRAINT approvals_approver_id_fkey FOREIGN KEY (approver_id) REFERENCES public.users(id)
);
CREATE TABLE public.assistant_artifacts (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  thread_id uuid NOT NULL,
  artifact_type text NOT NULL,
  title text NOT NULL,
  payload jsonb DEFAULT '{}'::jsonb,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT assistant_artifacts_pkey PRIMARY KEY (id),
  CONSTRAINT assistant_artifacts_thread_id_fkey FOREIGN KEY (thread_id) REFERENCES public.assistant_threads(id)
);
CREATE TABLE public.assistant_messages (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  thread_id uuid NOT NULL,
  role text NOT NULL,
  content text NOT NULL,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT assistant_messages_pkey PRIMARY KEY (id),
  CONSTRAINT assistant_messages_thread_id_fkey FOREIGN KEY (thread_id) REFERENCES public.assistant_threads(id)
);
CREATE TABLE public.assistant_threads (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  user_id uuid NOT NULL,
  title text NOT NULL DEFAULT 'New strategy thread'::text,
  status text NOT NULL DEFAULT 'active'::text,
  last_message_preview text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT assistant_threads_pkey PRIMARY KEY (id),
  CONSTRAINT assistant_threads_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
CREATE TABLE public.brand_profiles (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  user_id uuid NOT NULL UNIQUE,
  product_name text NOT NULL,
  website_url text,
  audience text,
  offer_summary text,
  tone_voice text,
  campaign_goals jsonb DEFAULT '[]'::jsonb,
  asset_urls jsonb DEFAULT '[]'::jsonb,
  timezone text NOT NULL DEFAULT 'UTC'::text,
  posting_cadence jsonb DEFAULT '{}'::jsonb,
  approval_preferences jsonb DEFAULT '{"mode": "review_first"}'::jsonb,
  telegram_contact text,
  onboarding_status text NOT NULL DEFAULT 'pending'::text CHECK (onboarding_status = ANY (ARRAY['pending'::text, 'completed'::text])),
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT brand_profiles_pkey PRIMARY KEY (id),
  CONSTRAINT brand_profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
CREATE TABLE public.campaigns (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  user_id uuid NOT NULL,
  name text NOT NULL,
  description text,
  status text NOT NULL DEFAULT 'draft'::text CHECK (status = ANY (ARRAY['draft'::text, 'ready_for_review'::text, 'active'::text, 'paused'::text, 'completed'::text])),
  start_date timestamp with time zone NOT NULL,
  end_date timestamp with time zone,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  brand_profile_id uuid,
  plan_status text NOT NULL DEFAULT 'draft'::text CHECK (plan_status = ANY (ARRAY['draft'::text, 'approved'::text, 'launched'::text])),
  approval_status text NOT NULL DEFAULT 'pending'::text CHECK (approval_status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text])),
  approval_feedback text,
  approved_at timestamp with time zone,
  launched_at timestamp with time zone,
  active_workflow_id text,
  target_platforms ARRAY DEFAULT '{}'::text[],
  connected_account_ids ARRAY DEFAULT '{}'::uuid[],
  plan_data jsonb DEFAULT '{}'::jsonb,
  artifact_summary jsonb DEFAULT '{}'::jsonb,
  CONSTRAINT campaigns_pkey PRIMARY KEY (id),
  CONSTRAINT campaigns_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id),
  CONSTRAINT campaigns_brand_profile_id_fkey FOREIGN KEY (brand_profile_id) REFERENCES public.brand_profiles(id)
);
CREATE TABLE public.chatgpt_oauth_links (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  chatgpt_subject text NOT NULL UNIQUE,
  user_id uuid NOT NULL,
  display_name text,
  session_id text NOT NULL,
  linked_at timestamp with time zone DEFAULT now(),
  last_used_at timestamp with time zone DEFAULT now(),
  active boolean NOT NULL DEFAULT true,
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT chatgpt_oauth_links_pkey PRIMARY KEY (id),
  CONSTRAINT chatgpt_oauth_links_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
CREATE TABLE public.content (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  user_id uuid NOT NULL,
  campaign_id uuid,
  title text NOT NULL,
  content text NOT NULL,
  platform ARRAY NOT NULL,
  status text NOT NULL DEFAULT 'draft'::text CHECK (status = ANY (ARRAY['draft'::text, 'pending_approval'::text, 'approved'::text, 'scheduled'::text, 'published'::text, 'failed'::text])),
  scheduled_at timestamp with time zone,
  published_at timestamp with time zone,
  media_urls ARRAY,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT content_pkey PRIMARY KEY (id),
  CONSTRAINT content_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id),
  CONSTRAINT content_campaign_id_fkey FOREIGN KEY (campaign_id) REFERENCES public.campaigns(id)
);
CREATE TABLE public.customer_ai_backbone_settings (
  user_id uuid NOT NULL,
  access_mode text NOT NULL DEFAULT 'platform_managed'::text CHECK (access_mode = ANY (ARRAY['platform_managed'::text, 'customer_api_key'::text, 'chatgpt_oauth'::text])),
  openclaw_api_url text,
  encrypted_openclaw_api_key text,
  chatgpt_subject text,
  chatgpt_display_name text,
  chatgpt_subscription_tier text CHECK (chatgpt_subscription_tier IS NULL OR (chatgpt_subscription_tier = ANY (ARRAY['plus'::text, 'pro'::text]))),
  encrypted_connector_session_token text,
  connector_session_id text,
  connector_session_expires_at timestamp with time zone,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT customer_ai_backbone_settings_pkey PRIMARY KEY (user_id),
  CONSTRAINT customer_ai_backbone_settings_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
CREATE TABLE public.engagement_action_logs (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  workflow_id text,
  social_account_id uuid,
  platform text NOT NULL,
  target_post_id text,
  target_url text,
  action_types ARRAY NOT NULL DEFAULT '{}'::text[],
  status text NOT NULL DEFAULT 'pending'::text CHECK (status = ANY (ARRAY['pending'::text, 'running'::text, 'completed'::text, 'failed'::text, 'canceled'::text, 'cancelled'::text])),
  provider_job_id text,
  result_payload jsonb DEFAULT '{}'::jsonb,
  error_message text,
  created_at timestamp with time zone DEFAULT now(),
  completed_at timestamp with time zone,
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT engagement_action_logs_pkey PRIMARY KEY (id),
  CONSTRAINT engagement_action_logs_workflow_id_fkey FOREIGN KEY (workflow_id) REFERENCES public.workflows(workflow_id),
  CONSTRAINT engagement_action_logs_social_account_id_fkey FOREIGN KEY (social_account_id) REFERENCES public.social_accounts(id)
);
CREATE TABLE public.engagement_actions (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  social_account_id uuid NOT NULL,
  target_content_id uuid,
  action_type text NOT NULL,
  platform text NOT NULL,
  target_url text,
  comment_text text,
  status text NOT NULL DEFAULT 'pending'::text CHECK (status = ANY (ARRAY['pending'::text, 'completed'::text, 'failed'::text, 'canceled'::text, 'cancelled'::text])),
  executed_at timestamp with time zone,
  error_message text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT engagement_actions_pkey PRIMARY KEY (id),
  CONSTRAINT engagement_actions_social_account_id_fkey FOREIGN KEY (social_account_id) REFERENCES public.social_accounts(id),
  CONSTRAINT engagement_actions_target_content_id_fkey FOREIGN KEY (target_content_id) REFERENCES public.content(id)
);
CREATE TABLE public.media_assets (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  user_id uuid NOT NULL,
  content_id uuid,
  persona_id text,
  owner_key text,
  url text NOT NULL,
  source_url text,
  type text NOT NULL CHECK (type = ANY (ARRAY['image'::text, 'video'::text, 'audio'::text, 'document'::text])),
  filename text NOT NULL,
  bucket_name text,
  storage_path text,
  storage_provider text NOT NULL DEFAULT 'supabase'::text,
  visibility text NOT NULL DEFAULT 'private'::text CHECK (visibility = ANY (ARRAY['private'::text, 'public'::text])),
  asset_origin text NOT NULL DEFAULT 'generated'::text CHECK (asset_origin = ANY (ARRAY['generated'::text, 'uploaded'::text, 'imported'::text, 'backfill'::text])),
  status text NOT NULL DEFAULT 'available'::text CHECK (status = ANY (ARRAY['available'::text, 'pending'::text, 'failed'::text, 'archived'::text])),
  provider_job_id text,
  size integer,
  mime_type text,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT media_assets_pkey PRIMARY KEY (id),
  CONSTRAINT media_assets_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id),
  CONSTRAINT media_assets_content_id_fkey FOREIGN KEY (content_id) REFERENCES public.content(id)
);
CREATE TABLE public.personas (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  user_id uuid NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001'::uuid,
  name text NOT NULL DEFAULT ''::text,
  description text,
  voice_profile text,
  platforms ARRAY NOT NULL DEFAULT '{}'::text[],
  is_active boolean DEFAULT true,
  avatar_url text,
  proxy_config jsonb,
  persona_id text,
  display_name text,
  language text DEFAULT 'English'::text,
  tts_voice text,
  avatar_image_url text,
  avatar_source_type text,
  avatar_prompt text,
  heygen_avatar_id text,
  status text DEFAULT 'draft'::text CHECK (status = ANY (ARRAY['draft'::text, 'ready'::text, 'failed'::text, 'archived'::text])),
  video_count integer DEFAULT 0,
  tone_default text,
  market_default text,
  thumbnail_url text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  avatar_media_asset_id uuid,
  CONSTRAINT personas_pkey PRIMARY KEY (id),
  CONSTRAINT personas_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id),
  CONSTRAINT personas_avatar_media_asset_id_fkey FOREIGN KEY (avatar_media_asset_id) REFERENCES public.media_assets(id)
);
CREATE TABLE public.postiz_schedules (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  content_id uuid NOT NULL,
  platform text NOT NULL,
  postiz_post_id text,
  scheduled_for timestamp with time zone,
  status text NOT NULL DEFAULT 'scheduled'::text CHECK (status = ANY (ARRAY['scheduled'::text, 'published'::text, 'failed'::text, 'canceled'::text, 'cancelled'::text])),
  response_payload jsonb DEFAULT '{}'::jsonb,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT postiz_schedules_pkey PRIMARY KEY (id),
  CONSTRAINT postiz_schedules_content_id_fkey FOREIGN KEY (content_id) REFERENCES public.content(id)
);
CREATE TABLE public.social_accounts (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  user_id uuid NOT NULL,
  persona_id uuid,
  platform text NOT NULL,
  account_name text NOT NULL,
  account_handle text,
  is_primary boolean DEFAULT false,
  oauth_token text,
  oauth_secret text,
  proxy_config jsonb,
  is_active boolean DEFAULT true,
  last_used_at timestamp with time zone,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  account_health integer,
  followers_count integer,
  ban_risk_level text,
  last_api_response jsonb DEFAULT '{}'::jsonb,
  warnings ARRAY DEFAULT '{}'::text[],
  connection_status text NOT NULL DEFAULT 'prepared'::text CHECK (connection_status = ANY (ARRAY['prepared'::text, 'connected'::text, 'disconnected'::text])),
  provider_account_id text,
  display_name text,
  connection_method text,
  scopes ARRAY DEFAULT '{}'::text[],
  token_ref text,
  encrypted_token_bundle text,
  token_expires_at timestamp with time zone,
  last_sync_at timestamp with time zone,
  last_error text,
  publish_capabilities jsonb DEFAULT '{}'::jsonb,
  CONSTRAINT social_accounts_pkey PRIMARY KEY (id),
  CONSTRAINT social_accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id),
  CONSTRAINT social_accounts_persona_id_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id)
);
CREATE TABLE public.telegram_link_tokens (
  token_hash text NOT NULL,
  user_id uuid,
  expires_at timestamp with time zone NOT NULL,
  used_at timestamp with time zone,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT telegram_link_tokens_pkey PRIMARY KEY (token_hash),
  CONSTRAINT telegram_link_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
CREATE TABLE public.telegram_subscribers (
  chat_id bigint NOT NULL,
  chat_type character varying NOT NULL DEFAULT 'private'::character varying CHECK (chat_type::text = ANY (ARRAY['private'::character varying, 'group'::character varying, 'supergroup'::character varying]::text[])),
  username character varying,
  first_name character varying,
  role character varying NOT NULL DEFAULT 'OPERATOR'::character varying CHECK (role::text = ANY (ARRAY['ADMIN'::character varying, 'OPERATOR'::character varying, 'VIEWER'::character varying]::text[])),
  is_active boolean NOT NULL DEFAULT true,
  registered_at timestamp with time zone NOT NULL DEFAULT now(),
  last_seen_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT telegram_subscribers_pkey PRIMARY KEY (chat_id)
);
CREATE TABLE public.telegram_user_links (
  chat_id bigint NOT NULL,
  user_id uuid NOT NULL,
  telegram_username text,
  linked_at timestamp with time zone NOT NULL DEFAULT now(),
  last_verified_at timestamp with time zone NOT NULL DEFAULT now(),
  revoked_at timestamp with time zone,
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT telegram_user_links_pkey PRIMARY KEY (chat_id),
  CONSTRAINT telegram_user_links_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
CREATE INDEX IF NOT EXISTS idx_telegram_subscribers_active_role
    ON public.telegram_subscribers(is_active, role, registered_at);

CREATE TABLE public.telegram_events (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  telegram_update_id bigint NOT NULL UNIQUE,
  chat_id bigint NOT NULL,
  linked_user_id uuid,
  route text NOT NULL DEFAULT 'received'::text,
  approval_id uuid,
  workflow_id text,
  event_type text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  error_message text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT telegram_events_pkey PRIMARY KEY (id),
  CONSTRAINT telegram_events_linked_user_id_fkey FOREIGN KEY (linked_user_id) REFERENCES public.users(id),
  CONSTRAINT telegram_events_approval_id_fkey FOREIGN KEY (approval_id) REFERENCES public.approvals(id),
  CONSTRAINT telegram_events_workflow_id_fkey FOREIGN KEY (workflow_id) REFERENCES public.workflows(workflow_id)
);

-- Keep a stable system-owned user row for persona defaults and internal tooling.
INSERT INTO public.users (id, email, name)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'persona-system@local.ai-influencer.invalid',
    'Persona System'
)
ON CONFLICT (id) DO NOTHING;

-- Final persona registry shape used by the newer persona API/service layer.
ALTER TABLE public.personas
    ADD COLUMN IF NOT EXISTS persona_id TEXT,
    ADD COLUMN IF NOT EXISTS display_name TEXT,
    ADD COLUMN IF NOT EXISTS language TEXT,
    ADD COLUMN IF NOT EXISTS tts_voice TEXT,
    ADD COLUMN IF NOT EXISTS avatar_image_url TEXT,
    ADD COLUMN IF NOT EXISTS avatar_source_type TEXT,
    ADD COLUMN IF NOT EXISTS avatar_prompt TEXT,
    ADD COLUMN IF NOT EXISTS heygen_avatar_id TEXT,
    ADD COLUMN IF NOT EXISTS avatar_media_asset_id UUID REFERENCES public.media_assets(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS status TEXT,
    ADD COLUMN IF NOT EXISTS video_count INTEGER,
    ADD COLUMN IF NOT EXISTS tone_default TEXT,
    ADD COLUMN IF NOT EXISTS market_default TEXT,
    ADD COLUMN IF NOT EXISTS thumbnail_url TEXT;

ALTER TABLE public.personas
    ALTER COLUMN user_id SET DEFAULT '00000000-0000-0000-0000-000000000001',
    ALTER COLUMN name SET DEFAULT '',
    ALTER COLUMN platforms SET DEFAULT '{}'::text[],
    ALTER COLUMN language SET DEFAULT 'English',
    ALTER COLUMN status SET DEFAULT 'draft',
    ALTER COLUMN video_count SET DEFAULT 0;

UPDATE public.personas
SET
    persona_id = COALESCE(persona_id, 'persona-' || REPLACE(id::text, '-', '')),
    display_name = COALESCE(display_name, NULLIF(name, ''), 'Persona ' || LEFT(id::text, 8)),
    language = COALESCE(language, 'English'),
    tts_voice = COALESCE(tts_voice, NULLIF(voice_profile, '')),
    avatar_image_url = COALESCE(avatar_image_url, avatar_url),
    status = COALESCE(status, CASE WHEN COALESCE(is_active, TRUE) THEN 'draft' ELSE 'failed' END),
    video_count = COALESCE(video_count, 0)
WHERE
    persona_id IS NULL
    OR display_name IS NULL
    OR language IS NULL
    OR status IS NULL
    OR video_count IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_personas_user_persona_id
    ON public.personas(user_id, persona_id);

CREATE INDEX IF NOT EXISTS idx_personas_registry_status
    ON public.personas(status);

CREATE INDEX IF NOT EXISTS idx_personas_avatar_media_asset_id
    ON public.personas(avatar_media_asset_id);

-- Final media asset contract used by the owner/persona-scoped storage pipeline.
ALTER TABLE public.media_assets
    ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS persona_id TEXT,
    ADD COLUMN IF NOT EXISTS owner_key TEXT,
    ADD COLUMN IF NOT EXISTS source_url TEXT,
    ADD COLUMN IF NOT EXISTS bucket_name TEXT,
    ADD COLUMN IF NOT EXISTS storage_path TEXT,
    ADD COLUMN IF NOT EXISTS storage_provider TEXT NOT NULL DEFAULT 'supabase',
    ADD COLUMN IF NOT EXISTS visibility TEXT NOT NULL DEFAULT 'private',
    ADD COLUMN IF NOT EXISTS asset_origin TEXT NOT NULL DEFAULT 'generated',
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'available',
    ADD COLUMN IF NOT EXISTS provider_job_id TEXT;

UPDATE public.media_assets
SET
    persona_id = COALESCE(persona_id, NULLIF(metadata->>'persona_id', '')),
    owner_key = COALESCE(owner_key, NULLIF(metadata->>'owner_key', '')),
    source_url = COALESCE(source_url, NULLIF(metadata->>'source_url', '')),
    bucket_name = COALESCE(bucket_name, NULLIF(metadata->>'storage_bucket', '')),
    storage_path = COALESCE(storage_path, NULLIF(metadata->>'storage_path', '')),
    storage_provider = COALESCE(NULLIF(metadata->>'storage_provider', ''), storage_provider, 'supabase'),
    visibility = COALESCE(NULLIF(metadata->>'visibility', ''), visibility, 'private'),
    asset_origin = COALESCE(NULLIF(metadata->>'asset_origin', ''), asset_origin, 'generated'),
    status = CASE
        WHEN LOWER(COALESCE(NULLIF(metadata->>'status', ''), status, 'available')) IN ('completed', 'stored', 'success')
            THEN 'available'
        ELSE LOWER(COALESCE(NULLIF(metadata->>'status', ''), status, 'available'))
    END,
    provider_job_id = COALESCE(provider_job_id, NULLIF(metadata->>'provider_job_id', ''))
WHERE
    persona_id IS NULL
    OR owner_key IS NULL
    OR source_url IS NULL
    OR bucket_name IS NULL
    OR storage_path IS NULL
    OR storage_provider IS NULL
    OR visibility IS NULL
    OR asset_origin IS NULL
    OR status IS NULL
    OR provider_job_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_media_assets_user_persona_created_at
    ON public.media_assets(user_id, persona_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_media_assets_bucket_path
    ON public.media_assets(bucket_name, storage_path);

CREATE UNIQUE INDEX IF NOT EXISTS idx_media_assets_storage_identity
    ON public.media_assets(storage_provider, bucket_name, storage_path);

-- Telegram/customer ownership linking for persona and media routing.
CREATE TABLE IF NOT EXISTS public.telegram_link_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE public.workflows (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  workflow_id text NOT NULL UNIQUE,
  user_id uuid NOT NULL,
  type text NOT NULL,
  status text NOT NULL DEFAULT 'running'::text CHECK (status = ANY (ARRAY['running'::text, 'waiting_approval'::text, 'completed'::text, 'failed'::text, 'canceled'::text, 'cancelled'::text])),
  channel text,
  current_step text,
  progress integer DEFAULT 0,
  request_key text,
  telegram_message_ref jsonb,
  decision_source text,
  decision_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  input_data jsonb,
  output_data jsonb,
  error_message text,
  started_at timestamp with time zone DEFAULT now(),
  completed_at timestamp with time zone,
  approval_required boolean DEFAULT false,
  approval_status text,
  approved_by uuid,
  approval_feedback text,
  approved_at timestamp with time zone,
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT workflows_pkey PRIMARY KEY (id),
  CONSTRAINT workflows_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id),
  CONSTRAINT workflows_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.users(id)
);

-- Supabase-hosted environments also install an auth.users -> public.users sync
-- trigger via 20260329_supabase_auth_user_sync.sql so customer auth stays
-- aligned with the relational ownership anchor used by the app tables.
