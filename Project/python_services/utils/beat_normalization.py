"""Helpers to normalize pre-production beats before ScriptContract assembly."""

from typing import Any, Dict, Iterable, List, Optional

from services.contracts import (
    URL_REQUIRED_SOURCE_TYPES,
    URL_OPTIONAL_WITH_FALLBACK_TYPES,
    VALID_TOP_HALF_SOURCE_TYPES,
)

# Ordered by preference when resolving beat-level source refs.
_SOURCE_REF_KEYS = (
    "source_ref",
    "reference_url",
    "url",
    "page_url",
    "target_url",
    "source_url",
    "link",
)


def _normalize_source_ref(value: Any) -> Optional[str]:
    """Convert incoming values into a cleaned URL-like string or None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _resolve_source_ref(beat: Dict[str, Any], default_source_ref: Optional[str]) -> Optional[str]:
    """Resolve source_ref from beat keys first, then concept-level default."""
    for key in _SOURCE_REF_KEYS:
        resolved = _normalize_source_ref(beat.get(key))
        if resolved:
            return resolved
    return _normalize_source_ref(default_source_ref)


def normalize_beats(beats: Iterable[Dict[str, Any]], default_source_ref: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Normalize beat objects for downstream script assembly.

    - Unknown top_half_source_type values are normalized to ai_visual_fallback.
    - source_ref is backfilled from alternate URL key names and concept default.
    - URL-required source types (public_page_capture, authenticated_capture_later) 
      must end up with a source_ref or raise an error.
    - hybrid_candidate: URL is optional; will use AI fallback if missing or capture fails.
    """
    normalized: List[Dict[str, Any]] = []

    for index, beat in enumerate(beats, start=1):
        if not isinstance(beat, dict):
            raise ValueError(f"Beat {index} must be an object")

        normalized_beat = dict(beat)

        raw_type = str(normalized_beat.get("top_half_source_type") or "").strip()
        top_half_source_type = (
            raw_type if raw_type in VALID_TOP_HALF_SOURCE_TYPES else "ai_visual_fallback"
        )
        normalized_beat["top_half_source_type"] = top_half_source_type

        source_ref = _resolve_source_ref(normalized_beat, default_source_ref)
        normalized_beat["source_ref"] = source_ref

        # Only strict URL-required types raise an error if source_ref is missing
        # hybrid_candidate is URL-optional (falls back to AI if missing)
        if top_half_source_type in URL_REQUIRED_SOURCE_TYPES and not source_ref:
            raise ValueError(
                f"Beat {index} type '{top_half_source_type}' requires source_ref or concept_brief.reference_url"
            )

        normalized.append(normalized_beat)

    return normalized
