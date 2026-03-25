"""Renderer tests for the Telegram studio surface."""

from services.telegram_renderer import TelegramRenderer
from skills.publish_manager import PublishManagerSkill


def test_render_menu_main_includes_new_studio_copy():
    rendered = TelegramRenderer.render_menu("menu_main")

    assert "TripC Media Studio" in rendered["text"]
    rows = rendered["reply_markup"]["inline_keyboard"]
    callback_values = {button["callback_data"] for row in rows for button in row}
    assert "menu_image" in callback_values
    assert "menu_content" in callback_values


def test_render_catalog_info_for_long_post_points_back_to_content_menu():
    rendered = TelegramRenderer.render_catalog_info("long-post")

    assert "Status:" in rendered["text"]
    rows = rendered["reply_markup"]["inline_keyboard"]
    assert rows[-1][0]["callback_data"] == "menu_content"


def test_render_publish_manager_prompt_shows_queue_actions():
    session = PublishManagerSkill.initial_session()
    session.step_key = "select_item"
    session.artifacts["queue_items"] = [
        {
            "id": "failed-1",
            "title": "Retry this failed post",
            "status": "failed",
            "platform": ["facebook"],
        }
    ]

    rendered = TelegramRenderer.render_skill_prompt(session)

    assert "Publish Queue" in rendered["text"]
    rows = rendered["reply_markup"]["inline_keyboard"]
    callback_values = [button["callback_data"] for row in rows for button in row]
    assert "option::failed-1" in callback_values
    assert "action::refresh_queue" in callback_values
