"""Renderer tests for the Telegram studio surface."""

from services.telegram_renderer import TelegramRenderer
from skills.base import SkillControl, SkillResult, SkillSession, SkillStatus
from skills.publish_manager import PublishManagerSkill


def test_render_menu_main_includes_new_studio_copy():
    rendered = TelegramRenderer.render_menu("menu_main")

    assert "TripC Media Editor" in rendered["text"]
    rows = rendered["reply_markup"]["inline_keyboard"]
    callback_values = {button["callback_data"] for row in rows for button in row}
    assert "menu_image" in callback_values
    assert "menu_manage" in callback_values


def test_render_menu_image_includes_poster_and_scene():
    rendered = TelegramRenderer.render_menu("menu_image")

    rows = rendered["reply_markup"]["inline_keyboard"]
    callback_values = {button["callback_data"] for row in rows for button in row}
    assert "skill_image-poster" in callback_values
    assert "skill_image-scene" in callback_values


def test_render_catalog_info_for_long_post_points_back_to_content_menu():
    rendered = TelegramRenderer.render_catalog_info("long-post")

    assert "Status:" in rendered["text"]
    rows = rendered["reply_markup"]["inline_keyboard"]
    assert rows[-1][0]["callback_data"] == "menu_content"


def test_render_publish_manager_prompt_shows_queue_actions():
    session = PublishManagerSkill.initial_session()
    session.step_key = "select_item"
    session.artifacts["queue_items"] = [
        {
            "id": "failed-1",
            "title": "Retry this failed post",
            "status": "failed",
            "platform": ["facebook"],
        }
    ]

    rendered = TelegramRenderer.render_skill_prompt(session)

    assert "Publish Queue" in rendered["text"]
    rows = rendered["reply_markup"]["inline_keyboard"]
    callback_values = [button["callback_data"] for row in rows for button in row]
    assert "option::failed-1" in callback_values
    assert "action::refresh_queue" in callback_values


def test_render_image_scene_preview_uses_first_candidate_photo_url():
    session = SkillSession(
        skill_name="image-scene",
        step_key="confirm_or_regenerate",
        collected={
            "style": "clean",
            "scene_type": "city",
            "aspect_ratio": "16:9",
            "topic_or_prompt": "Da Nang skyline",
        },
        artifacts={"image_candidates": [{"url": "https://cdn.example/scene-1.png"}]},
        control=SkillControl(status=SkillStatus.preview_ready),
    )
    result = SkillResult(
        success=True,
        next_step="confirm_or_regenerate",
        output={"image_candidates": [{"url": "https://cdn.example/scene-1.png"}]},
        session=session,
    )

    rendered = TelegramRenderer.render_skill_result(result)

    assert rendered.get("photo_url") == "https://cdn.example/scene-1.png"
    assert "Image Generated Successfully" in rendered["text"]


def test_render_video_waiting_state_explains_follow_up_messages():
    session = SkillSession(
        skill_name="video-ai",
        step_key="approve_video",
        collected={
            "persona_id": "persona-1",
            "topic": "Weekend beach trip",
            "tone": "natural",
            "platform": "tiktok",
        },
        artifacts={"workflow_id": "video-wf-1"},
        control=SkillControl(
            status=SkillStatus.waiting_approval,
            workflow_id="video-wf-1",
            approval_required=True,
        ),
    )
    result = SkillResult(
        success=True,
        next_step="poll_status",
        output={"workflow_id": "video-wf-1", "status": "started"},
        session=session,
    )

    rendered = TelegramRenderer.render_skill_result(result)

    assert "Video Generation Started" in rendered["text"]
    assert "Script review and the final preview will arrive in this chat." in rendered["text"]


def test_render_persona_inspector_done_shows_photo_and_details():
    session = SkillSession(
        skill_name="persona-inspector",
        step_key="done",
        collected={"persona_id": "hero-host"},
        artifacts={},
        control=SkillControl(status=SkillStatus.done),
    )
    result = SkillResult(
        success=True,
        next_step="done",
        output={
            "persona": {
                "persona_id": "hero-host",
                "display_name": "Hero Host",
                "language": "Vietnamese",
                "tts_voice": "vi-VN-Wavenet-D",
                "status": "draft",
                "avatar_image_url": "https://cdn.example/hero-host.png",
                "avatar_media_asset_id": "asset-123",
                "heygen_avatar_id": "heygen-456",
            },
            "readiness": {
                "ready": False,
                "blocking_reason": "Persona status is not ready.",
                "checks": {
                    "status_ready": False,
                    "has_tts_voice": True,
                    "has_avatar_asset": True,
                    "has_heygen_avatar_id": True,
                },
            },
            "preview_image_url": "https://cdn.example/hero-host.png",
        },
        session=session,
    )

    rendered = TelegramRenderer.render_skill_result(result)

    assert rendered.get("photo_url") == "https://cdn.example/hero-host.png"
    assert "Persona inspection completed." in rendered["text"]
    assert "Hero Host" in rendered["text"]
    assert "asset-123" in rendered["text"]
    assert "heygen-456" in rendered["text"]
    assert "Avatar image URL: YES" in rendered["text"]


def test_render_persona_inspector_done_reports_missing_image():
    session = SkillSession(
        skill_name="persona-inspector",
        step_key="done",
        collected={"persona_id": "hero-host"},
        artifacts={},
        control=SkillControl(status=SkillStatus.done),
    )
    result = SkillResult(
        success=True,
        next_step="done",
        output={
            "persona": {
                "persona_id": "hero-host",
                "display_name": "Hero Host",
                "language": "Vietnamese",
                "tts_voice": "vi-VN-Wavenet-D",
                "status": "draft",
                "avatar_media_asset_id": None,
                "heygen_avatar_id": None,
            },
            "readiness": {
                "ready": False,
                "blocking_reason": "Missing avatar_media_asset_id. Save persona media first.",
                "checks": {
                    "status_ready": False,
                    "has_tts_voice": True,
                    "has_avatar_asset": False,
                    "has_heygen_avatar_id": False,
                },
            },
        },
        session=session,
    )

    rendered = TelegramRenderer.render_skill_result(result)

    assert "Avatar preview image is not available yet." in rendered["text"]
    assert rendered.get("photo_url") is None


def test_render_persona_creator_preview_warns_that_save_is_still_required():
    session = SkillSession(
        skill_name="persona-creator",
        step_key="preview",
        collected={"persona_id": "hero-host"},
        artifacts={
            "persona_id": "hero-host",
            "preview_image_url": "https://cdn.example/hero-host.png",
        },
        control=SkillControl(status=SkillStatus.preview_ready),
    )
    result = SkillResult(
        success=True,
        next_step="preview",
        output={
            "preview_image_url": "https://cdn.example/hero-host.png",
            "persona": {
                "persona_id": "hero-host",
                "language": "Vietnamese",
                "tts_voice": "vi-VN-Wavenet-D",
                "status": "draft",
                "avatar_image_url": "https://cdn.example/hero-host.png",
                "avatar_media_asset_id": None,
            },
            "readiness": {
                "ready": False,
                "blocking_reason": (
                    "The avatar preview looks good, but it has not been saved to your project yet. "
                    "Tap Save Persona to keep it and use this persona in video workflows."
                ),
                "checks": {
                    "status_ready": False,
                    "has_tts_voice": True,
                    "has_avatar_image": True,
                    "has_avatar_asset": False,
                    "has_heygen_avatar_id": False,
                },
                "save_required": True,
            },
        },
        session=session,
    )

    rendered = TelegramRenderer.render_skill_result(result)

    assert "Persona Preview Ready" in rendered["text"]
    assert "temporary preview only" in rendered["text"]
    assert "Tap Save Persona to keep it" in rendered["text"]


def test_render_cancelled_video_result_uses_friendly_copy():
    session = SkillSession(
        skill_name="video-ai",
        step_key="approve_video",
        artifacts={"workflow_id": "video-wf-1"},
        control=SkillControl(status=SkillStatus.done),
    )
    result = SkillResult(
        success=True,
        next_step="done",
        output={"status": "cancelled", "workflow_id": "video-wf-1"},
        session=session,
    )

    rendered = TelegramRenderer.render_skill_result(result)

    assert "Video workflow cancelled" in rendered["text"]
    assert "No further generation steps will run" in rendered["text"]
    assert "video-wf-1" in rendered["text"]
