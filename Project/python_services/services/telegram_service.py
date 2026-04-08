"""
Telegram Bot Service
Handles human-in-the-loop approvals and notifications.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from config.settings import settings

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - depends on local env
    Redis = None

logger = logging.getLogger(__name__)

APPROVAL_TTL_SECONDS = 1800

# Characters that need escaping in Telegram Markdown V1
_MARKDOWN_ESCAPE_CHARS = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']


def escape_markdown(text: str) -> str:
    """Escape special characters for Telegram Markdown V1 parsing."""
    if not text:
        return text
    result = str(text)
    for char in _MARKDOWN_ESCAPE_CHARS:
        result = result.replace(char, f'\\{char}')
    return result


class TelegramService:
    """
    Integration with Telegram for approval workflows and notifications.
    """

    approval_requests: Dict[str, Dict[str, Any]] = {}
    _redis_client: Optional[Any] = None
    _redis_enabled: bool = False
    _redis_init_attempted: bool = False

    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.bot = Bot(token=self.bot_token)
        self.approval_requests = TelegramService.approval_requests
        self._init_redis()

    async def _record_usage(
        self,
        operation: str,
        usage: Dict[str, Any],
        error: Exception | None = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        from services.quota_monitor_service import QuotaMonitorService
        quota_metadata = {
            "service": "telegram_service",
            "operation": operation,
            "status": "error" if error else "success",
        }
        if metadata:
            quota_metadata.update(metadata)
        if error:
            quota_metadata["error_type"] = type(error).__name__
            quota_metadata["error_message"] = str(error)

        await QuotaMonitorService.record_runtime_usage(
            provider="telegram",
            usage=usage,
            metadata=quota_metadata,
        )

    @classmethod
    def _init_redis(cls) -> None:
        if cls._redis_init_attempted:
            return
        cls._redis_init_attempted = True

        if Redis is None:
            logger.warning("Redis client not installed. Falling back to in-memory approval state.")
            cls._redis_enabled = False
            return

        redis_url = getattr(settings, "REDIS_URL", None)
        if not redis_url:
            logger.warning("REDIS_URL is not configured. Falling back to in-memory approval state.")
            cls._redis_enabled = False
            return

        try:
            cls._redis_client = Redis.from_url(redis_url, decode_responses=True)
            cls._redis_enabled = True
        except Exception as exc:  # pragma: no cover - defensive init path
            logger.warning(
                "Redis unavailable at init time (%s). Falling back to in-memory approval state.",
                exc,
            )
            cls._redis_client = None
            cls._redis_enabled = False

    @staticmethod
    def _approval_key(request_id: str) -> str:
        return f"approval:{request_id}"

    @classmethod
    async def _write_request(cls, request_id: str, payload: Dict[str, Any]) -> None:
        cls.approval_requests[request_id] = payload
        if not cls._redis_enabled or cls._redis_client is None:
            return
        try:
            await cls._redis_client.setex(
                cls._approval_key(request_id),
                APPROVAL_TTL_SECONDS,
                json.dumps(payload),
            )
        except Exception as exc:  # pragma: no cover - depends on external Redis
            logger.warning(
                "Redis write failed. Falling back to in-memory approval state: %s",
                exc,
            )
            cls._redis_enabled = False

    @classmethod
    async def _read_request(cls, request_id: str) -> Optional[Dict[str, Any]]:
        if cls._redis_enabled and cls._redis_client is not None:
            try:
                raw = await cls._redis_client.get(cls._approval_key(request_id))
                if raw:
                    payload = json.loads(raw)
                    cls.approval_requests[request_id] = payload
                    return payload
            except Exception as exc:  # pragma: no cover - depends on external Redis
                logger.warning(
                    "Redis read failed. Falling back to in-memory approval state: %s",
                    exc,
                )
                cls._redis_enabled = False

        payload = cls.approval_requests.get(request_id)
        return payload.copy() if payload else None

    async def send_approval_request(
        self, user_id: str, message: str, buttons: List[Dict[str, str]]
    ) -> str:
        """
        Send approval request with inline buttons.
        """
        logger.info("Sending approval request to %s", user_id)

        keyboard = [
            [InlineKeyboardButton(btn["text"], callback_data=btn["callback_data"])]
            for btn in buttons
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            sent_message = await self.bot.send_message(
                chat_id=user_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
            await self._record_usage(
                operation="send_approval_request",
                usage={"requests": 1, "messages": 1},
                metadata={"chat_id": user_id},
            )

            request_id = f"{user_id}_{sent_message.message_id}"
            await self._write_request(
                request_id,
                {
                    "user_id": user_id,
                    "message_id": sent_message.message_id,
                    "status": "pending",
                    "approved": False,
                    "feedback": "",
                },
            )

            logger.info("Approval request sent: %s", request_id)
            return request_id
        except Exception as exc:
            logger.error("Failed to send approval request: %s", str(exc))
            raise

    async def check_approval_status(self, request_id: str) -> Dict[str, Any]:
        """
        Check the status of an approval request.
        """
        payload = await self._read_request(request_id)
        if payload is None:
            return {"approved": False, "feedback": "Request not found"}
        return payload

    @classmethod
    async def apply_callback_payload(
        cls,
        request_id: str,
        callback_data: str,
    ) -> Optional[str]:
        """Handle approval callback data without requiring python-telegram-bot Update objects."""
        cls._init_redis()
        current_state = await cls._read_request(request_id)
        if current_state is None:
            return None

        if callback_data.startswith("approve_"):
            current_state["approved"] = True
            current_state["status"] = "approved"
            await cls._write_request(request_id, current_state)
            return "Strategy approved! Proceeding with content generation."

        if callback_data.startswith("reject_"):
            current_state["approved"] = False
            current_state["status"] = "rejected"
            await cls._write_request(request_id, current_state)
            return "Strategy rejected. Workflow cancelled."

        if callback_data.startswith("edit_"):
            return "Please provide your feedback for edits:"

        if callback_data.startswith("save_"):
            current_state["approved"] = True
            current_state["status"] = "save"
            current_state["feedback"] = "save"
            await cls._write_request(request_id, current_state)
            return "Saved. Final video kept for downstream use."

        if callback_data.startswith("discard_"):
            current_state["approved"] = False
            current_state["status"] = "discard"
            current_state["feedback"] = "discard"
            await cls._write_request(request_id, current_state)
            return "Discarded. Final video will not be used."

        return None
