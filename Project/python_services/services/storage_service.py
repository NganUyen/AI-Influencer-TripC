"""
Object storage service.

Supabase Storage is the primary backend. Legacy S3-compatible storage remains
available for older environments that still use Cloudflare R2-style settings.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from io import BytesIO
from typing import Any, BinaryIO, Dict
from urllib.parse import quote

import boto3
import httpx
from botocore.config import Config

from config.settings import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Upload, list, delete, and sign media assets in the configured storage backend."""

    _SUPABASE_LIST_LIMIT = 100

    def __init__(self):
        self.provider = settings.STORAGE_PROVIDER
        self.bucket_name = settings.STORAGE_BUCKET_NAME or ""
        self.public_base_url = (settings.STORAGE_PUBLIC_URL or "").rstrip("/")
        self.cache_control = f"max-age={settings.STORAGE_CACHE_CONTROL_SECONDS}"
        self.http_timeout = settings.STORAGE_HTTP_TIMEOUT_SECONDS

        self.supabase_api_url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1"
        self.supabase_headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        }

        self.s3_client = None
        if self.provider == "s3":
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=settings.R2_ENDPOINT_URL,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                config=Config(signature_version="s3v4"),
                region_name="auto",
            )

    async def upload(
        self,
        file_data: BinaryIO,
        filename: str,
        content_type: str = "application/octet-stream",
        metadata: Dict[str, str] | None = None,
    ) -> str:
        """Upload file data and return the public URL."""
        normalized_filename = self._normalize_path(filename)
        logger.info("Uploading file to %s storage: %s", self.provider, normalized_filename)

        if self.provider == "supabase":
            payload = await asyncio.to_thread(file_data.read)
            return await self._upload_supabase(
                data=payload,
                filename=normalized_filename,
                content_type=content_type,
                metadata=metadata,
            )

        return await self._upload_s3(
            file_data=file_data,
            filename=normalized_filename,
            content_type=content_type,
            metadata=metadata,
        )

    async def upload_bytes(
        self,
        data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        metadata: Dict[str, str] | None = None,
    ) -> str:
        """Upload raw bytes while keeping the same public interface for callers."""
        return await self.upload(
            file_data=BytesIO(data),
            filename=filename,
            content_type=content_type,
            metadata=metadata,
        )

    async def delete(self, filename: str) -> bool:
        """Delete a file from the configured storage backend."""
        normalized_filename = self._normalize_path(filename)
        logger.info("Deleting file from %s storage: %s", self.provider, normalized_filename)

        if self.provider == "supabase":
            await self._supabase_request(
                "DELETE",
                f"/object/{quote(self.bucket_name, safe='')}",
                json_body={"prefixes": [normalized_filename]},
            )
            return True

        try:
            await asyncio.to_thread(
                self.s3_client.delete_object,
                Bucket=self.bucket_name,
                Key=normalized_filename,
            )
            return True
        except Exception as exc:
            logger.error("Failed to delete file from S3-compatible storage: %s", exc)
            return False

    async def get_presigned_url(self, filename: str, expiration: int | None = None) -> str:
        """Generate a temporary signed URL."""
        normalized_filename = self._normalize_path(filename)
        expires_in = expiration or settings.STORAGE_SIGNED_URL_TTL_SECONDS

        if self.provider == "supabase":
            response = await self._supabase_request(
                "POST",
                f"/object/sign/{self._supabase_object_key(normalized_filename)}",
                json_body={"expiresIn": expires_in},
            )
            signed_url = response.get("signedURL") or response.get("signedUrl")
            if not signed_url:
                raise RuntimeError("Supabase Storage did not return a signed URL")
            if signed_url.startswith("/"):
                return f"{self.supabase_api_url}{signed_url}"
            return signed_url

        return self.s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": normalized_filename},
            ExpiresIn=expires_in,
        )

    async def list_files(self, prefix: str = "") -> list[str]:
        """List file keys in the configured storage backend."""
        normalized_prefix = self._normalize_path(prefix)

        if self.provider == "supabase":
            return await self._list_supabase_recursive(normalized_prefix)

        response = await asyncio.to_thread(
            self.s3_client.list_objects_v2,
            Bucket=self.bucket_name,
            Prefix=normalized_prefix,
        )
        return [obj["Key"] for obj in response.get("Contents", [])]

    async def _upload_supabase(
        self,
        data: bytes,
        filename: str,
        content_type: str,
        metadata: Dict[str, str] | None,
    ) -> str:
        headers = {
            **self.supabase_headers,
            "cache-control": self.cache_control,
            "content-type": content_type,
            "x-upsert": str(settings.STORAGE_UPSERT).lower(),
        }
        if metadata:
            encoded_metadata = base64.b64encode(json.dumps(metadata).encode("utf-8"))
            headers["x-metadata"] = encoded_metadata.decode("ascii")

        await self._supabase_request(
            "POST",
            f"/object/{self._supabase_object_key(filename)}",
            headers=headers,
            data=data,
        )
        public_url = self._build_public_url(filename)
        logger.info("File uploaded successfully: %s", public_url)
        return public_url

    async def _upload_s3(
        self,
        file_data: BinaryIO,
        filename: str,
        content_type: str,
        metadata: Dict[str, str] | None,
    ) -> str:
        extra_args: Dict[str, Any] = {
            "ContentType": content_type,
            "ACL": "public-read",
        }
        if metadata:
            extra_args["Metadata"] = metadata

        await asyncio.to_thread(
            self.s3_client.upload_fileobj,
            file_data,
            self.bucket_name,
            filename,
            ExtraArgs=extra_args,
        )
        public_url = self._build_public_url(filename)
        logger.info("File uploaded successfully: %s", public_url)
        return public_url

    async def _supabase_request(
        self,
        method: str,
        path: str,
        *,
        headers: Dict[str, str] | None = None,
        data: bytes | None = None,
        json_body: Dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.supabase_api_url}{path}"
        request_headers = {**self.supabase_headers, **(headers or {})}

        async with httpx.AsyncClient(timeout=self.http_timeout) as client:
            response = await client.request(
                method,
                url,
                headers=request_headers,
                content=data,
                json=json_body,
            )
            response.raise_for_status()
            if not response.content:
                return None
            return response.json()

    async def _list_supabase_recursive(self, prefix: str) -> list[str]:
        files: list[str] = []
        offset = 0

        while True:
            page = await self._supabase_request(
                "POST",
                f"/object/list/{quote(self.bucket_name, safe='')}",
                json_body={
                    "prefix": prefix,
                    "limit": self._SUPABASE_LIST_LIMIT,
                    "offset": offset,
                    "sortBy": {"column": "name", "order": "asc"},
                },
            )

            if not isinstance(page, list):
                break

            for entry in page:
                name = str(entry.get("name") or "").strip()
                if not name:
                    continue

                full_path = f"{prefix}/{name}" if prefix else name
                if entry.get("id") is None:
                    files.extend(await self._list_supabase_recursive(full_path))
                else:
                    files.append(full_path)

            if len(page) < self._SUPABASE_LIST_LIMIT:
                break
            offset += self._SUPABASE_LIST_LIMIT

        return files

    def _supabase_object_key(self, filename: str) -> str:
        return (
            f"{quote(self.bucket_name, safe='')}/"
            f"{quote(self._normalize_path(filename), safe='/')}"
        )

    def _build_public_url(self, filename: str) -> str:
        return f"{self.public_base_url}/{quote(self._normalize_path(filename), safe='/')}"

    @staticmethod
    def _normalize_path(path: str) -> str:
        parts = [part for part in str(path).split("/") if part]
        return "/".join(parts)
