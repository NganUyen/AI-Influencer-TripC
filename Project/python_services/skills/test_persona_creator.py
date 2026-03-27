from unittest.mock import AsyncMock

import httpx
import pytest

from skills.persona_creator import PersonaCreatorSkill


@pytest.mark.asyncio
async def test_persona_creator_returns_error_result_on_http_failure(monkeypatch):
    session = PersonaCreatorSkill.initial_session()
    session.collected.update(
        {
            "persona_id": "demo-persona",
            "language": "English",
            "voice": "male_friendly",
            "appearance_prompt_or_photo": "young traveler",
        }
    )

    request = httpx.Request("POST", "http://backend/api/personas")
    response = httpx.Response(400, request=request, json={"detail": "persona_id already exists"})

    monkeypatch.setattr(
        PersonaCreatorSkill,
        "_request_json",
        AsyncMock(side_effect=httpx.HTTPStatusError("bad request", request=request, response=response)),
    )

    result = await PersonaCreatorSkill.execute(session, "http://backend", AsyncMock())

    assert result.success is False
    assert result.error == "persona_id already exists"
    assert result.session is not None
    assert result.session.step_key == "failed"


@pytest.mark.asyncio
async def test_persona_creator_resumes_existing_persona_when_create_reports_duplicate(monkeypatch):
    session = PersonaCreatorSkill.initial_session()
    session.artifacts["telegram_chat_id"] = "123456"
    session.collected.update(
        {
            "persona_id": "demo-persona",
            "language": "English",
            "voice": "male_friendly",
            "appearance_prompt_or_photo": "young vietnamese traveler",
        }
    )

    request = httpx.Request("POST", "http://backend/api/personas")
    response = httpx.Response(
        400,
        request=request,
        json={"detail": "Persona 'demo-persona' already exists for this owner."},
    )

    monkeypatch.setattr(
        PersonaCreatorSkill,
        "_request_json",
        AsyncMock(
            side_effect=[
                httpx.HTTPStatusError("duplicate", request=request, response=response),
                {
                    "persona_id": "demo-persona",
                    "display_name": "Demo Persona",
                    "status": "draft",
                    "language": "English",
                    "tts_voice": "en-US-Studio-O",
                    "avatar_image_url": None,
                    "avatar_media_asset_id": None,
                    "avatar_prompt": "young vietnamese traveler",
                    "heygen_avatar_id": None,
                },
                {
                    "url": "https://cdn.example/avatar.png",
                    "media_asset_id": "asset-generated-1",
                },
                {
                    "persona_id": "demo-persona",
                    "display_name": "Demo Persona",
                    "status": "draft",
                    "language": "English",
                    "tts_voice": "en-US-Studio-O",
                    "avatar_image_url": "https://cdn.example/avatar.png",
                    "avatar_media_asset_id": "asset-generated-1",
                    "avatar_source_type": "generated",
                    "avatar_prompt": "young vietnamese traveler",
                    "heygen_avatar_id": None,
                },
            ]
        ),
    )

    result = await PersonaCreatorSkill.execute(session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.session is not None
    assert result.session.artifacts["resumed_existing_persona"] is True
    assert result.session.artifacts["avatar_media_asset_id"] == "asset-generated-1"


@pytest.mark.asyncio
async def test_persona_creator_generates_avatar_when_missing(monkeypatch):
    session = PersonaCreatorSkill.initial_session()
    session.artifacts["telegram_chat_id"] = "123456"
    session.collected.update(
        {
            "persona_id": "demo-persona",
            "language": "English",
            "voice": "male_friendly",
            "appearance_prompt_or_photo": "young vietnamese traveler",
        }
    )

    monkeypatch.setattr(
        PersonaCreatorSkill,
        "_request_json",
        AsyncMock(
            side_effect=[
                {
                    "persona_id": "demo-persona",
                    "display_name": "Demo Persona",
                    "status": "draft",
                    "language": "English",
                    "tts_voice": "en-US-Studio-O",
                    "avatar_image_url": None,
                    "avatar_prompt": "young vietnamese traveler",
                    "heygen_avatar_id": None,
                },
                {
                    "url": "https://cdn.example/avatar.png",
                    "media_asset_id": "asset-generated-1",
                },
                {
                    "persona_id": "demo-persona",
                    "display_name": "Demo Persona",
                    "status": "draft",
                    "language": "English",
                    "tts_voice": "en-US-Studio-O",
                    "avatar_image_url": "https://cdn.example/avatar.png",
                    "avatar_media_asset_id": "asset-generated-1",
                    "avatar_source_type": "generated",
                    "avatar_prompt": "young vietnamese traveler",
                    "heygen_avatar_id": None,
                },
            ]
        ),
    )

    result = await PersonaCreatorSkill.execute(session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.session is not None
    assert result.session.artifacts.get("avatar_image_url") == "https://cdn.example/avatar.png"
    assert result.session.artifacts.get("avatar_media_asset_id") == "asset-generated-1"
    assert result.output.get("preview_image_url") == "https://cdn.example/avatar.png"
    create_payload = PersonaCreatorSkill._request_json.await_args_list[0].kwargs["json"]
    assert create_payload["tts_voice"] == "en-US-Studio-O"
    avatar_generation_payload = PersonaCreatorSkill._request_json.await_args_list[1].kwargs["json"]
    assert avatar_generation_payload["owner_key"] == "telegram:123456"
    assert avatar_generation_payload["persona_id"] == "demo-persona"
    patch_payload = PersonaCreatorSkill._request_json.await_args_list[2].kwargs["json"]
    assert patch_payload["avatar_media_asset_id"] == "asset-generated-1"


@pytest.mark.asyncio
async def test_persona_creator_uses_uploaded_reference_avatar_when_present(monkeypatch):
    session = PersonaCreatorSkill.initial_session()
    session.artifacts["telegram_chat_id"] = "123456"
    session.artifacts["uploaded_reference_image_url"] = "https://storage.example/avatar.png"
    session.artifacts["uploaded_reference_asset_id"] = "asset-123"
    session.collected.update(
        {
            "persona_id": "demo-persona",
            "language": "English",
            "voice": "male_friendly",
            "appearance_prompt_or_photo": "https://storage.example/avatar.png",
        }
    )

    monkeypatch.setattr(
        PersonaCreatorSkill,
        "_request_json",
        AsyncMock(
            side_effect=[
                {
                    "persona_id": "demo-persona",
                    "display_name": "Demo Persona",
                    "status": "draft",
                    "language": "English",
                    "tts_voice": "en-US-Studio-O",
                    "avatar_image_url": None,
                    "avatar_media_asset_id": None,
                    "avatar_prompt": "https://storage.example/avatar.png",
                    "heygen_avatar_id": None,
                },
                {
                    "persona_id": "demo-persona",
                    "display_name": "Demo Persona",
                    "status": "draft",
                    "language": "English",
                    "tts_voice": "en-US-Studio-O",
                    "avatar_image_url": "https://storage.example/avatar.png",
                    "avatar_media_asset_id": "asset-123",
                    "avatar_source_type": "telegram_upload",
                    "avatar_prompt": "https://storage.example/avatar.png",
                    "heygen_avatar_id": None,
                },
            ]
        ),
    )

    result = await PersonaCreatorSkill.execute(session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.session is not None
    assert result.session.artifacts.get("avatar_media_asset_id") == "asset-123"
    assert result.session.artifacts.get("avatar_image_url") == "https://storage.example/avatar.png"
    assert len(PersonaCreatorSkill._request_json.await_args_list) == 2
    create_payload = PersonaCreatorSkill._request_json.await_args_list[0].kwargs["json"]
    assert create_payload["tts_voice"] == "en-US-Studio-O"
    attach_payload = PersonaCreatorSkill._request_json.await_args_list[1].kwargs["json"]
    assert attach_payload["avatar_media_asset_id"] == "asset-123"
    assert attach_payload["avatar_source_type"] == "telegram_upload"


@pytest.mark.asyncio
async def test_persona_creator_force_regenerates_existing_avatar(monkeypatch):
    session = PersonaCreatorSkill.initial_session()
    session.artifacts["telegram_chat_id"] = "123456"
    session.artifacts["force_regenerate_avatar"] = True
    session.collected.update(
        {
            "persona_id": "demo-persona",
            "language": "English",
            "voice": "male_friendly",
            "appearance_prompt_or_photo": "young vietnamese traveler",
        }
    )

    monkeypatch.setattr(
        PersonaCreatorSkill,
        "_request_json",
        AsyncMock(
            side_effect=[
                {
                    "persona_id": "demo-persona",
                    "display_name": "Demo Persona",
                    "status": "draft",
                    "language": "English",
                    "tts_voice": "en-US-Studio-O",
                    "avatar_image_url": "https://cdn.example/old-avatar.png",
                    "avatar_media_asset_id": "asset-old",
                    "avatar_prompt": "young vietnamese traveler",
                    "heygen_avatar_id": None,
                },
                {
                    "url": "https://cdn.example/new-avatar.png",
                    "media_asset_id": "asset-new",
                },
                {
                    "persona_id": "demo-persona",
                    "display_name": "Demo Persona",
                    "status": "draft",
                    "language": "English",
                    "tts_voice": "en-US-Studio-O",
                    "avatar_image_url": "https://cdn.example/new-avatar.png",
                    "avatar_media_asset_id": "asset-new",
                    "avatar_source_type": "generated",
                    "avatar_prompt": "young vietnamese traveler",
                    "heygen_avatar_id": None,
                },
            ]
        ),
    )

    result = await PersonaCreatorSkill.execute(session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.session is not None
    assert result.session.artifacts.get("avatar_image_url") == "https://cdn.example/new-avatar.png"
    assert result.session.artifacts.get("avatar_media_asset_id") == "asset-new"
    assert result.session.artifacts.get("force_regenerate_avatar") is None
    patch_payload = PersonaCreatorSkill._request_json.await_args_list[2].kwargs["json"]
    assert patch_payload["avatar_media_asset_id"] == "asset-new"
