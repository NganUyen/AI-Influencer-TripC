"""
Google Cloud Text-to-Speech Service
Tích hợp Google TTS API với giọng tiếng Việt Wavenet chất lượng cao.
Thay thế PlayHT vì rẻ hơn và giọng Việt tự nhiên hơn.
"""

import base64
import binascii
import logging
import httpx
from config.settings import settings
from services.quota_monitor_service import QuotaMonitorService

logger = logging.getLogger(__name__)

# Các giọng Việt khuyến nghị
VIETNAMESE_VOICES = {
    "male_professional": "vi-VN-Wavenet-B",  # Giọng nam trầm, chuyên nghiệp
    "male_friendly": "vi-VN-Wavenet-D",  # Giọng nam trẻ, thân thiện (= "Minh")
    "female_warm": "vi-VN-Wavenet-A",  # Giọng nữ ấm
    "female_clear": "vi-VN-Wavenet-C",  # Giọng nữ rõ ràng, phổ thông
}

ENGLISH_VOICES = {
    "male_professional": "en-GB-Wavenet-B",
    "male_friendly": "en-US-Studio-O",
    "female_warm": "en-US-Neural2-F",
    "female_clear": "en-AU-Wavenet-C",
}

VOICE_LABELS = {
    "male_professional": "Male Professional",
    "male_friendly": "Male Friendly",
    "female_warm": "Female Warm",
    "female_clear": "Female Clear",
    "vi-VN-Wavenet-A": "Vietnamese Female Warm",
    "vi-VN-Wavenet-B": "Vietnamese Male Professional",
    "vi-VN-Wavenet-C": "Vietnamese Female Clear",
    "vi-VN-Wavenet-D": "Vietnamese Male Friendly",
    "en-GB-Wavenet-B": "English UK Male Professional",
    "en-US-Studio-O": "English US Male Friendly",
    "en-US-Neural2-F": "English US Female Warm",
    "en-AU-Wavenet-C": "English AU Female Clear",
}

GOOGLE_TTS_ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"

# Validation constants
MAX_TEXT_LENGTH = 5000
MIN_SPEAKING_RATE = 0.25
MAX_SPEAKING_RATE = 4.0
MIN_PITCH = -20.0
MAX_PITCH = 20.0
VALID_OUTPUT_FORMATS = {"MP3", "OGG_OPUS", "LINEAR16"}

# Timeout configuration: base timeout + extra time based on text length
BASE_TIMEOUT_SECONDS = 15.0
TIMEOUT_PER_1000_CHARS = 5.0
MAX_TIMEOUT_SECONDS = 60.0


class GoogleTTSService:
    """
    Service tích hợp Google Cloud Text-to-Speech API.
    Hỗ trợ giọng Wavenet tiếng Việt tự nhiên, multi-voice.
    """

    def __init__(self):
        self.api_key = settings.GOOGLE_TTS_API_KEY
        if not self.api_key:
            raise ValueError("GOOGLE_TTS_API_KEY không được cấu hình trong .env")

    def _sanitize_text(self, value: object) -> str:
        text = str(value)
        if self.api_key:
            return text.replace(self.api_key, "***")
        return text

    @staticmethod
    def _normalize_language_name(language: str | None) -> str:
        normalized = str(language or "").strip().lower()
        if normalized.startswith("vi") or "viet" in normalized:
            return "vi"
        if normalized.startswith("en") or "english" in normalized:
            return "en"
        return ""

    @classmethod
    def resolve_voice_name(
        cls, voice: str | None, *, language: str | None = None
    ) -> str:
        requested = str(voice or "").strip()
        language_key = cls._normalize_language_name(language)

        if (
            requested in VIETNAMESE_VOICES.values()
            or requested in ENGLISH_VOICES.values()
        ):
            return requested

        alias = requested.lower()
        if language_key == "en" and alias in ENGLISH_VOICES:
            return ENGLISH_VOICES[alias]
        if alias in VIETNAMESE_VOICES:
            return VIETNAMESE_VOICES[alias]
        if alias in ENGLISH_VOICES:
            return ENGLISH_VOICES[alias]

        return requested or VIETNAMESE_VOICES["male_friendly"]

    @classmethod
    def infer_language_code(
        cls, voice: str | None, *, fallback_language: str | None = None
    ) -> str:
        resolved_voice = cls.resolve_voice_name(voice, language=fallback_language)
        parts = [part for part in resolved_voice.split("-") if part]
        if len(parts) >= 2:
            return f"{parts[0]}-{parts[1]}"
        if cls._normalize_language_name(fallback_language) == "en":
            return "en-US"
        return "vi-VN"

    @classmethod
    def describe_voice(cls, voice: str | None, *, language: str | None = None) -> str:
        requested = str(voice or "").strip()
        if not requested:
            return "Unconfigured"
        if requested in VOICE_LABELS:
            return VOICE_LABELS[requested]
        if requested.lower() in VOICE_LABELS:
            return VOICE_LABELS[requested.lower()]
        resolved = cls.resolve_voice_name(requested, language=language)
        return VOICE_LABELS.get(resolved, resolved)

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
            metadata["error_message"] = self._sanitize_text(error)

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
        voice: str = "vi-VN-Wavenet-D",  # Mặc định giọng "Minh" – nam trẻ
        speaking_rate: float = 1.05,  # Nhịp nói hơi nhanh, tự nhiên hơn
        pitch: float = 0.0,  # Giọng chuẩn (0 = không thay đổi)
        output_format: str = "MP3",
        language: str | None = None,
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

        Raises:
            ValueError: If text is empty, too long, or parameters are invalid
        """
        # Validate text
        text = text.strip() if text else ""
        if not text:
            raise ValueError("Text cannot be empty")
        if len(text) > MAX_TEXT_LENGTH:
            raise ValueError(
                f"Text exceeds {MAX_TEXT_LENGTH} character limit: {len(text)} characters"
            )

        # Validate speaking_rate
        if not (MIN_SPEAKING_RATE <= speaking_rate <= MAX_SPEAKING_RATE):
            raise ValueError(
                f"speaking_rate must be between {MIN_SPEAKING_RATE} and {MAX_SPEAKING_RATE}, "
                f"got {speaking_rate}"
            )

        # Validate pitch
        if not (MIN_PITCH <= pitch <= MAX_PITCH):
            raise ValueError(
                f"pitch must be between {MIN_PITCH} and {MAX_PITCH}, got {pitch}"
            )

        # Validate output_format
        output_format_upper = output_format.upper()
        if output_format_upper not in VALID_OUTPUT_FORMATS:
            raise ValueError(
                f"output_format must be one of {VALID_OUTPUT_FORMATS}, got '{output_format}'"
            )

        resolved_voice = self.resolve_voice_name(voice, language=language)
        payload = {
            "input": {"text": text},
            "voice": {
                "languageCode": self.infer_language_code(
                    resolved_voice, fallback_language=language
                ),
                "name": resolved_voice,
            },
            "audioConfig": {
                "audioEncoding": output_format_upper,
                "speakingRate": speaking_rate,
                "pitch": pitch,
                "effectsProfileId": ["headphone-class-device"],
            },
        }

        url = GOOGLE_TTS_ENDPOINT
        headers = {"X-Goog-Api-Key": self.api_key}
        logger.info(f"Gọi Google TTS | Voice: {resolved_voice} | {len(text)} ký tự")

        # Calculate timeout based on text length
        timeout = min(
            BASE_TIMEOUT_SECONDS + (len(text) / 1000) * TIMEOUT_PER_1000_CHARS,
            MAX_TIMEOUT_SECONDS,
        )

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
            except httpx.HTTPStatusError as http_exc:
                # [SECURITY] Keep API keys out of error propagation and suppress
                # the original chained exception so worker tracebacks stay clean.
                error_msg = self._sanitize_text(http_exc)
                sanitized_exc = httpx.HTTPStatusError(
                    error_msg,
                    request=http_exc.request,
                    response=http_exc.response,
                )
                await self._record_usage(
                    text=text,
                    voice=resolved_voice,
                    output_format=output_format_upper,
                    error=sanitized_exc,
                )
                raise sanitized_exc from None
            except Exception as exc:
                await self._record_usage(
                    text=text,
                    voice=resolved_voice,
                    output_format=output_format_upper,
                    error=exc,
                )
                raise

        result = response.json()
        audio_content_b64 = result.get("audioContent")
        if not audio_content_b64:
            error = ValueError("Google TTS không trả về audioContent")
            await self._record_usage(
                text=text,
                voice=resolved_voice,
                output_format=output_format_upper,
                error=error,
            )
            raise error

        try:
            audio_bytes = base64.b64decode(audio_content_b64)
        except (binascii.Error, ValueError) as decode_error:
            error = ValueError(
                f"Invalid base64 audio content from Google TTS: {decode_error}"
            )
            await self._record_usage(
                text=text,
                voice=resolved_voice,
                output_format=output_format_upper,
                error=error,
            )
            raise error from decode_error

        if not audio_bytes:
            error = ValueError("Google TTS returned empty audio data")
            await self._record_usage(
                text=text,
                voice=resolved_voice,
                output_format=output_format_upper,
                error=error,
            )
            raise error

        logger.info(f"Google TTS thành công | {len(audio_bytes):,} bytes MP3")
        await self._record_usage(
            text=text,
            voice=resolved_voice,
            output_format=output_format_upper,
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
        audio_bytes = await self.generate_audio(
            text, voice=voice, speaking_rate=speaking_rate
        )
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
