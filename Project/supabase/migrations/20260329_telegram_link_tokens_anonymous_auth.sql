-- Allow anonymous Telegram auth bootstrap tokens to be created before a user
-- is resolved, then backfill the canonical user_id when the bot consumes them.

ALTER TABLE IF EXISTS public.telegram_link_tokens
    ALTER COLUMN user_id DROP NOT NULL;
