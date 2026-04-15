"""
Telegram Bot Service
Handles human-in-the-loop approvals and notifications.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from config.settings import settings
from services.approval_state_service import ApprovalStateService
from services.telegram_link_service import TelegramLinkService

logger = logging.getLogger(__name__)

# Characters that need escaping in Telegram Markdown V1
_MARKDOWN_ESCAPE_CHARS = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
_APPROVAL_ACTIONS = ("approve", "reject", "edit", "save", "discard")


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

    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.bot = Bot(token=self.bot_token)
        self.approval_requests = TelegramService.approval_requests

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

    @staticmethod
    def _extract_approval_action(callback_data: str) -> Optional[str]:
        normalized = str(callback_data or "").strip()
        for action in _APPROVAL_ACTIONS:
            if (
                normalized == action
                or normalized.startswith(f"{action}:")
                or normalized.startswith(f"{action}_")
            ):
                return action
        return None

    @classmethod
    def _build_callback_data(cls, callback_data: str, approval_id: str) -> str:
        action = cls._extract_approval_action(callback_data)
        if action is None:
            return str(callback_data or "")
        return f"{action}:{approval_id}"

    @classmethod
    async def _resolve_approver_id(
        cls,
        *,
        chat_id: int | str,
        approver_id: Optional[str],
    ) -> Optional[str]:
        normalized = str(approver_id or "").strip()
        if normalized:
            return normalized
        return await TelegramLinkService.resolve_user_id_for_owner_key(
            f"telegram:{chat_id}"
        )

    @classmethod
    async def _read_legacy_request(
        cls,
        request_id: str,
    ) -> Optional[Dict[str, Any]]:
        payload = cls.approval_requests.get(request_id)
        return dict(payload) if payload else None

    async def send_approval_request(
        self,
        user_id: str,
        message: str,
        buttons: List[Dict[str, str]],
        *,
        workflow_id: Optional[str] = None,
        content_id: Optional[str] = None,
        approver_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Send approval request with inline buttons.
        """
        logger.info("Sending approval request to %s", user_id)

        resolved_approver_id = await self._resolve_approver_id(
            chat_id=user_id,
            approver_id=approver_id,
        )
        if not resolved_approver_id:
            raise ValueError(
                "Telegram approval routing requires a linked customer account."
            )

        approval = await ApprovalStateService.create_request(
            approver_id=resolved_approver_id,
            workflow_id=workflow_id,
            content_id=content_id,
            channel="telegram",
            metadata=metadata,
        )
        approval_id = str(approval["approval_id"])
        keyboard = [
            [
                InlineKeyboardButton(
                    btn["text"],
                    callback_data=self._build_callback_data(
                        btn.get("callback_data", ""),
                        approval_id,
                    ),
                )
            ]
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
            await ApprovalStateService.attach_telegram_message(
                approval_id=approval_id,
                chat_id=user_id,
                message_id=sent_message.message_id,
            )
            logger.info("Approval request sent: %s", approval_id)
            return approval_id
        except Exception as exc:
            logger.error("Failed to send approval request: %s", str(exc))
            raise

    async def check_approval_status(self, request_id: str) -> Dict[str, Any]:
        """
        Check the status of an approval request.
        """
        payload = await ApprovalStateService.get_status(request_id)
        if payload.get("feedback") != "Request not found":
            return payload
        legacy_payload = await self._read_legacy_request(request_id)
        if legacy_payload is None:
            return {"approved": False, "feedback": "Request not found"}
        return legacy_payload

    @classmethod
    async def apply_callback_payload(
        cls,
        request_id: str,
        callback_data: str,
        *,
        decision_source: str = "telegram_callback",
        decision_payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Handle approval callback data without requiring python-telegram-bot Update objects."""
        action = cls._extract_approval_action(callback_data)
        if action is None:
            return None

        current_state = await ApprovalStateService.get_status(request_id)
        if current_state.get("feedback") != "Request not found":
            approval_id = str(current_state["approval_id"])
            if action == "edit":
                return {
                    "text": "Please provide your feedback for edits:",
                    "approval_id": approval_id,
                    "workflow_id": current_state.get("workflow_id"),
                    "status": current_state.get("status"),
                }

            updated = await ApprovalStateService.apply_decision(
                approval_id=approval_id,
                action=action,
                decision_source=decision_source,
                decision_payload=decision_payload or {"callback_data": callback_data},
            )
            if updated is None:
                return None

            text = {
                "approve": "Strategy approved! Proceeding with content generation.",
                "reject": "Strategy rejected. Workflow cancelled.",
                "save": "Saved. Final video kept for downstream use.",
                "discard": "Discarded. Final video will not be used.",
            }.get(action)
            return {
                "text": text or "Approval updated.",
                "approval_id": updated.get("approval_id"),
                "workflow_id": updated.get("workflow_id"),
                "status": updated.get("status"),
            }

        current_state = await cls._read_legacy_request(request_id)
        if current_state is None:
            return None

        if action == "approve":
            current_state["approved"] = True
            current_state["status"] = "approved"
            cls.approval_requests[request_id] = current_state
            return {
                "text": "Strategy approved! Proceeding with content generation.",
                "approval_id": request_id,
                "workflow_id": current_state.get("workflow_id"),
                "status": current_state.get("status"),
            }

        if action == "reject":
            current_state["approved"] = False
            current_state["status"] = "rejected"
            cls.approval_requests[request_id] = current_state
            return {
                "text": "Strategy rejected. Workflow cancelled.",
                "approval_id": request_id,
                "workflow_id": current_state.get("workflow_id"),
                "status": current_state.get("status"),
            }

        if action == "edit":
            return {
                "text": "Please provide your feedback for edits:",
                "approval_id": request_id,
                "workflow_id": current_state.get("workflow_id"),
                "status": current_state.get("status"),
            }

        if action == "save":
            current_state["approved"] = True
            current_state["status"] = "save"
            current_state["feedback"] = "save"
            cls.approval_requests[request_id] = current_state
            return {
                "text": "Saved. Final video kept for downstream use.",
                "approval_id": request_id,
                "workflow_id": current_state.get("workflow_id"),
                "status": current_state.get("status"),
            }

        if action == "discard":
            current_state["approved"] = False
            current_state["status"] = "discard"
            current_state["feedback"] = "discard"
            cls.approval_requests[request_id] = current_state
            return {
                "text": "Discarded. Final video will not be used.",
                "approval_id": request_id,
                "workflow_id": current_state.get("workflow_id"),
                "status": current_state.get("status"),
            }

        return None
