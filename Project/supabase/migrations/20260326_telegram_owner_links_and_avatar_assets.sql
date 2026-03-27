-- Telegram/customer ownership linking + persona avatar storage hardening
-- Created: 2026-03-26

CREATE TABLE IF NOT EXISTS public.telegram_link_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_telegram_link_tokens_user_id
    ON public.telegram_link_tokens(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_telegram_link_tokens_expires_at
    ON public.telegram_link_tokens(expires_at);

DROP TRIGGER IF EXISTS update_telegram_link_tokens_updated_at
    ON public.telegram_link_tokens;
CREATE TRIGGER update_telegram_link_tokens_updated_at
    BEFORE UPDATE ON public.telegram_link_tokens
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE public.telegram_link_tokens ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own telegram link tokens"
    ON public.telegram_link_tokens;
CREATE POLICY "Users can view own telegram link tokens"
    ON public.telegram_link_tokens
    FOR ALL USING (auth.uid() = user_id);

CREATE TABLE IF NOT EXISTS public.telegram_user_links (
    chat_id BIGINT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    telegram_username TEXT,
    linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_telegram_user_links_user_id
    ON public.telegram_user_links(user_id, linked_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_telegram_user_links_active_user
    ON public.telegram_user_links(user_id)
    WHERE revoked_at IS NULL;

ALTER TABLE public.telegram_user_links ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own telegram links"
    ON public.telegram_user_links;
CREATE POLICY "Users can view own telegram links"
    ON public.telegram_user_links
    FOR ALL USING (auth.uid() = user_id);

ALTER TABLE public.personas
    ADD COLUMN IF NOT EXISTS avatar_media_asset_id UUID REFERENCES public.media_assets(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_personas_avatar_media_asset_id
    ON public.personas(avatar_media_asset_id);

ALTER TABLE public.media_assets
    ADD COLUMN IF NOT EXISTS storage_provider TEXT NOT NULL DEFAULT 'supabase',
    ADD COLUMN IF NOT EXISTS visibility TEXT NOT NULL DEFAULT 'private',
    ADD COLUMN IF NOT EXISTS asset_origin TEXT NOT NULL DEFAULT 'generated',
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'available';

UPDATE public.media_assets
SET
    storage_provider = COALESCE(NULLIF(metadata->>'storage_provider', ''), storage_provider, 'supabase'),
    visibility = COALESCE(NULLIF(metadata->>'visibility', ''), visibility, 'private'),
    asset_origin = COALESCE(NULLIF(metadata->>'asset_origin', ''), asset_origin, 'generated'),
    status = CASE
        WHEN LOWER(COALESCE(NULLIF(metadata->>'status', ''), status, 'available')) IN ('completed', 'stored', 'success')
            THEN 'available'
        ELSE LOWER(COALESCE(NULLIF(metadata->>'status', ''), status, 'available'))
    END
WHERE
    storage_provider IS NULL
    OR visibility IS NULL
    OR asset_origin IS NULL
    OR status IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_media_assets_storage_identity
    ON public.media_assets(storage_provider, bucket_name, storage_path);
