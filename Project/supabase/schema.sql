-- AI Influencer Factory Database Schema
-- PostgreSQL / Supabase

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Provide a lightweight auth.uid() shim when running against plain PostgreSQL
-- instead of a Supabase-managed auth schema.
DO $auth_compat$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.schemata
        WHERE schema_name = 'auth'
    ) THEN
        EXECUTE 'CREATE SCHEMA auth';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'auth'
          AND p.proname = 'uid'
          AND pg_catalog.pg_get_function_identity_arguments(p.oid) = ''
    ) THEN
        EXECUTE $fn$
            CREATE FUNCTION auth.uid()
            RETURNS uuid
            LANGUAGE sql
            STABLE
            AS $body$
                SELECT NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid
            $body$
        $fn$;
    END IF;
END
$auth_compat$;

-- Users table
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Campaigns table
CREATE TABLE IF NOT EXISTS public.campaigns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'draft', -- draft, active, paused, completed
    start_date TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Content table
CREATE TABLE IF NOT EXISTS public.content (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    campaign_id UUID REFERENCES public.campaigns(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    platform TEXT[] NOT NULL, -- ['twitter', 'linkedin', etc.]
    status TEXT NOT NULL DEFAULT 'draft', -- draft, pending_approval, approved, scheduled, published, failed
    scheduled_at TIMESTAMP WITH TIME ZONE,
    published_at TIMESTAMP WITH TIME ZONE,
    media_urls TEXT[],
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- AI Personas table
CREATE TABLE IF NOT EXISTS public.personas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    voice_profile TEXT, -- Voice characteristics and tone
    platforms TEXT[] NOT NULL,
    is_active BOOLEAN DEFAULT true,
    avatar_url TEXT,
    proxy_config JSONB, -- Proxy settings for this persona
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Media Assets table
CREATE TABLE IF NOT EXISTS public.media_assets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    content_id UUID REFERENCES public.content(id) ON DELETE SET NULL,
    url TEXT NOT NULL,
    type TEXT NOT NULL, -- image, video, audio, document
    filename TEXT NOT NULL,
    size INTEGER,
    mime_type TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Workflows table (Temporal tracking)
CREATE TABLE IF NOT EXISTS public.workflows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id TEXT UNIQUE NOT NULL, -- Temporal workflow ID
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    type TEXT NOT NULL, -- weekly_marketing, content_generation, distribution
    status TEXT NOT NULL DEFAULT 'running', -- running, waiting_approval, completed, failed
    current_step TEXT,
    progress INTEGER DEFAULT 0,
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Social Accounts table
CREATE TABLE IF NOT EXISTS public.social_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    persona_id UUID REFERENCES public.personas(id) ON DELETE SET NULL,
    platform TEXT NOT NULL, -- twitter, linkedin, facebook, etc.
    account_name TEXT NOT NULL,
    account_handle TEXT,
    is_primary BOOLEAN DEFAULT false, -- Main account vs engagement account
    oauth_token TEXT,
    oauth_secret TEXT,
    proxy_config JSONB, -- IP rotation config
    is_active BOOLEAN DEFAULT true,
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.brand_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL UNIQUE REFERENCES public.users(id) ON DELETE CASCADE,
    product_name TEXT NOT NULL,
    website_url TEXT,
    audience TEXT,
    offer_summary TEXT,
    tone_voice TEXT,
    campaign_goals JSONB DEFAULT '[]',
    asset_urls JSONB DEFAULT '[]',
    timezone TEXT NOT NULL DEFAULT 'UTC',
    posting_cadence JSONB DEFAULT '{}',
    approval_preferences JSONB DEFAULT '{"mode":"review_first"}',
    telegram_contact TEXT,
    onboarding_status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.assistant_threads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'New strategy thread',
    status TEXT NOT NULL DEFAULT 'active',
    last_message_preview TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.assistant_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thread_id UUID NOT NULL REFERENCES public.assistant_threads(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.assistant_artifacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thread_id UUID NOT NULL REFERENCES public.assistant_threads(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,
    title TEXT NOT NULL,
    payload JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ChatGPT OAuth link table for connector identity mapping
CREATE TABLE IF NOT EXISTS public.chatgpt_oauth_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chatgpt_subject TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    display_name TEXT,
    session_id TEXT,
    linked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    active BOOLEAN DEFAULT TRUE
);

-- Engagement Actions table (for tracking bot engagement)
CREATE TABLE IF NOT EXISTS public.engagement_actions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    social_account_id UUID NOT NULL REFERENCES public.social_accounts(id) ON DELETE CASCADE,
    target_content_id UUID REFERENCES public.content(id) ON DELETE SET NULL,
    action_type TEXT NOT NULL, -- like, comment, share, repost
    platform TEXT NOT NULL,
    target_url TEXT,
    comment_text TEXT,
    status TEXT NOT NULL DEFAULT 'pending', -- pending, completed, failed
    executed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Analytics Events table
CREATE TABLE IF NOT EXISTS public.analytics_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_id UUID REFERENCES public.content(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL, -- view, click, engagement, etc.
    platform TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_content_user_id ON public.content(user_id);
CREATE INDEX IF NOT EXISTS idx_content_campaign_id ON public.content(campaign_id);
CREATE INDEX IF NOT EXISTS idx_content_status ON public.content(status);
CREATE INDEX IF NOT EXISTS idx_content_scheduled_at ON public.content(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_personas_user_id ON public.personas(user_id);
CREATE INDEX IF NOT EXISTS idx_workflows_user_id ON public.workflows(user_id);
CREATE INDEX IF NOT EXISTS idx_workflows_status ON public.workflows(status);
CREATE INDEX IF NOT EXISTS idx_social_accounts_user_id ON public.social_accounts(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_social_accounts_customer_account ON public.social_accounts(user_id, platform, account_handle, is_primary);
CREATE INDEX IF NOT EXISTS idx_chatgpt_oauth_links_subject ON public.chatgpt_oauth_links(chatgpt_subject);
CREATE INDEX IF NOT EXISTS idx_engagement_actions_account_id ON public.engagement_actions(social_account_id);
CREATE INDEX IF NOT EXISTS idx_engagement_actions_status ON public.engagement_actions(status);
CREATE INDEX IF NOT EXISTS idx_brand_profiles_user_id ON public.brand_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_assistant_threads_user_id ON public.assistant_threads(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_assistant_messages_thread_id ON public.assistant_messages(thread_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_assistant_artifacts_thread_id ON public.assistant_artifacts(thread_id, created_at DESC);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at triggers
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON public.users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_campaigns_updated_at BEFORE UPDATE ON public.campaigns
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_content_updated_at BEFORE UPDATE ON public.content
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_personas_updated_at BEFORE UPDATE ON public.personas
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_social_accounts_updated_at BEFORE UPDATE ON public.social_accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_brand_profiles_updated_at BEFORE UPDATE ON public.brand_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_assistant_threads_updated_at BEFORE UPDATE ON public.assistant_threads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Enable Row Level Security (RLS)
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.content ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.personas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.media_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workflows ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.social_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chatgpt_oauth_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.engagement_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brand_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assistant_threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assistant_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assistant_artifacts ENABLE ROW LEVEL SECURITY;

-- RLS Policies (users can only access their own data)
CREATE POLICY "Users can view own data" ON public.users
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own data" ON public.users
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can view own campaigns" ON public.campaigns
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own content" ON public.content
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own personas" ON public.personas
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own media" ON public.media_assets
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own workflows" ON public.workflows
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own accounts" ON public.social_accounts
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own brand profiles" ON public.brand_profiles
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own assistant threads" ON public.assistant_threads
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own assistant messages" ON public.assistant_messages
    FOR ALL USING (
        auth.uid() IN (
            SELECT t.user_id FROM public.assistant_threads t WHERE t.id = assistant_messages.thread_id
        )
    );

CREATE POLICY "Users can view own assistant artifacts" ON public.assistant_artifacts
    FOR ALL USING (
        auth.uid() IN (
            SELECT t.user_id FROM public.assistant_threads t WHERE t.id = assistant_artifacts.thread_id
        )
    );

-- Approval tracking table (workflow + content review trail)
CREATE TABLE IF NOT EXISTS public.approvals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_id UUID REFERENCES public.content(id) ON DELETE CASCADE,
    workflow_id TEXT REFERENCES public.workflows(workflow_id) ON DELETE SET NULL,
    approver_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending', -- pending, approved, rejected
    feedback TEXT,
    approved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Postiz schedule tracking
CREATE TABLE IF NOT EXISTS public.postiz_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_id UUID NOT NULL REFERENCES public.content(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    postiz_post_id TEXT,
    scheduled_for TIMESTAMP WITH TIME ZONE,
    status TEXT NOT NULL DEFAULT 'scheduled', -- scheduled, published, failed, canceled
    response_payload JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- GrowChief engagement job log
CREATE TABLE IF NOT EXISTS public.engagement_action_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id TEXT REFERENCES public.workflows(workflow_id) ON DELETE SET NULL,
    social_account_id UUID REFERENCES public.social_accounts(id) ON DELETE SET NULL,
    platform TEXT NOT NULL,
    target_post_id TEXT,
    target_url TEXT,
    action_types TEXT[] NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending', -- pending, running, completed, failed
    provider_job_id TEXT,
    result_payload JSONB DEFAULT '{}',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- ChatGPT connector identity links
CREATE TABLE IF NOT EXISTS public.chatgpt_oauth_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chatgpt_subject TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    display_name TEXT,
    session_id TEXT NOT NULL,
    linked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    active BOOLEAN NOT NULL DEFAULT TRUE
);

-- Extend workflows for approval state persistence
ALTER TABLE public.workflows ADD COLUMN IF NOT EXISTS approval_required BOOLEAN DEFAULT FALSE;
ALTER TABLE public.workflows ADD COLUMN IF NOT EXISTS approval_status TEXT; -- pending, approved, rejected
ALTER TABLE public.workflows ADD COLUMN IF NOT EXISTS approved_by UUID REFERENCES public.users(id) ON DELETE SET NULL;
ALTER TABLE public.workflows ADD COLUMN IF NOT EXISTS approval_feedback TEXT;
ALTER TABLE public.workflows ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP WITH TIME ZONE;

-- Extend social accounts for account health snapshots
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS account_health INTEGER;
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS followers_count INTEGER;
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS ban_risk_level TEXT;
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS last_api_response JSONB DEFAULT '{}';
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS warnings TEXT[] DEFAULT '{}';
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS connection_status TEXT NOT NULL DEFAULT 'prepared';
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS provider_account_id TEXT;
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS display_name TEXT;
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS connection_method TEXT;
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS scopes TEXT[] DEFAULT '{}';
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS token_ref TEXT;
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS encrypted_token_bundle TEXT;
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS token_expires_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS last_error TEXT;
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS publish_capabilities JSONB DEFAULT '{}';

ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS brand_profile_id UUID REFERENCES public.brand_profiles(id) ON DELETE SET NULL;
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS plan_status TEXT NOT NULL DEFAULT 'draft';
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS approval_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS approval_feedback TEXT;
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS launched_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS active_workflow_id TEXT;
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS target_platforms TEXT[] DEFAULT '{}';
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS connected_account_ids UUID[] DEFAULT '{}';
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS plan_data JSONB DEFAULT '{}';
ALTER TABLE public.campaigns ADD COLUMN IF NOT EXISTS artifact_summary JSONB DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_approvals_workflow_id ON public.approvals(workflow_id);
CREATE INDEX IF NOT EXISTS idx_approvals_content_id ON public.approvals(content_id);
CREATE INDEX IF NOT EXISTS idx_postiz_schedules_content_id ON public.postiz_schedules(content_id);
CREATE INDEX IF NOT EXISTS idx_postiz_schedules_status ON public.postiz_schedules(status);
CREATE INDEX IF NOT EXISTS idx_engagement_action_logs_workflow_id ON public.engagement_action_logs(workflow_id);
CREATE INDEX IF NOT EXISTS idx_engagement_action_logs_status ON public.engagement_action_logs(status);
CREATE INDEX IF NOT EXISTS idx_chatgpt_oauth_links_subject ON public.chatgpt_oauth_links(chatgpt_subject);
CREATE INDEX IF NOT EXISTS idx_chatgpt_oauth_links_last_used ON public.chatgpt_oauth_links(last_used_at DESC);
CREATE INDEX IF NOT EXISTS idx_social_accounts_connection_status ON public.social_accounts(user_id, connection_status, platform);
CREATE INDEX IF NOT EXISTS idx_campaigns_brand_profile_id ON public.campaigns(brand_profile_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_approval_status ON public.campaigns(user_id, approval_status, updated_at DESC);

ALTER TABLE public.approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.postiz_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.engagement_action_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own approvals" ON public.approvals
    FOR ALL USING (auth.uid() = approver_id);

CREATE POLICY "Users can view own postiz schedules" ON public.postiz_schedules
    FOR ALL USING (
        auth.uid() IN (
            SELECT c.user_id FROM public.content c WHERE c.id = postiz_schedules.content_id
        )
    );

CREATE POLICY "Users can view own engagement logs" ON public.engagement_action_logs
    FOR ALL USING (
        social_account_id IS NULL OR
        auth.uid() IN (
            SELECT sa.user_id FROM public.social_accounts sa WHERE sa.id = engagement_action_logs.social_account_id
        )
    );

-- Telegram subscriber persistence used by the Telegram webhook flow.
CREATE TABLE IF NOT EXISTS public.telegram_subscribers (
    chat_id BIGINT PRIMARY KEY,
    chat_type VARCHAR(20) NOT NULL DEFAULT 'private'
        CHECK (chat_type IN ('private', 'group', 'supergroup')),
    username VARCHAR(255),
    first_name VARCHAR(255),
    role VARCHAR(20) NOT NULL DEFAULT 'OPERATOR'
        CHECK (role IN ('ADMIN', 'OPERATOR', 'VIEWER')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_telegram_subscribers_active_role
    ON public.telegram_subscribers(is_active, role, registered_at);

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

CREATE UNIQUE INDEX IF NOT EXISTS idx_personas_persona_id
    ON public.personas(persona_id);

CREATE INDEX IF NOT EXISTS idx_personas_registry_status
    ON public.personas(status);

-- Final connector-link contract used by the ChatGPT connector runtime.
UPDATE public.chatgpt_oauth_links
SET
    session_id = COALESCE(session_id, 'legacy-' || REPLACE(id::text, '-', '')),
    active = COALESCE(active, TRUE)
WHERE
    session_id IS NULL
    OR active IS NULL;

ALTER TABLE public.chatgpt_oauth_links
    ALTER COLUMN session_id SET NOT NULL,
    ALTER COLUMN active SET DEFAULT TRUE,
    ALTER COLUMN active SET NOT NULL;

-- Customer-selectable AI backbone settings
CREATE TABLE IF NOT EXISTS public.customer_ai_backbone_settings (
    user_id UUID PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
    access_mode TEXT NOT NULL DEFAULT 'platform_managed',
    openclaw_api_url TEXT,
    encrypted_openclaw_api_key TEXT,
    chatgpt_subject TEXT,
    chatgpt_display_name TEXT,
    chatgpt_subscription_tier TEXT,
    encrypted_connector_session_token TEXT,
    connector_session_id TEXT,
    connector_session_expires_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT customer_ai_backbone_settings_access_mode_check
        CHECK (access_mode IN ('platform_managed', 'customer_api_key', 'chatgpt_oauth')),
    CONSTRAINT customer_ai_backbone_settings_subscription_tier_check
        CHECK (
            chatgpt_subscription_tier IS NULL
            OR chatgpt_subscription_tier IN ('plus', 'pro')
        )
);

CREATE INDEX IF NOT EXISTS idx_customer_ai_backbone_settings_access_mode
    ON public.customer_ai_backbone_settings(access_mode);

DROP TRIGGER IF EXISTS update_customer_ai_backbone_settings_updated_at
    ON public.customer_ai_backbone_settings;
CREATE TRIGGER update_customer_ai_backbone_settings_updated_at
    BEFORE UPDATE ON public.customer_ai_backbone_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE public.customer_ai_backbone_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own AI backbone settings"
    ON public.customer_ai_backbone_settings;
CREATE POLICY "Users can view own AI backbone settings"
    ON public.customer_ai_backbone_settings
    FOR ALL USING (auth.uid() = user_id);
