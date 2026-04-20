from unittest.mock import AsyncMock

import pytest

from services import persona_registry_service as persona_registry_service_module
from services.errors import PersonaConfigurationError
from services.persona_registry_service import (
    PersonaRegistryService,
    _SYSTEM_PERSONA_USER_ID,
)


@pytest.fixture(autouse=True)
def stub_reserved_global_persona_list(monkeypatch):
    monkeypatch.setattr(
        PersonaRegistryService,
        "_list_reserved_global_personas_from_db",
        AsyncMock(return_value=[]),
    )


@pytest.mark.asyncio
async def test_list_personas_falls_back_to_legacy_system_scope_for_owner_key(monkeypatch):
    synthetic_owner_id = "53fd56c6-ae1d-51fb-bc5b-706032e24226"

    async def fake_resolve_owner_user_id(*, user_id=None, owner_key=None):
        assert owner_key == "telegram:1972936401"
        return synthetic_owner_id

    async def fake_list_from_db(*, user_id, status=None):
        if user_id == synthetic_owner_id:
            return []
        if user_id == _SYSTEM_PERSONA_USER_ID:
            return [{"persona_id": "legacy-demo", "status": "ready"}]
        return []

    monkeypatch.setattr(
        PersonaRegistryService,
        "_resolve_owner_user_id",
        fake_resolve_owner_user_id,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_list_from_db",
        fake_list_from_db,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_list_unowned_from_db",
        AsyncMock(return_value=[]),
    )

    personas = await PersonaRegistryService.list_personas(owner_key="telegram:1972936401")

    assert personas == [{"persona_id": "legacy-demo", "status": "ready"}]


@pytest.mark.asyncio
async def test_list_personas_merges_user_and_system_personas_for_explicit_user_id(
    monkeypatch,
):
    resolved_user_id = "550e8400-e29b-41d4-a716-446655440000"
    list_calls = []

    async def fake_resolve_owner_user_id(*, user_id=None, owner_key=None):
        assert user_id == resolved_user_id
        assert owner_key is None
        return resolved_user_id

    async def fake_list_from_db(*, user_id, status=None):
        list_calls.append(user_id)
        if user_id == resolved_user_id:
            return [{"persona_id": "custom-hero", "status": "ready"}]
        if user_id == _SYSTEM_PERSONA_USER_ID:
            return [{"persona_id": "global-mx-valeria", "status": "draft"}]
        return []

    monkeypatch.setattr(
        PersonaRegistryService,
        "_resolve_owner_user_id",
        fake_resolve_owner_user_id,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_list_from_db",
        fake_list_from_db,
    )

    personas = await PersonaRegistryService.list_personas(user_id=resolved_user_id)

    assert personas == [
        {"persona_id": "custom-hero", "status": "ready"},
        {"persona_id": "global-mx-valeria", "status": "draft"},
    ]
    assert list_calls == [resolved_user_id, _SYSTEM_PERSONA_USER_ID]


@pytest.mark.asyncio
async def test_list_personas_appends_reserved_global_personas_even_if_owner_drifted(
    monkeypatch,
):
    resolved_user_id = "550e8400-e29b-41d4-a716-446655440000"

    async def fake_resolve_owner_user_id(*, user_id=None, owner_key=None):
        assert user_id == resolved_user_id
        return resolved_user_id

    async def fake_list_from_db(*, user_id, status=None):
        if user_id == resolved_user_id:
            return [{"persona_id": "custom-hero", "status": "ready", "user_id": resolved_user_id}]
        if user_id == _SYSTEM_PERSONA_USER_ID:
            return [{"persona_id": "global-us-alex", "status": "ready", "user_id": _SYSTEM_PERSONA_USER_ID}]
        return []

    async def fake_list_reserved_global_personas_from_db(*, status=None):
        return [
            {
                "persona_id": "global-cn-wei",
                "status": "ready",
                "user_id": "ecfafcde-45c3-5a00-9711-34246e451cf7",
            }
        ]

    monkeypatch.setattr(
        PersonaRegistryService,
        "_resolve_owner_user_id",
        fake_resolve_owner_user_id,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_list_from_db",
        fake_list_from_db,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_list_reserved_global_personas_from_db",
        fake_list_reserved_global_personas_from_db,
    )

    personas = await PersonaRegistryService.list_personas(user_id=resolved_user_id)

    assert [item["persona_id"] for item in personas] == [
        "custom-hero",
        "global-us-alex",
        "global-cn-wei",
    ]


@pytest.mark.asyncio
async def test_list_personas_falls_back_to_unowned_legacy_scope_for_owner_key(monkeypatch):
    synthetic_owner_id = "53fd56c6-ae1d-51fb-bc5b-706032e24226"

    async def fake_resolve_owner_user_id(*, user_id=None, owner_key=None):
        return synthetic_owner_id

    async def fake_list_from_db(*, user_id, status=None):
        assert status is None
        return []

    async def fake_list_unowned_from_db(*, status=None):
        assert status is None
        return [{"persona_id": "legacy-unowned", "status": "draft"}]

    monkeypatch.setattr(
        PersonaRegistryService,
        "_resolve_owner_user_id",
        fake_resolve_owner_user_id,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_list_from_db",
        fake_list_from_db,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_list_unowned_from_db",
        fake_list_unowned_from_db,
    )

    personas = await PersonaRegistryService.list_personas(owner_key="telegram:1972936401")

    assert personas == [{"persona_id": "legacy-unowned", "status": "draft"}]


@pytest.mark.asyncio
async def test_get_persona_falls_back_to_system_scope_for_explicit_user_id(monkeypatch):
    resolved_user_id = "550e8400-e29b-41d4-a716-446655440000"
    get_calls = []

    async def fake_resolve_owner_user_id(*, user_id=None, owner_key=None):
        assert user_id == resolved_user_id
        assert owner_key is None
        return resolved_user_id

    async def fake_get_from_db(persona_id, *, user_id):
        get_calls.append((persona_id, user_id))
        if user_id == _SYSTEM_PERSONA_USER_ID:
            return {"persona_id": persona_id, "status": "draft"}
        return None

    monkeypatch.setattr(
        PersonaRegistryService,
        "_resolve_owner_user_id",
        fake_resolve_owner_user_id,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_get_from_db",
        fake_get_from_db,
    )

    persona = await PersonaRegistryService.get_persona(
        "global-mx-valeria",
        user_id=resolved_user_id,
    )

    assert persona == {"persona_id": "global-mx-valeria", "status": "draft"}
    assert get_calls == [
        ("global-mx-valeria", resolved_user_id),
        ("global-mx-valeria", _SYSTEM_PERSONA_USER_ID),
    ]


@pytest.mark.asyncio
async def test_get_persona_falls_back_to_reserved_global_match_when_system_owner_missing(
    monkeypatch,
):
    resolved_user_id = "550e8400-e29b-41d4-a716-446655440000"

    async def fake_resolve_owner_user_id(*, user_id=None, owner_key=None):
        assert user_id == resolved_user_id
        return resolved_user_id

    async def fake_get_from_db(persona_id, *, user_id):
        return None

    async def fake_find_personas_by_id_global(persona_id):
        assert persona_id == "global-cn-wei"
        return [
            {
                "persona_id": "global-cn-wei",
                "status": "ready",
                "user_id": "ecfafcde-45c3-5a00-9711-34246e451cf7",
            }
        ]

    monkeypatch.setattr(
        PersonaRegistryService,
        "_resolve_owner_user_id",
        fake_resolve_owner_user_id,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_get_from_db",
        fake_get_from_db,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_find_personas_by_id_global",
        fake_find_personas_by_id_global,
    )

    persona = await PersonaRegistryService.get_persona(
        "global-cn-wei",
        user_id=resolved_user_id,
    )

    assert persona == {
        "persona_id": "global-cn-wei",
        "status": "ready",
        "user_id": "ecfafcde-45c3-5a00-9711-34246e451cf7",
    }


@pytest.mark.asyncio
async def test_update_persona_falls_back_to_legacy_system_scope_for_owner_key(monkeypatch):
    synthetic_owner_id = "53fd56c6-ae1d-51fb-bc5b-706032e24226"

    async def fake_resolve_owner_user_id(*, user_id=None, owner_key=None):
        return synthetic_owner_id

    update_calls = []

    async def fake_update_in_db(persona_id, fields, *, user_id):
        update_calls.append((persona_id, user_id, fields))
        if user_id == synthetic_owner_id:
            return None
        if user_id == _SYSTEM_PERSONA_USER_ID:
            return {"persona_id": persona_id, **fields}
        return None

    monkeypatch.setattr(
        PersonaRegistryService,
        "_resolve_owner_user_id",
        fake_resolve_owner_user_id,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_update_in_db",
        fake_update_in_db,
    )

    persona = await PersonaRegistryService.update_persona(
        "legacy-demo",
        {"status": "ready"},
        owner_key="telegram:1972936401",
    )

    assert persona == {"persona_id": "legacy-demo", "status": "ready"}
    assert update_calls[0][1] == synthetic_owner_id
    assert update_calls[1][1] == _SYSTEM_PERSONA_USER_ID


@pytest.mark.asyncio
async def test_resolve_owner_user_id_requires_real_owner_in_production(monkeypatch):
    monkeypatch.setattr(persona_registry_service_module.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(persona_registry_service_module.settings, "DEBUG", False)
    monkeypatch.setattr(
        "services.persona_registry_service.TelegramLinkService.resolve_user_id_for_owner_key",
        AsyncMock(return_value=None),
    )

    with pytest.raises(PersonaConfigurationError) as exc_info:
        await PersonaRegistryService._resolve_owner_user_id(owner_key="telegram:1972936401")

    assert "not linked" in str(exc_info.value)


@pytest.mark.asyncio
async def test_list_personas_skips_legacy_scope_in_production(monkeypatch):
    resolved_user_id = "550e8400-e29b-41d4-a716-446655440000"

    async def fake_resolve_owner_user_id(*, user_id=None, owner_key=None):
        assert owner_key == "telegram:1972936401"
        return resolved_user_id

    async def fake_list_from_db(*, user_id, status=None):
        assert user_id == resolved_user_id
        return []

    async def fail_list_unowned_from_db(*, status=None):
        raise AssertionError("legacy unowned fallback should be disabled in production")

    monkeypatch.setattr(persona_registry_service_module.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(persona_registry_service_module.settings, "DEBUG", False)
    monkeypatch.setattr(
        PersonaRegistryService,
        "_resolve_owner_user_id",
        fake_resolve_owner_user_id,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_list_from_db",
        fake_list_from_db,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_list_unowned_from_db",
        fail_list_unowned_from_db,
    )

    personas = await PersonaRegistryService.list_personas(owner_key="telegram:1972936401")

    assert personas == []


@pytest.mark.asyncio
async def test_create_persona_recovers_unowned_legacy_duplicate(monkeypatch):
    synthetic_owner_id = "53fd56c6-ae1d-51fb-bc5b-706032e24226"

    async def fake_resolve_owner_user_id(*, user_id=None, owner_key=None):
        return synthetic_owner_id

    async def fake_ensure_owner_user_row(user_id, owner_key):
        assert user_id == synthetic_owner_id
        assert owner_key == "telegram:1972936401"

    async def fake_get_from_db(persona_id, *, user_id):
        return None

    async def fake_get_unowned_from_db(persona_id):
        assert persona_id == "ni"
        return None

    async def fake_create_in_db(payload):
        raise RuntimeError("duplicate key value violates unique constraint")

    async def fake_recover_duplicate_persona(persona_id, *, candidate_user_ids, include_unowned):
        assert persona_id == "ni"
        assert candidate_user_ids == [synthetic_owner_id, _SYSTEM_PERSONA_USER_ID]
        assert include_unowned is True
        return (
            {
                "persona_id": "ni",
                "user_id": None,
                "status": "draft",
            },
            {
                "persona_id": "ni",
                "user_id": None,
                "status": "draft",
            },
        )

    monkeypatch.setattr(
        PersonaRegistryService,
        "_resolve_owner_user_id",
        fake_resolve_owner_user_id,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_ensure_owner_user_row",
        fake_ensure_owner_user_row,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_get_from_db",
        fake_get_from_db,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_get_unowned_from_db",
        fake_get_unowned_from_db,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_create_in_db",
        fake_create_in_db,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_recover_duplicate_persona",
        fake_recover_duplicate_persona,
    )

    persona = await PersonaRegistryService.create_persona(
        {
            "persona_id": "ni",
            "display_name": "Ni",
            "language": "English",
            "tts_voice": "male_friendly",
            "owner_key": "telegram:1972936401",
        }
    )

    assert persona == {
        "persona_id": "ni",
        "user_id": None,
        "status": "draft",
    }


@pytest.mark.asyncio
async def test_create_persona_reports_legacy_global_index_conflict(monkeypatch):
    synthetic_owner_id = "53fd56c6-ae1d-51fb-bc5b-706032e24226"
    other_owner_id = "11111111-1111-1111-1111-111111111111"

    async def fake_resolve_owner_user_id(*, user_id=None, owner_key=None):
        return synthetic_owner_id

    async def fake_ensure_owner_user_row(user_id, owner_key):
        return None

    async def fake_get_from_db(persona_id, *, user_id):
        return None

    async def fake_get_unowned_from_db(persona_id):
        return None

    async def fake_create_in_db(payload):
        raise RuntimeError("duplicate key value violates unique constraint")

    async def fake_recover_duplicate_persona(persona_id, *, candidate_user_ids, include_unowned):
        return (
            None,
            {
                "persona_id": "ni",
                "user_id": other_owner_id,
                "status": "draft",
            },
        )

    monkeypatch.setattr(
        PersonaRegistryService,
        "_resolve_owner_user_id",
        fake_resolve_owner_user_id,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_ensure_owner_user_row",
        fake_ensure_owner_user_row,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_get_from_db",
        fake_get_from_db,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_get_unowned_from_db",
        fake_get_unowned_from_db,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_create_in_db",
        fake_create_in_db,
    )
    monkeypatch.setattr(
        PersonaRegistryService,
        "_recover_duplicate_persona",
        fake_recover_duplicate_persona,
    )

    with pytest.raises(PersonaConfigurationError) as exc_info:
        await PersonaRegistryService.create_persona(
            {
                "persona_id": "ni",
                "display_name": "Ni",
                "language": "English",
                "tts_voice": "male_friendly",
                "owner_key": "telegram:1972936401",
            }
        )

    assert "legacy global persona index" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_persona_rejects_reserved_global_ids_for_non_system_owner(monkeypatch):
    synthetic_owner_id = "53fd56c6-ae1d-51fb-bc5b-706032e24226"

    async def fake_resolve_owner_user_id(*, user_id=None, owner_key=None):
        assert user_id == synthetic_owner_id
        return synthetic_owner_id

    monkeypatch.setattr(
        PersonaRegistryService,
        "_resolve_owner_user_id",
        fake_resolve_owner_user_id,
    )

    with pytest.raises(PersonaConfigurationError) as exc_info:
        await PersonaRegistryService.create_persona(
            {
                "persona_id": "global-cn-wei",
                "display_name": "Wei Chen",
                "language": "Mandarin",
                "tts_voice": "cmn-CN-Standard-B",
                "user_id": synthetic_owner_id,
            }
        )

    assert "reserved for system personas" in str(exc_info.value)
