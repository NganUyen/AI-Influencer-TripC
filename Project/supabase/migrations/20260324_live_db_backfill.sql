-- Live database backfill for post-initial schema drift
-- Created: 2026-03-24

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

-- Persona registry compatibility for the newer persona API/service layer.
INSERT INTO public.users (id, email, name)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'persona-system@local.ai-influencer.invalid',
    'Persona System'
)
ON CONFLICT (id) DO NOTHING;

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

-- Repair early connector-link installs so the later migration contract holds.
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

