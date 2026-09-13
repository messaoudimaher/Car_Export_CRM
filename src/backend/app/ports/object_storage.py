"""ObjectStorageProvider Port Definition & Path Traversal Guard (ADR-0018, TASK-1003)."""

from abc import ABC, abstractmethod

from app.core.errors import ValidationException


class ObjectStorageProvider(ABC):
    """Provider-agnostic port interface for private object storage operations."""

    @staticmethod
    def validate_object_key(object_key: str) -> None:
        """Validate object key construction to prevent path traversal attacks.

        Args:
            object_key: S3/Storage object key path string.

        Raises:
            ValidationException: If key contains path traversal sequences or invalid format.
        """
        if not object_key or not object_key.strip():
            raise ValidationException("Object key cannot be empty")

        key = object_key.strip()
        if key.startswith("/") or key.startswith("\\"):
            raise ValidationException("Object key cannot start with a path separator")

        # Guard against directory traversal
        parts = key.replace("\\", "/").split("/")
        for part in parts:
            if part in ("..", "."):
                raise ValidationException("Path traversal sequence prohibited in object key")

    @abstractmethod
    async def upload_object(
        self, object_key: str, data: bytes, content_type: str = "application/pdf"
    ) -> str:
        """Upload binary payload to private object storage.

        Args:
            object_key: Storage object key path.
            data: Binary payload bytes.
            content_type: MIME content type string.

        Returns:
            str: Verified object key path.
        """

    @abstractmethod
    async def get_object(self, object_key: str) -> bytes:
        """Retrieve binary payload from private object storage.

        Args:
            object_key: Storage object key path.

        Returns:
            bytes: Binary payload bytes.
        """

    @abstractmethod
    async def generate_presigned_url(self, object_key: str, expiration_seconds: int = 900) -> str:
        """Generate a short-lived presigned URL for authorized private access (default 15m).

        Args:
            object_key: Storage object key path.
            expiration_seconds: URL validity lifetime in seconds (default 900).

        Returns:
            str: Temporary presigned authorized URL string.
        """

    @abstractmethod
    async def generate_presigned_upload_url(
        self, object_key: str, content_type: str, expiration_seconds: int = 900
    ) -> dict[str, str]:
        """Generate a short-lived presigned upload URL or POST params for direct upload.

        Args:
            object_key: Storage object key path.
            content_type: MIME content type string.
            expiration_seconds: URL validity lifetime in seconds (default 900).

        Returns:
            dict[str, str]: Dictionary containing upload_url and parameters.
        """

    @abstractmethod
    async def object_exists(self, object_key: str) -> bool:
        """Check whether an object exists in private storage.

        Args:
            object_key: Storage object key path.

        Returns:
            bool: True if object exists, False otherwise.
        """

    @abstractmethod
    async def delete_object(self, object_key: str) -> bool:
        """Delete an object from private storage.

        Args:
            object_key: Storage object key path.

        Returns:
            bool: True if deleted or non-existent, False on error.
        """
