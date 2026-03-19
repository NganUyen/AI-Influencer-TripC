"""
Google Cloud Text-to-Speech Service
Tích hợp Google TTS API với giọng tiếng Việt Wavenet chất lượng cao.
Thay thế PlayHT vì rẻ hơn và giọng Việt tự nhiên hơn.
"""

import base64
import logging
import httpx
from config.settings import settings
from services.quota_monitor_service import QuotaMonitorService

logger = logging.getLogger(__name__)

# Các giọng Việt khuyến nghị
VIETNAMESE_VOICES = {
    "male_professional": "vi-VN-Wavenet-B",    # Giọng nam trầm, chuyên nghiệp
    "male_friendly": "vi-VN-Wavenet-D",         # Giọng nam trẻ, thân thiện (= "Minh")
    "female_warm": "vi-VN-Wavenet-A",           # Giọng nữ ấm
    "female_clear": "vi-VN-Wavenet-C",          # Giọng nữ rõ ràng, phổ thông
}

GOOGLE_TTS_ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"


class GoogleTTSService:
    """
    Service tích hợp Google Cloud Text-to-Speech API.
    Hỗ trợ giọng Wavenet tiếng Việt tự nhiên, multi-voice.
    """

    def __init__(self):
        self.api_key = settings.GOOGLE_TTS_API_KEY
        if not self.api_key:
            raise ValueError("GOOGLE_TTS_API_KEY không được cấu hình trong .env")

    async def _record_usage(
        self,
        text: str,
        voice: str,
        output_format: str,
        audio_bytes: bytes | None = None,
        error: Exception | None = None,
    ) -> None:
        metadata = {
            "service": "google_tts_service",
            "operation": "generate_audio",
            "voice": voice,
            "output_format": output_format,
            "status": "error" if error else "success",
        }
        if error:
            metadata["error_type"] = type(error).__name__
            metadata["error_message"] = str(error)

        usage = {
            "requests": 1,
            "characters": len(text),
        }
        if audio_bytes is not None:
            usage["bytes"] = len(audio_bytes)

        await QuotaMonitorService.record_runtime_usage(
            provider="google_tts",
            usage=usage,
            metadata=metadata,
        )

    async def generate_audio(
        self,
        text: str,
        voice: str = "vi-VN-Wavenet-D",   # Mặc định giọng "Minh" – nam trẻ
        speaking_rate: float = 1.05,       # Nhịp nói hơi nhanh, tự nhiên hơn
        pitch: float = 0.0,               # Giọng chuẩn (0 = không thay đổi)
        output_format: str = "MP3",
    ) -> bytes:
        """
        Gọi Google TTS API và trả về MP3 bytes.

        Args:
            text: Nội dung cần đọc (tối đa 5000 ký tự/request)
            voice: Tên giọng Wavenet (vi-VN-Wavenet-A/B/C/D)
            speaking_rate: Tốc độ đọc (0.25 – 4.0, 1.0 = bình thường)
            pitch: Cao độ giọng (-20.0 đến +20.0)
            output_format: "MP3" | "OGG_OPUS" | "LINEAR16"

        Returns:
            bytes: Dữ liệu audio MP3 thô
        """
        payload = {
            "input": {"text": text},
            "voice": {
                "languageCode": "vi-VN",
                "name": voice,
            },
            "audioConfig": {
                "audioEncoding": output_format,
                "speakingRate": speaking_rate,
                "pitch": pitch,
                "effectsProfileId": ["headphone-class-device"],
            },
        }

        url = f"{GOOGLE_TTS_ENDPOINT}?key={self.api_key}"
        logger.info(f"Gọi Google TTS | Voice: {voice} | {len(text)} ký tự")

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
            except Exception as exc:
                await self._record_usage(
                    text=text,
                    voice=voice,
                    output_format=output_format,
                    error=exc,
                )
                raise

        result = response.json()
        audio_content_b64 = result.get("audioContent")
        if not audio_content_b64:
            raise ValueError("Google TTS không trả về audioContent")

        audio_bytes = base64.b64decode(audio_content_b64)
        logger.info(f"Google TTS thành công | {len(audio_bytes):,} bytes MP3")
        await self._record_usage(
            text=text,
            voice=voice,
            output_format=output_format,
            audio_bytes=audio_bytes,
        )
        return audio_bytes

    async def generate_and_save(
        self,
        text: str,
        output_path: str,
        voice: str = "vi-VN-Wavenet-D",
        speaking_rate: float = 1.05,
    ) -> str:
        """
        Sinh audio và lưu file MP3 về local.

        Returns:
            str: Đường dẫn file MP3 đã lưu
        """
        audio_bytes = await self.generate_audio(text, voice=voice, speaking_rate=speaking_rate)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)
        logger.info(f"Đã lưu audio: {output_path}")
        return output_path

    def get_voices(self) -> dict:
        """Trả về danh sách giọng Việt được hỗ trợ."""
        return VIETNAMESE_VOICES


# ─────────────────────────────────────────────────────────────────────────────
# Script template GPT-4 cho AI influencer "Minh"
# ─────────────────────────────────────────────────────────────────────────────
INFLUENCER_SCRIPT_SYSTEM_PROMPT = """
Bạn là copywriter chuyên viết script TikTok cho AI influencer người Việt tên "Minh" 
- một KOL trẻ thú vị, am hiểu ẩm thực và du lịch Đà Nẵng.

Quy tắc bắt buộc:
1. Hook mạnh trong 3 giây đầu (câu hỏi bất ngờ hoặc claim táo bạo)
2. Giọng tự nhiên như người thật nói chuyện, không formal
3. Có đúng 1 "tip local" mà ít người biết
4. CTA cuối: mention app TripC tự nhiên, không quảng cáo lộ liễu
5. Tối đa 150 từ tiếng Việt
6. Format: [HOOK] | [NỘI DUNG] | [TIP LOCAL] | [CTA]
7. Không dùng từ: "chắc chắn", "tuyệt vời", "đặc sắc", "nổi tiếng"
"""

INFLUENCER_SCRIPT_USER_TEMPLATE = """
Viết script TikTok 45-60 giây cho "Minh" giới thiệu: {topic}

Địa điểm/Context: {location}
Tone: {tone}

Chỉ trả về script thuần túy, không có chú thích hay metadata.
"""
