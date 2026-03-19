-- AI Influencer Factory Database Schema
-- PostgreSQL / Supabase

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Campaigns table
CREATE TABLE IF NOT EXISTS public.campaigns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'draft', -- draft, active, paused, completed
    start_date TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Content table
CREATE TABLE IF NOT EXISTS public.content (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    campaign_id UUID REFERENCES public.campaigns(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    platform TEXT[] NOT NULL, -- ['twitter', 'linkedin', etc.]
    status TEXT NOT NULL DEFAULT 'draft', -- draft, pending_approval, approved, scheduled, published, failed
    scheduled_at TIMESTAMP WITH TIME ZONE,
    published_at TIMESTAMP WITH TIME ZONE,
    media_urls TEXT[],
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- AI Personas table
CREATE TABLE IF NOT EXISTS public.personas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    voice_profile TEXT, -- Voice characteristics and tone
    platforms TEXT[] NOT NULL,
    is_active BOOLEAN DEFAULT true,
    avatar_url TEXT,
    proxy_config JSONB, -- Proxy settings for this persona
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Media Assets table
CREATE TABLE IF NOT EXISTS public.media_assets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    content_id UUID REFERENCES public.content(id) ON DELETE SET NULL,
    url TEXT NOT NULL,
    type TEXT NOT NULL, -- image, video, audio, document
    filename TEXT NOT NULL,
    size INTEGER,
    mime_type TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Workflows table (Temporal tracking)
CREATE TABLE IF NOT EXISTS public.workflows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id TEXT UNIQUE NOT NULL, -- Temporal workflow ID
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    type TEXT NOT NULL, -- weekly_marketing, content_generation, distribution
    status TEXT NOT NULL DEFAULT 'running', -- running, waiting_approval, completed, failed
    current_step TEXT,
    progress INTEGER DEFAULT 0,
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Social Accounts table
CREATE TABLE IF NOT EXISTS public.social_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    persona_id UUID REFERENCES public.personas(id) ON DELETE SET NULL,
    platform TEXT NOT NULL, -- twitter, linkedin, facebook, etc.
    account_name TEXT NOT NULL,
    account_handle TEXT,
    is_primary BOOLEAN DEFAULT false, -- Main account vs engagement account
    oauth_token TEXT,
    oauth_secret TEXT,
    proxy_config JSONB, -- IP rotation config
    is_active BOOLEAN DEFAULT true,
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ChatGPT OAuth link table for connector identity mapping
CREATE TABLE IF NOT EXISTS public.chatgpt_oauth_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chatgpt_subject TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    display_name TEXT,
    session_id TEXT,
    linked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    active BOOLEAN DEFAULT TRUE
);

-- Engagement Actions table (for tracking bot engagement)
CREATE TABLE IF NOT EXISTS public.engagement_actions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    social_account_id UUID NOT NULL REFERENCES public.social_accounts(id) ON DELETE CASCADE,
    target_content_id UUID REFERENCES public.content(id) ON DELETE SET NULL,
    action_type TEXT NOT NULL, -- like, comment, share, repost
    platform TEXT NOT NULL,
    target_url TEXT,
    comment_text TEXT,
    status TEXT NOT NULL DEFAULT 'pending', -- pending, completed, failed
    executed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Analytics Events table
CREATE TABLE IF NOT EXISTS public.analytics_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_id UUID REFERENCES public.content(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL, -- view, click, engagement, etc.
    platform TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_content_user_id ON public.content(user_id);
CREATE INDEX IF NOT EXISTS idx_content_campaign_id ON public.content(campaign_id);
CREATE INDEX IF NOT EXISTS idx_content_status ON public.content(status);
CREATE INDEX IF NOT EXISTS idx_content_scheduled_at ON public.content(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_personas_user_id ON public.personas(user_id);
CREATE INDEX IF NOT EXISTS idx_workflows_user_id ON public.workflows(user_id);
CREATE INDEX IF NOT EXISTS idx_workflows_status ON public.workflows(status);
CREATE INDEX IF NOT EXISTS idx_social_accounts_user_id ON public.social_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_chatgpt_oauth_links_subject ON public.chatgpt_oauth_links(chatgpt_subject);
CREATE INDEX IF NOT EXISTS idx_engagement_actions_account_id ON public.engagement_actions(social_account_id);
CREATE INDEX IF NOT EXISTS idx_engagement_actions_status ON public.engagement_actions(status);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at triggers
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON public.users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_campaigns_updated_at BEFORE UPDATE ON public.campaigns
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_content_updated_at BEFORE UPDATE ON public.content
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_personas_updated_at BEFORE UPDATE ON public.personas
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_social_accounts_updated_at BEFORE UPDATE ON public.social_accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Enable Row Level Security (RLS)
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.content ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.personas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.media_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workflows ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.social_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chatgpt_oauth_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.engagement_actions ENABLE ROW LEVEL SECURITY;

-- RLS Policies (users can only access their own data)
CREATE POLICY "Users can view own data" ON public.users
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own data" ON public.users
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can view own campaigns" ON public.campaigns
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own content" ON public.content
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own personas" ON public.personas
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own media" ON public.media_assets
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own workflows" ON public.workflows
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own accounts" ON public.social_accounts
    FOR ALL USING (auth.uid() = user_id);

-- Approval tracking table (workflow + content review trail)
CREATE TABLE IF NOT EXISTS public.approvals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_id UUID REFERENCES public.content(id) ON DELETE CASCADE,
    workflow_id TEXT REFERENCES public.workflows(workflow_id) ON DELETE SET NULL,
    approver_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending', -- pending, approved, rejected
    feedback TEXT,
    approved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Postiz schedule tracking
CREATE TABLE IF NOT EXISTS public.postiz_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_id UUID NOT NULL REFERENCES public.content(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    postiz_post_id TEXT,
    scheduled_for TIMESTAMP WITH TIME ZONE,
    status TEXT NOT NULL DEFAULT 'scheduled', -- scheduled, published, failed, canceled
    response_payload JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- GrowChief engagement job log
CREATE TABLE IF NOT EXISTS public.engagement_action_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id TEXT REFERENCES public.workflows(workflow_id) ON DELETE SET NULL,
    social_account_id UUID REFERENCES public.social_accounts(id) ON DELETE SET NULL,
    platform TEXT NOT NULL,
    target_post_id TEXT,
    target_url TEXT,
    action_types TEXT[] NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending', -- pending, running, completed, failed
    provider_job_id TEXT,
    result_payload JSONB DEFAULT '{}',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- ChatGPT connector identity links
CREATE TABLE IF NOT EXISTS public.chatgpt_oauth_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chatgpt_subject TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    display_name TEXT,
    session_id TEXT NOT NULL,
    linked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    active BOOLEAN NOT NULL DEFAULT TRUE
);

-- Extend workflows for approval state persistence
ALTER TABLE public.workflows ADD COLUMN IF NOT EXISTS approval_required BOOLEAN DEFAULT FALSE;
ALTER TABLE public.workflows ADD COLUMN IF NOT EXISTS approval_status TEXT; -- pending, approved, rejected
ALTER TABLE public.workflows ADD COLUMN IF NOT EXISTS approved_by UUID REFERENCES public.users(id) ON DELETE SET NULL;
ALTER TABLE public.workflows ADD COLUMN IF NOT EXISTS approval_feedback TEXT;
ALTER TABLE public.workflows ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP WITH TIME ZONE;

-- Extend social accounts for account health snapshots
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS account_health INTEGER;
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS followers_count INTEGER;
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS ban_risk_level TEXT;
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS last_api_response JSONB DEFAULT '{}';
ALTER TABLE public.social_accounts ADD COLUMN IF NOT EXISTS warnings TEXT[] DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_approvals_workflow_id ON public.approvals(workflow_id);
CREATE INDEX IF NOT EXISTS idx_approvals_content_id ON public.approvals(content_id);
CREATE INDEX IF NOT EXISTS idx_postiz_schedules_content_id ON public.postiz_schedules(content_id);
CREATE INDEX IF NOT EXISTS idx_postiz_schedules_status ON public.postiz_schedules(status);
CREATE INDEX IF NOT EXISTS idx_engagement_action_logs_workflow_id ON public.engagement_action_logs(workflow_id);
CREATE INDEX IF NOT EXISTS idx_engagement_action_logs_status ON public.engagement_action_logs(status);
CREATE INDEX IF NOT EXISTS idx_chatgpt_oauth_links_subject ON public.chatgpt_oauth_links(chatgpt_subject);
CREATE INDEX IF NOT EXISTS idx_chatgpt_oauth_links_last_used ON public.chatgpt_oauth_links(last_used_at DESC);

ALTER TABLE public.approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.postiz_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.engagement_action_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own approvals" ON public.approvals
    FOR ALL USING (auth.uid() = approver_id);

CREATE POLICY "Users can view own postiz schedules" ON public.postiz_schedules
    FOR ALL USING (
        auth.uid() IN (
            SELECT c.user_id FROM public.content c WHERE c.id = postiz_schedules.content_id
        )
    );

CREATE POLICY "Users can view own engagement logs" ON public.engagement_action_logs
    FOR ALL USING (
        social_account_id IS NULL OR
        auth.uid() IN (
            SELECT sa.user_id FROM public.social_accounts sa WHERE sa.id = engagement_action_logs.social_account_id
        )
    );
