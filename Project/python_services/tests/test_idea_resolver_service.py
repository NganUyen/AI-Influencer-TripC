"""
Tests for IdeaResolverService (V3.1 Gate 2 - Idea Resolution Quality).

V3.1 Fix 6: Gate 2 tests belong here, NOT in test_recorded_demo_failure_policy.py.

Gate 2 tests:
- Hard precedence: official_name > user_video_thesis > video consistency
- Catalog gate: has_official_source OR has_fallback_grounded (Fix 1)
- idea_confidence calculation
- All idea_source scenarios
"""

import pytest

from services.contracts import (
    GroundedFeatureContract,
    GroundingAuditContract,
    OfficialFeatureCatalogContract,
    OfficialFeatureContract,
    ResolvedIdeaContract,
    TimelineStepContract,
)
from services.idea_resolver_service import IdeaResolverService


@pytest.fixture
def resolver():
    """Create IdeaResolverService instance."""
    return IdeaResolverService()


@pytest.fixture
def sample_timeline_steps():
    """Sample timeline steps showing feature prominence."""
    return [
        TimelineStepContract(
            timestamp_sec=0.0,
            segment_type="intro",
            narration_text="Welcome to our product demo",
            screen_activity="Logo appears",
            features_visible=[],
        ),
        TimelineStepContract(
            timestamp_sec=5.0,
            segment_type="feature_demo",
            narration_text="Check out real-time collaboration",
            screen_activity="User demonstrates collaborative editing",
            features_visible=["Real-time Collaboration", "Live Cursors"],
        ),
        TimelineStepContract(
            timestamp_sec=12.0,
            segment_type="feature_demo",
            narration_text="AI-powered suggestions make your work easier",
            screen_activity="AI suggestions panel shown",
            features_visible=["AI Suggestions"],
        ),
        TimelineStepContract(
            timestamp_sec=20.0,
            segment_type="outro",
            narration_text="Try it today!",
            screen_activity="CTA screen",
            features_visible=[],
        ),
    ]


@pytest.fixture
def official_catalog_full():
    """Official catalog with comprehensive feature coverage."""
    return OfficialFeatureCatalogContract(
        project_name="SuperApp",
        homepage_url="https://superapp.com",
        source_type="official_site",
        features=[
            OfficialFeatureContract(
                name="Real-time Collaboration",
                description="Work together with your team in real-time",
                prominence_score=0.9,
                source_url="https://superapp.com/features/collaboration",
            ),
            OfficialFeatureContract(
                name="AI-Powered Suggestions",
                description="Get intelligent suggestions as you work",
                prominence_score=0.7,
                source_url="https://superapp.com/features/ai",
            ),
            OfficialFeatureContract(
                name="Version Control",
                description="Track changes and revert when needed",
                prominence_score=0.5,
                source_url="https://superapp.com/features/versioning",
            ),
        ],
    )


@pytest.fixture
def grounded_features_all_official():
    """All features successfully grounded to official catalog."""
    return [
        GroundedFeatureContract(
            original_name="Real-time Collaboration",
            official_name="Real-time Collaboration",
            grounded=True,
            source="official_catalog",
            consistency_score=0.95,
            explanation="Matched official feature from catalog",
        ),
        GroundedFeatureContract(
            original_name="AI Suggestions",
            official_name="AI-Powered Suggestions",
            grounded=True,
            source="official_catalog",
            consistency_score=0.85,
            explanation="Mapped to official terminology",
        ),
    ]


@pytest.fixture
def grounding_audit_official():
    """Grounding audit showing official source was used."""
    return GroundingAuditContract(
        has_official_source=True,
        has_fallback_grounded=False,
        official_coverage_percent=100.0,
        fallback_coverage_percent=0.0,
        ungrounded_count=0,
    )


class TestIdeaResolverPrecedence:
    """Test hard precedence: official_name > user_video_thesis > video consistency."""

    def test_official_name_beats_user_thesis(
        self,
        resolver,
        sample_timeline_steps,
        official_catalog_full,
        grounded_features_all_official,
        grounding_audit_official,
    ):
        """Official catalog feature should override user's description (Fix 1)."""
        user_thesis = "This video is about AI features"

        resolved = resolver.resolve_main_idea(
            timeline_steps=sample_timeline_steps,
            official_catalog=official_catalog_full,
            grounding_audit=grounding_audit_official,
            grounded_features=grounded_features_all_official,
            user_video_thesis=user_thesis,
        )

        # Official name "Real-time Collaboration" should win (highest consistency)
        assert resolved.main_idea_name == "Real-time Collaboration"
        assert resolved.idea_source == "official_catalog_prominence"
        assert resolved.idea_confidence >= 0.8

    def test_user_thesis_beats_video_inference_when_no_catalog(
        self,
        resolver,
        sample_timeline_steps,
    ):
        """User thesis should override raw video inference when no catalog."""
        user_thesis = "Real-time teamwork features"

        # No catalog, all features ungrounded
        grounded_features_ungrounded = [
            GroundedFeatureContract(
                original_name="Collaboration",
                official_name=None,
                grounded=False,
                source="video_ocr",
                consistency_score=0.6,
                explanation="OCR-derived name",
            ),
        ]

        audit_no_catalog = GroundingAuditContract(
            has_official_source=False,
            has_fallback_grounded=False,
            official_coverage_percent=0.0,
            fallback_coverage_percent=0.0,
            ungrounded_count=1,
        )

        resolved = resolver.resolve_main_idea(
            timeline_steps=sample_timeline_steps,
            official_catalog=None,
            grounding_audit=audit_no_catalog,
            grounded_features=grounded_features_ungrounded,
            user_video_thesis=user_thesis,
        )

        assert (
            "teamwork" in resolved.main_idea_name.lower()
            or "collaboration" in resolved.main_idea_name.lower()
        )
        assert resolved.idea_source == "user_video_thesis"

    def test_video_consistency_fallback(
        self,
        resolver,
        sample_timeline_steps,
    ):
        """Video-inferred feature should be used when nothing else available."""
        grounded_features = [
            GroundedFeatureContract(
                original_name="Collaborative Editing",
                official_name=None,
                grounded=False,
                source="video_ocr",
                consistency_score=0.7,
                explanation="Appears in 3 timeline steps",
            ),
        ]

        audit = GroundingAuditContract(
            has_official_source=False,
            has_fallback_grounded=False,
            official_coverage_percent=0.0,
            fallback_coverage_percent=0.0,
            ungrounded_count=1,
        )

        resolved = resolver.resolve_main_idea(
            timeline_steps=sample_timeline_steps,
            official_catalog=None,
            grounding_audit=audit,
            grounded_features=grounded_features,
            user_video_thesis="",
        )

        assert resolved.main_idea_name == "Collaborative Editing"
        assert resolved.idea_source == "video_consistency"


class TestCatalogGate:
    """Test Fix 1: Catalog gate = has_official_source OR has_fallback_grounded."""

    def test_official_source_passes_gate(
        self,
        resolver,
        sample_timeline_steps,
        official_catalog_full,
        grounded_features_all_official,
        grounding_audit_official,
    ):
        """has_official_source=True should pass catalog gate."""
        resolved = resolver.resolve_main_idea(
            timeline_steps=sample_timeline_steps,
            official_catalog=official_catalog_full,
            grounding_audit=grounding_audit_official,
            grounded_features=grounded_features_all_official,
            user_video_thesis="",
        )

        assert resolved.idea_source in [
            "official_catalog_prominence",
            "official_catalog_consistency",
        ]
        assert resolved.idea_confidence >= 0.8

    def test_fallback_grounded_passes_gate(
        self,
        resolver,
        sample_timeline_steps,
    ):
        """has_fallback_grounded=True should pass catalog gate (Fix 1)."""
        grounded_features_fallback = [
            GroundedFeatureContract(
                original_name="Real-time sync",
                official_name="Real-time Synchronization",
                grounded=True,
                source="openclaw_fallback",
                consistency_score=0.8,
                explanation="Grounded via fallback OpenClaw",
            ),
        ]

        audit_fallback = GroundingAuditContract(
            has_official_source=False,
            has_fallback_grounded=True,
            official_coverage_percent=0.0,
            fallback_coverage_percent=100.0,
            ungrounded_count=0,
        )

        resolved = resolver.resolve_main_idea(
            timeline_steps=sample_timeline_steps,
            official_catalog=None,
            grounding_audit=audit_fallback,
            grounded_features=grounded_features_fallback,
            user_video_thesis="",
        )

        # Fallback grounded features should still be used with high confidence
        assert resolved.main_idea_name == "Real-time Synchronization"
        assert resolved.idea_source in [
            "fallback_grounded_consistency",
            "official_catalog_consistency",
        ]

    def test_no_catalog_no_fallback_fails_gate(
        self,
        resolver,
        sample_timeline_steps,
    ):
        """Neither official nor fallback should result in low confidence."""
        grounded_features_none = [
            GroundedFeatureContract(
                original_name="Some Feature",
                official_name=None,
                grounded=False,
                source="video_ocr",
                consistency_score=0.5,
                explanation="Ungrounded",
            ),
        ]

        audit_none = GroundingAuditContract(
            has_official_source=False,
            has_fallback_grounded=False,
            official_coverage_percent=0.0,
            fallback_coverage_percent=0.0,
            ungrounded_count=1,
        )

        resolved = resolver.resolve_main_idea(
            timeline_steps=sample_timeline_steps,
            official_catalog=None,
            grounding_audit=audit_none,
            grounded_features=grounded_features_none,
            user_video_thesis="",
        )

        # Should still resolve but with lower confidence
        assert resolved.idea_confidence < 0.7
        assert resolved.idea_source in ["video_consistency", "timeline_inference"]


class TestIdeaConfidence:
    """Test idea_confidence (Gate 2) calculation."""

    def test_high_confidence_official_catalog(
        self,
        resolver,
        sample_timeline_steps,
        official_catalog_full,
        grounded_features_all_official,
        grounding_audit_official,
    ):
        """Official catalog with high consistency = high confidence."""
        resolved = resolver.resolve_main_idea(
            timeline_steps=sample_timeline_steps,
            official_catalog=official_catalog_full,
            grounding_audit=grounding_audit_official,
            grounded_features=grounded_features_all_official,
            user_video_thesis="",
        )

        assert resolved.idea_confidence >= 0.8
        assert resolved.idea_confidence <= 1.0

    def test_medium_confidence_partial_grounding(
        self,
        resolver,
        sample_timeline_steps,
    ):
        """Partial grounding should yield medium confidence."""
        grounded_features_mixed = [
            GroundedFeatureContract(
                original_name="Feature A",
                official_name="Official Feature A",
                grounded=True,
                source="official_catalog",
                consistency_score=0.8,
                explanation="Grounded",
            ),
            GroundedFeatureContract(
                original_name="Feature B",
                official_name=None,
                grounded=False,
                source="video_ocr",
                consistency_score=0.4,
                explanation="Ungrounded",
            ),
        ]

        audit_partial = GroundingAuditContract(
            has_official_source=True,
            has_fallback_grounded=False,
            official_coverage_percent=50.0,
            fallback_coverage_percent=0.0,
            ungrounded_count=1,
        )

        catalog = OfficialFeatureCatalogContract(
            project_name="TestApp",
            homepage_url="https://test.com",
            source_type="official_site",
            features=[
                OfficialFeatureContract(
                    name="Official Feature A",
                    description="Test",
                    prominence_score=0.8,
                    source_url="https://test.com/a",
                ),
            ],
        )

        resolved = resolver.resolve_main_idea(
            timeline_steps=sample_timeline_steps,
            official_catalog=catalog,
            grounding_audit=audit_partial,
            grounded_features=grounded_features_mixed,
            user_video_thesis="",
        )

        assert 0.5 <= resolved.idea_confidence < 0.8

    def test_low_confidence_no_grounding(
        self,
        resolver,
        sample_timeline_steps,
    ):
        """No grounding should yield low confidence."""
        grounded_features_none = [
            GroundedFeatureContract(
                original_name="Unknown Feature",
                official_name=None,
                grounded=False,
                source="video_ocr",
                consistency_score=0.3,
                explanation="Low quality OCR",
            ),
        ]

        audit_none = GroundingAuditContract(
            has_official_source=False,
            has_fallback_grounded=False,
            official_coverage_percent=0.0,
            fallback_coverage_percent=0.0,
            ungrounded_count=1,
        )

        resolved = resolver.resolve_main_idea(
            timeline_steps=sample_timeline_steps,
            official_catalog=None,
            grounding_audit=audit_none,
            grounded_features=grounded_features_none,
            user_video_thesis="",
        )

        assert resolved.idea_confidence < 0.5


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_inputs(self, resolver):
        """Empty inputs should still produce a result."""
        resolved = resolver.resolve_main_idea(
            timeline_steps=[],
            official_catalog=None,
            grounding_audit=GroundingAuditContract(
                has_official_source=False,
                has_fallback_grounded=False,
                official_coverage_percent=0.0,
                fallback_coverage_percent=0.0,
                ungrounded_count=0,
            ),
            grounded_features=[],
            user_video_thesis="",
        )

        assert isinstance(resolved, ResolvedIdeaContract)
        assert resolved.main_idea_name
        assert resolved.idea_confidence < 0.5

    def test_user_thesis_only(self, resolver):
        """User thesis alone should produce high-confidence result."""
        resolved = resolver.resolve_main_idea(
            timeline_steps=[],
            official_catalog=None,
            grounding_audit=GroundingAuditContract(
                has_official_source=False,
                has_fallback_grounded=False,
                official_coverage_percent=0.0,
                fallback_coverage_percent=0.0,
                ungrounded_count=0,
            ),
            grounded_features=[],
            user_video_thesis="Advanced data visualization",
        )

        assert (
            "visualization" in resolved.main_idea_name.lower()
            or "data" in resolved.main_idea_name.lower()
        )
        assert resolved.idea_source == "user_video_thesis"
        assert resolved.idea_confidence >= 0.7
