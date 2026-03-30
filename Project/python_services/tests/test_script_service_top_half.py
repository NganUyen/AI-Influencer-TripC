import pytest
from services.script_service import ScriptService


@pytest.mark.asyncio
async def test_generate_script_from_package():
    # Provide a simple mock package matching ApprovedProductionPackageContract
    package = {
        "concept_brief": {
            "persona_id": "test_persona",
            "feature_focus": "test",
            "video_goal": "feature_demo",
            "audience": "test",
            "angle": "test",
            "platform": "tiktok",
            "cta": "Link in bio",
            "reference_url": "https://example.com",
            "access_level": "public_page_only",
            "source_summary": "test",
            "tone_resolved": "test",
        },
        "beat_sheet": {
            "beats": [
                {
                    "idx": 1,
                    "purpose": "hook",
                    "bottom_half_message": "Look at this tool!",
                    "top_half_source_type": "public_page_capture",
                    "top_half_target": "Landing Page",
                    "top_half_capture_hint": "Scroll hero section",
                    "source_ref": "https://playwright.dev",
                    "overlay_text": "Mind blown",
                    "duration_sec": 5,
                },
                {
                    "idx": 2,
                    "purpose": "feature_demo",
                    "bottom_half_message": "It lets you write scripts.",
                    "top_half_source_type": "ai_visual_fallback",
                    "top_half_target": "Abstract Code",
                    "top_half_capture_hint": "none",
                    "overlay_text": "Write code",
                    "duration_sec": 5,
                },
            ]
        },
    }

    svc = ScriptService()
    script = await svc.generate_script_from_package(
        app_name="Playwright Demo",
        package=package,
        persona_config={"language_name": "English"},
    )

    dumped = script.model_dump()
    print("SCRIPT DUMP:", dumped)

    assert len(dumped["scenes"]) == 2

    # Assert scene 1 has the right public_page_capture setup
    scene1 = dumped["scenes"][0]
    assert scene1["top_half_source_type"] == "public_page_capture"
    assert scene1["source_ref"] == "https://playwright.dev"
    assert scene1["prompt"] == "Landing Page"
    assert scene1["narration_text"] == "Look at this tool!"

    # Assert scene 2 is normalized to Playwright public capture
    scene2 = dumped["scenes"][1]
    assert scene2["top_half_source_type"] == "public_page_capture"
    assert scene2["source_ref"] == "https://example.com"
    assert scene2["prompt"] == "Abstract Code"
    assert scene2["narration_text"] == "It lets you write scripts."

    print("generate_script_from_package passed successfully.")


@pytest.mark.asyncio
async def test_generate_script_from_package_falls_back_to_concept_reference_url():
    package = {
        "concept_brief": {
            "persona_id": "test_persona",
            "feature_focus": "test",
            "video_goal": "feature_demo",
            "audience": "test",
            "angle": "test",
            "platform": "tiktok",
            "cta": "Link in bio",
            "reference_url": "https://example.com/root",
            "access_level": "public_page_only",
            "source_summary": "test",
            "tone_resolved": "test",
        },
        "beat_sheet": {
            "beats": [
                {
                    "idx": 1,
                    "purpose": "hook",
                    "bottom_half_message": "Look at this tool!",
                    "top_half_source_type": "public_page_capture",
                    "top_half_target": "Landing Page",
                    "top_half_capture_hint": "Scroll hero section",
                    "source_ref": None,
                    "overlay_text": "Mind blown",
                    "duration_sec": 5,
                }
            ]
        },
    }

    svc = ScriptService()
    script = await svc.generate_script_from_package(
        app_name="Playwright Demo",
        package=package,
        persona_config={"language_name": "English"},
    )

    scene = script.model_dump()["scenes"][0]
    assert scene["top_half_source_type"] == "public_page_capture"
    assert scene["source_ref"] == "https://example.com/root"
    assert scene["narration_text"] == "Look at this tool!"
