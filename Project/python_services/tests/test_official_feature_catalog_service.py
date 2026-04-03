"""
Tests for OfficialFeatureCatalogService (V3.1 official documentation parsing).

Tests:
- Feature extraction from URLs
- Deduplication logic
- Merge strategy
- Fallback handling when extraction fails
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from services.contracts import OfficialFeatureCatalogContract, OfficialFeatureContract
from services.official_feature_catalog_service import OfficialFeatureCatalogService


@pytest.fixture
def mock_ai_service():
    """Mock AIService for GPT-4o mini calls."""
    mock = MagicMock()
    mock.analyze_text_structured = AsyncMock()
    return mock


@pytest.fixture
def service(mock_ai_service):
    """Create OfficialFeatureCatalogService with mocked AIService."""
    return OfficialFeatureCatalogService(ai_service=mock_ai_service)


class TestFeatureExtraction:
    """Test feature extraction from HTML content."""

    @pytest.mark.asyncio
    async def test_successful_extraction(self, service, mock_ai_service):
        """Successful extraction should return features with prominence scores."""
        mock_ai_service.analyze_text_structured.return_value = {
            "features": [
                {
                    "name": "Real-time Collaboration",
                    "description": "Work together with your team in real-time",
                    "prominence_score": 0.9,
                },
                {
                    "name": "Version Control",
                    "description": "Track changes and revert when needed",
                    "prominence_score": 0.7,
                },
            ]
        }

        catalog = await service.build_catalog(
            homepage_url="https://example.com",
            feature_urls=[
                "https://example.com/features/collaboration",
                "https://example.com/features/versioning",
            ],
            project_name="TestApp",
        )

        assert isinstance(catalog, OfficialFeatureCatalogContract)
        assert catalog.project_name == "TestApp"
        assert catalog.homepage_url == "https://example.com"
        assert catalog.source_type == "official_site"
        assert len(catalog.features) == 2
        assert catalog.features[0].name == "Real-time Collaboration"
        assert catalog.features[0].prominence_score == 0.9

    @pytest.mark.asyncio
    async def test_deduplication_by_name(self, service, mock_ai_service):
        """Duplicate feature names should be merged."""
        # Simulate two URLs returning overlapping features
        responses = [
            {
                "features": [
                    {
                        "name": "Real-time Collaboration",
                        "description": "First description",
                        "prominence_score": 0.9,
                    },
                    {
                        "name": "AI Suggestions",
                        "description": "AI-powered help",
                        "prominence_score": 0.7,
                    },
                ]
            },
            {
                "features": [
                    {
                        "name": "Real-time Collaboration",  # Duplicate
                        "description": "Second description (more detailed)",
                        "prominence_score": 0.8,
                    },
                    {
                        "name": "Version Control",
                        "description": "Track changes",
                        "prominence_score": 0.6,
                    },
                ]
            },
        ]

        call_count = 0

        async def mock_analyze(*args, **kwargs):
            nonlocal call_count
            result = responses[call_count % len(responses)]
            call_count += 1
            return result

        mock_ai_service.analyze_text_structured = mock_analyze

        catalog = await service.build_catalog(
            homepage_url="https://example.com",
            feature_urls=[
                "https://example.com/page1",
                "https://example.com/page2",
            ],
            project_name="TestApp",
        )

        # Should have 3 unique features (deduped "Real-time Collaboration")
        assert len(catalog.features) == 3
        feature_names = [f.name for f in catalog.features]
        assert "Real-time Collaboration" in feature_names
        assert "AI Suggestions" in feature_names
        assert "Version Control" in feature_names

        # Duplicate should keep higher prominence score or longer description
        collab_feature = next(
            f for f in catalog.features if f.name == "Real-time Collaboration"
        )
        assert collab_feature.prominence_score == 0.9  # Max of 0.9 and 0.8

    @pytest.mark.asyncio
    async def test_prominence_score_normalization(self, service, mock_ai_service):
        """Prominence scores should be normalized to [0, 1]."""
        mock_ai_service.analyze_text_structured.return_value = {
            "features": [
                {
                    "name": "Feature A",
                    "description": "Test",
                    "prominence_score": 1.5,  # Over 1.0
                },
                {
                    "name": "Feature B",
                    "description": "Test",
                    "prominence_score": -0.2,  # Negative
                },
            ]
        }

        catalog = await service.build_catalog(
            homepage_url="https://example.com",
            feature_urls=["https://example.com/features"],
            project_name="TestApp",
        )

        # Scores should be clamped to [0, 1]
        assert 0.0 <= catalog.features[0].prominence_score <= 1.0
        assert 0.0 <= catalog.features[1].prominence_score <= 1.0


class TestFallbackHandling:
    """Test fallback behavior when extraction fails."""

    @pytest.mark.asyncio
    async def test_single_url_failure_continues(self, service, mock_ai_service):
        """Single URL failure should not abort entire catalog build."""
        call_count = 0

        async def mock_analyze_with_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # First URL fails
                raise Exception("Timeout")
            return {
                "features": [
                    {
                        "name": "Feature from URL 2",
                        "description": "Success",
                        "prominence_score": 0.8,
                    }
                ]
            }

        mock_ai_service.analyze_text_structured = mock_analyze_with_failure

        catalog = await service.build_catalog(
            homepage_url="https://example.com",
            feature_urls=[
                "https://example.com/fail",
                "https://example.com/success",
            ],
            project_name="TestApp",
        )

        # Should have 1 feature from successful URL
        assert len(catalog.features) == 1
        assert catalog.features[0].name == "Feature from URL 2"

    @pytest.mark.asyncio
    async def test_all_urls_fail_returns_empty_catalog(self, service, mock_ai_service):
        """All URLs failing should return empty catalog, not crash."""
        mock_ai_service.analyze_text_structured.side_effect = Exception("All failed")

        catalog = await service.build_catalog(
            homepage_url="https://example.com",
            feature_urls=[
                "https://example.com/url1",
                "https://example.com/url2",
            ],
            project_name="TestApp",
        )

        assert isinstance(catalog, OfficialFeatureCatalogContract)
        assert catalog.features == []
        assert catalog.project_name == "TestApp"

    @pytest.mark.asyncio
    async def test_empty_feature_list_handled(self, service, mock_ai_service):
        """API returning empty features list should be handled gracefully."""
        mock_ai_service.analyze_text_structured.return_value = {"features": []}

        catalog = await service.build_catalog(
            homepage_url="https://example.com",
            feature_urls=["https://example.com/empty"],
            project_name="TestApp",
        )

        assert catalog.features == []


class TestMergeStrategy:
    """Test feature merge strategy for duplicates."""

    @pytest.mark.asyncio
    async def test_merge_keeps_longer_description(self, service, mock_ai_service):
        """When merging duplicates, keep the longer description."""
        responses = [
            {
                "features": [
                    {
                        "name": "Feature X",
                        "description": "Short",
                        "prominence_score": 0.5,
                    }
                ]
            },
            {
                "features": [
                    {
                        "name": "Feature X",
                        "description": "This is a much longer and more detailed description",
                        "prominence_score": 0.6,
                    }
                ]
            },
        ]

        call_count = 0

        async def mock_analyze(*args, **kwargs):
            nonlocal call_count
            result = responses[call_count]
            call_count += 1
            return result

        mock_ai_service.analyze_text_structured = mock_analyze

        catalog = await service.build_catalog(
            homepage_url="https://example.com",
            feature_urls=["https://example.com/a", "https://example.com/b"],
            project_name="TestApp",
        )

        assert len(catalog.features) == 1
        # Should keep longer description
        assert len(catalog.features[0].description) > 10

    @pytest.mark.asyncio
    async def test_merge_takes_max_prominence(self, service, mock_ai_service):
        """When merging duplicates, take max prominence score."""
        responses = [
            {
                "features": [
                    {
                        "name": "Feature Y",
                        "description": "Test",
                        "prominence_score": 0.9,
                    }
                ]
            },
            {
                "features": [
                    {
                        "name": "Feature Y",
                        "description": "Test",
                        "prominence_score": 0.7,
                    }
                ]
            },
        ]

        call_count = 0

        async def mock_analyze(*args, **kwargs):
            nonlocal call_count
            result = responses[call_count]
            call_count += 1
            return result

        mock_ai_service.analyze_text_structured = mock_analyze

        catalog = await service.build_catalog(
            homepage_url="https://example.com",
            feature_urls=["https://example.com/a", "https://example.com/b"],
            project_name="TestApp",
        )

        assert len(catalog.features) == 1
        assert catalog.features[0].prominence_score == 0.9


class TestEdgeCases:
    """Test edge cases and validation."""

    @pytest.mark.asyncio
    async def test_empty_feature_urls_returns_empty_catalog(
        self, service, mock_ai_service
    ):
        """Empty feature_urls list should return empty catalog."""
        catalog = await service.build_catalog(
            homepage_url="https://example.com",
            feature_urls=[],
            project_name="TestApp",
        )

        assert catalog.features == []
        mock_ai_service.analyze_text_structured.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_optional_fields_use_defaults(self, service, mock_ai_service):
        """Missing optional fields should use defaults."""
        mock_ai_service.analyze_text_structured.return_value = {
            "features": [
                {
                    "name": "Minimal Feature",
                    # Missing description and prominence_score
                }
            ]
        }

        catalog = await service.build_catalog(
            homepage_url="https://example.com",
            feature_urls=["https://example.com/minimal"],
            project_name="TestApp",
        )

        assert len(catalog.features) == 1
        assert catalog.features[0].name == "Minimal Feature"
        assert catalog.features[0].description == ""  # Default
        assert 0.0 <= catalog.features[0].prominence_score <= 1.0  # Default

    @pytest.mark.asyncio
    async def test_case_insensitive_deduplication(self, service, mock_ai_service):
        """Deduplication should be case-insensitive."""
        responses = [
            {
                "features": [
                    {
                        "name": "Real-Time Sync",
                        "description": "First",
                        "prominence_score": 0.8,
                    }
                ]
            },
            {
                "features": [
                    {
                        "name": "real-time sync",  # Different case
                        "description": "Second",
                        "prominence_score": 0.7,
                    }
                ]
            },
        ]

        call_count = 0

        async def mock_analyze(*args, **kwargs):
            nonlocal call_count
            result = responses[call_count]
            call_count += 1
            return result

        mock_ai_service.analyze_text_structured = mock_analyze

        catalog = await service.build_catalog(
            homepage_url="https://example.com",
            feature_urls=["https://example.com/a", "https://example.com/b"],
            project_name="TestApp",
        )

        # Should deduplicate to 1 feature despite case difference
        assert len(catalog.features) == 1
