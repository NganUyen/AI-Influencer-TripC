"""
Sync local audio library files to object storage + media_assets.
Supports simplified paths (bgm/..., movement/...) and cleans up legacy paths.

Usage:
  .\.venv\Scripts\python.exe scripts/sync_audio_library_to_storage.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid
import json
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv()

from services.background_music_service import BackgroundMusicService
from services.database_service import DatabaseService
from services.storage_service import StorageService


SYSTEM_LIBRARY_USER_ID = "00000000-0000-0000-0000-000000000001"
SYSTEM_LIBRARY_PERSONA_ID = "audio-library"


def _resolve_local_source(track: Dict[str, Any]) -> Path:
    library_root = ROOT / "assets" / "audio_library"
    relative_path = str(track.get("relative_path") or "").strip().lstrip("/")
    if relative_path:
        candidate = library_root / relative_path
        if candidate.exists():
            return candidate

    group = str(track.get("group") or "bgm").strip().lower() or "bgm"
    filename = str(track.get("filename") or "").strip()
    if filename:
        grouped = library_root / group / filename
        if grouped.exists():
            return grouped
        fallback = library_root / filename
        if fallback.exists():
            return fallback

    raise FileNotFoundError(
        f"Cannot resolve local source file for track id={track.get('id')}"
    )


async def _sync_track(track: Dict[str, Any]) -> bool:
    track_id = str(track.get("id") or "unknown")
    group = str(track.get("group") or "bgm")
    profile = str(track.get("profile") or "")
    filename = str(track.get("filename") or "").strip()
    
    if not filename:
        relative_path = str(track.get("relative_path") or "").strip().lstrip("/")
        filename = Path(relative_path).name
        
    # Always prefer resolver-provided storage_path to keep sync script and service aligned.
    storage_path = str(track.get("storage_path") or "").strip().lstrip("/")
    if not storage_path:
        storage_path = f"{group}/{filename}"

    try:
        local_source = _resolve_local_source(track)
        payload = local_source.read_bytes()
    except Exception as exc:
        print(f"[FAIL] {track_id}: {exc}")
        return False

    storage = StorageService()

    try:
        # Upload using the new simplified path
        access_url = await storage.upload_bytes(
            data=payload,
            filename=storage_path,
            content_type="audio/mpeg",
        )
    except Exception as exc:
        print(f"[FAIL] {track_id}: storage upload failed ({exc})")
        return False

    # Upsert directly into public.media_assets
    metadata = {
        "audio_library": True,
        "track_id": track_id,
        "group": group,
        "profile": profile,
        "mood": track.get("mood"),
        "style": track.get("style"),
        "duration_seconds": track.get("duration_seconds"),
        "start_offset_seconds": track.get("start_offset_seconds"),
        "clip_duration_seconds": track.get("clip_duration_seconds"),
        "source_file": str(local_source),
        "storage_path": storage_path,
    }
    
    pool = await DatabaseService.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO public.media_assets (
                id, user_id, url, persona_id, type, filename,
                bucket_name, storage_path, storage_provider, visibility,
                asset_origin, status, size, mime_type, metadata
            )
            VALUES (
                $1::uuid, $2::uuid, $3, $4, $5, $6,
                $7, $8, $9, $10,
                $11, $12, $13, $14, $15::jsonb
            )
            ON CONFLICT (storage_provider, bucket_name, storage_path) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                url = EXCLUDED.url,
                persona_id = EXCLUDED.persona_id,
                type = EXCLUDED.type,
                filename = EXCLUDED.filename,
                visibility = EXCLUDED.visibility,
                asset_origin = EXCLUDED.asset_origin,
                status = EXCLUDED.status,
                size = EXCLUDED.size,
                mime_type = EXCLUDED.mime_type,
                metadata = EXCLUDED.metadata
            RETURNING id
            """,
            str(uuid.uuid4()),
            SYSTEM_LIBRARY_USER_ID,
            access_url,
            SYSTEM_LIBRARY_PERSONA_ID,
            "audio",
            filename,
            storage.bucket_name,
            storage_path,
            storage.provider,
            "public",
            "imported",
            "available",
            len(payload),
            "audio/mpeg",
            json.dumps(metadata)
        )
    
    if not row:
        print(f"[FAIL] {track_id}: DB record failed")
        return False

    print(f"[OK] {track_id} | path={storage_path}")
    return True


async def cleanup_old_assets():
    print("Cleaning up old assets...")
    pool = await DatabaseService.get_pool()
    storage = StorageService()
    
    async with pool.acquire() as conn:
        # Find old rows (legacy users/... structure)
        rows = await conn.fetch(
            """
            SELECT id, storage_path 
            FROM public.media_assets
            WHERE user_id = $1::uuid
              AND persona_id = $2
              AND storage_path LIKE 'users/%'
            """,
            SYSTEM_LIBRARY_USER_ID,
            SYSTEM_LIBRARY_PERSONA_ID
        )
        
        if not rows:
            print("No old assets found to clean up.")
            return

        print(f"Found {len(rows)} old assets. Deleting...")
        
        for row in rows:
            asset_id = row["id"]
            old_path = row["storage_path"]
            
            # 1. Delete from object storage
            try:
                await storage.delete(old_path)
                print(f"  [DEL] Storage: {old_path}")
            except Exception as exc:
                print(f"  [ERR] Failed to delete {old_path} from storage: {exc}")
                
            # 2. Delete from database
            await conn.execute("DELETE FROM public.media_assets WHERE id = $1", asset_id)
            print(f"  [DEL] DB Record: {asset_id}")

    print("Cleanup completed.")


async def main() -> None:
    print("=" * 72)
    print(" Sync Audio Library To Storage (Simplified Path)")
    print("=" * 72)

    tracks: List[Dict[str, Any]] = []
    # Always read from local definitions
    tracks.extend(BackgroundMusicService.list_tracks(group="bgm"))
    tracks.extend(BackgroundMusicService.list_tracks(group="movement"))
    print(f"Discovered tracks: {len(tracks)}")

    success = 0
    for track in tracks:
        if await _sync_track(track):
            success += 1

    print("-" * 72)
    print(f"Completed: {success}/{len(tracks)} tracks synced")
    
    # Run cleanup if at least some new ones were synced successfully
    if success > 0:
        await cleanup_old_assets()
        
    print("=" * 72)
    await DatabaseService.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
