"""Reference Telegram router implementation for image-scene skill with multi-candidate selection.

This is a template for how to integrate the new image-scene skill with Telegram.
Shows button callbacks, gallery rendering, and session management.
"""

from typing import Any, Dict, List, Optional
import json
from aiogram import Bot, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from aiogram.filters.callback_data import CallbackData

from skills.image_scene import ImageSceneSkill
from services.skill_session_store import SkillSessionStore


# ═══════════════════════════════════════════════════════════════════════════════
# Callback Data Models
# ═══════════════════════════════════════════════════════════════════════════════

class ImageSceneCallback(CallbackData, prefix="img_scene"):
    """Callback data for image-scene skill actions."""
    action: str  # "select_candidate", "regenerate", "cancel"
    session_id: str
    index: Optional[int] = None  # For select_candidate action


# ═══════════════════════════════════════════════════════════════════════════════
# Gallery Renderer
# ═══════════════════════════════════════════════════════════════════════════════

async def render_image_gallery(
    bot: Bot,
    chat_id: int,
    candidates: List[Dict[str, Any]],
    message: str,
    session_id: str,
) -> None:
    """
    Send 4 images as a media group with selection buttons below.

    Args:
        bot: Aiogram bot instance
        chat_id: Telegram chat ID
        candidates: List of image dicts with 'url' keys
        message: Caption message
        session_id: Skill session ID for button callbacks
    """

    # Build media group (up to 10 media items)
    media_group = [
        InputMediaPhoto(media=candidate["url"], caption=f"Option {i + 1}")
        for i, candidate in enumerate(candidates[:10])
    ]

    # Send media group
    if media_group:
        await bot.send_media_group(chat_id=chat_id, media=media_group)

    # Build selection buttons
    buttons: List[List[InlineKeyboardButton]] = []

    # Row 1-2: Selection buttons (2 per row)
    selection_buttons = []
    for i in range(len(candidates)):
        callback_data = ImageSceneCallback(
            action="select_candidate",
            session_id=session_id,
            index=i
        )
        selection_buttons.append(
            InlineKeyboardButton(
                text=f"✅ #{i + 1}",
                callback_data=callback_data.pack()
            )
        )

    # Arrange selection buttons in pairs
    for i in range(0, len(selection_buttons), 2):
        row = selection_buttons[i : i + 2]
        buttons.append(row)

    # Bottom row: Regenerate + Cancel
    bottom_row = [
        InlineKeyboardButton(
            text="🔄 More Options",
            callback_data=ImageSceneCallback(
                action="regenerate",
                session_id=session_id
            ).pack()
        ),
        InlineKeyboardButton(
            text="❌ Cancel",
            callback_data=ImageSceneCallback(
                action="cancel",
                session_id=session_id
            ).pack()
        ),
    ]
    buttons.append(bottom_row)

    # Send message with buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await bot.send_message(
        chat_id=chat_id,
        text=message,
        reply_markup=keyboard
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Button Callback Handler
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_image_scene_button(
    bot: Bot,
    callback_query: types.CallbackQuery,
    callback_data: ImageSceneCallback,
    session_store: SkillSessionStore,
    backend_url: str,
    http_client: Any,
) -> None:
    """
    Handle image-scene skill button clicks.

    Supports:
    - select_candidate: User picks one of the 4 images
    - regenerate: Generate 4 new images
    - cancel: Abort the skill
    """

    user_id = callback_query.from_user.id
    session_id = callback_data.session_id

    # Acknowledge the callback (removes "loading" state)
    await callback_query.answer()

    try:
        # Load session from store
        session = await session_store.get(user_id, session_id)
        if not session:
            await callback_query.message.edit_text(
                "❌ Session expired. Please start over with /media"
            )
            return

        if callback_data.action == "select_candidate":
            # User selected one image
            index = callback_data.index
            result = ImageSceneSkill.handle_selection(session, index)

            if result.success:
                # Update session in store
                await session_store.save(user_id, result.session)

                # Show confirmation
                selected_url = result.output["image_url"]
                await callback_query.message.delete()

                await bot.send_photo(
                    chat_id=user_id,
                    photo=selected_url,
                    caption=(
                        f"✅ Selected image #{result.output['selected_index'] + 1}\n\n"
                        f"Ready to use in your content creation!"
                    )
                )
            else:
                await callback_query.message.edit_text(
                    f"❌ Error: {result.error}"
                )

        elif callback_data.action == "regenerate":
            # Clear candidates and generate new batch
            session.artifacts["image_candidates"] = []
            session.step_key = "generating_candidates"

            # Re-execute skill to generate new candidates
            result = await ImageSceneSkill.execute(
                session,
                backend_url,
                http_client
            )

            if result.success:
                # Update session
                await session_store.save(user_id, result.session)

                # Update message text
                await callback_query.message.edit_text(
                    "🔄 Generating new images..."
                )

                # Send new gallery
                await render_image_gallery(
                    bot,
                    user_id,
                    result.output["image_candidates"],
                    result.output["message"],
                    session_id
                )
            else:
                await callback_query.message.edit_text(
                    f"❌ Generation failed: {result.error}"
                )

        elif callback_data.action == "cancel":
            # Clean up session and cancel
            await session_store.delete(user_id, session_id)
            await callback_query.message.delete()

            await bot.send_message(
                chat_id=user_id,
                text="❌ Image creation cancelled."
            )

    except Exception as e:
        await callback_query.message.edit_text(
            f"❌ Unexpected error: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Main Skill Executor (Called from /media menu)
# ═══════════════════════════════════════════════════════════════════════════════

async def execute_image_scene_skill(
    bot: Bot,
    user_id: int,
    collected: Dict[str, Any],  # {"topic_or_prompt": "...", "style": "..."}
    session_store: SkillSessionStore,
    backend_url: str,
    http_client: Any,
) -> None:
    """
    Execute image-scene skill from the /media menu.

    User has already provided:
    - topic_or_prompt (required)
    - style (required)
    - Optional: persona_id, aspect_ratio, scene_type, freeform_brief, creative_notes
    """

    # Initialize session
    session = ImageSceneSkill.initial_session()
    session.collected.update(collected)

    # Generate unique session ID
    session_id = f"{user_id}_{int(time.time())}"

    # Save session
    await session_store.save(user_id, session, session_id)

    try:
        # Execute skill (generates 4 candidates)
        result = await ImageSceneSkill.execute(
            session,
            backend_url,
            http_client
        )

        if result.success:
            # Update session with result
            await session_store.save(user_id, result.session, session_id)

            # Check which step we're at
            if result.next_step == "selecting_image":
                # Display gallery + buttons
                await render_image_gallery(
                    bot,
                    user_id,
                    result.output["image_candidates"],
                    result.output["message"],
                    session_id
                )

            elif result.next_step == "done":
                # Already selected (shouldn't happen on first execute)
                await bot.send_photo(
                    chat_id=user_id,
                    photo=result.output["image_url"],
                    caption="✅ Image ready to use!"
                )
        else:
            await bot.send_message(
                chat_id=user_id,
                text=f"❌ Image generation failed: {result.error}"
            )

    except Exception as e:
        await bot.send_message(
            chat_id=user_id,
            text=f"❌ Unexpected error: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Example Usage in Router Setup
# ═══════════════════════════════════════════════════════════════════════════════

"""
# In your main bot/telegram setup file:

from aiogram import Dispatcher, Router, types
from aiogram.filters.callback_data import CallbackData
import httpx

dp = Dispatcher()
router = Router()

# Dependencies
session_store = SkillSessionStore()  # Redis or in-memory
backend_url = "http://localhost:8000"

@router.callback_query(ImageSceneCallback.filter())
async def image_scene_callback_handler(
    query: types.CallbackQuery,
    callback_data: ImageSceneCallback,
):
    '''Handle image-scene button clicks.'''
    async with httpx.AsyncClient() as http_client:
        await handle_image_scene_button(
            bot=query.bot,
            callback_query=query,
            callback_data=callback_data,
            session_store=session_store,
            backend_url=backend_url,
            http_client=http_client,
        )


@router.message(Command("image-scene"))
async def start_image_scene(message: types.Message):
    '''Start image-scene skill from command or menu.'''

    # In real implementation, this would come from the /media menu
    # and user would have already provided topic + style

    collected = {
        "topic_or_prompt": "beautiful sunset landscape",
        "style": "realistic photography",
        "aspect_ratio": "16:9",
    }

    async with httpx.AsyncClient() as http_client:
        await execute_image_scene_skill(
            bot=message.bot,
            user_id=message.from_user.id,
            collected=collected,
            session_store=session_store,
            backend_url=backend_url,
            http_client=http_client,
        )


dp.include_router(router)
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Unit Tests
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import pytest
    import asyncio
    from unittest.mock import Mock, AsyncMock, patch

    @pytest.mark.asyncio
    async def test_handle_image_selection():
        """Test selecting one of the generated images."""
        # Create mock session with 4 candidates
        session = ImageSceneSkill.initial_session()
        session.artifacts["image_candidates"] = [
            {"url": f"https://example.com/img{i}.jpg", "storage_key": f"key{i}"}
            for i in range(4)
        ]
        session.step_key = "selecting_image"

        # User selects image #1 (index=1)
        result = ImageSceneSkill.handle_selection(session, selected_index=1)

        # Verify result
        assert result.success == True
        assert result.next_step == "done"
        assert result.output["selected_index"] == 1
        assert result.session.artifacts["final_image_url"] == "https://example.com/img1.jpg"

    @pytest.mark.asyncio
    async def test_handle_invalid_selection():
        """Test selecting an invalid index."""
        session = ImageSceneSkill.initial_session()
        session.artifacts["image_candidates"] = [
            {"url": "https://example.com/img0.jpg", "storage_key": "key0"}
        ]

        # Try to select index 5 (out of range)
        result = ImageSceneSkill.handle_selection(session, selected_index=5)

        # Should fail
        assert result.success == False
        assert "Invalid selection" in result.error

    def test_callback_data_packing():
        """Test ImageSceneCallback data serialization."""
        callback = ImageSceneCallback(
            action="select_candidate",
            session_id="user123_session456",
            index=2
        )

        packed = callback.pack()
        assert "select_candidate" in packed
        assert "user123_session456" in packed
        assert "2" in packed


# Run tests: pytest telegram_router_example.py -v
