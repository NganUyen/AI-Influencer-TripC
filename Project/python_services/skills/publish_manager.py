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

    @classmethod
    async def inspect_provider_wiring(
        cls,
        session: SkillSession,
        backend_url: str,
        http_client: Any,
    ) -> SkillResult:
        selected_item = session.artifacts.get("selected_item") or {}
        content_id = selected_item.get("id")
        if not content_id:
            return cls._error_result(session, "Pick a publish item before inspecting provider wiring.")

        wiring = await cls._request_json(
            http_client,
            "GET",
            backend_url,
            f"/api/content/providers/{content_id}",
        )

        session.artifacts["selected_item"] = {
            **selected_item,
            "postUrl": wiring.get("post_url") or selected_item.get("postUrl"),
            "platformPostId": wiring.get("platform_post_id") or selected_item.get("platformPostId"),
            "providerPostId": wiring.get("provider_post_id") or selected_item.get("providerPostId"),
            "publishMethod": wiring.get("publish_method") or selected_item.get("publishMethod"),
            "syndicateTriggered": wiring.get("syndicate_triggered"),
            "syndicateJobId": wiring.get("syndicate_job_id"),
            "engagementMetrics": wiring.get("engagement_metrics") or selected_item.get("engagementMetrics"),
        }
        session.artifacts["provider_wiring"] = wiring
        session.step_key = "publish_or_schedule"
        session.control.status = SkillStatus.collecting
        return SkillResult(
            success=True,
            next_step="publish_or_schedule",
            output={
                "content_item": session.artifacts["selected_item"],
                "provider_wiring": wiring,
                "message": "Provider wiring refreshed for this item.",
            },
            session=session,
        )

    @classmethod
    async def refresh_selected_engagement(
        cls,
        session: SkillSession,
        backend_url: str,
        http_client: Any,
    ) -> SkillResult:
        selected_item = session.artifacts.get("selected_item") or {}
        content_id = selected_item.get("id")
        if not content_id:
            return cls._error_result(session, "Pick a publish item before checking engagement.")

        snapshot = await cls._request_json(
            http_client,
            "GET",
            backend_url,
            f"/api/content/engagement/{content_id}",
        )

        metrics = snapshot.get("metrics") or {}
        session.artifacts["selected_item"] = {
            **selected_item,
            "engagementMetrics": metrics,
            "lastEngagementCheckedAt": snapshot.get("checked_at") or snapshot.get("status"),
        }
        session.artifacts["engagement_result"] = snapshot
        session.step_key = "publish_or_schedule"
        session.control.status = SkillStatus.collecting
        return SkillResult(
            success=True,
            next_step="publish_or_schedule",
            output={
                "content_item": session.artifacts["selected_item"],
                "engagement": snapshot,
                "message": "Engagement snapshot refreshed.",
            },
            session=session,
        )

    @classmethod
    async def boost_selected_engagement(
        cls,
        session: SkillSession,
        backend_url: str,
        http_client: Any,
    ) -> SkillResult:
        selected_item = session.artifacts.get("selected_item") or {}
        content_id = selected_item.get("id")
        if not content_id:
            return cls._error_result(session, "Pick a publish item before triggering engagement.")

        trigger = await cls._request_json(
            http_client,
            "POST",
            backend_url,
            f"/api/content/engagement/{content_id}/trigger",
            json={
                "action_types": ["like", "comment", "share"],
                "account_count": 5,
                "delay_minutes": 30,
            },
        )

        session.artifacts["selected_item"] = {
            **selected_item,
            "syndicateTriggered": True,
            "syndicateJobId": (trigger.get("job") or {}).get("job_id"),
            "postUrl": trigger.get("post_url") or selected_item.get("postUrl"),
        }
        session.artifacts["engagement_trigger_result"] = trigger
        session.step_key = "publish_or_schedule"
        session.control.status = SkillStatus.collecting
        return SkillResult(
            success=True,
            next_step="publish_or_schedule",
            output={
                "content_item": session.artifacts["selected_item"],
                "engagement_trigger": trigger,
                "message": "GrowChief engagement boost has been triggered.",
            },
            session=session,
        )
