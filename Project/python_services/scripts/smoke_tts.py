"""
Smoke Test: Google TTS
=======================
Chạy: .\.venv\Scripts\python scripts/smoke_tts.py
"""
import asyncio
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from services.google_tts_service import GoogleTTSService
from services.storage_service import StorageService
from services.contracts import AudioContract


async def main():
    print("=" * 55)
    print("  SMOKE TEST: Google TTS")
    print("=" * 55)

    test_script = (
        "TripC là ứng dụng du lịch thông minh hàng đầu Việt Nam. "
        "Chỉ cần 3 bước, bạn có thể lên kế hoạch cho cả chuyến đi. "
        "Thử ngay hôm nay!"
    )
    voice = "vi-VN-Wavenet-D"  # Minh voice

    print(f"\n▶ Script: {test_script[:60]}...")
    print(f"▶ Voice: {voice}")

    try:
        tts = GoogleTTSService()

        print("\n[1/3] Gọi Google TTS API...")
        audio_bytes = await tts.generate_audio(
            text=test_script,
            voice=voice,
        )
        print(f"      ✅ Audio bytes: {len(audio_bytes):,} bytes")
        assert len(audio_bytes) > 1000, "Audio quá nhỏ — có thể rỗng"

        # Save locally
        local_path = "smoke_test_audio.mp3"
        with open(local_path, "wb") as f:
            f.write(audio_bytes)
        print(f"      ✅ Saved locally: {local_path}")

        print("\n[2/3] Upload lên Cloudflare R2...")
        storage = StorageService()
        audio_url = await storage.upload_bytes(
            data=audio_bytes,
            filename="smoke_test/tts_smoke.mp3",
            content_type="audio/mpeg",
        )
        print(f"      ✅ URL: {audio_url}")
        assert audio_url.startswith("http"), "URL không hợp lệ"

        print("\n[3/3] Validate AudioContract...")
        contract = AudioContract(url=audio_url, voice=voice)
        print(f"      ✅ Contract OK: type={contract.type}, voice={contract.voice}")

        print("\n" + "=" * 55)
        print("  TTS SMOKE TEST PASSED ✅")
        print("=" * 55)
        print(f"\n👁️  Lưu âm thanh URL cho smoke_heygen.py:")
        print(f"   HEYGEN_TEST_AUDIO_URL={audio_url}")

    except Exception as e:
        print(f"\n❌ SMOKE TEST FAILED: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
