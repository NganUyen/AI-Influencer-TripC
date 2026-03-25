"""Render skill state and menus into Telegram message payloads."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from skills import SKILL_REGISTRY
from skills.base import SkillResult, SkillSession, SkillStatus
from skills.definitions import get_skill_definition

from .step_config import PREVIEW_ACTIONS, get_menu, get_step_definition

_STATUS_LABELS = {
    "implemented_backing": "Live backend",
    "partial": "Beta / partial",
    "defined_only": "Catalog only",
    "deferred": "Planned later",
}

_INFO_BACK_MENU_BY_SKILL = {
    "image-avatar": "menu_image",
    "video-tutorial": "menu_video",
    "long-post": "menu_content",
}

_INFO_BACK_MENU_BY_PARENT = {
    "media": "menu_main",
    "image-menu": "menu_image",
    "video-menu": "menu_video",
    "manage-menu": "menu_manage",
    "persona-manager": "menu_personas",
}


def _inline_keyboard_from_pairs(rows: Iterable[Iterable[tuple[str, str]]]) -> Dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": label, "callback_data": data} for label, data in row]
            for row in rows
        ]
    }


def _inline_keyboard_from_options(
    options: List[Dict[str, str]],
    prefix: str = "option::",
) -> Dict[str, Any]:
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


def _menu_text(menu: Dict[str, Any]) -> str:
    lines = [menu["text"]]
    description_lines = menu.get("description_lines") or []
    if description_lines:
        lines.append("")
        lines.extend(description_lines)
    return "\n".join(lines)


def _image_scene_batch_keyboard() -> Dict[str, Any]:
    return _inline_keyboard_from_pairs(
        [
            [("Use Images", "action::use_images"), ("Regenerate", "action::regenerate")],
            [("Cancel", "action::cancel")],
        ]
    )


def _image_scene_selection_keyboard(
    candidates: List[Dict[str, Any]],
    selected_indexes: List[int],
) -> Dict[str, Any]:
    rows: List[List[tuple[str, str]]] = []
    row: List[tuple[str, str]] = []
    selected = set(selected_indexes)

    for index, _candidate in enumerate(candidates):
        marker = "[x]" if index in selected else "[ ]"
        row.append((f"{marker} #{index + 1}", f"action::toggle:{index}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([("Submit", "action::submit_selection"), ("Back", "action::back_to_preview")])
    rows.append([("Cancel", "action::cancel")])
    return _inline_keyboard_from_pairs(rows)


def _format_image_scene_candidates(
    candidates: List[Dict[str, Any]],
    *,
    selected_indexes: List[int] | None = None,
    intro: str,
) -> str:
    lines = [intro]
    selected = set(selected_indexes or [])

    if selected_indexes is not None:
        selected_labels = ", ".join(f"#{index + 1}" for index in selected_indexes) or "none"
        lines.append(f"Selected: {selected_labels}")

    for index, candidate in enumerate(candidates):
        prefix = "-"
        if selected_indexes is not None:
            prefix = "[x]" if index in selected else "[ ]"
        lines.append(f"{prefix} #{index + 1}: {candidate.get('url', '-')}")

    return "\n".join(lines)


def _truncate(text: str, max_length: int = 30) -> str:
    value = str(text or "").strip()
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 3]}..."


def _status_badge(status: str) -> str:
    normalized = str(status or "unknown").strip().lower()
    return {
        "failed": "FAILED",
        "scheduled": "SCHEDULED",
        "published": "PUBLISHED",
        "pending_approval": "PENDING",
        "draft": "DRAFT",
    }.get(normalized, normalized.upper() or "UNKNOWN")


def _publish_queue_keyboard(items: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    if not items:
        return _inline_keyboard_from_pairs(
            [
                [("Refresh Queue", "action::refresh_queue")],
                [("Cancel", "action::cancel")],
            ]
        )

    rows = [
        [
            (
                _truncate(
                    f"{_status_badge(item.get('status', ''))} | {item.get('title') or item.get('id')}",
                    34,
                ),
                f"option::{item.get('id')}",
            )
        ]
        for item in items
        if item.get("id")
    ]
    rows.append([("Refresh Queue", "action::refresh_queue"), ("Cancel", "action::cancel")])
    return _inline_keyboard_from_pairs(rows)


def _format_publish_queue(items: List[Dict[str, Any]], *, intro: str) -> str:
    lines = [intro]
    if not items:
        lines.append("No recent publish items were found.")
        return "\n".join(lines)

    for index, item in enumerate(items, start=1):
        title = item.get("title") or item.get("id") or "Untitled"
        platforms = ", ".join(item.get("platform") or []) or "n/a"
        lines.append(
            f"{index}. {_status_badge(item.get('status', ''))} | {_truncate(title, 42)} | {platforms}"
        )
    return "\n".join(lines)


def _publish_item_actions_keyboard(item: Dict[str, Any]) -> Dict[str, Any]:
    rows: List[List[tuple[str, str]]] = []
    if item.get("status") == "failed":
        rows.append([("Retry Publish", "action::retry_publish")])
    rows.append([("Refresh Queue", "action::refresh_queue"), ("Back", "action::back_to_queue")])
    rows.append([("Cancel", "action::cancel")])
    return _inline_keyboard_from_pairs(rows)


def _format_publish_item_details(item: Dict[str, Any], *, intro: str) -> str:
    lines = [intro]
    lines.append(f"Title: {item.get('title') or item.get('id') or '-'}")
    lines.append(f"Status: {_status_badge(item.get('status', ''))}")
    lines.append(f"Platforms: {', '.join(item.get('platform') or []) or 'n/a'}")
    if item.get("scheduledAt"):
        lines.append(f"Scheduled: {item['scheduledAt']}")
    if item.get("publishedAt"):
        lines.append(f"Published: {item['publishedAt']}")
    if item.get("workflowId"):
        lines.append(f"Workflow ID: {item['workflowId']}")
    if item.get("publishError"):
        lines.append(f"Publish error: {item['publishError']}")
    if item.get("postUrl"):
        lines.append(f"Post URL: {item['postUrl']}")
    return "\n".join(lines)


class TelegramRenderer:
    """Translate skill/menu state into Telegram-safe payloads."""

    @staticmethod
    def render_menu(menu_key: str) -> Dict[str, Any]:
        menu = get_menu(menu_key) or get_menu("menu_main")
        return {
            "text": _menu_text(menu),
            "reply_markup": _inline_keyboard_from_pairs(menu["rows"]),
            "parse_mode": None,
        }

    @staticmethod
    def render_catalog_info(skill_name: str) -> Dict[str, Any]:
        definition = get_skill_definition(skill_name)
        if not definition:
            return {
                "text": "No catalog information is available for this skill yet.",
                "reply_markup": _inline_keyboard_from_pairs([[("Back", "menu_main")]]),
                "parse_mode": None,
            }

        status = definition.get("status", "defined_only")
        api_call = definition.get("api_call") or {}
        lines = [
            definition.get("name") or skill_name,
            "",
            f"Status: {_STATUS_LABELS.get(status, status)}",
            definition.get("description") or "No description available.",
        ]
        if api_call.get("target"):
            lines.append(f"Backend: {api_call['target']}")
        note = api_call.get("note") or definition.get("integration_note")
        if note:
            lines.append(f"Note: {note}")
        if skill_name in SKILL_REGISTRY:
            lines.append("Telegram flow: available now from the studio menu.")
        else:
            lines.append("Telegram flow: not fully wired yet.")

        back_menu = _INFO_BACK_MENU_BY_SKILL.get(skill_name)
        if back_menu is None:
            back_menu = _INFO_BACK_MENU_BY_PARENT.get(definition.get("parent"), "menu_main")

        rows: List[List[tuple[str, str]]] = []
        if skill_name in SKILL_REGISTRY:
            rows.append([("Start Skill", f"skill_{skill_name}")])
        rows.append([("Back", back_menu)])
        return {
            "text": "\n".join(lines),
            "reply_markup": _inline_keyboard_from_pairs(rows),
            "parse_mode": None,
        }

    @classmethod
    def render_skill_prompt(cls, session: SkillSession) -> Dict[str, Any]:
        if session.skill_name == "image-scene" and session.step_key == "selecting_images":
            candidates = session.artifacts.get("image_candidates") or []
            selected_indexes = list(session.artifacts.get("selected_candidate_indexes") or [])
            text = _format_image_scene_candidates(
                candidates,
                selected_indexes=selected_indexes,
                intro="Select one or more images from the current batch, then press Submit.",
            )
            return {
                "text": text,
                "reply_markup": _image_scene_selection_keyboard(candidates, selected_indexes),
                "parse_mode": None,
            }

        if session.skill_name == "publish-manager" and session.step_key == "select_item":
            queue_items = list(session.artifacts.get("queue_items") or [])
            return {
                "text": _format_publish_queue(
                    queue_items,
                    intro="Publish Queue\n\nChoose a recent content item to inspect.",
                ),
                "reply_markup": _publish_queue_keyboard(queue_items),
                "parse_mode": None,
            }

        if session.skill_name == "publish-manager" and session.step_key == "publish_or_schedule":
            item = session.artifacts.get("selected_item") or {}
            return {
                "text": _format_publish_item_details(
                    item,
                    intro="Publish Item Details",
                ),
                "reply_markup": _publish_item_actions_keyboard(item),
                "parse_mode": None,
            }

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
                "reply_markup": _inline_keyboard_from_options(
                    step.get("options", PREVIEW_ACTIONS),
                    prefix="action::",
                ),
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

        if session.skill_name == "image-scene" and session.step_key == "selecting_images":
            output = result.output or {}
            candidates = output.get("image_candidates") or session.artifacts.get("image_candidates") or []
            selected_indexes = list(
                output.get("selected_candidate_indexes")
                or session.artifacts.get("selected_candidate_indexes")
                or []
            )
            intro = output.get("message") or "Select one or more images from the current batch."
            return {
                "text": _format_image_scene_candidates(
                    candidates,
                    selected_indexes=selected_indexes,
                    intro=intro,
                ),
                "reply_markup": _image_scene_selection_keyboard(candidates, selected_indexes),
                "parse_mode": None,
            }

        if session.skill_name == "publish-manager" and session.step_key == "select_item":
            output = result.output or {}
            queue_items = output.get("queue_items") or session.artifacts.get("queue_items") or []
            return {
                "text": _format_publish_queue(
                    queue_items,
                    intro=output.get("message")
                    or "Publish Queue\n\nChoose a recent content item to inspect.",
                ),
                "reply_markup": _publish_queue_keyboard(queue_items),
                "parse_mode": None,
            }

        if session.skill_name == "publish-manager" and session.step_key == "publish_or_schedule":
            output = result.output or {}
            item = output.get("content_item") or session.artifacts.get("selected_item") or {}
            return {
                "text": _format_publish_item_details(
                    item,
                    intro=output.get("message") or "Publish Item Details",
                ),
                "reply_markup": _publish_item_actions_keyboard(item),
                "parse_mode": None,
            }

        if session.control.status == SkillStatus.preview_ready:
            output = result.output or {}
            if session.skill_name == "carousel":
                slides = output.get("slides") or []
                text = (
                    "Carousel preview ready.\n"
                    f"Slides: {len(slides)}\n"
                    f"Manifest: {output.get('manifest_url', '-')}"
                )
                reply_markup = _inline_keyboard_from_options(PREVIEW_ACTIONS, prefix="action::")
            elif session.skill_name == "image-scene":
                candidates = output.get("image_candidates") or session.artifacts.get("image_candidates") or []
                text = _format_image_scene_candidates(
                    candidates,
                    intro=output.get("message")
                    or "Generated image batch ready. Choose what to do next.",
                )
                reply_markup = _image_scene_batch_keyboard()
            elif session.skill_name == "image-poster":
                text = (
                    "Poster preview ready.\n"
                    f"URL: {output.get('preview_image_url') or output.get('image_url') or '-'}\n"
                    f"Style: {output.get('style') or session.collected.get('style') or '-'}\n"
                    f"Tone: {output.get('tone') or session.collected.get('tone') or '-'}"
                )
                reply_markup = _inline_keyboard_from_options(PREVIEW_ACTIONS, prefix="action::")
            else:
                text = (
                    "Preview ready.\n"
                    f"URL: {output.get('preview_image_url') or output.get('image_url') or '-'}"
                )
                reply_markup = _inline_keyboard_from_options(PREVIEW_ACTIONS, prefix="action::")
            return {
                "text": text,
                "reply_markup": reply_markup,
                "parse_mode": None,
            }

        if session.control.status == SkillStatus.waiting_approval or result.next_step == "poll_status":
            output = result.output or {}
            workflow_id = output.get("workflow_id") or session.control.workflow_id
            return {
                "text": f"Workflow started.\nWorkflow ID: {workflow_id}\nWaiting for approval/status updates.",
                "reply_markup": _inline_keyboard_from_options(
                    [{"label": "Cancel", "value": "cancel"}],
                    prefix="action::",
                ),
                "parse_mode": None,
            }

        if session.control.status == SkillStatus.done or result.next_step == "done":
            output = result.output or {}
            lines = [f"{session.skill_name} completed."]
            if isinstance(output, dict):
                if output.get("message"):
                    lines.append(output["message"])
                if output.get("workflow_id"):
                    lines.append(f"Workflow ID: {output['workflow_id']}")
                if output.get("manifest_url"):
                    lines.append(f"Manifest: {output['manifest_url']}")
                if output.get("image_urls"):
                    lines.append(f"Images selected: {len(output['image_urls'])}")
                    for index, url in enumerate(output["image_urls"]):
                        lines.append(f"#{index + 1}: {url}")
                elif output.get("image_url"):
                    lines.append(f"Image: {output['image_url']}")
                if output.get("quota_summary"):
                    lines.append("Quota summary ready.")
                if output.get("persona"):
                    lines.append(f"Persona: {output['persona'].get('persona_id', '-')}")
                if output.get("content_item"):
                    item = output["content_item"]
                    lines.append(f"Item: {item.get('title') or item.get('id') or '-'}")
                    lines.append(f"Status: {_status_badge(item.get('status', ''))}")
            return {"text": "\n".join(lines), "reply_markup": None, "parse_mode": None}

        return cls.render_skill_prompt(session)
