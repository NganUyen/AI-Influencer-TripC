"""Local background music selection for fallback audio."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class BackgroundMusicError(RuntimeError):
    pass


class BackgroundMusicService:
    _library_root = Path(__file__).resolve().parent.parent / "assets" / "audio_library"
    _legacy_manifest_path = _library_root / "library.json"

    @classmethod
    def _manifest_path_for_group(cls, group: str) -> Path:
        normalized_group = str(group or "bgm").strip().lower() or "bgm"
        grouped_manifest = cls._library_root / normalized_group / "library.json"
        if grouped_manifest.exists():
            return grouped_manifest
        if normalized_group == "bgm":
            return cls._legacy_manifest_path
        return grouped_manifest

    @classmethod
    def _load_manifest(cls, *, group: str = "bgm") -> List[Dict[str, Any]]:
        manifest_path = cls._manifest_path_for_group(group)
        if not manifest_path.exists():
            raise BackgroundMusicError(
                f"Background music manifest is missing: {manifest_path}"
            )
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise BackgroundMusicError("Background music manifest must be a list")
        return [item for item in data if isinstance(item, dict)]

    @classmethod
    def _resolve_track_path(cls, *, group: str, entry: Dict[str, Any]) -> Path:
        normalized_group = str(group or "bgm").strip().lower() or "bgm"
        relative_path = str(entry.get("relative_path") or "").strip()
        if relative_path:
            candidate = cls._library_root / relative_path
            if candidate.exists():
                return candidate

        filename = str(entry.get("filename") or "").strip()
        if not filename:
            raise BackgroundMusicError(
                f"Track manifest entry is missing filename: {entry}"
            )

        grouped_candidate = cls._library_root / normalized_group / filename
        if grouped_candidate.exists():
            return grouped_candidate

        root_candidate = cls._library_root / filename
        if root_candidate.exists():
            return root_candidate

        return grouped_candidate

    @classmethod
    def list_tracks(cls, *, group: str = "bgm") -> List[Dict[str, Any]]:
        entries = cls._load_manifest(group=group)
        payload: List[Dict[str, Any]] = []
        for item in entries:
            try:
                track_path = cls._resolve_track_path(group=group, entry=item)
            except BackgroundMusicError:
                continue
            payload.append(
                {
                    **item,
                    "group": str(item.get("group") or group),
                    "path": str(track_path),
                }
            )
        return payload

    @classmethod
    def select_track(
        cls,
        *,
        profile: str = "product_explainer",
        group: str = "bgm",
        max_duration_seconds: int = 60,
    ) -> Dict[str, Any]:
        entries = cls._load_manifest(group=group)
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
        track_path = cls._resolve_track_path(group=group, entry=selected)
        if not track_path.exists():
            raise BackgroundMusicError(f"Configured track is missing: {track_path}")

        return {
            **selected,
            "group": str(selected.get("group") or group),
            "path": str(track_path),
        }
