ALTER TABLE public.approvals
    DROP CONSTRAINT IF EXISTS approvals_status_check;

ALTER TABLE public.approvals
    ADD COLUMN IF NOT EXISTS channel TEXT NOT NULL DEFAULT 'telegram',
    ADD COLUMN IF NOT EXISTS request_key TEXT,
    ADD COLUMN IF NOT EXISTS telegram_message_ref JSONB,
    ADD COLUMN IF NOT EXISTS decision_source TEXT,
    ADD COLUMN IF NOT EXISTS decision_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE public.approvals
    ADD CONSTRAINT approvals_status_check
    CHECK (
        status = ANY (
            ARRAY[
                'pending'::text,
                'approved'::text,
                'rejected'::text,
                'save'::text,
                'discard'::text
            ]
        )
    );

CREATE UNIQUE INDEX IF NOT EXISTS idx_approvals_request_key
    ON public.approvals(request_key)
    WHERE request_key IS NOT NULL;

ALTER TABLE public.workflows
    ADD COLUMN IF NOT EXISTS channel TEXT,
    ADD COLUMN IF NOT EXISTS request_key TEXT,
    ADD COLUMN IF NOT EXISTS telegram_message_ref JSONB,
    ADD COLUMN IF NOT EXISTS decision_source TEXT,
    ADD COLUMN IF NOT EXISTS decision_payload JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_workflows_request_key
    ON public.workflows(request_key)
    WHERE request_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.telegram_events (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_update_id bigint NOT NULL UNIQUE,
    chat_id bigint NOT NULL,
    linked_user_id uuid REFERENCES public.users(id),
    route text NOT NULL DEFAULT 'received',
    approval_id uuid REFERENCES public.approvals(id),
    workflow_id text REFERENCES public.workflows(workflow_id),
    event_type text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_message text,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_telegram_events_chat_created
    ON public.telegram_events(chat_id, created_at DESC);
