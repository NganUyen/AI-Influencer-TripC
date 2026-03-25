"""Render skill state and menus into Telegram message payloads."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from skills.base import SkillResult, SkillSession, SkillStatus

from .step_config import PREVIEW_ACTIONS, get_menu, get_step_definition


def _inline_keyboard_from_pairs(rows: Iterable[Iterable[tuple[str, str]]]) -> Dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": label, "callback_data": data} for label, data in row]
            for row in rows
        ]
    }


def _inline_keyboard_from_options(options: List[Dict[str, str]], prefix: str = "option::") -> Dict[str, Any]:
    rows: List[List[tuple[str, str]]] = []
    row: List[tuple[str, str]] = []
    for option in options:
        row.append((option["label"], f"{prefix}{option['value']}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return _inline_keyboard_from_pairs(rows)


class TelegramRenderer:
    """Translate skill/menu state into Telegram-safe payloads."""

    @staticmethod
    def render_menu(menu_key: str) -> Dict[str, Any]:
        menu = get_menu(menu_key) or get_menu("menu_main")
        return {
            "text": menu["text"],
            "reply_markup": _inline_keyboard_from_pairs(menu["rows"]),
            "parse_mode": None,
        }

    @classmethod
    def render_skill_prompt(cls, session: SkillSession) -> Dict[str, Any]:
        step = get_step_definition(session.skill_name, session.step_key)
        prompt_text = step.get("prompt_text") or f"{session.skill_name}: {session.step_key}"
        input_type = step.get("input_type")

        if input_type in {"persona_picker", "persona_selector"}:
            personas = session.artifacts.get("available_personas") or []
            options = [
                {
                    "label": item.get("display_name") or item.get("persona_id") or "persona",
                    "value": item.get("persona_id") or "",
                }
                for item in personas
                if item.get("persona_id")
            ]
            if step.get("allow_skip"):
                options.append({"label": "Skip", "value": "__skip__"})
            if not options:
                prompt_text = "No personas available yet. Create one first or try again later."
                return {"text": prompt_text, "reply_markup": None, "parse_mode": None}
            return {
                "text": prompt_text,
                "reply_markup": _inline_keyboard_from_options(options),
                "parse_mode": None,
            }

        if input_type == "inline_keyboard":
            return {
                "text": prompt_text,
                "reply_markup": _inline_keyboard_from_options(step.get("options", [])),
                "parse_mode": None,
            }

        if input_type == "preview_actions":
            return {
                "text": prompt_text,
                "reply_markup": _inline_keyboard_from_options(PREVIEW_ACTIONS, prefix="action::"),
                "parse_mode": None,
            }

        return {
            "text": prompt_text,
            "reply_markup": None,
            "parse_mode": None,
        }

    @classmethod
    def render_skill_result(cls, result: SkillResult) -> Dict[str, Any]:
        session = result.session
        if session is None:
            if result.success:
                status = ""
                if isinstance(result.output, dict):
                    status = result.output.get("message") or result.output.get("status") or ""
                return {
                    "text": status or "Skill flow completed.",
                    "reply_markup": None,
                    "parse_mode": None,
                }
            return {
                "text": result.error or "No active skill session.",
                "reply_markup": None,
                "parse_mode": None,
            }

        if not result.success:
            return {
                "text": result.error or "Skill execution failed.",
                "reply_markup": _inline_keyboard_from_options(
                    [{"label": "Cancel", "value": "cancel"}],
                    prefix="action::",
                ),
                "parse_mode": None,
            }

        if session.control.status == SkillStatus.preview_ready:
            output = result.output or {}
            if session.skill_name == "carousel":
                slides = output.get("slides") or []
                topic = session.collected.get("topic", "N/A")
                text = (
                    f"🎠 *Carousel Generated Successfully!*\n\n"
                    f"• *Topic*: {topic}\n"
                    f"• *Slides*: {len(slides)}\n"
                    f"• *Manifest*: {output.get('manifest_url', '-')}\n\n"
                    "Choose an action to proceed:"
                )
                return {
                    "text": text,
                    "reply_markup": _inline_keyboard_from_options(PREVIEW_ACTIONS, prefix="action::"),
                    "parse_mode": "Markdown",
                }

            image_url = (
                output.get("preview_image_url")
                or output.get("image_url")
                or session.artifacts.get("preview_image_url")
                or session.artifacts.get("final_image_url")
            )

            if session.skill_name in ("image-scene", "image_generation"):
                style = session.collected.get("style", "N/A")
                scene = session.collected.get("scene_type", "N/A")
                ratio = session.collected.get("aspect_ratio", "16:9")
                prompt = output.get("prompt") or session.collected.get("topic_or_prompt", "N/A")
                text = (
                    f"🎨 *Image Generated Successfully!*\n\n"
                    f"• *Style*: {style}\n"
                    f"• *Scene*: {scene}\n"
                    f"• *Aspect Ratio*: {ratio}\n"
                    f"• *Prompt*: {prompt}\n\n"
                    "Review the image below and choose an action."
                )
                photo_caption = (
                    f"🎨 Style: {style} | 📐 Ratio: {ratio}\n"
                    "Review the image and choose an action."
                )
            else:
                text = "Preview ready.\nReview the image below and choose an action."
                photo_caption = "Generated preview."

            payload = {
                "text": text,
                "reply_markup": _inline_keyboard_from_options(PREVIEW_ACTIONS, prefix="action::"),
                "parse_mode": "Markdown",
            }
            if image_url:
                payload["photo_url"] = image_url
                payload["photo_caption"] = photo_caption
            else:
                payload["text"] = "Preview ready.\nImage URL unavailable."
            return payload

        if session.control.status == SkillStatus.waiting_approval or result.next_step == "poll_status":
            output = result.output or {}
            workflow_id = output.get("workflow_id") or session.control.workflow_id

            if session.skill_name in ("video-ai", "video_generation"):
                persona = session.collected.get("persona_id", "N/A")
                topic = session.collected.get("topic", "N/A")
                tone = session.collected.get("tone", "N/A")
                platform = session.collected.get("platform", "N/A")
                text = (
                    f"🎬 *Video Generation Started!*\n\n"
                    f"• *Persona*: {persona}\n"
                    f"• *Topic*: {topic}\n"
                    f"• *Tone*: {tone}\n"
                    f"• *Platform*: {platform}\n\n"
                    f"Workflow ID: `{workflow_id}`\n"
                    "Waiting for approval/status updates."
                )
            else:
                text = f"Workflow started.\nWorkflow ID: `{workflow_id}`\nWaiting for approval/status updates."

            return {
                "text": text,
                "reply_markup": _inline_keyboard_from_options(
                    [{"label": "Cancel", "value": "cancel"}],
                    prefix="action::",
                ),
                "parse_mode": "Markdown",
            }

        if session.control.status == SkillStatus.done or result.next_step == "done":
            output = result.output or {}
            lines = [f"{session.skill_name} completed."]
            if isinstance(output, dict):
                if output.get("workflow_id"):
                    lines.append(f"Workflow ID: {output['workflow_id']}")
                if output.get("manifest_url"):
                    lines.append(f"Manifest: {output['manifest_url']}")
                if output.get("image_url"):
                    lines.append(f"Image: {output['image_url']}")
                if output.get("quota_summary"):
                    lines.append("Quota summary ready.")
                if output.get("persona"):
                    lines.append(f"Persona: {output['persona'].get('persona_id', '-')}")
            return {"text": "\n".join(lines), "reply_markup": None, "parse_mode": None}

        return cls.render_skill_prompt(session)
