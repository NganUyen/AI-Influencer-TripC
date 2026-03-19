"""
Telegram Bot Service
Handles human-in-the-loop approvals and notifications
"""

import logging
from typing import Dict, Any, List
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config.settings import settings

logger = logging.getLogger(__name__)


class TelegramService:
    """
    Integration with Telegram for approval workflows and notifications
    """

    approval_requests: Dict[str, Dict[str, Any]] = {}

    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.bot = Bot(token=self.bot_token)
        self.approval_requests = TelegramService.approval_requests

    async def send_approval_request(
        self, user_id: str, message: str, buttons: List[Dict[str, str]]
    ) -> str:
        """
        Send approval request with inline buttons

        Args:
            user_id: Telegram user ID or chat ID
            message: Message text
            buttons: List of button configs with text and callback_data

        Returns:
            Request ID for tracking
        """
        logger.info(f"Sending approval request to {user_id}")

        # Create inline keyboard
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

            request_id = f"{user_id}_{sent_message.message_id}"

            # Store request in memory (in production, use Redis/database)
            self.approval_requests[request_id] = {
                "user_id": user_id,
                "message_id": sent_message.message_id,
                "status": "pending",
                "approved": False,
                "feedback": "",
            }

            logger.info(f"Approval request sent: {request_id}")
            return request_id

        except Exception as e:
            logger.error(f"Failed to send approval request: {str(e)}")
            raise

    async def check_approval_status(self, request_id: str) -> Dict[str, Any]:
        """
        Check the status of an approval request

        Args:
            request_id: Request ID from send_approval_request

        Returns:
            Approval status and feedback
        """
        if request_id not in self.approval_requests:
            return {"approved": False, "feedback": "Request not found"}

        return self.approval_requests[request_id]

    async def handle_approval_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Callback handler for approval button clicks
        """
        query = update.callback_query
        await query.answer()

        callback_data = query.data
        request_id = f"{query.from_user.id}_{query.message.message_id}"

        if request_id in self.approval_requests:
            if callback_data.startswith("approve_"):
                self.approval_requests[request_id]["approved"] = True
                self.approval_requests[request_id]["status"] = "approved"
                await query.edit_message_text(
                    text=f"✅ Strategy approved! Proceeding with content generation."
                )

            elif callback_data.startswith("reject_"):
                self.approval_requests[request_id]["approved"] = False
                self.approval_requests[request_id]["status"] = "rejected"
                await query.edit_message_text(
                    text=f"❌ Strategy rejected. Workflow cancelled."
                )

            elif callback_data.startswith("edit_"):
                await query.edit_message_text(
                    text=f"✏️ Please provide your feedback for edits:"
                )
                # In production, handle text input for feedback

    async def send_notification(self, user_id: str, message: str):
        """
        Send a simple notification message

        Args:
            user_id: Telegram user ID or chat ID
            message: Notification message
        """
        try:
            await self.bot.send_message(
                chat_id=user_id, text=message, parse_mode="Markdown"
            )
            logger.info(f"Notification sent to {user_id}")

        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")

    async def send_media(
        self, user_id: str, media_url: str, media_type: str, caption: str = ""
    ):
        """
        Send media (image/video) to user

        Args:
            user_id: Telegram user ID or chat ID
            media_url: URL of the media
            media_type: Type of media (photo, video, audio)
            caption: Optional caption
        """
        try:
            if media_type == "photo":
                await self.bot.send_photo(
                    chat_id=user_id, photo=media_url, caption=caption
                )
            elif media_type == "video":
                await self.bot.send_video(
                    chat_id=user_id, video=media_url, caption=caption
                )
            elif media_type == "audio":
                await self.bot.send_audio(
                    chat_id=user_id, audio=media_url, caption=caption
                )

            logger.info(f"Media sent to {user_id}")

        except Exception as e:
            logger.error(f"Failed to send media: {str(e)}")
