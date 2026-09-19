"""Deterministic CSV Export Service for Qualified Vehicle Requests (Phase 6 & Phase 7).

PostgreSQL is the single authoritative source of truth.
This service ensures:
1. ONLY qualified vehicle requests (status == 'QUALIFIED' and confirmed_at is not None) are exported.
2. UTF-8 (with BOM) encoding preserving Arabic, French, and special characters.
3. Stable column order.
4. Idempotent incremental updates.
5. 100% database regenerability on demand from PostgreSQL.
"""

import csv
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import logger
from app.models.customer import Customer
from app.models.vehicle_request import VehicleRequest, VehicleRequestStatus

# Stable deterministic column order
CSV_FIELDNAMES = [
    "request_id",
    "tenant_id",
    "customer_id",
    "customer_phone",
    "customer_name",
    "make",
    "model",
    "year",
    "fuel_type",
    "transmission",
    "budget_eur",
    "destination_port",
    "fcr_compatible",
    "additional_requirements",
    "confirmed_at",
    "status",
]


class CSVExportService:
    """Manages deterministic CSV exports for qualified vehicle requests."""

    def __init__(self, export_dir: str | Path | None = None) -> None:
        self.export_dir = Path(export_dir or settings.CSV_EXPORT_DIRECTORY)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def get_csv_path(self, tenant_id: uuid.UUID | str | None = None) -> Path:
        """Return tenant-scoped or global CSV export filepath."""
        if tenant_id:
            return self.export_dir / f"qualified_leads_{tenant_id}.csv"
        return self.export_dir / "qualified_leads.csv"

    def export_qualified_request(
        self,
        request_id: uuid.UUID | str,
        tenant_id: uuid.UUID | str,
        customer_id: uuid.UUID | str,
        customer_phone: str,
        customer_name: str | None,
        make: str,
        model: str,
        year: int | None,
        fuel_type: str | None,
        transmission: str | None,
        budget_eur: float | None,
        destination_port: str,
        fcr_compatible: bool,
        additional_requirements: str | None,
        confirmed_at: datetime | None,
        status: str = "QUALIFIED",
    ) -> Path:
        """Idempotently export or update a qualified vehicle request record in the CSV file."""
        # Non-negotiable: only qualified requests may be exported to the qualified CSV output
        if status != VehicleRequestStatus.QUALIFIED or confirmed_at is None:
            raise ValueError(f"Cannot export non-qualified request '{request_id}' with status '{status}' to qualified output.")

        req_id_str = str(request_id)
        file_path = self.get_csv_path(tenant_id)

        rows: list[dict[str, Any]] = []
        found = False

        if file_path.exists():
            with open(file_path, mode="r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    if r.get("request_id") == req_id_str:
                        found = True
                        r.update({
                            "customer_phone": customer_phone,
                            "customer_name": customer_name or "",
                            "make": make,
                            "model": model,
                            "year": str(year or ""),
                            "fuel_type": fuel_type or "",
                            "transmission": transmission or "",
                            "budget_eur": f"{budget_eur:.2f}" if budget_eur is not None else "",
                            "destination_port": destination_port,
                            "fcr_compatible": "true" if fcr_compatible else "false",
                            "additional_requirements": additional_requirements or "",
                            "confirmed_at": confirmed_at.isoformat() if confirmed_at else datetime.now(UTC).isoformat(),
                            "status": status,
                        })
                    rows.append(r)

        if not found:
            rows.append({
                "request_id": req_id_str,
                "tenant_id": str(tenant_id),
                "customer_id": str(customer_id),
                "customer_phone": customer_phone,
                "customer_name": customer_name or "",
                "make": make,
                "model": model,
                "year": str(year or ""),
                "fuel_type": fuel_type or "",
                "transmission": transmission or "",
                "budget_eur": f"{budget_eur:.2f}" if budget_eur is not None else "",
                "destination_port": destination_port,
                "fcr_compatible": "true" if fcr_compatible else "false",
                "additional_requirements": additional_requirements or "",
                "confirmed_at": confirmed_at.isoformat() if confirmed_at else datetime.now(UTC).isoformat(),
                "status": status,
            })

        # Deterministic sort by confirmed_at ascending, request_id ascending
        rows.sort(key=lambda r: (r.get("confirmed_at", ""), r.get("request_id", "")))

        # Atomic file write with UTF-8 BOM encoding for universal Excel/spreadsheet compatibility
        tmp_path = file_path.with_suffix(".tmp")
        with open(tmp_path, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)

        os.replace(tmp_path, file_path)

        logger.info(
            "CSV_QUALIFIED_LEAD_EXPORTED",
            extra={
                "request_id": req_id_str,
                "tenant_id": str(tenant_id),
                "csv_path": str(file_path),
                "total_rows": len(rows),
            },
        )
        return file_path

    async def regenerate_csv_from_db(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID | str | None = None,
    ) -> Path:
        """Regenerate the complete CSV export file deterministically from PostgreSQL authoritative records."""
        stmt = (
            select(VehicleRequest)
            .options(selectinload(VehicleRequest.customer))
            .where(
                VehicleRequest.status == VehicleRequestStatus.QUALIFIED,
                VehicleRequest.confirmed_at.isnot(None),
            )
        )
        if tenant_id:
            tid = uuid.UUID(str(tenant_id)) if isinstance(tenant_id, str) else tenant_id
            stmt = stmt.where(VehicleRequest.tenant_id == tid)

        stmt = stmt.order_by(VehicleRequest.confirmed_at.asc(), VehicleRequest.id.asc())
        records = list((await db.execute(stmt)).scalars().all())

        file_path = self.get_csv_path(tenant_id)
        rows: list[dict[str, Any]] = []

        for vreq in records:
            cust_phone = vreq.customer.phone_e164 if vreq.customer else ""
            cust_name = vreq.customer.full_name or vreq.customer.first_name if vreq.customer else ""

            rows.append({
                "request_id": str(vreq.id),
                "tenant_id": str(vreq.tenant_id),
                "customer_id": str(vreq.customer_id),
                "customer_phone": cust_phone,
                "customer_name": cust_name or "",
                "make": vreq.make,
                "model": vreq.model,
                "year": str(vreq.min_year or ""),
                "fuel_type": vreq.fuel_type or "",
                "transmission": vreq.transmission or "",
                "budget_eur": f"{float(vreq.budget_eur):.2f}" if vreq.budget_eur is not None else "",
                "destination_port": vreq.destination_port,
                "fcr_compatible": "true" if vreq.fcr_compatible else "false",
                "additional_requirements": vreq.additional_requirements or "",
                "confirmed_at": vreq.confirmed_at.isoformat() if vreq.confirmed_at else "",
                "status": vreq.status,
            })

        tmp_path = file_path.with_suffix(".tmp")
        with open(tmp_path, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)

        os.replace(tmp_path, file_path)

        logger.info(
            "CSV_REGENERATED_FROM_DATABASE",
            extra={
                "tenant_id": str(tenant_id) if tenant_id else "global",
                "csv_path": str(file_path),
                "total_rows": len(rows),
            },
        )
        return file_path


# Global singleton instance
csv_export_service = CSVExportService()
