"""
Creative Fatigue Detector — identifies when creatives are losing effectiveness.

Features:
- CTR decline detection (>20% drop from peak)
- Frequency threshold monitoring (>3.5 average frequency)
- Multi-signal fatigue scoring
- Replacement queue priority
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum
import statistics


class FatigueStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"  # Early signs of fatigue
    FATIGUED = "fatigued"  # Active fatigue — needs rotation
    EXHAUSTED = "exhausted"  # Severely fatigued — immediate replacement


@dataclass
class CreativeMetricSnapshot:
    """Performance metrics for a creative at a point in time."""
    creative_id: str
    timestamp: datetime
    ctr: float
    conversion_rate: float
    frequency: float
    impressions: int
    spend: float
    cpa: float = 0.0


@dataclass
class FatigueSignal:
    """A detected fatigue signal for a creative."""
    creative_id: str
    signal_type: str  # "ctr_decline", "frequency_cap", "engagement_drop"
    severity: float  # 0.0-1.0
    current_value: float
    threshold_value: float
    peak_value: float
    decline_pct: float
    detected_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FatigueAssessment:
    """Complete fatigue assessment for a creative."""
    creative_id: str
    campaign_id: str
    status: FatigueStatus
    fatigue_score: float  # 0.0-1.0 (1.0 = fully exhausted)
    signals: list[FatigueSignal]
    days_active: int
    peak_ctr: float
    current_ctr: float
    current_frequency: float
    ctr_decline_from_peak: float
    recommendation: str
    replacement_priority: int = 0  # 0=none, 1-10 urgency
    assessed_at: datetime = field(default_factory=datetime.utcnow)


class CreativeFatigueDetector:
    """
    Detects creative fatigue using multiple signals.

    Primary fatigue condition:
    - CTR decline > 20% from peak AND frequency > 3.5

    Additional signals:
    - Conversion rate decline > 30% from peak
    - Frequency > 5.0 (severe)
    - Days active > 21 with declining metrics
    """

    def __init__(
        self,
        ctr_decline_threshold: float = 0.20,
        frequency_threshold: float = 3.5,
        severe_frequency: float = 5.0,
        conversion_decline_threshold: float = 0.30,
        min_data_points: int = 7,
        min_impressions: int = 1000,
    ):
        self.ctr_decline_threshold = ctr_decline_threshold
        self.frequency_threshold = frequency_threshold
        self.severe_frequency = severe_frequency
        self.conversion_decline_threshold = conversion_decline_threshold
        self.min_data_points = min_data_points
        self.min_impressions = min_impressions

    def assess(
        self,
        creative_id: str,
        campaign_id: str,
        history: list[CreativeMetricSnapshot],
    ) -> FatigueAssessment:
        """
        Assess fatigue status for a creative based on its performance history.

        Args:
            creative_id: The creative identifier
            campaign_id: The campaign this creative belongs to
            history: Time-ordered list of metric snapshots

        Returns:
            FatigueAssessment with status, score, and recommendation
        """
        if len(history) < self.min_data_points:
            return FatigueAssessment(
                creative_id=creative_id,
                campaign_id=campaign_id,
                status=FatigueStatus.HEALTHY,
                fatigue_score=0.0,
                signals=[],
                days_active=len(history),
                peak_ctr=history[-1].ctr if history else 0.0,
                current_ctr=history[-1].ctr if history else 0.0,
                current_frequency=history[-1].frequency if history else 0.0,
                ctr_decline_from_peak=0.0,
                recommendation="Insufficient data for fatigue assessment",
            )

        # Compute metrics
        peak_ctr = max(s.ctr for s in history)
        current_ctr = statistics.mean([s.ctr for s in history[-3:]])  # Last 3 readings
        current_frequency = history[-1].frequency
        ctr_decline = (peak_ctr - current_ctr) / peak_ctr if peak_ctr > 0 else 0.0
        days_active = (history[-1].timestamp - history[0].timestamp).days

        # Detect signals
        signals = []

        # Signal 1: CTR decline from peak
        if ctr_decline > self.ctr_decline_threshold:
            signals.append(FatigueSignal(
                creative_id=creative_id,
                signal_type="ctr_decline",
                severity=min(1.0, ctr_decline / 0.5),
                current_value=current_ctr,
                threshold_value=peak_ctr * (1 - self.ctr_decline_threshold),
                peak_value=peak_ctr,
                decline_pct=ctr_decline,
            ))

        # Signal 2: Frequency threshold
        if current_frequency > self.frequency_threshold:
            freq_severity = min(1.0, (current_frequency - self.frequency_threshold) / 2.0)
            signals.append(FatigueSignal(
                creative_id=creative_id,
                signal_type="frequency_cap",
                severity=freq_severity,
                current_value=current_frequency,
                threshold_value=self.frequency_threshold,
                peak_value=max(s.frequency for s in history),
                decline_pct=0.0,
            ))

        # Signal 3: Conversion rate decline
        peak_conv = max(s.conversion_rate for s in history)
        current_conv = statistics.mean([s.conversion_rate for s in history[-3:]])
        conv_decline = (peak_conv - current_conv) / peak_conv if peak_conv > 0 else 0.0

        if conv_decline > self.conversion_decline_threshold:
            signals.append(FatigueSignal(
                creative_id=creative_id,
                signal_type="conversion_decline",
                severity=min(1.0, conv_decline / 0.6),
                current_value=current_conv,
                threshold_value=peak_conv * (1 - self.conversion_decline_threshold),
                peak_value=peak_conv,
                decline_pct=conv_decline,
            ))

        # Compute fatigue score (weighted average of signals)
        fatigue_score = self._compute_fatigue_score(signals, ctr_decline, current_frequency)

        # Determine status
        status = self._classify_status(fatigue_score, ctr_decline, current_frequency)

        # Generate recommendation
        recommendation = self._generate_recommendation(status, signals, days_active)

        # Replacement priority
        replacement_priority = self._compute_replacement_priority(status, fatigue_score)

        return FatigueAssessment(
            creative_id=creative_id,
            campaign_id=campaign_id,
            status=status,
            fatigue_score=fatigue_score,
            signals=signals,
            days_active=days_active,
            peak_ctr=peak_ctr,
            current_ctr=current_ctr,
            current_frequency=current_frequency,
            ctr_decline_from_peak=ctr_decline,
            recommendation=recommendation,
            replacement_priority=replacement_priority,
        )

    def detect_batch(
        self, campaign_id: str, creatives: dict[str, list[CreativeMetricSnapshot]]
    ) -> list[FatigueAssessment]:
        """Assess fatigue for all creatives in a campaign."""
        assessments = []
        for creative_id, history in creatives.items():
            assessment = self.assess(creative_id, campaign_id, history)
            assessments.append(assessment)

        # Sort by fatigue score (most fatigued first)
        assessments.sort(key=lambda a: a.fatigue_score, reverse=True)
        return assessments

    def get_rotation_candidates(
        self, assessments: list[FatigueAssessment], min_active: int = 3
    ) -> list[FatigueAssessment]:
        """
        Get creatives that should be rotated out.

        Ensures at least min_active creatives remain.
        """
        fatigued = [a for a in assessments if a.status in (FatigueStatus.FATIGUED, FatigueStatus.EXHAUSTED)]
        healthy = [a for a in assessments if a.status in (FatigueStatus.HEALTHY, FatigueStatus.WARNING)]

        # Only rotate if enough healthy creatives remain
        if len(healthy) >= min_active:
            return fatigued
        else:
            # Only rotate the most fatigued, keeping minimum active
            can_rotate = max(0, len(assessments) - min_active)
            return fatigued[:can_rotate]

    def _compute_fatigue_score(
        self, signals: list[FatigueSignal], ctr_decline: float, frequency: float
    ) -> float:
        """Compute overall fatigue score from signals."""
        if not signals:
            return 0.0

        # Primary condition: CTR decline + frequency
        primary_score = 0.0
        if ctr_decline > self.ctr_decline_threshold and frequency > self.frequency_threshold:
            primary_score = 0.7 + min(0.3, ctr_decline)

        # Signal-based score
        signal_score = sum(s.severity for s in signals) / (len(signals) * 1.5)

        return min(1.0, max(primary_score, signal_score))

    def _classify_status(
        self, fatigue_score: float, ctr_decline: float, frequency: float
    ) -> FatigueStatus:
        """Classify fatigue status based on score and signals."""
        # Primary fatigue condition
        if ctr_decline > self.ctr_decline_threshold and frequency > self.frequency_threshold:
            if frequency > self.severe_frequency or ctr_decline > 0.4:
                return FatigueStatus.EXHAUSTED
            return FatigueStatus.FATIGUED

        if fatigue_score >= 0.7:
            return FatigueStatus.FATIGUED
        elif fatigue_score >= 0.4:
            return FatigueStatus.WARNING
        return FatigueStatus.HEALTHY

    def _generate_recommendation(
        self, status: FatigueStatus, signals: list[FatigueSignal], days_active: int
    ) -> str:
        """Generate actionable recommendation."""
        if status == FatigueStatus.EXHAUSTED:
            return "Immediately pause creative and replace with fresh variant. Audience has been overexposed."
        elif status == FatigueStatus.FATIGUED:
            return "Creative is fatigued. Queue replacement and reduce impression share."
        elif status == FatigueStatus.WARNING:
            signal_types = [s.signal_type for s in signals]
            if "frequency_cap" in signal_types:
                return "Frequency rising — consider expanding audience or reducing budget share."
            return "Early fatigue signals detected. Monitor closely over next 48 hours."
        return "Creative is performing well. No action needed."

    def _compute_replacement_priority(self, status: FatigueStatus, fatigue_score: float) -> int:
        """Compute replacement urgency (0-10)."""
        if status == FatigueStatus.EXHAUSTED:
            return 10
        elif status == FatigueStatus.FATIGUED:
            return int(5 + fatigue_score * 4)
        elif status == FatigueStatus.WARNING:
            return int(fatigue_score * 4)
        return 0
