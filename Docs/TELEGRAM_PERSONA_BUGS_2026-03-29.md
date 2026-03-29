# Telegram Persona Bugs 2026-03-29

Last verified: 2026-03-29 (Asia/Saigon)

This document records two Telegram persona-flow bugs investigated on March 29, 2026:

- avatar generation returning a generic 500 error during persona creation
- persona session remaining logically active after `Save Persona`, causing the next text message to be routed into the old skill session

## Scope

This note covers the Telegram persona flow in:

- `Project/python_services/skills/persona_creator.py`
- `Project/python_services/api/media.py`
- `Project/python_services/services/skill_session_store.py`
- `Project/python_services/services/skill_dispatcher.py`

It does not claim that the entire persona-to-video lane is complete. In particular, persona readiness for video still depends on `tts_voice`, `avatar_media_asset_id`, and `heygen_avatar_id`.

## Bug 1. Avatar generation failed with an opaque 500

### Symptom

During Telegram persona creation, after the appearance prompt was sent, the bot could fail with a message similar to:

- `Failed to generate/attach persona avatar: Server error '500 Internal Server Error' for url 'http://backend/api/media/generate/image'`

This was hard to diagnose because the Telegram user only saw the outer internal request failure, not the real upstream provider error.

### Root cause

The persona skill called:

- `POST /api/media/generate/image`

through the internal ASGI client.

When that backend route failed, the skill mostly surfaced the outer `httpx.HTTPStatusError` string. That meant Telegram showed the internal backend URL instead of the real error detail returned by the media route or upstream provider.

### Fix

Two changes were made:

1. `persona_creator.py` now extracts backend `detail` from `httpx.HTTPStatusError` before composing the Telegram-facing error.
2. `api/media.py` now converts upstream `httpx.HTTPStatusError` into a clearer backend `detail`, including the upstream status and best available error message.

### Result

Telegram error messages should now show the real failure cause more clearly, for example:

- provider auth failure
- upstream 4xx or 5xx
- invalid media request

This fix improves diagnosis. It does not guarantee avatar generation success by itself.

## Bug 2. `Save Persona` completed, but the old Telegram skill session came back

### Symptom

The user could:

1. create a persona preview
2. tap `Save Persona`
3. receive a success message saying the persona was saved and marked ready
4. send another normal message such as `show me available personas`

But instead of continuing normally, the bot could still behave as if the old `persona-creator` session was active. The user then had to send `/cancel`, and cancellation could even show draft-related copy from the old preview.

### Expected behavior

After `Save Persona` succeeds:

- the persona record should be updated in storage/database
- the Telegram persona skill session should end immediately
- the next message should no longer be routed into the old preview session

### Actual root cause

`SkillDispatcher.handle_action("save")` already cleared the Telegram session correctly.

The real bug was in `TelegramSkillSessionStore.get_session()`:

- when Redis was enabled and returned `None`
- the store still fell back to worker-local in-memory cache
- that stale cache could resurrect a session that had already been cleared from Redis

This is especially plausible in multi-worker or just-redeployed environments, where one worker still holds an old in-memory copy.

### Fix

`TelegramSkillSessionStore.get_session()` was changed so that:

- if Redis is enabled and Redis returns no session, Redis is treated as authoritative
- any local in-memory cached copy for that chat is discarded immediately
- in-memory fallback is used only when Redis is disabled or Redis read itself fails

### Result

After a successful `Save Persona`:

- the persona skill session should not reappear from stale worker memory
- the next text message should no longer be trapped in the old `persona-creator` flow

## What this fix does and does not guarantee

### Fixed

- better Telegram-visible error detail for avatar-generation failures
- correct end-of-session behavior after `Save Persona`
- protection against stale worker-local skill session resurrection when Redis no longer has the session

### Not fixed by this patch

- automatic creation of `heygen_avatar_id`
- full persona readiness for the video production lane if required persona fields are still missing
- UX copy inconsistency where a preview may say the avatar asset is saved while the persona status is still `draft`

## Important readiness boundary for video

Saving the persona is not the only requirement for video.

For the Telegram `video-ai` lane, persona readiness still checks:

- `status == ready`
- `tts_voice`
- `avatar_media_asset_id`
- `heygen_avatar_id`

If `heygen_avatar_id` is still missing, video production can still be blocked even after `Save Persona`.

## Verification

The following test coverage was added or verified during this fix:

- `Project/python_services/tests/test_skill_session_store.py`
  stale memory cache must not resurrect a cleared Redis session
- `Project/python_services/tests/test_skill_dispatcher.py`
  save action must clear the persona session
- `Project/python_services/skills/test_persona_creator.py`
  avatar-generation failures should surface backend detail
- `Project/python_services/tests/test_media_api.py`
  media route should surface upstream HTTP detail

## Operational note

If production is running multiple workers, correct Redis-backed skill session behavior is important. If `REDIS_URL` is missing or unstable, Telegram multi-step flows can still drift because worker-local memory is not a safe shared source of truth.
