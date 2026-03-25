"""Unit tests for image_scene skill with multi-candidate selection."""

from unittest.mock import AsyncMock

import pytest

from skills.base import SkillStatus
from skills.image_scene import ImageSceneSkill


@pytest.fixture
def initial_session():
    return ImageSceneSkill.initial_session()


@pytest.fixture
def session_with_params():
    session = ImageSceneSkill.initial_session()
    session.collected["topic_or_prompt"] = "beautiful sunset landscape"
    session.collected["style"] = "realistic photography"
    session.collected["aspect_ratio"] = "16:9"
    return session


@pytest.fixture
def session_with_candidates():
    session = ImageSceneSkill.initial_session()
    session.collected["topic_or_prompt"] = "sunset landscape"
    session.collected["style"] = "realistic"
    session.artifacts["image_candidates"] = [
        {
            "url": f"https://r2.example.com/img{i}.jpg",
            "storage_key": f"scenes/img{i}",
            "model": "fal-ai/flux-pro",
            "prompt": "A beautiful sunset landscape in realistic style",
        }
        for i in range(4)
    ]
    session.artifacts["selected_candidate_indexes"] = []
    session.step_key = "confirm_or_regenerate"
    session.control.status = SkillStatus.preview_ready
    return session


@pytest.mark.asyncio
async def test_collects_missing_params(initial_session):
    result = await ImageSceneSkill.execute(initial_session, "http://localhost:8000", AsyncMock())

    assert result.success is True
    assert result.next_step == "choose_style"
    assert "topic_or_prompt" in result.output["missing_params"]
    assert "style" in result.output["missing_params"]


@pytest.mark.asyncio
async def test_generates_candidate_batch(session_with_params):
    mock_responses = [
        {
            "url": f"https://r2.example.com/img{i}.jpg",
            "storage_key": f"scenes/img{i}",
            "model": "fal-ai/flux-pro",
            "prompt": "A beautiful sunset landscape",
        }
        for i in range(4)
    ]

    ImageSceneSkill._request_json = AsyncMock(side_effect=mock_responses)

    result = await ImageSceneSkill.execute(session_with_params, "http://localhost:8000", AsyncMock())

    assert result.success is True
    assert result.next_step == "confirm_or_regenerate"
    assert result.output["candidate_count"] == 4
    assert result.session.step_key == "confirm_or_regenerate"
    assert result.session.control.status == SkillStatus.preview_ready
    assert result.session.artifacts["selected_candidate_indexes"] == []


def test_enter_selection_mode(session_with_candidates):
    result = ImageSceneSkill.enter_selection_mode(session_with_candidates)

    assert result.success is True
    assert result.next_step == "selecting_images"
    assert result.session.step_key == "selecting_images"
    assert result.session.control.status == SkillStatus.collecting


def test_toggle_selection_on_and_off(session_with_candidates):
    enter_result = ImageSceneSkill.enter_selection_mode(session_with_candidates)

    first_toggle = ImageSceneSkill.toggle_selection(enter_result.session, 1)
    assert first_toggle.success is True
    assert first_toggle.output["selected_candidate_indexes"] == [1]

    second_toggle = ImageSceneSkill.toggle_selection(first_toggle.session, 1)
    assert second_toggle.success is True
    assert second_toggle.output["selected_candidate_indexes"] == []


def test_submit_requires_at_least_one_selection(session_with_candidates):
    enter_result = ImageSceneSkill.enter_selection_mode(session_with_candidates)
    submit_result = ImageSceneSkill.submit_selection(enter_result.session)

    assert submit_result.success is True
    assert submit_result.next_step == "selecting_images"
    assert "Choose at least one image" in submit_result.output["message"]


def test_submit_multiple_selected_images(session_with_candidates):
    session = ImageSceneSkill.enter_selection_mode(session_with_candidates).session
    session = ImageSceneSkill.toggle_selection(session, 0).session
    session = ImageSceneSkill.toggle_selection(session, 2).session

    result = ImageSceneSkill.submit_selection(session)

    assert result.success is True
    assert result.next_step == "done"
    assert result.output["selected_indexes"] == [0, 2]
    assert len(result.output["image_urls"]) == 2
    assert result.session.artifacts["final_image_url"] == "https://r2.example.com/img0.jpg"
    assert result.session.artifacts["final_image_urls"] == [
        "https://r2.example.com/img0.jpg",
        "https://r2.example.com/img2.jpg",
    ]
    assert result.session.control.status == SkillStatus.done


def test_handle_selection_still_supports_single_pick(session_with_candidates):
    result = ImageSceneSkill.handle_selection(session_with_candidates, selected_index=3)

    assert result.success is True
    assert result.next_step == "done"
    assert result.output["selected_index"] == 3
    assert result.output["selected_indexes"] == [3]
    assert result.output["image_urls"] == ["https://r2.example.com/img3.jpg"]


@pytest.mark.asyncio
async def test_done_status_returns_immediately(session_with_candidates):
    session_with_candidates.artifacts["final_image_url"] = "https://r2.example.com/img0.jpg"
    session_with_candidates.artifacts["final_image_urls"] = ["https://r2.example.com/img0.jpg"]
    session_with_candidates.artifacts["final_storage_keys"] = ["scenes/img0"]

    mock_client = AsyncMock()
    result = await ImageSceneSkill.execute(session_with_candidates, "http://localhost:8000", mock_client)

    assert result.success is True
    assert result.next_step == "done"
    assert result.output["image_urls"] == ["https://r2.example.com/img0.jpg"]
    assert mock_client.request.call_count == 0


@pytest.mark.asyncio
async def test_full_flow_generate_select_multiple_and_finish():
    session = ImageSceneSkill.initial_session()
    session.collected["topic_or_prompt"] = "mountain landscape"
    session.collected["style"] = "oil painting"

    mock_responses = [
        {
            "url": f"https://r2.example.com/mountain{i}.jpg",
            "storage_key": f"scenes/mountain{i}",
            "model": "fal-ai/flux-pro",
        }
        for i in range(4)
    ]
    ImageSceneSkill._request_json = AsyncMock(side_effect=mock_responses)

    generate_result = await ImageSceneSkill.execute(session, "http://localhost:8000", AsyncMock())
    assert generate_result.next_step == "confirm_or_regenerate"

    selection_result = ImageSceneSkill.enter_selection_mode(generate_result.session)
    selection_result = ImageSceneSkill.toggle_selection(selection_result.session, 1)
    selection_result = ImageSceneSkill.toggle_selection(selection_result.session, 3)
    submit_result = ImageSceneSkill.submit_selection(selection_result.session)

    assert submit_result.success is True
    assert submit_result.output["selected_indexes"] == [1, 3]

    final_result = await ImageSceneSkill.execute(
        submit_result.session,
        "http://localhost:8000",
        AsyncMock(),
    )
    assert final_result.next_step == "done"
    assert final_result.output["image_urls"] == [
        "https://r2.example.com/mountain1.jpg",
        "https://r2.example.com/mountain3.jpg",
    ]
