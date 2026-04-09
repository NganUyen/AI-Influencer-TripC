import pytest

from services.contracts import ConceptBriefContract
from services.creative_director_service import CreativeDirectorService


class _StubOpenClawService:
    response = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def execute_task(self, task_type, prompt, user_id, context=None):
        return self.response


def _sample_collected():
    return {
        "persona_id": "minh_vn",
        "idea_brief": "Introduce the AI itinerary planner for young travelers.",
        "feature_focus": "AI itinerary planner",
        "video_goal": "feature_demo",
        "audience": "travelers aged 22-35",
        "cta": "Try TripC free",
        "reference_url": "https://tripc.ai",
        "access_level": "public_page_only",
        "platform": "tiktok",
    }


def _sample_persona():
    return {
        "persona_id": "minh_vn",
        "display_name": "Minh VN",
        "language": "Vietnamese",
        "tts_voice": "vi-VN-Neural2-A",
        "tone_default": "confident",
    }


@pytest.mark.asyncio
async def test_build_concept_brief_accepts_valid_structured_output(monkeypatch):
    _StubOpenClawService.response = {
        "persona_id": "minh_vn",
        "creative_input_mode": "idea_brief",
        "feature_focus": "AI itinerary planner",
        "video_goal": "feature_demo",
        "audience": "travelers aged 22-35",
        "angle": "problem_solution",
        "platform": "tiktok",
        "cta": "Try TripC free",
        "reference_url": "https://tripc.ai",
        "access_level": "public_page_only",
        "source_summary": "TripC is presented as a travel planning product.",
        "tone_resolved": "confident",
    }
    monkeypatch.setattr(
        CreativeDirectorService,
        "_openclaw_service_class",
        _StubOpenClawService,
    )

    concept = await CreativeDirectorService.build_concept_brief(
        _sample_collected(),
        _sample_persona(),
    )

    assert concept.persona_id == "minh_vn"
    assert concept.video_goal == "feature_demo"
    assert concept.tone_resolved == "confident"


@pytest.mark.asyncio
async def test_build_concept_brief_falls_back_when_output_drifts_from_collected(
    monkeypatch,
):
    _StubOpenClawService.response = {
        "persona_id": "minh_vn",
        "creative_input_mode": "idea_brief",
        "feature_focus": "restaurant finder",
        "video_goal": "conversion",  # Changed from "awareness" (no longer supported)
        "audience": "general audience",
        "angle": "problem_solution",
        "platform": "tiktok",
        "cta": "Learn more",
        "reference_url": "https://tripc.ai",
        "access_level": "public_page_only",
        "source_summary": "TripC is presented as a travel planning product.",
        "tone_resolved": "confident",
    }
    monkeypatch.setattr(
        CreativeDirectorService,
        "_openclaw_service_class",
        _StubOpenClawService,
    )

    concept = await CreativeDirectorService.build_concept_brief(
        _sample_collected(),
        _sample_persona(),
    )

    assert concept.feature_focus == "AI itinerary planner"
    assert concept.video_goal == "feature_demo"
    assert concept.audience == "travelers aged 22-35"
    assert concept.cta == "Try TripC free"


@pytest.mark.asyncio
async def test_build_concept_brief_falls_back_on_public_page_overclaim(monkeypatch):
    _StubOpenClawService.response = {
        "persona_id": "minh_vn",
        "creative_input_mode": "idea_brief",
        "feature_focus": "AI itinerary planner",
        "video_goal": "feature_demo",
        "audience": "travelers aged 22-35",
        "angle": "problem_solution",
        "platform": "tiktok",
        "cta": "Try TripC free",
        "reference_url": "https://tripc.ai",
        "access_level": "public_page_only",
        "source_summary": "TripC shows a logged-in dashboard with private workspace planning tools.",
        "tone_resolved": "confident",
    }
    monkeypatch.setattr(
        CreativeDirectorService,
        "_openclaw_service_class",
        _StubOpenClawService,
    )

    concept = await CreativeDirectorService.build_concept_brief(
        _sample_collected(),
        _sample_persona(),
    )

    assert concept.access_level == "public_page_only"
    assert "logged-in" not in concept.source_summary.lower()


@pytest.mark.asyncio
async def test_build_concept_brief_falls_back_on_invalid_output(monkeypatch):
    _StubOpenClawService.response = {"text": "not structured"}
    monkeypatch.setattr(
        CreativeDirectorService,
        "_openclaw_service_class",
        _StubOpenClawService,
    )

    concept = await CreativeDirectorService.build_concept_brief(
        _sample_collected(),
        _sample_persona(),
    )

    assert concept.reference_url == "https://tripc.ai"
    assert concept.source_summary


@pytest.mark.asyncio
async def test_build_beat_sheet_enforces_taxonomy_and_count(monkeypatch):
    _StubOpenClawService.response = {
        "concept_id": "concept_bad",
        "beats": [
            {
                "idx": 1,
                "purpose": "invented_purpose",
                "bottom_half_message": "Bad beat",
                "top_half_source_type": "public_page_capture",
                "top_half_target": "hero_section",
                "top_half_capture_hint": "Show hero",
                "overlay_text": "Bad",
                "duration_sec": 4,
            }
        ]
        * 7,
    }
    monkeypatch.setattr(
        CreativeDirectorService,
        "_openclaw_service_class",
        _StubOpenClawService,
    )

    concept = ConceptBriefContract(
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
    )

    with pytest.raises(Exception):
        await CreativeDirectorService.build_beat_sheet(concept, _sample_persona())


@pytest.mark.asyncio
async def test_build_beat_sheet_rejects_weak_structure_or_public_overclaim(monkeypatch):
    _StubOpenClawService.response = {
        "concept_id": "concept_bad",
        "beats": [
            {
                "idx": 1,
                "purpose": "problem",
                "bottom_half_message": "Planning takes too long.",
                "top_half_source_type": "public_page_capture",
                "top_half_target": "hero_section",
                "top_half_capture_hint": "Show hero",
                "overlay_text": "Too slow",
                "duration_sec": 4,
            },
            {
                "idx": 2,
                "purpose": "benefit",
                "bottom_half_message": "TripC helps travelers move faster.",
                "top_half_source_type": "authenticated_capture_later",
                "top_half_target": "dashboard",
                "top_half_capture_hint": "Show logged-in dashboard",
                "overlay_text": "Move faster",
                "duration_sec": 4,
            },
            {
                "idx": 3,
                "purpose": "feature_demo",
                "bottom_half_message": "It gives you suggestions.",
                "top_half_source_type": "public_page_capture",
                "top_half_target": "feature_block",
                "top_half_capture_hint": "Show feature block",
                "overlay_text": "Suggestions",
                "duration_sec": 4,
            },
            {
                "idx": 4,
                "purpose": "benefit",
                "bottom_half_message": "This saves time.",
                "top_half_source_type": "public_page_capture",
                "top_half_target": "cta_section",
                "top_half_capture_hint": "Show CTA",
                "overlay_text": "Save time",
                "duration_sec": 4,
            },
            {
                "idx": 5,
                "purpose": "cta",
                "bottom_half_message": "Try TripC free.",
                "top_half_source_type": "public_page_capture",
                "top_half_target": "cta_section",
                "top_half_capture_hint": "Show CTA",
                "overlay_text": "Try now",
                "duration_sec": 4,
            },
        ],
    }
    monkeypatch.setattr(
        CreativeDirectorService,
        "_openclaw_service_class",
        _StubOpenClawService,
    )

    concept = ConceptBriefContract(
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
    )

    with pytest.raises(Exception):
        await CreativeDirectorService.build_beat_sheet(concept, _sample_persona())


@pytest.mark.asyncio
async def test_build_beat_sheet_rejects_outputs_that_ignore_feature_focus(monkeypatch):
    _StubOpenClawService.response = {
        "concept_id": "concept_bad",
        "beats": [
            {
                "idx": 1,
                "purpose": "hook",
                "bottom_half_message": "Need better restaurant deals?",
                "top_half_source_type": "public_page_capture",
                "top_half_target": "pricing_section",
                "top_half_capture_hint": "Show pricing",
                "overlay_text": "Save more",
                "duration_sec": 4,
            },
            {
                "idx": 2,
                "purpose": "problem",
                "bottom_half_message": "Travelers waste money.",
                "top_half_source_type": "public_page_capture",
                "top_half_target": "pricing_section",
                "top_half_capture_hint": "Show pricing",
                "overlay_text": "Waste less",
                "duration_sec": 4,
            },
            {
                "idx": 3,
                "purpose": "benefit",
                "bottom_half_message": "This helps with restaurant choices.",
                "top_half_source_type": "public_page_capture",
                "top_half_target": "food_section",
                "top_half_capture_hint": "Show food section",
                "overlay_text": "Food picks",
                "duration_sec": 4,
            },
            {
                "idx": 4,
                "purpose": "proof",
                "bottom_half_message": "People enjoy better meals.",
                "top_half_source_type": "public_page_capture",
                "top_half_target": "testimonials",
                "top_half_capture_hint": "Show testimonials",
                "overlay_text": "Loved by users",
                "duration_sec": 4,
            },
            {
                "idx": 5,
                "purpose": "cta",
                "bottom_half_message": "Try it now.",
                "top_half_source_type": "public_page_capture",
                "top_half_target": "cta_section",
                "top_half_capture_hint": "Show CTA",
                "overlay_text": "Try now",
                "duration_sec": 4,
            },
        ],
    }
    monkeypatch.setattr(
        CreativeDirectorService,
        "_openclaw_service_class",
        _StubOpenClawService,
    )

    concept = ConceptBriefContract(
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
    )

    with pytest.raises(Exception):
        await CreativeDirectorService.build_beat_sheet(concept, _sample_persona())


@pytest.mark.asyncio
async def test_build_beat_sheet_changes_when_brief_changes_direction(monkeypatch):
    responses = [
        {
            "concept_id": "concept_itinerary",
            "beats": [
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
                    "bottom_half_message": "Too many tabs for itineraries.",
                    "top_half_source_type": "public_page_capture",
                    "top_half_target": "planner_intro",
                    "top_half_capture_hint": "Show itinerary planning intro",
                    "overlay_text": "Too many tabs",
                    "duration_sec": 4,
                },
                {
                    "idx": 3,
                    "purpose": "solution_intro",
                    "bottom_half_message": "TripC organizes your itinerary planning.",
                    "top_half_source_type": "public_page_capture",
                    "top_half_target": "itinerary_planner_section",
                    "top_half_capture_hint": "Show itinerary planner section",
                    "overlay_text": "AI itinerary planner",
                    "duration_sec": 4,
                },
                {
                    "idx": 4,
                    "purpose": "feature_demo",
                    "bottom_half_message": "The AI itinerary planner suggests routes fast.",
                    "top_half_source_type": "public_page_capture",
                    "top_half_target": "itinerary_planner_section",
                    "top_half_capture_hint": "Show itinerary suggestions",
                    "overlay_text": "Smart itinerary",
                    "duration_sec": 4,
                },
                {
                    "idx": 5,
                    "purpose": "cta",
                    "bottom_half_message": "Try TripC free today.",
                    "top_half_source_type": "public_page_capture",
                    "top_half_target": "cta_section",
                    "top_half_capture_hint": "Show CTA",
                    "overlay_text": "Try now",
                    "duration_sec": 4,
                },
            ],
        },
        {
            "concept_id": "concept_discovery",
            "beats": [
                {
                    "idx": 1,
                    "purpose": "hook",
                    "bottom_half_message": "Still wasting time finding restaurants?",
                    "top_half_source_type": "public_page_capture",
                    "top_half_target": "hero_section",
                    "top_half_capture_hint": "Show hero section",
                    "overlay_text": "Find spots faster",
                    "duration_sec": 4,
                },
                {
                    "idx": 2,
                    "purpose": "problem",
                    "bottom_half_message": "Travelers miss good local food options.",
                    "top_half_source_type": "public_page_capture",
                    "top_half_target": "food_discovery_intro",
                    "top_half_capture_hint": "Show discovery intro",
                    "overlay_text": "Miss less",
                    "duration_sec": 4,
                },
                {
                    "idx": 3,
                    "purpose": "solution_intro",
                    "bottom_half_message": "TripC highlights restaurant discovery options.",
                    "top_half_source_type": "public_page_capture",
                    "top_half_target": "restaurant_discovery_section",
                    "top_half_capture_hint": "Show restaurant section",
                    "overlay_text": "Restaurant discovery",
                    "duration_sec": 4,
                },
                {
                    "idx": 4,
                    "purpose": "feature_demo",
                    "bottom_half_message": "You can discover restaurants faster inside TripC.",
                    "top_half_source_type": "public_page_capture",
                    "top_half_target": "restaurant_discovery_section",
                    "top_half_capture_hint": "Show discovery cards",
                    "overlay_text": "Local picks",
                    "duration_sec": 4,
                },
                {
                    "idx": 5,
                    "purpose": "cta",
                    "bottom_half_message": "Try TripC free today.",
                    "top_half_source_type": "public_page_capture",
                    "top_half_target": "cta_section",
                    "top_half_capture_hint": "Show CTA",
                    "overlay_text": "Try now",
                    "duration_sec": 4,
                },
            ],
        },
    ]

    class _SequentialStubOpenClawService(_StubOpenClawService):
        async def execute_task(self, task_type, prompt, user_id, context=None):
            return responses.pop(0)

    monkeypatch.setattr(
        CreativeDirectorService,
        "_openclaw_service_class",
        _SequentialStubOpenClawService,
    )

    itinerary_concept = ConceptBriefContract(
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
    )
    discovery_concept = ConceptBriefContract(
        persona_id="minh_vn",
        feature_focus="restaurant discovery",
        video_goal="feature_demo",
        audience="travelers aged 22-35",
        angle="problem_solution",
        platform="tiktok",
        cta="Try TripC free",
        reference_url="https://tripc.ai",
        access_level="public_page_only",
        source_summary="TripC is a travel planning product.",
        tone_resolved="confident",
    )

    itinerary_beats = await CreativeDirectorService.build_beat_sheet(
        itinerary_concept,
        _sample_persona(),
    )
    discovery_beats = await CreativeDirectorService.build_beat_sheet(
        discovery_concept,
        _sample_persona(),
    )

    itinerary_text = " ".join(
        beat.bottom_half_message for beat in itinerary_beats.beats
    ).lower()
    discovery_text = " ".join(
        beat.bottom_half_message for beat in discovery_beats.beats
    ).lower()

    assert "itinerary" in itinerary_text
    assert "restaurant" not in itinerary_text
    assert "restaurant" in discovery_text
