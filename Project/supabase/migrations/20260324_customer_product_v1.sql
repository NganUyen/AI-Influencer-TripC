-- Customer-facing product v1 foundation
-- Created: 2026-03-24

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

CREATE TABLE IF NOT EXISTS public.brand_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL UNIQUE REFERENCES public.users(id) ON DELETE CASCADE,
    product_name TEXT NOT NULL,
    website_url TEXT,
    audience TEXT,
    offer_summary TEXT,
    tone_voice TEXT,
    campaign_goals JSONB NOT NULL DEFAULT '[]'::jsonb,
    asset_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    posting_cadence JSONB NOT NULL DEFAULT '{}'::jsonb,
    approval_preferences JSONB NOT NULL DEFAULT '{"mode":"review_first"}'::jsonb,
    telegram_contact TEXT,
    onboarding_status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.assistant_threads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'New strategy thread',
    status TEXT NOT NULL DEFAULT 'active',
    last_message_preview TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.assistant_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thread_id UUID NOT NULL REFERENCES public.assistant_threads(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.assistant_artifacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thread_id UUID NOT NULL REFERENCES public.assistant_threads(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,
    title TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.social_accounts
    ADD COLUMN IF NOT EXISTS connection_status TEXT NOT NULL DEFAULT 'prepared',
    ADD COLUMN IF NOT EXISTS provider_account_id TEXT,
    ADD COLUMN IF NOT EXISTS display_name TEXT,
    ADD COLUMN IF NOT EXISTS connection_method TEXT,
    ADD COLUMN IF NOT EXISTS scopes TEXT[] NOT NULL DEFAULT '{}'::text[],
    ADD COLUMN IF NOT EXISTS token_ref TEXT,
    ADD COLUMN IF NOT EXISTS encrypted_token_bundle TEXT,
    ADD COLUMN IF NOT EXISTS token_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_error TEXT,
    ADD COLUMN IF NOT EXISTS publish_capabilities JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE public.campaigns
    ADD COLUMN IF NOT EXISTS brand_profile_id UUID REFERENCES public.brand_profiles(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS plan_status TEXT NOT NULL DEFAULT 'draft',
    ADD COLUMN IF NOT EXISTS approval_status TEXT NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS approval_feedback TEXT,
    ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS launched_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS active_workflow_id TEXT,
    ADD COLUMN IF NOT EXISTS target_platforms TEXT[] NOT NULL DEFAULT '{}'::text[],
    ADD COLUMN IF NOT EXISTS connected_account_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
    ADD COLUMN IF NOT EXISTS plan_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS artifact_summary JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_brand_profiles_user_id
    ON public.brand_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_assistant_threads_user_id
    ON public.assistant_threads(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_assistant_messages_thread_id
    ON public.assistant_messages(thread_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_assistant_artifacts_thread_id
    ON public.assistant_artifacts(thread_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_social_accounts_connection_status
    ON public.social_accounts(user_id, connection_status, platform);
CREATE UNIQUE INDEX IF NOT EXISTS idx_social_accounts_customer_account
    ON public.social_accounts(user_id, platform, account_handle, is_primary);
CREATE INDEX IF NOT EXISTS idx_campaigns_brand_profile_id
    ON public.campaigns(brand_profile_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_approval_status
    ON public.campaigns(user_id, approval_status, updated_at DESC);

ALTER TABLE public.brand_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assistant_threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assistant_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assistant_artifacts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own brand profiles" ON public.brand_profiles;
CREATE POLICY "Users can view own brand profiles" ON public.brand_profiles
    FOR ALL USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view own assistant threads" ON public.assistant_threads;
CREATE POLICY "Users can view own assistant threads" ON public.assistant_threads
    FOR ALL USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view own assistant messages" ON public.assistant_messages;
CREATE POLICY "Users can view own assistant messages" ON public.assistant_messages
    FOR ALL USING (
        auth.uid() IN (
            SELECT t.user_id FROM public.assistant_threads t WHERE t.id = assistant_messages.thread_id
        )
    );

DROP POLICY IF EXISTS "Users can view own assistant artifacts" ON public.assistant_artifacts;
CREATE POLICY "Users can view own assistant artifacts" ON public.assistant_artifacts
    FOR ALL USING (
        auth.uid() IN (
            SELECT t.user_id FROM public.assistant_threads t WHERE t.id = assistant_artifacts.thread_id
        )
    );
