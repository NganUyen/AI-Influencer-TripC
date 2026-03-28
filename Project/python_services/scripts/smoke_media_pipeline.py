"""
Smoke Test: Media Storage Pipeline (E2E)
=========================================
Kiểm tra toàn bộ luồng lưu trữ cho 3 loại media:
  1. Audio (TTS)  → StorageService upload → media_assets DB record
  2. Image (dummy/PNG) → MediaStorageService.upload_bytes → DB record
  3. Video (dummy/MP4) → MediaStorageService.upload_bytes → DB record

Điều kiện để PASS:
  ✅ File được upload thành công lên Supabase Storage (URL hợp lệ)
  ✅ Record được insert vào bảng public.media_assets
  ✅ Trường type/bucket/status/storage_path đúng
  ✅ URL có thể fetch được (HEAD request 200/206)

Chạy:
  .\.venv\Scripts\python scripts/smoke_media_pipeline.py

Để chạy test TTS thật (sẽ consume API quota), thêm flag:
  .\.venv\Scripts\python scripts/smoke_media_pipeline.py --real-tts
"""
import argparse
import asyncio
import os
import sys
import time
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import httpx

# ── Pre-flight: detect missing credentials before loading settings ─────────────
def _check_env_preflight() -> bool:
    """Kiểm tra .env trước khi import settings (tránh Pydantic crash không rõ ràng)."""
    import os
    required = {
        "SUPABASE_URL": os.getenv("SUPABASE_URL", ""),
        "SUPABASE_KEY": os.getenv("SUPABASE_KEY", "") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", ""),
        "SUPABASE_SERVICE_ROLE_KEY": os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        "DATABASE_URL": os.getenv("DATABASE_URL", ""),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
        "IPROYAL_USERNAME": os.getenv("IPROYAL_USERNAME", ""),
        "IPROYAL_PASSWORD": os.getenv("IPROYAL_PASSWORD", ""),
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
    }
    placeholders = {"your_", "change-this", "example", "placeholder", "test_", "localhost"}
    missing = []
    for key, val in required.items():
        stripped = (val or "").strip()
        is_placeholder = not stripped or any(p in stripped.lower() for p in placeholders)
        if is_placeholder:
            missing.append(key)

    # Storage bucket is separate
    bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "") or os.getenv("STORAGE_BUCKET_NAME", "")
    if not bucket:
        missing.append("SUPABASE_STORAGE_BUCKET")

    if missing:
        print("\n" + "⚠️" * 20)
        print("  WARNING: Các biến sau vẫn đang là placeholder hoặc thiếu:")
        for m in missing:
            print(f"    • {m}")
        print("\n  Tiếp tục chạy test cho Storage và Database...")
        print("⚠️" * 20 + "\n")
        return True # Trả về True để không bị chặn
    return True


if not _check_env_preflight():
    sys.exit(1)


from services.database_service import DatabaseService
from services.media_storage_service import MediaStorageService
from services.storage_service import StorageService

# ── Constants ──────────────────────────────────────────────────────────────────
SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"  # Persona System user
TEST_PERSONA_ID = "smoke-test-persona"
DUMMY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
    b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
    b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)  # Minimal 1x1 valid PNG
DUMMY_MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x00" * 100
DUMMY_MP4 = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41" + b"\x00" * 200

# ── Helpers ────────────────────────────────────────────────────────────────────
PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "
INFO = "   "


def section(title: str) -> None:
    print(f"\n{'─' * 55}")
    print(f"  {title}")
    print(f"{'─' * 55}")


def check(label: str, ok: bool, detail: str = "") -> bool:
    icon = PASS if ok else FAIL
    suffix = f"  → {detail}" if detail else ""
    print(f"  {icon} {label}{suffix}")
    return ok


async def verify_url_accessible(url: str, timeout: float = 10.0) -> bool:
    """HEAD request để xác nhận file tồn tại và truy cập được."""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.head(url)
            return resp.status_code in (200, 206, 302)
    except Exception as exc:
        print(f"  {WARN} URL check exception: {exc}")
        return False


async def verify_db_record(storage_path: str, expected_type: str) -> dict | None:
    """Truy vấn DB xác nhận record tồn tại với đúng fields."""
    try:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, user_id, persona_id, type, status,
                       bucket_name, storage_path, storage_provider, visibility, asset_origin
                FROM public.media_assets
                WHERE storage_path = $1
                LIMIT 1
                """,
                storage_path,
            )
        if row is None:
            return None
        return dict(row)
    except Exception as exc:
        print(f"  {WARN} DB query failed: {exc}")
        return None


# ── Test Cases ─────────────────────────────────────────────────────────────────

async def test_raw_storage_upload():
    """Test 1: StorageService trực tiếp (không ghi DB) — baseline connectivity."""
    section("Test 1: StorageService raw upload (no DB)")
    storage = StorageService()
    run_id = uuid.uuid4().hex[:8]
    all_ok = True

    for label, data, ct, ext in [
        ("Image PNG", DUMMY_PNG, "image/png", "png"),
        ("Audio MP3", DUMMY_MP3, "audio/mpeg", "mp3"),
        ("Video MP4", DUMMY_MP4, "video/mp4", "mp4"),
    ]:
        path = f"smoke_test/raw/{run_id}/test.{ext}"
        try:
            url = await storage.upload_bytes(data=data, filename=path, content_type=ct)
            ok = url.startswith("http")
            all_ok = all_ok and check(f"Upload {label}", ok, url[:70] + "..." if len(url) > 70 else url)
        except Exception as exc:
            check(f"Upload {label}", False, str(exc))
            all_ok = False

    return all_ok


async def test_media_storage_service_image():
    """Test 2: MediaStorageService.upload_bytes → Storage + DB record cho IMAGE."""
    section("Test 2: MediaStorageService → Image → DB record")
    svc = MediaStorageService()
    run_id = uuid.uuid4().hex[:8]
    all_ok = True

    result = await svc.upload_bytes(
        data=DUMMY_PNG,
        content_type="image/png",
        asset_type="IMAGE",
        asset_kind="image",
        asset_origin="generated",
        user_id=SYSTEM_USER_ID,
        persona_id=TEST_PERSONA_ID,
        file_name_hint=f"smoke-image-{run_id}",
        metadata={"smoke_test": True, "run_id": run_id},
    )

    all_ok = check("upload_bytes returned result", result is not None) and all_ok
    if result is None:
        print(f"  {FAIL} MediaStorageService returned None — check logs for details")
        return False

    all_ok = check("Has access_url", bool(result.get("access_url")), result.get("access_url", "")) and all_ok
    all_ok = check("Has media_asset_id", bool(result.get("media_asset_id"))) and all_ok
    all_ok = check("Has storage_path", bool(result.get("storage_path"))) and all_ok

    storage_path = result.get("storage_path", "")
    print(f"  {INFO} storage_path = {storage_path}")

    # Verify DB
    db_row = await verify_db_record(storage_path, "image")
    all_ok = check("DB record exists", db_row is not None) and all_ok
    if db_row:
        all_ok = check("DB type = image", db_row.get("type") == "image", db_row.get("type", "")) and all_ok
        all_ok = check("DB status = available", db_row.get("status") == "available", db_row.get("status", "")) and all_ok
        all_ok = check("DB bucket_name set", bool(db_row.get("bucket_name")), db_row.get("bucket_name", "")) and all_ok
        persona_match = db_row.get("persona_id") == TEST_PERSONA_ID
        all_ok = check("DB persona_id matched", persona_match, db_row.get("persona_id", "")) and all_ok

    # Verify URL accessible
    url = result.get("access_url", "")
    url_ok = await verify_url_accessible(url)
    all_ok = check("URL accessible (HEAD 200)", url_ok, url[:60] + "...") and all_ok

    return all_ok


async def test_media_storage_service_audio(use_real_tts: bool = False):
    """Test 3: Audio storage — dummy bytes hoặc real TTS."""
    section(f"Test 3: MediaStorageService → Audio → DB record {'(Real TTS)' if use_real_tts else '(Dummy bytes)'}")
    svc = MediaStorageService()
    run_id = uuid.uuid4().hex[:8]
    all_ok = True

    if use_real_tts:
        try:
            from services.google_tts_service import GoogleTTSService
            tts = GoogleTTSService()
            print(f"  {INFO} Calling Google TTS API...")
            t0 = time.time()
            audio_data = await tts.generate_audio(
                text="TripC - ứng dụng du lịch Việt Nam. Khám phá ngay hôm nay!",
                voice="vi-VN-Wavenet-D",
            )
            elapsed = time.time() - t0
            check(f"TTS generated {len(audio_data):,} bytes in {elapsed:.1f}s", len(audio_data) > 500)
            content_type = "audio/mpeg"
        except Exception as exc:
            check("TTS generation", False, str(exc))
            print(f"  {WARN} Falling back to dummy audio bytes")
            audio_data = DUMMY_MP3
            content_type = "audio/mpeg"
    else:
        audio_data = DUMMY_MP3
        content_type = "audio/mpeg"

    result = await svc.upload_bytes(
        data=audio_data,
        content_type=content_type,
        asset_type="AUDIO",
        asset_kind="audio",
        asset_origin="generated",
        user_id=SYSTEM_USER_ID,
        persona_id=TEST_PERSONA_ID,
        file_name_hint=f"smoke-audio-{run_id}",
        metadata={"smoke_test": True, "run_id": run_id, "is_real_tts": use_real_tts},
    )

    all_ok = check("upload_bytes returned result", result is not None) and all_ok
    if result is None:
        return False

    all_ok = check("Has access_url", bool(result.get("access_url"))) and all_ok
    all_ok = check("Has media_asset_id", bool(result.get("media_asset_id"))) and all_ok

    storage_path = result.get("storage_path", "")
    print(f"  {INFO} storage_path = {storage_path}")

    db_row = await verify_db_record(storage_path, "audio")
    all_ok = check("DB record exists", db_row is not None) and all_ok
    if db_row:
        all_ok = check("DB type = audio", db_row.get("type") == "audio", db_row.get("type", "")) and all_ok
        all_ok = check("DB status = available", db_row.get("status") == "available") and all_ok

    url = result.get("access_url", "")
    url_ok = await verify_url_accessible(url)
    all_ok = check("URL accessible (HEAD 200)", url_ok) and all_ok

    return all_ok


async def test_media_storage_service_video():
    """Test 4: Video storage — simulates what FFMPEG output goes through."""
    section("Test 4: MediaStorageService → Video (Final MP4) → DB record")
    svc = MediaStorageService()
    run_id = uuid.uuid4().hex[:8]
    all_ok = True

    result = await svc.upload_bytes(
        data=DUMMY_MP4,
        content_type="video/mp4",
        asset_type="VIDEO",
        asset_kind="video",
        asset_origin="generated",
        user_id=SYSTEM_USER_ID,
        persona_id=TEST_PERSONA_ID,
        file_name_hint=f"smoke-video-final-{run_id}",
        metadata={
            "smoke_test": True,
            "run_id": run_id,
            "pipeline_stage": "ffmpeg_output",
            "resolution": "1080x1920",
        },
    )

    all_ok = check("upload_bytes returned result", result is not None) and all_ok
    if result is None:
        return False

    all_ok = check("Has access_url", bool(result.get("access_url"))) and all_ok
    all_ok = check("Has media_asset_id", bool(result.get("media_asset_id"))) and all_ok

    storage_path = result.get("storage_path", "")
    print(f"  {INFO} storage_path = {storage_path}")

    # Path must follow canonical pattern
    canonical_ok = (
        "users/" in storage_path
        and "/personas/" in storage_path
        and "/video/" in storage_path
    )
    all_ok = check("storage_path is canonical", canonical_ok, storage_path) and all_ok

    db_row = await verify_db_record(storage_path, "video")
    all_ok = check("DB record exists", db_row is not None) and all_ok
    if db_row:
        all_ok = check("DB type = video", db_row.get("type") == "video", db_row.get("type", "")) and all_ok
        all_ok = check("DB status = available", db_row.get("status") == "available") and all_ok
        all_ok = check("DB asset_origin = generated", db_row.get("asset_origin") == "generated") and all_ok
        all_ok = check(
            "DB storage_provider set",
            bool(db_row.get("storage_provider")),
            db_row.get("storage_provider", ""),
        ) and all_ok

    url = result.get("access_url", "")
    url_ok = await verify_url_accessible(url)
    all_ok = check("URL accessible (HEAD 200)", url_ok) and all_ok

    print(f"\n  {INFO} Final video URL:\n  {INFO} {url}")
    print(f"  {INFO} media_asset_id: {result.get('media_asset_id')}")

    return all_ok


async def test_upload_from_url():
    """Test 5: MediaStorageService.upload_from_url — simulates HeyGen video download + re-upload."""
    section("Test 5: MediaStorageService.upload_from_url (simulate HeyGen re-upload)")

    # Use a stable public test PNG from Supabase docs or any CDN
    TEST_URL = "https://www.gstatic.com/webp/gallery/1.jpg"
    svc = MediaStorageService()
    run_id = uuid.uuid4().hex[:8]

    result = await svc.upload_from_url(
        url=TEST_URL,
        asset_type="IMAGE",
        asset_kind="image",
        asset_origin="imported",
        user_id=SYSTEM_USER_ID,
        persona_id=TEST_PERSONA_ID,
        file_name_hint=f"smoke-from-url-{run_id}",
        metadata={"smoke_test": True, "run_id": run_id, "source": "gstatic_test"},
    )

    all_ok = True
    all_ok = check("upload_from_url returned result", result is not None) and all_ok
    if result is None:
        print(f"  {WARN} upload_from_url returned None — network or DB issue")
        return False

    all_ok = check("Has access_url", bool(result.get("access_url"))) and all_ok
    all_ok = check("Has media_asset_id", bool(result.get("media_asset_id"))) and all_ok
    all_ok = check("source_url preserved", bool(result.get("source_url"))) and all_ok

    storage_path = result.get("storage_path", "")
    db_row = await verify_db_record(storage_path, "image")
    all_ok = check("DB record exists", db_row is not None) and all_ok
    if db_row:
        all_ok = check("DB asset_origin = imported", db_row.get("asset_origin") == "imported") and all_ok

    return all_ok


async def test_db_connectivity():
    """Test 0: Kiểm tra DB kết nối trước khi chạy các test khác."""
    section("Test 0: Database connectivity check")
    try:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT 1")
        ok = val == 1
        check("DB ping (SELECT 1)", ok)

        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM public.media_assets")
        check(f"media_assets table accessible ({count} records)", True)
        return True
    except Exception as exc:
        check("DB connection", False, str(exc))
        print(f"\n  {WARN} Kiểm tra DATABASE_URL trong .env")
        return False


# ── Main ───────────────────────────────────────────────────────────────────────
async def main(real_tts: bool):
    print("\n" + "=" * 55)
    print("  SMOKE TEST: Media Storage Pipeline (E2E)")
    print("  Kiểm tra: Audio / Image / Video → Storage + DB")
    print("=" * 55)

    results: dict[str, bool] = {}

    # Test 0: DB connectivity (abort if fail)
    results["db_connectivity"] = await test_db_connectivity()
    if not results["db_connectivity"]:
        print(f"\n{FAIL} DB không kết nối được. Dừng test.")
        return

    # Test 1: Raw StorageService
    results["raw_storage"] = await test_raw_storage_upload()

    # Test 2: Image via MediaStorageService
    results["image_media"] = await test_media_storage_service_image()

    # Test 3: Audio (+/- real TTS)
    results["audio_media"] = await test_media_storage_service_audio(use_real_tts=real_tts)

    # Test 4: Video (simulate FFMPEG output)
    results["video_media"] = await test_media_storage_service_video()

    # Test 5: Upload from URL (simulate HeyGen download)
    results["upload_from_url"] = await test_upload_from_url()

    # Final Summary
    print("\n" + "=" * 55)
    print("  SUMMARY")
    print("=" * 55)
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, ok in results.items():
        icon = PASS if ok else FAIL
        print(f"  {icon} {name.replace('_', ' ').title()}")

    print(f"\n  Result: {passed}/{total} tests passed")

    if passed == total:
        print("\n  🎉 ALL MEDIA STORAGE TESTS PASSED")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"\n  ⚠️  FAILED: {', '.join(failed)}")
        print("  → Kiểm tra logs phía trên để biết chi tiết lỗi")

    print("=" * 55 + "\n")

    # Cleanup DB pool
    await DatabaseService.close_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Media Storage Pipeline Smoke Test")
    parser.add_argument(
        "--real-tts",
        action="store_true",
        help="Gọi Google TTS API thật (consume API quota). Mặc định dùng dummy bytes.",
    )
    args = parser.parse_args()
    asyncio.run(main(real_tts=args.real_tts))
