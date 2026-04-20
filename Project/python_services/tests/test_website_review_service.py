from unittest.mock import AsyncMock

import pytest

from services.website_review_service import WebsiteReviewService


@pytest.mark.asyncio
async def test_website_review_service_returns_structured_review(monkeypatch):
    async def fake_fetch_source(normalized_url: str):
        assert normalized_url == "https://example.com"
        return ("ExampleApp helps teams plan launches and share dashboards.", "jina_reader")

    async def fake_execute_task(self, task_type, prompt, user_id, context=None):
        assert task_type == "website_review_planner"
        assert user_id == "telegram:123"
        assert context["fetch_method"] == "jina_reader"
        return {
            "page_title": "ExampleApp",
            "product_summary": "ExampleApp is a launch planning platform.",
            "access_level": "public_page_only",
            "login_required": False,
            "visible_features": [
                {
                    "label": "Planning dashboard",
                    "summary": "Shows campaign and launch planning in one place.",
                    "evidence": ["Plan launches and collaborate from one dashboard"],
                    "source_url": "https://example.com",
                }
            ],
            "visible_flows": [
                {
                    "label": "Launch review flow",
                    "summary": "Walks users from planning to approval.",
                    "evidence": ["Review timelines before publishing"],
                    "source_url": "https://example.com",
                }
            ],
            "recording_candidates": ["Landing page hero", "Planning dashboard"],
            "risks": ["Dashboard may require a logged-in demo later."],
            "assumptions": ["Homepage reflects the current product positioning."],
        }

    monkeypatch.setattr(WebsiteReviewService, "_fetch_source", classmethod(lambda cls, normalized_url: fake_fetch_source(normalized_url)))
    monkeypatch.setattr(
        "services.website_review_service.OpenClawService.execute_task",
        fake_execute_task,
    )
    monkeypatch.setattr(
        "services.website_review_service.OpenClawService.close",
        AsyncMock(return_value=None),
    )

    review = await WebsiteReviewService.review_url(
        "example.com",
        objective="Create a product review video",
        user_id="telegram:123",
    )

    assert review.normalized_url == "https://example.com"
    assert review.page_fetch_method == "jina_reader"
    assert review.page_title == "ExampleApp"
    assert review.product_summary == "ExampleApp is a launch planning platform."
    assert review.visible_features[0].label == "Planning dashboard"
    assert review.recording_candidates == ["Landing page hero", "Planning dashboard"]


@pytest.mark.asyncio
async def test_website_review_service_accepts_feature_alias_fields(monkeypatch):
    async def fake_fetch_source(normalized_url: str):
        return ("Feature one. Feature two. Feature three.", "manual_summary")

    async def fake_execute_task(self, task_type, prompt, user_id, context=None):
        return {
            "page_title": "ExampleApp",
            "product_summary": "ExampleApp is a launch planning platform.",
            "access_level": "public_page_only",
            "login_required": False,
            "visible_features": [
                {
                    "name": "Dashboard",
                    "description": "Shows campaign and launch metrics.",
                    "sourceUrl": "https://example.com",
                },
                {
                    "title": "Reports",
                    "details": "Exports campaign reports for sharing.",
                    "url": "https://example.com/reports",
                },
            ],
            "visible_flows": [],
            "recording_candidates": [],
            "risks": [],
            "assumptions": [],
        }

    monkeypatch.setattr(
        WebsiteReviewService,
        "_fetch_source",
        classmethod(lambda cls, normalized_url: fake_fetch_source(normalized_url)),
    )
    monkeypatch.setattr(
        "services.website_review_service.OpenClawService.execute_task",
        fake_execute_task,
    )
    monkeypatch.setattr(
        "services.website_review_service.OpenClawService.close",
        AsyncMock(return_value=None),
    )

    review = await WebsiteReviewService.review_url(
        "example.com",
        objective="Create a product review video",
        user_id="telegram:123",
    )

    assert len(review.visible_features) == 2
    assert review.visible_features[0].label == "Dashboard"
    assert review.visible_features[0].summary == "Shows campaign and launch metrics."
    assert review.visible_features[0].source_url == "https://example.com"
    assert review.visible_features[1].label == "Reports"
    assert review.visible_features[1].summary == "Exports campaign reports for sharing."
    assert review.visible_features[1].source_url == "https://example.com/reports"


@pytest.mark.asyncio
async def test_website_review_service_falls_back_when_ai_analysis_fails(monkeypatch):
    async def fake_fetch_source(normalized_url: str):
        return (
            "Sign in to your dashboard to manage campaigns. Track approvals and publishing status.",
            "browser_capture",
        )

    async def fake_execute_task(self, task_type, prompt, user_id, context=None):
        raise ValueError("OpenClaw unavailable")

    monkeypatch.setattr(WebsiteReviewService, "_fetch_source", classmethod(lambda cls, normalized_url: fake_fetch_source(normalized_url)))
    monkeypatch.setattr(
        "services.website_review_service.OpenClawService.execute_task",
        fake_execute_task,
    )
    monkeypatch.setattr(
        "services.website_review_service.OpenClawService.close",
        AsyncMock(return_value=None),
    )

    review = await WebsiteReviewService.review_url(
        "https://example.com/app",
        objective="Capture an authenticated workflow",
        user_id="telegram:123",
    )

    assert review.page_fetch_method == "browser_capture"
    assert review.login_required is True
    assert review.access_level == "has_logged_in_access"
    assert review.recording_candidates == ["Show the product homepage or landing message"]
