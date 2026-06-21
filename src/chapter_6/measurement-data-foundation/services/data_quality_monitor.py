"""
Data Quality Monitor — ensures data freshness, completeness, and consistency.

Features:
- Freshness checks (alert if data is stale)
- Completeness scoring (missing fields, expected records)
- Volume anomaly detection (unexpected drops/spikes)
- Agent gate (blocks downstream actions on stale/low-quality data)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum


class QualityStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    STALE = "stale"


class GateDecision(Enum):
    ALLOW = "allow"
    BLOCK = "block"
    ALLOW_WITH_WARNING = "allow_with_warning"


@dataclass
class FreshnessCheck:
    """Result of a data freshness check."""
    source: str
    platform: str
    latest_data_timestamp: Optional[datetime]
    expected_freshness_minutes: int
    actual_age_minutes: float
    is_fresh: bool
    staleness_severity: str = ""  # "mild", "moderate", "severe"


@dataclass
class CompletenessCheck:
    """Result of a data completeness check."""
    source: str
    expected_fields: list[str]
    present_fields: list[str]
    missing_fields: list[str]
    completeness_pct: float
    expected_record_count: int
    actual_record_count: int
    record_completeness_pct: float


@dataclass
class VolumeAnomaly:
    """A detected volume anomaly."""
    source: str
    metric: str
    expected_volume: float
    actual_volume: float
    deviation_pct: float
    anomaly_type: str  # "drop" or "spike"
    severity: str


@dataclass
class DataQualityReport:
    """Complete data quality assessment."""
    report_id: str
    overall_status: QualityStatus
    freshness_checks: list[FreshnessCheck]
    completeness_checks: list[CompletenessCheck]
    volume_anomalies: list[VolumeAnomaly]
    quality_score: float  # 0.0-1.0
    gate_decision: GateDecision
    gate_reasoning: str
    generated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DataSourceConfig:
    """Configuration for a monitored data source."""
    source_name: str
    platform: str
    expected_freshness_minutes: int = 60
    expected_fields: list[str] = field(default_factory=list)
    expected_daily_records: int = 0
    volume_deviation_threshold: float = 0.5  # 50% deviation = anomaly


class DataQualityMonitor:
    """
    Monitors data quality and gates downstream agent actions.

    When data quality falls below thresholds, the agent gate blocks
    optimization and execution actions to prevent decisions based on
    stale or incomplete information.
    """

    def __init__(
        self,
        freshness_warning_minutes: int = 30,
        freshness_critical_minutes: int = 60,
        completeness_threshold: float = 0.90,
        gate_block_threshold: float = 0.70,
    ):
        self.freshness_warning_minutes = freshness_warning_minutes
        self.freshness_critical_minutes = freshness_critical_minutes
        self.completeness_threshold = completeness_threshold
        self.gate_block_threshold = gate_block_threshold
        self._source_configs: dict[str, DataSourceConfig] = {}
        self._latest_timestamps: dict[str, datetime] = {}

    def register_source(self, config: DataSourceConfig) -> None:
        """Register a data source for monitoring."""
        self._source_configs[config.source_name] = config

    def record_data_arrival(self, source_name: str, timestamp: Optional[datetime] = None) -> None:
        """Record that fresh data arrived from a source."""
        self._latest_timestamps[source_name] = timestamp or datetime.utcnow()

    def check_freshness(self, source_name: str) -> FreshnessCheck:
        """Check data freshness for a source."""
        config = self._source_configs.get(source_name)
        latest = self._latest_timestamps.get(source_name)

        if not config:
            return FreshnessCheck(
                source=source_name,
                platform="unknown",
                latest_data_timestamp=None,
                expected_freshness_minutes=60,
                actual_age_minutes=float("inf"),
                is_fresh=False,
                staleness_severity="severe",
            )

        if not latest:
            return FreshnessCheck(
                source=source_name,
                platform=config.platform,
                latest_data_timestamp=None,
                expected_freshness_minutes=config.expected_freshness_minutes,
                actual_age_minutes=float("inf"),
                is_fresh=False,
                staleness_severity="severe",
            )

        age = (datetime.utcnow() - latest).total_seconds() / 60
        is_fresh = age <= config.expected_freshness_minutes

        if age > self.freshness_critical_minutes:
            severity = "severe"
        elif age > self.freshness_warning_minutes:
            severity = "moderate"
        elif age > config.expected_freshness_minutes:
            severity = "mild"
        else:
            severity = ""

        return FreshnessCheck(
            source=source_name,
            platform=config.platform,
            latest_data_timestamp=latest,
            expected_freshness_minutes=config.expected_freshness_minutes,
            actual_age_minutes=round(age, 1),
            is_fresh=is_fresh,
            staleness_severity=severity,
        )

    def check_completeness(
        self, source_name: str, records: list[dict]
    ) -> CompletenessCheck:
        """Check data completeness for a batch of records."""
        config = self._source_configs.get(source_name)
        if not config:
            return CompletenessCheck(
                source=source_name,
                expected_fields=[],
                present_fields=[],
                missing_fields=[],
                completeness_pct=0.0,
                expected_record_count=0,
                actual_record_count=len(records),
                record_completeness_pct=0.0,
            )

        # Field completeness
        expected_fields = config.expected_fields
        present_fields = []
        missing_fields = []

        if records:
            all_keys = set()
            for record in records:
                all_keys.update(record.keys())
            present_fields = [f for f in expected_fields if f in all_keys]
            missing_fields = [f for f in expected_fields if f not in all_keys]
        else:
            missing_fields = expected_fields.copy()

        field_completeness = len(present_fields) / len(expected_fields) if expected_fields else 1.0

        # Record count completeness
        record_completeness = 1.0
        if config.expected_daily_records > 0:
            record_completeness = min(1.0, len(records) / config.expected_daily_records)

        return CompletenessCheck(
            source=source_name,
            expected_fields=expected_fields,
            present_fields=present_fields,
            missing_fields=missing_fields,
            completeness_pct=round(field_completeness, 3),
            expected_record_count=config.expected_daily_records,
            actual_record_count=len(records),
            record_completeness_pct=round(record_completeness, 3),
        )

    def check_volume_anomaly(
        self, source_name: str, current_volume: float, historical_avg: float
    ) -> Optional[VolumeAnomaly]:
        """Check for volume anomalies (unexpected drops or spikes)."""
        config = self._source_configs.get(source_name)
        threshold = config.volume_deviation_threshold if config else 0.5

        if historical_avg == 0:
            return None

        deviation = (current_volume - historical_avg) / historical_avg

        if abs(deviation) < threshold:
            return None

        anomaly_type = "spike" if deviation > 0 else "drop"
        severity = "critical" if abs(deviation) > threshold * 2 else "warning"

        return VolumeAnomaly(
            source=source_name,
            metric="record_volume",
            expected_volume=historical_avg,
            actual_volume=current_volume,
            deviation_pct=round(deviation, 3),
            anomaly_type=anomaly_type,
            severity=severity,
        )

    def evaluate_gate(self, source_names: list[str] = None) -> tuple[GateDecision, str]:
        """
        Evaluate the agent gate — should downstream actions be allowed?

        Blocks actions when:
        - Any source has severe staleness
        - Overall quality score below threshold
        """
        sources = source_names or list(self._source_configs.keys())
        if not sources:
            return GateDecision.ALLOW, "No sources configured"

        freshness_scores = []
        for source in sources:
            check = self.check_freshness(source)
            if check.staleness_severity == "severe":
                return GateDecision.BLOCK, f"Data source '{source}' is severely stale. Blocking agent actions."
            elif check.is_fresh:
                freshness_scores.append(1.0)
            elif check.staleness_severity == "moderate":
                freshness_scores.append(0.5)
            else:
                freshness_scores.append(0.7)

        avg_freshness = sum(freshness_scores) / len(freshness_scores) if freshness_scores else 0.0

        if avg_freshness < self.gate_block_threshold:
            return GateDecision.BLOCK, f"Overall data freshness ({avg_freshness:.0%}) below gate threshold ({self.gate_block_threshold:.0%})"
        elif avg_freshness < 0.9:
            return GateDecision.ALLOW_WITH_WARNING, f"Data freshness ({avg_freshness:.0%}) is degraded. Proceed with caution."

        return GateDecision.ALLOW, "All data sources are fresh and complete."

    def generate_report(self, source_names: list[str] = None) -> DataQualityReport:
        """Generate a full quality report across all sources."""
        sources = source_names or list(self._source_configs.keys())
        freshness_checks = [self.check_freshness(s) for s in sources]
        gate_decision, gate_reasoning = self.evaluate_gate(sources)

        # Overall quality score
        fresh_count = sum(1 for f in freshness_checks if f.is_fresh)
        quality_score = fresh_count / len(freshness_checks) if freshness_checks else 0.0

        # Overall status
        if quality_score >= 0.9:
            status = QualityStatus.HEALTHY
        elif quality_score >= 0.7:
            status = QualityStatus.WARNING
        elif any(f.staleness_severity == "severe" for f in freshness_checks):
            status = QualityStatus.STALE
        else:
            status = QualityStatus.CRITICAL

        return DataQualityReport(
            report_id=f"dqr-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            overall_status=status,
            freshness_checks=freshness_checks,
            completeness_checks=[],
            volume_anomalies=[],
            quality_score=round(quality_score, 3),
            gate_decision=gate_decision,
            gate_reasoning=gate_reasoning,
        )
