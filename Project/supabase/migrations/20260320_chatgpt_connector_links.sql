-- ChatGPT connector identity links
-- Created: 2026-03-20

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

CREATE INDEX IF NOT EXISTS idx_chatgpt_oauth_links_subject
    ON public.chatgpt_oauth_links(chatgpt_subject);

CREATE INDEX IF NOT EXISTS idx_chatgpt_oauth_links_last_used
    ON public.chatgpt_oauth_links(last_used_at DESC);
