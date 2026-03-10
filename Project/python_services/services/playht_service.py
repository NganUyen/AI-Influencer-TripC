"""
PlayHT Service Integration
Audio synthesis with 900+ voices across 142 languages
"""

import httpx
import logging
from typing import Dict, Any, Optional
from config.settings import settings

logger = logging.getLogger(__name__)


class PlayHTService:
    """
    Integration with PlayHT for AI voice synthesis
    Supports instant voice cloning and extensive voice library
    """

    def __init__(self):
        self.api_key = settings.PLAYHT_API_KEY
        self.user_id = settings.PLAYHT_USER_ID
        self.client = httpx.AsyncClient(
            base_url="https://api.play.ht/api/v2",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "X-User-ID": self.user_id,
            },
            timeout=120.0,
        )

    async def generate_audio(
        self,
        text: str,
        voice_id: str,
        voice_engine: str = "PlayHT2.0",
        output_format: str = "mp3",
        speed: float = 1.0,
        temperature: float = 0.8,
    ) -> Dict[str, Any]:
        """
        Generate audio from text using specified voice

        Args:
            text: Text to convert to speech
            voice_id: Voice ID from PlayHT library
            voice_engine: Engine to use (PlayHT2.0, PlayHT2.0-turbo, etc.)
            output_format: Audio format (mp3, wav, ogg, flac)
            speed: Speech speed (0.5 to 2.0)
            temperature: Voice temperature/variation (0.0 to 2.0)
        """
        logger.info(f"Generating audio with voice {voice_id}")

        payload = {
            "text": text,
            "voice": voice_id,
            "voice_engine": voice_engine,
            "output_format": output_format,
            "speed": speed,
            "temperature": temperature,
            "quality": "premium",
        }

        try:
            response = await self.client.post("/tts", json=payload)
            response.raise_for_status()

            result = response.json()
            logger.info(f"Audio generated successfully: {result.get('url')}")

            return {
                "url": result.get("url"),
                "duration": result.get("duration"),
                "voice_id": voice_id,
                "text": text[:100] + "..." if len(text) > 100 else text,
            }

        except httpx.HTTPError as e:
            logger.error(f"Audio generation failed: {str(e)}")
            raise

    async def clone_voice(self, audio_url: str, voice_name: str) -> Dict[str, Any]:
        """
        Clone a voice from audio sample (requires 30+ seconds of audio)

        Args:
            audio_url: URL to audio sample
            voice_name: Name for the cloned voice
        """
        logger.info(f"Cloning voice: {voice_name}")

        try:
            response = await self.client.post(
                "/cloned-voices/instant",
                json={"voice_name": voice_name, "sample_file_url": audio_url},
            )
            response.raise_for_status()

            result = response.json()
            logger.info(f"Voice cloned successfully: {result.get('id')}")

            return result

        except httpx.HTTPError as e:
            logger.error(f"Voice cloning failed: {str(e)}")
            raise

    async def list_voices(
        self, language: Optional[str] = None, gender: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List available voices from PlayHT library

        Args:
            language: Filter by language code (e.g., "en", "es", "fr")
            gender: Filter by gender ("male", "female")
        """
        params = {}
        if language:
            params["language"] = language
        if gender:
            params["gender"] = gender

        response = await self.client.get("/voices", params=params)
        response.raise_for_status()

        return response.json()

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
