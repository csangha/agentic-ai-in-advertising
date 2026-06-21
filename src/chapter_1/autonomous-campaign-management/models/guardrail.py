"""
Guardrail models — safety boundaries for autonomous campaign management.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Column, String, Numeric, Float, DateTime, Boolean, JSON, Index,
)
from pydantic import BaseModel
from models.campaign import Base


class GuardrailType(str, Enum):
    BUDGET_CAP = "BUDGET_CAP"
    CPA_CEILING = "CPA_CEILING"
    SPEND_RATE = "SPEND_RATE"
    SENTIMENT_FLOOR = "SENTIMENT_FLOOR"
    BRAND_SAFETY = "BRAND_SAFETY"
    AUDIENCE_CONCENTRATION = "AUDIENCE_CONCENTRATION"
    BID_CHANGE_LIMIT = "BID_CHANGE_LIMIT"
    ESCALATION_THRESHOLD = "ESCALATION_THRESHOLD"


class Guardrail(Base):
    """Guardrail configuration per campaign."""

    __tablename__ = "guardrails"

    guardrail_id = Column(String(64), primary_key=True)
    campaign_id = Column(String(64), nullable=False, index=True)
    guardrail_type = Column(String(32), nullable=False)
    description = Column(String(256))

    # Threshold values (interpretation depends on guardrail_type)
    threshold_value = Column(Numeric(18, 4))
    threshold_pct = Column(Float)
    threshold_duration_hours = Column(Float)  # For time-based guardrails (e.g., CPA > 200% for 4h)

    # Configuration
    action_on_breach = Column(String(32))  # "pause", "reduce", "alert", "escalate"
    is_hard_limit = Column(Boolean, default=True)  # Hard = cannot be overridden; Soft = alert only
    enabled = Column(Boolean, default=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(128))

    __table_args__ = (
        Index("idx_guardrail_campaign", "campaign_id", "guardrail_type"),
    )


class GuardrailResult(BaseModel):
    """Result of checking a proposed action against guardrails."""

    passed: bool
    guardrail_id: Optional[str] = None
    guardrail_type: Optional[str] = None
    violation_message: Optional[str] = None
    current_value: Optional[float] = None
    threshold: Optional[float] = None
    action_blocked: bool = False
    escalation_required: bool = False


class GuardrailCheckRequest(BaseModel):
    """Request to evaluate a proposed action against guardrails."""

    campaign_id: str
    action_type: str
    proposed_change: dict  # e.g., {"bid_change_pct": 0.12, "platform": "meta"}
    current_metrics: dict  # e.g., {"current_cpa": 42.5, "spend_today": 1500}
