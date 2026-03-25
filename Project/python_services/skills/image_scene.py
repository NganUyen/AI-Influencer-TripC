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
        return [result for result in results if result is not None]

    @classmethod
    def _done_output(cls, session: SkillSession) -> Dict[str, Any]:
        image_urls = list(session.artifacts.get("final_image_urls") or [])
        storage_keys = list(session.artifacts.get("final_storage_keys") or [])

        if not image_urls and session.artifacts.get("final_image_url"):
            image_urls = [session.artifacts["final_image_url"]]
        if not storage_keys and session.artifacts.get("storage_key"):
            storage_keys = [session.artifacts["storage_key"]]

        return {
            "image_url": image_urls[0] if image_urls else None,
            "image_urls": image_urls,
            "storage_key": storage_keys[0] if storage_keys else None,
            "storage_keys": storage_keys,
            "selected_indexes": list(session.artifacts.get("selected_candidate_indexes") or []),
            "candidates_count": len(session.artifacts.get("image_candidates", [])),
        }

    @classmethod
    async def execute(
        cls,
        session: Optional[SkillSession | Dict[str, Any]],
        backend_url: str,
        http_client: Any,
    ) -> SkillResult:
        current = cls._normalize_session(session)
        missing = cls._missing_required_params(current)

        if missing:
            next_step = "choose_style" if "style" in missing else "collect_prompt"
            return cls._collecting_result(
                current,
                next_step=next_step,
                output={"missing_params": missing},
            )

        if current.artifacts.get("final_image_url") or current.artifacts.get("final_image_urls"):
            current.step_key = "done"
            current.control.status = SkillStatus.done
            return SkillResult(
                success=True,
                next_step="done",
                output=cls._done_output(current),
                session=current,
            )

        candidates = current.artifacts.get("image_candidates", [])
        if candidates and current.step_key in {"confirm_or_regenerate", "selecting_images"}:
            return SkillResult(
                success=True,
                next_step=current.step_key,
                output={
                    "image_candidates": candidates,
                    "candidate_count": len(candidates),
                    "selected_candidate_indexes": list(
                        current.artifacts.get("selected_candidate_indexes", [])
                    ),
                    "message": (
                        "Use Images to choose one or more images, regenerate for a new batch,"
                        " or cancel."
                    ),
                },
                session=current,
            )

        payload = {
            "prompt": cls._build_prompt(current.collected),
            "aspect_ratio": current.collected.get("aspect_ratio") or "16:9",
        }
        candidates = await cls._generate_candidates(
            http_client,
            backend_url,
            payload,
            count=cls.DEFAULT_CANDIDATE_COUNT,
        )

        if not candidates:
            return cls._error_result(current, "Failed to generate any images. Please try again.")

        current.artifacts["image_candidates"] = candidates
        current.artifacts["selected_candidate_index"] = None
        current.artifacts["selected_candidate_indexes"] = []
        current.step_key = "confirm_or_regenerate"
        current.control.status = SkillStatus.preview_ready

        return SkillResult(
            success=True,
            next_step="confirm_or_regenerate",
            output={
                "image_candidates": candidates,
                "candidate_count": len(candidates),
                "selected_candidate_indexes": [],
                "message": (
                    f"Generated {len(candidates)} image options. "
                    "Choose Use Images to select one or more."
                ),
            },
            session=current,
        )

    @classmethod
    def enter_selection_mode(cls, session: SkillSession) -> SkillResult:
        candidates = session.artifacts.get("image_candidates", [])
        if not candidates:
            return cls._error_result(session, "No generated images available to select.")

        session.step_key = "selecting_images"
        session.control.status = SkillStatus.collecting
        return SkillResult(
            success=True,
            next_step="selecting_images",
            output={
                "image_candidates": candidates,
                "selected_candidate_indexes": list(
                    session.artifacts.get("selected_candidate_indexes", [])
                ),
                "message": "Select one or more images, then press Submit.",
            },
            session=session,
        )

    @classmethod
    def toggle_selection(
        cls,
        session: SkillSession,
        selected_index: int,
    ) -> SkillResult:
        candidates = session.artifacts.get("image_candidates", [])
        if not (0 <= selected_index < len(candidates)):
            return cls._error_result(session, f"Invalid selection: {selected_index}")

        selected_indexes = list(session.artifacts.get("selected_candidate_indexes", []))
        if selected_index in selected_indexes:
            selected_indexes.remove(selected_index)
        else:
            selected_indexes.append(selected_index)
            selected_indexes.sort()

        session.artifacts["selected_candidate_indexes"] = selected_indexes
        session.step_key = "selecting_images"
        session.control.status = SkillStatus.collecting

        return SkillResult(
            success=True,
            next_step="selecting_images",
            output={
                "image_candidates": candidates,
                "selected_candidate_indexes": selected_indexes,
                "message": (
                    "Select one or more images, then press Submit."
                    if selected_indexes
                    else "No images selected yet. Pick one or more images."
                ),
            },
            session=session,
        )

    @classmethod
    def return_to_preview(cls, session: SkillSession) -> SkillResult:
        candidates = session.artifacts.get("image_candidates", [])
        if not candidates:
            return cls._error_result(session, "No generated images available to preview.")

        session.step_key = "confirm_or_regenerate"
        session.control.status = SkillStatus.preview_ready
        return SkillResult(
            success=True,
            next_step="confirm_or_regenerate",
            output={
                "image_candidates": candidates,
                "candidate_count": len(candidates),
                "selected_candidate_indexes": list(
                    session.artifacts.get("selected_candidate_indexes", [])
                ),
                "message": "Current batch is ready. Use Images, Regenerate, or Cancel.",
            },
            session=session,
        )

    @classmethod
    def submit_selection(cls, session: SkillSession) -> SkillResult:
        candidates = session.artifacts.get("image_candidates", [])
        selected_indexes = list(session.artifacts.get("selected_candidate_indexes", []))

        if not selected_indexes:
            session.step_key = "selecting_images"
            session.control.status = SkillStatus.collecting
            return SkillResult(
                success=True,
                next_step="selecting_images",
                output={
                    "image_candidates": candidates,
                    "selected_candidate_indexes": [],
                    "message": "Choose at least one image before submitting.",
                },
                session=session,
            )

        selected_images = [candidates[index] for index in selected_indexes]
        image_urls = [item["url"] for item in selected_images]
        storage_keys = [item.get("storage_key") for item in selected_images]

        session.artifacts["selected_candidate_index"] = selected_indexes[0]
        session.artifacts["preview_image_url"] = image_urls[0]
        session.artifacts["final_image_url"] = image_urls[0]
        session.artifacts["final_image_urls"] = image_urls
        session.artifacts["storage_key"] = storage_keys[0]
        session.artifacts["final_storage_keys"] = storage_keys
        session.step_key = "done"
        session.control.status = SkillStatus.done

        return SkillResult(
            success=True,
            next_step="done",
            output={
                "image_url": image_urls[0],
                "image_urls": image_urls,
                "storage_key": storage_keys[0],
                "storage_keys": storage_keys,
                "selected_index": selected_indexes[0],
                "selected_indexes": selected_indexes,
                "total_selected": len(selected_indexes),
                "total_candidates": len(candidates),
            },
            session=session,
        )

    @classmethod
    def handle_selection(
        cls,
        session: SkillSession,
        selected_index: int,
    ) -> SkillResult:
        """Backward-compatible single-image selection helper."""
        candidates = session.artifacts.get("image_candidates", [])
        if not (0 <= selected_index < len(candidates)):
            return cls._error_result(session, f"Invalid selection: {selected_index}")

        session.artifacts["selected_candidate_indexes"] = [selected_index]
        result = cls.submit_selection(session)
        if result.success and isinstance(result.output, dict):
            result.output["selected_index"] = selected_index
        return result
