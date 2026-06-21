"""
Performance metrics models — canonical schema for cross-platform metrics.
Uses TimescaleDB hypertable for efficient time-series queries.
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, BigInteger, Numeric, Float, DateTime, Index,
)
from models.campaign import Base


class PerformanceSnapshot(Base):
    """
    Canonical performance metrics table.
    Normalized from all platforms into a single comparable schema.
    Designed as a TimescaleDB hypertable partitioned by event_hour.
    """

    __tablename__ = "fact_ad_performance_hourly"

    # Composite primary key: platform + ad_id + event_hour
    event_hour = Column(DateTime, primary_key=True, nullable=False)
    platform = Column(String(32), primary_key=True, nullable=False)
    account_id = Column(String(128), nullable=False)
    campaign_id = Column(String(128), nullable=False)
    ad_group_id = Column(String(128))
    ad_id = Column(String(128), primary_key=True, nullable=False)
    creative_id = Column(String(128))

    # Core metrics
    impressions = Column(BigInteger, default=0)
    clicks = Column(BigInteger, default=0)
    spend = Column(Numeric(18, 4), default=0)
    conversions = Column(BigInteger, default=0)
    conversion_value = Column(Numeric(18, 4), default=0)

    # Computed metrics
    ctr = Column(Float)
    cpc = Column(Numeric(18, 6))
    cpm = Column(Numeric(18, 6))
    cpa = Column(Numeric(18, 6))
    roas = Column(Float)

    # Attribution metadata
    source_attribution_type = Column(String(64))

    # Lineage
    ingestion_ts = Column(DateTime, default=datetime.utcnow)
    source_file = Column(String(512))

    __table_args__ = (
        Index("idx_perf_campaign_hour", "campaign_id", "event_hour"),
        Index("idx_perf_platform_hour", "platform", "event_hour"),
        Index("idx_perf_creative_hour", "creative_id", "event_hour"),
    )


class PacingSnapshot(Base):
    """Campaign pacing status captured at regular intervals."""

    __tablename__ = "pacing_snapshots"

    snapshot_id = Column(String(64), primary_key=True)
    campaign_id = Column(String(128), nullable=False, index=True)
    platform = Column(String(32))
    snapshot_time = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Pacing metrics
    expected_spend = Column(Numeric(18, 4))  # Where we should be
    actual_spend = Column(Numeric(18, 4))  # Where we actually are
    pacing_ratio = Column(Float)  # actual / expected (1.0 = on track)
    projected_exhaustion_date = Column(DateTime)

    # Status
    pacing_status = Column(String(16))  # ON_TRACK, OVER_PACING, UNDER_PACING

    __table_args__ = (
        Index("idx_pacing_campaign_time", "campaign_id", "snapshot_time"),
    )
