"""
Campaign data models — SQLAlchemy ORM definitions for campaign state and lifecycle.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List

from sqlalchemy import (
    Column, String, Numeric, Float, DateTime, Enum as SAEnum,
    JSON, Boolean, Integer, Text, ForeignKey, Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class CampaignStatus(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    LAUNCHING = "LAUNCHING"
    ACTIVE = "ACTIVE"
    OPTIMIZING = "OPTIMIZING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"


class CampaignBrief(Base):
    """The natural language brief provided by the marketing manager."""

    __tablename__ = "campaign_briefs"

    brief_id = Column(String(64), primary_key=True)
    raw_text = Column(Text, nullable=False)
    budget_total = Column(Numeric(18, 4), nullable=False)
    target_cpa = Column(Numeric(18, 4), nullable=False)
    audience_description = Column(Text)
    platforms = Column(JSON)  # ["meta", "google", "tiktok", "amazon"]
    sentiment_threshold = Column(Float, default=0.75)
    constraints = Column(JSON)  # Additional constraints as key-value
    parsed_parameters = Column(JSON)  # LLM-extracted structured parameters
    is_valid = Column(Boolean, default=True)
    validation_errors = Column(JSON)
    submitted_by = Column(String(128))
    submitted_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    campaign = relationship("CampaignState", back_populates="brief", uselist=False)


class CampaignState(Base):
    """
    Core campaign state — the unified object tracking a campaign's lifecycle.
    This is the single source of truth for any campaign.
    """

    __tablename__ = "campaign_states"

    campaign_id = Column(String(64), primary_key=True)
    brief_id = Column(String(64), ForeignKey("campaign_briefs.brief_id"))
    status = Column(SAEnum(CampaignStatus), default=CampaignStatus.DRAFT, nullable=False)

    # Budget tracking
    budget_total = Column(Numeric(18, 4), nullable=False)
    budget_spent = Column(Numeric(18, 4), default=0)
    budget_remaining = Column(Numeric(18, 4))
    daily_budget = Column(Numeric(18, 4))

    # Performance targets
    target_cpa = Column(Numeric(18, 4), nullable=False)
    current_cpa = Column(Numeric(18, 4))
    target_roas = Column(Float)
    current_roas = Column(Float)

    # Sentiment
    sentiment_threshold = Column(Float, default=0.75)
    current_sentiment = Column(Float)

    # Campaign schedule
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    flight_days = Column(Integer)

    # Configuration
    platform_configs = Column(JSON)  # Platform-specific campaign configs
    initial_allocation = Column(JSON)  # Budget split across platforms

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    approved_at = Column(DateTime)
    approved_by = Column(String(128))
    launched_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Relationships
    brief = relationship("CampaignBrief", back_populates="campaign")
    platforms = relationship("PlatformCampaign", back_populates="campaign")

    __table_args__ = (
        Index("idx_campaign_status", "status"),
        Index("idx_campaign_dates", "created_at", "status"),
    )
