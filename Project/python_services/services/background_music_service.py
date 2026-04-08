"""Local background music selection for fallback audio."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class BackgroundMusicError(RuntimeError):
    pass


class BackgroundMusicService:
    _library_dir = Path(__file__).resolve().parent.parent / "assets" / "audio_library"
    _manifest_path = _library_dir / "library.json"

    @classmethod
    def _load_manifest(cls) -> List[Dict[str, Any]]:
        if not cls._manifest_path.exists():
            raise BackgroundMusicError(
                f"Background music manifest is missing: {cls._manifest_path}"
            )
        data = json.loads(cls._manifest_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise BackgroundMusicError("Background music manifest must be a list")
        return [item for item in data if isinstance(item, dict)]

    @classmethod
    def select_track(
        cls,
        *,
        profile: str = "product_explainer",
        max_duration_seconds: int = 60,
    ) -> Dict[str, Any]:
        entries = cls._load_manifest()
        normalized_profile = str(profile or "product_explainer").strip() or "product_explainer"
        candidates = [
            item
            for item in entries
            if str(item.get("profile") or "").strip() == normalized_profile
            and int(item.get("duration_seconds") or 0) <= max_duration_seconds
        ]
        if not candidates:
            candidates = [
                item
                for item in entries
                if int(item.get("duration_seconds") or 0) <= max_duration_seconds
            ]
        if not candidates:
            raise BackgroundMusicError(
                f"No local background music tracks fit max_duration_seconds={max_duration_seconds}"
            )

        selected = sorted(
            candidates,
            key=lambda item: (
                0 if str(item.get("profile") or "") == normalized_profile else 1,
                int(item.get("duration_seconds") or 999),
            ),
        )[0]
        track_path = cls._library_dir / str(selected.get("filename") or "")
        if not track_path.exists():
            raise BackgroundMusicError(f"Configured track is missing: {track_path}")

        return {
            **selected,
            "path": str(track_path),
        }
