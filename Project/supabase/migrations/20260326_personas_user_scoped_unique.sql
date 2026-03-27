-- Scope persona identity by owner (user_id + persona_id)
-- Created: 2026-03-26

DROP INDEX IF EXISTS public.idx_personas_persona_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_personas_user_persona_id
    ON public.personas(user_id, persona_id);
