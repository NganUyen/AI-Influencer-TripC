from temporalio import activity
from typing import Dict, Any

@activity.defn(name="generate_creative_package_activity")
async def generate_creative_package_activity(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Invokes CreativeDirectorService to generate concept and beat sheet
    from a basic idea.
    """
    from services.creative_director_service import CreativeDirectorService
    import json
    
    idea = config.get("idea")
    reference_url = config.get("reference_url")
    persona_id = config.get("persona_id")
    
    svc = CreativeDirectorService()
    
    # 1. Build Concept
    concept_payload = {
        "persona_id": persona_id,
        "idea_brief": idea,
        "reference_url": reference_url,
        "video_goal_hint": "feature_demo",
        "market_context": "Global"
    }
    concept_brief = await svc.build_concept_brief(concept_payload)
    
    # 2. Build BeatSheet (Top-Half structure)
    beat_sheet = await svc.build_beat_sheet(concept_brief)
    
    # 3. Assemble and return
    package = svc.build_approved_package(
        concept_brief=concept_brief,
        beat_sheet=beat_sheet,
        persona_snapshot={"persona_id": persona_id}
    )
    
    # Important: Convert pydantic models to dict so they serialize directly in Temporal
    return {
        "approved_package": package.model_dump()
    }
