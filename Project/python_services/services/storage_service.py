"""
Cloudflare R2 Storage Service
Object storage with zero egress fees
"""

import boto3
import asyncio
import logging
from typing import BinaryIO, Dict, Any
from io import BytesIO
from botocore.config import Config
from config.settings import settings

logger = logging.getLogger(__name__)


class StorageService:
    """
    Integration with Cloudflare R2 for media asset storage
    Uses S3-compatible API
    """

    def __init__(self):
        self.bucket_name = settings.R2_BUCKET_NAME
        self.public_domain = settings.R2_PUBLIC_DOMAIN

        # Configure S3 client for R2
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
        metadata: Dict[str, str] = None,
    ) -> str:
        """
        Upload file to R2 storage

        Args:
            file_data: File data as binary stream
            filename: Target filename/path in bucket
            content_type: MIME type of the file
            metadata: Optional metadata tags

        Returns:
            Public URL of the uploaded file
        """
        logger.info(f"Uploading file to R2: {filename}")

        try:
            extra_args = {
                "ContentType": content_type,
                "ACL": "public-read",  # Make file publicly accessible
            }

            if metadata:
                extra_args["Metadata"] = metadata

            await asyncio.to_thread(
                self.s3_client.upload_fileobj,
                file_data, self.bucket_name, filename, ExtraArgs=extra_args
            )

            # Construct public URL
            public_url = f"{self.public_domain}/{filename}"
            logger.info(f"File uploaded successfully: {public_url}")

            return public_url

        except Exception as e:
            logger.error(f"Failed to upload file to R2: {str(e)}")
            raise

    async def upload_bytes(
        self,
        data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        metadata: Dict[str, str] = None,
    ) -> str:
        """
        Upload raw bytes to R2 storage (convenience method)

        Args:
            data: Raw bytes data
            filename: Target filename/path in bucket
            content_type: MIME type of the file
            metadata: Optional metadata tags

        Returns:
            Public URL of the uploaded file
        """
        file_obj = BytesIO(data)
        return await self.upload(
            file_data=file_obj,
            filename=filename,
            content_type=content_type,
            metadata=metadata,
        )

    async def delete(self, filename: str) -> bool:
        """
        Delete file from R2 storage

        Args:
            filename: File path in bucket

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Deleting file from R2: {filename}")

        try:
            await asyncio.to_thread(
                self.s3_client.delete_object, Bucket=self.bucket_name, Key=filename
            )
            logger.info(f"File deleted successfully: {filename}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete file from R2: {str(e)}")
            return False

    async def get_presigned_url(self, filename: str, expiration: int = 3600) -> str:
        """
        Generate presigned URL for temporary access

        Args:
            filename: File path in bucket
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            Presigned URL
        """
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": filename},
                ExpiresIn=expiration,
            )
            return url

        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            raise

    async def list_files(self, prefix: str = "") -> list:
        """
        List files in bucket with optional prefix filter

        Args:
            prefix: Path prefix to filter by

        Returns:
            List of file keys
        """
        try:
            response = await asyncio.to_thread(
                self.s3_client.list_objects_v2,
                Bucket=self.bucket_name, Prefix=prefix
            )

            files = [obj["Key"] for obj in response.get("Contents", [])]
            return files

        except Exception as e:
            logger.error(f"Failed to list files from R2: {str(e)}")
            raise
