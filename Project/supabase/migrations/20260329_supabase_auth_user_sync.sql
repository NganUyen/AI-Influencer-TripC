-- Keep public.users aligned with Supabase Auth identities in hosted environments.

CREATE OR REPLACE FUNCTION public.sync_public_user_from_auth_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    resolved_name TEXT;
    resolved_avatar_url TEXT;
BEGIN
    resolved_name := NULLIF(
        BTRIM(
            COALESCE(
                NEW.raw_user_meta_data->>'full_name',
                NEW.raw_user_meta_data->>'name',
                ''
            )
        ),
        ''
    );
    resolved_avatar_url := NULLIF(
        BTRIM(COALESCE(NEW.raw_user_meta_data->>'avatar_url', '')),
        ''
    );

    INSERT INTO public.users (id, email, name, avatar_url)
    VALUES (
        NEW.id,
        COALESCE(
            NULLIF(BTRIM(NEW.email), ''),
            'user-' || NEW.id::text || '@local.ai-influencer.invalid'
        ),
        resolved_name,
        resolved_avatar_url
    )
    ON CONFLICT (id) DO UPDATE
    SET email = EXCLUDED.email,
        name = COALESCE(EXCLUDED.name, public.users.name),
        avatar_url = COALESCE(EXCLUDED.avatar_url, public.users.avatar_url),
        updated_at = NOW();

    RETURN NEW;
END;
$$;

DO $$
BEGIN
    IF to_regclass('auth.users') IS NULL OR to_regclass('public.users') IS NULL THEN
        RAISE NOTICE 'Skipping auth.users sync install because auth.users or public.users is unavailable.';
        RETURN;
    END IF;

    EXECUTE 'DROP TRIGGER IF EXISTS on_auth_user_synced ON auth.users';
    EXECUTE '
        CREATE TRIGGER on_auth_user_synced
        AFTER INSERT OR UPDATE ON auth.users
        FOR EACH ROW
        EXECUTE FUNCTION public.sync_public_user_from_auth_user()
    ';
END;
$$;

DO $$
BEGIN
    IF to_regclass('auth.users') IS NULL OR to_regclass('public.users') IS NULL THEN
        RETURN;
    END IF;

    INSERT INTO public.users (id, email, name, avatar_url)
    SELECT
        au.id,
        COALESCE(
            NULLIF(BTRIM(au.email), ''),
            'user-' || au.id::text || '@local.ai-influencer.invalid'
        ),
        NULLIF(
            BTRIM(
                COALESCE(
                    au.raw_user_meta_data->>'full_name',
                    au.raw_user_meta_data->>'name',
                    ''
                )
            ),
            ''
        ),
        NULLIF(BTRIM(COALESCE(au.raw_user_meta_data->>'avatar_url', '')), '')
    FROM auth.users au
    ON CONFLICT (id) DO UPDATE
    SET email = EXCLUDED.email,
        name = COALESCE(EXCLUDED.name, public.users.name),
        avatar_url = COALESCE(EXCLUDED.avatar_url, public.users.avatar_url),
        updated_at = NOW();
END;
$$;
