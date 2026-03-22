"""Lightweight access to the OpenClaw skill registry without importing agents."""

from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any, Dict


@lru_cache(maxsize=1)
def _load_registry_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "agents" / "openclaw_telegram_skill_configs.py"
    spec = importlib.util.spec_from_file_location(
        "openclaw_telegram_skill_configs_raw",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load OpenClaw skill registry from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_skill_definition(skill_name: str) -> Dict[str, Any]:
    module = _load_registry_module()
    getter = getattr(module, "get_openclaw_telegram_skill")
    return getter(skill_name)
