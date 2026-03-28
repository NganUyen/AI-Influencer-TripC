# Persona Pipeline Fixes

## Context
Fixed critical issues in persona creation flow that prevented personas from being saved to database and made usable for video-ai workflow.

## Test Status
✅ **Persona/Telegram/media test suite passing** after fixes

## Issues Fixed

### 1. Preview allowed without persisted avatar asset
**Location:** `Project/python_services/skills/persona_creator.py:184-211`

**Problem:**
- Preview was shown to user even when `avatar_media_asset_id` was `None`
- Image generation could return `storage_status="source_only"` (persist failed)
- User thought persona was ready, but it wasn't actually saved to workspace media

**Fix:**
```python
if not avatar_media_asset_id:
    raise RuntimeError(
        "Avatar was generated but failed to persist to workspace storage "
        "(storage_status=source_only)..."
    )
```

**Impact:** Preview now only shows when avatar is truly persisted with valid `media_asset_id`. If persistence fails, the flow returns a clear error instead of entering preview state.

---

### 2. Save Persona re-uploaded from URL instead of finalizing existing asset
**Location:** `Project/python_services/services/skill_dispatcher.py:342-407`

**Problem:**
- When user clicked "Save Persona", if `avatar_media_asset_id` was missing, code attempted to re-upload from URL
- This was wasteful (network + storage) and didn't fix root cause
- If original persist failed due to ownership, re-upload would fail the same way

**Fix:**
```python
# CRITICAL FIX: Save should only finalize an already-persisted asset
# Never re-upload from URL; if avatar_media_asset_id is missing, the preview flow failed
if not avatar_media_asset_id:
    return SkillResult(
        success=False,
        error=(
            "Avatar preview exists but was not persisted to workspace media. "
            "Please regenerate the avatar or try creating the persona again."
        ),
        session=session,
    )
```

**Impact:**
- Cleaner error messaging
- No wasteful duplicate uploads
- Forces user to regenerate properly if preview flow failed

---

### 3. Session lost after save/regenerate fail
**Location:** `Project/python_services/services/skill_session_store.py:63-98`

**Problem:**
- With multi-worker deployment (`--workers 2`), session stored in memory was not shared between workers
- If Redis failed/unavailable, fallback to memory broke session continuity across requests
- After save failed, next request could hit different worker → session lost → "No active skill session"

**Fix:**
```python
# Don't disable Redis on transient errors; keep retrying
# Only use memory fallback when Redis is truly not configured
if cls._redis_enabled and cls._redis_client is not None:
    try:
        raw = await cls._redis_client.get(key)
        if raw:
            return SkillSession.model_validate(json.loads(raw))
        return None  # Session expired/missing, not a transient error
    except Exception as exc:
        logger.error("Redis read failed... Attempting memory fallback.", exc)
        # Don't disable Redis permanently on transient error
```

**Impact:** Session reliability improved, especially in production with multiple workers

---

### 4. Telegram Linking Required (Bypass Removed)

**Status:** ✅ **BYPASS_TELEGRAM_LINK_CHECK has been permanently removed**

Persona creation now **requires** a valid `telegram_user_links` entry. Users must link their Telegram account via the dashboard before creating personas.

**Required Flow:**
1. **Dashboard:** User clicks Telegram link button
2. **Backend:** Generates link token via `TelegramLinkService.create_link_token(user_id)`
3. **Frontend:** Displays link like `https://t.me/bot?start={token}`
4. **User:** Clicks link in Telegram
5. **Bot:** Receives `/start {token}`, calls `TelegramLinkService.consume_link_token()`
6. **Database:** Row inserted into `telegram_user_links` mapping `chat_id` → `user_id`
7. **Persona Creation:** Now works with valid ownership

**Error Messages:**
- "Telegram owner scope is invalid or not linked. Please link your Telegram account via the dashboard first."
- "Resolved persona owner user_id does not exist in public.users. Please ensure your Telegram account is linked via the dashboard."

---

## Testing Checklist

- [ ] Link Telegram account via dashboard `/start {token}` flow
- [ ] Create persona from Telegram bot
- [ ] Verify preview shows with valid `avatar_media_asset_id`
- [ ] Save persona successfully to `status=ready`
- [ ] Verify persona appears in video-ai picker
- [ ] Regenerate avatar works without losing session
- [ ] Multiple workers don't cause session loss
- [ ] Media assets properly linked to persona in DB
- [ ] **Verify unlinked users get clear error message**

---

## Files Modified

1. `Project/python_services/skills/persona_creator.py` - Block preview without asset
2. `Project/python_services/services/skill_dispatcher.py` - Remove re-upload logic from save
3. `Project/python_services/services/skill_session_store.py` - Improve Redis error handling
4. `Project/python_services/services/persona_registry_service.py` - Enforce Telegram linking
5. `Project/python_services/services/media_storage_service.py` - Enforce Telegram linking
6. `Project/python_services/services/telegram_link_service.py` - Disable legacy fallback permanently
