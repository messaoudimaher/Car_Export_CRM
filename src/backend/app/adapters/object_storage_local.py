"""Local Filesystem ObjectStorageProvider Adapter (Zero-AWS Credentials for Dev & Testing)."""

from pathlib import Path

from app.core.errors import NotFoundException
from app.ports.object_storage import ObjectStorageProvider


class LocalStorageAdapter(ObjectStorageProvider):
    """Local filesystem implementation of ObjectStorageProvider.

    Allows local development and automated tests to run cleanly without AWS accounts,
    AWS credentials, or paid third-party cloud services.
    """

    def __init__(self, base_dir: Path | str = "storage") -> None:
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, object_key: str) -> Path:
        """Validate key and resolve absolute filesystem path safely."""
        self.validate_object_key(object_key)
        target_path = (self.base_dir / object_key.replace("\\", "/")).resolve()
        # Verify target_path is inside base_dir to prevent path traversal
        if not str(target_path).startswith(str(self.base_dir)):
            raise NotFoundException("Invalid object key path")
        return target_path

    async def upload_object(
        self, object_key: str, data: bytes, content_type: str = "application/pdf"
    ) -> str:
        """Save binary payload to local storage directory."""
        path = self._resolve_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return object_key

    async def get_object(self, object_key: str) -> bytes:
        """Retrieve binary payload from local storage directory."""
        path = self._resolve_path(object_key)
        if not path.is_file():
            raise NotFoundException(f"Object '{object_key}' not found in local storage")
        return path.read_bytes()

    async def generate_presigned_url(self, object_key: str, expiration_seconds: int = 900) -> str:
        """Generate a simulated local access URL for authorized object viewing."""
        path = self._resolve_path(object_key)
        if not path.is_file():
            raise NotFoundException(f"Object '{object_key}' not found in local storage")
        return f"file:///{path.as_posix()}?expires_in={expiration_seconds}"

    async def generate_presigned_upload_url(
        self, object_key: str, content_type: str, expiration_seconds: int = 900
    ) -> dict[str, str]:
        """Generate a simulated local upload target parameters dict for dev/testing."""
        path = self._resolve_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        return {
            "upload_url": f"http://localhost:8000/api/v1/documents/upload-local?key={object_key}",
            "key": object_key,
            "content_type": content_type,
            "expires_in_seconds": str(expiration_seconds),
        }

    async def object_exists(self, object_key: str) -> bool:
        """Check if object file exists on local storage."""
        try:
            path = self._resolve_path(object_key)
            return path.is_file()
        except NotFoundException:
            return False

    async def delete_object(self, object_key: str) -> bool:
        """Delete file from local storage directory."""
        try:
            path = self._resolve_path(object_key)
            if path.is_file():
                path.unlink()
                return True
            return False
        except NotFoundException:
            return False
