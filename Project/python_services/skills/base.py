"""Base models and helpers for OpenClaw Telegram skill integration."""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from copy import deepcopy
from enum import Enum
from typing import Any, ClassVar, Dict, List, Optional

from pydantic import BaseModel, Field


class SkillStatus(str, Enum):
    collecting = "collecting"
    preview_ready = "preview_ready"
    running = "running"
    waiting_approval = "waiting_approval"
    done = "done"
    failed = "failed"


class SkillControl(BaseModel):
    status: SkillStatus = SkillStatus.collecting
    workflow_id: Optional[str] = None
    approval_required: bool = False
    error_message: Optional[str] = None


class SkillSession(BaseModel):
    skill_name: str
    step_key: str
    collected: Dict[str, Any] = Field(default_factory=dict)
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    control: SkillControl = Field(default_factory=SkillControl)
    last_result: Optional["SkillResult"] = None


class SkillResult(BaseModel):
    success: bool
    next_step: Optional[str] = None
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    session: Optional[SkillSession] = None


class BaseSkill(ABC):
    name: ClassVar[str] = ""
    required_params: ClassVar[List[str]] = []
    optional_params: ClassVar[List[str]] = []
    api_target: ClassVar[str] = ""
    backend_status: ClassVar[str] = "implemented"
    steps: ClassVar[List[str]] = []
    session_shape: ClassVar[Dict[str, Any]] = {
        "step_key": "collecting",
        "collected": {},
        "artifacts": {},
    }

    @classmethod
    def initial_session(cls) -> SkillSession:
        template = deepcopy(cls.session_shape)
        return SkillSession(
            skill_name=cls.name,
            step_key=template.get("step_key", "collecting"),
            collected=template.get("collected", {}),
            artifacts=template.get("artifacts", {}),
            control=SkillControl(),
        )

    @classmethod
    def _normalize_session(
        cls,
        session: Optional[SkillSession | Dict[str, Any]],
    ) -> SkillSession:
        if session is None:
            return cls.initial_session()
        if isinstance(session, SkillSession):
            return session.model_copy(deep=True)
        return SkillSession.model_validate(session)

    @classmethod
    def _has_value(cls, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, dict, tuple, set)):
            return bool(value)
        return True

    @classmethod
    def _missing_required_params(cls, session: SkillSession) -> List[str]:
        return [
            param
            for param in cls.required_params
            if not cls._has_value(session.collected.get(param))
        ]

    @classmethod
    def _extract_path(cls, api_target: Optional[str] = None) -> str:
        target = api_target or cls.api_target
        match = re.search(r"/api/[A-Za-z0-9_./{}*-]+", target)
        if not match:
            raise ValueError(f"Could not extract API path from target: {target}")
        return match.group(0)

    @classmethod
    def _build_url(cls, backend_url: str, path: str) -> str:
        return f"{backend_url.rstrip('/')}/{path.lstrip('/')}"

    @classmethod
    def _auth_headers(cls) -> Dict[str, str]:
        token = os.getenv("INTERNAL_API_TOKEN", "").strip()
        if not token:
            try:
                from config.settings import settings

                token = (getattr(settings, "INTERNAL_API_TOKEN", None) or "").strip()
            except Exception:
                token = ""
        if not token:
            return {}
        return {"x-internal-api-token": token}

    @classmethod
    async def _request_json(
        cls,
        http_client: Any,
        method: str,
        backend_url: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Any] = None,
    ) -> Dict[str, Any]:
        response = await http_client.request(
            method=method.upper(),
            url=cls._build_url(backend_url, path),
            params=params,
            json=json,
            headers=cls._auth_headers(),
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return {"items": payload}
        return payload

    @classmethod
    def _collecting_result(
        cls,
        session: SkillSession,
        *,
        next_step: Optional[str] = None,
        output: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        session.control.status = SkillStatus.collecting
        if next_step:
            session.step_key = next_step
        return SkillResult(
            success=True,
            next_step=next_step or session.step_key,
            output=output,
            session=session,
        )

    @classmethod
    def _error_result(
        cls,
        session: SkillSession,
        error: str,
    ) -> SkillResult:
        session.control.status = SkillStatus.failed
        session.control.error_message = error
        session.step_key = "failed"
        return SkillResult(success=False, error=error, session=session)

    @classmethod
    @abstractmethod
    async def execute(
        cls,
        session: Optional[SkillSession | Dict[str, Any]],
        backend_url: str,
        http_client: Any,
    ) -> SkillResult:
        raise NotImplementedError


# Update forward references after all models are defined
SkillSession.model_rebuild()
