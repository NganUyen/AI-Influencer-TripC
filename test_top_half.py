import asyncio
import os
import sys

from services.script_service import ScriptService
from services.contracts import ApprovedProductionPackageContract

async def test_top_half():
    print("Testing Top Half Scripts...")
    
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
            "tone_resolved": "test"
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
                    "narration_draft": "I found this crazy tool that automates everything.",
                    "onscreen_text": "Crazy Tool",
                    "visual_concept": "Website hero section"
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
                    "narration_draft": "It can even write scripts for you.",
                    "onscreen_text": "Code faster",
                    "visual_concept": "A futuristic glowing monitor showing python code"
                }
            ]
        }
    }
    
    svc = ScriptService()
    try:
        script = await svc.generate_script_from_package(
            app_name="Playwright Demo",
            package={"approved_beat_sheet": package["beat_sheet"]},
            persona_config={"language_name": "English"}
        )
        print("Generated ScriptContract:")
        print(script.model_dump_json(indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath("Project/python_services"))
    asyncio.run(test_top_half())
