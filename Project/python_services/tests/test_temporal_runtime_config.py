import sys
import types
from types import SimpleNamespace

import pytest

pil_mod = types.ModuleType("PIL")
pil_mod.Image = object
pil_mod.ImageDraw = object
pil_mod.ImageFont = object
sys.modules.setdefault("PIL", pil_mod)
sys.modules.setdefault("PIL.Image", types.ModuleType("PIL.Image"))
sys.modules.setdefault("PIL.ImageDraw", types.ModuleType("PIL.ImageDraw"))
sys.modules.setdefault("PIL.ImageFont", types.ModuleType("PIL.ImageFont"))

import main
from api import workflows
from config import settings as settings_module


def test_resolve_temporal_address_rewrites_docker_alias_for_host_runtime():
    assert (
        settings_module.resolve_temporal_address_for_runtime(
            "temporal:7233",
            running_in_container=False,
        )
        == "localhost:7233"
    )


def test_resolve_temporal_address_keeps_docker_alias_in_container():
    assert (
        settings_module.resolve_temporal_address_for_runtime(
            "temporal:7233",
            running_in_container=True,
        )
        == "temporal:7233"
    )


@pytest.mark.asyncio
async def test_workflow_client_uses_effective_temporal_address(monkeypatch):
    captured = {}

    async def fake_connect(address, namespace):
        captured["address"] = address
        captured["namespace"] = namespace
        return object()

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    monkeypatch.setattr(settings_module, "_is_running_inside_docker", lambda: False)
    monkeypatch.setattr(workflows.Client, "connect", fake_connect)
    monkeypatch.setattr(workflows.settings, "TEMPORAL_ADDRESS", "temporal:7233")

    await workflows.get_temporal_client(request)

    assert captured["address"] == "localhost:7233"
    assert captured["namespace"] == workflows.settings.TEMPORAL_NAMESPACE


@pytest.mark.asyncio
async def test_health_check_reports_degraded_when_temporal_disconnected(monkeypatch):
    monkeypatch.setattr(settings_module, "_is_running_inside_docker", lambda: False)
    monkeypatch.setattr(main.settings, "TEMPORAL_ADDRESS", "temporal:7233")
    monkeypatch.setattr(main, "temporal_client", None)

    payload = await main.health_check()

    assert payload["status"] == "degraded"
    assert payload["temporal"] == "disconnected"
    assert payload["temporal_address_effective"] == "localhost:7233"
