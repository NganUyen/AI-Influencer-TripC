import pytest

from services.video_capture_handoff_service import (
    VideoCaptureHandoffError,
    VideoCaptureHandoffService,
)


def test_video_capture_handoff_token_round_trip(monkeypatch):
    token_payload = VideoCaptureHandoffService.create_token(
        user_id="11111111-1111-1111-1111-111111111111",
        plan_id="plan_123",
        objective="Capture the dashboard flow",
        target_url="https://example.com/app",
        persona_id="persona-1",
        execution_mode="authenticated_pc_recording",
        review_plan={"plan_id": "plan_123", "execution_mode": "authenticated_pc_recording"},
        telegram_chat_id="555",
    )

    inspected = VideoCaptureHandoffService.inspect_token(
        token_payload["token"],
        expected_user_id="11111111-1111-1111-1111-111111111111",
    )

    assert inspected["plan_id"] == "plan_123"
    assert inspected["target_url"] == "https://example.com/app"
    assert inspected["execution_mode"] == "authenticated_pc_recording"
    assert inspected["review_plan"]["plan_id"] == "plan_123"
    assert inspected["telegram_chat_id"] == "555"
    assert "/capture-handoff?token=" in token_payload["handoff_url"]


def test_video_capture_handoff_rejects_wrong_user():
    token_payload = VideoCaptureHandoffService.create_token(
        user_id="11111111-1111-1111-1111-111111111111",
        plan_id="plan_123",
        objective="Capture the dashboard flow",
        target_url="https://example.com/app",
        persona_id="persona-1",
        execution_mode="authenticated_pc_recording",
        review_plan={"plan_id": "plan_123", "execution_mode": "authenticated_pc_recording"},
    )

    with pytest.raises(VideoCaptureHandoffError):
        VideoCaptureHandoffService.inspect_token(
            token_payload["token"],
            expected_user_id="22222222-2222-2222-2222-222222222222",
        )
