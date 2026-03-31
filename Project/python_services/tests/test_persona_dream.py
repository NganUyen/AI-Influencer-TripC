
import asyncio
import json
import logging
import sys
from typing import Dict, Any, Optional

# Add the project root to sys.path
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.persona_creator import PersonaCreatorSkill
from skills.base import SkillSession, SkillStatus

# Mock AIService
class MockAIService:
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def generate_text(self, prompt, **kwargs):
        # Return a simulated JSON response
        return json.dumps({
            "display_name": "Test Persona",
            "persona_id": "test-id",
            "appearance": "A tall person with blue hair and a futuristic suit."
        })

async def test_dream_flow():
    print("🚀 Starting Persona Dream Logic Test...")
    
    # Setup initial session
    session = PersonaCreatorSkill.initial_session()
    session.collected["dream_brief"] = "A futuristic blue-haired scientist"
    session.artifacts["creation_mode"] = "dream"
    
    # 1. First Execution (Triggering Dream)
    print("\n--- Step 1: Triggering AI Dream ---")
    # We mock the AIService within the skill's execute block by monkeypatching
    import services.ai_service
    services.ai_service.AIService = MockAIService
    
    result = await PersonaCreatorSkill.execute(session, "http://localhost:8000", None)
    
    if result.success and result.next_step == "confirm_dream":
        print("✅ SUCCESS: AI Dream triggered and returned confirmation step.")
        print(f"Identity: {result.session.collected.get('persona_id')}")
        print(f"Summary: {result.session.artifacts.get('dream_summary')[:50]}...")
    else:
        print(f"❌ FAILED: Unexpected result status: {result.next_step}")
        return

    # 2. Transition to Save (Simulate user clicking 'Use & Continue')
    print("\n--- Step 2: Simulating 'Use & Continue' action ---")
    session = result.session
    session.step_key = "save"
    # Note: In reality, handle_action sets step_key = 'save' 
    
    # This should hit the 'Persistence Guard' and proceed to the POST block (which will fail here, but we check if it HITS it)
    try:
        result = await PersonaCreatorSkill.execute(session, "http://localhost:8000", None)
        print(f"Next step after save attempt: {result.next_step}")
    except Exception as e:
        # It's expected to fail here because we passed None for http_client
        print(f"✅ SUCCESS: Reached backend block as expected (failed on http_client: {e})")

    print("\n✨ Test Complete!")

if __name__ == "__main__":
    asyncio.run(test_dream_flow())
