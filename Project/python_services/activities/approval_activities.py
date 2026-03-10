"""
Approval Activities
Handles human-in-the-loop approvals via Telegram
"""

from temporalio import activity
from typing import Dict, Any
import logging
from datetime import datetime

from services.telegram_service import TelegramService

logger = logging.getLogger(__name__)


@activity.defn
async def send_telegram_approval_request(user_id: str, strategy: Dict[str, Any]) -> str:
    """
    Send approval request to user via Telegram
    Returns approval request ID for tracking
    """
    logger.info(f"Sending approval request to user {user_id}")

    telegram = TelegramService()

    # Format strategy for human review
    message = format_strategy_message(strategy)

    # Send to Telegram with inline approval buttons
    request_id = await telegram.send_approval_request(
        user_id=user_id,
        message=message,
        buttons=[
            {"text": "✅ Approve", "callback_data": f"approve_{strategy['user_id']}"},
            {"text": "✏️ Edit", "callback_data": f"edit_{strategy['user_id']}"},
            {"text": "❌ Reject", "callback_data": f"reject_{strategy['user_id']}"},
        ],
    )

    logger.info(f"Approval request sent with ID: {request_id}")
    return request_id


@activity.defn
async def wait_for_approval(request_id: str) -> Dict[str, Any]:
    """
    Check approval status (called periodically by workflow)
    """
    telegram = TelegramService()

    approval_status = await telegram.check_approval_status(request_id)

    return {
        "request_id": request_id,
        "approved": approval_status.get("approved", False),
        "feedback": approval_status.get("feedback", ""),
        "timestamp": datetime.utcnow().isoformat(),
    }


def format_strategy_message(strategy: Dict[str, Any]) -> str:
    """Format strategy for Telegram display"""
    message = "📅 **Weekly Content Strategy**\\n\\n"

    daily_content = strategy.get("strategy", {}).get("daily_content", [])

    for day_idx, day in enumerate(daily_content):
        message += f"**Day {day_idx + 1}:** {day.get('theme', 'N/A')}\\n"
        message += f"🎯 Platforms: {', '.join(day.get('platforms', []))}\\n"
        message += f"📝 {day.get('message', 'N/A')[:100]}...\\n"
        message += f"⏰ Posting time: {day.get('posting_time', 'N/A')}\\n\\n"

    message += "\\n**Please review and approve to proceed with content generation.**"

    return message
