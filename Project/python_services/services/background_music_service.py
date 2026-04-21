"""Background music and movement library resolver backed by object storage."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from services.storage_service import StorageService


logger = logging.getLogger(__name__)

class BackgroundMusicError(RuntimeError):
    pass


class BackgroundMusicService:
    _library_root = Path(__file__).resolve().parent.parent / "assets" / "audio_library"
    _legacy_manifest_path = _library_root / "library.json"

    @staticmethod
    def _normalize_group(group: str) -> str:
        return str(group or "bgm").strip().lower() or "bgm"

    @classmethod
    def _manifest_path_for_group(cls, group: str) -> Path:
        normalized_group = cls._normalize_group(group)
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

    @staticmethod
    def _normalize_storage_path(value: str) -> str:
        return "/".join(part for part in str(value or "").strip().split("/") if part)

    @classmethod
    def _default_storage_path(cls, *, group: str, filename: str) -> str:
        normalized_group = cls._normalize_group(group)
        clean_filename = Path(cls._normalize_storage_path(filename)).name
        # Keep library assets in dedicated root folders for simpler browsing:
        #   bgm/<file>, movement/<file>
        return f"{normalized_group}/{clean_filename}"

    @classmethod
    def _resolve_storage_path(cls, *, group: str, entry: Dict[str, Any]) -> str:
        explicit_path = cls._normalize_storage_path(entry.get("storage_path") or "")
        if explicit_path:
            return explicit_path

        filename = str(entry.get("filename") or "").strip()
        if not filename:
            relative_path = cls._normalize_storage_path(entry.get("relative_path") or "")
            filename = Path(relative_path).name
        if not filename:
            raise BackgroundMusicError(
                f"Track manifest entry is missing filename: {entry}"
            )
        return cls._default_storage_path(group=group, filename=filename)

    @classmethod
    def _build_access_url(cls, storage_path: str) -> str:
        try:
            return StorageService().get_public_url(storage_path)
        except Exception as exc:
            raise BackgroundMusicError(
                f"Cannot resolve public URL for track storage path '{storage_path}': {exc}"
            ) from exc

    @classmethod
    def _resolve_preview_path(
        cls,
        *,
        entry: Dict[str, Any],
        access_url: str,
    ) -> str:
        preview = str(entry.get("preview_path") or "").strip()
        if preview.startswith(("http://", "https://")):
            return preview

        if preview and not preview.startswith("/"):
            normalized = cls._normalize_storage_path(preview)
            if normalized:
                return cls._build_access_url(normalized)

        return access_url

    @staticmethod
    def _duration_seconds(item: Dict[str, Any]) -> int:
        try:
            return int(item.get("duration_seconds") or 0)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def list_tracks(cls, *, group: str = "bgm") -> List[Dict[str, Any]]:
        normalized_group = cls._normalize_group(group)
        entries = cls._load_manifest(group=group)
        payload: List[Dict[str, Any]] = []
        for item in entries:
            try:
                storage_path = cls._resolve_storage_path(
                    group=normalized_group,
                    entry=item,
                )
                access_url = str(item.get("access_url") or "").strip()
                if not access_url:
                    access_url = cls._build_access_url(storage_path)
                preview_path = cls._resolve_preview_path(
                    entry=item,
                    access_url=access_url,
                )
            except BackgroundMusicError as exc:
                logger.warning("Skipping invalid audio library entry: %s", exc)
                continue
            payload.append(
                {
                    **item,
                    "group": str(item.get("group") or normalized_group),
                    "storage_path": storage_path,
                    "access_url": access_url,
                    "preview_path": preview_path,
                    # Keep backward compatibility for callers that still read `path`.
                    "path": access_url,
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
        entries = cls.list_tracks(group=group)
        normalized_profile = str(profile or "product_explainer").strip() or "product_explainer"
        candidates = [
            item
            for item in entries
            if str(item.get("profile") or "").strip() == normalized_profile
            and cls._duration_seconds(item) <= max_duration_seconds
        ]
        if not candidates:
            candidates = [
                item
                for item in entries
                if cls._duration_seconds(item) <= max_duration_seconds
            ]
        if not candidates:
            raise BackgroundMusicError(
                f"No background music tracks fit max_duration_seconds={max_duration_seconds}"
            )

        selected = sorted(
            candidates,
            key=lambda item: (
                0 if str(item.get("profile") or "") == normalized_profile else 1,
                cls._duration_seconds(item) or 999,
            ),
        )[0]
        return selected
