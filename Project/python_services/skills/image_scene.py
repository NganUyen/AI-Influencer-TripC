"""Image scene skill wrapper with multi-candidate selection."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any, Dict, List, Optional

from .base import BaseSkill, SkillResult, SkillSession, SkillStatus
from .definitions import get_skill_definition

_DEFINITION = get_skill_definition("image-scene")


class ImageSceneSkill(BaseSkill):
    name = "image-scene"
    required_params = list(_DEFINITION.get("required_params", []))
    optional_params = list(_DEFINITION.get("optional_params", []))
    api_target = _DEFINITION.get("api_call", {}).get("target", "POST /api/media/generate/image")
    backend_status = _DEFINITION.get("status", "implemented")
    steps = list(_DEFINITION.get("steps", []))
    session_shape = deepcopy(_DEFINITION.get("session_shape", BaseSkill.session_shape))

    # Number of candidates to generate per batch
    DEFAULT_CANDIDATE_COUNT = 4

    @classmethod
    def _build_prompt(cls, collected: Dict[str, Any]) -> str:
        lines = [str(collected["topic_or_prompt"]).strip()]
        if collected.get("scene_type"):
            lines.append(f"Scene type: {collected['scene_type']}")
        if collected.get("style"):
            lines.append(f"Style: {collected['style']}")
        if collected.get("persona_id"):
            lines.append(f"Persona reference: {collected['persona_id']}")
        if collected.get("freeform_brief"):
            lines.append(f"Brief: {collected['freeform_brief']}")
        if collected.get("creative_notes"):
            lines.append(f"Creative notes: {collected['creative_notes']}")
        return "\n".join(lines)

    @classmethod
    async def _generate_single_image(
        cls,
        http_client: Any,
        backend_url: str,
        payload: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Generate a single image. Returns {url, storage_key, model, prompt} or None on error."""
        try:
            response = await cls._request_json(
                http_client,
                "POST",
                backend_url,
                cls._extract_path(),
                json=payload,
            )
            image_url = response.get("url")
            if image_url:
                return {
                    "url": image_url,
                    "storage_key": response.get("storage_key"),
                    "model": response.get("model"),
                    "prompt": response.get("prompt"),
                }
            return None
        except Exception:
            return None

    @classmethod
    async def _generate_candidates(
        cls,
        http_client: Any,
        backend_url: str,
        payload: Dict[str, Any],
        count: int = DEFAULT_CANDIDATE_COUNT,
    ) -> List[Dict[str, Any]]:
        """Generate multiple image candidates in parallel."""
        tasks = [
            cls._generate_single_image(http_client, backend_url, payload)
            for _ in range(count)
        ]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    @classmethod
    async def execute(
        cls,
        session: Optional[SkillSession | Dict[str, Any]],
        backend_url: str,
        http_client: Any,
    ) -> SkillResult:
        current = cls._normalize_session(session)
        missing = cls._missing_required_params(current)

        # Step 1: Collect params
        if missing:
            next_step = "choose_style" if "style" in missing else "collect_prompt"
            return cls._collecting_result(
                current,
                next_step=next_step,
                output={"missing_params": missing},
            )

        # Step 2: Check if user already selected an image → done
        if current.artifacts.get("final_image_url"):
            current.step_key = "done"
            current.control.status = SkillStatus.done
            return SkillResult(
                success=True,
                next_step="done",
                output={
                    "image_url": current.artifacts.get("final_image_url"),
                    "storage_key": current.artifacts.get("storage_key"),
                    "candidates_count": len(current.artifacts.get("image_candidates", [])),
                },
                session=current,
            )

        # Step 3: Check if we're in selection phase (candidates already generated)
        candidates = current.artifacts.get("image_candidates", [])
        if candidates and current.step_key == "selecting_image":
            # User should select one candidate
            # This is handled by the router/Telegram layer:
            # They will respond with "select_candidate_{index}" or "regenerate"
            return cls._collecting_result(
                current,
                next_step="selecting_image",
                output={
                    "image_candidates": candidates,
                    "candidate_count": len(candidates),
                    "message": "Choose your preferred image or regenerate for more options",
                },
            )

        # Step 4: Generate image candidates (first time or regenerate)
        payload = {
            "prompt": cls._build_prompt(current.collected),
            "aspect_ratio": current.collected.get("aspect_ratio") or "16:9",
        }

        # Generate multiple candidates in parallel
        candidates = await cls._generate_candidates(
            http_client,
            backend_url,
            payload,
            count=cls.DEFAULT_CANDIDATE_COUNT,
        )

        if not candidates:
            return cls._error_result(current, "Failed to generate any images. Please try again.")

        # Store candidates in artifacts
        current.artifacts["image_candidates"] = candidates
        current.artifacts["selected_candidate_index"] = None
        current.step_key = "selecting_image"
        current.control.status = SkillStatus.preview_ready

        return SkillResult(
            success=True,
            next_step="selecting_image",
            output={
                "image_candidates": candidates,
                "candidate_count": len(candidates),
                "message": f"Generated {len(candidates)} image options. Choose your favorite!",
            },
            session=current,
        )

    @classmethod
    def handle_selection(
        cls,
        session: SkillSession,
        selected_index: int,
    ) -> SkillResult:
        """Handle user's image selection (called by router after user picks)."""
        candidates = session.artifacts.get("image_candidates", [])

        if not (0 <= selected_index < len(candidates)):
            return cls._error_result(session, f"Invalid selection: {selected_index}")

        selected = candidates[selected_index]
        session.artifacts["selected_candidate_index"] = selected_index
        session.artifacts["preview_image_url"] = selected["url"]
        session.artifacts["final_image_url"] = selected["url"]
        session.artifacts["storage_key"] = selected.get("storage_key")
        session.step_key = "done"
        session.control.status = SkillStatus.done

        return SkillResult(
            success=True,
            next_step="done",
            output={
                "image_url": selected["url"],
                "storage_key": selected.get("storage_key"),
                "selected_index": selected_index,
                "total_candidates": len(candidates),
            },
            session=session,
        )

