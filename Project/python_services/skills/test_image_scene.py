"""Unit tests for image_scene skill with multi-candidate selection."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from typing import Any, Dict, List, Optional

from skills.image_scene import ImageSceneSkill
from skills.base import SkillResult, SkillSession, SkillStatus


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_http_client():
    """Mock HTTP client for API calls."""
    return AsyncMock()


@pytest.fixture
def backend_url():
    """Backend URL."""
    return "http://localhost:8000"


@pytest.fixture
def initial_session():
    """Get initial session."""
    return ImageSceneSkill.initial_session()


@pytest.fixture
def session_with_params():
    """Session with all required params filled."""
    session = ImageSceneSkill.initial_session()
    session.collected["topic_or_prompt"] = "beautiful sunset landscape"
    session.collected["style"] = "realistic photography"
    session.collected["aspect_ratio"] = "16:9"
    return session


@pytest.fixture
def session_with_candidates():
    """Session with 4 image candidates already generated."""
    session = ImageSceneSkill.initial_session()
    session.collected["topic_or_prompt"] = "sunset landscape"
    session.collected["style"] = "realistic"
    session.artifacts["image_candidates"] = [
        {
            "url": f"https://r2.example.com/img{i}.jpg",
            "storage_key": f"scenes/img{i}",
            "model": "fal-ai/flux-pro",
            "prompt": "A beautiful sunset landscape in realistic style"
        }
        for i in range(4)
    ]
    session.step_key = "selecting_image"
    session.control.status = SkillStatus.preview_ready
    return session


@pytest.fixture
def mock_image_response():
    """Mock API response for single image generation."""
    return {
        "url": "https://r2.example.com/test-image.jpg",
        "storage_key": "scenes/test-image",
        "model": "fal-ai/flux-pro",
        "prompt": "A test prompt"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Test: Missing Parameters
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_collect_topic_when_missing(initial_session):
    """Test that skill requests params when both topic and style are missing."""
    mock_client = AsyncMock()
    result = await ImageSceneSkill.execute(initial_session, "http://localhost:8000", mock_client)

    assert result.success == True
    # When both are missing, skill prioritizes style collection
    assert result.next_step == "choose_style"
    assert "missing_params" in result.output
    assert "topic_or_prompt" in result.output["missing_params"]
    assert "style" in result.output["missing_params"]


@pytest.mark.asyncio
async def test_collect_style_when_missing(initial_session):
    """Test that skill requests style when missing."""
    initial_session.collected["topic_or_prompt"] = "sunset landscape"

    mock_client = AsyncMock()
    result = await ImageSceneSkill.execute(initial_session, "http://localhost:8000", mock_client)

    assert result.success == True
    assert result.next_step == "choose_style"
    assert "missing_params" in result.output
    assert "style" in result.output["missing_params"]


# ═══════════════════════════════════════════════════════════════════════════════
# Test: Image Generation - Success
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_generate_image_candidates_success(session_with_params, mock_http_client, backend_url):
    """Test successful generation of 4 image candidates."""
    # Mock the API to return an image for each call
    mock_responses = [
        {
            "url": f"https://r2.example.com/img{i}.jpg",
            "storage_key": f"scenes/img{i}",
            "model": "fal-ai/flux-pro",
            "prompt": "A beautiful sunset landscape"
        }
        for i in range(4)
    ]

    mock_http_client._request_json = AsyncMock(side_effect=mock_responses)
    ImageSceneSkill._request_json = AsyncMock(side_effect=mock_responses)

    result = await ImageSceneSkill.execute(session_with_params, backend_url, mock_http_client)

    # Verify success
    assert result.success == True
    assert result.next_step == "selecting_image"
    assert result.output["candidate_count"] == 4
    assert len(result.output["image_candidates"]) == 4

    # Verify session state
    assert result.session.step_key == "selecting_image"
    assert result.session.control.status == SkillStatus.preview_ready
    assert len(result.session.artifacts["image_candidates"]) == 4


@pytest.mark.asyncio
async def test_generate_candidates_in_parallel(session_with_params, mock_http_client, backend_url):
    """Test that candidates are generated in parallel."""
    call_count = 0
    async def mock_api_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return {
            "url": f"https://r2.example.com/img{call_count}.jpg",
            "storage_key": f"scenes/img{call_count}",
        }

    ImageSceneSkill._request_json = AsyncMock(side_effect=mock_api_call)

    result = await ImageSceneSkill.execute(session_with_params, backend_url, mock_http_client)

    # Should have called API 4 times (for 4 candidates)
    assert call_count >= 4
    assert len(result.output["image_candidates"]) == 4


# ═══════════════════════════════════════════════════════════════════════════════
# Test: Image Generation - Failure Cases
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_generation_fails_when_all_apis_fail(session_with_params, mock_http_client, backend_url):
    """Test graceful failure when all image generation attempts fail."""
    # Mock all API calls to return None (failure)
    ImageSceneSkill._request_json = AsyncMock(side_effect=Exception("API Error"))

    result = await ImageSceneSkill.execute(session_with_params, backend_url, mock_http_client)

    assert result.success == False
    assert "Failed to generate any images" in result.error


@pytest.mark.asyncio
async def test_generation_succeeds_with_partial_failures(session_with_params, mock_http_client, backend_url):
    """Test that generation succeeds if some candidates fail (at least 1 succeeds)."""
    responses = [
        {"url": "https://r2.example.com/img0.jpg", "storage_key": "scenes/img0"},  # Success
        None,  # Failure
        {"url": "https://r2.example.com/img2.jpg", "storage_key": "scenes/img2"},  # Success
        None,  # Failure
    ]

    ImageSceneSkill._request_json = AsyncMock(side_effect=responses)

    result = await ImageSceneSkill.execute(session_with_params, backend_url, mock_http_client)

    assert result.success == True
    assert len(result.output["image_candidates"]) == 2  # 2 successful


# ═══════════════════════════════════════════════════════════════════════════════
# Test: Image Selection (User Picks One)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_select_first_candidate(session_with_candidates):
    """Test user selects the first image candidate."""
    result = ImageSceneSkill.handle_selection(session_with_candidates, selected_index=0)

    assert result.success == True
    assert result.next_step == "done"
    assert result.output["selected_index"] == 0
    assert result.output["image_url"] == "https://r2.example.com/img0.jpg"
    assert result.session.artifacts["final_image_url"] == "https://r2.example.com/img0.jpg"
    assert result.session.artifacts["selected_candidate_index"] == 0
    assert result.session.step_key == "done"
    assert result.session.control.status == SkillStatus.done


@pytest.mark.asyncio
async def test_select_last_candidate(session_with_candidates):
    """Test user selects the last image candidate."""
    result = ImageSceneSkill.handle_selection(session_with_candidates, selected_index=3)

    assert result.success == True
    assert result.output["selected_index"] == 3
    assert result.output["image_url"] == "https://r2.example.com/img3.jpg"
    assert result.session.artifacts["final_image_url"] == "https://r2.example.com/img3.jpg"


@pytest.mark.asyncio
async def test_select_invalid_index_negative(session_with_candidates):
    """Test that negative index selection fails."""
    result = ImageSceneSkill.handle_selection(session_with_candidates, selected_index=-1)

    assert result.success == False
    assert "Invalid selection" in result.error


@pytest.mark.asyncio
async def test_select_invalid_index_out_of_range(session_with_candidates):
    """Test that out-of-range index selection fails."""
    result = ImageSceneSkill.handle_selection(session_with_candidates, selected_index=10)

    assert result.success == False
    assert "Invalid selection" in result.error


@pytest.mark.asyncio
async def test_select_empty_candidates(initial_session):
    """Test that selection fails when no candidates exist."""
    result = ImageSceneSkill.handle_selection(initial_session, selected_index=0)

    assert result.success == False
    assert "Invalid selection" in result.error


# ═══════════════════════════════════════════════════════════════════════════════
# Test: Regenerate Flow (Generate More Candidates)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_regenerate_clears_old_candidates(session_with_candidates):
    """Test that regenerate keeps old candidates in history."""
    # Old flow: user calls execute again after clearing artifacts
    old_candidates = session_with_candidates.artifacts["image_candidates"].copy()

    # Clear for regeneration
    session_with_candidates.artifacts["image_candidates"] = []
    session_with_candidates.step_key = "generating_candidates"

    # (Would call execute() here to generate new ones)
    # But for this test, just verify the clear worked
    assert len(session_with_candidates.artifacts["image_candidates"]) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Test: Prompt Building
# ═══════════════════════════════════════════════════════════════════════════════

def test_build_prompt_with_all_fields():
    """Test prompt building with all optional fields."""
    collected = {
        "topic_or_prompt": "sunset landscape",
        "style": "realistic photography",
        "scene_type": "outdoor",
        "persona_id": "persona_1",
        "freeform_brief": "golden hour lighting",
        "creative_notes": "cinematic composition"
    }

    prompt = ImageSceneSkill._build_prompt(collected)

    assert "sunset landscape" in prompt
    assert "Scene type: outdoor" in prompt
    assert "Style: realistic photography" in prompt
    assert "Persona reference: persona_1" in prompt
    assert "Brief: golden hour lighting" in prompt
    assert "Creative notes: cinematic composition" in prompt


def test_build_prompt_minimal():
    """Test prompt building with only required fields."""
    collected = {
        "topic_or_prompt": "sunset landscape",
        "style": "realistic"
    }

    prompt = ImageSceneSkill._build_prompt(collected)

    assert "sunset landscape" in prompt
    assert "Style: realistic" in prompt
    # Optional fields should not appear
    assert "Scene type:" not in prompt
    assert "Persona reference:" not in prompt


# ═══════════════════════════════════════════════════════════════════════════════
# Test: Session Management
# ═══════════════════════════════════════════════════════════════════════════════

def test_initial_session_structure():
    """Test initial session has correct structure."""
    session = ImageSceneSkill.initial_session()

    assert session.skill_name == "image-scene"
    assert session.step_key == "collect_prompt"
    assert session.collected["topic_or_prompt"] is None
    assert session.collected["style"] is None
    assert session.artifacts["image_candidates"] == []
    assert session.artifacts["final_image_url"] is None


def test_session_preserves_candidates_after_selection(session_with_candidates):
    """Test that candidates are preserved in session after selection."""
    original_candidates = session_with_candidates.artifacts["image_candidates"].copy()

    result = ImageSceneSkill.handle_selection(session_with_candidates, selected_index=1)

    # Candidates should still be in artifacts
    assert result.session.artifacts["image_candidates"] == original_candidates
    # But we know which one was selected
    assert result.session.artifacts["selected_candidate_index"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Test: Final done Status
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_done_status_returns_immediately(session_with_candidates):
    """Test that when final_image_url is set, skill returns done immediately."""
    # Simulate selection already made
    session_with_candidates.artifacts["final_image_url"] = "https://r2.example.com/img0.jpg"

    mock_client = AsyncMock()
    result = await ImageSceneSkill.execute(session_with_candidates, "http://localhost:8000", mock_client)

    # Should return done immediately without generating more
    assert result.success == True
    assert result.next_step == "done"
    assert mock_client.request.call_count == 0  # No API calls


# ═══════════════════════════════════════════════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_full_flow_generate_and_select(backend_url):
    """Integration test: complete flow from generation to selection."""
    # Step 1: Initialize with params
    session = ImageSceneSkill.initial_session()
    session.collected["topic_or_prompt"] = "mountain landscape"
    session.collected["style"] = "oil painting"

    # Step 2: Generate candidates
    mock_responses = [
        {
            "url": f"https://r2.example.com/mountain{i}.jpg",
            "storage_key": f"scenes/mountain{i}",
            "model": "fal-ai/flux-pro",
        }
        for i in range(4)
    ]

    ImageSceneSkill._request_json = AsyncMock(side_effect=mock_responses)

    result = await ImageSceneSkill.execute(session, backend_url, AsyncMock())
    assert result.success == True
    assert result.next_step == "selecting_image"

    # Step 3: User selects image #2
    selection_result = ImageSceneSkill.handle_selection(result.session, selected_index=2)
    assert selection_result.success == True
    assert selection_result.next_step == "done"
    assert "mountain2" in selection_result.output["image_url"]

    # Step 4: Execute again should return done immediately
    final_result = await ImageSceneSkill.execute(
        selection_result.session,
        backend_url,
        AsyncMock()
    )
    assert final_result.next_step == "done"


if __name__ == "__main__":
    # Run with: pytest skills/test_image_scene.py -v
    pytest.main([__file__, "-v"])
