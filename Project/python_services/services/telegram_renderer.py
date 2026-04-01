"""Render skill state and menus into Telegram message payloads."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from skills import SKILL_REGISTRY
from skills.base import SkillResult, SkillSession, SkillStatus
from skills.definitions import get_skill_definition

from .google_tts_service import GoogleTTSService
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

_CANCELLATION_COPY = {
    "persona-creator": (
        "🛑 Persona creation cancelled.\n"
        "Your current preview was not saved, so this persona is still just a draft. "
        "Start again anytime when you're ready."
    ),
    "image-scene": (
        "🛑 Image generation cancelled.\n"
        "No new image was selected or saved from this run. "
        "You can generate another set whenever you want."
    ),
    "image_generation": (
        "🛑 Image generation cancelled.\n"
        "No new image was selected or saved from this run. "
        "You can generate another set whenever you want."
    ),
    "image-poster": (
        "🛑 Poster creation cancelled.\n"
        "This preview was discarded and nothing new was saved. "
        "You can create another poster anytime."
    ),
    "video-ai": (
        "🛑 Video workflow cancelled.\n"
        "No further generation steps will run for this request."
    ),
    "video_generation": (
        "🛑 Video workflow cancelled.\n"
        "No further generation steps will run for this request."
    ),
}


def _inline_keyboard_from_pairs(
    rows: Iterable[Iterable[tuple[str, str]]],
) -> Dict[str, Any]:
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
            [
                ("Use Images", "action::use_images"),
                ("Regenerate", "action::regenerate"),
            ],
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

    rows.append(
        [("Submit", "action::submit_selection"), ("Back", "action::back_to_preview")]
    )
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
        selected_labels = (
            ", ".join(f"#{index + 1}" for index in selected_indexes) or "none"
        )
        lines.append(f"Selected: {selected_labels}")

    for index, candidate in enumerate(candidates):
        prefix = "-"
        if selected_indexes is not None:
            prefix = "[x]" if index in selected else "[ ]"
        lines.append(f"{prefix} #{index + 1}: {candidate.get('url', '-')}")

    return "\n".join(lines)


def _render_cancelled_result(
    session: SkillSession, output: Dict[str, Any]
) -> Dict[str, Any]:
    text = _CANCELLATION_COPY.get(
        session.skill_name,
        "🛑 Action cancelled.\nNothing else will run for this request.",
    )
    workflow_id = output.get("workflow_id")
    if workflow_id:
        text = f"{text}\nWorkflow ID: `{workflow_id}`"
    return {
        "text": text,
        "reply_markup": None,
        "parse_mode": "Markdown" if workflow_id else None,
    }


def _truncate(text: str, max_length: int = 30) -> str:
    value = str(text or "").strip()
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 3]}..."


def _humanize_token(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    return text.replace("_", " ").strip().title()


def _video_ai_concept_text(
    concept: Dict[str, Any], persona_snapshot: Dict[str, Any]
) -> str:
    persona_label = (
        persona_snapshot.get("display_name")
        or persona_snapshot.get("persona_id")
        or concept.get("persona_id")
        or "-"
    )
    lines = [
        "Video Concept Ready",
        "",
        f"Persona: {persona_label}",
        f"Feature Focus: {concept.get('feature_focus') or '-'}",
        f"Goal: {_humanize_token(concept.get('video_goal'))}",
        f"Audience: {concept.get('audience') or '-'}",
        f"CTA: {concept.get('cta') or '-'}",
        f"Source URL: {concept.get('reference_url') or '-'}",
        f"Access: {_humanize_token(concept.get('access_level'))}",
        f"Tone: {concept.get('tone_resolved') or persona_snapshot.get('tone_resolved') or '-'}",
    ]
    source_summary = str(concept.get("source_summary") or "").strip()
    if source_summary:
        lines.extend(["", f"Source Summary: {source_summary}"])
    lines.extend(["", "Approve this brief, edit the inputs, or regenerate it."])
    return "\n".join(lines)


def _video_ai_beats_text(beat_sheet: Dict[str, Any], concept: Dict[str, Any]) -> str:
    lines = [
        "Beat Plan Ready",
        "",
        f"Feature Focus: {concept.get('feature_focus') or '-'}",
        f"Goal: {_humanize_token(concept.get('video_goal'))}",
        "",
    ]
    for beat in beat_sheet.get("beats") or []:
        idx = beat.get("idx") or "?"
        purpose = _humanize_token(beat.get("purpose"))
        bottom = beat.get("bottom_half_message") or "-"
        target = beat.get("top_half_target") or "-"
        source_type = _humanize_token(beat.get("top_half_source_type"))
        lines.append(f"{idx}. {purpose}: {bottom}")
        lines.append(f"   Top Half: {target} ({source_type})")
    lines.extend(["", "Approve this beat plan, edit the inputs, or regenerate it."])
    return "\n".join(lines)


def _video_ai_retry_options(
    options: List[Dict[str, str]],
    *,
    allow_approve: bool,
) -> List[Dict[str, str]]:
    if allow_approve:
        return options
    return [option for option in options if option.get("value") != "approve"]


def _video_ai_retry_text(
    *,
    error: str,
    concept: Dict[str, Any] | None = None,
    beat_sheet: Dict[str, Any] | None = None,
    persona_snapshot: Dict[str, Any] | None = None,
) -> str:
    lines = [error]
    if beat_sheet:
        lines.extend(["", _video_ai_beats_text(beat_sheet, concept or {})])
    elif concept:
        lines.extend(["", _video_ai_concept_text(concept, persona_snapshot or {})])
    else:
        lines.extend(["", "Use Regenerate to try again, or Edit to revise the inputs."])
    return "\n".join(lines)


def _status_badge(status: str) -> str:
    normalized = str(status or "unknown").strip().lower()
    return {
        "failed": "FAILED",
        "scheduled": "SCHEDULED",
        "published": "PUBLISHED",
        "pending_approval": "PENDING",
        "draft": "DRAFT",
    }.get(normalized, normalized.upper() or "UNKNOWN")


def _persona_check_badge(value: bool) -> str:
    return "YES" if value else "NO"


def _render_persona_inspector_result(
    *,
    session: SkillSession,
    output: Dict[str, Any],
) -> Dict[str, Any]:
    persona = (
        output.get("persona")
        or (session.artifacts.get("persona_summary") or {}).get("persona")
        or {}
    )
    readiness = (
        output.get("readiness")
        or (session.artifacts.get("persona_summary") or {}).get("readiness")
        or {}
    )
    persona_id = (
        persona.get("persona_id")
        or session.collected.get("persona_id")
        or session.artifacts.get("persona_id")
        or "unknown"
    )
    display_name = persona.get("display_name") or persona_id
    language = persona.get("language") or "—"
    tts_voice = GoogleTTSService.describe_voice(
        persona.get("tts_voice"),
        language=persona.get("language"),
    )
    status = persona.get("status") or "unknown"
    avatar_image_url = (
        output.get("preview_image_url")
        or persona.get("avatar_image_url")
        or session.artifacts.get("preview_image_url")
    )
    readiness_checks = readiness.get("checks") or {}
    lines = [
        "✅ Persona inspection completed.",
        "",
        f"👤 Persona: {display_name}",
        f"• ID: {persona_id}",
        f"• Status: {status}",
        f"• Language: {language}",
        f"• TTS Voice: {tts_voice}",
        f"• Avatar Media Asset: {persona.get('avatar_media_asset_id') or 'missing'}",
        f"• HeyGen Avatar ID: {persona.get('heygen_avatar_id') or 'missing'}",
        f"• Readiness: {'READY' if readiness.get('ready') else 'NOT READY'}",
        f"• Blocking Reason: {readiness.get('blocking_reason') or 'None'}",
        "",
        "Checks:",
        f"• Status ready: {_persona_check_badge(bool(readiness_checks.get('status_ready')))}",
        f"• TTS voice: {_persona_check_badge(bool(readiness_checks.get('has_tts_voice')))}",
        f"• Avatar image URL: {_persona_check_badge(bool(avatar_image_url))}",
        f"• Avatar media asset: {_persona_check_badge(bool(readiness_checks.get('has_avatar_asset')))}",
        f"• HeyGen avatar: {_persona_check_badge(bool(readiness_checks.get('has_heygen_avatar_id')))}",
    ]
    if persona.get("thumbnail_url"):
        lines.append(f"• Thumbnail: {persona.get('thumbnail_url')}")
    if persona.get("description"):
        lines.extend(["", f"Description: {persona.get('description')}"])
    if not avatar_image_url:
        lines.extend(
            [
                "",
                "⚠️ Avatar preview image is not available yet.",
                "The persona currently has no renderable image URL to show in Telegram.",
            ]
        )

    # Add Edit Buttons
    persona_actions = [
        [("✏️ Name", f"edit_p_name::{persona_id}"), ("🎭 Appearance", f"edit_p_appearance::{persona_id}")],
        [("🔄 Regenerate Image", f"edit_p_appearance::{persona_id}")],
        [("Refresh", f"inspect_persona::{persona_id}")],
    ]
    
    payload: Dict[str, Any] = {
        "text": "\n".join(lines),
        "reply_markup": _inline_keyboard_from_pairs(persona_actions, prefix="action::"),
        "parse_mode": None,
    }
    if avatar_image_url:
        payload["photo_url"] = avatar_image_url
        payload["photo_caption"] = (
            f"👤 {display_name}\n"
            f"Status: {status} | Readiness: {'READY' if readiness.get('ready') else 'NOT READY'}"
        )
    return payload


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
    rows.append(
        [("Refresh Queue", "action::refresh_queue"), ("Cancel", "action::cancel")]
    )
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
    rows.append([("Inspect Provider", "action::inspect_provider_wiring")])
    rows.append([("Check Engagement", "action::check_engagement")])
    if item.get("status") in {"published", "scheduled"} or item.get("postUrl"):
        rows.append([("Boost Engagement", "action::boost_engagement")])
    if item.get("status") == "failed":
        rows.append([("Retry Publish", "action::retry_publish")])
    rows.append(
        [("Refresh Queue", "action::refresh_queue"), ("Back", "action::back_to_queue")]
    )
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
    if item.get("publishMethod"):
        lines.append(f"Publish method: {item['publishMethod']}")
    if item.get("platformPostId"):
        lines.append(f"Platform post ID: {item['platformPostId']}")
    if item.get("providerPostId"):
        lines.append(f"Provider post ID: {item['providerPostId']}")
    if item.get("publishError"):
        lines.append(f"Publish error: {item['publishError']}")
    if item.get("postUrl"):
        lines.append(f"Post URL: {item['postUrl']}")
    if item.get("syndicateTriggered") is not None:
        lines.append(
            f"Syndicate triggered: {'yes' if item.get('syndicateTriggered') else 'no'}"
        )
    if item.get("syndicateJobId"):
        lines.append(f"Syndicate job ID: {item['syndicateJobId']}")
    metrics = item.get("engagementMetrics") or {}
    if isinstance(metrics, dict) and metrics:
        engagement_rate = metrics.get("engagement_rate")
        if engagement_rate is not None:
            lines.append(f"Engagement rate: {engagement_rate}")
        lines.append(f"Metrics source: {metrics.get('source') or 'provider'}")
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
            back_menu = _INFO_BACK_MENU_BY_PARENT.get(
                definition.get("parent"), "menu_main"
            )

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
        if (
            session.skill_name == "persona-creator"
            and session.step_key == "preview"
        ):
            step = get_step_definition(session.skill_name, session.step_key)
            persona_id = session.artifacts.get("persona_id") or session.collected.get("persona_id", "—")
            image_url = (
                session.artifacts.get("avatar_image_url")
                or session.artifacts.get("preview_image_url")
                or session.collected.get("avatar_image_url")
                or session.artifacts.get("persona_data", {}).get("avatar_image_url")
            )
            
            # Simple metadata summary for the prompt
            language = session.artifacts.get("language") or session.collected.get("language", "—")
            voice = (
                session.artifacts.get("tts_voice") 
                or session.collected.get("voice")
                or session.artifacts.get("persona_data", {}).get("tts_voice", "—")
            )
            display_name = session.artifacts.get("persona_data", {}).get("display_name") or persona_id
            
            prompt_text = step.get("prompt_text") or "✨ *Persona Profile Ready\\!*"
            # Readiness/Status message restoration
            readiness = session.artifacts.get("readiness") or {}
            blocking_reason = readiness.get("blocking_reason")
            status_text = ""
            if blocking_reason:
                status_text = f"\n\n⚠️ {blocking_reason}"
            elif readiness.get("ready"):
                status_text = "\n\n✅ All checks passed; ready for production\\!"

            full_text = (
                f"{prompt_text}\n\n"
                f"• ID: `{persona_id}`\n"
                f"• Language: {language}\n"
                f"• Voice: {voice}\n"
                f"{status_text}\n\n"
                "Use the buttons below to edit or proceed\\."
            )
            
            payload = {
                "text": full_text,
                "reply_markup": _inline_keyboard_from_options(
                    step.get("options", []),
                    prefix="action::",
                ),
                "parse_mode": "Markdown",
            }
            if image_url:
                payload["photo_url"] = image_url
                payload["photo_caption"] = f"👤 {display_name} | {language}"
                
            return payload

        if session.skill_name == "video-ai" and session.step_key == "confirm_concept":
            step = get_step_definition(session.skill_name, session.step_key)
            concept = session.artifacts.get("concept_brief") or {}
            persona_snapshot = session.artifacts.get("persona_snapshot") or {}
            return {
                "text": _video_ai_concept_text(concept, persona_snapshot),
                "reply_markup": _inline_keyboard_from_options(
                    step.get("options", []),
                    prefix="action::",
                ),
                "parse_mode": None,
            }

        if session.skill_name == "video-ai" and session.step_key == "confirm_beats":
            step = get_step_definition(session.skill_name, session.step_key)
            beat_sheet = session.artifacts.get("beat_sheet") or {}
            concept = session.artifacts.get("concept_brief") or {}
            return {
                "text": _video_ai_beats_text(beat_sheet, concept),
                "reply_markup": _inline_keyboard_from_options(
                    step.get("options", []),
                    prefix="action::",
                ),
                "parse_mode": None,
            }

        if session.skill_name == "video-ai" and session.step_key == "package_ready":
            workflow_id = session.control.workflow_id or session.artifacts.get(
                "workflow_id"
            )
            if workflow_id:
                production_note = session.artifacts.get("production_note")
                topic = (
                    session.collected.get("topic")
                    or session.collected.get("idea_brief")
                    or "N/A"
                )
                tone = session.collected.get("tone", "natural")
                platform = session.collected.get("platform", "N/A")
                lines = [
                    "🎬 *Video Generation Started!*",
                    "",
                    f"• *Persona*: {session.collected.get('persona_id', 'N/A')}",
                    f"• *Topic*: {topic}",
                    f"• *Tone*: {tone}",
                    f"• *Platform*: {platform}",
                    "",
                    f"Workflow ID: `{workflow_id}`",
                    "Script review and the final preview will arrive in this chat.",
                ]
                if production_note:
                    lines.extend(["", production_note])
                return {
                    "text": "\n".join(lines),
                    "reply_markup": _inline_keyboard_from_options(
                        [{"label": "Cancel", "value": "cancel"}],
                        prefix="action::",
                    ),
                    "parse_mode": "Markdown",
                }

        if (
            session.skill_name == "image-scene"
            and session.step_key == "selecting_images"
        ):
            candidates = session.artifacts.get("image_candidates") or []
            selected_indexes = list(
                session.artifacts.get("selected_candidate_indexes") or []
            )
            text = _format_image_scene_candidates(
                candidates,
                selected_indexes=selected_indexes,
                intro="Select one or more images from the current batch, then press Submit.",
            )
            return {
                "text": text,
                "reply_markup": _image_scene_selection_keyboard(
                    candidates, selected_indexes
                ),
                "parse_mode": None,
            }

        if (
            session.skill_name == "publish-manager"
            and session.step_key == "select_item"
        ):
            queue_items = list(session.artifacts.get("queue_items") or [])
            return {
                "text": _format_publish_queue(
                    queue_items,
                    intro="Publish Queue\n\nChoose a recent content item to inspect.",
                ),
                "reply_markup": _publish_queue_keyboard(queue_items),
                "parse_mode": None,
            }

        if session.skill_name == "daily-story" and session.step_key == "choose_media_action":
            step = get_step_definition(session.skill_name, session.step_key)
            story_draft = session.artifacts.get("story_draft") or {}
            title = story_draft.get("title", "Daily Story")
            body = story_draft.get("body", "")
            tags = " ".join(f"#{t}" for t in story_draft.get("hashtags", []))
            
            prompt_text = step.get("prompt_text") or "Story draft is ready!"
            full_text = f"*{title}*\n\n{body}\n\n{tags}\n\n{prompt_text}"
            
            return {
                "text": full_text,
                "reply_markup": _inline_keyboard_from_options(
                    step.get("options", []),
                    prefix="action::",
                ),
                "parse_mode": "Markdown",
            }

        if (
            session.skill_name == "publish-manager"
            and session.step_key == "publish_or_schedule"
        ):
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
        prompt_text = (
            step.get("prompt_text") or f"{session.skill_name}: {session.step_key}"
        )
        input_type = step.get("input_type")

        if input_type in {"persona_picker", "persona_selector"}:
            personas = session.artifacts.get("available_personas") or []
            options = [
                {
                    "label": item.get("display_name")
                    or item.get("persona_id")
                    or "persona",
                    "value": item.get("persona_id") or "",
                }
                for item in personas
                if item.get("persona_id")
            ]
            if step.get("allow_skip"):
                options.append({"label": "Skip", "value": "__skip__"})
            if not options:
                prompt_text = "🚫 No personas available yet. Please create one first or try again later."
                return {"text": prompt_text, "reply_markup": None, "parse_mode": None}
            
            # Use 'action::inspect_persona::' for better bootstrapping
            prefix = "action::inspect_persona::" if session.skill_name == "persona-inspector" else "option::"
            return {
                "text": prompt_text,
                "reply_markup": _inline_keyboard_from_options(options, prefix=prefix),
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
                    status = (
                        result.output.get("message")
                        or result.output.get("status")
                        or ""
                    )
                    if result.output.get("status") == "cancelled":
                        status = "🛑 Action cancelled.\nNothing else will run for this request."
                return {
                    "text": status or "✨ Skill flow completed successfully.",
                    "reply_markup": None,
                    "parse_mode": None,
                }
            return {
                "text": result.error or "⚠️ No active skill session.",
                "reply_markup": None,
                "parse_mode": None,
            }

        if not result.success:
            if session.skill_name == "video-ai" and session.step_key == "package_ready":
                output = result.output or {}
                package = (
                    output.get("approved_production_package")
                    or session.artifacts.get("approved_production_package")
                    or {}
                )
                concept = (
                    package.get("concept_brief")
                    or session.artifacts.get("concept_brief")
                    or {}
                )
                beat_sheet = (
                    package.get("beat_sheet")
                    or session.artifacts.get("beat_sheet")
                    or {}
                )
                beat_count = len(beat_sheet.get("beats") or [])
                production_note = (
                    output.get("production_note")
                    or session.artifacts.get("production_note")
                )
                lines = [
                    "Pre-production package ready.",
                    "Production workflow could not be started.",
                    "",
                    f"Persona: {concept.get('persona_id') or '-'}",
                    f"Feature Focus: {concept.get('feature_focus') or '-'}",
                    f"Goal: {_humanize_token(concept.get('video_goal'))}",
                    f"Beats: {beat_count}",
                ]
                if production_note:
                    lines.extend(["", production_note])
                if result.error:
                    lines.extend(["", f"Start error: {result.error}"])
                return {
                    "text": "\n".join(lines),
                    "reply_markup": _inline_keyboard_from_options(
                        [
                            {"label": "Retry Start", "value": "retry_start"},
                            {"label": "Cancel", "value": "cancel"},
                        ],
                        prefix="action::",
                    ),
                    "parse_mode": None,
                }
            if session.skill_name == "video-ai" and session.step_key in {
                "confirm_concept",
                "confirm_beats",
            }:
                output = result.output or {}
                concept = (
                    output.get("concept_brief")
                    or session.artifacts.get("concept_brief")
                    or {}
                )
                beat_sheet = (
                    output.get("beat_sheet")
                    or session.artifacts.get("beat_sheet")
                    or {}
                )
                persona_snapshot = (
                    output.get("persona_snapshot")
                    or session.artifacts.get("persona_snapshot")
                    or {}
                )
                step = get_step_definition(session.skill_name, session.step_key)
                allow_approve = (
                    bool(concept)
                    if session.step_key == "confirm_concept"
                    else bool(beat_sheet)
                )
                return {
                    "text": _video_ai_retry_text(
                        error=result.error or "Pre-production step failed.",
                        concept=concept,
                        beat_sheet=beat_sheet,
                        persona_snapshot=persona_snapshot,
                    ),
                    "reply_markup": _inline_keyboard_from_options(
                        _video_ai_retry_options(
                            step.get("options", []),
                            allow_approve=allow_approve,
                        ),
                        prefix="action::",
                    ),
                    "parse_mode": None,
                }
            return {
                "text": result.error or "❌ Skill execution failed. Please try again.",
                "reply_markup": _inline_keyboard_from_options(
                    [{"label": "Cancel", "value": "cancel"}],
                    prefix="action::",
                ),
                "parse_mode": None,
            }

        if session.skill_name == "video-ai" and session.step_key == "confirm_concept":
            output = result.output or {}
            concept = (
                output.get("concept_brief")
                or session.artifacts.get("concept_brief")
                or {}
            )
            persona_snapshot = (
                output.get("persona_snapshot")
                or session.artifacts.get("persona_snapshot")
                or {}
            )
            step = get_step_definition(session.skill_name, session.step_key)
            return {
                "text": _video_ai_concept_text(concept, persona_snapshot),
                "reply_markup": _inline_keyboard_from_options(
                    step.get("options", []),
                    prefix="action::",
                ),
                "parse_mode": None,
            }

        if session.skill_name == "video-ai" and session.step_key == "confirm_beats":
            output = result.output or {}
            beat_sheet = (
                output.get("beat_sheet") or session.artifacts.get("beat_sheet") or {}
            )
            concept = (
                output.get("concept_brief")
                or session.artifacts.get("concept_brief")
                or {}
            )
            step = get_step_definition(session.skill_name, session.step_key)
            return {
                "text": _video_ai_beats_text(beat_sheet, concept),
                "reply_markup": _inline_keyboard_from_options(
                    step.get("options", []),
                    prefix="action::",
                ),
                "parse_mode": None,
            }

        if (
            session.skill_name == "image-scene"
            and session.step_key == "selecting_images"
        ):
            output = result.output or {}
            candidates = (
                output.get("image_candidates")
                or session.artifacts.get("image_candidates")
                or []
            )
            selected_indexes = list(
                output.get("selected_candidate_indexes")
                or session.artifacts.get("selected_candidate_indexes")
                or []
            )
            intro = (
                output.get("message")
                or "Select one or more images from the current batch."
            )
            return {
                "text": _format_image_scene_candidates(
                    candidates,
                    selected_indexes=selected_indexes,
                    intro=intro,
                ),
                "reply_markup": _image_scene_selection_keyboard(
                    candidates, selected_indexes
                ),
                "parse_mode": None,
            }

        if (
            session.skill_name == "publish-manager"
            and session.step_key == "select_item"
        ):
            output = result.output or {}
            queue_items = (
                output.get("queue_items") or session.artifacts.get("queue_items") or []
            )
            return {
                "text": _format_publish_queue(
                    queue_items,
                    intro=output.get("message")
                    or "Publish Queue\n\nChoose a recent content item to inspect.",
                ),
                "reply_markup": _publish_queue_keyboard(queue_items),
                "parse_mode": None,
            }

        if (
            session.skill_name == "publish-manager"
            and session.step_key == "publish_or_schedule"
        ):
            output = result.output or {}
            item = (
                output.get("content_item")
                or session.artifacts.get("selected_item")
                or {}
            )
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
            image_url = (
                output.get("preview_image_url")
                or output.get("final_image_url")
                or session.artifacts.get("preview_image_url")
                or session.artifacts.get("final_image_url")
            )
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
                    "reply_markup": _inline_keyboard_from_options(
                        PREVIEW_ACTIONS, prefix="action::"
                    ),
                    "parse_mode": "Markdown",
                }
            if session.skill_name == "persona-creator":
                persona = (
                    output.get("persona") or session.artifacts.get("persona_data") or {}
                )
                readiness = (
                    output.get("readiness") or session.artifacts.get("readiness") or {}
                )
                persona_id = persona.get("persona_id") or session.artifacts.get(
                    "persona_id", "—"
                )
                language = persona.get("language", "—")
                tts_voice = GoogleTTSService.describe_voice(
                    persona.get("tts_voice"),
                    language=persona.get("language"),
                )
                status = persona.get("status", "—")
                ready_emoji = "✅" if readiness.get("ready") else "⚠️"
                blocking = readiness.get("blocking_reason") or "All checks passed"
                avatar_persisted = bool(persona.get("avatar_media_asset_id"))
                persistence_label = (
                    "saved to project media"
                    if avatar_persisted
                    else "temporary preview only"
                )
                text = (
                    "👤 Persona Preview Ready\n\n"
                    f"• ID: {persona_id}\n"
                    f"• Language: {language}\n"
                    f"• TTS Voice: {tts_voice}\n"
                    f"• Status: {status}\n"
                    f"• Avatar: {persistence_label}\n"
                    f"• Ready to use: {ready_emoji} {blocking}\n\n"
                    "This preview is not saved yet and is not production-ready until you save it. "
                    "Tap Save Persona to keep it and make the persona ready for later workflows."
                )
                photo_caption = (
                    f"👤 {persona_id} | {language} | {tts_voice}\n"
                    f"{'Saved' if avatar_persisted else 'Unsaved preview'} | {ready_emoji} {blocking}"
                )
                image_url = (
                    output.get("preview_image_url")
                    or session.artifacts.get("preview_image_url")
                    or session.artifacts.get("avatar_image_url")
                )
                persona_actions = [
                    {"label": "✅ Save Persona", "value": "save"},
                    {"label": "🔄 Regenerate", "value": "regenerate"},
                ]
                payload: Dict[str, Any] = {
                    "text": text,
                    "reply_markup": _inline_keyboard_from_options(
                        persona_actions, prefix="action::"
                    ),
                    "parse_mode": None,
                }
                if image_url:
                    payload["photo_url"] = image_url
                    payload["photo_caption"] = photo_caption
                return payload

            if session.skill_name in ("image-scene", "image_generation"):
                if not image_url:
                    candidates = (
                        output.get("image_candidates")
                        or session.artifacts.get("image_candidates")
                        or []
                    )
                    if candidates:
                        image_url = candidates[0].get("url")
                style = session.collected.get("style", "N/A")
                scene = session.collected.get("scene_type", "N/A")
                ratio = session.collected.get("aspect_ratio", "16:9")
                prompt = output.get("prompt") or session.collected.get(
                    "topic_or_prompt", "N/A"
                )
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
            elif session.skill_name == "image-poster":
                style = session.collected.get("style", "N/A")
                tone = session.collected.get("tone", "N/A")
                ratio = session.collected.get("aspect_ratio", "4:5")
                brief = session.collected.get("topic_or_brief", "N/A")
                text = (
                    f"🖼️ *Poster Preview Ready!*\n\n"
                    f"• *Brief*: {brief}\n"
                    f"• *Style*: {style}\n"
                    f"• *Tone*: {tone}\n"
                    f"• *Aspect Ratio*: {ratio}\n\n"
                    "Review the poster below and choose an action."
                )
                photo_caption = (
                    f"🖼️ {style.title()} poster | {tone.title()} | {ratio}\n"
                    "Review the poster and choose an action."
                )
            else:
                text = "✨ Preview ready!\nReview the image below and choose an action."
                photo_caption = "Generated preview 🖼️."

            payload = {
                "text": text,
                "reply_markup": (
                    _image_scene_batch_keyboard()
                    if session.skill_name in ("image-scene", "image_generation")
                    else _inline_keyboard_from_options(
                        PREVIEW_ACTIONS, prefix="action::"
                    )
                ),
                "parse_mode": "Markdown",
            }
            if image_url:
                payload["photo_url"] = image_url
                payload["photo_caption"] = photo_caption
            else:
                payload["text"] = (
                    "✨ Preview ready!\n⚠️ Image URL is currently unavailable. Choose an action:"
                )
            return payload

        if (
            session.control.status in {SkillStatus.waiting_approval, SkillStatus.running}
            or result.next_step == "poll_status"
        ):
            output = result.output or {}
            workflow_id = output.get("workflow_id") or session.control.workflow_id

            if session.skill_name in ("video-ai", "video_generation"):
                persona = session.collected.get("persona_id", "N/A")
                topic = (
                    session.collected.get("topic")
                    or session.collected.get("idea_brief")
                    or "N/A"
                )
                tone = session.collected.get("tone", "natural")
                platform = session.collected.get("platform", "N/A")
                approved_package_started = bool(
                    output.get("approved_production_package")
                    or session.artifacts.get("approved_production_package")
                    or session.step_key == "package_ready"
                )
                production_note = (
                    output.get("production_note")
                    or session.artifacts.get("production_note")
                )
                lines = [
                    "🎬 *Video Generation Started!*",
                    "",
                    f"• *Persona*: {persona}",
                    f"• *Topic*: {topic}",
                    f"• *Tone*: {tone}",
                    f"• *Platform*: {platform}",
                    "",
                    f"Workflow ID: `{workflow_id}`",
                    (
                        "The final preview will arrive in this chat."
                        if approved_package_started
                        else "Script review and the final preview will arrive in this chat."
                    ),
                ]
                if production_note:
                    lines.extend(["", production_note])
                text = "\n".join(lines)
            else:
                text = f"🚀 Workflow started.\nWorkflow ID: `{workflow_id}`\n⏳ Waiting for approval or status updates..."

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
            if session.skill_name == "video-ai" and (
                output.get("approved_production_package")
                or session.artifacts.get("approved_production_package")
                or session.step_key == "package_ready"
            ):
                package = (
                    output.get("approved_production_package")
                    or session.artifacts.get("approved_production_package")
                    or {}
                )
                concept = (
                    package.get("concept_brief")
                    or session.artifacts.get("concept_brief")
                    or {}
                )
                beat_sheet = (
                    package.get("beat_sheet")
                    or session.artifacts.get("beat_sheet")
                    or {}
                )
                beat_count = len(beat_sheet.get("beats") or [])

                # Check if production workflow was started
                workflow_id = output.get("workflow_id")
                production_note = (
                    output.get("production_note")
                    or session.artifacts.get("production_note")
                )
                if workflow_id:
                    lines = [
                        "Production workflow started!",
                        f"Workflow ID: {workflow_id}",
                        "",
                        f"Persona: {concept.get('persona_id') or '-'}",
                        f"Feature Focus: {concept.get('feature_focus') or '-'}",
                        f"Goal: {_humanize_token(concept.get('video_goal'))}",
                        f"Beats: {beat_count}",
                    ]
                    if production_note:
                        lines.extend(["", production_note])
                    lines.extend(
                        [
                            "",
                            "Your video is being generated. This may take a few minutes...",
                        ]
                    )
                else:
                    lines = [
                        "Pre-production package ready.",
                        "Production workflow could not be started.",
                        "",
                        f"Persona: {concept.get('persona_id') or '-'}",
                        f"Feature Focus: {concept.get('feature_focus') or '-'}",
                        f"Goal: {_humanize_token(concept.get('video_goal'))}",
                        f"Beats: {beat_count}",
                    ]
                    if production_note:
                        lines.extend(["", production_note])
                    lines.extend(["", "Please try again or contact support."])
                return {
                    "text": "\n".join(lines),
                    "reply_markup": None,
                    "parse_mode": None,
                }
            if output.get("status") == "cancelled":
                return _render_cancelled_result(session, output)
            if session.skill_name == "persona-inspector":
                return _render_persona_inspector_result(session=session, output=output)
            lines = [f"✅ `{session.skill_name}` completed successfully!"]
            if isinstance(output, dict):
                if output.get("message"):
                    lines.append(output["message"])
                if output.get("workflow_id"):
                    lines.append(f"🔗 Workflow ID: `{output['workflow_id']}`")
                if output.get("manifest_url"):
                    lines.append(f"📦 Manifest: [Link]({output['manifest_url']})")
                if output.get("image_urls"):
                    lines.append(f"🖼️ Images selected: {len(output['image_urls'])}")
                    for index, url in enumerate(output["image_urls"]):
                        lines.append(f"#{index + 1}: [Link]({url})")
                elif output.get("image_url"):
                    lines.append(f"🖼️ Image: [Link]({output['image_url']})")
                if output.get("quota_summary"):
                    lines.append("📊 Quota summary ready.")
                if output.get("persona"):
                    lines.append(
                        f"👤 Persona: `{output['persona'].get('persona_id', '-')}`"
                    )
                if output.get("content_item"):
                    item = output["content_item"]
                    lines.append(
                        f"📄 Item: {item.get('title') or item.get('id') or '-'}"
                    )
                    lines.append(f"📡 Status: {_status_badge(item.get('status', ''))}")
            return {
                "text": "\n".join(lines),
                "reply_markup": None,
                "parse_mode": "Markdown",
            }

        return cls.render_skill_prompt(session)
