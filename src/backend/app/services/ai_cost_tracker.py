"""AI Token Usage & Cost Metric Tracking Service (docs/ai-architecture.md Section 9).

Note: Cost tracking metrics are for observability and ops monitoring ONLY.
Cost estimates MUST NOT be used as binding billing data (is_authoritative_billing=False).
"""

from typing import Any

from app.core.logging import get_tenant_id, logger

# Model Pricing in USD per 1,000,000 tokens
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {
        "prompt_usd_per_1m": 0.15,
        "completion_usd_per_1m": 0.60,
    },
    "gpt-4o": {
        "prompt_usd_per_1m": 2.50,
        "completion_usd_per_1m": 10.00,
    },
    "text-embedding-3-small": {
        "prompt_usd_per_1m": 0.02,
        "completion_usd_per_1m": 0.00,
    },
    "text-embedding-3-large": {
        "prompt_usd_per_1m": 0.13,
        "completion_usd_per_1m": 0.00,
    },
    "demo-llm": {
        "prompt_usd_per_1m": 0.00,
        "completion_usd_per_1m": 0.00,
    },
}

# Fallback pricing per 1M tokens for unknown/unregistered models
DEFAULT_PROMPT_USD_PER_1M = 0.50
DEFAULT_COMPLETION_USD_PER_1M = 1.50


class AICostTracker:
    """Service for calculating AI token costs and recording structured telemetry metrics."""

    @staticmethod
    def calculate_cost(
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int = 0,
    ) -> tuple[float, bool]:
        """Calculate estimated USD cost given model name and token counts.

        Returns:
            tuple[float, bool]: (estimated_cost_usd, is_fallback_pricing)
        """
        model_key = model_name.lower()
        pricing = MODEL_PRICING.get(model_key)
        is_fallback = False

        if pricing:
            prompt_rate = pricing["prompt_usd_per_1m"]
            completion_rate = pricing["completion_usd_per_1m"]
        else:
            is_fallback = True
            prompt_rate = DEFAULT_PROMPT_USD_PER_1M
            completion_rate = DEFAULT_COMPLETION_USD_PER_1M
            logger.warning(
                "ai_cost_tracker_unregistered_model",
                extra={
                    "model_name": model_name,
                    "prompt_rate_usd_per_1m": prompt_rate,
                    "completion_rate_usd_per_1m": completion_rate,
                },
            )

        prompt_cost = (prompt_tokens / 1_000_000.0) * prompt_rate
        completion_cost = (completion_tokens / 1_000_000.0) * completion_rate
        return round(prompt_cost + completion_cost, 6), is_fallback

    def track_usage(
        self,
        tenant_id: str | None = None,
        model_name: str = "gpt-4o-mini",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: float = 0.0,
        operation: str = "llm_completion",
        extra_context: dict[str, Any] | None = None,
    ) -> float:
        """Calculate cost and emit structured log telemetry for AI execution."""
        resolved_tenant_id = tenant_id or get_tenant_id() or "system"
        estimated_cost_usd, is_fallback = self.calculate_cost(
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        total_tokens = prompt_tokens + completion_tokens

        telemetry_payload: dict[str, Any] = {
            "tenant_id": resolved_tenant_id,
            "model_name": model_name,
            "operation": operation,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "is_fallback_pricing": is_fallback,
            "is_authoritative_billing": False,
            "latency_ms": round(latency_ms, 2),
        }
        if extra_context:
            telemetry_payload.update(extra_context)

        logger.info(
            "ai_token_usage_telemetry",
            extra=telemetry_payload,
        )

        return estimated_cost_usd
