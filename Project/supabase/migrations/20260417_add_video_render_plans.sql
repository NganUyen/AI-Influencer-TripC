-- Create Video Render Plans table and update Personas
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS public.video_render_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    campaign_id UUID REFERENCES public.campaigns(id),
    persona_id UUID NOT NULL REFERENCES public.personas(id),
    
    -- Input context
    source_url TEXT NOT NULL,
    objective TEXT,
    
    -- Script content
    script_text TEXT NOT NULL,
    scenes_data JSONB NOT NULL DEFAULT '[]'::jsonb,
    duration_estimate FLOAT,
    
    -- Status tracking
    status TEXT DEFAULT 'generated',
    
    -- Workflow link
    workflow_id TEXT,
    video_url TEXT,
    publish_settings JSONB DEFAULT '{}'::jsonb,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    approved_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_video_render_plans_user_id ON public.video_render_plans(user_id);
CREATE INDEX IF NOT EXISTS idx_video_render_plans_campaign_id ON public.video_render_plans(campaign_id);
CREATE INDEX IF NOT EXISTS idx_video_render_plans_workflow_id ON public.video_render_plans(workflow_id);

ALTER TABLE public.personas ADD COLUMN IF NOT EXISTS gender VARCHAR(20);
ALTER TABLE public.personas ADD COLUMN IF NOT EXISTS channel_configs JSONB DEFAULT '{}'::jsonb;
