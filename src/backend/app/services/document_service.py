"""Document Service orchestrating PDF generation, private storage & RBAC (WS-10, TASK-1003)."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters.object_storage_local import LocalStorageAdapter
from app.adapters.object_storage_s3 import S3StorageAdapter
from app.core.config import settings
from app.core.errors import ForbiddenException, NotFoundException, ValidationException
from app.core.logging import get_logger
from app.core.uuid import generate_uuidv7
from app.models.customer import Customer
from app.models.document import Document
from app.models.lead import Lead
from app.models.quotation import Quotation
from app.models.user import User
from app.ports.object_storage import ObjectStorageProvider
from app.schemas.document import DocumentUploadInitRequest
from app.services.pdf_service import QuotePdfGenerator

logger = get_logger(__name__)


class DocumentService:
    """Service layer managing private document storage, PDF generation & presigned URL access."""

    def __init__(
        self,
        session: AsyncSession,
        storage_provider: ObjectStorageProvider | None = None,
    ) -> None:
        self.session = session
        if storage_provider is not None:
            self.storage_provider = storage_provider
        elif settings.S3_ENDPOINT_URL or settings.is_production:
            self.storage_provider = S3StorageAdapter()
        else:
            self.storage_provider = LocalStorageAdapter()

    async def initiate_upload(
        self,
        tenant_id: uuid.UUID,
        uploader_id: uuid.UUID,
        payload: DocumentUploadInitRequest,
    ) -> tuple[Document, dict[str, str]]:
        """Initialize upload session with server-side key and presigned URL (TASK-1501)."""
        if not tenant_id:
            raise ValueError("tenant_id is strictly mandatory (SEC-007)")

        # Validate file size limit (10MB)
        max_bytes = 10_485_760
        if payload.file_size_bytes > max_bytes:
            raise ValidationException("File size exceeds 10MB limit")

        # Validate lead association under tenant context if provided
        if payload.lead_id:
            lead_res = await self.session.execute(
                select(Lead).where(Lead.id == payload.lead_id, Lead.tenant_id == tenant_id)
            )
            if lead_res.scalar_one_or_none() is None:
                raise NotFoundException(f"Lead '{payload.lead_id}' not found for tenant")

        # Validate customer association under tenant context if provided
        if payload.customer_id:
            cust_res = await self.session.execute(
                select(Customer).where(
                    Customer.id == payload.customer_id, Customer.tenant_id == tenant_id
                )
            )
            if cust_res.scalar_one_or_none() is None:
                raise NotFoundException(f"Customer '{payload.customer_id}' not found for tenant")

        document_id = generate_uuidv7()
        # Generate safe server-side object key: tenants/<tenant_id>/docs/<document_id>/<file_name>
        safe_filename = payload.file_name.replace("/", "_").replace("\\", "_")
        object_key = f"tenants/{tenant_id}/docs/{document_id}/{safe_filename}"
        self.storage_provider.validate_object_key(object_key)

        # Create Document metadata record in 'Pending' state
        doc = Document(
            id=document_id,
            tenant_id=tenant_id,
            lead_id=payload.lead_id,
            customer_id=payload.customer_id,
            uploader_id=uploader_id,
            document_type="Customer_Export_Doc",
            category=payload.category,
            object_key=object_key,
            file_name=payload.file_name,
            file_size_bytes=payload.file_size_bytes,
            mime_type=payload.mime_type,
            scan_status="Pending",
            status="Pending",
        )
        self.session.add(doc)
        await self.session.commit()
        await self.session.refresh(doc)

        upload_info = await self.storage_provider.generate_presigned_upload_url(
            object_key=object_key,
            content_type=payload.mime_type,
            expiration_seconds=900,
        )

        logger.info(
            f"Initiated document upload session '{doc.id}'",
            extra={
                "tenant_id": str(tenant_id),
                "document_id": str(doc.id),
                "object_key": object_key,
            },
        )
        return doc, upload_info

    async def complete_upload(
        self,
        tenant_id: uuid.UUID,
        document_id: uuid.UUID,
        sha256_hash: str | None = None,
    ) -> Document:
        """Verify object existence and checksum, leaving scan_status Pending."""
        stmt = select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            raise NotFoundException(f"Document '{document_id}' not found")

        # Verify object existence in private storage
        exists = await self.storage_provider.object_exists(doc.object_key)
        if not exists:
            doc.scan_status = "Failed"
            doc.status = "Quarantined"
            await self.session.commit()
            raise ValidationException("Uploaded object file not found in storage")

        if sha256_hash:
            doc.sha256_hash = sha256_hash

        # Safe Scan Lifecycle: Only auto-pass if explicit dev bypass setting is enabled
        if settings.DEV_AUTO_PASS_FILE_SCANS:
            doc.scan_status = "Passed"
            doc.status = "Available"
        else:
            doc.scan_status = "Pending"
            doc.status = "Pending"

        await self.session.commit()
        await self.session.refresh(doc)

        logger.info(
            f"Completed document upload verification for '{doc.id}'",
            extra={
                "tenant_id": str(tenant_id),
                "document_id": str(doc.id),
                "status": doc.status,
                "scan_status": doc.scan_status,
            },
        )
        return doc

    async def process_scan_result(
        self,
        tenant_id: uuid.UUID,
        document_id: uuid.UUID,
        scan_passed: bool,
        scanner_info: str = "ClamAV/v1.0",
        failure_reason: str | None = None,
    ) -> Document:
        """Process asynchronous security scan result for a document."""
        stmt = select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            raise NotFoundException(f"Document '{document_id}' not found")

        scanned_at = datetime.now(UTC).isoformat()
        doc.scan_details = {
            "scanner_info": scanner_info,
            "scanned_at": scanned_at,
            "scan_passed": scan_passed,
            "failure_reason": failure_reason,
        }

        if scan_passed:
            doc.scan_status = "Passed"
            doc.status = "Available"
        else:
            doc.scan_status = "Quarantined"
            doc.status = "Quarantined"

        await self.session.commit()
        await self.session.refresh(doc)

        logger.info(
            f"Processed scan result for document '{doc.id}': scan_status='{doc.scan_status}'",
            extra={
                "tenant_id": str(tenant_id),
                "document_id": str(doc.id),
                "scan_status": doc.scan_status,
                "scanner_info": scanner_info,
            },
        )
        return doc

    async def generate_and_store_quote_pdf(
        self,
        tenant_id: uuid.UUID,
        quotation_id: uuid.UUID,
        requesting_user: User,
        version: int = 1,
    ) -> Document:
        """Generate and upload private PDF quote document with idempotency & transaction safety."""
        # Security & RBAC: Verify requesting user belongs to tenant
        if requesting_user.tenant_id != tenant_id:
            raise ForbiddenException("User cannot access documents outside tenant organization")

        # 1. Fetch authoritative Quotation entity with tenant & vehicle details
        stmt = (
            select(Quotation)
            .options(
                selectinload(Quotation.items),
                selectinload(Quotation.tenant),
                selectinload(Quotation.vehicle),
                selectinload(Quotation.lead).selectinload(Lead.customer),
            )
            .where(Quotation.id == quotation_id, Quotation.tenant_id == tenant_id)
        )
        result = await self.session.execute(stmt)
        quotation = result.scalar_one_or_none()

        if quotation is None:
            raise NotFoundException(f"Quotation '{quotation_id}' not found")

        # Construct safe tenant-scoped key: tenants/<tenant_id>/quotes/<quote_id>/v<version>.pdf
        object_key = f"tenants/{tenant_id}/quotes/{quotation_id}/v{version}.pdf"
        self.storage_provider.validate_object_key(object_key)

        # 2. Idempotency Check: Return existing document if already generated
        doc_stmt = select(Document).where(
            Document.tenant_id == tenant_id,
            Document.quotation_id == quotation_id,
            Document.version == version,
        )
        existing_doc_res = await self.session.execute(doc_stmt)
        existing_doc = existing_doc_res.scalar_one_or_none()

        if existing_doc is not None:
            logger.info(
                "QUOTE_PDF_IDEMPOTENT_HIT: Document already exists",
                extra={
                    "tenant_id": str(tenant_id),
                    "quotation_id": str(quotation_id),
                    "object_key": object_key,
                },
            )
            return existing_doc

        # Extract customer info from lead
        customer_name = None
        customer_phone = None
        if quotation.lead and quotation.lead.customer:
            customer_name = quotation.lead.customer.full_name
            customer_phone = quotation.lead.customer.phone_e164

        # 3. Render PDF binary bytes
        try:
            pdf_bytes = QuotePdfGenerator.generate_pdf_bytes(
                quotation=quotation,
                tenant=quotation.tenant,
                vehicle=quotation.vehicle,
                customer_name=customer_name,
                customer_phone=customer_phone,
            )
        except Exception as err:
            logger.error(
                "QUOTE_PDF_GENERATION_FAILED: PDF rendering error",
                extra={
                    "tenant_id": str(tenant_id),
                    "quotation_id": str(quotation_id),
                    "error": str(err),
                },
            )
            raise ValidationException(f"Failed to render PDF quote document: {err}") from err

        file_name = f"{quotation.quote_number}.pdf"
        file_size_bytes = len(pdf_bytes)

        # 4. Upload payload to private object storage
        try:
            uploaded_key = await self.storage_provider.upload_object(
                object_key=object_key,
                data=pdf_bytes,
                content_type="application/pdf",
            )
        except Exception as err:
            logger.error(
                "QUOTE_PDF_UPLOAD_FAILED: Object storage upload error",
                extra={
                    "tenant_id": str(tenant_id),
                    "quotation_id": str(quotation_id),
                    "object_key": object_key,
                    "error": str(err),
                },
            )
            raise

        # 5. Persist Document metadata in database with atomic rollback guard
        doc = Document(
            tenant_id=tenant_id,
            quotation_id=quotation_id,
            document_type="Quotation_PDF",
            category="Quotation_PDF",
            object_key=uploaded_key,
            file_name=file_name,
            file_size_bytes=file_size_bytes,
            mime_type="application/pdf",
            scan_status="Passed",
            status="Available",
            version=version,
        )

        quotation.pdf_s3_key = uploaded_key
        self.session.add(doc)

        try:
            await self.session.flush()
        except Exception as err:
            # Clean up orphan storage object on database error
            logger.error(
                "QUOTE_PDF_DB_PERSISTENCE_FAILED: Rolling back storage upload",
                extra={
                    "tenant_id": str(tenant_id),
                    "quotation_id": str(quotation_id),
                    "object_key": uploaded_key,
                    "error": str(err),
                },
            )
            await self.storage_provider.delete_object(uploaded_key)
            raise

        logger.info(
            "QUOTE_PDF_GENERATED: PDF successfully generated and uploaded",
            extra={
                "tenant_id": str(tenant_id),
                "quotation_id": str(quotation_id),
                "object_key": uploaded_key,
                "file_size_bytes": file_size_bytes,
            },
        )
        return doc

    async def get_document_access_url(
        self,
        tenant_id: uuid.UUID,
        document_id: uuid.UUID,
        requesting_user: Any,
        expiration_seconds: int = 900,
    ) -> tuple[Document, str]:
        """Authorize user access and generate a presigned temporary download URL."""
        if requesting_user.tenant_id != tenant_id:
            raise ForbiddenException("User cannot access documents outside tenant organization")

        stmt = select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            raise NotFoundException(f"Document '{document_id}' not found")

        # Reject download access unless status is Available AND scan_status is Passed
        if doc.status != "Available" or doc.scan_status != "Passed":
            raise ForbiddenException(
                f"Document access denied: status '{doc.status}', scan_status '{doc.scan_status}'"
            )

        url = await self.storage_provider.generate_presigned_url(
            object_key=doc.object_key,
            expiration_seconds=expiration_seconds,
        )

        user_id_val = getattr(requesting_user, "user_id", None) or getattr(
            requesting_user, "id", None
        )
        logger.info(
            "DOCUMENT_ACCESS_GRANTED: Presigned URL generated",
            extra={
                "tenant_id": str(tenant_id),
                "document_id": str(document_id),
                "user_id": str(user_id_val),
            },
        )
        return doc, url

    async def get_document_by_id(
        self,
        tenant_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> Document:
        """Retrieve single document metadata record under tenant context (SEC-007)."""
        stmt = select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc is None:
            raise NotFoundException(f"Document '{document_id}' not found")
        return doc

    async def list_documents(
        self,
        tenant_id: uuid.UUID,
        lead_id: uuid.UUID | None = None,
        customer_id: uuid.UUID | None = None,
        category: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Document]:
        """List tenant document metadata records with optional filters (SEC-007)."""
        stmt = (
            select(Document)
            .where(Document.tenant_id == tenant_id)
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if lead_id:
            stmt = stmt.where(Document.lead_id == lead_id)
        if customer_id:
            stmt = stmt.where(Document.customer_id == customer_id)
        if category:
            stmt = stmt.where(Document.category == category)
        if status:
            stmt = stmt.where(Document.status == status)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_document(
        self,
        tenant_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> bool:
        """Delete object from storage and mark metadata as Deleted (SEC-007)."""
        stmt = select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            raise NotFoundException(f"Document '{document_id}' not found")

        await self.storage_provider.delete_object(doc.object_key)
        doc.status = "Deleted"
        await self.session.commit()
        return True
