"""Persona creation skill wrapper."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, Optional

import httpx
from services.google_tts_service import GoogleTTSService

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
            if checks["has_avatar_image"] and checks["has_avatar_asset"]:
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

        avatar_prompt = (
            "Create a clean, realistic head-and-shoulders portrait avatar for a social media creator.\n"
            f"Appearance brief: {appearance}\n"
            "Style: premium, natural lighting, plain background, centered composition."
        )
        telegram_chat_id = current.artifacts.get("telegram_chat_id")
        owner_key = f"telegram:{telegram_chat_id}" if telegram_chat_id else None

        image_response = await cls._request_json(
            http_client,
            "POST",
            backend_url,
            "/api/media/generate/image",
            json={
                "prompt": avatar_prompt,
                "aspect_ratio": "1:1",
                "num_images": 1,
                "owner_key": owner_key,
                "persona_id": current.collected.get("persona_id"),
                "metadata": {
                    "source": "telegram_skill",
                    "skill_name": cls.name,
                    "persona_id": current.collected.get("persona_id"),
                },
            },
        )
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
        force_regenerate_avatar = bool(
            current.artifacts.pop("force_regenerate_avatar", False)
        )
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
            return cls._collecting_result(
                current,
                next_step=next_step,
                output={"missing_params": missing},
            )

        payload = {
            "persona_id": current.collected["persona_id"],
            "display_name": cls._display_name_from_persona_id(
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
            if "already exists" in detail.lower():
                persona = await cls._get_existing_persona(
                    current, backend_url, http_client
                )
                if persona:
                    current.artifacts["resumed_existing_persona"] = True
                else:
                    return cls._error_result(current, detail)
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
