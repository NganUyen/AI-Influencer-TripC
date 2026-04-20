from __future__ import annotations

from typing import Any, Dict, List

import pytest

from services import app_review_studio_service as studio_module
from services.app_review_studio_service import AppReviewStudioService
from services.contracts import WebPageReviewContract
from services.customer_auth_service import CustomerSession


def _session() -> CustomerSession:
    return CustomerSession(
        user_id="00000000-0000-0000-0000-000000000123",
        email="founder@example.com",
        display_name="Founder",
        avatar_url=None,
        access_token="token",
        raw_user={},
    )


def _page_review(**overrides: Any) -> WebPageReviewContract:
    payload = {
        "target_url": "https://example.com/app",
        "normalized_url": "https://example.com/app",
        "page_title": "Example App",
        "product_summary": "Example summary",
        "access_level": "public_page_only",
        "login_required": False,
        "visible_features": [
            {
                "label": "Dashboard",
                "summary": "Main analytics dashboard",
                "evidence": ["Analytics visible above the fold"],
                "source_url": "https://example.com/app",
            }
        ],
        "risks": ["Some flows may change during rollout."],
        "assumptions": ["Homepage reflects current product."],
    }
    payload.update(overrides)
    return WebPageReviewContract.model_validate(payload)


@pytest.mark.asyncio
async def test_get_setup_uses_canonical_system_and_customer_persona_split(
    monkeypatch,
):
    async def fake_list_personas(*, user_id):
        assert user_id == _session().user_id
        return [
            {
                "user_id": _session().user_id,
                "persona_id": "custom-hero",
                "display_name": "Custom Hero",
                "language": "English",
                "status": "ready",
            },
            {
                "user_id": AppReviewStudioService.SYSTEM_PERSONA_USER_ID,
                "persona_id": "global-us-alex",
                "display_name": "Alex Rivera",
                "language": "English (US)",
                "status": "draft",
            },
        ]

    async def fake_list_accounts(_user_id):
        return []

    async def fake_get_link_for_user(_user_id):
        return None

    monkeypatch.setattr(
        studio_module.PersonaRegistryService,
        "list_personas",
        fake_list_personas,
    )
    monkeypatch.setattr(
        studio_module.AccountConnectionService,
        "list_accounts",
        fake_list_accounts,
    )
    monkeypatch.setattr(
        studio_module.TelegramLinkService,
        "get_link_for_user",
        fake_get_link_for_user,
    )

    payload = await AppReviewStudioService.get_setup(user_id=_session().user_id)

    assert [item["persona_id"] for item in payload["persona_options"]] == [
        "global-us-alex"
    ]
    assert payload["persona_options"][0]["is_preset_catalog"] is True
    assert [item["persona_id"] for item in payload["custom_personas"]] == [
        "custom-hero"
    ]


@pytest.mark.asyncio
async def test_get_setup_treats_reserved_global_ids_as_system_when_owner_drifted(
    monkeypatch,
):
    async def fake_list_personas(*, user_id):
        assert user_id == _session().user_id
        return [
            {
                "user_id": _session().user_id,
                "persona_id": "custom-hero",
                "display_name": "Custom Hero",
                "language": "English",
                "status": "ready",
            },
            {
                "user_id": _session().user_id,
                "persona_id": "global-cn-wei",
                "display_name": "Wei Chen",
                "language": "Mandarin",
                "status": "ready",
            },
        ]

    async def fake_list_accounts(_user_id):
        return []

    async def fake_get_link_for_user(_user_id):
        return None

    monkeypatch.setattr(
        studio_module.PersonaRegistryService,
        "list_personas",
        fake_list_personas,
    )
    monkeypatch.setattr(
        studio_module.AccountConnectionService,
        "list_accounts",
        fake_list_accounts,
    )
    monkeypatch.setattr(
        studio_module.TelegramLinkService,
        "get_link_for_user",
        fake_get_link_for_user,
    )

    payload = await AppReviewStudioService.get_setup(user_id=_session().user_id)

    assert [item["persona_id"] for item in payload["persona_options"]] == [
        "global-cn-wei"
    ]
    assert payload["persona_options"][0]["is_preset_catalog"] is True
    assert [item["persona_id"] for item in payload["custom_personas"]] == [
        "custom-hero"
    ]


@pytest.mark.asyncio
async def test_create_jobs_user_upload_persists_plan_state(monkeypatch):
    recorded_plan_payloads: List[Dict[str, Any]] = []

    async def fake_get_link(_user_id):
        return None

    async def fake_list_accounts(_user_id):
        return []

    async def fake_get_brand(_user_id):
        return None

    async def fake_review_url(*, url, objective=None, user_id=None):
        assert url == "https://example.com/app"
        assert objective == "Review product"
        assert user_id == _session().user_id
        return _page_review()

    async def fake_resolve_persona(*, persona_id, user_id):
        assert persona_id == "persona-1"
        assert user_id == _session().user_id
        return {
            "persona_id": "persona-1",
            "display_name": "Ava",
            "language": "English",
            "tts_voice": "en-US-Standard-F",
        }

    async def fake_create_plan(payload):
        recorded_plan_payloads.append(payload)
        return {
            "id": "plan-1",
            "user_id": payload["user_id"],
            "campaign_id": payload.get("campaign_id"),
            "persona_id": payload["persona_id"],
            "source_url": payload["source_url"],
            "objective": payload["objective"],
            "script_text": payload["script_text"],
            "scenes_data": payload["scenes_data"],
            "duration_estimate": payload["duration_estimate"],
            "status": payload["status"],
            "workflow_id": None,
            "video_url": None,
            "publish_settings": payload["publish_settings"],
            "creative_preferences": payload["creative_preferences"],
            "page_review_data": payload["page_review_data"],
            "created_at": "2026-04-18T00:00:00Z",
            "updated_at": "2026-04-18T00:00:00Z",
            "approved_at": None,
        }

    async def fake_generate_script(*args, **kwargs):
        return (
            type("Script", (), {"model_dump": lambda self, mode=None: {"script": "English master", "scenes": [], "duration_estimate": 12}})(),
            None,
        )

    monkeypatch.setattr(
        "services.app_review_studio_service.TelegramLinkService.get_link_for_user",
        fake_get_link,
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.AccountConnectionService.list_accounts",
        fake_list_accounts,
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.BrandProfileService.get_for_user",
        fake_get_brand,
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.WebsiteReviewService.review_url",
        fake_review_url,
    )
    monkeypatch.setattr(
        AppReviewStudioService,
        "_resolve_persona",
        classmethod(lambda cls, *, persona_id, user_id: fake_resolve_persona(persona_id=persona_id, user_id=user_id)),
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.VideoPlanningService.create_plan",
        fake_create_plan,
    )
    monkeypatch.setattr(
        "services.script_service.ScriptService.generate_script_from_review_plan",
        fake_generate_script,
    )

    result = await AppReviewStudioService.create_jobs(
        session=_session(),
        payload={
            "source_url": "https://example.com/app",
            "objective": "Review product",
            "target_personas": ["persona-1"],
            "input_mode": "user_upload",
            "creative_preferences": {"hook_style": "bold"},
        },
        temporal_client=None,
    )

    assert result["jobs"][0]["status"] == "upload_required"
    assert result["jobs"][0]["plan_id"] == "plan-1"
    assert result["jobs"][0]["input_mode"] == "user_upload"
    assert result["master_contract"]["language"] == "English"
    assert recorded_plan_payloads[0]["persona_id"] == "persona-1"
    assert recorded_plan_payloads[0]["status"] == "upload_required"
    assert recorded_plan_payloads[0]["publish_settings"]["input_mode"] == "user_upload"
    assert recorded_plan_payloads[0]["publish_settings"]["shared_contract"]["language"] == "English"
    assert recorded_plan_payloads[0]["creative_preferences"] == {"hook_style": "bold"}
    assert (
        recorded_plan_payloads[0]["page_review_data"]["normalized_url"]
        == "https://example.com/app"
    )


@pytest.mark.asyncio
async def test_create_jobs_ai_script_failure_does_not_create_plan(monkeypatch):
    async def fake_get_link(_user_id):
        return None

    async def fake_list_accounts(_user_id):
        return []

    async def fake_get_brand(_user_id):
        return None

    async def fake_review_url(*, url, objective=None, user_id=None):
        return _page_review()

    async def fake_resolve_persona(*, persona_id, user_id):
        return {
            "persona_id": persona_id,
            "display_name": "Ava",
            "language": "English",
            "tts_voice": "en-US-Standard-F",
        }

    async def fail_create_plan(_payload):
        raise AssertionError("plan should not be created on autonomous script failure")

    async def fake_generate_script(*args, **kwargs):
        raise RuntimeError("openai offline")

    monkeypatch.setattr(
        "services.app_review_studio_service.TelegramLinkService.get_link_for_user",
        fake_get_link,
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.AccountConnectionService.list_accounts",
        fake_list_accounts,
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.BrandProfileService.get_for_user",
        fake_get_brand,
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.WebsiteReviewService.review_url",
        fake_review_url,
    )
    monkeypatch.setattr(
        AppReviewStudioService,
        "_resolve_persona",
        classmethod(lambda cls, *, persona_id, user_id: fake_resolve_persona(persona_id=persona_id, user_id=user_id)),
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.VideoPlanningService.create_plan",
        fail_create_plan,
    )
    monkeypatch.setattr(
        "services.script_service.ScriptService.generate_script_from_review_plan",
        fake_generate_script,
    )

    with pytest.raises(ValueError, match="No plan was created"):
        await AppReviewStudioService.create_jobs(
            session=_session(),
            payload={
                "source_url": "https://example.com/app",
                "objective": "Review product",
                "target_personas": ["persona-1"],
                "input_mode": "ai_autonomous",
            },
            temporal_client=None,
        )


@pytest.mark.asyncio
async def test_create_jobs_reuses_validated_page_review_payload_without_live_review(monkeypatch):
    recorded_plan_payloads: List[Dict[str, Any]] = []

    async def fake_get_link(_user_id):
        return None

    async def fake_list_accounts(_user_id):
        return []

    async def fake_get_brand(_user_id):
        return None

    async def fail_live_review(**kwargs):
        raise AssertionError("validated page_review_data should bypass live source review")

    async def fake_resolve_persona(*, persona_id, user_id):
        return {
            "persona_id": persona_id,
            "display_name": "Ava",
            "language": "English",
            "tts_voice": "en-US-Standard-F",
        }

    async def fake_create_plan(payload):
        recorded_plan_payloads.append(payload)
        return {
            "id": "plan-1",
            "user_id": payload["user_id"],
            "campaign_id": payload.get("campaign_id"),
            "persona_id": payload["persona_id"],
            "source_url": payload["source_url"],
            "objective": payload["objective"],
            "script_text": payload["script_text"],
            "scenes_data": payload["scenes_data"],
            "duration_estimate": payload["duration_estimate"],
            "status": payload["status"],
            "workflow_id": None,
            "video_url": None,
            "publish_settings": payload["publish_settings"],
            "creative_preferences": payload["creative_preferences"],
            "page_review_data": payload["page_review_data"],
            "created_at": "2026-04-20T00:00:00Z",
            "updated_at": "2026-04-20T00:00:00Z",
            "approved_at": None,
        }

    async def fake_generate_script(*args, **kwargs):
        return (
            type("Script", (), {"model_dump": lambda self, mode="json": {"script": "English master", "scenes": [], "duration_estimate": 12}})(),
            None,
        )

    monkeypatch.setattr(
        "services.app_review_studio_service.TelegramLinkService.get_link_for_user",
        fake_get_link,
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.AccountConnectionService.list_accounts",
        fake_list_accounts,
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.BrandProfileService.get_for_user",
        fake_get_brand,
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.WebsiteReviewService.review_url",
        fail_live_review,
    )
    monkeypatch.setattr(
        AppReviewStudioService,
        "_resolve_persona",
        classmethod(lambda cls, *, persona_id, user_id: fake_resolve_persona(persona_id=persona_id, user_id=user_id)),
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.VideoPlanningService.create_plan",
        fake_create_plan,
    )
    monkeypatch.setattr(
        "services.script_service.ScriptService.generate_script_from_review_plan",
        fake_generate_script,
    )

    result = await AppReviewStudioService.create_jobs(
        session=_session(),
        payload={
            "source_url": "https://example.com/app",
            "objective": "Review product",
            "target_personas": ["persona-1"],
            "input_mode": "ai_autonomous",
            "page_review_data": _page_review().model_dump(mode="json"),
        },
        temporal_client=None,
    )

    assert result["jobs"][0]["source_url"] == "https://example.com/app"
    assert recorded_plan_payloads[0]["page_review_data"]["normalized_url"] == "https://example.com/app"


@pytest.mark.asyncio
async def test_create_jobs_builds_english_master_and_translates_persona_outputs(monkeypatch):
    recorded_review_plans: List[Dict[str, Any]] = []
    recorded_plan_payloads: List[Dict[str, Any]] = []

    async def fake_get_link(_user_id):
        return None

    async def fake_list_accounts(_user_id):
        return []

    async def fake_get_brand(_user_id):
        return None

    async def fake_review_url(*, url, objective=None, user_id=None):
        return _page_review()

    async def fake_resolve_persona(*, persona_id, user_id):
        personas = {
            "persona-en": {
                "persona_id": "persona-en",
                "display_name": "Ava",
                "language": "English",
                "tts_voice": "en-US-Standard-F",
            },
            "persona-ru": {
                "persona_id": "persona-ru",
                "display_name": "Nika",
                "language": "Russian",
                "tts_voice": "ru-RU-Standard-A",
            },
        }
        return personas[persona_id]

    async def fake_create_plan(payload):
        recorded_plan_payloads.append(payload)
        return {
            "id": f"plan-{payload['persona_id']}",
            "user_id": payload["user_id"],
            "campaign_id": payload.get("campaign_id"),
            "persona_id": payload["persona_id"],
            "source_url": payload["source_url"],
            "objective": payload["objective"],
            "script_text": payload["script_text"],
            "scenes_data": payload["scenes_data"],
            "duration_estimate": payload["duration_estimate"],
            "status": payload["status"],
            "workflow_id": None,
            "video_url": None,
            "publish_settings": payload["publish_settings"],
            "creative_preferences": payload["creative_preferences"],
            "page_review_data": payload["page_review_data"],
            "created_at": "2026-04-20T00:00:00Z",
            "updated_at": "2026-04-20T00:00:00Z",
            "approved_at": None,
        }

    async def fake_generate_script(_self, *, app_name, review_plan, persona_config):
        recorded_review_plans.append(review_plan)
        language = review_plan["language"]
        if language == "English":
            return (
                type("Script", (), {"model_dump": lambda self, mode="json": {"script": "English master script", "scenes": [{"description": "English scene 1", "duration": 6}], "duration_estimate": 12}})(),
                None,
            )
        raise AssertionError("persona generation should translate from English master instead of regenerating by persona language")

    async def fake_translate_script(_self, *, app_name, source_script, target_language, persona_config):
        assert source_script.script == "English master script"
        assert target_language == "Russian"
        return type(
            "TranslatedScript",
            (),
            {
                "model_dump": lambda self, mode="json": {
                    "script": "Russian translated script",
                    "scenes": [{"description": "Russian scene 1", "duration": 6}],
                    "duration_estimate": 12,
                }
            },
        )()

    monkeypatch.setattr(
        "services.app_review_studio_service.TelegramLinkService.get_link_for_user",
        fake_get_link,
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.AccountConnectionService.list_accounts",
        fake_list_accounts,
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.BrandProfileService.get_for_user",
        fake_get_brand,
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.WebsiteReviewService.review_url",
        fake_review_url,
    )
    monkeypatch.setattr(
        AppReviewStudioService,
        "_resolve_persona",
        classmethod(lambda cls, *, persona_id, user_id: fake_resolve_persona(persona_id=persona_id, user_id=user_id)),
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.VideoPlanningService.create_plan",
        fake_create_plan,
    )
    monkeypatch.setattr(
        "services.script_service.ScriptService.generate_script_from_review_plan",
        fake_generate_script,
    )
    monkeypatch.setattr(
        "services.script_service.ScriptService.translate_review_plan_script",
        fake_translate_script,
    )

    result = await AppReviewStudioService.create_jobs(
        session=_session(),
        payload={
            "source_url": "https://example.com/app",
            "objective": "Review product",
            "target_personas": ["persona-ru", "persona-en"],
            "input_mode": "ai_autonomous",
        },
        temporal_client=None,
    )

    assert recorded_review_plans[0]["language"] == "English"
    scripts_by_persona = {item["persona_id"]: item["script_text"] for item in recorded_plan_payloads}
    assert scripts_by_persona["persona-en"] == "English master script"
    assert scripts_by_persona["persona-ru"] == "Russian translated script"
    assert result["master_contract"]["script_text"] == "English master script"


@pytest.mark.asyncio
async def test_list_jobs_merges_plan_and_workflow_by_plan_id(monkeypatch):
    async def fake_list_plans(_user_id, limit=50):
        return [
            {
                "id": "plan-1",
                "persona_id": "persona-1",
                "source_url": "https://example.com/app",
                "objective": "Review product",
                "script_text": "Script body",
                "scenes_data": [],
                "status": "approved",
                "workflow_id": "video-wf-1",
                "video_url": None,
                "publish_settings": {
                    "content_title": "Example App · Ava",
                    "caption_draft": "Caption draft",
                    "publish_requested": False,
                    "input_mode": "ai_autonomous",
                },
                "creative_preferences": {"hook_style": "bold"},
                "page_review_data": {
                    "normalized_url": "https://example.com/app",
                    "page_title": "Example App",
                    "access_level": "public_page_only",
                    "login_required": False,
                    "visible_features": [],
                    "risks": [],
                    "assumptions": [],
                },
                "created_at": "2026-04-18T00:00:00Z",
                "updated_at": "2026-04-18T01:00:00Z",
                "approved_at": "2026-04-18T01:00:00Z",
            }
        ]

    async def fake_list_rows(*, user_id, limit=50):
        return [
            {
                "workflow_id": "video-wf-1",
                "type": "app_review_video",
                "status": "running",
                "current_step": "generation_queued",
                "input_data": {
                    "plan_id": "plan-1",
                    "persona_id": "persona-1",
                    "persona_display_name": "Ava",
                    "persona_language": "English",
                    "persona_region": "American",
                    "persona_image_url": "https://cdn.example/ava.png",
                    "objective": "Review product",
                    "normalized_url": "https://example.com/app",
                    "page_title": "Example App",
                    "publish_requested": False,
                    "content_title": "Example App · Ava",
                    "editable_content": "Caption draft",
                    "review_plan": {"plan_id": "plan-1"},
                    "script": {"script": "Script body", "scenes": []},
                    "publish_settings": {
                        "content_title": "Example App · Ava",
                        "caption_draft": "Caption draft",
                    },
                    "creative_preferences": {"hook_style": "bold"},
                },
                "output_data": {},
                "updated_at": "2026-04-18T02:00:00Z",
                "started_at": "2026-04-18T01:30:00Z",
            }
        ]

    async def fake_refresh(*, temporal_client, job_row):
        return job_row

    async def fake_list_accounts(_user_id):
        return []

    async def fake_load_media(*, workflow_ids, user_id):
        return {}

    async def fake_load_content(*, workflow_ids, user_id):
        return {}

    async def fake_resolve_persona(*, persona_id, user_id):
        return {
            "persona_id": persona_id,
            "display_name": "Ava",
            "language": "English",
            "tts_voice": "en-US-Standard-F",
        }

    monkeypatch.setattr(
        "services.app_review_studio_service.VideoPlanningService.list_plans",
        fake_list_plans,
    )
    monkeypatch.setattr(AppReviewStudioService, "_list_job_rows", classmethod(lambda cls, *, user_id, limit=50: fake_list_rows(user_id=user_id, limit=limit)))
    monkeypatch.setattr(AppReviewStudioService, "_refresh_live_status", classmethod(lambda cls, *, temporal_client, job_row: fake_refresh(temporal_client=temporal_client, job_row=job_row)))
    monkeypatch.setattr(AppReviewStudioService, "_load_media_by_workflow", classmethod(lambda cls, *, workflow_ids, user_id: fake_load_media(workflow_ids=workflow_ids, user_id=user_id)))
    monkeypatch.setattr(AppReviewStudioService, "_load_content_by_workflow", classmethod(lambda cls, *, workflow_ids, user_id: fake_load_content(workflow_ids=workflow_ids, user_id=user_id)))
    monkeypatch.setattr(
        "services.app_review_studio_service.AccountConnectionService.list_accounts",
        fake_list_accounts,
    )
    monkeypatch.setattr(
        AppReviewStudioService,
        "_resolve_persona",
        classmethod(lambda cls, *, persona_id, user_id: fake_resolve_persona(persona_id=persona_id, user_id=user_id)),
    )

    payload = await AppReviewStudioService.list_jobs(
        user_id=_session().user_id,
        temporal_client=None,
        limit=50,
    )

    assert len(payload["jobs"]) == 1
    job = payload["jobs"][0]
    assert job["job_id"] == "plan-1"
    assert job["plan_id"] == "plan-1"
    assert job["workflow_id"] == "video-wf-1"
    assert job["status"] == "running"
    assert job["input_mode"] == "ai_autonomous"
    assert job["creative_preferences"] == {"hook_style": "bold"}
    assert job["source_url"] == "https://example.com/app"


@pytest.mark.asyncio
async def test_upload_manual_video_updates_existing_plan(monkeypatch):
    update_calls: List[Dict[str, Any]] = []

    async def fake_find_plan_for_job(public_job_id, user_id):
        assert public_job_id == "plan-1"
        assert user_id == _session().user_id
        return {
            "id": "plan-1",
            "persona_id": "persona-1",
            "source_url": "https://example.com/app",
            "objective": "Review product",
            "status": "upload_required",
            "workflow_id": None,
            "publish_settings": {"input_mode": "user_upload"},
        }

    async def fake_update_plan(plan_id, user_id, updates):
        update_calls.append({"plan_id": plan_id, "user_id": user_id, "updates": updates})
        return {
            "id": plan_id,
            "status": updates["status"],
            "video_url": updates["video_url"],
            "publish_settings": updates["publish_settings"],
        }

    async def fake_get_job(*, user_id, job_id, temporal_client=None):
        return {
            "job_id": job_id,
            "plan_id": job_id,
            "status": "generated",
            "production": {
                "ready": True,
                "playable_video_url": "https://cdn.example/upload.mp4",
            },
        }

    class FakeMediaStorage:
        async def upload_bytes(self, **kwargs):
            return {
                "access_url": "https://cdn.example/upload.mp4",
                "media_asset_id": "media-1",
            }

    monkeypatch.setattr(
        "services.app_review_studio_service.VideoPlanningService.find_plan_for_job",
        fake_find_plan_for_job,
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.VideoPlanningService.update_plan",
        fake_update_plan,
    )
    monkeypatch.setattr(AppReviewStudioService, "get_job", classmethod(lambda cls, *, user_id, job_id, temporal_client=None: fake_get_job(user_id=user_id, job_id=job_id, temporal_client=temporal_client)))
    monkeypatch.setattr(
        "services.app_review_studio_service.MediaStorageService",
        FakeMediaStorage,
    )

    result = await AppReviewStudioService.upload_manual_video(
        session=_session(),
        job_id="plan-1",
        file_name="demo.mp4",
        content_type="video/mp4",
        data=b"video",
    )

    assert result["production"]["ready"] is True
    assert update_calls[0]["updates"]["status"] == "generated"
    assert update_calls[0]["updates"]["video_url"] == "https://cdn.example/upload.mp4"
    assert (
        update_calls[0]["updates"]["publish_settings"]["uploaded_media_asset_id"]
        == "media-1"
    )


@pytest.mark.asyncio
async def test_start_workflow_from_plan_rebuilds_persisted_page_review(monkeypatch):
    captured: Dict[str, Any] = {}

    async def fake_get_plan(plan_id, user_id):
        return {
            "id": plan_id,
            "persona_id": "persona-1",
            "source_url": "https://example.com/login",
            "objective": "Review secure dashboard",
            "script_text": "Script body",
            "scenes_data": [],
            "status": "approved",
            "workflow_id": None,
            "video_url": None,
            "campaign_id": None,
            "publish_settings": {
                "caption_draft": "Caption draft",
                "content_title": "Secure App · Ava",
                "publish_requested": False,
                "input_mode": "ai_autonomous",
            },
            "creative_preferences": {"hook_style": "bold"},
            "page_review_data": {
                "target_url": "https://example.com/login",
                "normalized_url": "https://example.com/login",
                "page_title": "Secure App",
                "product_summary": "Secure workflow",
                "access_level": "has_logged_in_access",
                "login_required": True,
                "visible_features": [
                    {
                        "label": "Dashboard",
                        "summary": "Shows analytics",
                        "evidence": ["Analytics cards"],
                        "source_url": "https://example.com/login",
                    }
                ],
                "risks": ["Needs auth"],
                "assumptions": ["User has access"],
            },
            "created_at": "2026-04-18T00:00:00Z",
            "updated_at": "2026-04-18T00:00:00Z",
            "approved_at": "2026-04-18T00:00:00Z",
        }

    async def fake_resolve_persona(*, persona_id, user_id):
        return {
            "persona_id": persona_id,
            "display_name": "Ava",
            "language": "English",
            "tts_voice": "en-US-Standard-F",
        }

    async def fake_get_link(_user_id):
        return None

    async def fake_list_accounts(_user_id):
        return []

    async def fake_start_video_workflow(**kwargs):
        captured["page_review"] = kwargs["page_review"]
        captured["execution_mode"] = kwargs["execution_mode"]
        return {
            "workflow_id": "video-persona-1-abcd1234",
            "review_plan": {"plan_id": "plan-1", "page_review": {"page_title": "Secure App"}},
        }

    async def fake_update_plan(plan_id, user_id, updates):
        captured["plan_update"] = updates
        return {"id": plan_id, **updates}

    async def fake_record_job_state(**kwargs):
        captured["job_input"] = kwargs["input_data"]

    monkeypatch.setattr(
        "services.app_review_studio_service.VideoPlanningService.get_plan",
        fake_get_plan,
    )
    monkeypatch.setattr(
        AppReviewStudioService,
        "_resolve_persona",
        classmethod(lambda cls, *, persona_id, user_id: fake_resolve_persona(persona_id=persona_id, user_id=user_id)),
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.TelegramLinkService.get_link_for_user",
        fake_get_link,
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.AccountConnectionService.list_accounts",
        fake_list_accounts,
    )
    monkeypatch.setattr(
        AppReviewStudioService,
        "_start_video_workflow",
        classmethod(lambda cls, **kwargs: fake_start_video_workflow(**kwargs)),
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.VideoPlanningService.update_plan",
        fake_update_plan,
    )
    monkeypatch.setattr(
        AppReviewStudioService,
        "_record_job_state",
        classmethod(lambda cls, **kwargs: fake_record_job_state(**kwargs)),
    )

    result = await AppReviewStudioService.start_workflow_from_plan(
        session=_session(),
        plan_id="plan-1",
        temporal_client=None,
    )

    assert result["workflow_id"] == "video-persona-1-abcd1234"
    assert captured["page_review"].page_title == "Secure App"
    assert captured["page_review"].normalized_url == "https://example.com/login"
    assert captured["page_review"].access_level == "has_logged_in_access"
    assert captured["execution_mode"] == "authenticated_pc_recording"
    assert captured["plan_update"] == {"workflow_id": "video-persona-1-abcd1234"}
    assert captured["job_input"]["plan_id"] == "plan-1"
    assert captured["job_input"]["review_plan"]["plan_id"] == "plan-1"


@pytest.mark.asyncio
async def test_start_workflow_from_plan_manual_upload_creates_synthetic_workflow(monkeypatch):
    captured: Dict[str, Any] = {}

    async def fake_get_plan(plan_id, user_id):
        return {
            "id": plan_id,
            "persona_id": "persona-1",
            "source_url": "https://example.com/app",
            "objective": "Review product",
            "script_text": "",
            "scenes_data": [],
            "status": "approved",
            "workflow_id": None,
            "video_url": "https://cdn.example/final.mp4",
            "campaign_id": None,
            "publish_settings": {
                "caption_draft": "",
                "content_title": "Example App · Ava",
                "publish_requested": False,
                "input_mode": "user_upload",
                "uploaded_media_asset_id": "media-1",
            },
            "creative_preferences": {},
            "page_review_data": {
                "target_url": "https://example.com/app",
                "normalized_url": "https://example.com/app",
                "page_title": "Example App",
                "access_level": "public_page_only",
                "login_required": False,
                "visible_features": [],
                "risks": [],
                "assumptions": [],
            },
        }

    async def fake_resolve_persona(*, persona_id, user_id):
        return {
            "persona_id": persona_id,
            "display_name": "Ava",
            "language": "English",
            "tts_voice": "en-US-Standard-F",
        }

    async def fake_get_link(_user_id):
        return None

    async def fake_list_accounts(_user_id):
        return []

    async def fail_start_video_workflow(**kwargs):
        raise AssertionError("manual upload path should not start temporal workflow")

    async def fake_record_job_state(**kwargs):
        captured["workflow_id"] = kwargs["workflow_id"]
        captured["status"] = kwargs["status"]
        captured["input_data"] = kwargs["input_data"]

    async def fake_update_job_output(**kwargs):
        captured["output_data"] = kwargs["output_data"]
        return {}

    async def fake_update_plan(plan_id, user_id, updates):
        captured["plan_update"] = updates
        return {"id": plan_id, **updates}

    monkeypatch.setattr(
        "services.app_review_studio_service.VideoPlanningService.get_plan",
        fake_get_plan,
    )
    monkeypatch.setattr(
        AppReviewStudioService,
        "_resolve_persona",
        classmethod(lambda cls, *, persona_id, user_id: fake_resolve_persona(persona_id=persona_id, user_id=user_id)),
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.TelegramLinkService.get_link_for_user",
        fake_get_link,
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.AccountConnectionService.list_accounts",
        fake_list_accounts,
    )
    monkeypatch.setattr(
        AppReviewStudioService,
        "_start_video_workflow",
        classmethod(lambda cls, **kwargs: fail_start_video_workflow(**kwargs)),
    )
    monkeypatch.setattr(
        AppReviewStudioService,
        "_record_job_state",
        classmethod(lambda cls, **kwargs: fake_record_job_state(**kwargs)),
    )
    monkeypatch.setattr(
        AppReviewStudioService,
        "_update_job_output",
        classmethod(lambda cls, **kwargs: fake_update_job_output(**kwargs)),
    )
    monkeypatch.setattr(
        "services.app_review_studio_service.VideoPlanningService.update_plan",
        fake_update_plan,
    )

    result = await AppReviewStudioService.start_workflow_from_plan(
        session=_session(),
        plan_id="plan-1",
        temporal_client=None,
    )

    assert result["status"] == "started"
    assert captured["workflow_id"].startswith("review-upload-plan-1")
    assert captured["status"] == "completed"
    assert captured["output_data"]["final_video_url"] == "https://cdn.example/final.mp4"
    assert captured["plan_update"]["workflow_id"] == captured["workflow_id"]
