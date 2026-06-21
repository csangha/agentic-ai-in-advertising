"""
Anomaly Detector — statistical detection of performance anomalies.

Methods:
- Z-score deviation (>2σ from 7-day rolling baseline)
- Rate-of-change detection (>50% change in 1 hour)
- Severity classification (LOW, MEDIUM, HIGH, CRITICAL)
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional
import math


class AnomalySeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AnomalyType(str, Enum):
    CPA_SPIKE = "CPA_SPIKE"
    SPEND_ACCELERATION = "SPEND_ACCELERATION"
    CTR_COLLAPSE = "CTR_COLLAPSE"
    CONVERSION_DROP = "CONVERSION_DROP"
    IMPRESSION_SURGE = "IMPRESSION_SURGE"
    ROAS_DECLINE = "ROAS_DECLINE"


@dataclass
class AnomalyEvent:
    anomaly_id: str
    campaign_id: str
    platform: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    metric_name: str
    expected_value: float
    actual_value: float
    deviation_sigma: float
    rate_of_change_pct: Optional[float]
    description: str
    recommended_action: str
    detected_at: datetime


@dataclass
class MetricPoint:
    timestamp: datetime
    value: float


class AnomalyDetector:
    """
    Detects performance anomalies using statistical methods.
    Designed to run every 15 minutes on the latest metrics.
    """

    def __init__(
        self,
        zscore_threshold: float = 2.0,
        rate_of_change_threshold: float = 0.50,
        min_data_points: int = 24,  # Minimum 24 data points (6 hours at 15-min intervals)
    ):
        self.zscore_threshold = zscore_threshold
        self.rate_of_change_threshold = rate_of_change_threshold
        self.min_data_points = min_data_points

    def detect(
        self,
        campaign_id: str,
        platform: str,
        metric_name: str,
        history: List[MetricPoint],
        current_value: float,
        higher_is_worse: bool = True,
    ) -> Optional[AnomalyEvent]:
        """
        Detect if the current value is anomalous relative to history.

        Args:
            campaign_id: Campaign identifier
            platform: Platform name
            metric_name: Name of the metric (e.g., "cpa", "ctr", "spend")
            history: Historical data points (7-day rolling window)
            current_value: The latest observed value
            higher_is_worse: If True, spikes are bad (CPA, spend). If False, drops are bad (CTR, conversions).

        Returns:
            AnomalyEvent if anomaly detected, None otherwise.
        """
        if len(history) < self.min_data_points:
            return None  # Not enough data for baseline

        values = [p.value for p in history]

        # Z-score detection
        zscore_result = self._zscore_check(values, current_value, higher_is_worse)

        # Rate-of-change detection (compare to 1 hour ago)
        roc_result = self._rate_of_change_check(history, current_value, higher_is_worse)

        # Determine if anomaly exists and classify severity
        if zscore_result or roc_result:
            sigma = zscore_result if zscore_result else 0
            roc = roc_result if roc_result else 0

            severity = self._classify_severity(abs(sigma), abs(roc))
            anomaly_type = self._infer_type(metric_name, higher_is_worse)
            mean_val = sum(values) / len(values)

            return AnomalyEvent(
                anomaly_id=f"anomaly-{campaign_id}-{metric_name}-{int(datetime.utcnow().timestamp())}",
                campaign_id=campaign_id,
                platform=platform,
                anomaly_type=anomaly_type,
                severity=severity,
                metric_name=metric_name,
                expected_value=round(mean_val, 4),
                actual_value=round(current_value, 4),
                deviation_sigma=round(sigma, 2),
                rate_of_change_pct=round(roc, 4) if roc else None,
                description=self._describe(metric_name, current_value, mean_val, sigma, roc),
                recommended_action=self._recommend_action(severity, anomaly_type),
                detected_at=datetime.utcnow(),
            )

        return None

    def detect_multiple(
        self,
        campaign_id: str,
        platform: str,
        metrics: dict,  # metric_name → (history, current_value, higher_is_worse)
    ) -> List[AnomalyEvent]:
        """Detect anomalies across multiple metrics simultaneously."""
        anomalies = []
        for metric_name, (history, current_value, higher_is_worse) in metrics.items():
            event = self.detect(campaign_id, platform, metric_name, history, current_value, higher_is_worse)
            if event:
                anomalies.append(event)
        return anomalies

    def _zscore_check(self, values: List[float], current: float, higher_is_worse: bool) -> Optional[float]:
        """Compute Z-score and check against threshold."""
        n = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        std = math.sqrt(variance) if variance > 0 else 0

        if std == 0:
            return None

        zscore = (current - mean) / std

        # Check direction
        if higher_is_worse and zscore > self.zscore_threshold:
            return zscore
        elif not higher_is_worse and zscore < -self.zscore_threshold:
            return zscore

        return None

    def _rate_of_change_check(
        self, history: List[MetricPoint], current: float, higher_is_worse: bool
    ) -> Optional[float]:
        """Check if value changed >50% in the last hour (4 data points at 15-min intervals)."""
        if len(history) < 4:
            return None

        # Value 1 hour ago (4 intervals back)
        one_hour_ago = history[-4].value

        if one_hour_ago == 0:
            return None

        rate_of_change = (current - one_hour_ago) / abs(one_hour_ago)

        if higher_is_worse and rate_of_change > self.rate_of_change_threshold:
            return rate_of_change
        elif not higher_is_worse and rate_of_change < -self.rate_of_change_threshold:
            return rate_of_change

        return None

    def _classify_severity(self, sigma: float, roc: float) -> AnomalySeverity:
        """Classify severity based on Z-score magnitude and rate of change."""
        max_signal = max(sigma, abs(roc) * 4)  # Normalize RoC to sigma-equivalent

        if max_signal >= 4.0:
            return AnomalySeverity.CRITICAL
        elif max_signal >= 3.0:
            return AnomalySeverity.HIGH
        elif max_signal >= 2.5:
            return AnomalySeverity.MEDIUM
        else:
            return AnomalySeverity.LOW

    def _infer_type(self, metric_name: str, higher_is_worse: bool) -> AnomalyType:
        """Infer anomaly type from metric name."""
        type_map = {
            "cpa": AnomalyType.CPA_SPIKE,
            "spend": AnomalyType.SPEND_ACCELERATION,
            "ctr": AnomalyType.CTR_COLLAPSE,
            "conversions": AnomalyType.CONVERSION_DROP,
            "impressions": AnomalyType.IMPRESSION_SURGE,
            "roas": AnomalyType.ROAS_DECLINE,
        }
        return type_map.get(metric_name, AnomalyType.CPA_SPIKE)

    def _describe(self, metric: str, current: float, mean: float, sigma: float, roc: float) -> str:
        """Generate human-readable description."""
        parts = [f"{metric} is {current:.2f} vs baseline {mean:.2f}"]
        if sigma:
            parts.append(f"({abs(sigma):.1f}σ deviation)")
        if roc:
            parts.append(f"({abs(roc):.0%} change in 1h)")
        return " ".join(parts)

    def _recommend_action(self, severity: AnomalySeverity, anomaly_type: AnomalyType) -> str:
        """Recommend action based on severity."""
        actions = {
            AnomalySeverity.LOW: "Monitor closely. No immediate action required.",
            AnomalySeverity.MEDIUM: "Investigate root cause. Consider reducing bid by 5-10%.",
            AnomalySeverity.HIGH: "Reduce exposure immediately. Pause affected ad groups and escalate.",
            AnomalySeverity.CRITICAL: "EMERGENCY: Pause all affected campaigns. Escalate to human immediately.",
        }
        return actions[severity]
