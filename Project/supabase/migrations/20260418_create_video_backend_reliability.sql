DO $$
DECLARE
    persona_column_type TEXT;
    unresolved_count INTEGER;
BEGIN
    SELECT data_type
    INTO persona_column_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'video_render_plans'
      AND column_name = 'persona_id';

    IF persona_column_type IS NULL THEN
        RAISE EXCEPTION 'public.video_render_plans.persona_id does not exist';
    END IF;

    ALTER TABLE public.video_render_plans
        ADD COLUMN IF NOT EXISTS persona_id_text TEXT;

    IF persona_column_type <> 'text' THEN
        UPDATE public.video_render_plans AS plans
        SET persona_id_text = personas.persona_id
        FROM public.personas AS personas
        WHERE plans.persona_id_text IS NULL
          AND plans.persona_id = personas.id;

        SELECT COUNT(*)
        INTO unresolved_count
        FROM public.video_render_plans
        WHERE persona_id IS NOT NULL
          AND persona_id_text IS NULL;

        IF unresolved_count > 0 THEN
            RAISE EXCEPTION
                'Failed to backfill text persona_id for % existing video_render_plans rows',
                unresolved_count;
        END IF;

        ALTER TABLE public.video_render_plans
            DROP CONSTRAINT IF EXISTS video_render_plans_persona_id_fkey;

        ALTER TABLE public.video_render_plans
            DROP COLUMN persona_id;

        ALTER TABLE public.video_render_plans
            RENAME COLUMN persona_id_text TO persona_id;
    ELSE
        UPDATE public.video_render_plans
        SET persona_id_text = persona_id
        WHERE persona_id_text IS NULL;

        ALTER TABLE public.video_render_plans
            DROP COLUMN IF EXISTS persona_id_text;
    END IF;
END $$;

ALTER TABLE public.video_render_plans
    ADD COLUMN IF NOT EXISTS creative_preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS page_review_data JSONB NOT NULL DEFAULT '{}'::jsonb;

UPDATE public.video_render_plans
SET creative_preferences = COALESCE(creative_preferences, '{}'::jsonb),
    page_review_data = COALESCE(page_review_data, '{}'::jsonb),
    publish_settings = COALESCE(publish_settings, '{}'::jsonb);

ALTER TABLE public.video_render_plans
    ALTER COLUMN persona_id TYPE TEXT USING persona_id::text,
    ALTER COLUMN persona_id SET NOT NULL,
    ALTER COLUMN creative_preferences SET DEFAULT '{}'::jsonb,
    ALTER COLUMN creative_preferences SET NOT NULL,
    ALTER COLUMN page_review_data SET DEFAULT '{}'::jsonb,
    ALTER COLUMN page_review_data SET NOT NULL,
    ALTER COLUMN publish_settings SET DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_video_render_plans_user_persona_id
    ON public.video_render_plans(user_id, persona_id);

CREATE INDEX IF NOT EXISTS idx_video_render_plans_workflow_id
    ON public.video_render_plans(workflow_id);
