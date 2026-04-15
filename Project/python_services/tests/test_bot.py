import pytest

from services.approval_state_service import ApprovalStateService
from services.telegram_service import TelegramService


@pytest.fixture(autouse=True)
def reset_telegram_service_state():
    TelegramService.approval_requests.clear()
    yield
    TelegramService.approval_requests.clear()


@pytest.mark.asyncio
async def test_apply_callback_payload_marks_request_approved(monkeypatch):
    async def fake_get_status(_approval_id):
        return {
            "approval_id": "approval-1",
            "workflow_id": "workflow-1",
            "status": "pending",
            "approved": False,
            "feedback": "",
        }

    async def fake_apply_decision(**kwargs):
        assert kwargs["approval_id"] == "approval-1"
        assert kwargs["action"] == "approve"
        assert kwargs["decision_source"] == "telegram_callback"
        return {
            "approval_id": "approval-1",
            "workflow_id": "workflow-1",
            "status": "approved",
            "approved": True,
            "feedback": "",
        }

    monkeypatch.setattr(ApprovalStateService, "get_status", fake_get_status)
    monkeypatch.setattr(ApprovalStateService, "apply_decision", fake_apply_decision)

    response = await TelegramService.apply_callback_payload(
        "approval-1",
        "approve:approval-1",
    )

    assert response == {
        "text": "Strategy approved! Proceeding with content generation.",
        "approval_id": "approval-1",
        "workflow_id": "workflow-1",
        "status": "approved",
    }


@pytest.mark.asyncio
async def test_apply_callback_payload_marks_request_discarded():
    request_id = "123_789"
    TelegramService.approval_requests[request_id] = {
        "user_id": "123",
        "message_id": 789,
        "status": "pending",
        "approved": False,
        "feedback": "",
    }

    response = await TelegramService.apply_callback_payload(request_id, "discard_123")

    assert response == {
        "text": "Discarded. Final video will not be used.",
        "approval_id": request_id,
        "workflow_id": None,
        "status": "discard",
    }
    assert TelegramService.approval_requests[request_id]["approved"] is False
    assert TelegramService.approval_requests[request_id]["status"] == "discard"
    assert TelegramService.approval_requests[request_id]["feedback"] == "discard"


@pytest.mark.asyncio
async def test_apply_callback_payload_returns_none_for_unknown_request(monkeypatch):
    async def fake_get_status(_approval_id):
        return {"approved": False, "feedback": "Request not found"}

    monkeypatch.setattr(ApprovalStateService, "get_status", fake_get_status)

    response = await TelegramService.apply_callback_payload(
        "missing_request",
        "approve:missing_request",
    )

    assert response is None


@pytest.mark.asyncio
async def test_check_approval_status_reports_missing_request(monkeypatch):
    async def fake_get_status(_approval_id):
        return {"approved": False, "feedback": "Request not found"}

    monkeypatch.setattr(ApprovalStateService, "get_status", fake_get_status)

    service = TelegramService()
    status = await service.check_approval_status("missing_request")

    assert status == {"approved": False, "feedback": "Request not found"}
