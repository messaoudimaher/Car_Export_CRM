"""S3 / MinIO ObjectStorageProvider Adapter (TASK-1003)."""

from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.errors import NotFoundException, ServiceUnavailableException
from app.ports.object_storage import ObjectStorageProvider


class S3StorageAdapter(ObjectStorageProvider):
    """S3 and MinIO compatible implementation of ObjectStorageProvider."""

    def __init__(
        self,
        bucket_name: str | None = None,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        self.bucket_name = bucket_name or settings.OBJECT_STORAGE_BUCKET
        self.endpoint_url = endpoint_url or settings.S3_ENDPOINT_URL
        self.access_key_id = access_key_id or settings.S3_ACCESS_KEY_ID
        self.secret_access_key = secret_access_key or settings.S3_SECRET_ACCESS_KEY

        # Initialize boto3 S3 client
        client_kwargs: dict[str, Any] = {
            "service_name": "s3",
            "aws_access_key_id": self.access_key_id,
            "aws_secret_access_key": self.secret_access_key,
            "config": Config(signature_version="s3v4"),
        }
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url

        self.s3_client = boto3.client(**client_kwargs)

    async def upload_object(
        self, object_key: str, data: bytes, content_type: str = "application/pdf"
    ) -> str:
        """Upload binary payload to S3 / MinIO bucket."""
        self.validate_object_key(object_key)
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=data,
                ContentType=content_type,
            )
            return object_key
        except ClientError as err:
            raise ServiceUnavailableException(f"Failed to upload object to storage: {err}") from err

    async def get_object(self, object_key: str) -> bytes:
        """Download binary payload from S3 / MinIO bucket."""
        self.validate_object_key(object_key)
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=object_key)
            content: bytes = response["Body"].read()
            return content
        except ClientError as err:
            error_code = err.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchKey"):
                raise NotFoundException(f"Object '{object_key}' not found in storage") from err
            raise ServiceUnavailableException(
                f"Failed to retrieve object from storage: {err}"
            ) from err

    async def generate_presigned_url(self, object_key: str, expiration_seconds: int = 3600) -> str:
        """Generate a short-lived S3 / MinIO presigned URL."""
        self.validate_object_key(object_key)
        try:
            url: str = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": object_key},
                ExpiresIn=expiration_seconds,
            )
            return url
        except ClientError as err:
            raise ServiceUnavailableException(f"Failed to generate presigned URL: {err}") from err

    async def delete_object(self, object_key: str) -> bool:
        """Delete object from S3 / MinIO bucket."""
        self.validate_object_key(object_key)
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except ClientError:
            return False
