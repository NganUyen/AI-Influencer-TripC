"""Renderer tests for the Telegram studio surface."""

from services.contracts import BeatSheetContract, ConceptBriefContract
from services.telegram_renderer import TelegramRenderer
from skills.publish_manager import PublishManagerSkill
from skills.base import SkillControl, SkillResult, SkillSession, SkillStatus


def test_render_menu_main_includes_new_studio_copy():
    rendered = TelegramRenderer.render_menu("menu_main")

    assert "TripC Media Studio" in rendered["text"]
    rows = rendered["reply_markup"]["inline_keyboard"]
    callback_values = {button["callback_data"] for row in rows for button in row}
    assert "menu_image" in callback_values
    assert "menu_content" in callback_values


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


def test_render_video_ai_concept_preview_uses_human_summary():
    session = SkillSession(
        skill_name="video-ai",
        step_key="confirm_concept",
        collected={"persona_id": "minh_vn"},
        artifacts={
            "concept_brief": _video_concept(),
            "persona_snapshot": {"display_name": "Minh VN", "tone_resolved": "confident"},
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


def test_render_video_ai_done_state_reports_package_ready():
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
        output={"approved_production_package": package},
        session=session,
    )

    rendered = TelegramRenderer.render_skill_result(result)

    assert "Pre-production package ready." in rendered["text"]
    assert "No production workflow has started yet." in rendered["text"]
    assert rendered["reply_markup"] is None


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
