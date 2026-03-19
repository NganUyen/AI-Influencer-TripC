import worker
from activities import send_telegram_approval_request, wait_for_approval


def test_legacy_approval_activities_are_exported():
    assert callable(send_telegram_approval_request)
    assert callable(wait_for_approval)
    assert callable(worker.send_telegram_approval_request)
    assert callable(worker.wait_for_approval)
