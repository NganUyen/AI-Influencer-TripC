-- MVP integrations migration: Temporal approval persistence + Postiz/GrowChief tracking
-- Created: 2026-03-16

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

ALTER TABLE public.workflows ADD COLUMN IF NOT EXISTS approval_required BOOLEAN DEFAULT FALSE;
ALTER TABLE public.workflows ADD COLUMN IF NOT EXISTS approval_status TEXT;
ALTER TABLE public.workflows ADD COLUMN IF NOT EXISTS approved_by UUID REFERENCES public.users(id) ON DELETE SET NULL;
ALTER TABLE public.workflows ADD COLUMN IF NOT EXISTS approval_feedback TEXT;
ALTER TABLE public.workflows ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP WITH TIME ZONE;

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

ALTER TABLE public.approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.postiz_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.engagement_action_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own approvals" ON public.approvals;
CREATE POLICY "Users can view own approvals" ON public.approvals
    FOR ALL USING (auth.uid() = approver_id);

DROP POLICY IF EXISTS "Users can view own postiz schedules" ON public.postiz_schedules;
CREATE POLICY "Users can view own postiz schedules" ON public.postiz_schedules
    FOR ALL USING (
        auth.uid() IN (
            SELECT c.user_id FROM public.content c WHERE c.id = postiz_schedules.content_id
        )
    );

DROP POLICY IF EXISTS "Users can view own engagement logs" ON public.engagement_action_logs;
CREATE POLICY "Users can view own engagement logs" ON public.engagement_action_logs
    FOR ALL USING (
        social_account_id IS NULL OR
        auth.uid() IN (
            SELECT sa.user_id FROM public.social_accounts sa WHERE sa.id = engagement_action_logs.social_account_id
        )
    );
