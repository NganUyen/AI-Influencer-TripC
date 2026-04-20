-- Executable local bootstrap schema.
-- Generated from live Supabase public schema on 2026-04-20.
CREATE SCHEMA IF NOT EXISTS extensions;
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA extensions;
--
-- PostgreSQL database dump
--


-- Dumped from database version 17.6
-- Dumped by pg_dump version 17.9 (Debian 17.9-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA IF NOT EXISTS public;


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS 'standard public schema';


--
-- Name: asset_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.asset_status AS ENUM (
    'PENDING',
    'PROCESSING',
    'COMPLETED',
    'FAILED'
);


--
-- Name: apply_telegram_link_ownership(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.apply_telegram_link_ownership() RETURNS trigger
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


--
-- Name: rls_auto_enable(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.rls_auto_enable() RETURNS event_trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'pg_catalog'
    AS $$
DECLARE
  cmd record;
BEGIN
  FOR cmd IN
    SELECT *
    FROM pg_event_trigger_ddl_commands()
    WHERE command_tag IN ('CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO')
      AND object_type IN ('table','partitioned table')
  LOOP
     IF cmd.schema_name IS NOT NULL AND cmd.schema_name IN ('public') AND cmd.schema_name NOT IN ('pg_catalog','information_schema') AND cmd.schema_name NOT LIKE 'pg_toast%' AND cmd.schema_name NOT LIKE 'pg_temp%' THEN
      BEGIN
        EXECUTE format('alter table if exists %s enable row level security', cmd.object_identity);
        RAISE LOG 'rls_auto_enable: enabled RLS on %', cmd.object_identity;
      EXCEPTION
        WHEN OTHERS THEN
          RAISE LOG 'rls_auto_enable: failed to enable RLS on %', cmd.object_identity;
      END;
     ELSE
        RAISE LOG 'rls_auto_enable: skip % (either system schema or not in enforced list: %.)', cmd.object_identity, cmd.schema_name;
     END IF;
  END LOOP;
END;
$$;


--
-- Name: sync_public_user_from_auth(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sync_public_user_from_auth() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
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


--
-- Name: sync_public_user_from_auth_user(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sync_public_user_from_auth_user() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
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


--
-- Name: update_modified_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_modified_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: analytics_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.analytics_events (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    content_id uuid,
    event_type text NOT NULL,
    platform text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    user_id uuid NOT NULL
);


--
-- Name: approvals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.approvals (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    content_id uuid,
    workflow_id text,
    approver_id uuid NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    feedback text,
    approved_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    channel text DEFAULT 'telegram'::text NOT NULL,
    request_key text,
    telegram_message_ref jsonb,
    decision_source text,
    decision_payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT approvals_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text, 'save'::text, 'discard'::text])))
);


--
-- Name: assistant_artifacts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assistant_artifacts (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    thread_id uuid NOT NULL,
    artifact_type text NOT NULL,
    title text NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: assistant_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assistant_messages (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    thread_id uuid NOT NULL,
    role text NOT NULL,
    content text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: assistant_threads; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assistant_threads (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    title text DEFAULT 'New strategy thread'::text NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    last_message_preview text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: brand_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.brand_profiles (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    product_name text NOT NULL,
    website_url text,
    audience text,
    offer_summary text,
    tone_voice text,
    campaign_goals jsonb DEFAULT '[]'::jsonb,
    asset_urls jsonb DEFAULT '[]'::jsonb,
    timezone text DEFAULT 'UTC'::text NOT NULL,
    posting_cadence jsonb DEFAULT '{}'::jsonb,
    approval_preferences jsonb DEFAULT '{"mode": "review_first"}'::jsonb,
    telegram_contact text,
    onboarding_status text DEFAULT 'pending'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT brand_profiles_onboarding_status_check CHECK ((onboarding_status = ANY (ARRAY['pending'::text, 'completed'::text])))
);


--
-- Name: campaigns; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.campaigns (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    name text NOT NULL,
    description text,
    status text DEFAULT 'draft'::text NOT NULL,
    start_date timestamp with time zone NOT NULL,
    end_date timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    brand_profile_id uuid,
    plan_status text DEFAULT 'draft'::text NOT NULL,
    approval_status text DEFAULT 'pending'::text NOT NULL,
    approval_feedback text,
    approved_at timestamp with time zone,
    launched_at timestamp with time zone,
    active_workflow_id text,
    target_platforms text[] DEFAULT '{}'::text[],
    connected_account_ids uuid[] DEFAULT '{}'::uuid[],
    plan_data jsonb DEFAULT '{}'::jsonb,
    artifact_summary jsonb DEFAULT '{}'::jsonb,
    CONSTRAINT campaigns_approval_status_check CHECK ((approval_status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text]))),
    CONSTRAINT campaigns_plan_status_check CHECK ((plan_status = ANY (ARRAY['draft'::text, 'approved'::text, 'launched'::text]))),
    CONSTRAINT campaigns_status_check CHECK ((status = ANY (ARRAY['draft'::text, 'ready_for_review'::text, 'active'::text, 'paused'::text, 'completed'::text])))
);


--
-- Name: chatgpt_oauth_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chatgpt_oauth_links (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    chatgpt_subject text NOT NULL,
    user_id uuid NOT NULL,
    display_name text,
    session_id text NOT NULL,
    linked_at timestamp with time zone DEFAULT now(),
    last_used_at timestamp with time zone DEFAULT now(),
    active boolean DEFAULT true NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: content; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.content (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    campaign_id uuid,
    title text NOT NULL,
    content text NOT NULL,
    platform text[] NOT NULL,
    status text DEFAULT 'draft'::text NOT NULL,
    scheduled_at timestamp with time zone,
    published_at timestamp with time zone,
    media_urls text[],
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT content_status_check CHECK ((status = ANY (ARRAY['draft'::text, 'pending_approval'::text, 'approved'::text, 'scheduled'::text, 'published'::text, 'failed'::text])))
);


--
-- Name: customer_ai_backbone_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.customer_ai_backbone_settings (
    user_id uuid NOT NULL,
    access_mode text DEFAULT 'platform_managed'::text NOT NULL,
    openclaw_api_url text,
    encrypted_openclaw_api_key text,
    chatgpt_subject text,
    chatgpt_display_name text,
    chatgpt_subscription_tier text,
    encrypted_connector_session_token text,
    connector_session_id text,
    connector_session_expires_at timestamp with time zone,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT customer_ai_backbone_settings_access_mode_check CHECK ((access_mode = ANY (ARRAY['platform_managed'::text, 'customer_api_key'::text, 'chatgpt_oauth'::text]))),
    CONSTRAINT customer_ai_backbone_settings_subscription_tier_check CHECK (((chatgpt_subscription_tier IS NULL) OR (chatgpt_subscription_tier = ANY (ARRAY['plus'::text, 'pro'::text]))))
);


--
-- Name: engagement_action_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.engagement_action_logs (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    workflow_id text,
    social_account_id uuid,
    platform text NOT NULL,
    target_post_id text,
    target_url text,
    action_types text[] DEFAULT '{}'::text[] NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    provider_job_id text,
    result_payload jsonb DEFAULT '{}'::jsonb,
    error_message text,
    created_at timestamp with time zone DEFAULT now(),
    completed_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT engagement_action_logs_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'running'::text, 'completed'::text, 'failed'::text, 'canceled'::text, 'cancelled'::text])))
);


--
-- Name: engagement_actions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.engagement_actions (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    social_account_id uuid NOT NULL,
    target_content_id uuid,
    action_type text NOT NULL,
    platform text NOT NULL,
    target_url text,
    comment_text text,
    status text DEFAULT 'pending'::text NOT NULL,
    executed_at timestamp with time zone,
    error_message text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT engagement_actions_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'completed'::text, 'failed'::text, 'canceled'::text, 'cancelled'::text])))
);


--
-- Name: media_assets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.media_assets (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    content_id uuid,
    persona_id text,
    owner_key text,
    url text NOT NULL,
    source_url text,
    type text NOT NULL,
    filename text NOT NULL,
    bucket_name text,
    storage_path text,
    storage_provider text DEFAULT 'supabase'::text NOT NULL,
    visibility text DEFAULT 'private'::text NOT NULL,
    asset_origin text DEFAULT 'generated'::text NOT NULL,
    status text DEFAULT 'available'::text NOT NULL,
    provider_job_id text,
    size integer,
    mime_type text,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT media_assets_asset_origin_check CHECK ((asset_origin = ANY (ARRAY['generated'::text, 'uploaded'::text, 'imported'::text, 'backfill'::text]))),
    CONSTRAINT media_assets_status_check CHECK ((status = ANY (ARRAY['available'::text, 'pending'::text, 'failed'::text, 'archived'::text]))),
    CONSTRAINT media_assets_type_check CHECK ((type = ANY (ARRAY['image'::text, 'video'::text, 'audio'::text, 'document'::text]))),
    CONSTRAINT media_assets_visibility_check CHECK ((visibility = ANY (ARRAY['private'::text, 'public'::text])))
);


--
-- Name: personas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.personas (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    user_id uuid DEFAULT '00000000-0000-0000-0000-000000000001'::uuid NOT NULL,
    name text DEFAULT ''::text NOT NULL,
    description text,
    voice_profile text,
    platforms text[] DEFAULT '{}'::text[] NOT NULL,
    is_active boolean DEFAULT true,
    avatar_url text,
    proxy_config jsonb,
    persona_id text,
    display_name text,
    language text DEFAULT 'English'::text,
    tts_voice text,
    avatar_image_url text,
    avatar_source_type text,
    avatar_prompt text,
    heygen_avatar_id text,
    status text DEFAULT 'draft'::text,
    video_count integer DEFAULT 0,
    tone_default text,
    market_default text,
    thumbnail_url text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    avatar_media_asset_id uuid,
    gender character varying(20),
    channel_configs jsonb DEFAULT '{}'::jsonb,
    CONSTRAINT personas_status_check CHECK ((status = ANY (ARRAY['draft'::text, 'generating'::text, 'ready'::text, 'failed'::text, 'archived'::text])))
);


--
-- Name: postiz_schedules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.postiz_schedules (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    content_id uuid NOT NULL,
    platform text NOT NULL,
    postiz_post_id text,
    scheduled_for timestamp with time zone,
    status text DEFAULT 'scheduled'::text NOT NULL,
    response_payload jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT postiz_schedules_status_check CHECK ((status = ANY (ARRAY['scheduled'::text, 'published'::text, 'failed'::text, 'canceled'::text, 'cancelled'::text])))
);


--
-- Name: social_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.social_accounts (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    persona_id uuid,
    platform text NOT NULL,
    account_name text NOT NULL,
    account_handle text,
    is_primary boolean DEFAULT false,
    oauth_token text,
    oauth_secret text,
    proxy_config jsonb,
    is_active boolean DEFAULT true,
    last_used_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    account_health integer,
    followers_count integer,
    ban_risk_level text,
    last_api_response jsonb DEFAULT '{}'::jsonb,
    warnings text[] DEFAULT '{}'::text[],
    connection_status text DEFAULT 'prepared'::text NOT NULL,
    provider_account_id text,
    display_name text,
    connection_method text,
    scopes text[] DEFAULT '{}'::text[],
    token_ref text,
    encrypted_token_bundle text,
    token_expires_at timestamp with time zone,
    last_sync_at timestamp with time zone,
    last_error text,
    publish_capabilities jsonb DEFAULT '{}'::jsonb,
    CONSTRAINT social_accounts_connection_status_check CHECK ((connection_status = ANY (ARRAY['prepared'::text, 'connected'::text, 'disconnected'::text])))
);


--
-- Name: system_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.system_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    level text NOT NULL,
    category text NOT NULL,
    message text NOT NULL,
    details jsonb,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE system_logs; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.system_logs IS 'System-wide event and error logs for the Operations Console.';


--
-- Name: telegram_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.telegram_events (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    telegram_update_id bigint NOT NULL,
    chat_id bigint NOT NULL,
    linked_user_id uuid,
    route text DEFAULT 'received'::text NOT NULL,
    approval_id uuid,
    workflow_id text,
    event_type text NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: telegram_link_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.telegram_link_tokens (
    token_hash text NOT NULL,
    user_id uuid,
    expires_at timestamp with time zone NOT NULL,
    used_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: telegram_subscribers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.telegram_subscribers (
    chat_id bigint NOT NULL,
    chat_type character varying(20) DEFAULT 'private'::character varying NOT NULL,
    username character varying(255),
    first_name character varying(255),
    role character varying(20) DEFAULT 'OPERATOR'::character varying NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    registered_at timestamp with time zone DEFAULT now() NOT NULL,
    last_seen_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT telegram_subscribers_chat_type_check CHECK (((chat_type)::text = ANY ((ARRAY['private'::character varying, 'group'::character varying, 'supergroup'::character varying])::text[]))),
    CONSTRAINT telegram_subscribers_role_check CHECK (((role)::text = ANY ((ARRAY['ADMIN'::character varying, 'OPERATOR'::character varying, 'VIEWER'::character varying])::text[])))
);


--
-- Name: telegram_user_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.telegram_user_links (
    chat_id bigint NOT NULL,
    user_id uuid NOT NULL,
    telegram_username text,
    linked_at timestamp with time zone DEFAULT now() NOT NULL,
    last_verified_at timestamp with time zone DEFAULT now() NOT NULL,
    revoked_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    email text NOT NULL,
    name text,
    avatar_url text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: video_render_plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.video_render_plans (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    campaign_id uuid,
    source_url text NOT NULL,
    objective text,
    script_text text NOT NULL,
    scenes_data jsonb DEFAULT '[]'::jsonb NOT NULL,
    duration_estimate double precision,
    status text DEFAULT 'generated'::text,
    workflow_id text,
    video_url text,
    publish_settings jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    approved_at timestamp with time zone,
    page_review_snapshot jsonb,
    input_mode text DEFAULT 'ai_autonomous'::text,
    persona_id text NOT NULL,
    creative_preferences jsonb DEFAULT '{}'::jsonb NOT NULL,
    page_review_data jsonb DEFAULT '{}'::jsonb NOT NULL
);


--
-- Name: workflows; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.workflows (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    workflow_id text NOT NULL,
    user_id uuid NOT NULL,
    type text NOT NULL,
    status text DEFAULT 'running'::text NOT NULL,
    current_step text,
    progress integer DEFAULT 0,
    input_data jsonb,
    output_data jsonb,
    error_message text,
    started_at timestamp with time zone DEFAULT now(),
    completed_at timestamp with time zone,
    approval_required boolean DEFAULT false,
    approval_status text,
    approved_by uuid,
    approval_feedback text,
    approved_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    channel text,
    request_key text,
    telegram_message_ref jsonb,
    decision_source text,
    decision_payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT workflows_status_check CHECK ((status = ANY (ARRAY['running'::text, 'waiting_approval'::text, 'completed'::text, 'failed'::text, 'canceled'::text, 'cancelled'::text])))
);


--
-- Name: analytics_events analytics_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.analytics_events
    ADD CONSTRAINT analytics_events_pkey PRIMARY KEY (id);


--
-- Name: approvals approvals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approvals
    ADD CONSTRAINT approvals_pkey PRIMARY KEY (id);


--
-- Name: assistant_artifacts assistant_artifacts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_artifacts
    ADD CONSTRAINT assistant_artifacts_pkey PRIMARY KEY (id);


--
-- Name: assistant_messages assistant_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_messages
    ADD CONSTRAINT assistant_messages_pkey PRIMARY KEY (id);


--
-- Name: assistant_threads assistant_threads_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_threads
    ADD CONSTRAINT assistant_threads_pkey PRIMARY KEY (id);


--
-- Name: brand_profiles brand_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.brand_profiles
    ADD CONSTRAINT brand_profiles_pkey PRIMARY KEY (id);


--
-- Name: brand_profiles brand_profiles_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.brand_profiles
    ADD CONSTRAINT brand_profiles_user_id_key UNIQUE (user_id);


--
-- Name: campaigns campaigns_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT campaigns_pkey PRIMARY KEY (id);


--
-- Name: chatgpt_oauth_links chatgpt_oauth_links_chatgpt_subject_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chatgpt_oauth_links
    ADD CONSTRAINT chatgpt_oauth_links_chatgpt_subject_key UNIQUE (chatgpt_subject);


--
-- Name: chatgpt_oauth_links chatgpt_oauth_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chatgpt_oauth_links
    ADD CONSTRAINT chatgpt_oauth_links_pkey PRIMARY KEY (id);


--
-- Name: content content_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content
    ADD CONSTRAINT content_pkey PRIMARY KEY (id);


--
-- Name: customer_ai_backbone_settings customer_ai_backbone_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_ai_backbone_settings
    ADD CONSTRAINT customer_ai_backbone_settings_pkey PRIMARY KEY (user_id);


--
-- Name: engagement_action_logs engagement_action_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.engagement_action_logs
    ADD CONSTRAINT engagement_action_logs_pkey PRIMARY KEY (id);


--
-- Name: engagement_actions engagement_actions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.engagement_actions
    ADD CONSTRAINT engagement_actions_pkey PRIMARY KEY (id);


--
-- Name: media_assets media_assets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.media_assets
    ADD CONSTRAINT media_assets_pkey PRIMARY KEY (id);


--
-- Name: personas personas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personas
    ADD CONSTRAINT personas_pkey PRIMARY KEY (id);


--
-- Name: postiz_schedules postiz_schedules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.postiz_schedules
    ADD CONSTRAINT postiz_schedules_pkey PRIMARY KEY (id);


--
-- Name: social_accounts social_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.social_accounts
    ADD CONSTRAINT social_accounts_pkey PRIMARY KEY (id);


--
-- Name: system_logs system_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_logs
    ADD CONSTRAINT system_logs_pkey PRIMARY KEY (id);


--
-- Name: telegram_events telegram_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_events
    ADD CONSTRAINT telegram_events_pkey PRIMARY KEY (id);


--
-- Name: telegram_events telegram_events_telegram_update_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_events
    ADD CONSTRAINT telegram_events_telegram_update_id_key UNIQUE (telegram_update_id);


--
-- Name: telegram_link_tokens telegram_link_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_link_tokens
    ADD CONSTRAINT telegram_link_tokens_pkey PRIMARY KEY (token_hash);


--
-- Name: telegram_subscribers telegram_subscribers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_subscribers
    ADD CONSTRAINT telegram_subscribers_pkey PRIMARY KEY (chat_id);


--
-- Name: telegram_user_links telegram_user_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_user_links
    ADD CONSTRAINT telegram_user_links_pkey PRIMARY KEY (chat_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: video_render_plans video_render_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.video_render_plans
    ADD CONSTRAINT video_render_plans_pkey PRIMARY KEY (id);


--
-- Name: workflows workflows_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflows
    ADD CONSTRAINT workflows_pkey PRIMARY KEY (id);


--
-- Name: workflows workflows_workflow_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflows
    ADD CONSTRAINT workflows_workflow_id_key UNIQUE (workflow_id);


--
-- Name: idx_analytics_events_user_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_analytics_events_user_created_at ON public.analytics_events USING btree (user_id, created_at DESC);


--
-- Name: idx_approvals_content_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_approvals_content_id ON public.approvals USING btree (content_id);


--
-- Name: idx_approvals_request_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_approvals_request_key ON public.approvals USING btree (request_key) WHERE (request_key IS NOT NULL);


--
-- Name: idx_approvals_workflow_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_approvals_workflow_id ON public.approvals USING btree (workflow_id);


--
-- Name: idx_assistant_artifacts_thread_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assistant_artifacts_thread_id ON public.assistant_artifacts USING btree (thread_id, created_at DESC);


--
-- Name: idx_assistant_messages_thread_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assistant_messages_thread_id ON public.assistant_messages USING btree (thread_id, created_at);


--
-- Name: idx_assistant_threads_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assistant_threads_user_id ON public.assistant_threads USING btree (user_id, updated_at DESC);


--
-- Name: idx_brand_profiles_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_brand_profiles_user_id ON public.brand_profiles USING btree (user_id);


--
-- Name: idx_campaigns_approval_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_campaigns_approval_status ON public.campaigns USING btree (user_id, approval_status, updated_at DESC);


--
-- Name: idx_campaigns_brand_profile_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_campaigns_brand_profile_id ON public.campaigns USING btree (brand_profile_id);


--
-- Name: idx_chatgpt_oauth_links_last_used; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chatgpt_oauth_links_last_used ON public.chatgpt_oauth_links USING btree (last_used_at DESC);


--
-- Name: idx_chatgpt_oauth_links_subject; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chatgpt_oauth_links_subject ON public.chatgpt_oauth_links USING btree (chatgpt_subject);


--
-- Name: idx_chatgpt_oauth_links_user_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chatgpt_oauth_links_user_active ON public.chatgpt_oauth_links USING btree (user_id, active, last_used_at DESC);


--
-- Name: idx_content_campaign_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_content_campaign_id ON public.content USING btree (campaign_id);


--
-- Name: idx_content_scheduled_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_content_scheduled_at ON public.content USING btree (scheduled_at);


--
-- Name: idx_content_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_content_status ON public.content USING btree (status);


--
-- Name: idx_content_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_content_user_id ON public.content USING btree (user_id);


--
-- Name: idx_customer_ai_backbone_settings_access_mode; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_customer_ai_backbone_settings_access_mode ON public.customer_ai_backbone_settings USING btree (access_mode);


--
-- Name: idx_engagement_action_logs_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_engagement_action_logs_status ON public.engagement_action_logs USING btree (status);


--
-- Name: idx_engagement_action_logs_workflow_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_engagement_action_logs_workflow_id ON public.engagement_action_logs USING btree (workflow_id);


--
-- Name: idx_engagement_actions_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_engagement_actions_account_id ON public.engagement_actions USING btree (social_account_id);


--
-- Name: idx_engagement_actions_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_engagement_actions_status ON public.engagement_actions USING btree (status);


--
-- Name: idx_media_assets_bucket_path; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_media_assets_bucket_path ON public.media_assets USING btree (bucket_name, storage_path);


--
-- Name: idx_media_assets_content_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_media_assets_content_id ON public.media_assets USING btree (content_id);


--
-- Name: idx_media_assets_storage_identity; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_media_assets_storage_identity ON public.media_assets USING btree (storage_provider, bucket_name, storage_path);


--
-- Name: idx_media_assets_user_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_media_assets_user_created_at ON public.media_assets USING btree (user_id, created_at DESC);


--
-- Name: idx_media_assets_user_persona_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_media_assets_user_persona_created_at ON public.media_assets USING btree (user_id, persona_id, created_at DESC);


--
-- Name: idx_personas_avatar_media_asset_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_personas_avatar_media_asset_id ON public.personas USING btree (avatar_media_asset_id);


--
-- Name: idx_personas_registry_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_personas_registry_status ON public.personas USING btree (status);


--
-- Name: idx_personas_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_personas_user_id ON public.personas USING btree (user_id);


--
-- Name: idx_personas_user_persona_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_personas_user_persona_id ON public.personas USING btree (user_id, persona_id);


--
-- Name: idx_personas_user_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_personas_user_status ON public.personas USING btree (user_id, status, updated_at DESC);


--
-- Name: idx_postiz_schedules_content_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_postiz_schedules_content_id ON public.postiz_schedules USING btree (content_id);


--
-- Name: idx_postiz_schedules_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_postiz_schedules_status ON public.postiz_schedules USING btree (status);


--
-- Name: idx_social_accounts_connection_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_social_accounts_connection_status ON public.social_accounts USING btree (user_id, connection_status, platform);


--
-- Name: idx_social_accounts_customer_account; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_social_accounts_customer_account ON public.social_accounts USING btree (user_id, platform, account_handle, is_primary);


--
-- Name: idx_social_accounts_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_social_accounts_user_id ON public.social_accounts USING btree (user_id);


--
-- Name: idx_system_logs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_system_logs_created_at ON public.system_logs USING btree (created_at DESC);


--
-- Name: idx_system_logs_level; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_system_logs_level ON public.system_logs USING btree (level);


--
-- Name: idx_telegram_events_chat_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_telegram_events_chat_created ON public.telegram_events USING btree (chat_id, created_at DESC);


--
-- Name: idx_telegram_link_tokens_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_telegram_link_tokens_expires_at ON public.telegram_link_tokens USING btree (expires_at);


--
-- Name: idx_telegram_link_tokens_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_telegram_link_tokens_user_id ON public.telegram_link_tokens USING btree (user_id, created_at DESC);


--
-- Name: idx_telegram_subscribers_active_role; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_telegram_subscribers_active_role ON public.telegram_subscribers USING btree (is_active, role, registered_at);


--
-- Name: idx_telegram_user_links_active_user; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_telegram_user_links_active_user ON public.telegram_user_links USING btree (user_id) WHERE (revoked_at IS NULL);


--
-- Name: idx_telegram_user_links_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_telegram_user_links_user_id ON public.telegram_user_links USING btree (user_id, linked_at DESC);


--
-- Name: idx_video_render_plans_campaign_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_video_render_plans_campaign_id ON public.video_render_plans USING btree (campaign_id);


--
-- Name: idx_video_render_plans_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_video_render_plans_user_id ON public.video_render_plans USING btree (user_id);


--
-- Name: idx_video_render_plans_user_persona_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_video_render_plans_user_persona_id ON public.video_render_plans USING btree (user_id, persona_id);


--
-- Name: idx_video_render_plans_workflow_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_video_render_plans_workflow_id ON public.video_render_plans USING btree (workflow_id);


--
-- Name: idx_workflows_request_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_workflows_request_key ON public.workflows USING btree (request_key) WHERE (request_key IS NOT NULL);


--
-- Name: idx_workflows_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_workflows_status ON public.workflows USING btree (status);


--
-- Name: idx_workflows_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_workflows_user_id ON public.workflows USING btree (user_id);


--
-- Name: telegram_user_links apply_telegram_link_ownership_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER apply_telegram_link_ownership_trigger AFTER INSERT OR UPDATE OF user_id, revoked_at ON public.telegram_user_links FOR EACH ROW EXECUTE FUNCTION public.apply_telegram_link_ownership();


--
-- Name: analytics_events update_analytics_events_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_analytics_events_updated_at BEFORE UPDATE ON public.analytics_events FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: approvals update_approvals_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_approvals_updated_at BEFORE UPDATE ON public.approvals FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: assistant_artifacts update_assistant_artifacts_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_assistant_artifacts_updated_at BEFORE UPDATE ON public.assistant_artifacts FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: assistant_messages update_assistant_messages_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_assistant_messages_updated_at BEFORE UPDATE ON public.assistant_messages FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: assistant_threads update_assistant_threads_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_assistant_threads_updated_at BEFORE UPDATE ON public.assistant_threads FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: brand_profiles update_brand_profiles_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_brand_profiles_updated_at BEFORE UPDATE ON public.brand_profiles FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: campaigns update_campaigns_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_campaigns_updated_at BEFORE UPDATE ON public.campaigns FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: chatgpt_oauth_links update_chatgpt_oauth_links_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_chatgpt_oauth_links_updated_at BEFORE UPDATE ON public.chatgpt_oauth_links FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: content update_content_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_content_updated_at BEFORE UPDATE ON public.content FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: customer_ai_backbone_settings update_customer_ai_backbone_settings_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_customer_ai_backbone_settings_updated_at BEFORE UPDATE ON public.customer_ai_backbone_settings FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: engagement_action_logs update_engagement_action_logs_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_engagement_action_logs_updated_at BEFORE UPDATE ON public.engagement_action_logs FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: engagement_actions update_engagement_actions_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_engagement_actions_updated_at BEFORE UPDATE ON public.engagement_actions FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: media_assets update_media_assets_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_media_assets_updated_at BEFORE UPDATE ON public.media_assets FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: personas update_personas_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_personas_updated_at BEFORE UPDATE ON public.personas FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: social_accounts update_social_accounts_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_social_accounts_updated_at BEFORE UPDATE ON public.social_accounts FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: telegram_link_tokens update_telegram_link_tokens_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_telegram_link_tokens_updated_at BEFORE UPDATE ON public.telegram_link_tokens FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: telegram_user_links update_telegram_user_links_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_telegram_user_links_updated_at BEFORE UPDATE ON public.telegram_user_links FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: users update_users_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: workflows update_workflows_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_workflows_updated_at BEFORE UPDATE ON public.workflows FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: analytics_events analytics_events_content_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.analytics_events
    ADD CONSTRAINT analytics_events_content_id_fkey FOREIGN KEY (content_id) REFERENCES public.content(id) ON DELETE CASCADE;


--
-- Name: analytics_events analytics_events_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.analytics_events
    ADD CONSTRAINT analytics_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: approvals approvals_approver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approvals
    ADD CONSTRAINT approvals_approver_id_fkey FOREIGN KEY (approver_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: approvals approvals_content_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approvals
    ADD CONSTRAINT approvals_content_id_fkey FOREIGN KEY (content_id) REFERENCES public.content(id) ON DELETE CASCADE;


--
-- Name: approvals approvals_workflow_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approvals
    ADD CONSTRAINT approvals_workflow_id_fkey FOREIGN KEY (workflow_id) REFERENCES public.workflows(workflow_id) ON DELETE SET NULL;


--
-- Name: assistant_artifacts assistant_artifacts_thread_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_artifacts
    ADD CONSTRAINT assistant_artifacts_thread_id_fkey FOREIGN KEY (thread_id) REFERENCES public.assistant_threads(id) ON DELETE CASCADE;


--
-- Name: assistant_messages assistant_messages_thread_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_messages
    ADD CONSTRAINT assistant_messages_thread_id_fkey FOREIGN KEY (thread_id) REFERENCES public.assistant_threads(id) ON DELETE CASCADE;


--
-- Name: assistant_threads assistant_threads_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_threads
    ADD CONSTRAINT assistant_threads_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: brand_profiles brand_profiles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.brand_profiles
    ADD CONSTRAINT brand_profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: campaigns campaigns_brand_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT campaigns_brand_profile_id_fkey FOREIGN KEY (brand_profile_id) REFERENCES public.brand_profiles(id) ON DELETE SET NULL;


--
-- Name: campaigns campaigns_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT campaigns_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: chatgpt_oauth_links chatgpt_oauth_links_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chatgpt_oauth_links
    ADD CONSTRAINT chatgpt_oauth_links_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: content content_campaign_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content
    ADD CONSTRAINT content_campaign_id_fkey FOREIGN KEY (campaign_id) REFERENCES public.campaigns(id) ON DELETE SET NULL;


--
-- Name: content content_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content
    ADD CONSTRAINT content_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: customer_ai_backbone_settings customer_ai_backbone_settings_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_ai_backbone_settings
    ADD CONSTRAINT customer_ai_backbone_settings_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: engagement_action_logs engagement_action_logs_social_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.engagement_action_logs
    ADD CONSTRAINT engagement_action_logs_social_account_id_fkey FOREIGN KEY (social_account_id) REFERENCES public.social_accounts(id) ON DELETE SET NULL;


--
-- Name: engagement_action_logs engagement_action_logs_workflow_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.engagement_action_logs
    ADD CONSTRAINT engagement_action_logs_workflow_id_fkey FOREIGN KEY (workflow_id) REFERENCES public.workflows(workflow_id) ON DELETE SET NULL;


--
-- Name: engagement_actions engagement_actions_social_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.engagement_actions
    ADD CONSTRAINT engagement_actions_social_account_id_fkey FOREIGN KEY (social_account_id) REFERENCES public.social_accounts(id) ON DELETE CASCADE;


--
-- Name: engagement_actions engagement_actions_target_content_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.engagement_actions
    ADD CONSTRAINT engagement_actions_target_content_id_fkey FOREIGN KEY (target_content_id) REFERENCES public.content(id) ON DELETE SET NULL;


--
-- Name: media_assets media_assets_content_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.media_assets
    ADD CONSTRAINT media_assets_content_id_fkey FOREIGN KEY (content_id) REFERENCES public.content(id) ON DELETE SET NULL;


--
-- Name: media_assets media_assets_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.media_assets
    ADD CONSTRAINT media_assets_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: personas personas_avatar_media_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personas
    ADD CONSTRAINT personas_avatar_media_asset_id_fkey FOREIGN KEY (avatar_media_asset_id) REFERENCES public.media_assets(id) ON DELETE SET NULL;


--
-- Name: personas personas_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personas
    ADD CONSTRAINT personas_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: postiz_schedules postiz_schedules_content_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.postiz_schedules
    ADD CONSTRAINT postiz_schedules_content_id_fkey FOREIGN KEY (content_id) REFERENCES public.content(id) ON DELETE CASCADE;


--
-- Name: social_accounts social_accounts_persona_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.social_accounts
    ADD CONSTRAINT social_accounts_persona_id_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id) ON DELETE SET NULL;


--
-- Name: social_accounts social_accounts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.social_accounts
    ADD CONSTRAINT social_accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: telegram_events telegram_events_approval_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_events
    ADD CONSTRAINT telegram_events_approval_id_fkey FOREIGN KEY (approval_id) REFERENCES public.approvals(id);


--
-- Name: telegram_events telegram_events_linked_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_events
    ADD CONSTRAINT telegram_events_linked_user_id_fkey FOREIGN KEY (linked_user_id) REFERENCES public.users(id);


--
-- Name: telegram_events telegram_events_workflow_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_events
    ADD CONSTRAINT telegram_events_workflow_id_fkey FOREIGN KEY (workflow_id) REFERENCES public.workflows(workflow_id);


--
-- Name: telegram_link_tokens telegram_link_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_link_tokens
    ADD CONSTRAINT telegram_link_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: telegram_user_links telegram_user_links_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_user_links
    ADD CONSTRAINT telegram_user_links_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: video_render_plans video_render_plans_campaign_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.video_render_plans
    ADD CONSTRAINT video_render_plans_campaign_id_fkey FOREIGN KEY (campaign_id) REFERENCES public.campaigns(id);


--
-- Name: video_render_plans video_render_plans_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.video_render_plans
    ADD CONSTRAINT video_render_plans_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: workflows workflows_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflows
    ADD CONSTRAINT workflows_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: workflows workflows_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflows
    ADD CONSTRAINT workflows_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: users Users can update own data; Type: POLICY; Schema: public; Owner: -
--



--
-- Name: customer_ai_backbone_settings Users can view own AI backbone settings; Type: POLICY; Schema: public; Owner: -
--



--
-- Name: chatgpt_oauth_links Users can view own ChatGPT OAuth links; Type: POLICY; Schema: public; Owner: -
--



--
-- Name: social_accounts Users can view own accounts; Type: POLICY; Schema: public; Owner: -
--



--
-- Name: analytics_events Users can view own analytics events; Type: POLICY; Schema: public; Owner: -
--



--
-- Name: approvals Users can view own approvals; Type: POLICY; Schema: public; Owner: -
--



--
-- Name: assistant_artifacts Users can view own assistant artifacts; Type: POLICY; Schema: public; Owner: -
--



--
-- Name: assistant_messages Users can view own assistant messages; Type: POLICY; Schema: public; Owner: -
--



--
-- Name: assistant_threads Users can view own assistant threads; Type: POLICY; Schema: public; Owner: -
--



--
-- Name: brand_profiles Users can view own brand profiles; Type: POLICY; Schema: public; Owner: -
--



--
-- Name: campaigns Users can view own campaigns; Type: POLICY; Schema: public; Owner: -
--



--
-- Name: content Users can view own content; Type: POLICY; Schema: public; Owner: -
--



--
-- Name: users Users can view own data; Type: POLICY; Schema: public; Owner: -
--



--
-- Name: engagement_action_logs Users can view own engagement logs; Type: POLICY; Schema: public; Owner: -
--



--
-- Name: media_assets Users can view own media; Type: POLICY; Schema: public; Owner: -
--



--
-- Name: personas Users can view own personas; Type: POLICY; Schema: public; Owner: -
--



--
-- Name: postiz_schedules Users can view own postiz schedules; Type: POLICY; Schema: public; Owner: -
--



--
-- Name: telegram_link_tokens Users can view own telegram link tokens; Type: POLICY; Schema: public; Owner: -
--



--
-- Name: telegram_user_links Users can view own telegram links; Type: POLICY; Schema: public; Owner: -
--



--
-- Name: workflows Users can view own workflows; Type: POLICY; Schema: public; Owner: -
--



--
-- Name: analytics_events; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: approvals; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: assistant_artifacts; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: assistant_messages; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: assistant_threads; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: brand_profiles; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: campaigns; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: chatgpt_oauth_links; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: content; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: customer_ai_backbone_settings; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: engagement_action_logs; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: engagement_actions; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: media_assets; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: personas; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: postiz_schedules; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: social_accounts; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: system_logs; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: telegram_events; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: telegram_link_tokens; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: telegram_subscribers; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: telegram_user_links; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: users; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: video_render_plans; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- Name: workflows; Type: ROW SECURITY; Schema: public; Owner: -
--


--
-- PostgreSQL database dump complete
--


