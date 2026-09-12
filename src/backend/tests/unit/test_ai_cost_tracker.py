"""Unit tests for AI Token Usage & Cost Metric Tracking Service (TASK-1103)."""

import pytest

from app.core.logging import set_tenant_id
from app.services.ai_cost_tracker import AICostTracker


def test_calculate_cost_gpt_4o_mini() -> None:
    # gpt-4o-mini: prompt $0.15/1M, completion $0.60/1M
    # 1,000,000 prompt tokens = $0.15
    # 500,000 completion tokens = $0.30
    cost = AICostTracker.calculate_cost(
        "gpt-4o-mini", prompt_tokens=1_000_000, completion_tokens=500_000
    )
    assert cost == 0.45

    # Small token count
    # 1000 prompt tokens = 0.00015, 500 completion tokens = 0.00030 -> total = 0.00045
    cost_small = AICostTracker.calculate_cost(
        "gpt-4o-mini", prompt_tokens=1000, completion_tokens=500
    )
    assert cost_small == 0.00045


def test_calculate_cost_gpt_4o() -> None:
    # gpt-4o: prompt $2.50/1M, completion $10.00/1M
    # 100,000 prompt tokens = $0.25
    # 10,000 completion tokens = $0.10
    cost = AICostTracker.calculate_cost("gpt-4o", prompt_tokens=100_000, completion_tokens=10_000)
    assert cost == 0.35


def test_calculate_cost_embedding_model() -> None:
    # text-embedding-3-small: prompt $0.02/1M, completion $0.00
    cost = AICostTracker.calculate_cost("text-embedding-3-small", prompt_tokens=100_000)
    assert cost == 0.002


def test_calculate_cost_unknown_model_fallback() -> None:
    # Fallback rates: prompt $0.50/1M, completion $1.50/1M
    cost = AICostTracker.calculate_cost(
        "custom-fine-tuned-v1", prompt_tokens=1_000_000, completion_tokens=1_000_000
    )
    assert cost == 2.00


def test_track_usage_logging(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    tracker = AICostTracker()
    cost = tracker.track_usage(
        tenant_id="tenant_test_123",
        model_name="gpt-4o-mini",
        prompt_tokens=2000,
        completion_tokens=500,
        latency_ms=150.5,
        operation="structured_extraction",
        extra_context={"lead_id": "lead_99"},
    )
    assert cost > 0

    assert len(caplog.records) >= 1
    rec = caplog.records[-1]
    assert rec.message == "ai_token_usage_telemetry"
    assert getattr(rec, "tenant_id", None) == "tenant_test_123"
    assert getattr(rec, "model_name", None) == "gpt-4o-mini"
    assert getattr(rec, "prompt_tokens", None) == 2000
    assert getattr(rec, "completion_tokens", None) == 500
    assert getattr(rec, "total_tokens", None) == 2500
    assert getattr(rec, "estimated_cost_usd", None) == 0.0006
    assert getattr(rec, "lead_id", None) == "lead_99"


def test_track_usage_context_tenant(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    set_tenant_id("tenant_context_456")
    tracker = AICostTracker()
    cost = tracker.track_usage(
        model_name="gpt-4o-mini",
        prompt_tokens=500,
        completion_tokens=100,
    )
    assert cost > 0

    assert len(caplog.records) >= 1
    rec = caplog.records[-1]
    assert getattr(rec, "tenant_id", None) == "tenant_context_456"
