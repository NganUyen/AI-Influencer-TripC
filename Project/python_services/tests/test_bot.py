import pytest

from services.telegram_service import TelegramService


@pytest.fixture(autouse=True)
def reset_telegram_service_state():
    TelegramService.approval_requests.clear()
    TelegramService._redis_client = None
    TelegramService._redis_enabled = False
    TelegramService._redis_init_attempted = True
    yield
    TelegramService.approval_requests.clear()


@pytest.mark.asyncio
async def test_apply_callback_payload_marks_request_approved():
    request_id = "123_456"
    TelegramService.approval_requests[request_id] = {
        "user_id": "123",
        "message_id": 456,
        "status": "pending",
        "approved": False,
        "feedback": "",
    }

    response = await TelegramService.apply_callback_payload(request_id, "approve_123")

    assert response == "Strategy approved! Proceeding with content generation."
    assert TelegramService.approval_requests[request_id]["approved"] is True
    assert TelegramService.approval_requests[request_id]["status"] == "approved"


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

    assert response == "Discarded. Final video will not be used."
    assert TelegramService.approval_requests[request_id]["approved"] is False
    assert TelegramService.approval_requests[request_id]["status"] == "discard"
    assert TelegramService.approval_requests[request_id]["feedback"] == "discard"


@pytest.mark.asyncio
async def test_apply_callback_payload_returns_none_for_unknown_request():
    response = await TelegramService.apply_callback_payload("missing_request", "approve_123")

    assert response is None


@pytest.mark.asyncio
async def test_check_approval_status_reports_missing_request():
    service = TelegramService()

    status = await service.check_approval_status("missing_request")

    assert status == {"approved": False, "feedback": "Request not found"}
