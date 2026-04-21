CREATE TABLE IF NOT EXISTS public.system_persona_account_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    persona_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    profile_url TEXT NOT NULL,
    account_handle TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (persona_id, provider, profile_url)
);

CREATE INDEX IF NOT EXISTS idx_system_persona_account_links_persona_provider
    ON public.system_persona_account_links(persona_id, provider, is_active);
