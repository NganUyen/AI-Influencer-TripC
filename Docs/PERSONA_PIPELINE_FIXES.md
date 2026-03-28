# Persona Pipeline Fixes

## Context
Fixed critical issues in persona creation flow that prevented personas from being saved to database and made usable for video-ai workflow.

## Test Status
✅ **Persona/Telegram/media test suite passing** after fixes
- Updated `test_resolve_user_id_for_owner_key_disables_synthetic_fallback_in_production` to set `BYPASS_TELEGRAM_LINK_CHECK=False` explicitly
- Fixed `_allows_legacy_fallback()` logic to properly respect bypass flag in production mode
- Added regression coverage for `source_only` avatar generation so persona flow does not enter `preview_ready`

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

### 4. Production ownership check blocked persona creation
**Location:** 
- `Project/python_services/config/settings.py:54-62`
- `Project/python_services/services/persona_registry_service.py:73-77`
- `Project/python_services/services/media_storage_service.py:133-136`

**Problem:**
- In production mode, media/persona ownership requires Telegram chat to be linked to workspace user
- Link is created via `/start <token>` flow from dashboard
- Dashboard login flow not yet implemented
- → All persona creation failed with ownership errors

**Temporary Fix:**
```python
# settings.py
BYPASS_TELEGRAM_LINK_CHECK: bool = False  # default off

# persona_registry_service.py
allow_fallback=(not settings.is_production_like) or settings.BYPASS_TELEGRAM_LINK_CHECK

# media_storage_service.py
allow_fallback=bool(owner_key) and ((not settings.is_production_like) or settings.BYPASS_TELEGRAM_LINK_CHECK)
```

**Impact:** 
- Persona creation can work immediately without dashboard link flow when the flag is explicitly enabled in env
- Creates synthetic user per Telegram chat for now
- **TODO:** Implement proper dashboard Telegram login flow, then keep `BYPASS_TELEGRAM_LINK_CHECK=false`

---

## Environment Variables Added

**`.env`:**
```bash
# TEMPORARY: Bypass Telegram link ownership check until dashboard login flow is implemented
# Default is false. Enable explicitly only in the target env when testing persona flow without dashboard sync.
BYPASS_TELEGRAM_LINK_CHECK=false
```

---

## TODO: Dashboard Telegram Link Flow

**Deferred for later implementation:**

1. **Dashboard:** Add Telegram login button
2. **Backend:** Generate link token via `TelegramLinkService.create_link_token(user_id)`
3. **Frontend:** Display link like `https://t.me/bot?start={token}`
4. **User:** Clicks link in Telegram
5. **Bot:** Receives `/start {token}`, calls `TelegramLinkService.consume_link_token()`
6. **Database:** Row inserted into `telegram_user_links` mapping `chat_id` → `user_id`
7. **Production:** Set `BYPASS_TELEGRAM_LINK_CHECK=false` to enforce proper ownership

---

## Testing Checklist

- [ ] Create persona from Telegram bot
- [ ] Verify preview shows with valid `avatar_media_asset_id`
- [ ] Save persona successfully to `status=ready`
- [ ] Verify persona appears in video-ai picker
- [ ] Regenerate avatar works without losing session
- [ ] Multiple workers don't cause session loss
- [ ] Media assets properly linked to persona in DB

---

## Files Modified

1. `Project/python_services/skills/persona_creator.py` - Block preview without asset
2. `Project/python_services/services/skill_dispatcher.py` - Remove re-upload logic from save
3. `Project/python_services/services/skill_session_store.py` - Improve Redis error handling
4. `Project/python_services/config/settings.py` - Add `BYPASS_TELEGRAM_LINK_CHECK` flag
5. `Project/python_services/services/persona_registry_service.py` - Use bypass flag
6. `Project/python_services/services/media_storage_service.py` - Use bypass flag
7. `Project/.env` - Enable bypass flag
8. `Project/.env.example` - Document bypass flag

---

## Temporary Redeploy Notes

1. For temporary persona-flow testing without dashboard sync, set `BYPASS_TELEGRAM_LINK_CHECK=true` in the target env before redeploy.
2. Keep the default value `false` in repo and examples so long-term production does not silently stay in bypass mode.
3. Redis should be healthy for session reliability.
4. After deploying, test `create -> preview -> save -> regenerate -> inspect persona`.
5. Verify the saved persona appears in the `video-ai` persona picker.
6. Monitor logs for any `Redis read/write failed` or ownership fallback warnings.

## Removal Plan After Dashboard Sync

When Telegram dashboard linking is implemented and verified, remove the temporary bypass in this order:

1. Set `BYPASS_TELEGRAM_LINK_CHECK=false` in the deployment env.
2. Verify `/start <token>` and `telegram_user_links` ownership mapping work end to end.
3. Remove bypass-specific branches from:
   - `Project/python_services/services/telegram_link_service.py`
   - `Project/python_services/services/persona_registry_service.py`
   - `Project/python_services/services/media_storage_service.py`
4. Remove the `BYPASS_TELEGRAM_LINK_CHECK` setting from:
   - `Project/python_services/config/settings.py`
   - `Project/.env.example`
5. Delete or update tests that exist only for bypass behavior, while keeping the persona persistence regression tests.
