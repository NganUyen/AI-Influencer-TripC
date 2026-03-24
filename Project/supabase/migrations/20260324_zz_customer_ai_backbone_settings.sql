-- Customer-selectable AI backbone settings
-- Created: 2026-03-24

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
