"""Unit and DB integration tests for extended Document model (WS-15, TASK-1501)."""

import uuid
from pathlib import Path

import pytest

from app.adapters.object_storage_local import LocalStorageAdapter
from app.core.database import check_database_health, get_db_session
from app.core.errors import ForbiddenException, ValidationException
from app.models.customer import Customer
from app.models.document import Document
from app.models.lead import Lead, LeadStatus
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.ports.object_storage import ObjectStorageProvider
from app.schemas.document import DocumentUploadInitRequest
from app.services.document_service import DocumentService


def test_object_key_path_traversal_guards() -> None:
    """Verify ObjectStorageProvider rejects path traversal key sequences."""
    with pytest.raises(ValidationException, match="Object key cannot be empty"):
        ObjectStorageProvider.validate_object_key("")

    with pytest.raises(ValidationException, match="Object key cannot start with a path separator"):
        ObjectStorageProvider.validate_object_key("/etc/passwd")

    with pytest.raises(ValidationException, match="Path traversal sequence prohibited"):
        ObjectStorageProvider.validate_object_key("tenants/../../etc/passwd")


@pytest.mark.asyncio
async def test_local_storage_adapter_contract(tmp_path: Path) -> None:
    """Verify LocalStorageAdapter upload, get, presigned URLs, and delete operations."""
    adapter = LocalStorageAdapter(base_dir=tmp_path)
    object_key = "tenants/test_tenant/docs/doc123/carte_grise.pdf"
    content = b"%PDF-1.4 Carte Grise Test Content"

    # Upload object
    uploaded_key = await adapter.upload_object(object_key=object_key, data=content)
    assert uploaded_key == object_key
    assert await adapter.object_exists(object_key) is True

    # Get object
    data = await adapter.get_object(object_key)
    assert data == content

    # Presigned URL generation
    download_url = await adapter.generate_presigned_url(object_key, expiration_seconds=900)
    assert "file:///" in download_url
    assert "expires_in=900" in download_url

    upload_info = await adapter.generate_presigned_upload_url(
        object_key=object_key, content_type="application/pdf", expiration_seconds=900
    )
    assert upload_info["key"] == object_key
    assert upload_info["expires_in_seconds"] == "900"

    # Delete object
    deleted = await adapter.delete_object(object_key)
    assert deleted is True
    assert await adapter.object_exists(object_key) is False


@pytest.mark.asyncio
async def test_document_service_upload_initiate_and_complete_flow(tmp_path: Path) -> None:
    """Test full document upload initiation, completion verification, and status transitions."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database unavailable for integration test.")

    adapter = LocalStorageAdapter(base_dir=tmp_path)

    async for session in get_db_session():
        tenant = Tenant(
            name=f"Doc Org {uuid.uuid4().hex[:6]}",
            slug=f"doc-{uuid.uuid4().hex[:6]}",
        )
        session.add(tenant)
        await session.flush()

        user = User(
            tenant_id=tenant.id,
            email=f"uploader-{uuid.uuid4().hex[:6]}@example.com",
            hashed_password="hash",  # noqa: S106
            full_name="Doc Uploader",
            role=UserRole.SALES_AGENT.value,
        )
        session.add(user)
        await session.flush()

        customer = Customer(
            tenant_id=tenant.id,
            first_name="Mehdi",
            last_name="Trabelsi",
            phone_e164=f"+21698{uuid.uuid4().int % 1000000:06d}",
        )
        session.add(customer)
        await session.flush()

        lead = Lead(
            tenant_id=tenant.id,
            customer_id=customer.id,
            status=LeadStatus.NEW.value,
        )
        session.add(lead)
        await session.commit()

        service = DocumentService(session=session, storage_provider=adapter)

        # 1. Initiate upload
        init_payload = DocumentUploadInitRequest(
            file_name="carte_grise_golf7.pdf",
            mime_type="application/pdf",
            file_size_bytes=2048,
            category="Carte_Grise",
            lead_id=lead.id,
            customer_id=customer.id,
        )

        doc, upload_info = await service.initiate_upload(
            tenant_id=tenant.id,
            uploader_id=user.id,
            payload=init_payload,
        )

        assert doc.id is not None
        assert doc.status == "Pending"
        assert doc.scan_status == "Pending"
        assert doc.category == "Carte_Grise"
        assert f"tenants/{tenant.id}/docs/{doc.id}/carte_grise_golf7.pdf" in doc.object_key

        # Accessing download URL when status is Pending must be rejected
        with pytest.raises(ForbiddenException, match="Document access denied"):
            await service.get_document_access_url(
                tenant_id=tenant.id, document_id=doc.id, requesting_user=user
            )

        # 2. Completing upload without putting object in storage must fail and quarantine
        with pytest.raises(ValidationException, match="Uploaded object file not found in storage"):
            await service.complete_upload(tenant_id=tenant.id, document_id=doc.id)

        # Confirm document transitions to Quarantined
        doc_quarantined = await session.get(Document, doc.id)
        assert doc_quarantined is not None
        assert doc_quarantined.status == "Quarantined"

        # 3. Simulate client writing file to storage and completing upload
        await adapter.upload_object(doc.object_key, b"%PDF-1.4 Fake Carte Grise")
        completed_doc = await service.complete_upload(
            tenant_id=tenant.id,
            document_id=doc.id,
            sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )

        # In secure mode, complete_upload leaves status Pending until scan worker completes
        assert completed_doc.status == "Pending"
        assert completed_doc.scan_status == "Pending"
        assert (
            completed_doc.sha256_hash
            == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

        # 4. Controlled scan result process marks document Passed & Available
        scanned_doc = await service.process_scan_result(
            tenant_id=tenant.id,
            document_id=doc.id,
            scan_passed=True,
            scanner_info="ClamAV/v1.0",
        )

        assert scanned_doc.status == "Available"
        assert scanned_doc.scan_status == "Passed"
        assert scanned_doc.scan_details is not None
        assert scanned_doc.scan_details["scan_passed"] is True

        # 5. Authorized download access
        accessed_doc, download_url = await service.get_document_access_url(
            tenant_id=tenant.id, document_id=doc.id, requesting_user=user
        )
        assert accessed_doc.id == doc.id
        assert "expires_in=900" in download_url

        # 6. Cross-tenant access rejection
        other_tenant_user = User(
            tenant_id=uuid.uuid4(),
            email=f"other-{uuid.uuid4().hex[:6]}@example.com",
            hashed_password="hash",  # noqa: S106
            full_name="Other Agent",
            role=UserRole.SALES_AGENT.value,
        )

        with pytest.raises(ForbiddenException):
            await service.get_document_access_url(
                tenant_id=tenant.id, document_id=doc.id, requesting_user=other_tenant_user
            )

        # 7. Delete document
        deleted = await service.delete_document(tenant_id=tenant.id, document_id=doc.id)
        assert deleted is True

        doc_deleted = await session.get(Document, doc.id)
        assert doc_deleted is not None
        assert doc_deleted.status == "Deleted"

        break
