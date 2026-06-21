"""
Audit log model — immutable append-only record of all autonomous decisions.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Column, String, DateTime, JSON, Boolean, Text, Index,
)
from models.campaign import Base


class ActionType(str, Enum):
    BID_CHANGE = "BID_CHANGE"
    BUDGET_REALLOC = "BUDGET_REALLOC"
    CREATIVE_LAUNCH = "CREATIVE_LAUNCH"
    CREATIVE_PAUSE = "CREATIVE_PAUSE"
    AUDIENCE_EXPAND = "AUDIENCE_EXPAND"
    AUDIENCE_CONTRACT = "AUDIENCE_CONTRACT"
    CAMPAIGN_PAUSE = "CAMPAIGN_PAUSE"
    CAMPAIGN_RESUME = "CAMPAIGN_RESUME"
    GUARDRAIL_TRIGGER = "GUARDRAIL_TRIGGER"
    ESCALATION = "ESCALATION"
    TREND_DETECTED = "TREND_DETECTED"
    ANOMALY_DETECTED = "ANOMALY_DETECTED"


class AuditEntry(Base):
    """
    Immutable audit log entry. Every autonomous action generates one of these.
    Supports full explainability and rollback.
    """

    __tablename__ = "audit_log"

    entry_id = Column(String(64), primary_key=True)
    campaign_id = Column(String(64), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # What happened
    agent = Column(String(64), nullable=False)  # e.g., "optimization_agent"
    action_type = Column(String(32), nullable=False)

    # State before and after
    pre_state = Column(JSON)
    post_state = Column(JSON)

    # Decision context
    reasoning = Column(Text)  # LLM-generated explanation
    metrics_at_decision = Column(JSON)  # Metrics snapshot that triggered the decision
    confidence_score = Column(String(8))  # Agent's confidence in the action

    # Guardrail check
    guardrail_check_passed = Column(Boolean, default=True)
    guardrail_details = Column(JSON)

    # Reversibility
    reversible = Column(Boolean, default=True)
    reversed = Column(Boolean, default=False)
    reversed_at = Column(DateTime)
    reversed_by = Column(String(128))

    # Correlation for multi-step decisions
    correlation_id = Column(String(64))
    parent_entry_id = Column(String(64))

    __table_args__ = (
        Index("idx_audit_campaign_time", "campaign_id", "timestamp"),
        Index("idx_audit_agent", "agent", "timestamp"),
        Index("idx_audit_action_type", "action_type", "timestamp"),
        Index("idx_audit_correlation", "correlation_id"),
    )
