"""Unit tests for AI Token Usage & Cost Metric Tracking Service (TASK-1103)."""

import pytest

from app.core.logging import set_tenant_id
from app.services.ai_cost_tracker import AICostTracker


def test_calculate_cost_gpt_4o_mini() -> None:
    # gpt-4o-mini: prompt $0.15/1M, completion $0.60/1M
    cost, is_fallback = AICostTracker.calculate_cost(
        "gpt-4o-mini", prompt_tokens=1_000_000, completion_tokens=500_000
    )
    assert cost == 0.45
    assert not is_fallback

    cost_small, is_fallback_small = AICostTracker.calculate_cost(
        "gpt-4o-mini", prompt_tokens=1000, completion_tokens=500
    )
    assert cost_small == 0.00045
    assert not is_fallback_small


def test_calculate_cost_gpt_4o() -> None:
    cost, is_fallback = AICostTracker.calculate_cost(
        "gpt-4o", prompt_tokens=100_000, completion_tokens=10_000
    )
    assert cost == 0.35
    assert not is_fallback


def test_calculate_cost_embedding_model() -> None:
    cost, is_fallback = AICostTracker.calculate_cost(
        "text-embedding-3-small", prompt_tokens=100_000
    )
    assert cost == 0.002
    assert not is_fallback


def test_calculate_cost_unknown_model_fallback() -> None:
    cost, is_fallback = AICostTracker.calculate_cost(
        "custom-fine-tuned-v1", prompt_tokens=1_000_000, completion_tokens=1_000_000
    )
    assert cost == 2.00
    assert is_fallback is True


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
    assert getattr(rec, "is_fallback_pricing", None) is False
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
