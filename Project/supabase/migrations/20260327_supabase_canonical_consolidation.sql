BEGIN;

SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '0';

-- Consolidate the app schema around Supabase Postgres as the canonical
-- customer-facing database while keeping legacy/system ownership only for
-- backfill and ops-only rows.

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.run_if_table_exists(
    qualified_table TEXT,
    statement TEXT
)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    IF to_regclass(qualified_table) IS NULL THEN
        RETURN;
    END IF;

    EXECUTE statement;
END;
$$;

CREATE OR REPLACE FUNCTION public.ensure_table_updated_at(
    qualified_table TEXT,
    coalesce_sources TEXT,
    trigger_name TEXT
)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    IF to_regclass(qualified_table) IS NULL THEN
        RETURN;
    END IF;

    EXECUTE format(
        'ALTER TABLE %s ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ',
        qualified_table
    );
    EXECUTE format(
        'UPDATE %s SET updated_at = COALESCE(updated_at, %s, NOW()) WHERE updated_at IS NULL',
        qualified_table,
        coalesce_sources
    );
    EXECUTE format(
        'ALTER TABLE %s ALTER COLUMN updated_at SET DEFAULT NOW(), ALTER COLUMN updated_at SET NOT NULL',
        qualified_table
    );
    EXECUTE format(
        'DROP TRIGGER IF EXISTS %I ON %s',
        trigger_name,
        qualified_table
    );
    EXECUTE format(
        'CREATE TRIGGER %I BEFORE UPDATE ON %s FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column()',
        trigger_name,
        qualified_table
    );
END;
$$;

INSERT INTO public.users (id, email, name)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'persona-system@local.ai-influencer.invalid',
    'Persona System'
)
ON CONFLICT (id) DO NOTHING;

DO $$
DECLARE
    missing_tables TEXT[];
BEGIN
    SELECT COALESCE(array_agg(required_table), ARRAY[]::TEXT[])
    INTO missing_tables
    FROM (
        VALUES
            ('public.users'),
            ('public.personas'),
            ('public.media_assets'),
            ('public.content'),
            ('public.chatgpt_oauth_links'),
            ('public.analytics_events')
    ) AS required(required_table)
    WHERE to_regclass(required.required_table) IS NULL;

    IF array_length(missing_tables, 1) IS NOT NULL THEN
        RAISE EXCEPTION
            '20260327_supabase_canonical_consolidation.sql requires the base app schema first. Missing tables: %',
            array_to_string(missing_tables, ', ');
    END IF;
END
$$;

CREATE OR REPLACE FUNCTION public.sync_public_user_from_auth()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.users (id, email, name, avatar_url)
    VALUES (
        NEW.id,
        COALESCE(NEW.email, 'user-' || NEW.id::text || '@local.ai-influencer.invalid'),
        COALESCE(
            NULLIF(NEW.raw_user_meta_data->>'name', ''),
            NULLIF(NEW.raw_user_meta_data->>'full_name', ''),
            NULLIF(NEW.email, '')
        ),
        NULLIF(NEW.raw_user_meta_data->>'avatar_url', '')
    )
    ON CONFLICT (id) DO UPDATE
    SET
        email = EXCLUDED.email,
        name = COALESCE(EXCLUDED.name, public.users.name),
        avatar_url = COALESCE(EXCLUDED.avatar_url, public.users.avatar_url),
        updated_at = NOW();

    RETURN NEW;
END;
$$;

DO $$
BEGIN
    IF to_regclass('auth.users') IS NOT NULL THEN
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

        EXECUTE 'DROP TRIGGER IF EXISTS on_auth_user_created_or_updated ON auth.users';
        EXECUTE $trigger$
            CREATE TRIGGER on_auth_user_created_or_updated
            AFTER INSERT OR UPDATE OF email, raw_user_meta_data
            ON auth.users
            FOR EACH ROW
            EXECUTE FUNCTION public.sync_public_user_from_auth()
        $trigger$;
    END IF;
END
$$;

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
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

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

SELECT public.ensure_table_updated_at(
    'public.media_assets',
    'created_at',
    'update_media_assets_updated_at'
);
SELECT public.ensure_table_updated_at(
    'public.workflows',
    'completed_at, started_at',
    'update_workflows_updated_at'
);
SELECT public.ensure_table_updated_at(
    'public.assistant_messages',
    'created_at',
    'update_assistant_messages_updated_at'
);
SELECT public.ensure_table_updated_at(
    'public.assistant_artifacts',
    'created_at',
    'update_assistant_artifacts_updated_at'
);
SELECT public.ensure_table_updated_at(
    'public.chatgpt_oauth_links',
    'last_used_at, linked_at',
    'update_chatgpt_oauth_links_updated_at'
);
SELECT public.ensure_table_updated_at(
    'public.engagement_actions',
    'executed_at, created_at',
    'update_engagement_actions_updated_at'
);
SELECT public.ensure_table_updated_at(
    'public.approvals',
    'approved_at, created_at',
    'update_approvals_updated_at'
);
SELECT public.ensure_table_updated_at(
    'public.analytics_events',
    'created_at',
    'update_analytics_events_updated_at'
);
SELECT public.ensure_table_updated_at(
    'public.engagement_action_logs',
    'completed_at, created_at',
    'update_engagement_action_logs_updated_at'
);
SELECT public.ensure_table_updated_at(
    'public.telegram_user_links',
    'last_verified_at, linked_at',
    'update_telegram_user_links_updated_at'
);

UPDATE public.personas
SET status = CASE
    WHEN LOWER(COALESCE(status, 'draft')) IN ('draft', 'ready', 'failed', 'archived')
        THEN LOWER(COALESCE(status, 'draft'))
    ELSE 'draft'
END;

UPDATE public.media_assets
SET
    type = CASE
        WHEN LOWER(COALESCE(type, 'document')) IN ('image', 'video', 'audio', 'document')
            THEN LOWER(COALESCE(type, 'document'))
        ELSE 'document'
    END,
    visibility = CASE
        WHEN LOWER(COALESCE(visibility, 'private')) IN ('private', 'public')
            THEN LOWER(COALESCE(visibility, 'private'))
        ELSE 'private'
    END,
    asset_origin = CASE
        WHEN LOWER(COALESCE(asset_origin, 'generated')) IN ('generated', 'uploaded', 'imported', 'backfill')
            THEN LOWER(COALESCE(asset_origin, 'generated'))
        ELSE 'generated'
    END,
    status = CASE
        WHEN LOWER(COALESCE(status, 'available')) IN ('available', 'pending', 'failed', 'archived')
            THEN LOWER(COALESCE(status, 'available'))
        WHEN LOWER(COALESCE(status, 'available')) IN ('completed', 'stored', 'success')
            THEN 'available'
        ELSE 'available'
    END,
    bucket_name = COALESCE(
        NULLIF(bucket_name, ''),
        CASE
            WHEN storage_provider = 'supabase'
                 AND (storage_path IS NOT NULL OR filename LIKE 'users/%')
                THEN 'media'
            ELSE bucket_name
        END
    ),
    storage_path = COALESCE(
        storage_path,
        CASE
            WHEN filename LIKE 'users/%' THEN filename
            ELSE NULL
        END
    );

UPDATE public.content
SET status = CASE
    WHEN LOWER(COALESCE(status, 'draft')) IN ('draft', 'pending_approval', 'approved', 'scheduled', 'published', 'failed')
        THEN LOWER(COALESCE(status, 'draft'))
    ELSE 'draft'
END;

SELECT public.run_if_table_exists(
    'public.campaigns',
    $sql$
    UPDATE public.campaigns
    SET
        status = CASE
            WHEN LOWER(COALESCE(status, 'draft')) IN ('draft', 'ready_for_review', 'active', 'paused', 'completed')
                THEN LOWER(COALESCE(status, 'draft'))
            ELSE 'draft'
        END,
        plan_status = CASE
            WHEN LOWER(COALESCE(plan_status, 'draft')) IN ('draft', 'approved', 'launched')
                THEN LOWER(COALESCE(plan_status, 'draft'))
            ELSE 'draft'
        END,
        approval_status = CASE
            WHEN LOWER(COALESCE(approval_status, 'pending')) IN ('pending', 'approved', 'rejected')
                THEN LOWER(COALESCE(approval_status, 'pending'))
            ELSE 'pending'
        END
    $sql$
);

SELECT public.run_if_table_exists(
    'public.workflows',
    $sql$
    UPDATE public.workflows
    SET status = CASE
        WHEN LOWER(COALESCE(status, 'running')) IN ('running', 'waiting_approval', 'completed', 'failed', 'canceled', 'cancelled')
            THEN LOWER(COALESCE(status, 'running'))
        ELSE 'running'
    END
    $sql$
);

SELECT public.run_if_table_exists(
    'public.social_accounts',
    $sql$
    UPDATE public.social_accounts
    SET connection_status = CASE
        WHEN LOWER(COALESCE(connection_status, 'prepared')) IN ('prepared', 'connected', 'disconnected')
            THEN LOWER(COALESCE(connection_status, 'prepared'))
        ELSE 'prepared'
    END
    $sql$
);

SELECT public.run_if_table_exists(
    'public.brand_profiles',
    $sql$
    UPDATE public.brand_profiles
    SET onboarding_status = CASE
        WHEN LOWER(COALESCE(onboarding_status, 'pending')) IN ('pending', 'completed')
            THEN LOWER(COALESCE(onboarding_status, 'pending'))
        ELSE 'pending'
    END
    $sql$
);

SELECT public.run_if_table_exists(
    'public.approvals',
    $sql$
    UPDATE public.approvals
    SET status = CASE
        WHEN LOWER(COALESCE(status, 'pending')) IN ('pending', 'approved', 'rejected')
            THEN LOWER(COALESCE(status, 'pending'))
        ELSE 'pending'
    END
    $sql$
);

SELECT public.run_if_table_exists(
    'public.postiz_schedules',
    $sql$
    UPDATE public.postiz_schedules
    SET status = CASE
        WHEN LOWER(COALESCE(status, 'scheduled')) IN ('scheduled', 'published', 'failed', 'canceled', 'cancelled')
            THEN LOWER(COALESCE(status, 'scheduled'))
        ELSE 'scheduled'
    END
    $sql$
);

SELECT public.run_if_table_exists(
    'public.engagement_actions',
    $sql$
    UPDATE public.engagement_actions
    SET status = CASE
        WHEN LOWER(COALESCE(status, 'pending')) IN ('pending', 'completed', 'failed', 'canceled', 'cancelled')
            THEN LOWER(COALESCE(status, 'pending'))
        ELSE 'pending'
    END
    $sql$
);

SELECT public.run_if_table_exists(
    'public.engagement_action_logs',
    $sql$
    UPDATE public.engagement_action_logs
    SET status = CASE
        WHEN LOWER(COALESCE(status, 'pending')) IN ('pending', 'running', 'completed', 'failed', 'canceled', 'cancelled')
            THEN LOWER(COALESCE(status, 'pending'))
        ELSE 'pending'
    END
    $sql$
);

ALTER TABLE public.personas
    DROP CONSTRAINT IF EXISTS personas_status_check;
ALTER TABLE public.personas
    ADD CONSTRAINT personas_status_check
        CHECK (status IN ('draft', 'ready', 'failed', 'archived'));

ALTER TABLE public.media_assets
    DROP CONSTRAINT IF EXISTS media_assets_type_check,
    DROP CONSTRAINT IF EXISTS media_assets_visibility_check,
    DROP CONSTRAINT IF EXISTS media_assets_asset_origin_check,
    DROP CONSTRAINT IF EXISTS media_assets_status_check;
ALTER TABLE public.media_assets
    ADD CONSTRAINT media_assets_type_check
        CHECK (type IN ('image', 'video', 'audio', 'document')),
    ADD CONSTRAINT media_assets_visibility_check
        CHECK (visibility IN ('private', 'public')),
    ADD CONSTRAINT media_assets_asset_origin_check
        CHECK (asset_origin IN ('generated', 'uploaded', 'imported', 'backfill')),
    ADD CONSTRAINT media_assets_status_check
        CHECK (status IN ('available', 'pending', 'failed', 'archived'));

ALTER TABLE public.content
    DROP CONSTRAINT IF EXISTS content_status_check;
ALTER TABLE public.content
    ADD CONSTRAINT content_status_check
        CHECK (status IN ('draft', 'pending_approval', 'approved', 'scheduled', 'published', 'failed'));

SELECT public.run_if_table_exists(
    'public.campaigns',
    $sql$
    ALTER TABLE public.campaigns
        DROP CONSTRAINT IF EXISTS campaigns_status_check,
        DROP CONSTRAINT IF EXISTS campaigns_plan_status_check,
        DROP CONSTRAINT IF EXISTS campaigns_approval_status_check
    $sql$
);
SELECT public.run_if_table_exists(
    'public.campaigns',
    $sql$
    ALTER TABLE public.campaigns
        ADD CONSTRAINT campaigns_status_check
            CHECK (status IN ('draft', 'ready_for_review', 'active', 'paused', 'completed')),
        ADD CONSTRAINT campaigns_plan_status_check
            CHECK (plan_status IN ('draft', 'approved', 'launched')),
        ADD CONSTRAINT campaigns_approval_status_check
            CHECK (approval_status IN ('pending', 'approved', 'rejected'))
    $sql$
);

SELECT public.run_if_table_exists(
    'public.workflows',
    $sql$
    ALTER TABLE public.workflows
        DROP CONSTRAINT IF EXISTS workflows_status_check
    $sql$
);
SELECT public.run_if_table_exists(
    'public.workflows',
    $sql$
    ALTER TABLE public.workflows
        ADD CONSTRAINT workflows_status_check
            CHECK (status IN ('running', 'waiting_approval', 'completed', 'failed', 'canceled', 'cancelled'))
    $sql$
);

SELECT public.run_if_table_exists(
    'public.social_accounts',
    $sql$
    ALTER TABLE public.social_accounts
        DROP CONSTRAINT IF EXISTS social_accounts_connection_status_check
    $sql$
);
SELECT public.run_if_table_exists(
    'public.social_accounts',
    $sql$
    ALTER TABLE public.social_accounts
        ADD CONSTRAINT social_accounts_connection_status_check
            CHECK (connection_status IN ('prepared', 'connected', 'disconnected'))
    $sql$
);

SELECT public.run_if_table_exists(
    'public.brand_profiles',
    $sql$
    ALTER TABLE public.brand_profiles
        DROP CONSTRAINT IF EXISTS brand_profiles_onboarding_status_check
    $sql$
);
SELECT public.run_if_table_exists(
    'public.brand_profiles',
    $sql$
    ALTER TABLE public.brand_profiles
        ADD CONSTRAINT brand_profiles_onboarding_status_check
            CHECK (onboarding_status IN ('pending', 'completed'))
    $sql$
);

SELECT public.run_if_table_exists(
    'public.approvals',
    $sql$
    ALTER TABLE public.approvals
        DROP CONSTRAINT IF EXISTS approvals_status_check
    $sql$
);
SELECT public.run_if_table_exists(
    'public.approvals',
    $sql$
    ALTER TABLE public.approvals
        ADD CONSTRAINT approvals_status_check
            CHECK (status IN ('pending', 'approved', 'rejected'))
    $sql$
);

SELECT public.run_if_table_exists(
    'public.postiz_schedules',
    $sql$
    ALTER TABLE public.postiz_schedules
        DROP CONSTRAINT IF EXISTS postiz_schedules_status_check
    $sql$
);
SELECT public.run_if_table_exists(
    'public.postiz_schedules',
    $sql$
    ALTER TABLE public.postiz_schedules
        ADD CONSTRAINT postiz_schedules_status_check
            CHECK (status IN ('scheduled', 'published', 'failed', 'canceled', 'cancelled'))
    $sql$
);

SELECT public.run_if_table_exists(
    'public.engagement_actions',
    $sql$
    ALTER TABLE public.engagement_actions
        DROP CONSTRAINT IF EXISTS engagement_actions_status_check
    $sql$
);
SELECT public.run_if_table_exists(
    'public.engagement_actions',
    $sql$
    ALTER TABLE public.engagement_actions
        ADD CONSTRAINT engagement_actions_status_check
            CHECK (status IN ('pending', 'completed', 'failed', 'canceled', 'cancelled'))
    $sql$
);

SELECT public.run_if_table_exists(
    'public.engagement_action_logs',
    $sql$
    ALTER TABLE public.engagement_action_logs
        DROP CONSTRAINT IF EXISTS engagement_action_logs_status_check
    $sql$
);
SELECT public.run_if_table_exists(
    'public.engagement_action_logs',
    $sql$
    ALTER TABLE public.engagement_action_logs
        ADD CONSTRAINT engagement_action_logs_status_check
            CHECK (status IN ('pending', 'running', 'completed', 'failed', 'canceled', 'cancelled'))
    $sql$
);

DO $$
DECLARE
    has_invalid_user_ids BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'chatgpt_oauth_links'
          AND column_name = 'user_id'
          AND udt_name <> 'uuid'
    )
    INTO has_invalid_user_ids;

    IF has_invalid_user_ids THEN
        IF EXISTS (
            SELECT 1
            FROM public.chatgpt_oauth_links
            WHERE NULLIF(BTRIM(user_id), '') IS NULL
               OR BTRIM(user_id) !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        ) THEN
            RAISE EXCEPTION
                'public.chatgpt_oauth_links contains non-UUID user_id values; clean them before applying 20260327_supabase_canonical_consolidation.sql';
        END IF;

        ALTER TABLE public.chatgpt_oauth_links
            ALTER COLUMN user_id TYPE UUID
            USING user_id::uuid;
    END IF;
END
$$;

ALTER TABLE public.chatgpt_oauth_links
    ALTER COLUMN user_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chatgpt_oauth_links_user_id_fkey'
          AND conrelid = 'public.chatgpt_oauth_links'::regclass
    ) THEN
        ALTER TABLE public.chatgpt_oauth_links
            ADD CONSTRAINT chatgpt_oauth_links_user_id_fkey
            FOREIGN KEY (user_id)
            REFERENCES public.users(id)
            ON DELETE CASCADE;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_chatgpt_oauth_links_user_active
    ON public.chatgpt_oauth_links(user_id, active, last_used_at DESC);

ALTER TABLE public.chatgpt_oauth_links ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own ChatGPT OAuth links" ON public.chatgpt_oauth_links;
CREATE POLICY "Users can view own ChatGPT OAuth links"
    ON public.chatgpt_oauth_links
    FOR ALL
    USING (auth.uid() = user_id);

ALTER TABLE public.analytics_events
    ADD COLUMN IF NOT EXISTS user_id UUID;

UPDATE public.analytics_events ae
SET user_id = c.user_id
FROM public.content c
WHERE ae.user_id IS NULL
  AND ae.content_id = c.id;

UPDATE public.analytics_events
SET user_id = '00000000-0000-0000-0000-000000000001'::uuid
WHERE user_id IS NULL;

ALTER TABLE public.analytics_events
    ALTER COLUMN user_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'analytics_events_user_id_fkey'
          AND conrelid = 'public.analytics_events'::regclass
    ) THEN
        ALTER TABLE public.analytics_events
            ADD CONSTRAINT analytics_events_user_id_fkey
            FOREIGN KEY (user_id)
            REFERENCES public.users(id)
            ON DELETE CASCADE;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_analytics_events_user_created_at
    ON public.analytics_events(user_id, created_at DESC);

ALTER TABLE public.analytics_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own analytics events" ON public.analytics_events;
CREATE POLICY "Users can view own analytics events"
    ON public.analytics_events
    FOR ALL
    USING (auth.uid() = user_id);

UPDATE public.media_assets ma
SET
    user_id = tul.user_id,
    updated_at = NOW()
FROM public.telegram_user_links tul
WHERE tul.revoked_at IS NULL
  AND ma.owner_key = 'telegram:' || tul.chat_id::text
  AND ma.user_id = '00000000-0000-0000-0000-000000000001'::uuid;

UPDATE public.personas p
SET
    user_id = linked.user_id,
    updated_at = NOW()
FROM (
    SELECT DISTINCT
        ma.persona_id,
        ma.user_id
    FROM public.media_assets ma
    WHERE ma.persona_id IS NOT NULL
      AND ma.owner_key LIKE 'telegram:%'
      AND ma.user_id <> '00000000-0000-0000-0000-000000000001'::uuid
) AS linked
WHERE p.persona_id = linked.persona_id
  AND p.user_id = '00000000-0000-0000-0000-000000000001'::uuid;

CREATE OR REPLACE FUNCTION public.apply_telegram_link_ownership()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.revoked_at IS NOT NULL THEN
        RETURN NEW;
    END IF;

    UPDATE public.media_assets ma
    SET
        user_id = NEW.user_id,
        owner_key = COALESCE(ma.owner_key, 'telegram:' || NEW.chat_id::text),
        updated_at = NOW()
    WHERE ma.owner_key = 'telegram:' || NEW.chat_id::text
      AND ma.user_id = '00000000-0000-0000-0000-000000000001'::uuid;

    UPDATE public.personas p
    SET
        user_id = NEW.user_id,
        updated_at = NOW()
    WHERE p.user_id = '00000000-0000-0000-0000-000000000001'::uuid
      AND EXISTS (
          SELECT 1
          FROM public.media_assets ma
          WHERE ma.persona_id = p.persona_id
            AND ma.user_id = NEW.user_id
      );

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS apply_telegram_link_ownership_trigger ON public.telegram_user_links;
CREATE TRIGGER apply_telegram_link_ownership_trigger
    AFTER INSERT OR UPDATE OF user_id, revoked_at
    ON public.telegram_user_links
    FOR EACH ROW EXECUTE FUNCTION public.apply_telegram_link_ownership();

DROP FUNCTION IF EXISTS public.ensure_table_updated_at(TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS public.run_if_table_exists(TEXT, TEXT);

COMMIT;
