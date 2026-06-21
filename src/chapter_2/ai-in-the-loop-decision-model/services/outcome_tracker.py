"""
Outcome Tracker — tracks decision outcomes to improve routing over time.

Features:
- Records outcomes of autonomous and human-approved decisions
- Computes quality scores per decision type and confidence band
- Recommends autonomy threshold adjustments based on historical performance
- Decay weighting (recent outcomes matter more)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum
import math


class DecisionOutcome(Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    NEUTRAL = "neutral"


class DecisionRoute(Enum):
    AUTONOMOUS = "autonomous"
    HUMAN_APPROVED = "human_approved"
    HUMAN_REJECTED = "human_rejected"
    EMERGENCY = "emergency"


@dataclass
class OutcomeRecord:
    """Record of a decision and its outcome."""
    decision_id: str
    decision_type: str
    route: DecisionRoute
    confidence_score: float
    risk_level: str
    outcome: DecisionOutcome
    impact_actual_usd: float = 0.0
    impact_predicted_usd: float = 0.0
    campaign_id: str = ""
    recorded_at: datetime = field(default_factory=datetime.utcnow)
    decision_made_at: Optional[datetime] = None
    notes: str = ""


@dataclass
class QualityScore:
    """Quality metrics for a decision category."""
    decision_type: str
    confidence_band: str  # e.g., "0.85-0.90"
    total_decisions: int
    success_count: int
    failure_count: int
    success_rate: float
    avg_impact_usd: float
    weighted_score: float  # Decay-weighted quality score


@dataclass
class AutonomyRecommendation:
    """Recommendation to adjust autonomy thresholds."""
    decision_type: str
    current_threshold: float
    recommended_threshold: float
    direction: str  # "increase", "decrease", "maintain"
    evidence_count: int
    confidence_in_recommendation: float
    reasoning: str


class OutcomeTracker:
    """
    Tracks and analyzes decision outcomes to inform autonomy adjustments.

    Uses exponential decay weighting so recent outcomes matter more than old ones.
    """

    def __init__(self, decay_half_life_days: float = 14.0, min_sample_size: int = 20):
        self.decay_half_life_days = decay_half_life_days
        self.min_sample_size = min_sample_size
        self._records: list[OutcomeRecord] = []

    def record_outcome(self, record: OutcomeRecord) -> None:
        """Record a decision outcome."""
        self._records.append(record)

    def get_quality_score(
        self, decision_type: str, confidence_min: float = 0.0, confidence_max: float = 1.0
    ) -> Optional[QualityScore]:
        """Compute quality score for a decision type within a confidence band."""
        relevant = [
            r for r in self._records
            if r.decision_type == decision_type
            and confidence_min <= r.confidence_score < confidence_max
        ]

        if len(relevant) < self.min_sample_size:
            return None

        now = datetime.utcnow()
        total_weight = 0.0
        success_weight = 0.0
        total_impact = 0.0
        success_count = 0
        failure_count = 0

        for record in relevant:
            weight = self._decay_weight(record.recorded_at, now)
            total_weight += weight
            if record.outcome == DecisionOutcome.SUCCESS:
                success_weight += weight
                success_count += 1
            elif record.outcome == DecisionOutcome.FAILURE:
                failure_count += 1
            total_impact += abs(record.impact_actual_usd)

        weighted_score = success_weight / total_weight if total_weight > 0 else 0.0
        success_rate = success_count / len(relevant) if relevant else 0.0
        avg_impact = total_impact / len(relevant) if relevant else 0.0

        band_label = f"{confidence_min:.2f}-{confidence_max:.2f}"
        return QualityScore(
            decision_type=decision_type,
            confidence_band=band_label,
            total_decisions=len(relevant),
            success_count=success_count,
            failure_count=failure_count,
            success_rate=success_rate,
            avg_impact_usd=avg_impact,
            weighted_score=weighted_score,
        )

    def recommend_autonomy_adjustment(
        self, decision_type: str, current_threshold: float = 0.85
    ) -> AutonomyRecommendation:
        """
        Recommend whether to raise, lower, or maintain the autonomy threshold.

        Logic:
        - If quality > 0.92 in the band just below threshold → recommend lowering (more autonomy)
        - If quality < 0.80 in the band just above threshold → recommend raising (less autonomy)
        - Otherwise → maintain
        """
        # Check quality in the band just below current threshold
        lower_band = self.get_quality_score(
            decision_type,
            confidence_min=max(0.0, current_threshold - 0.10),
            confidence_max=current_threshold,
        )

        # Check quality in the band just above threshold
        upper_band = self.get_quality_score(
            decision_type,
            confidence_min=current_threshold,
            confidence_max=min(1.0, current_threshold + 0.10),
        )

        evidence_count = 0
        if lower_band:
            evidence_count += lower_band.total_decisions
        if upper_band:
            evidence_count += upper_band.total_decisions

        # Default recommendation: maintain
        direction = "maintain"
        recommended = current_threshold
        reasoning = "Insufficient evidence or performance is within acceptable bounds."
        confidence_in_rec = 0.5

        if upper_band and upper_band.weighted_score < 0.80:
            # Autonomous decisions are failing too often — increase threshold
            direction = "increase"
            recommended = min(0.95, current_threshold + 0.05)
            reasoning = (
                f"Autonomous decisions (confidence {current_threshold:.0%}+) have "
                f"quality score {upper_band.weighted_score:.2f} < 0.80. "
                f"Recommend raising threshold to reduce failures."
            )
            confidence_in_rec = min(0.9, upper_band.total_decisions / 50)

        elif lower_band and lower_band.weighted_score > 0.92:
            # Decisions just below threshold succeed often — decrease threshold
            direction = "decrease"
            recommended = max(0.50, current_threshold - 0.05)
            reasoning = (
                f"Decisions in confidence band {lower_band.confidence_band} have "
                f"quality score {lower_band.weighted_score:.2f} > 0.92. "
                f"These could safely be autonomous."
            )
            confidence_in_rec = min(0.9, lower_band.total_decisions / 50)

        return AutonomyRecommendation(
            decision_type=decision_type,
            current_threshold=current_threshold,
            recommended_threshold=recommended,
            direction=direction,
            evidence_count=evidence_count,
            confidence_in_recommendation=confidence_in_rec,
            reasoning=reasoning,
        )

    def get_summary(self, days: int = 30) -> dict:
        """Get summary statistics for the last N days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        recent = [r for r in self._records if r.recorded_at >= cutoff]

        by_route = {}
        for record in recent:
            route = record.route.value
            if route not in by_route:
                by_route[route] = {"total": 0, "success": 0, "failure": 0}
            by_route[route]["total"] += 1
            if record.outcome == DecisionOutcome.SUCCESS:
                by_route[route]["success"] += 1
            elif record.outcome == DecisionOutcome.FAILURE:
                by_route[route]["failure"] += 1

        return {
            "period_days": days,
            "total_decisions": len(recent),
            "by_route": by_route,
            "decision_types": list(set(r.decision_type for r in recent)),
        }

    def _decay_weight(self, recorded_at: datetime, now: datetime) -> float:
        """Compute exponential decay weight based on age."""
        age_days = (now - recorded_at).total_seconds() / 86400
        return math.exp(-math.log(2) * age_days / self.decay_half_life_days)
