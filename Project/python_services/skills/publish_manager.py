"""Publish queue skill wrapper."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

from .base import BaseSkill, SkillResult, SkillSession, SkillStatus
from .definitions import get_skill_definition

_DEFINITION = get_skill_definition("publish-manager")


class PublishManagerSkill(BaseSkill):
    name = "publish-manager"
    required_params: List[str] = list(_DEFINITION.get("required_params", []))
    optional_params = list(_DEFINITION.get("optional_params", []))
    api_target = _DEFINITION.get("api_call", {}).get(
        "target",
        "GET /api/content/list + POST /api/content/retry/{content_id}",
    )
    backend_status = _DEFINITION.get("status", "partial")
    steps = list(_DEFINITION.get("steps", []))
    session_shape = deepcopy(_DEFINITION.get("session_shape", BaseSkill.session_shape))

    @classmethod
    async def _fetch_queue(
        cls,
        backend_url: str,
        http_client: Any,
        *,
        limit: int = 8,
    ) -> List[Dict[str, Any]]:
        response = await cls._request_json(
            http_client,
            "GET",
            backend_url,
            "/api/content/list",
            params={"limit": limit},
        )
        items = response.get("items")
        if not isinstance(items, list):
            return []
        return items

    @classmethod
    def _select_item_result(
        cls,
        session: SkillSession,
        *,
        message: str,
    ) -> SkillResult:
        session.step_key = "select_item"
        session.control.status = SkillStatus.collecting
        return SkillResult(
            success=True,
            next_step="select_item",
            output={
                "queue_items": list(session.artifacts.get("queue_items") or []),
                "message": message,
            },
            session=session,
        )

    @classmethod
    def _item_actions_result(
        cls,
        session: SkillSession,
        item: Dict[str, Any],
        *,
        message: Optional[str] = None,
    ) -> SkillResult:
        session.artifacts["selected_item"] = item
        session.step_key = "publish_or_schedule"
        session.control.status = SkillStatus.collecting
        return SkillResult(
            success=True,
            next_step="publish_or_schedule",
            output={
                "content_item": item,
                "queue_items": list(session.artifacts.get("queue_items") or []),
                "message": message or "Inspect the item, retry failed posts, or go back.",
            },
            session=session,
        )

    @classmethod
    async def execute(
        cls,
        session: Optional[SkillSession | Dict[str, Any]],
        backend_url: str,
        http_client: Any,
    ) -> SkillResult:
        current = cls._normalize_session(session)

        if current.step_key == "list_publish_queue" or not current.artifacts.get("queue_items"):
            queue_items = await cls._fetch_queue(backend_url, http_client)
            current.artifacts["queue_items"] = queue_items
            current.artifacts["selected_item"] = None
            if not cls._has_value(current.collected.get("content_id")):
                return cls._select_item_result(
                    current,
                    message="Choose a recent publish item to inspect.",
                )

        content_id = current.collected.get("content_id")
        if not cls._has_value(content_id):
            return cls._select_item_result(
                current,
                message="Choose a recent publish item to inspect.",
            )

        queue_items = list(current.artifacts.get("queue_items") or [])
        selected_item = next((item for item in queue_items if item.get("id") == content_id), None)
        if selected_item is None:
            queue_items = await cls._fetch_queue(backend_url, http_client)
            current.artifacts["queue_items"] = queue_items
            selected_item = next((item for item in queue_items if item.get("id") == content_id), None)

        if selected_item is None:
            current.collected["content_id"] = None
            return cls._select_item_result(
                current,
                message="That publish item is no longer in the recent queue. Pick another one.",
            )

        return cls._item_actions_result(current, selected_item)

    @classmethod
    def back_to_queue(cls, session: SkillSession) -> SkillResult:
        session.collected["content_id"] = None
        session.artifacts["selected_item"] = None
        return cls._select_item_result(
            session,
            message="Choose another publish item to inspect.",
        )

    @classmethod
    async def retry_selected(
        cls,
        session: SkillSession,
        backend_url: str,
        http_client: Any,
    ) -> SkillResult:
        selected_item = session.artifacts.get("selected_item") or {}
        if not selected_item.get("id"):
            return cls._error_result(session, "Pick a publish item before retrying.")

        if selected_item.get("status") != "failed":
            return cls._item_actions_result(
                session,
                selected_item,
                message="Only failed items can be retried right now.",
            )

        response = await cls._request_json(
            http_client,
            "POST",
            backend_url,
            f"/api/content/retry/{selected_item['id']}",
        )
        session.artifacts["publish_result"] = response
        session.step_key = "done"
        session.control.status = SkillStatus.done
        return SkillResult(
            success=True,
            next_step="done",
            output={
                "content_item": selected_item,
                "workflow_id": response.get("workflow_id"),
                "run_id": response.get("run_id"),
                "status": response.get("status"),
                "message": "Retry workflow started for the selected failed post.",
            },
            session=session,
        )
