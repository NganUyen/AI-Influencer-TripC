BEGIN;

SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '0';

-- Shared updated_at trigger helper.
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

-- App-local users table expected by the backend.
CREATE TABLE IF NOT EXISTS public.users (
  id UUID PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  name TEXT,
  avatar_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Stable system user used by legacy rows that do not yet have a real owner.
INSERT INTO public.users (id, email, name)
VALUES (
  '00000000-0000-0000-0000-000000000001',
  'persona-system@local.ai-influencer.invalid',
  'Persona System'
)
ON CONFLICT (id) DO NOTHING;

-- Backfill app-local users from Supabase Auth users.
INSERT INTO public.users (id, email, name, avatar_url)
SELECT
  au.id,
  COALESCE(au.email, 'user-' || au.id::text || '@local.ai-influencer.invalid'),
  COALESCE(
    NULLIF(au.raw_user_meta_data->>'name', ''),
    NULLIF(au.raw_user_meta_data->>'full_name', ''),
    NULLIF(au.email, '')
  ),
  NULLIF(au.raw_user_meta_data->>'avatar_url', '')
FROM auth.users au
ON CONFLICT (id) DO UPDATE
SET
  email = EXCLUDED.email,
  name = COALESCE(EXCLUDED.name, public.users.name),
  avatar_url = COALESCE(EXCLUDED.avatar_url, public.users.avatar_url),
  updated_at = NOW();

DROP TRIGGER IF EXISTS update_users_updated_at ON public.users;
CREATE TRIGGER update_users_updated_at
  BEFORE UPDATE ON public.users
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own data" ON public.users;
CREATE POLICY "Users can view own data"
  ON public.users
  FOR SELECT
  USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can update own data" ON public.users;
CREATE POLICY "Users can update own data"
  ON public.users
  FOR UPDATE
  USING (auth.uid() = id);

-- Supabase Storage bucket used by the app.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.schemata
    WHERE schema_name = 'storage'
  ) THEN
    INSERT INTO storage.buckets (
      id,
      name,
      public,
      file_size_limit,
      allowed_mime_types
    )
    VALUES (
      'media',
      'media',
      TRUE,
      104857600,
      ARRAY[
        'application/json',
        'audio/mpeg',
        'audio/mp3',
        'audio/wav',
        'audio/x-wav',
        'image/jpeg',
        'image/png',
        'image/webp',
        'video/mp4'
      ]
    )
    ON CONFLICT (id) DO UPDATE
    SET
      name = EXCLUDED.name,
      public = EXCLUDED.public,
      file_size_limit = EXCLUDED.file_size_limit,
      allowed_mime_types = EXCLUDED.allowed_mime_types;
  END IF;
END $$;

-- Bridge old personas table into the new backend contract.
ALTER TABLE public.personas
  ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS persona_id TEXT,
  ADD COLUMN IF NOT EXISTS display_name TEXT,
  ADD COLUMN IF NOT EXISTS language TEXT,
  ADD COLUMN IF NOT EXISTS tts_voice TEXT,
  ADD COLUMN IF NOT EXISTS avatar_image_url TEXT,
  ADD COLUMN IF NOT EXISTS avatar_source_type TEXT,
  ADD COLUMN IF NOT EXISTS avatar_prompt TEXT,
  ADD COLUMN IF NOT EXISTS heygen_avatar_id TEXT,
  ADD COLUMN IF NOT EXISTS avatar_media_asset_id UUID,
  ADD COLUMN IF NOT EXISTS status TEXT,
  ADD COLUMN IF NOT EXISTS video_count INTEGER,
  ADD COLUMN IF NOT EXISTS tone_default TEXT,
  ADD COLUMN IF NOT EXISTS market_default TEXT,
  ADD COLUMN IF NOT EXISTS thumbnail_url TEXT,
  ADD COLUMN IF NOT EXISTS description TEXT;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'personas_avatar_media_asset_id_fkey'
      AND conrelid = 'public.personas'::regclass
  ) THEN
    ALTER TABLE public.personas
      ADD CONSTRAINT personas_avatar_media_asset_id_fkey
      FOREIGN KEY (avatar_media_asset_id)
      REFERENCES public.media_assets(id)
      ON DELETE SET NULL;
  END IF;
END $$;

ALTER TABLE public.personas
  ALTER COLUMN user_id SET DEFAULT '00000000-0000-0000-0000-000000000001'::uuid,
  ALTER COLUMN language SET DEFAULT 'English',
  ALTER COLUMN status SET DEFAULT 'draft',
  ALTER COLUMN video_count SET DEFAULT 0;

UPDATE public.personas
SET
  user_id = COALESCE(user_id, '00000000-0000-0000-0000-000000000001'::uuid),
  persona_id = COALESCE(
    persona_id,
    CASE
      WHEN NULLIF(BTRIM(REGEXP_REPLACE(LOWER(COALESCE(name, '')), '[^a-z0-9]+', '-', 'g'), '-'), '') IS NULL
        THEN 'persona-' || LEFT(REPLACE(id::text, '-', ''), 12)
      ELSE BTRIM(REGEXP_REPLACE(LOWER(name), '[^a-z0-9]+', '-', 'g'), '-') || '-' || LEFT(REPLACE(id::text, '-', ''), 8)
    END
  ),
  display_name = COALESCE(display_name, NULLIF(name, ''), 'Persona ' || LEFT(id::text, 8)),
  language = COALESCE(language, 'English'),
  tts_voice = COALESCE(tts_voice, NULLIF(playht_voice_id, '')),
  avatar_image_url = COALESCE(avatar_image_url, avatar_public_url),
  avatar_source_type = COALESCE(
    avatar_source_type,
    CASE
      WHEN avatar_public_url IS NOT NULL OR avatar_storage_path IS NOT NULL THEN 'upload'
      ELSE NULL
    END
  ),
  description = COALESCE(description, NULLIF(system_prompt, '')),
  status = COALESCE(
    status,
    CASE
      WHEN avatar_public_url IS NOT NULL OR avatar_storage_path IS NOT NULL THEN 'ready'
      ELSE 'draft'
    END
  ),
  video_count = COALESCE(video_count, 0),
  thumbnail_url = COALESCE(thumbnail_url, avatar_public_url)
WHERE
  user_id IS NULL
  OR persona_id IS NULL
  OR display_name IS NULL
  OR language IS NULL
  OR tts_voice IS NULL
  OR avatar_image_url IS NULL
  OR avatar_source_type IS NULL
  OR description IS NULL
  OR status IS NULL
  OR video_count IS NULL
  OR thumbnail_url IS NULL;

ALTER TABLE public.personas
  ALTER COLUMN user_id SET NOT NULL;

DROP TRIGGER IF EXISTS update_personas_updated_at ON public.personas;
CREATE TRIGGER update_personas_updated_at
  BEFORE UPDATE ON public.personas
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

DROP INDEX IF EXISTS public.idx_personas_persona_id;
CREATE UNIQUE INDEX IF NOT EXISTS idx_personas_user_persona_id
  ON public.personas(user_id, persona_id);

CREATE INDEX IF NOT EXISTS idx_personas_user_status
  ON public.personas(user_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_personas_avatar_media_asset_id
  ON public.personas(avatar_media_asset_id);

ALTER TABLE public.personas ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own personas" ON public.personas;
CREATE POLICY "Users can view own personas"
  ON public.personas
  FOR ALL
  USING (auth.uid() = user_id);

-- Bridge old media_assets table into the new backend contract.
ALTER TABLE public.media_assets
  ALTER COLUMN status DROP DEFAULT;

ALTER TABLE public.media_assets
  ALTER COLUMN status TYPE TEXT
  USING LOWER(status::text);

ALTER TABLE public.media_assets
  ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS url TEXT,
  ADD COLUMN IF NOT EXISTS persona_id TEXT,
  ADD COLUMN IF NOT EXISTS owner_key TEXT,
  ADD COLUMN IF NOT EXISTS source_url TEXT,
  ADD COLUMN IF NOT EXISTS type TEXT,
  ADD COLUMN IF NOT EXISTS filename TEXT,
  ADD COLUMN IF NOT EXISTS bucket_name TEXT,
  ADD COLUMN IF NOT EXISTS storage_provider TEXT,
  ADD COLUMN IF NOT EXISTS visibility TEXT,
  ADD COLUMN IF NOT EXISTS asset_origin TEXT,
  ADD COLUMN IF NOT EXISTS size INTEGER,
  ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

ALTER TABLE public.media_assets
  ALTER COLUMN user_id SET DEFAULT '00000000-0000-0000-0000-000000000001'::uuid,
  ALTER COLUMN storage_provider SET DEFAULT 'supabase',
  ALTER COLUMN visibility SET DEFAULT 'private',
  ALTER COLUMN asset_origin SET DEFAULT 'generated',
  ALTER COLUMN status SET DEFAULT 'available',
  ALTER COLUMN metadata SET DEFAULT '{}'::jsonb;

UPDATE public.media_assets
SET metadata = '{}'::jsonb
WHERE metadata IS NULL;

UPDATE public.media_assets
SET
  user_id = COALESCE(user_id, '00000000-0000-0000-0000-000000000001'::uuid),
  url = COALESCE(url, public_url),
  type = COALESCE(type, LOWER(asset_type::text)),
  filename = COALESCE(
    filename,
    NULLIF(REGEXP_REPLACE(COALESCE(storage_path, ''), '^.*/', ''), ''),
    'asset-' || LEFT(REPLACE(id::text, '-', ''), 12)
  ),
  bucket_name = COALESCE(bucket_name, storage_bucket),
  storage_provider = COALESCE(storage_provider, 'supabase'),
  visibility = COALESCE(
    visibility,
    CASE
      WHEN COALESCE(url, public_url) IS NOT NULL THEN 'public'
      ELSE 'private'
    END
  ),
  asset_origin = COALESCE(asset_origin, 'generated'),
  status = CASE
    WHEN LOWER(COALESCE(status, 'available')) IN ('completed', 'stored', 'success')
      THEN 'available'
    ELSE LOWER(COALESCE(status, 'available'))
  END,
  size = COALESCE(
    size,
    CASE
      WHEN file_size IS NULL THEN NULL
      ELSE LEAST(file_size, 2147483647)::integer
    END
  )
WHERE
  user_id IS NULL
  OR url IS NULL
  OR type IS NULL
  OR filename IS NULL
  OR bucket_name IS NULL
  OR storage_provider IS NULL
  OR visibility IS NULL
  OR asset_origin IS NULL
  OR status IS NULL
  OR metadata IS NULL;

-- Map media to personas and owners through existing campaigns/persona_operators.
WITH campaign_owner AS (
  SELECT
    c.id AS campaign_id,
    p.persona_id AS persona_key,
    p.user_id AS persona_user_id,
    MIN(po.chat_id) AS operator_chat_id
  FROM public.campaigns c
  JOIN public.personas p
    ON p.id = c.persona_id
  LEFT JOIN public.persona_operators po
    ON po.persona_id = p.id
  GROUP BY c.id, p.persona_id, p.user_id
)
UPDATE public.media_assets ma
SET
  user_id = COALESCE(
    NULLIF(ma.user_id, '00000000-0000-0000-0000-000000000001'::uuid),
    co.persona_user_id,
    '00000000-0000-0000-0000-000000000001'::uuid
  ),
  persona_id = COALESCE(ma.persona_id, co.persona_key),
  owner_key = COALESCE(
    ma.owner_key,
    CASE
      WHEN co.operator_chat_id IS NOT NULL THEN 'telegram:' || co.operator_chat_id::text
      ELSE NULL
    END
  )
FROM campaign_owner co
WHERE ma.campaign_id = co.campaign_id;

ALTER TABLE public.media_assets
  ALTER COLUMN user_id SET NOT NULL,
  ALTER COLUMN storage_provider SET NOT NULL,
  ALTER COLUMN visibility SET NOT NULL,
  ALTER COLUMN asset_origin SET NOT NULL,
  ALTER COLUMN status SET NOT NULL;

DROP TRIGGER IF EXISTS update_media_assets_updated_at ON public.media_assets;
CREATE TRIGGER update_media_assets_updated_at
  BEFORE UPDATE ON public.media_assets
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM public.media_assets
    WHERE bucket_name IS NOT NULL
      AND storage_path IS NOT NULL
    GROUP BY storage_provider, bucket_name, storage_path
    HAVING COUNT(*) > 1
  ) THEN
    RAISE EXCEPTION 'Duplicate rows exist for (storage_provider, bucket_name, storage_path) in public.media_assets';
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_media_assets_user_created_at
  ON public.media_assets(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_media_assets_user_persona_created_at
  ON public.media_assets(user_id, persona_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_media_assets_bucket_path
  ON public.media_assets(bucket_name, storage_path);

CREATE UNIQUE INDEX IF NOT EXISTS idx_media_assets_storage_identity
  ON public.media_assets(storage_provider, bucket_name, storage_path);

ALTER TABLE public.media_assets ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own media assets" ON public.media_assets;
CREATE POLICY "Users can view own media assets"
  ON public.media_assets
  FOR ALL
  USING (auth.uid() = user_id);

-- Attach persona avatar to a real media asset when possible.
UPDATE public.personas p
SET avatar_media_asset_id = ma.id
FROM public.media_assets ma
WHERE p.avatar_media_asset_id IS NULL
  AND (
    (p.avatar_storage_path IS NOT NULL AND ma.storage_path = p.avatar_storage_path)
    OR
    (p.avatar_public_url IS NOT NULL AND ma.url = p.avatar_public_url)
  );

-- Telegram link tables used by the backend.
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
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.telegram_link_tokens ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own telegram link tokens"
  ON public.telegram_link_tokens;

CREATE POLICY "Users can view own telegram link tokens"
  ON public.telegram_link_tokens
  FOR ALL
  USING (auth.uid() = user_id);

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
  FOR ALL
  USING (auth.uid() = user_id);

-- When a Telegram chat is linked to a real app user, move legacy persona/media ownership over.
CREATE OR REPLACE FUNCTION public.apply_telegram_link_ownership()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.revoked_at IS NOT NULL THEN
    RETURN NEW;
  END IF;

  UPDATE public.personas p
  SET
    user_id = NEW.user_id,
    updated_at = NOW()
  FROM public.persona_operators po
  WHERE po.persona_id = p.id
    AND po.chat_id = NEW.chat_id
    AND p.user_id = '00000000-0000-0000-0000-000000000001'::uuid;

  UPDATE public.media_assets ma
  SET
    user_id = CASE
      WHEN ma.user_id = '00000000-0000-0000-0000-000000000001'::uuid THEN NEW.user_id
      ELSE ma.user_id
    END,
    persona_id = COALESCE(ma.persona_id, p.persona_id),
    owner_key = COALESCE(ma.owner_key, 'telegram:' || NEW.chat_id::text)
  FROM public.campaigns c
  JOIN public.personas p
    ON p.id = c.persona_id
  JOIN public.persona_operators po
    ON po.persona_id = p.id
  WHERE ma.campaign_id = c.id
    AND po.chat_id = NEW.chat_id;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS apply_telegram_link_ownership_trigger
  ON public.telegram_user_links;

CREATE TRIGGER apply_telegram_link_ownership_trigger
  AFTER INSERT OR UPDATE OF user_id, revoked_at
  ON public.telegram_user_links
  FOR EACH ROW
  EXECUTE FUNCTION public.apply_telegram_link_ownership();

-- One-time ownership backfill for any already-linked Telegram chats.
UPDATE public.personas p
SET
  user_id = tul.user_id,
  updated_at = NOW()
FROM public.persona_operators po
JOIN public.telegram_user_links tul
  ON tul.chat_id = po.chat_id
 AND tul.revoked_at IS NULL
WHERE po.persona_id = p.id
  AND p.user_id = '00000000-0000-0000-0000-000000000001'::uuid;

WITH linked_campaign_owner AS (
  SELECT
    c.id AS campaign_id,
    p.persona_id AS persona_key,
    tul.user_id AS linked_user_id,
    tul.chat_id
  FROM public.campaigns c
  JOIN public.personas p
    ON p.id = c.persona_id
  JOIN public.persona_operators po
    ON po.persona_id = p.id
  JOIN public.telegram_user_links tul
    ON tul.chat_id = po.chat_id
   AND tul.revoked_at IS NULL
)
UPDATE public.media_assets ma
SET
  user_id = CASE
    WHEN ma.user_id = '00000000-0000-0000-0000-000000000001'::uuid THEN lco.linked_user_id
    ELSE ma.user_id
  END,
  persona_id = COALESCE(ma.persona_id, lco.persona_key),
  owner_key = COALESCE(ma.owner_key, 'telegram:' || lco.chat_id::text)
FROM linked_campaign_owner lco
WHERE ma.campaign_id = lco.campaign_id;

COMMIT;
