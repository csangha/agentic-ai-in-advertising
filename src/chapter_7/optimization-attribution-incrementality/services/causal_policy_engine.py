"""
Causal Policy Engine — optimization policies informed by incrementality evidence.

Features:
- Effective score computation (blends attribution + incrementality)
- Policy updates from experiment results
- Evidence decay (older experiments weighted less)
- Channel-level and tactic-level policies
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum
import math


class PolicyAction(Enum):
    INCREASE_SPEND = "increase_spend"
    MAINTAIN_SPEND = "maintain_spend"
    DECREASE_SPEND = "decrease_spend"
    PAUSE = "pause"
    TEST_FURTHER = "test_further"


@dataclass
class IncrementalityEvidence:
    """Evidence from an incrementality experiment."""
    experiment_id: str
    channel: str
    tactic: str  # e.g., "upper_funnel", "retargeting", "brand"
    incremental_lift: float  # e.g., 0.15 = 15% lift
    confidence_interval: tuple[float, float]
    p_value: float
    is_significant: bool
    cost_per_incremental: float
    experiment_date: datetime = field(default_factory=datetime.utcnow)
    sample_size: int = 0


@dataclass
class EffectiveScore:
    """Blended score combining attribution and incrementality evidence."""
    channel: str
    tactic: str
    attribution_score: float  # From last-click/data-driven attribution
    incrementality_score: float  # From experiments
    blended_score: float  # Weighted combination
    attribution_weight: float  # How much attribution contributes
    incrementality_weight: float  # How much incrementality contributes
    confidence: float  # Confidence in the blended score
    evidence_count: int  # Number of experiments informing this
    last_experiment_date: Optional[datetime] = None


@dataclass
class PolicyRecommendation:
    """A policy recommendation for a channel/tactic."""
    channel: str
    tactic: str
    action: PolicyAction
    current_spend_allocation: float
    recommended_allocation: float
    change_pct: float
    reasoning: str
    effective_score: float
    confidence: float
    evidence_freshness: str  # "fresh", "aging", "stale"


class CausalPolicyEngine:
    """
    Computes effective scores and policy recommendations based on
    causal (incrementality) evidence combined with attribution data.

    Key concept: The "effective score" blends:
    - Attribution data (frequent, responsive, but potentially biased)
    - Incrementality evidence (causal, but infrequent and noisy)

    Evidence decays over time — older experiments carry less weight.
    """

    def __init__(
        self,
        evidence_half_life_days: float = 60.0,
        min_evidence_for_policy: int = 1,
        default_attribution_weight: float = 0.6,
        stale_evidence_days: int = 90,
    ):
        self.evidence_half_life_days = evidence_half_life_days
        self.min_evidence_for_policy = min_evidence_for_policy
        self.default_attribution_weight = default_attribution_weight
        self.stale_evidence_days = stale_evidence_days
        self._evidence: list[IncrementalityEvidence] = []
        self._attribution_scores: dict[str, float] = {}  # "channel:tactic" → score

    def add_evidence(self, evidence: IncrementalityEvidence) -> None:
        """Add incrementality experiment evidence."""
        self._evidence.append(evidence)

    def set_attribution_score(self, channel: str, tactic: str, score: float) -> None:
        """Set the latest attribution-based score for a channel/tactic."""
        key = f"{channel}:{tactic}"
        self._attribution_scores[key] = score

    def compute_effective_score(self, channel: str, tactic: str) -> EffectiveScore:
        """
        Compute the effective score for a channel/tactic.

        Blends attribution and incrementality with evidence-age weighting.
        """
        key = f"{channel}:{tactic}"
        attribution_score = self._attribution_scores.get(key, 0.5)

        # Get relevant incrementality evidence
        relevant_evidence = [
            e for e in self._evidence
            if e.channel == channel and e.tactic == tactic and e.is_significant
        ]

        if not relevant_evidence:
            # No incrementality evidence — rely on attribution
            return EffectiveScore(
                channel=channel,
                tactic=tactic,
                attribution_score=attribution_score,
                incrementality_score=0.5,  # Neutral assumption
                blended_score=attribution_score,
                attribution_weight=1.0,
                incrementality_weight=0.0,
                confidence=0.4,  # Low confidence without causal evidence
                evidence_count=0,
            )

        # Compute decay-weighted incrementality score
        now = datetime.utcnow()
        weighted_lifts = []
        total_weight = 0.0

        for evidence in relevant_evidence:
            weight = self._decay_weight(evidence.experiment_date, now)
            weighted_lifts.append(evidence.incremental_lift * weight)
            total_weight += weight

        incrementality_score = sum(weighted_lifts) / total_weight if total_weight > 0 else 0.0

        # Normalize incrementality score to 0-1 range
        # Assume lift of 0.30+ is excellent (1.0), 0 is neutral (0.5), negative is bad
        normalized_incr = min(1.0, max(0.0, 0.5 + incrementality_score * 1.5))

        # Compute weights based on evidence freshness and quantity
        incr_weight = self._compute_incrementality_weight(relevant_evidence, now)
        attr_weight = 1.0 - incr_weight

        # Blend scores
        blended = attribution_score * attr_weight + normalized_incr * incr_weight

        # Confidence based on evidence strength
        confidence = min(0.95, 0.5 + len(relevant_evidence) * 0.1 + incr_weight * 0.3)

        last_date = max(e.experiment_date for e in relevant_evidence) if relevant_evidence else None

        return EffectiveScore(
            channel=channel,
            tactic=tactic,
            attribution_score=attribution_score,
            incrementality_score=round(normalized_incr, 3),
            blended_score=round(blended, 3),
            attribution_weight=round(attr_weight, 3),
            incrementality_weight=round(incr_weight, 3),
            confidence=round(confidence, 3),
            evidence_count=len(relevant_evidence),
            last_experiment_date=last_date,
        )

    def generate_policy(
        self, channels_tactics: list[tuple[str, str]], current_allocations: dict[str, float]
    ) -> list[PolicyRecommendation]:
        """
        Generate policy recommendations for all channel/tactic combinations.

        Args:
            channels_tactics: List of (channel, tactic) tuples
            current_allocations: Dict of "channel:tactic" → current spend %

        Returns:
            Sorted list of policy recommendations
        """
        recommendations = []

        scores = {}
        for channel, tactic in channels_tactics:
            effective = self.compute_effective_score(channel, tactic)
            scores[f"{channel}:{tactic}"] = effective

        # Compute recommended allocations (proportional to effective scores)
        total_score = sum(s.blended_score for s in scores.values())

        for key, effective in scores.items():
            channel, tactic = key.split(":", 1)
            current = current_allocations.get(key, 0.0)

            if total_score > 0:
                recommended = effective.blended_score / total_score
            else:
                recommended = 1.0 / len(scores)

            change_pct = (recommended - current) / current if current > 0 else 0.0

            # Determine action
            action = self._determine_action(effective, change_pct)

            # Evidence freshness
            freshness = self._evidence_freshness(effective.last_experiment_date)

            recommendations.append(PolicyRecommendation(
                channel=channel,
                tactic=tactic,
                action=action,
                current_spend_allocation=round(current, 4),
                recommended_allocation=round(recommended, 4),
                change_pct=round(change_pct, 4),
                reasoning=self._generate_reasoning(effective, action, freshness),
                effective_score=effective.blended_score,
                confidence=effective.confidence,
                evidence_freshness=freshness,
            ))

        # Sort by confidence descending
        recommendations.sort(key=lambda r: r.confidence, reverse=True)
        return recommendations

    def _decay_weight(self, evidence_date: datetime, now: datetime) -> float:
        """Compute exponential decay weight based on evidence age."""
        age_days = (now - evidence_date).total_seconds() / 86400
        return math.exp(-math.log(2) * age_days / self.evidence_half_life_days)

    def _compute_incrementality_weight(
        self, evidence: list[IncrementalityEvidence], now: datetime
    ) -> float:
        """
        Compute how much weight incrementality should get vs attribution.

        More recent, more numerous evidence = higher incrementality weight.
        """
        if not evidence:
            return 0.0

        # Freshness factor
        most_recent = max(e.experiment_date for e in evidence)
        age_days = (now - most_recent).total_seconds() / 86400
        freshness = math.exp(-age_days / self.stale_evidence_days)

        # Quantity factor
        quantity = min(1.0, len(evidence) * 0.25)

        # Combined: max 0.6 weight for incrementality
        weight = (freshness * 0.5 + quantity * 0.5) * 0.6

        return min(0.6, max(0.1, weight))

    def _determine_action(self, effective: EffectiveScore, change_pct: float) -> PolicyAction:
        """Determine policy action based on effective score and recommended change."""
        if effective.confidence < 0.4:
            return PolicyAction.TEST_FURTHER

        if effective.blended_score < 0.2:
            return PolicyAction.PAUSE

        if change_pct > 0.10:
            return PolicyAction.INCREASE_SPEND
        elif change_pct < -0.10:
            return PolicyAction.DECREASE_SPEND
        return PolicyAction.MAINTAIN_SPEND

    def _evidence_freshness(self, last_date: Optional[datetime]) -> str:
        """Classify evidence freshness."""
        if not last_date:
            return "none"
        age_days = (datetime.utcnow() - last_date).days
        if age_days <= 30:
            return "fresh"
        elif age_days <= self.stale_evidence_days:
            return "aging"
        return "stale"

    def _generate_reasoning(
        self, effective: EffectiveScore, action: PolicyAction, freshness: str
    ) -> str:
        """Generate reasoning for a policy recommendation."""
        parts = []

        if effective.evidence_count > 0:
            parts.append(
                f"Based on {effective.evidence_count} incrementality experiment(s) "
                f"(evidence: {freshness})."
            )
            parts.append(
                f"Incrementality score: {effective.incrementality_score:.2f}, "
                f"Attribution score: {effective.attribution_score:.2f}."
            )
        else:
            parts.append("No incrementality evidence available. Using attribution data only.")

        parts.append(f"Blended effective score: {effective.blended_score:.2f} (confidence: {effective.confidence:.0%}).")

        action_map = {
            PolicyAction.INCREASE_SPEND: "Recommend increasing spend allocation.",
            PolicyAction.MAINTAIN_SPEND: "Recommend maintaining current allocation.",
            PolicyAction.DECREASE_SPEND: "Recommend decreasing spend allocation.",
            PolicyAction.PAUSE: "Evidence suggests low incrementality. Consider pausing.",
            PolicyAction.TEST_FURTHER: "Insufficient evidence. Run an incrementality test.",
        }
        parts.append(action_map.get(action, ""))

        return " ".join(parts)
