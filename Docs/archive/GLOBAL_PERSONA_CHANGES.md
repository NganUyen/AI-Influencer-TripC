# Global Market Personas — Change Log

**Date:** 2026-04-16  
**Feature:** Global default personas for 5 worldwide markets, visible to all accounts.

---

## Architecture Summary

Global personas are stored once under the system user ID `00000000-0000-0000-0000-000000000001`. They are not copied per user account. Instead, the Python service layer dynamically merges them into every user's persona list at query time.

---

## ✅ Changes Completed

### 1. Database — Global Persona Seed Insert

**Table:** `public.personas`  
**Project:** AI Influencer Project (Supabase)

Inserted 5 records under `user_id = '00000000-0000-0000-0000-000000000001'` in `status = 'draft'`:

| `persona_id` | `display_name` | `language` | `tts_voice` | `status` |
|---|---|---|---|---|
| `global-us-alex` | Alex Rivera | English (US) | `en-US-Standard-F` | draft |
| `global-cn-wei` | Wei Chen | Mandarin | `cmn-CN-Standard-B` | draft |
| `global-ru-natasha` | Natasha Volkov | Russian | `ru-RU-Standard-C` | draft |
| `global-in-arjun` | Arjun Sharma | Indian English | `en-IN-Standard-D` | draft |
| `global-mx-valeria` | Valeria Cruz | Mexican Spanish | `es-US-Standard-B` | draft |

All records also contain:
- `avatar_prompt` — Fal AI generation prompt for each market
- `avatar_source_type = 'fal_ai'`
- `description`, `tone_default`, `market_default`

---

### 2. Backend — `PersonaRegistryService` Logic Fix

**File:** `python_services/services/persona_registry_service.py`

#### `list_personas()` (lines ~664–693)

**Problem:** The method returned early once it found personas for a user, completely hiding global system personas for users who have custom personas.

**Fix:** Changed to an aggregation pattern — user personas and system personas are always both fetched and merged together before returning.

```python
# Before (early return hid system personas):
for candidate_user_id in candidate_user_ids:
    personas = await cls._list_from_db(status=status, user_id=candidate_user_id)
    if personas:
        return personas  # <-- bug: never reached system personas

# After (always aggregate both):
aggregated_personas = []
for candidate_user_id in candidate_user_ids:
    personas = await cls._list_from_db(status=status, user_id=candidate_user_id)
    if personas:
        aggregated_personas.extend(personas)

# Always append global system personas
if _SYSTEM_PERSONA_USER_ID not in candidate_user_ids:
    system_personas = await cls._list_from_db(status=status, user_id=_SYSTEM_PERSONA_USER_ID)
    if system_personas:
        aggregated_personas.extend(system_personas)

return cls._dedupe_personas(aggregated_personas) if aggregated_personas else []
```

#### `get_persona()` (lines ~717–735)

**Problem:** Could not resolve global persona IDs when used in workflow jobs, because it only searched the requesting user's scope and legacy unowned scope.

**Fix:** Added an explicit fallback to `_SYSTEM_PERSONA_USER_ID` after exhausting the user's own scope.

```python
# After searching user scope, fall back to system scope:
if _SYSTEM_PERSONA_USER_ID not in candidate_user_ids:
    system_persona = await cls._get_from_db(persona_id, user_id=_SYSTEM_PERSONA_USER_ID)
    if system_persona:
        return system_persona
```

---

## ⏳ Pending — Phase 2: Avatar Generation

**Action required by operator.** Must be run inside the Docker container or local Python virtual environment with all environment variables loaded.

Run `setup_persona.py` for each global persona to:
1. Generate a Fal AI avatar image using the stored `avatar_prompt`
2. Upload the image to Object Storage
3. Register the image with HeyGen → receive `heygen_avatar_id`
4. Save `avatar_image_url`, `heygen_avatar_id` and set `status = 'ready'`

```bash
# Run from: Project/python_services/
.venv\Scripts\python scripts/setup_persona.py --persona_id=global-us-alex
.venv\Scripts\python scripts/setup_persona.py --persona_id=global-cn-wei
.venv\Scripts\python scripts/setup_persona.py --persona_id=global-ru-natasha
.venv\Scripts\python scripts/setup_persona.py --persona_id=global-in-arjun
.venv\Scripts\python scripts/setup_persona.py --persona_id=global-mx-valeria
```

> **If a run fails:** The script sets `status = 'failed'` and exits cleanly. Simply re-run the same command to retry. Use `--force` to regenerate an avatar that already succeeded.

**Completion check:**
```sql
SELECT persona_id, display_name, status, heygen_avatar_id
FROM public.personas
WHERE user_id = '00000000-0000-0000-0000-000000000001';
```
All 5 should show `status = 'ready'` and a non-null `heygen_avatar_id`.

---

## 🧪 Verification Steps (After Phase 2)

1. Open the Dashboard UI → Review Engine → persona selection modal.
2. Confirm all 5 global personas appear for **your account** and for **any other test account**.
3. Select **Valeria Cruz (Mexico)** and trigger a script generation job.
4. Confirm the backend resolves her `persona_id` (`global-mx-valeria`) and the generated script uses a **Mexican Spanish** tone.
