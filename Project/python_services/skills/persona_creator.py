"""Persona creation skill wrapper."""

from __future__ import annotations

import asyncio
import re
from copy import deepcopy
from typing import Any, Dict, Optional

import httpx
import json
import logging
from config.settings import settings
from services.google_tts_service import GoogleTTSService
from services.ai_service import AIService

logger = logging.getLogger(__name__)

from .base import BaseSkill, SkillResult, SkillSession, SkillStatus
from .definitions import get_skill_definition

_DEFINITION = get_skill_definition("persona-creator")


class PersonaCreatorSkill(BaseSkill):
    name = "persona-creator"
    required_params = ["persona_id", "language", "voice", "appearance_prompt_or_photo"]
    optional_params = ["nationality", "brief", "gender", "identity_notes", "creative_notes"]
    api_target = _DEFINITION.get("api_call", {}).get(
        "target",
        "POST /api/personas + PATCH /api/personas/{persona_id} + GET /api/personas/{persona_id}/readiness",
    )
    backend_status = _DEFINITION.get("status", "partial")
    steps = list(_DEFINITION.get("steps", []))
    session_shape = deepcopy(_DEFINITION.get("session_shape", BaseSkill.session_shape))

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
                "Looking at camera, plain neutral background, natural lighting, centered composition, "
                "no text, no logos, no props, no extra people, no collage."
            )

        normalized = cls._trim_text(appearance, max_length=600)
        return (
            "Create a clean, realistic head-and-shoulders portrait avatar for a social media creator.\n"
            f"Appearance brief: {normalized}\n"
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
    async def _dream_persona_details(
        cls, brief: str, ai_service: AIService
    ) -> Dict[str, Any]:
        """Use AI to suggest a name, ID, and appearance description based on a brief."""
        system_prompt = (
            "You are a creative persona designer for an AI social media agency.\n"
            "Given a brief (nationality, gender, optional vibes), suggest:\n"
            "1. display_name: A natural-sounding full name for this persona.\n"
            "2. persona_id: A unique snake_case slug (max 12 chars).\n"
            "3. appearance: A 150-word photorealistic description for AI image generation, "
            "focusing on features, outfit, lighting, and a high-end social media look.\n"
            "\n"
            "RESPONSE FORMAT: Strict JSON only.\n"
            "{\n"
            '  "display_name": "...",\n'
            '  "persona_id": "...",\n'
            '  "appearance": "..."\n'
            "}"
        )
        try:
            raw_json = await ai_service.generate_text(
                prompt=f"Dream up a persona for this brief: {brief}",
                system_prompt=system_prompt,
                temperature=0.8,
                max_tokens=600,
            )
            # Find the first { and last } to handle any extra text from AI
            start = raw_json.find("{")
            end = raw_json.rfind("}") + 1
            if start == -1 or end == 0:
                raise ValueError("AI did not return valid JSON block")
            
            data = json.loads(raw_json[start:end])
            return {
                "display_name": str(data.get("display_name") or "Unnamed Persona"),
                "persona_id": str(data.get("persona_id") or "unnamed_p")[:15].strip("_"),
                "appearance": str(data.get("appearance") or ""),
            }
        except Exception as e:
            import traceback
            logger.error(f"Failed to generate dream identity: {e}")
            
        # Robust fallback
        name = f"{nationality} Creator"
        return {
            "name": name,
            "id": f"{name.lower().replace(' ', '_')}_{int(asyncio.get_event_loop().time()) % 1000}",
            "refined_prompt": f"Photorealistic portrait of a {nationality} person, {brief}"
        }

    @classmethod
    async def _dream_persona_details(cls, brief: str, ai: AIService) -> Dict[str, Any]:
        """Legacy method - kept for backward compatibility if needed, but not used in the new flow."""
        return {}

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
            if status_code not in {400, 422}:
                raise RuntimeError(cls._extract_http_error_detail(exc)) from exc

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
                raise RuntimeError(cls._extract_http_error_detail(retry_exc)) from retry_exc

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
                # Revised Flow: Nationality -> Voice -> Description -> Auto-Gen
                nationality = current.collected.get("nationality")
                if not nationality:
                    current.step_key = "collect_nationality"
                    return cls._collecting_result(current, next_step="collect_nationality")
                
                voice = current.collected.get("voice")
                if not voice:
                    current.step_key = "choose_voice"
                    return cls._collecting_result(current, next_step="choose_voice")
                
                dream_brief = current.collected.get("brief")
                if not dream_brief:
                    current.step_key = "collect_description"
                    return cls._collecting_result(current, next_step="collect_description")

                # 4. Trigger AI Identity Generation once we have all 3
                if not current.artifacts.get("dream_identity_ready"):
                    dream = await cls._generate_dream_identity(nationality, dream_brief, voice)
                    
                    # Store suggestions in artifacts first
                    current.artifacts["dream_suggestion"] = dream
                    current.artifacts["dream_summary"] = (
                        f"✨ *AI Suggested Identity:*\n"
                        f"Name: *{dream['name']}*\n"
                        f"ID: `{dream['id']}`\n\n"
                        f"*Refined Appearance:* {dream['refined_prompt'][:200]}..."
                    )
                    current.artifacts["dream_identity_ready"] = True
                    current.step_key = "confirm_dream"
                    return cls._collecting_result(
                        current, next_step="confirm_dream", output={"message": current.artifacts["dream_summary"]}
                    )

                # 5. Handle Confirmation
                if current.step_key == "confirm_dream":
                    confirm = current.collected.get("confirm_dream")
                    if confirm == "retry":
                        # Start over from nationality
                        to_clear = ["nationality", "voice", "brief"]
                        for field in to_clear:
                            current.collected.pop(field, None)
                        current.artifacts.pop("dream_identity_ready", None)
                        current.artifacts.pop("dream_suggestion", None)
                        current.step_key = "collect_nationality"
                        return cls._collecting_result(current, next_step="collect_nationality")
                    
                    if confirm == "confirm":
                        # Commit the suggestion to standard fields and proceed
                        dream = current.artifacts.get("dream_suggestion", {})
                        current.collected["persona_id"] = dream.get("id")
                        current.collected["language"] = current.collected.get("language") or "English"
                        current.collected["appearance_prompt_or_photo"] = dream.get("refined_prompt")
                        current.artifacts["display_name_suggestion"] = dream.get("name")
                        
                        # Proceed directly to preview generation (Step 1 below will fall through)
                        pass
                    else:
                        # Re-show the summary if no valid confirm button yet
                        return cls._collecting_result(
                            current, next_step="confirm_dream", output={"message": current.artifacts["dream_summary"]}
                        )

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
            # IMPORTANT: We only proceed to the heavy POST block if we are actually
            # on the final preview or save steps. This prevents "Stuck" issues 
            # on intermediate steps like 'confirm_dream'.
            if current.step_key not in ["save", "generate_preview", "preview"]:
                return cls._collecting_result(current, next_step=current.step_key)

            payload = {
                "persona_id": current.collected["persona_id"],
                "display_name": current.artifacts.get("display_name_suggestion") or cls._display_name_from_persona_id(
                    current.collected["persona_id"]
                ),
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
            msg = f"🚫 Unexpected Error: {exc}"
            if getattr(settings, "DEBUG", False):
                msg += f"\n\nTraceback:\n{error_details[:800]}"
            return cls._error_result(current, msg)
