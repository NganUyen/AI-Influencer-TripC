import asyncio
import os
import sys

# Add python_services to path first
sys.path.insert(0, os.path.abspath("Project/python_services"))

# Mock config module before any imports
class MockSettings:
    TELEGRAM_BOT_TOKEN = 'dummy'
    SUPABASE_STORAGE_BUCKET = 'dummy'
    STORAGE_PROVIDER = 'local'
    MEDIA_STORAGE_BUCKET = 'dummy'
    POSTIZ_API_KEY = 'dummy'
    POSTIZ_API_URL = 'http://localhost'

class MockConfigSettings:
    settings = MockSettings()

sys.modules['config'] = type(sys)('config')
sys.modules['config.settings'] = MockConfigSettings
sys.modules['config'].settings = MockSettings()

sys.modules['services.openclaw_service'] = type('openclaw_service', (), {'OpenClawService': object})
sys.modules['services.telegram_service'] = type('telegram_service', (), {'TelegramService': object})
sys.modules['telegram'] = type('telegram', (), {'Bot': object, 'InlineKeyboardButton': object, 'InlineKeyboardMarkup': object})

from services.script_service import ScriptService

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
                    "top_half_capture_hint": "scroll",
                    "source_ref": None,  # Will use reference_url from concept_brief
                    "overlay_text": "Mind blown",
                    "duration_sec": 5,
                },
                {
                    "idx": 2,
                    "purpose": "feature_demo",
                    "bottom_half_message": "It lets you write scripts.",
                    "top_half_source_type": "ai_visual_fallback",
                    "top_half_target": "Abstract Code",
                    "top_half_capture_hint": "static",
                    "overlay_text": "Write code",
                    "duration_sec": 5,
                }
            ]
        }
    }
    
    svc = ScriptService()
    try:
        script = await svc.generate_script_from_package(
            app_name="Playwright Demo",
            package=package,
            persona_config={"language_name": "English"}
        )
        print("Generated ScriptContract:")
        print(script.model_dump_json(indent=2))
        
        # Verify source_ref is correctly populated
        for scene in script.scenes:
            print(f"\nScene {scene.id}:")
            print(f"  top_half_source_type: {scene.top_half_source_type}")
            print(f"  source_ref: {scene.source_ref}")
            if scene.top_half_source_type == "public_page_capture" and not scene.source_ref:
                print("  WARNING: public_page_capture but no source_ref!")
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_top_half())
