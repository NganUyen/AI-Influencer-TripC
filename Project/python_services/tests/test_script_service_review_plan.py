from unittest.mock import AsyncMock

import pytest

from services.errors import ScriptGenerationError
from services.script_service import ScriptService


@pytest.mark.asyncio
async def test_generate_script_from_review_plan_builds_script_and_recording_steps(monkeypatch):
    async def fake_execute_task(self, task_type, prompt, user_id, context=None):
        assert task_type == "review_plan_script_generation"
        return {
            "script": "Start with the hero message, then show the dashboard and final CTA.",
            "duration_estimate": 40,
            "steps": [
                {
                    "idx": 1,
                    "purpose": "hook",
                    "screen_target": "Hero section",
                    "action": "Open the homepage and pause on the hero copy",
                    "visual_success_criteria": "The hero headline and CTA are visible",
                    "narration_intent": "Hook the viewer with the main promise",
                    "capture_hint": "scroll",
                    "requires_login": False,
                    "max_capture_seconds": 8,
                },
                {
                    "idx": 2,
                    "purpose": "feature_demo",
                    "screen_target": "Planning dashboard",
                    "action": "Scroll to the dashboard preview and hold on the workflow cards",
                    "visual_success_criteria": "The planning cards are readable",
                    "narration_intent": "Explain how the dashboard organizes work",
                    "capture_hint": "interactive",
                    "requires_login": False,
                    "max_capture_seconds": 9,
                },
                {
                    "idx": 3,
                    "purpose": "cta",
                    "screen_target": "Final CTA section",
                    "action": "Scroll to the CTA block and pause on the signup button",
                    "visual_success_criteria": "The CTA button is centered and visible",
                    "narration_intent": "End with a clear call to action",
                    "capture_hint": "scroll",
                    "requires_login": False,
                    "max_capture_seconds": 8,
                },
            ],
        }

    monkeypatch.setattr(
        "services.script_service.OpenClawService.execute_task",
        fake_execute_task,
    )
    monkeypatch.setattr(
        "services.script_service.OpenClawService.close",
        AsyncMock(return_value=None),
    )

    service = ScriptService()
    script, recording_script = await service.generate_script_from_review_plan(
        app_name="TripC",
        review_plan={
            "planning_mode": "webpage_review",
            "objective": "Create a walkthrough review",
            "target_url": "https://example.com",
            "language": "English",
            "persona_id": "persona-1",
            "execution_mode": "autonomous_screen_recording",
            "access_level": "public_page_only",
            "status": "confirmed",
            "page_review": {
                "target_url": "https://example.com",
                "normalized_url": "https://example.com",
                "product_summary": "A launch planning app.",
                "access_level": "public_page_only",
                "login_required": False,
            },
        },
        persona_config={"language_name": "English", "tts_voice": "en-US-Neural2-A"},
    )

    assert "hero message" in script.script
    assert len(script.scenes) == 3
    assert script.scenes[0].top_half_source_type == "public_page_capture"
    assert script.scenes[1].top_half_target == "Planning dashboard"
    assert script.scenes[0].browser_action == "Open the homepage and pause on the hero copy"
    assert script.scenes[0].visual_success_criteria == "The hero headline and CTA are visible"
    assert script.scenes[0].top_half_capture_hint == "orchestrated"
    assert recording_script.execution_mode == "autonomous_screen_recording"
    assert len(recording_script.steps) == 3
    assert recording_script.steps[0].action.startswith("Open the homepage")


@pytest.mark.asyncio
async def test_generate_script_from_review_plan_treats_rate_limit_text_as_generation_error(
    monkeypatch,
):
    async def fake_execute_task(self, task_type, prompt, user_id, context=None):
        assert task_type == "review_plan_script_generation"
        return {
            "text": "API rate limit reached. Please try again later.",
            "response_id": "resp-rate-limited",
            "task_type": "review_plan_script_generation",
        }

    monkeypatch.setattr(
        "services.script_service.OpenClawService.execute_task",
        fake_execute_task,
    )
    monkeypatch.setattr(
        "services.script_service.OpenClawService.close",
        AsyncMock(return_value=None),
    )

    service = ScriptService()
    with pytest.raises(ScriptGenerationError, match="rate limit"):
        await service.generate_script_from_review_plan(
            app_name="TripC",
            review_plan={
                "planning_mode": "webpage_review",
                "objective": "Create a walkthrough review",
                "target_url": "https://example.com",
                "language": "English",
                "persona_id": "persona-1",
                "execution_mode": "autonomous_screen_recording",
                "access_level": "public_page_only",
                "status": "confirmed",
                "page_review": {
                    "target_url": "https://example.com",
                    "normalized_url": "https://example.com",
                    "product_summary": "A launch planning app.",
                    "access_level": "public_page_only",
                    "login_required": False,
                },
            },
            persona_config={"language_name": "English", "tts_voice": "en-US-Neural2-A"},
        )
