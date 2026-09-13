"""Document Management REST API & Pre-signed URL Flow (WS-15, TASK-1502)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CurrentUser,
    get_current_tenant_id,
    get_current_user,
    require_roles,
)
from app.core.database import get_db_session
from app.core.errors import ValidationException
from app.models.user import User, UserRole
from app.schemas.document import (
    DocumentAccessResponse,
    DocumentResponse,
    DocumentScanResultRequest,
    DocumentUploadCompleteRequest,
    DocumentUploadInitRequest,
    DocumentUploadInitResponse,
)
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
}


@router.post(
    "/upload-url",
    response_model=DocumentUploadInitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize Document Upload Session & Pre-signed URL",
)
async def initiate_document_upload(
    payload: DocumentUploadInitRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentUploadInitResponse:
    """Validate file metadata and issue a server-side object key and pre-signed upload URL."""
    if payload.mime_type.lower() not in ALLOWED_MIME_TYPES:
        raise ValidationException(
            f"Unsupported MIME type '{payload.mime_type}'. "
            f"Allowed types: {', '.join(sorted(ALLOWED_MIME_TYPES))}"
        )

    service = DocumentService(session=session)
    doc, upload_info = await service.initiate_upload(
        tenant_id=tenant_id,
        uploader_id=current_user.user_id,
        payload=payload,
    )

    return DocumentUploadInitResponse(
        document_id=doc.id,
        object_key=doc.object_key,
        upload_url=upload_info["upload_url"],
        upload_fields={},
        expires_in_seconds=int(upload_info.get("expires_in_seconds", "900")),
    )


@router.post(
    "/{document_id}/complete",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete Document Upload Verification",
)
async def complete_document_upload(
    document_id: UUID,
    payload: DocumentUploadCompleteRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentResponse:
    """Verify uploaded object on storage and register document completion."""
    service = DocumentService(session=session)
    doc = await service.complete_upload(
        tenant_id=tenant_id,
        document_id=document_id,
        sha256_hash=payload.sha256_hash,
    )
    return DocumentResponse.model_validate(doc)


@router.post(
    "/{document_id}/scan-result",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Process Security Scan Result for Document",
)
async def process_document_scan_result(
    document_id: UUID,
    payload: DocumentScanResultRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    _: User = Depends(require_roles(UserRole.TENANT_ADMIN, UserRole.SUPER_ADMIN)),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentResponse:
    """Record security scan result, marking document Passed/Available or Quarantined."""
    service = DocumentService(session=session)
    doc = await service.process_scan_result(
        tenant_id=tenant_id,
        document_id=document_id,
        scan_passed=payload.scan_passed,
        scanner_info=payload.scanner_info,
        failure_reason=payload.failure_reason,
    )
    return DocumentResponse.model_validate(doc)


@router.get(
    "",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="List Tenant Document Metadata Records",
)
async def list_documents(
    lead_id: UUID | None = Query(default=None, description="Filter by sales lead UUID"),
    customer_id: UUID | None = Query(default=None, description="Filter by customer UUID"),
    category: str | None = Query(default=None, description="Filter by category"),
    status: str | None = Query(default=None, description="Filter by status (Available, Pending)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[DocumentResponse]:
    """Retrieve document metadata list under tenant scope (SEC-007)."""
    service = DocumentService(session=session)
    docs = await service.list_documents(
        tenant_id=tenant_id,
        lead_id=lead_id,
        customer_id=customer_id,
        category=category,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [DocumentResponse.model_validate(doc) for doc in docs]


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Document Metadata Record by ID",
)
async def get_document_by_id(
    document_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentResponse:
    """Retrieve single document metadata record under tenant context (SEC-007)."""
    service = DocumentService(session=session)
    doc = await service.get_document_by_id(tenant_id=tenant_id, document_id=document_id)
    return DocumentResponse.model_validate(doc)


@router.get(
    "/{document_id}/download-url",
    response_model=DocumentAccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Authorized Pre-signed Download URL",
)
async def get_document_download_url(
    document_id: UUID,
    expiration_seconds: int = Query(default=900, ge=60, le=3600),
    tenant_id: UUID = Depends(get_current_tenant_id),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentAccessResponse:
    """Authorize access and generate a 15-minute temporary presigned download URL."""
    service = DocumentService(session=session)
    doc, access_url = await service.get_document_access_url(
        tenant_id=tenant_id,
        document_id=document_id,
        requesting_user=current_user,
        expiration_seconds=expiration_seconds,
    )
    return DocumentAccessResponse(
        document=DocumentResponse.model_validate(doc),
        access_url=access_url,
        expires_in_seconds=expiration_seconds,
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Document",
)
async def delete_document(
    document_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    _: User = Depends(require_roles(UserRole.TENANT_ADMIN, UserRole.SUPER_ADMIN)),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Delete document object from storage and mark metadata as Deleted under tenant scope."""
    service = DocumentService(session=session)
    await service.delete_document(tenant_id=tenant_id, document_id=document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
