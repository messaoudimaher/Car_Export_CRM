"""WhatsApp Webhook & Outbound Processing Telemetry (Phase 2 Performance & Monitoring)."""

import time
from typing import Any
from pydantic import BaseModel, Field

from app.core.logging import logger


class WhatsAppTimingMetrics(BaseModel):
    """Performance timing metrics for a single WhatsApp inbound/outbound transaction (Phase 9)."""

    wamid: str = Field(..., description="Provider unique message identifier")
    tenant_id: str | None = Field(None, description="Tenant organization UUID")
    phone_e164: str | None = Field(None, description="Customer phone number")

    # Timestamps in monotonic fractional seconds
    t_webhook_received: float = Field(default_factory=time.perf_counter)
    t_persisted: float | None = None
    t_acknowledged: float | None = None
    t_worker_started: float | None = None
    t_db_read_started: float | None = None
    t_db_read_completed: float | None = None
    t_context_constructed: float | None = None
    t_llm_started: float | None = None
    t_llm_completed: float | None = None
    t_validation_completed: float | None = None
    t_db_write_started: float | None = None
    t_db_write_completed: float | None = None
    t_outbound_started: float | None = None
    t_outbound_completed: float | None = None

    def mark_persisted(self) -> None:
        """Record timestamp when DB pre-ACK persistence completed."""
        self.t_persisted = time.perf_counter()

    def mark_acknowledged(self) -> None:
        """Record timestamp when HTTP 200 response returned to Meta."""
        self.t_acknowledged = time.perf_counter()

    def mark_worker_started(self) -> None:
        """Record timestamp when background worker begins processing."""
        self.t_worker_started = time.perf_counter()

    def mark_db_read_started(self) -> None:
        """Record timestamp when database queries begin."""
        self.t_db_read_started = time.perf_counter()

    def mark_db_read_completed(self) -> None:
        """Record timestamp when database queries finish."""
        self.t_db_read_completed = time.perf_counter()

    def mark_context_constructed(self) -> None:
        """Record timestamp when system prompt and conversation memory formatting finish."""
        self.t_context_constructed = time.perf_counter()

    def mark_llm_started(self) -> None:
        """Record timestamp when LLM generation request starts."""
        self.t_llm_started = time.perf_counter()

    def mark_llm_completed(self) -> None:
        """Record timestamp when LLM generation request finishes."""
        self.t_llm_completed = time.perf_counter()

    def mark_validation_completed(self) -> None:
        """Record timestamp when Pydantic parsing and decision validation finish."""
        self.t_validation_completed = time.perf_counter()

    def mark_db_write_started(self) -> None:
        """Record timestamp when database transaction write begins."""
        self.t_db_write_started = time.perf_counter()

    def mark_db_write_completed(self) -> None:
        """Record timestamp when database transaction commit finishes."""
        self.t_db_write_completed = time.perf_counter()

    def mark_outbound_started(self) -> None:
        """Record timestamp when outbound API request starts."""
        self.t_outbound_started = time.perf_counter()

    def mark_outbound_completed(self) -> None:
        """Record timestamp when outbound API request finishes."""
        self.t_outbound_completed = time.perf_counter()

    def to_latency_report(self) -> dict[str, Any]:
        """Compute latency intervals in milliseconds across all lifecycle stages."""
        report: dict[str, Any] = {
            "wamid": self.wamid,
            "tenant_id": self.tenant_id,
            "phone_e164": self.phone_e164,
        }

        # 1. Meta Webhook & Ingress ACK
        if self.t_persisted is not None:
            report["db_persistence_ms"] = round((self.t_persisted - self.t_webhook_received) * 1000.0, 2)
        if self.t_acknowledged is not None:
            report["webhook_ack_ms"] = round((self.t_acknowledged - self.t_webhook_received) * 1000.0, 2)
        if self.t_worker_started is not None and self.t_acknowledged is not None:
            report["worker_queue_delay_ms"] = round((self.t_worker_started - self.t_acknowledged) * 1000.0, 2)

        # 2. Pipeline Execution Stages
        if self.t_db_read_started is not None and self.t_db_read_completed is not None:
            report["db_read_ms"] = round((self.t_db_read_completed - self.t_db_read_started) * 1000.0, 2)
        if self.t_db_read_completed is not None and self.t_context_constructed is not None:
            report["context_construction_ms"] = round((self.t_context_constructed - self.t_db_read_completed) * 1000.0, 2)
        if self.t_llm_started is not None and self.t_llm_completed is not None:
            report["gemini_latency_ms"] = round((self.t_llm_completed - self.t_llm_started) * 1000.0, 2)
        if self.t_llm_completed is not None and self.t_validation_completed is not None:
            report["validation_latency_ms"] = round((self.t_validation_completed - self.t_llm_completed) * 1000.0, 2)
        if self.t_db_write_started is not None and self.t_db_write_completed is not None:
            report["db_write_ms"] = round((self.t_db_write_completed - self.t_db_write_started) * 1000.0, 2)
        if self.t_outbound_started is not None and self.t_outbound_completed is not None:
            report["meta_outbound_ms"] = round((self.t_outbound_completed - self.t_outbound_started) * 1000.0, 2)

        # 3. Total End-to-End Latency
        end_time = self.t_outbound_completed or self.t_db_write_completed or time.perf_counter()
        report["total_end_to_end_ms"] = round((end_time - self.t_webhook_received) * 1000.0, 2)

        return report

    def log_summary(self) -> None:
        """Emit structured JSON log of the transaction latency breakdown."""
        metrics_dict = self.to_latency_report()
        logger.info("WHATSAPP_RESPONSE_LATENCY_REPORT", extra=metrics_dict)

