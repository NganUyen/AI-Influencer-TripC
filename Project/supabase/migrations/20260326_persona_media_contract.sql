-- Persona/media storage contract alignment
-- Created: 2026-03-26

ALTER TABLE public.media_assets
    ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS persona_id TEXT,
    ADD COLUMN IF NOT EXISTS owner_key TEXT,
    ADD COLUMN IF NOT EXISTS source_url TEXT,
    ADD COLUMN IF NOT EXISTS bucket_name TEXT,
    ADD COLUMN IF NOT EXISTS storage_path TEXT,
    ADD COLUMN IF NOT EXISTS provider_job_id TEXT;

UPDATE public.media_assets
SET
    persona_id = COALESCE(persona_id, NULLIF(metadata->>'persona_id', '')),
    owner_key = COALESCE(owner_key, NULLIF(metadata->>'owner_key', '')),
    source_url = COALESCE(source_url, NULLIF(metadata->>'source_url', '')),
    bucket_name = COALESCE(bucket_name, NULLIF(metadata->>'storage_bucket', '')),
    storage_path = COALESCE(storage_path, NULLIF(metadata->>'storage_path', '')),
    provider_job_id = COALESCE(provider_job_id, NULLIF(metadata->>'provider_job_id', ''))
WHERE
    persona_id IS NULL
    OR owner_key IS NULL
    OR source_url IS NULL
    OR bucket_name IS NULL
    OR storage_path IS NULL
    OR provider_job_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_media_assets_user_created_at
    ON public.media_assets(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_media_assets_user_persona_created_at
    ON public.media_assets(user_id, persona_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_media_assets_content_id
    ON public.media_assets(content_id);

CREATE INDEX IF NOT EXISTS idx_media_assets_bucket_path
    ON public.media_assets(bucket_name, storage_path);

CREATE INDEX IF NOT EXISTS idx_personas_user_status
    ON public.personas(user_id, status, updated_at DESC);

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
