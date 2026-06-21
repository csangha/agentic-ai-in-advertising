"""
Tests for the Anomaly Detector — ensures anomalies are caught accurately.
"""

import pytest
from datetime import datetime, timedelta
from services.anomaly_detector import (
    AnomalyDetector, MetricPoint, AnomalySeverity, AnomalyType
)


@pytest.fixture
def detector():
    return AnomalyDetector(zscore_threshold=2.0, rate_of_change_threshold=0.50)


@pytest.fixture
def stable_history():
    """7 days of stable CPA data (~$35 ± $2)."""
    base = datetime(2026, 1, 15, 10, 0)
    points = []
    for i in range(672):  # 7 days at 15-min intervals
        value = 35.0 + (i % 7 - 3) * 0.5  # Small oscillation
        points.append(MetricPoint(timestamp=base + timedelta(minutes=15 * i), value=value))
    return points


@pytest.fixture
def stable_ctr_history():
    """Stable CTR data (~3.5%)."""
    base = datetime(2026, 1, 15, 10, 0)
    return [
        MetricPoint(timestamp=base + timedelta(minutes=15 * i), value=0.035 + (i % 5 - 2) * 0.001)
        for i in range(672)
    ]


class TestZScoreDetection:
    """Z-score based anomaly detection (>2σ from baseline)."""

    def test_normal_value_no_anomaly(self, detector, stable_history):
        result = detector.detect(
            campaign_id="camp-001", platform="meta",
            metric_name="cpa", history=stable_history,
            current_value=36.0, higher_is_worse=True,
        )
        assert result is None  # 36 is within normal range

    def test_high_cpa_detected(self, detector, stable_history):
        # $50 CPA when baseline is ~$35 should be anomalous
        result = detector.detect(
            campaign_id="camp-001", platform="meta",
            metric_name="cpa", history=stable_history,
            current_value=50.0, higher_is_worse=True,
        )
        assert result is not None
        assert result.anomaly_type == AnomalyType.CPA_SPIKE
        assert result.deviation_sigma > 2.0

    def test_low_ctr_detected(self, detector, stable_ctr_history):
        # CTR drop to 1% when baseline is ~3.5%
        result = detector.detect(
            campaign_id="camp-001", platform="meta",
            metric_name="ctr", history=stable_ctr_history,
            current_value=0.010, higher_is_worse=False,
        )
        assert result is not None
        assert result.anomaly_type == AnomalyType.CTR_COLLAPSE

    def test_insufficient_data_returns_none(self, detector):
        # Less than 24 data points
        short_history = [
            MetricPoint(timestamp=datetime(2026, 1, 15, i, 0), value=35.0)
            for i in range(10)
        ]
        result = detector.detect(
            campaign_id="camp-001", platform="meta",
            metric_name="cpa", history=short_history,
            current_value=100.0, higher_is_worse=True,
        )
        assert result is None


class TestRateOfChangeDetection:
    """Rate-of-change detection (>50% in 1 hour)."""

    def test_sudden_spike_detected(self, detector):
        base = datetime(2026, 1, 20, 10, 0)
        # Stable at $35, then jumps to $60 in last reading
        history = [
            MetricPoint(timestamp=base + timedelta(minutes=15 * i), value=35.0)
            for i in range(100)
        ]
        # Current value is 75% above the value 1 hour ago
        result = detector.detect(
            campaign_id="camp-001", platform="google",
            metric_name="cpa", history=history,
            current_value=61.25, higher_is_worse=True,  # 75% above $35
        )
        assert result is not None
        assert result.rate_of_change_pct is not None
        assert abs(result.rate_of_change_pct) >= 0.50

    def test_gradual_increase_not_flagged(self, detector, stable_history):
        # Only slightly above baseline — not >50% in 1 hour
        result = detector.detect(
            campaign_id="camp-001", platform="meta",
            metric_name="cpa", history=stable_history,
            current_value=37.0, higher_is_worse=True,
        )
        assert result is None


class TestSeverityClassification:
    """Severity levels based on deviation magnitude."""

    def test_low_severity(self, detector, stable_history):
        # Just barely above threshold
        result = detector.detect(
            campaign_id="camp-001", platform="meta",
            metric_name="cpa", history=stable_history,
            current_value=42.0, higher_is_worse=True,
        )
        if result:
            assert result.severity in [AnomalySeverity.LOW, AnomalySeverity.MEDIUM]

    def test_critical_severity(self, detector, stable_history):
        # Extreme deviation
        result = detector.detect(
            campaign_id="camp-001", platform="meta",
            metric_name="cpa", history=stable_history,
            current_value=100.0, higher_is_worse=True,
        )
        assert result is not None
        assert result.severity in [AnomalySeverity.HIGH, AnomalySeverity.CRITICAL]

    def test_recommended_action_matches_severity(self, detector, stable_history):
        result = detector.detect(
            campaign_id="camp-001", platform="meta",
            metric_name="cpa", history=stable_history,
            current_value=100.0, higher_is_worse=True,
        )
        assert result is not None
        assert "escalate" in result.recommended_action.lower() or "pause" in result.recommended_action.lower()


class TestMultipleMetrics:
    """Detect anomalies across multiple metrics simultaneously."""

    def test_detect_multiple(self, detector, stable_history, stable_ctr_history):
        results = detector.detect_multiple(
            campaign_id="camp-001", platform="meta",
            metrics={
                "cpa": (stable_history, 35.5, True),  # Normal
                "ctr": (stable_ctr_history, 0.010, False),  # Anomalous drop
            },
        )
        # Should detect CTR anomaly but not CPA
        ctr_anomalies = [r for r in results if r.metric_name == "ctr"]
        cpa_anomalies = [r for r in results if r.metric_name == "cpa"]
        assert len(ctr_anomalies) >= 1
        assert len(cpa_anomalies) == 0
