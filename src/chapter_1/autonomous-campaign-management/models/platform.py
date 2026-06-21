"""
Platform campaign models — tracks per-platform campaign state.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Column, String, Numeric, Float, DateTime, JSON, ForeignKey, Index,
)
from sqlalchemy.orm import relationship
from models.campaign import Base


class PlatformType(str, Enum):
    META = "meta"
    GOOGLE = "google"
    TIKTOK = "tiktok"
    AMAZON = "amazon"


class PlatformCampaign(Base):
    """Per-platform campaign configuration and state."""

    __tablename__ = "platform_campaigns"

    platform_campaign_id = Column(String(64), primary_key=True)
    campaign_id = Column(String(64), ForeignKey("campaign_states.campaign_id"), nullable=False)
    platform = Column(String(32), nullable=False)

    # Platform-specific IDs (returned after campaign creation)
    external_campaign_id = Column(String(256))
    external_ad_group_ids = Column(JSON)  # List of ad group IDs on the platform

    # Configuration
    platform_config = Column(JSON)  # Platform-specific campaign settings
    audience_targeting = Column(JSON)  # Targeting parameters
    bid_strategy = Column(String(64))  # e.g., "TARGET_CPA", "MAXIMIZE_CONVERSIONS"
    current_bid = Column(Numeric(18, 4))

    # Budget
    allocated_budget = Column(Numeric(18, 4))
    daily_budget = Column(Numeric(18, 4))
    spent = Column(Numeric(18, 4), default=0)

    # Performance (latest snapshot)
    current_cpa = Column(Numeric(18, 4))
    current_roas = Column(Float)
    current_ctr = Column(Float)
    impressions_total = Column(Numeric(18, 0), default=0)
    conversions_total = Column(Numeric(18, 0), default=0)

    # Status
    platform_status = Column(String(32))  # ACTIVE, PAUSED, PENDING, ERROR
    last_sync_at = Column(DateTime)
    last_error = Column(String(512))

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    campaign = relationship("CampaignState", back_populates="platforms")

    __table_args__ = (
        Index("idx_platform_campaign", "campaign_id", "platform"),
        Index("idx_platform_status", "platform", "platform_status"),
    )
