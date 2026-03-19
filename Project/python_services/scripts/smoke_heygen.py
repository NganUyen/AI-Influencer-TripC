"""
Smoke Test: HeyGen
====================
Chạy: .\.venv\Scripts\python scripts/smoke_heygen.py
Cần: HEYGEN_TEST_AUDIO_URL set trong .env (lấy từ output smoke_tts.py)
"""
import asyncio
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from services.heygen_service import HeyGenService
from services.contracts import TalkingHeadContract


TEST_AVATAR_ID = os.getenv("HEYGEN_TEST_AVATAR_ID", "Aria_Chair_public")
TEST_AUDIO_URL = os.getenv("HEYGEN_TEST_AUDIO_URL", "")


async def main():
    print("=" * 55)
    print("  SMOKE TEST: HeyGen Talking Head")
    print("=" * 55)

    if not TEST_AUDIO_URL:
        print("\n⚠️  HEYGEN_TEST_AUDIO_URL chưa có trong .env")
        print("   → Chạy smoke_tts.py trước để lấy audio URL.")
        return

    print(f"\n▶ Avatar ID: {TEST_AVATAR_ID}")
    print(f"▶ Audio URL: {TEST_AUDIO_URL[:60]}...")

    try:
        heygen = HeyGenService()

        print("\n[1/3] Tạo video HeyGen...")
        result = await heygen.create_video(
            avatar_id=TEST_AVATAR_ID,
            audio_url=TEST_AUDIO_URL,
            aspect_ratio="9:16",
        )
        video_id = result.get("video_id")
        print(f"      ✅ Video ID: {video_id}")

        print("\n[2/3] Polling (max 10 phút)...")
        video_url = await heygen.poll_video_status(video_id, timeout_seconds=600)
        print(f"      ✅ Video URL: {video_url}")
        assert video_url and video_url.startswith("http")

        print("\n[3/3] Validate TalkingHeadContract...")
        contract = TalkingHeadContract(
            url=video_url,
            avatar_id=TEST_AVATAR_ID,
            heygen_video_id=video_id,
        )
        print(f"      ✅ Contract OK: type={contract.type}")

        print("\n" + "=" * 55)
        print("  HEYGEN SMOKE TEST PASSED ✅")
        print("=" * 55)
        print(f"\n👁️  Lưu video URL cho smoke_assembly.py:")
        print(f"   SMOKE_TALKING_HEAD_URL={video_url}")

    except TimeoutError as e:
        print(f"\n⏱️  TIMEOUT (retryable): {e}")
    except Exception as e:
        print(f"\n❌ SMOKE TEST FAILED: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
