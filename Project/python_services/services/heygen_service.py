"""
HeyGen API Service
Tích hợp HeyGen để tạo video talking head AI influencer "Minh".
Docs: https://docs.heygen.com/reference/video-generate
"""

import asyncio
import logging
from urllib.parse import urlparse
import httpx
from config.settings import settings
from services.errors import HeyGenAvatarSetupError, HeyGenTimeoutError
from services.quota_monitor_service import QuotaMonitorService

logger = logging.getLogger(__name__)

HEYGEN_BASE_URL = "https://api.heygen.com"
HEYGEN_UPLOAD_BASE_URL = "https://upload.heygen.com"
HEYGEN_READY_AVATAR_STATUSES = {
    "ready",
    "completed",
    "complete",
    "success",
    "succeeded",
    "active",
}
HEYGEN_FAILED_AVATAR_STATUSES = {"failed", "error", "rejected", "cancelled", "canceled"}


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
        Upload ảnh persona và tạo HeyGen photo avatar (thực hiện 1 lần, lưu avatar_id).

        Returns:
            str: avatar_id để dùng lại cho tất cả video sau
        """
        logger.info(f"Tạo HeyGen avatar từ: {image_url}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                image_response = await client.get(image_url, follow_redirects=True)
                image_response.raise_for_status()

                upload_headers = {
                    "X-Api-Key": self.api_key,
                    "Accept": "application/json",
                    "Content-Type": self._detect_image_content_type(
                        image_url=image_url,
                        response=image_response,
                    ),
                }
                upload_resp = await client.post(
                    f"{HEYGEN_UPLOAD_BASE_URL}/v1/asset",
                    headers=upload_headers,
                    content=image_response.content,
                )
                upload_resp.raise_for_status()
                upload_data = upload_resp.json()
                image_key = upload_data.get("data", {}).get("image_key")
                if not image_key:
                    raise ValueError(
                        f"HeyGen upload không trả về image_key: {upload_data}"
                    )

                resp = await client.post(
                    f"{HEYGEN_BASE_URL}/v2/photo_avatar/avatar_group/create",
                    headers=self.headers,
                    json={
                        "name": avatar_name,
                        "image_key": image_key,
                    },
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

        avatar_payload = data.get("data", {}) if isinstance(data, dict) else {}
        avatar_id = (
            avatar_payload.get("id")
            or avatar_payload.get("avatar_id")
            or avatar_payload.get("group_id")
            or data.get("avatar_id")
        )
        if not avatar_id:
            raise ValueError(f"HeyGen không trả về avatar_id: {data}")

        logger.info(f"Avatar đã tạo: {avatar_id}")
        await self._record_usage(
            operation="create_avatar",
            usage={"requests": 1, "avatars": 1},
            metadata={"avatar_name": avatar_name},
        )
        return avatar_id

    async def get_avatar_details(self, avatar_id: str) -> dict:
        """Fetch current HeyGen photo-avatar status/details."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(
                    f"{HEYGEN_BASE_URL}/v2/photo_avatar/{avatar_id}",
                    headers=self.headers,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                await self._record_usage(
                    operation="get_avatar_details",
                    usage={"requests": 1, "status_checks": 1},
                    metadata={"avatar_id": avatar_id},
                    error=exc,
                )
                raise

        await self._record_usage(
            operation="get_avatar_details",
            usage={"requests": 1, "status_checks": 1},
            metadata={
                "avatar_id": avatar_id,
                "provider_status": self._extract_avatar_status(data),
            },
        )
        return data

    async def wait_for_avatar_ready(
        self,
        avatar_id: str,
        *,
        timeout_seconds: int = 45,
        poll_interval: int = 5,
    ) -> dict:
        """Poll HeyGen until the photo avatar is actually ready for use."""
        elapsed = 0
        last_payload: dict | None = None

        while elapsed <= timeout_seconds:
            last_payload = await self.get_avatar_details(avatar_id)
            status = self._normalize_status(self._extract_avatar_status(last_payload))

            logger.info(
                "HeyGen avatar %s status: %s (%ss)",
                avatar_id,
                status or "unknown",
                elapsed,
            )

            if status in HEYGEN_READY_AVATAR_STATUSES:
                return last_payload

            if status in HEYGEN_FAILED_AVATAR_STATUSES:
                raise HeyGenAvatarSetupError(
                    "HeyGen reported this avatar as failed"
                    + (f" (status={status})" if status else "")
                )

            if elapsed >= timeout_seconds:
                break

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        status = self._normalize_status(self._extract_avatar_status(last_payload))
        raise HeyGenTimeoutError(
            "HeyGen is still processing this avatar"
            + (f" (status={status})" if status else "")
        )

    # ─── Task 5.3: Tạo video từ avatar + audio ────────────────────────────────

    async def create_video(
        self,
        avatar_id: str,
        audio_url: str,
        background: str = "blur",
        aspect_ratio: str = "9:16",
        width: int = 1080,
        height: int = 1920,
        allow_aspect_ratio_fallback: bool = True,
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

        candidate_ratios = [aspect_ratio]
        if aspect_ratio == "1:1" and allow_aspect_ratio_fallback:
            # HeyGen v2 may reject square aspect ratio for some accounts/avatar types.
            candidate_ratios.append("9:16")

        async with httpx.AsyncClient(timeout=60.0) as client:
            data = None
            try:
                last_exc: Exception | None = None
                for candidate_ratio in candidate_ratios:
                    payload = {
                        "avatar_id": avatar_id,
                        "audio_url": audio_url,
                        "title": f"{avatar_id}-{candidate_ratio}",
                        "resolution": "1080p" if max(width, height) >= 1080 else "720p",
                        "aspect_ratio": candidate_ratio,
                        "expressiveness": "low",
                        "background": self._build_background(background),
                    }

                    resp = await client.post(
                        f"{HEYGEN_BASE_URL}/v2/videos",
                        headers=self.headers,
                        json=payload,
                    )
                    if resp.is_success:
                        data = resp.json()
                        break

                    response_text = (resp.text or "").strip()
                    logger.error(
                        "HeyGen create_video failed | status=%s | ratio=%s | response=%s",
                        resp.status_code,
                        candidate_ratio,
                        response_text[:600],
                    )

                    last_exc = httpx.HTTPStatusError(
                        f"HeyGen create_video failed with status {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )

                    # Only attempt fallback on request-validation errors.
                    if (
                        resp.status_code != 400
                        or candidate_ratio != "1:1"
                        or "9:16" not in candidate_ratios
                    ):
                        raise last_exc

                    logger.warning(
                        "Retrying HeyGen create_video with fallback aspect_ratio=9:16"
                    )

                if data is None and last_exc is not None:
                    raise last_exc
            except Exception as exc:
                await self._record_usage(
                    operation="create_video",
                    usage={"requests": 1, "jobs": 1},
                    metadata={"avatar_id": avatar_id},
                    error=exc,
                )
                raise

        video_id = data.get("video_id") or data.get("data", {}).get("video_id")
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
                # Extract error details from various possible response shapes
                data = status_data.get("data", {})
                error = (
                    data.get("failure_message")
                    or data.get("error")
                    or status_data.get("error")
                    or "Unknown"
                )
                error_code = (
                    data.get("failure_code")
                    or data.get("error_code")
                    or status_data.get("error_code")
                )
                logger.error(
                    "HeyGen video generation FAILED | video_id=%s | status=%s | error=%s | error_code=%s | full_response=%s",
                    video_id,
                    status,
                    error,
                    error_code,
                    str(status_data)[:500],
                )
                raise ValueError(f"HeyGen video failed: {error} (code={error_code}, video_id={video_id})")

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(f"HeyGen video {video_id} vượt quá {timeout_seconds}s")

    async def get_video_status(self, video_id: str) -> dict:
        """Kiểm tra trạng thái video."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                try:
                    resp = await client.get(
                        f"{HEYGEN_BASE_URL}/v2/videos/{video_id}",
                        headers=self.headers,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code not in {404, 405}:
                        raise
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

    def _detect_image_content_type(
        self,
        *,
        image_url: str,
        response: httpx.Response,
    ) -> str:
        content_type = (response.headers.get("content-type") or "").split(";", 1)[0]
        if content_type in {"image/jpeg", "image/png"}:
            return content_type

        path = urlparse(image_url).path.lower()
        if path.endswith(".png"):
            return "image/png"
        if path.endswith(".jpg") or path.endswith(".jpeg"):
            return "image/jpeg"

        image_bytes = response.content[:16]
        if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if image_bytes.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"

        # HeyGen Upload Asset only accepts PNG/JPEG for images.
        return "image/jpeg"

    def _extract_avatar_status(self, payload: dict | None) -> str | None:
        if not isinstance(payload, dict):
            return None

        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("status", "generation_status", "training_status"):
                value = data.get(key)
                if value is not None:
                    return str(value)

        for key in ("status", "generation_status", "training_status"):
            value = payload.get(key)
            if value is not None:
                return str(value)
        return None

    def _normalize_status(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip().lower()
        return normalized or None

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
