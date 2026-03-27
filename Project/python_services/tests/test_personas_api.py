import pytest

from api import personas


@pytest.mark.asyncio
async def test_list_personas_passes_owner_scope(monkeypatch):
    captured = {}

    async def fake_list_personas(status=None, user_id=None, owner_key=None):
        captured["status"] = status
        captured["user_id"] = user_id
        captured["owner_key"] = owner_key
        return []

    monkeypatch.setattr(personas.PersonaRegistryService, "list_personas", fake_list_personas)

    response = await personas.list_personas(status="ready", user_id=None, owner_key="telegram:123")

    assert response == []
    assert captured == {
        "status": "ready",
        "user_id": None,
        "owner_key": "telegram:123",
    }


@pytest.mark.asyncio
async def test_create_persona_passes_owner_fields(monkeypatch):
    captured = {}

    async def fake_create_persona(payload):
        captured.update(payload)
        return {"persona_id": payload["persona_id"], "user_id": "u"}

    monkeypatch.setattr(personas.PersonaRegistryService, "create_persona", fake_create_persona)

    payload = personas.CreatePersonaRequest(
        persona_id="demo",
        display_name="Demo",
        language="English",
        tts_voice="male_friendly",
        owner_key="telegram:123",
    )

    result = await personas.create_persona(payload)

    assert result["persona_id"] == "demo"
    assert captured["owner_key"] == "telegram:123"


@pytest.mark.asyncio
async def test_get_persona_passes_owner_scope(monkeypatch):
    captured = {}

    async def fake_get_persona(persona_id, user_id=None, owner_key=None):
        captured["persona_id"] = persona_id
        captured["user_id"] = user_id
        captured["owner_key"] = owner_key
        return {"persona_id": persona_id}

    monkeypatch.setattr(personas.PersonaRegistryService, "get_persona", fake_get_persona)

    result = await personas.get_persona("demo", user_id=None, owner_key="telegram:123")

    assert result["persona_id"] == "demo"
    assert captured == {
        "persona_id": "demo",
        "user_id": None,
        "owner_key": "telegram:123",
    }


@pytest.mark.asyncio
async def test_update_persona_passes_owner_scope(monkeypatch):
    captured = {}

    async def fake_update_persona(persona_id, fields, user_id=None, owner_key=None):
        captured["persona_id"] = persona_id
        captured["fields"] = fields
        captured["user_id"] = user_id
        captured["owner_key"] = owner_key
        return {"persona_id": persona_id, **fields}

    monkeypatch.setattr(personas.PersonaRegistryService, "update_persona", fake_update_persona)

    payload = personas.UpdatePersonaRequest(status="ready")
    result = await personas.update_persona("demo", payload, owner_key="telegram:123")

    assert result["status"] == "ready"
    assert captured["owner_key"] == "telegram:123"


@pytest.mark.asyncio
async def test_readiness_passes_owner_scope(monkeypatch):
    captured = {}

    async def fake_get_readiness(persona_id, user_id=None, owner_key=None):
        captured["persona_id"] = persona_id
        captured["user_id"] = user_id
        captured["owner_key"] = owner_key
        return {"persona_id": persona_id, "ready": True}

    monkeypatch.setattr(personas.PersonaRegistryService, "get_readiness", fake_get_readiness)

    result = await personas.get_persona_readiness("demo", owner_key="telegram:123")

    assert result["ready"] is True
    assert captured["owner_key"] == "telegram:123"
