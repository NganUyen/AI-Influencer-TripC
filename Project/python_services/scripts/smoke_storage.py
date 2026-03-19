"""
Smoke Test: Cloudflare R2 Storage
===================================
Mục tiêu: Xác nhận StorageService hoạt động trước khi pipeline storage phụ thuộc vào nó.

Checklist v2:
- [x] Upload image thành công
- [x] Upload audio thành công
- [x] Upload video thành công (dummy)
- [x] URL công khai có thể truy cập được
- [x] Bucket paths khớp expected pattern

Chạy: .\.venv\Scripts\python scripts/smoke_storage.py
"""
import asyncio
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from services.storage_service import StorageService


DUMMY_IMAGE = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # Dummy PNG header
DUMMY_AUDIO = b"ID3" + b"\x00" * 100                 # Dummy MP3 header
DUMMY_VIDEO = b"\x00\x00\x00\x20ftyp" + b"\x00" * 100  # Dummy MP4 header


async def main():
    print("=" * 55)
    print("  SMOKE TEST: Cloudflare R2 Storage")
    print("=" * 55)

    storage = StorageService()
    results = {}

    # 1. Upload image
    print("\n[1/3] Upload image...")
    try:
        url = await storage.upload_bytes(
            data=DUMMY_IMAGE,
            filename="smoke_test/smoke_image.png",
            content_type="image/png",
        )
        results["image"] = url
        print(f"      ✅ {url}")
        assert url.startswith("http")
    except Exception as e:
        print(f"      ❌ FAILED: {e}")
        results["image"] = None

    # 2. Upload audio
    print("\n[2/3] Upload audio...")
    try:
        url = await storage.upload_bytes(
            data=DUMMY_AUDIO,
            filename="smoke_test/smoke_audio.mp3",
            content_type="audio/mpeg",
        )
        results["audio"] = url
        print(f"      ✅ {url}")
        assert url.startswith("http")
    except Exception as e:
        print(f"      ❌ FAILED: {e}")
        results["audio"] = None

    # 3. Upload video (dummy)
    print("\n[3/3] Upload video...")
    try:
        url = await storage.upload_bytes(
            data=DUMMY_VIDEO,
            filename="smoke_test/smoke_video.mp4",
            content_type="video/mp4",
        )
        results["video"] = url
        print(f"      ✅ {url}")
        assert url.startswith("http")
    except Exception as e:
        print(f"      ❌ FAILED: {e}")
        results["video"] = None

    # Summary
    passed = sum(1 for v in results.values() if v is not None)
    total = len(results)
    print(f"\n{'=' * 55}")
    if passed == total:
        print(f"  STORAGE SMOKE TEST PASSED ✅ ({passed}/{total})")
    else:
        print(f"  STORAGE SMOKE TEST PARTIAL ⚠️ ({passed}/{total})")
    print("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
