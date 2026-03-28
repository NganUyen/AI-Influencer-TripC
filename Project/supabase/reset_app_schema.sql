-- Reset the application-owned public schema objects so the current bootstrap
-- snapshot can be reapplied on the same Supabase project.
--
-- This intentionally does NOT touch:
-- - auth schema / auth.users
-- - storage schema / storage.objects contents
-- - Supabase-managed schemas outside public
--
-- After running this file on the target database, immediately apply
-- `Project/supabase/schema.sql` to rebuild the canonical app schema.

BEGIN;

SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '0';

DO $$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'post_assets',
        'posts',
        'persona_operators',
        'customer_ai_backbone_settings',
        'telegram_user_links',
        'telegram_link_tokens',
        'telegram_subscribers',
        'engagement_action_logs',
        'postiz_schedules',
        'approvals',
        'analytics_events',
        'engagement_actions',
        'chatgpt_oauth_links',
        'assistant_artifacts',
        'assistant_messages',
        'assistant_threads',
        'brand_profiles',
        'social_accounts',
        'workflows',
        'media_assets',
        'content',
        'campaigns',
        'personas',
        'users'
    ]
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', table_name);
    END LOOP;
END
$$;

DO $$
DECLARE
    type_name TEXT;
BEGIN
    FOREACH type_name IN ARRAY ARRAY[
        'asset_role',
        'asset_type_enum',
        'campaign_status',
        'platform_enum',
        'postiz_status_enum'
    ]
    LOOP
        EXECUTE format('DROP TYPE IF EXISTS public.%I CASCADE', type_name);
    END LOOP;
END
$$;

DROP FUNCTION IF EXISTS public.apply_telegram_link_ownership() CASCADE;
DROP FUNCTION IF EXISTS public.sync_public_user_from_auth() CASCADE;
DROP FUNCTION IF EXISTS public.update_updated_at_column() CASCADE;
DROP FUNCTION IF EXISTS public.ensure_table_updated_at(TEXT, TEXT, TEXT) CASCADE;
DROP FUNCTION IF EXISTS public.run_if_table_exists(TEXT, TEXT) CASCADE;

COMMIT;
