"""Persona creation skill wrapper."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, Optional

import httpx
import json
import logging
from config.settings import settings
from services.google_tts_service import GoogleTTSService
from services.openclaw_gateway import OpenClawGateway

logger = logging.getLogger(__name__)

from .base import BaseSkill, SkillResult, SkillSession, SkillStatus
from .definitions import get_skill_definition

_DEFINITION = get_skill_definition("persona-creator")


class PersonaCreatorSkill(BaseSkill):
    name = "persona-creator"
    required_params = list(_DEFINITION.get("required_params", []))
    optional_params = list(_DEFINITION.get("optional_params", []))
    api_target = _DEFINITION.get("api_call", {}).get(
        "target",
        "POST /api/personas + PATCH /api/personas/{persona_id} + GET /api/personas/{persona_id}/readiness",
    )
    backend_status = _DEFINITION.get("status", "partial")
    steps = list(_DEFINITION.get("steps", []))
    session_shape = deepcopy(_DEFINITION.get("session_shape", BaseSkill.session_shape))

    @classmethod
    def _is_ai_auth_error(cls, exc: Exception) -> bool:
        message = str(exc).lower()
        return (
            "invalid_api_key" in message
            or "incorrect api key provided" in message
            or "authentication" in message
            or "http 401" in message
            or "status code: 401" in message
        )

    @classmethod
    def _is_ai_service_unavailable_error(cls, exc: Exception) -> bool:
        message = str(exc).lower()
        return (
            "service_disabled" in message
            or "has not been used in project" in message
            or "api is disabled" in message
            or "quota" in message
            or "rate limit" in message
            or "status code: 429" in message
            or "permission denied" in message
            or "forbidden" in message
        )

    @classmethod
    def _dream_persona_details_fallback(
        cls,
        nationality: str,
        brief: str,
        *,
        reason: str,
    ) -> Dict[str, Any]:
        # Build a deterministic, safe fallback so Dream flow can continue without external AI.
        nat = cls._trim_text(nationality, max_length=40) or "Global"
        brief_clean = cls._trim_text(brief, max_length=120) or "social media creator"

        tokens = [
            part.lower()
            for part in re.split(r"[^a-zA-Z0-9]+", f"{nat} {brief_clean}")
            if part
        ]
        persona_id = "_".join(tokens[:5]) or "creator_profile"
        persona_id = persona_id[:48].strip("_") or "creator_profile"

        display_name = f"{nat.title()} Creator"
        appearance = (
            f"A realistic portrait of a {nat} content creator, {brief_clean}. "
            "Preserve the requested cultural background and styling cues. "
            "Do not genericize into a default Western or white influencer look. "
            "Natural lighting, clean background, confident expression, social-media-ready style."
        )

        return {
            "persona_id": persona_id,
            "display_name": display_name,
            "appearance": appearance,
            "success": False,
            "error": reason,
        }

    @classmethod
    def _display_name_from_persona_id(cls, persona_id: str) -> str:
        parts = [part for part in re.split(r"[_-]+", persona_id.strip()) if part]
        if not parts:
            return persona_id
        return " ".join(part.capitalize() for part in parts)

    @classmethod
    def _owner_params(cls, session: SkillSession) -> Optional[Dict[str, str]]:
        telegram_chat_id = session.artifacts.get("telegram_chat_id")
        if not telegram_chat_id:
            return None
        return {"owner_key": f"telegram:{telegram_chat_id}"}

    @classmethod
    def _trim_text(cls, value: str, *, max_length: int) -> str:
        normalized = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(normalized) <= max_length:
            return normalized
        trimmed = normalized[:max_length].rsplit(" ", 1)[0].strip()
        return trimmed or normalized[:max_length].strip()

    @classmethod
    def _simplify_avatar_appearance(cls, appearance: str) -> str:
        cleaned = str(appearance or "")
        cleaned = re.sub(r"https?://\S+", " ", cleaned)
        cleaned = re.sub(r"\[[^\]]*\]\([^)]+\)", " ", cleaned)
        cleaned = re.sub(r"[\r\n\t]+", " ", cleaned)
        cleaned = re.sub(r"[`*_>#|]+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;:-")
        return cls._trim_text(cleaned, max_length=220)

    @classmethod
    def _build_avatar_prompt(cls, appearance: str, *, simplified: bool = False) -> str:
        if simplified:
            description = cls._simplify_avatar_appearance(appearance)
            if not description:
                description = "friendly adult social media creator"
            return (
                "Photorealistic head-and-shoulders portrait avatar of a single social media creator. "
                f"Appearance: {description}. "
                "Preserve the requested ethnicity, nationality, age range, styling, and cultural cues from the brief. "
                "Do not default to a generic white English-speaking influencer unless the brief explicitly asks for it. "
                "Looking at camera, plain neutral background, natural lighting, centered composition, "
                "no text, no logos, no props, no extra people, no collage."
            )

        normalized = cls._trim_text(appearance, max_length=600)
        return (
            "Create a clean, realistic head-and-shoulders portrait avatar for a social media creator.\n"
            f"Appearance brief: {normalized}\n"
            "Preserve the requested ethnicity, nationality, age range, styling, and cultural context from the brief.\n"
            "Avoid collapsing into a generic Western or white influencer look unless the brief explicitly requests that.\n"
            "Style: premium, natural lighting, plain background, centered composition."
        )

    @classmethod
    def _extract_http_error_detail(cls, exc: httpx.HTTPStatusError) -> str:
        response = exc.response
        if response is None:
            return str(exc)
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            for key in ("detail", "message", "error"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        body = response.text.strip()
        if body:
            return body
        return str(exc)

    @classmethod
    async def _request_avatar_generation(
        cls,
        current: SkillSession,
        backend_url: str,
        http_client: Any,
        *,
        avatar_prompt: str,
        resolved_user_id: Optional[str],
        owner_key: Optional[str],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        return await cls._request_json(
            http_client,
            "POST",
            backend_url,
            "/api/media/generate/image",
            json={
                "prompt": avatar_prompt,
                "aspect_ratio": "1:1",
                "num_images": 1,
                "user_id": resolved_user_id,
                "owner_key": owner_key,
                "persona_id": current.collected.get("persona_id"),
                "metadata": metadata,
            },
        )

    @classmethod
    async def _dream_persona_details_refined(
        cls, 
        nationality: str, 
        brief: str
    ) -> Dict[str, Any]:
        """AI-powered identity generation using OpenClaw."""
        openclaw = OpenClawGateway()
        
        prompt = f"""You are a master of global identities and cultural nuances.
Suggest a realistic, culturally accurate persona identity.

Nationality: {nationality}
Brief: {brief}

Hard requirements:
- Preserve the requested nationality and cultural context in both the name and appearance.
- The result must feel locally plausible, not generic.
- Do not default to an average white, Western, or English-coded influencer unless the brief explicitly asks for that.
- Reflect the brief's age, style, profession, and environment in the appearance description.

You MUST return valid JSON with these keys:
- persona_id: A unique URL-safe slug (e.g., 'kaito_tanaka')
- display_name: A realistic, localized full name (e.g., 'Kaito Tanaka')
- appearance: A detailed visual description for an image generator (e.g., 'A portrait of an elderly man with silver hair wearing a kimono...')

Response format:
{{
  "persona_id": "...",
  "display_name": "...",
  "appearance": "..."
}}"""

        try:
            logger.info("Dream: generating persona identity via OpenClaw")
            result = await openclaw.execute_task(
                task_type="dream_persona",
                prompt=prompt,
                user_id="system",
                context={"nationality": nationality, "brief": brief},
            )
            
            # Result may already be parsed JSON or contain a 'result' key
            data = result if isinstance(result.get("persona_id"), str) else result.get("result", result)
            
            # If data is still a string, try to parse it
            if isinstance(data, str):
                json_match = re.search(r"\{.*\}", data, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
            
            # Validate required keys
            if not isinstance(data, dict) or not all(k in data for k in ["persona_id", "display_name", "appearance"]):
                logger.error(f"OpenClaw response missing required keys: {result}")
                raise ValueError("AI response missing required JSON keys")
            
            logger.info("Dream: OpenClaw generation successful")
            return {
                "persona_id": data["persona_id"],
                "display_name": data["display_name"],
                "appearance": data["appearance"],
                "success": True,
            }
            
        except Exception as e:
            logger.error(f"Dream via OpenClaw failed: {e}")
            raise

    @classmethod
    def _build_readiness_report(
        cls, persona_id: str, persona: Dict[str, Any]
    ) -> Dict[str, Any]:
        checks = {
            "status_ready": bool(persona.get("status") == "ready"),
            "has_tts_voice": bool(persona.get("tts_voice")),
            "has_avatar_image": bool(persona.get("avatar_image_url")),
            "has_avatar_asset": bool(persona.get("avatar_media_asset_id")),
            "has_heygen_avatar_id": bool(persona.get("heygen_avatar_id")),
        }

        blocking_reason: Optional[str] = None
        status = persona.get("status", "missing")
        save_required = not checks["status_ready"]
        if not checks["status_ready"]:
            if (
                checks["has_avatar_image"]
                and checks["has_avatar_asset"]
                and checks["has_heygen_avatar_id"]
            ):
                blocking_reason = (
                    "HeyGen is still processing this avatar. Tap Save Persona again in a moment "
                    "to verify readiness and finish setup."
                )
            elif checks["has_avatar_image"] and checks["has_avatar_asset"]:
                blocking_reason = (
                    "The avatar is already saved, but this persona is still in draft mode. "
                    "Tap Save Persona to mark it ready to use."
                )
            elif checks["has_avatar_image"]:
                blocking_reason = (
                    "The avatar preview looks good, but it has not been saved to your project yet. "
                    "Tap Save Persona to keep it and use this persona in video workflows."
                )
            else:
                blocking_reason = (
                    "This draft still needs an avatar preview before it can be used."
                )
        elif not checks["has_tts_voice"]:
            blocking_reason = (
                "This persona does not have a voice yet. Choose a TTS voice first."
            )
        elif not checks["has_avatar_image"]:
            blocking_reason = "This persona does not have an avatar preview yet."
        elif not checks["has_avatar_asset"]:
            blocking_reason = "The avatar preview exists, but it has not been saved to project media yet."
        elif not checks["has_heygen_avatar_id"]:
            blocking_reason = "HeyGen avatar setup is still missing for this persona."

        return {
            "persona_id": persona_id,
            "ready": blocking_reason is None,
            "status": status,
            "blocking_reason": blocking_reason,
            "checks": checks,
            "save_required": save_required,
        }

    @classmethod
    async def _get_existing_persona(
        cls,
        current: SkillSession,
        backend_url: str,
        http_client: Any,
    ) -> Optional[Dict[str, Any]]:
        try:
            persona = await cls._request_json(
                http_client,
                "GET",
                backend_url,
                f"/api/personas/{current.collected['persona_id']}",
                params=cls._owner_params(current),
            )
        except Exception:
            return None
        return (
            persona if isinstance(persona, dict) and persona.get("persona_id") else None
        )

    @classmethod
    async def _attach_uploaded_avatar(
        cls,
        current: SkillSession,
        persona: Dict[str, Any],
        backend_url: str,
        http_client: Any,
    ) -> Dict[str, Any]:
        uploaded_url = str(
            current.artifacts.get("uploaded_reference_image_url") or ""
        ).strip()
        uploaded_asset_id = str(
            current.artifacts.get("uploaded_reference_asset_id") or ""
        ).strip()
        if not uploaded_url:
            return persona

        telegram_chat_id = current.artifacts.get("telegram_chat_id")
        owner_key = f"telegram:{telegram_chat_id}" if telegram_chat_id else None
        patch_params = {"owner_key": owner_key} if owner_key else None
        patch_payload: Dict[str, Any] = {
            "avatar_image_url": uploaded_url,
            "avatar_source_type": "telegram_upload",
            "avatar_prompt": "telegram_upload",
        }
        if uploaded_asset_id:
            patch_payload["avatar_media_asset_id"] = uploaded_asset_id

        patched = await cls._request_json(
            http_client,
            "PATCH",
            backend_url,
            f"/api/personas/{current.collected['persona_id']}",
            params=patch_params,
            json=patch_payload,
        )
        return patched if isinstance(patched, dict) else persona

    @classmethod
    async def _persist_artifact_avatar(
        cls,
        current: SkillSession,
        persona: Dict[str, Any],
        backend_url: str,
        http_client: Any,
    ) -> Dict[str, Any]:
        artifact_avatar_url = str(
            current.artifacts.get("avatar_image_url")
            or current.artifacts.get("preview_image_url")
            or ""
        ).strip()
        artifact_media_asset_id = str(
            current.artifacts.get("avatar_media_asset_id") or ""
        ).strip()

        if not artifact_avatar_url or not artifact_media_asset_id:
            return persona
        if persona.get("avatar_image_url") and persona.get("avatar_media_asset_id"):
            return persona

        telegram_chat_id = current.artifacts.get("telegram_chat_id")
        owner_key = f"telegram:{telegram_chat_id}" if telegram_chat_id else None
        patch_params = {"owner_key": owner_key} if owner_key else None
        patch_payload: Dict[str, Any] = {
            "avatar_image_url": artifact_avatar_url,
            "avatar_media_asset_id": artifact_media_asset_id,
            "avatar_source_type": "generated",
        }
        appearance = str(current.collected.get("appearance_prompt_or_photo") or "").strip()
        if appearance:
            patch_payload["avatar_prompt"] = appearance

        patched = await cls._request_json(
            http_client,
            "PATCH",
            backend_url,
            f"/api/personas/{current.collected['persona_id']}",
            params=patch_params,
            json=patch_payload,
        )
        return patched if isinstance(patched, dict) else {**persona, **patch_payload}

    @classmethod
    async def _ensure_avatar_image(
        cls,
        current: SkillSession,
        persona: Dict[str, Any],
        backend_url: str,
        http_client: Any,
        *,
        force: bool = False,
    ) -> Dict[str, Any]:
        if persona.get("avatar_image_url") and not force:
            return persona

        appearance = str(
            current.collected.get("appearance_prompt_or_photo") or ""
        ).strip()
        if not appearance:
            return persona

        telegram_chat_id = current.artifacts.get("telegram_chat_id")
        owner_key = f"telegram:{telegram_chat_id}" if telegram_chat_id else None
        resolved_user_id = str(persona.get("user_id") or "").strip() or None
        base_metadata = {
            "source": "telegram_skill",
            "skill_name": cls.name,
            "persona_id": current.collected.get("persona_id"),
        }
        avatar_prompt = cls._build_avatar_prompt(appearance)
        fallback_avatar_prompt = cls._build_avatar_prompt(appearance, simplified=True)
        retryable_status_codes = {400, 422, 500, 502, 503, 504}

        def _avatar_http_error_message(exc: httpx.HTTPStatusError) -> str:
            status_code = exc.response.status_code if exc.response is not None else None
            detail = cls._extract_http_error_detail(exc)
            if status_code is None:
                return detail
            if status_code >= 500 and detail.lower() == "internal server error":
                return (
                    f"Avatar generation request failed ({status_code}): "
                    "upstream media service returned an internal error"
                )
            return f"Avatar generation request failed ({status_code}): {detail}"

        try:
            image_response = await cls._request_avatar_generation(
                current,
                backend_url,
                http_client,
                avatar_prompt=avatar_prompt,
                resolved_user_id=resolved_user_id,
                owner_key=owner_key,
                metadata=base_metadata,
            )
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code not in retryable_status_codes:
                raise RuntimeError(_avatar_http_error_message(exc)) from exc

            try:
                image_response = await cls._request_avatar_generation(
                    current,
                    backend_url,
                    http_client,
                    avatar_prompt=fallback_avatar_prompt,
                    resolved_user_id=resolved_user_id,
                    owner_key=owner_key,
                    metadata={
                        **base_metadata,
                        "retry_strategy": "simplified_prompt",
                        "retry_after_status": status_code,
                    },
                )
            except httpx.HTTPStatusError as retry_exc:
                raise RuntimeError(_avatar_http_error_message(retry_exc)) from retry_exc

        avatar_url = image_response.get("url")
        if not avatar_url:
            raise RuntimeError(
                "Avatar generation failed: No image URL returned. Please try again."
            )
        avatar_media_asset_id = image_response.get("media_asset_id")
        if not avatar_media_asset_id:
            images = image_response.get("images") or []
            if images:
                avatar_media_asset_id = images[0].get("media_asset_id")

        # CRITICAL FIX: Only proceed if we have a valid media_asset_id
        # Preview should never be shown without a persisted avatar asset
        if not avatar_media_asset_id:
            raise RuntimeError(
                "Avatar was generated but failed to persist to workspace storage "
                "(storage_status=source_only). This may be due to ownership/permission issues. "
                "Please try again or contact support if the issue persists."
            )

        patch_params = {"owner_key": owner_key} if owner_key else None
        patch_payload: Dict[str, Any] = {
            "avatar_image_url": avatar_url,
            "avatar_source_type": "generated",
            "avatar_prompt": appearance,
            "avatar_media_asset_id": avatar_media_asset_id,
        }
        try:
            patched = await cls._request_json(
                http_client,
                "PATCH",
                backend_url,
                f"/api/personas/{current.collected['persona_id']}",
                params=patch_params,
                json=patch_payload,
            )
            return patched if isinstance(patched, dict) else persona
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Persona doesn't exist yet (normal for early preview steps)
                # We return the local record so the caller has the new avatar info
                return {**persona, **patch_payload}
            raise RuntimeError(cls._extract_http_error_detail(e)) from e

    @classmethod
    async def _sync_persona_profile(
        cls,
        current: SkillSession,
        persona: Dict[str, Any],
        payload: Dict[str, Any],
        backend_url: str,
        http_client: Any,
    ) -> Dict[str, Any]:
        patch_fields: Dict[str, Any] = {}
        for field in ("display_name", "language", "tts_voice", "avatar_prompt"):
            desired = payload.get(field)
            if desired is not None and persona.get(field) != desired:
                patch_fields[field] = desired

        if not patch_fields:
            return persona

        telegram_chat_id = current.artifacts.get("telegram_chat_id")
        patch_params = (
            {"owner_key": f"telegram:{telegram_chat_id}"} if telegram_chat_id else None
        )
        patched = await cls._request_json(
            http_client,
            "PATCH",
            backend_url,
            f"/api/personas/{current.collected['persona_id']}",
            params=patch_params,
            json=patch_fields,
        )
        return patched if isinstance(patched, dict) else persona

    @classmethod
    async def execute(
        cls,
        session: Optional[SkillSession | Dict[str, Any]],
        backend_url: str,
        http_client: Any,
    ) -> SkillResult:
        current = cls._normalize_session(session)
        try:
            force_regenerate_avatar = bool(
                current.artifacts.pop("force_regenerate_avatar", False)
            )

            # ── Action Dispatcher (Handle Preview Buttons) ──────────────────
            # We catch commands from the preview screen (e.g., 'edit_p_name') 
            # and jump to the correct step immediately.
            command = current.collected.pop("preview_command", None)
            if command:
                if command == "ready":
                    current.step_key = "save"
                elif command == "cancel":
                    current.control.status = SkillStatus.done
                    return SkillResult(success=True, next_step="cancel", session=current)
                elif command == "rebuild_avatar":
                    current.artifacts["force_regenerate_avatar"] = True
                    current.step_key = "generate_preview"
                else:
                    # 'edit_p_name', 'edit_appearance', 'choose_voice', etc.
                    current.step_key = command
                    return cls._collecting_result(current, next_step=command)

            # ── Step 0: Dream Logic (Discovery Layer) ──────────────────────────
            # We skip this if we are editing an existing persona
            if current.artifacts.get("is_editing"):
                creation_mode = "manual"
            else:
                creation_mode = current.artifacts.get("creation_mode") or current.collected.get("creation_mode")

            if not creation_mode:
                current.step_key = "choose_creation_mode"
                return cls._collecting_result(current, next_step="choose_creation_mode")

            if creation_mode == "dream":
                # Handle Clear/Retry
                if current.collected.get("dream_confirmed") == "retry":
                    current.collected.pop("nationality", None)
                    current.collected.pop("voice", None)
                    current.collected.pop("dream_brief", None)
                    current.collected.pop("dream_confirmed", None)
                    current.artifacts["dream_ready"] = False
                    current.step_key = "collect_nationality"
                    return cls._collecting_result(current, next_step="collect_nationality")

                # Step 1: Nationality
                nationality = current.collected.get("nationality")
                if not nationality:
                    current.step_key = "collect_nationality"
                    return cls._collecting_result(current, next_step="collect_nationality")

                # Step 2: Voice
                voice = current.collected.get("voice")
                if not voice:
                    current.step_key = "choose_voice"
                    return cls._collecting_result(current, next_step="choose_voice")

                # Step 2.5: Language (Required for persistence)
                language = current.collected.get("language")
                if not language:
                    current.step_key = "choose_language"
                    return cls._collecting_result(current, next_step="choose_language")

                # Step 3: Brief/Description
                dream_brief = current.collected.get("dream_brief")
                if not dream_brief:
                    current.step_key = "collect_dream_brief"
                    return cls._collecting_result(current, next_step="collect_dream_brief")

                # Step 4: Generate Results
                if not current.artifacts.get("dream_ready"):
                    try:
                        dream = await cls._dream_persona_details_refined(
                            nationality, dream_brief
                        )
                    except Exception as exc:
                        logger.error(
                            "Dream AI generation failed with error type=%s: %s",
                            type(exc).__name__,
                            exc,
                            exc_info=True,
                        )
                        if cls._is_ai_auth_error(exc) or cls._is_ai_service_unavailable_error(exc):
                            logger.warning(
                                "Dream provider unavailable (auth=%s, service=%s), switching to deterministic fallback",
                                cls._is_ai_auth_error(exc),
                                cls._is_ai_service_unavailable_error(exc),
                            )
                            dream = cls._dream_persona_details_fallback(
                                nationality,
                                dream_brief,
                                reason="Provider unavailable. Generated from your inputs.",
                            )
                        else:
                            raise
                    
                    current.artifacts["dream_ready"] = True
                    current.collected["persona_id"] = dream["persona_id"]
                    current.collected["display_name"] = dream["display_name"]
                    current.collected["appearance_prompt_or_photo"] = dream["appearance"]
                    
                    # IMMEDIATELY generate avatar preview for the 'Wow' factor
                    try:
                        persona_record = {
                            "persona_id": dream["persona_id"],
                            "display_name": dream["display_name"],
                            "avatar_prompt": dream["appearance"],
                        }
                        persona_record = await cls._ensure_avatar_image(
                            current, 
                            persona_record, 
                            backend_url, 
                            http_client,
                            force=True
                        )
                        current.artifacts["avatar_image_url"] = persona_record.get("avatar_image_url")
                        current.artifacts["preview_image_url"] = persona_record.get("avatar_image_url")
                        current.artifacts["avatar_media_asset_id"] = persona_record.get("avatar_media_asset_id")
                    except Exception as e:
                        logger.error(f"Early avatar generation failed: {e}")
                    
                    summary = (
                        f"✨ *AI Suggested Identity:*\n"
                        f"Nationality: {nationality}\n"
                        f"Suggested Name: *{dream['display_name']}*\n"
                        f"ID: `{dream['persona_id']}`\n\n"
                        f"*Appearance:* {dream['appearance'][:200]}..."
                    )
                    if not dream.get("success"):
                        summary += f"\n\n⚠️ *AI Dream Warning:* {dream.get('error')}"
                        if dream.get("debug_info"):
                            summary += f"\n`{dream['debug_info']}`"

                    current.artifacts["dream_summary"] = summary
                    current.step_key = "confirm_dream"
                    return cls._collecting_result(
                        current, 
                        next_step="confirm_dream",
                        output={"message": summary}
                    )

                if current.collected.get("dream_confirmed") == "confirm":
                    current.step_key = "generate_preview"
                    # Proceed to standard collection
                elif current.step_key == "confirm_dream":
                    # Stay here until confirmed or retried
                    return cls._collecting_result(current, next_step="confirm_dream")

            # ── Step 1: Standard Collection ────────────────────────────────────
            # We re-evaluate missing params AFTER the dreaming layer has pre-filled them
            missing = cls._missing_required_params(current)
            if missing:
                next_step = current.step_key or "collect_persona_id"
                if "persona_id" in missing:
                    next_step = "collect_persona_id"
                elif "language" in missing:
                    next_step = "choose_language"
                elif "voice" in missing:
                    next_step = "choose_voice"
                elif "appearance_prompt_or_photo" in missing:
                    next_step = "collect_appearance"
                
                # Move step_key forward if it was still on confirm_dream
                current.step_key = next_step
                return cls._collecting_result(
                    current,
                    next_step=next_step,
                    output={"missing_params": missing},
                )

            # ── Step 2: Persistence Guard ──────────────────────────────────────
            # Logic: If we are on a final action step (save, preview, generate_preview),
            # OR we just finished an edit step, proceed to the database POST block.
            is_final_step = current.step_key in ["save", "generate_preview", "preview"]
            is_post_edit = current.step_key in ["edit_p_name", "edit_appearance", "choose_voice", "choose_language"]
            
            if not (is_final_step or is_post_edit):
                return cls._collecting_result(current, next_step=current.step_key)

            # If we just finished an edit, force a preview generation after saving
            if is_post_edit:
                current.step_key = "generate_preview"

            # NOTE: We explicitly construct the payload with ONLY valid DB columns.
            # Transient inputs like 'nationality' are filtered out here.
            display_name = current.collected.get("display_name") or cls._display_name_from_persona_id(
                current.collected["persona_id"]
            )
            payload = {
                "persona_id": current.collected["persona_id"],
                "display_name": display_name,
                "name": display_name, # Critical: 'name' is NOT NULL in schema.sql
                "language": current.collected["language"],
                "tts_voice": GoogleTTSService.resolve_voice_name(
                    current.collected["voice"],
                    language=current.collected.get("language"),
                ),
                "avatar_prompt": current.collected["appearance_prompt_or_photo"],
            }
            owner_params = cls._owner_params(current)
            if owner_params:
                payload.update(owner_params)
            try:
                persona = await cls._request_json(
                    http_client,
                    "POST",
                    backend_url,
                    "/api/personas",
                    json=payload,
                )
            except httpx.HTTPStatusError as exc:
                detail = "Failed to create persona. Please try again."
                try:
                    error_payload = exc.response.json()
                    if isinstance(error_payload, dict) and isinstance(
                        error_payload.get("detail"), str
                    ):
                        detail = error_payload["detail"]
                except Exception:
                    pass
                
                # Efficiently handle editing existing personas
                if "already exists" in detail.lower() or current.artifacts.get("is_editing"):
                    persona = await cls._get_existing_persona(
                        current, backend_url, http_client
                    )
                    if persona:
                        if current.artifacts.get("is_editing"):
                            logger.info(f"Editing existing persona | id={current.collected['persona_id']}")
                        else:
                            current.artifacts["resumed_existing_persona"] = True
                            logger.info(f"Resumed existing persona session | id={current.collected['persona_id']}")
                    else:
                        return cls._error_result(current, f"Persona '{current.collected['persona_id']}' exists but could not be fetched.")
                else:
                    return cls._error_result(current, detail)
            except Exception as exc:
                return cls._error_result(current, f"Failed to create persona: {exc}")

            # Sync profile and ensure avatar with clear error handling
            try:
                persona = await cls._sync_persona_profile(
                    current, persona, payload, backend_url, http_client
                )
            except Exception as exc:
                return cls._error_result(current, f"Failed to sync persona profile: {exc}")

            try:
                if current.artifacts.get("uploaded_reference_image_url"):
                    persona = await cls._attach_uploaded_avatar(
                        current, persona, backend_url, http_client
                    )
                else:
                    if (
                        creation_mode == "dream"
                        and current.artifacts.get("dream_ready")
                    ):
                        persona = await cls._persist_artifact_avatar(
                            current, persona, backend_url, http_client
                        )
                    persona = await cls._ensure_avatar_image(
                        current,
                        persona,
                        backend_url,
                        http_client,
                        force=force_regenerate_avatar,
                    )
            except Exception as exc:
                return cls._error_result(
                    current,
                    f"Failed to generate/attach persona avatar: {exc}. Please try again or use a different appearance description.",
                )

            uploaded_reference_url = current.artifacts.get("uploaded_reference_image_url")
            uploaded_reference_asset_id = current.artifacts.get(
                "uploaded_reference_asset_id"
            )
            if uploaded_reference_url and not persona.get("avatar_image_url"):
                persona = {**persona, "avatar_image_url": uploaded_reference_url}
            if uploaded_reference_asset_id and not persona.get("avatar_media_asset_id"):
                persona = {**persona, "avatar_media_asset_id": uploaded_reference_asset_id}

            readiness = cls._build_readiness_report(
                current.collected["persona_id"], persona
            )

            avatar_url = persona.get("avatar_image_url") or uploaded_reference_url
            current.artifacts["preview_image_url"] = avatar_url
            current.artifacts["avatar_image_url"] = avatar_url
            current.artifacts["avatar_media_asset_id"] = (
                persona.get("avatar_media_asset_id") or uploaded_reference_asset_id
            )
            current.artifacts["heygen_avatar_id"] = persona.get("heygen_avatar_id")
            current.artifacts["persona_id"] = persona.get("persona_id")
            current.artifacts["persona_data"] = persona
            current.artifacts["readiness"] = readiness
            if current.step_key == "save":
                current.control.status = SkillStatus.done
                return SkillResult(
                    success=True,
                    next_step="done",
                    output={
                        "message": f"✅ Persona *{current.collected['persona_id']}* saved, linked to storage, and marked as ready\\!",
                        "persona": persona,
                        "readiness": readiness,
                    },
                    session=current,
                )

            current.step_key = "preview"
            current.control.status = SkillStatus.preview_ready
            return SkillResult(
                success=True,
                next_step="preview",
                output={
                    "persona": persona,
                    "readiness": readiness,
                    "preview_image_url": avatar_url,
                    "backend_status": cls.backend_status,
                },
                session=current,
            )
        except Exception as exc:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"SKILL EXECUTION FAILED: {exc}\n{error_details}")
            msg = "🚫 Unexpected error while creating persona. Please try again or send /cancel."
            return cls._error_result(current, msg)
