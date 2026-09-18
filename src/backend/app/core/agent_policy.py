"""Agent Policy Configuration & Safe Guardrails Engine (Step 3)."""

from enum import StrEnum
from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field


class AgentMode(StrEnum):
    DRAFT_THEN_SEND = "draft_then_send"
    AUTONOMOUS = "autonomous"


class AgentBehaviorPolicy(BaseModel):
    """Safety guardrail configuration governing AI actions in CRM."""

    provider: str = Field(default="gemini", description="Underlying LLM provider")
    model: str = Field(default="gemini-3.6-flash", description="Configured LLM model")
    mode: AgentMode = Field(default=AgentMode.AUTONOMOUS, description="Operational interaction mode")
    auto_reply: bool = Field(default=True, description="Automatically dispatch AI response without human approval")
    require_customer_confirmation: bool = Field(default=True, description="Enforce customer confirmation before action")
    allow_price_commitments: bool = Field(default=False, description="Block AI from committing to fixed prices")
    allow_availability_commitments: bool = Field(default=False, description="Block AI from guaranteeing stock availability")
    allow_unconfirmed_order_creation: bool = Field(default=False, description="Block creation of unverified orders")
    human_handoff_enabled: bool = Field(default=True, description="Enable automatic escalation to human sales agent")


def load_agent_policy(config_path: str | Path | None = None) -> AgentBehaviorPolicy:
    """Load agent behavior policy from YAML file with safe defaults."""
    if config_path is None:
        # Search relative to repo root
        candidates = [
            Path("config/agent_policy.yaml"),
            Path("../config/agent_policy.yaml"),
            Path("../../config/agent_policy.yaml"),
            Path(__file__).resolve().parents[3] / "config" / "agent_policy.yaml",
        ]
        for c in candidates:
            if c.exists():
                config_path = c
                break

    if config_path and Path(config_path).exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            agent_data = data.get("agent", data)
            return AgentBehaviorPolicy.model_validate(agent_data)

    return AgentBehaviorPolicy()
