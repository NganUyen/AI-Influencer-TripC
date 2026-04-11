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
    assert result.session.artifacts.get("avatar_media_asset_id") == "asset-123"
    assert result.session.artifacts.get("avatar_image_url") == "https://storage.example/avatar.png"
    assert len(PersonaCreatorSkill._request_json.await_args_list) == 2
    create_payload = PersonaCreatorSkill._request_json.await_args_list[0].kwargs["json"]
    assert create_payload["tts_voice"] == "en-US-Studio-O"
    attach_payload = PersonaCreatorSkill._request_json.await_args_list[1].kwargs["json"]
    assert attach_payload["avatar_media_asset_id"] == "asset-123"
    assert attach_payload["avatar_source_type"] == "telegram_upload"
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
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
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
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
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
    assert avatar_generation_payload["user_id"] == "550e8400-e29b-41d4-a716-446655440000"
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


def test_avatar_prompt_preserves_requested_identity_markers():
    prompt = PersonaCreatorSkill._build_avatar_prompt(
        "Jamaican fintech founder in Kingston, dark skin, locs, tailored navy blazer",
        simplified=True,
    )

    assert "Preserve the requested ethnicity, nationality" in prompt
    assert "Do not default to a generic white English-speaking influencer" in prompt
    assert "Jamaican fintech founder" in prompt


def test_dream_fallback_avoids_generic_western_defaulting():
    result = PersonaCreatorSkill._dream_persona_details_fallback(
        "Vietnamese",
        "young street-food creator in Ho Chi Minh City",
        reason="offline",
    )

    assert result["display_name"] == "Vietnamese Creator"
    assert "Do not genericize into a default Western or white influencer look" in result["appearance"]


@pytest.mark.asyncio
async def test_persona_creator_retries_avatar_with_simplified_prompt(monkeypatch):
    session = PersonaCreatorSkill.initial_session()
    session.artifacts["telegram_chat_id"] = "123456"
    session.collected.update(
        {
            "persona_id": "demo-persona",
            "language": "English",
            "voice": "male_friendly",
            "appearance_prompt_or_photo": "Tall creator\nhttps://example.com/ref\nwith *green* jacket and travel vibe",
        }
    )

    request = httpx.Request("POST", "http://backend/api/media/generate/image")
    response = httpx.Response(
        422,
        request=request,
        json={"detail": "Prompt was rejected by the image provider."},
    )

    monkeypatch.setattr(
        PersonaCreatorSkill,
        "_request_json",
        AsyncMock(
            side_effect=[
                {
                    "persona_id": "demo-persona",
                    "display_name": "Demo Persona",
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "status": "draft",
                    "language": "English",
                    "tts_voice": "en-US-Studio-O",
                    "avatar_image_url": None,
                    "avatar_prompt": "Tall creator\nhttps://example.com/ref\nwith *green* jacket and travel vibe",
                    "heygen_avatar_id": None,
                },
                httpx.HTTPStatusError("invalid prompt", request=request, response=response),
                {
                    "url": "https://cdn.example/avatar.png",
                    "media_asset_id": "asset-generated-1",
                },
                {
                    "persona_id": "demo-persona",
                    "display_name": "Demo Persona",
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "status": "draft",
                    "language": "English",
                    "tts_voice": "en-US-Studio-O",
                    "avatar_image_url": "https://cdn.example/avatar.png",
                    "avatar_media_asset_id": "asset-generated-1",
                    "avatar_source_type": "generated",
                    "avatar_prompt": "Tall creator",
                    "heygen_avatar_id": None,
                },
            ]
        ),
    )

    result = await PersonaCreatorSkill.execute(session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.session is not None
    assert PersonaCreatorSkill._request_json.await_count == 4
    first_avatar_payload = PersonaCreatorSkill._request_json.await_args_list[1].kwargs["json"]
    retry_avatar_payload = PersonaCreatorSkill._request_json.await_args_list[2].kwargs["json"]
    assert first_avatar_payload["prompt"] != retry_avatar_payload["prompt"]
    assert "https://example.com" not in retry_avatar_payload["prompt"]
    assert "*" not in retry_avatar_payload["prompt"]
    assert retry_avatar_payload["metadata"]["retry_strategy"] == "simplified_prompt"


@pytest.mark.asyncio
async def test_persona_creator_surfaces_retry_failure_detail(monkeypatch):
    session = PersonaCreatorSkill.initial_session()
    session.artifacts["telegram_chat_id"] = "123456"
    session.collected.update(
        {
            "persona_id": "demo-persona",
            "language": "English",
            "voice": "male_friendly",
            "appearance_prompt_or_photo": "creator portrait request",
        }
    )

    request = httpx.Request("POST", "http://backend/api/media/generate/image")
    first_response = httpx.Response(
        422,
        request=request,
        json={"detail": "Prompt was rejected by the image provider."},
    )
    retry_response = httpx.Response(
        422,
        request=request,
        json={"detail": "The simplified avatar prompt was also rejected."},
    )

    monkeypatch.setattr(
        PersonaCreatorSkill,
        "_request_json",
        AsyncMock(
            side_effect=[
                {
                    "persona_id": "demo-persona",
                    "display_name": "Demo Persona",
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "status": "draft",
                    "language": "English",
                    "tts_voice": "en-US-Studio-O",
                    "avatar_image_url": None,
                    "avatar_prompt": "creator portrait request",
                    "heygen_avatar_id": None,
                },
                httpx.HTTPStatusError("invalid prompt", request=request, response=first_response),
                httpx.HTTPStatusError("invalid retry prompt", request=request, response=retry_response),
            ]
        ),
    )

    result = await PersonaCreatorSkill.execute(session, "http://backend", AsyncMock())

    assert result.success is False
    assert result.error is not None
    assert "The simplified avatar prompt was also rejected." in result.error
    assert result.session is not None
    assert result.session.step_key == "failed"
    assert PersonaCreatorSkill._request_json.await_count == 3
    first_avatar_payload = PersonaCreatorSkill._request_json.await_args_list[1].kwargs["json"]
    retry_avatar_payload = PersonaCreatorSkill._request_json.await_args_list[2].kwargs["json"]
    assert first_avatar_payload["prompt"] != retry_avatar_payload["prompt"]


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


@pytest.mark.asyncio
async def test_persona_creator_dream_confirm_reuses_early_avatar(monkeypatch):
    session = PersonaCreatorSkill.initial_session()
    session.artifacts["telegram_chat_id"] = "123456"
    session.artifacts["dream_ready"] = True
    session.artifacts["avatar_image_url"] = "https://cdn.example/early-avatar.png"
    session.artifacts["preview_image_url"] = "https://cdn.example/early-avatar.png"
    session.artifacts["avatar_media_asset_id"] = "asset-early"
    session.step_key = "confirm_dream"
    session.collected.update(
        {
            "creation_mode": "dream",
            "dream_confirmed": "confirm",
            "nationality": "Chinese",
            "dream_brief": "A vet with his dog",
            "persona_id": "li_wei_vet",
            "display_name": "Li Wei",
            "language": "English",
            "voice": "male_friendly",
            "appearance_prompt_or_photo": "A realistic Chinese male veterinarian standing with his dog.",
        }
    )

    monkeypatch.setattr(
        PersonaCreatorSkill,
        "_request_json",
        AsyncMock(
            side_effect=[
                {
                    "persona_id": "li_wei_vet",
                    "display_name": "Li Wei",
                    "status": "draft",
                    "language": "English",
                    "tts_voice": "en-US-Studio-O",
                    "avatar_image_url": None,
                    "avatar_media_asset_id": None,
                    "avatar_prompt": "A realistic Chinese male veterinarian standing with his dog.",
                    "heygen_avatar_id": None,
                },
                {
                    "persona_id": "li_wei_vet",
                    "display_name": "Li Wei",
                    "status": "draft",
                    "language": "English",
                    "tts_voice": "en-US-Studio-O",
                    "avatar_image_url": "https://cdn.example/early-avatar.png",
                    "avatar_media_asset_id": "asset-early",
                    "avatar_source_type": "generated",
                    "avatar_prompt": "A realistic Chinese male veterinarian standing with his dog.",
                    "heygen_avatar_id": None,
                },
            ]
        ),
    )

    result = await PersonaCreatorSkill.execute(session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.session is not None
    assert result.session.artifacts.get("avatar_image_url") == "https://cdn.example/early-avatar.png"
    assert result.session.artifacts.get("avatar_media_asset_id") == "asset-early"
    request_paths = [call.args[3] for call in PersonaCreatorSkill._request_json.await_args_list]
    assert "/api/media/generate/image" not in request_paths
