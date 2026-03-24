"""
HeyGen API Service
Tích hợp HeyGen để tạo video talking head AI influencer "Minh".
Docs: https://docs.heygen.com/reference/video-generate
"""

import asyncio
import logging
import httpx
from config.settings import settings
from services.quota_monitor_service import QuotaMonitorService

logger = logging.getLogger(__name__)

HEYGEN_BASE_URL = "https://api.heygen.com"


class HeyGenService:
    """
    Service tạo video talking head từ avatar + audio dùng HeyGen API.
    """

    def __init__(self):
        self.api_key = settings.HEYGEN_API_KEY
        if not self.api_key:
            raise ValueError("HEYGEN_API_KEY không được cấu hình trong .env")
        self.headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

    async def _record_usage(
        self,
        operation: str,
        usage: dict,
        metadata: dict | None = None,
        error: Exception | None = None,
    ) -> None:
        quota_metadata = {
            "service": "heygen_service",
            "operation": operation,
            "status": "error" if error else "success",
        }
        if metadata:
            quota_metadata.update(metadata)
        if error:
            quota_metadata["error_type"] = type(error).__name__
            quota_metadata["error_message"] = str(error)

        await QuotaMonitorService.record_runtime_usage(
            provider="heygen",
            usage=usage,
            metadata=quota_metadata,
        )

    # ─── Task 5.2: Tạo avatar từ ảnh persona ─────────────────────────────────

    async def create_avatar(self, image_url: str, avatar_name: str = "Minh_TripC") -> str:
        """
        Upload ảnh persona và tạo HeyGen avatar (thực hiện 1 lần, lưu avatar_id).

        Returns:
            str: avatar_id để dùng lại cho tất cả video sau
        """
        logger.info(f"Tạo HeyGen avatar từ: {image_url}")

        payload = {
            "avatar_name": avatar_name,
            "image_url": image_url,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.post(
                    f"{HEYGEN_BASE_URL}/v2/photo_avatar/create",
                    headers=self.headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                await self._record_usage(
                    operation="create_avatar",
                    usage={"requests": 1, "avatars": 1},
                    metadata={"avatar_name": avatar_name},
                    error=exc,
                )
                raise

        avatar_id = data.get("data", {}).get("avatar_id") or data.get("avatar_id")
        if not avatar_id:
            raise ValueError(f"HeyGen không trả về avatar_id: {data}")

        logger.info(f"Avatar đã tạo: {avatar_id}")
        await self._record_usage(
            operation="create_avatar",
            usage={"requests": 1, "avatars": 1},
            metadata={"avatar_name": avatar_name},
        )
        return avatar_id

    # ─── Task 5.3: Tạo video từ avatar + audio ────────────────────────────────

    async def create_video(
        self,
        avatar_id: str,
        audio_url: str,
        background: str = "blur",
        aspect_ratio: str = "9:16",
        width: int = 1080,
        height: int = 1920,
    ) -> dict:
        """
        Tạo request video mới trên HeyGen.

        Args:
            avatar_id: ID avatar "Minh" đã tạo trước
            audio_url: URL file MP3 từ Google TTS
            background: "blur" | "white" | URL ảnh nền
            aspect_ratio: "9:16" cho TikTok/Shorts

        Returns:
            dict chứa video_id để polling
        """
        logger.info(f"Tạo HeyGen video | avatar: {avatar_id} | ratio: {aspect_ratio}")

        # HeyGen v2 API - Video Generate
        payload = {
            "video_inputs": [
                {
                    "character": {
                        "type": "avatar",
                        "avatar_id": avatar_id,
                        "avatar_style": "normal",
                    },
                    "voice": {
                        "type": "audio",
                        "audio_url": audio_url,
                    },
                    "background": self._build_background(background),
                }
            ],
            "dimension": {"width": width, "height": height},
            "aspect_ratio": None,  # Dùng dimension thay
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.post(
                    f"{HEYGEN_BASE_URL}/v2/video/generate",
                    headers=self.headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                await self._record_usage(
                    operation="create_video",
                    usage={"requests": 1, "jobs": 1},
                    metadata={"avatar_id": avatar_id},
                    error=exc,
                )
                raise

        video_id = data.get("data", {}).get("video_id") or data.get("video_id")
        if not video_id:
            raise ValueError(f"HeyGen không trả về video_id: {data}")

        logger.info(f"Video job đã tạo: {video_id}")
        await self._record_usage(
            operation="create_video",
            usage={"requests": 1, "jobs": 1},
            metadata={"avatar_id": avatar_id, "video_id": video_id},
        )
        return {"video_id": video_id, "raw": data}

    async def get_remaining_quota(self) -> dict:
        """
        Fetch the provider-reported remaining HeyGen quota.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(
                    f"{HEYGEN_BASE_URL}/v2/user/remaining_quota",
                    headers=self.headers,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                await self._record_usage(
                    operation="get_remaining_quota",
                    usage={},
                    error=exc,
                )
                raise

        payload = data.get("data", {}) if isinstance(data, dict) else {}
        remaining_quota = payload.get("remaining_quota")
        details = payload.get("details") if isinstance(payload.get("details"), dict) else {}

        quota = {
            "unit": "quota_units",
            "exact": True,
            "source": "provider_live_endpoint",
        }
        if remaining_quota is not None:
            quota["remaining"] = remaining_quota
        if details.get("api") is not None:
            quota["remaining"] = details.get("api")

        await QuotaMonitorService.record_runtime_usage(
            provider="heygen",
            usage={},
            quota=quota,
            metadata={
                "service": "heygen_service",
                "operation": "get_remaining_quota",
                "status": "success",
            },
        )
        return data

    # ─── Polling video status ─────────────────────────────────────────────────

    async def poll_video_status(
        self,
        video_id: str,
        timeout_seconds: int = 600,
        poll_interval: int = 10,
    ) -> str:
        """
        Polling đợi video HeyGen hoàn thành.

        Returns:
            str: URL video đã render (HeyGen CDN URL)
        """
        elapsed = 0
        while elapsed < timeout_seconds:
            status_data = await self.get_video_status(video_id)
            status = status_data.get("data", {}).get("status") or status_data.get("status")

            logger.info(f"  HeyGen video {video_id}: {status} ({elapsed}s)")

            if status == "completed":
                video_url = (
                    status_data.get("data", {}).get("video_url")
                    or status_data.get("video_url")
                )
                if not video_url:
                    raise ValueError(f"HeyGen completed nhưng không có video_url: {status_data}")
                return video_url

            if status in ["failed", "error"]:
                error = status_data.get("data", {}).get("error") or status_data.get("error", "Unknown")
                raise ValueError(f"HeyGen video failed: {error}")

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(f"HeyGen video {video_id} vượt quá {timeout_seconds}s")

    async def get_video_status(self, video_id: str) -> dict:
        """Kiểm tra trạng thái video."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(
                    f"{HEYGEN_BASE_URL}/v1/video_status.get",
                    headers=self.headers,
                    params={"video_id": video_id},
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                await self._record_usage(
                    operation="get_video_status",
                    usage={"requests": 1, "status_checks": 1},
                    metadata={"video_id": video_id},
                    error=exc,
                )
                raise

        await self._record_usage(
            operation="get_video_status",
            usage={"requests": 1, "status_checks": 1},
            metadata={
                "video_id": video_id,
                "provider_status": data.get("data", {}).get("status")
                or data.get("status"),
            },
        )
        return data

    # ─── Helper ───────────────────────────────────────────────────────────────

    def _build_background(self, background: str) -> dict:
        """Xây dựng config background cho HeyGen."""
        if background == "blur":
            return {"type": "color", "value": "#ffffff"}  # White, HeyGen tự blur avatar
        elif background.startswith("http"):
            return {"type": "image", "url": background}
        else:
            # Màu hex
            return {"type": "color", "value": background}

    async def list_avatars(self) -> list:
        """Liệt kê tất cả avatars đã tạo."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{HEYGEN_BASE_URL}/v2/avatars",
                headers=self.headers,
            )
            resp.raise_for_status()
            data = resp.json()
        return data.get("data", {}).get("avatars", [])
