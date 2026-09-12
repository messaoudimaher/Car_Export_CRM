"""Document Service orchestrating PDF generation, private storage & RBAC (WS-10, TASK-1003)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters.object_storage_local import LocalStorageAdapter
from app.adapters.object_storage_s3 import S3StorageAdapter
from app.core.config import settings
from app.core.errors import ForbiddenException, NotFoundException, ValidationException
from app.core.logging import get_logger
from app.models.document import Document
from app.models.lead import Lead
from app.models.quotation import Quotation
from app.models.user import User
from app.ports.object_storage import ObjectStorageProvider
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
            object_key=uploaded_key,
            file_name=file_name,
            file_size_bytes=file_size_bytes,
            mime_type="application/pdf",
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
        requesting_user: User,
        expiration_seconds: int = 3600,
    ) -> tuple[Document, str]:
        """Authorize user access and generate a presigned temporary download URL."""
        if requesting_user.tenant_id != tenant_id:
            raise ForbiddenException("User cannot access documents outside tenant organization")

        stmt = select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            raise NotFoundException(f"Document '{document_id}' not found")

        url = await self.storage_provider.generate_presigned_url(
            object_key=doc.object_key,
            expiration_seconds=expiration_seconds,
        )

        logger.info(
            "QUOTE_PDF_ACCESS_GRANTED: Presigned URL generated",
            extra={
                "tenant_id": str(tenant_id),
                "document_id": str(document_id),
                "user_id": str(requesting_user.id),
            },
        )
        return doc, url
