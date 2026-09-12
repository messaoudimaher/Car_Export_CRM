"""Integration tests for ObjectStorageProvider adapters & path traversal security (TASK-1003)."""

from pathlib import Path

import pytest

from app.adapters.object_storage_local import LocalStorageAdapter
from app.core.errors import NotFoundException, ValidationException
from app.ports.object_storage import ObjectStorageProvider


def test_object_storage_provider_path_traversal_validation() -> None:
    """Verify validate_object_key blocks path traversal and leading slashes."""
    # Valid object keys
    ObjectStorageProvider.validate_object_key("tenants/123/quotes/456/v1.pdf")
    ObjectStorageProvider.validate_object_key("documents/archive/doc1.pdf")

    # Invalid object keys (path traversal or leading slash)
    with pytest.raises(ValidationException, match="cannot be empty"):
        ObjectStorageProvider.validate_object_key("")

    with pytest.raises(ValidationException, match="cannot start with a path separator"):
        ObjectStorageProvider.validate_object_key("/etc/passwd")

    with pytest.raises(ValidationException, match="cannot start with a path separator"):
        ObjectStorageProvider.validate_object_key("\\Windows\\System32")

    with pytest.raises(ValidationException, match="Path traversal sequence prohibited"):
        ObjectStorageProvider.validate_object_key("tenants/123/../../etc/passwd")

    with pytest.raises(ValidationException, match="Path traversal sequence prohibited"):
        ObjectStorageProvider.validate_object_key("tenants/123/./quotes/doc.pdf")


@pytest.mark.asyncio
async def test_local_storage_adapter_lifecycle(tmp_path: Path) -> None:
    """Verify LocalStorageAdapter upload, retrieval, presigned URL, and deletion."""
    adapter = LocalStorageAdapter(base_dir=tmp_path)
    object_key = "tenants/test-tenant-id/quotes/quote-123/v1.pdf"
    data = b"%PDF-1.4 Mock Binary Content for Testing"

    # 1. Upload Object
    uploaded_key = await adapter.upload_object(object_key, data)
    assert uploaded_key == object_key

    # 2. Get Object
    retrieved_data = await adapter.get_object(object_key)
    assert retrieved_data == data

    # 3. Presigned URL Simulation
    presigned_url = await adapter.generate_presigned_url(object_key)
    assert presigned_url.startswith("file:///")

    # 4. Delete Object
    deleted = await adapter.delete_object(object_key)
    assert deleted is True

    # 5. Get Object after deletion raises NotFoundException
    with pytest.raises(NotFoundException, match="not found in local storage"):
        await adapter.get_object(object_key)
