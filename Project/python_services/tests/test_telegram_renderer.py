"""Renderer tests for the Telegram studio surface."""

from services.contracts import BeatSheetContract, ConceptBriefContract
from services.telegram_renderer import TelegramRenderer
from skills.base import SkillControl, SkillResult, SkillSession, SkillStatus
from skills.publish_manager import PublishManagerSkill


def test_render_menu_main_includes_new_studio_copy():
    rendered = TelegramRenderer.render_menu("menu_main")

    assert "TripC Media Studio" in rendered["text"]
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


def _video_concept():
    return ConceptBriefContract(
        persona_id="minh_vn",
        feature_focus="AI itinerary planner",
        video_goal="feature_demo",
        audience="travelers aged 22-35",
        angle="problem_solution",
        platform="tiktok",
        cta="Try TripC free",
        reference_url="https://tripc.ai",
        access_level="public_page_only",
        source_summary="TripC is a travel planning product.",
        tone_resolved="confident",
    ).model_dump(mode="json")


def _video_beats():
    return BeatSheetContract(
        beats=[
            {
                "idx": 1,
                "purpose": "hook",
                "bottom_half_message": "Still planning trips manually?",
                "top_half_source_type": "public_page_capture",
                "top_half_target": "hero_section",
                "top_half_capture_hint": "Show hero section",
                "overlay_text": "Plan faster",
                "duration_sec": 4,
            },
            {
                "idx": 2,
                "purpose": "problem",
                "bottom_half_message": "Too many tabs and notes.",
                "top_half_source_type": "public_page_capture",
                "top_half_target": "feature_block",
                "top_half_capture_hint": "Show feature block",
                "overlay_text": "Less chaos",
                "duration_sec": 4,
            },
            {
                "idx": 3,
                "purpose": "solution_intro",
                "bottom_half_message": "TripC simplifies the flow.",
                "top_half_source_type": "public_page_capture",
                "top_half_target": "product_overview",
                "top_half_capture_hint": "Show product overview",
                "overlay_text": "One flow",
                "duration_sec": 4,
            },
            {
                "idx": 4,
                "purpose": "feature_demo",
                "bottom_half_message": "AI suggests an itinerary fast.",
                "top_half_source_type": "public_page_capture",
                "top_half_target": "itinerary_section",
                "top_half_capture_hint": "Show itinerary section",
                "overlay_text": "AI itinerary",
                "duration_sec": 4,
            },
            {
                "idx": 5,
                "purpose": "cta",
                "bottom_half_message": "Try TripC free today.",
                "top_half_source_type": "public_page_capture",
                "top_half_target": "cta_section",
                "top_half_capture_hint": "Show CTA section",
                "overlay_text": "Try it now",
                "duration_sec": 4,
            },
        ]
    ).model_dump(mode="json")


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


def test_render_video_ai_concept_preview_uses_human_summary():
    session = SkillSession(
        skill_name="video-ai",
        step_key="confirm_concept",
        collected={"persona_id": "minh_vn"},
        artifacts={
            "concept_brief": _video_concept(),
            "persona_snapshot": {
                "display_name": "Minh VN",
                "tone_resolved": "confident",
            },
        },
        control=SkillControl(status=SkillStatus.preview_ready),
    )
    result = SkillResult(
        success=True,
        next_step="confirm_concept",
        output={"concept_brief": _video_concept()},
        session=session,
    )

    rendered = TelegramRenderer.render_skill_result(result)

    assert "Video Concept Ready" in rendered["text"]
    assert "Feature Focus: AI itinerary planner" in rendered["text"]
    assert "{" not in rendered["text"]
    callback_values = {
        button["callback_data"]
        for row in rendered["reply_markup"]["inline_keyboard"]
        for button in row
    }
    assert {"action::approve", "action::edit", "action::regenerate"} <= callback_values


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
    assert (
        "Script review and the final preview will arrive in this chat."
        in rendered["text"]
    )


def test_render_video_ai_beats_preview_lists_beats():
    session = SkillSession(
        skill_name="video-ai",
        step_key="confirm_beats",
        collected={"persona_id": "minh_vn"},
        artifacts={
            "concept_brief": _video_concept(),
            "beat_sheet": _video_beats(),
        },
        control=SkillControl(status=SkillStatus.preview_ready),
    )
    result = SkillResult(
        success=True,
        next_step="confirm_beats",
        output={"beat_sheet": _video_beats(), "concept_brief": _video_concept()},
        session=session,
    )

    rendered = TelegramRenderer.render_skill_result(result)

    assert "Beat Plan Ready" in rendered["text"]
    assert "1. Hook:" in rendered["text"]
    assert "Top Half: itinerary_section (Public Page Capture)" in rendered["text"]


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


def test_render_video_ai_done_state_reports_package_ready():
    """Test that video-ai done state shows workflow started when workflow_id present."""
    package = {
        "concept_brief": _video_concept(),
        "beat_sheet": _video_beats(),
        "persona_snapshot": {"persona_id": "minh_vn"},
    }
    session = SkillSession(
        skill_name="video-ai",
        step_key="package_ready",
        collected={"persona_id": "minh_vn"},
        artifacts={"approved_production_package": package},
        control=SkillControl(status=SkillStatus.done),
    )
    result = SkillResult(
        success=True,
        next_step="package_ready",
        output={
            "approved_production_package": package,
            "workflow_id": "video-minh_vn-abc123",
        },
        session=session,
    )

    rendered = TelegramRenderer.render_skill_result(result)

    assert "Production workflow started!" in rendered["text"]
    assert "video-minh_vn-abc123" in rendered["text"]
    assert rendered["reply_markup"] is None


def test_render_video_ai_done_state_shows_error_when_workflow_failed():
    """Test that video-ai done state shows error when workflow_id missing."""
    package = {
        "concept_brief": _video_concept(),
        "beat_sheet": _video_beats(),
        "persona_snapshot": {"persona_id": "minh_vn"},
    }
    session = SkillSession(
        skill_name="video-ai",
        step_key="package_ready",
        collected={"persona_id": "minh_vn"},
        artifacts={"approved_production_package": package},
        control=SkillControl(status=SkillStatus.done),
    )
    result = SkillResult(
        success=True,
        next_step="package_ready",
        output={"approved_production_package": package},  # No workflow_id
        session=session,
    )

    rendered = TelegramRenderer.render_skill_result(result)

    assert "Pre-production package ready." in rendered["text"]
    assert "Production workflow could not be started." in rendered["text"]
    assert rendered["reply_markup"] is None


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


def test_render_video_ai_retryable_failure_keeps_retry_actions_without_approve_when_missing_artifact():
    session = SkillSession(
        skill_name="video-ai",
        step_key="confirm_beats",
        collected={"persona_id": "minh_vn"},
        artifacts={"concept_brief": _video_concept(), "beat_sheet": None},
        control=SkillControl(status=SkillStatus.failed),
    )
    result = SkillResult(
        success=False,
        next_step="confirm_beats",
        output={"retryable": True, "concept_brief": _video_concept()},
        error="Could not build the beat plan yet.",
        session=session,
    )

    rendered = TelegramRenderer.render_skill_result(result)

    assert "Could not build the beat plan yet." in rendered["text"]
    callback_values = {
        button["callback_data"]
        for row in rendered["reply_markup"]["inline_keyboard"]
        for button in row
    }
    assert "action::approve" not in callback_values
    assert "action::regenerate" in callback_values
    assert "action::edit" in callback_values
