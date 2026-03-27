-- Provision the default public bucket used by the media pipeline when the app
-- runs against a Supabase-hosted project. Local plain-Postgres setups do not
-- have the `storage` schema, so the block is intentionally guarded.

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
