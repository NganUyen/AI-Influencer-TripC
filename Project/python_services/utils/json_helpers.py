"""JSON parsing helpers for robustly extracting structured data from LLM responses."""

import json
from typing import Any

def extract_json_from_llm_response(value: str) -> Any:
    """Extracts JSON from an LLM response, stripping markdown fences if present.
    If parsing fails but structures exist, tries to extract valid dict/list.
    Returns parsed JSON object (dict/list) or dict wrapping raw text on failure."""
    if not isinstance(value, str):
        return {}

    text = value.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            if lines[0].startswith("```"):
                lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    if not text:
        return {}

    candidates = [text]
    if "{" in text and "}" in text:
        candidates.append(text[text.find("{") : text.rfind("}") + 1])
    if "[" in text and "]" in text:
        candidates.append(text[text.find("[") : text.rfind("]") + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    return {"text": text}
