"""Unit tests for the marketing poster skill."""

from unittest.mock import AsyncMock

import pytest

from skills.base import SkillStatus
from skills.image_poster import ImagePosterSkill


@pytest.fixture
def initial_session():
    return ImagePosterSkill.initial_session()


@pytest.mark.asyncio
async def test_collects_brief_first(initial_session):
    result = await ImagePosterSkill.execute(initial_session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.next_step == "collect_brief"


@pytest.mark.asyncio
async def test_collects_style_after_brief(initial_session):
    initial_session.collected["topic_or_brief"] = "Weekend hotel sale"

    result = await ImagePosterSkill.execute(initial_session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.next_step == "choose_style"


@pytest.mark.asyncio
async def test_generates_preview_after_required_inputs(initial_session):
    initial_session.collected["topic_or_brief"] = "Weekend hotel sale"
    initial_session.collected["style"] = "bold"
    initial_session.collected["tone"] = "premium"

    ImagePosterSkill._request_json = AsyncMock(
        return_value={
            "url": "https://cdn.example.com/poster.jpg",
            "storage_key": "posters/poster.jpg",
            "prompt": "Create a premium marketing poster...",
        }
    )

    result = await ImagePosterSkill.execute(initial_session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.next_step == "confirm_or_regenerate"
    assert result.session.control.status == SkillStatus.preview_ready
    assert result.output["preview_image_url"] == "https://cdn.example.com/poster.jpg"


@pytest.mark.asyncio
async def test_use_after_preview_marks_done(initial_session):
    initial_session.collected["topic_or_brief"] = "Weekend hotel sale"
    initial_session.collected["style"] = "bold"
    initial_session.collected["tone"] = "premium"
    initial_session.artifacts["generated_image"] = {
        "url": "https://cdn.example.com/poster.jpg",
        "storage_key": "posters/poster.jpg",
        "prompt": "Create a premium marketing poster...",
    }
    initial_session.artifacts["preview_image_url"] = "https://cdn.example.com/poster.jpg"
    initial_session.step_key = "confirm_or_regenerate"
    initial_session.control.status = SkillStatus.preview_ready

    result = await ImagePosterSkill.execute(initial_session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.next_step == "done"
    assert result.session.control.status == SkillStatus.done
    assert result.output["image_url"] == "https://cdn.example.com/poster.jpg"
