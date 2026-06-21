"""
Optimization Engine — decision logic for bid adjustments and budget allocation.

Operates within guardrail boundaries. Implements:
- Policy-aware bid scoring (efficiency × confidence × causal weight)
- Bounded bid adjustments (±15% max per cycle)
- Budget reallocation (max 20% shift per day without approval)
- Diminishing returns detection
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import math


@dataclass
class ChannelState:
    channel: str
    platform: str
    campaign_id: str
    spend: float
    conversions: float
    current_cpa: Optional[float]
    target_cpa: float
    current_roas: Optional[float]
    ctr: float
    impressions: int
    frequency: float
    confidence_score: float  # 0-1: how confident we are in this data
    incremental_lift_pct: float  # from experiments (default 0 = no evidence)


@dataclass
class OptimizationPolicy:
    max_bid_change_pct: float = 0.15  # ±15% per cycle
    max_budget_shift_pct: float = 0.20  # 20% daily max without approval
    min_confidence_score: float = 0.6  # Below this, escalate instead of act
    attribution_weight: float = 0.6
    causal_weight: float = 0.4
    saturation_frequency_threshold: float = 4.0  # Frequency at which diminishing returns start


@dataclass
class BidRecommendation:
    campaign_id: str
    platform: str
    current_bid: float
    recommended_bid: float
    change_pct: float
    reasoning: str
    confidence: float


@dataclass
class AllocationRecommendation:
    shifts: Dict[str, float]  # campaign_id → $ amount to shift (positive = increase, negative = decrease)
    reasoning: str
    total_shift: float
    requires_approval: bool


class OptimizationEngine:
    """Computes bid adjustments and budget allocations within guardrail boundaries."""

    def __init__(self, policy: OptimizationPolicy = None):
        self.policy = policy or OptimizationPolicy()

    def compute_effective_score(self, state: ChannelState) -> float:
        """
        Compute the effective optimization score for a channel.
        Combines attributed efficiency with causal evidence.

        Score > 1.0 = performing above target (consider scaling)
        Score < 1.0 = performing below target (consider reducing)
        """
        # Efficiency score: how well is CPA tracking vs target
        if state.current_cpa is None or state.current_cpa == 0:
            efficiency_score = 0.0
        else:
            efficiency_score = max(0.0, state.target_cpa / state.current_cpa)

        # Causal modifier from incrementality evidence
        causal_score = max(0.0, 1.0 + state.incremental_lift_pct / 100.0)

        # Weighted combination
        effective = (
            efficiency_score * self.policy.attribution_weight +
            causal_score * self.policy.causal_weight
        )

        return effective

    def recommend_bid_change(
        self,
        state: ChannelState,
        current_bid: float,
    ) -> BidRecommendation:
        """
        Recommend a bid adjustment bounded by ±max_bid_change_pct.

        Logic:
        - If CPA < target → increase bid (capture more volume)
        - If CPA > target → decrease bid (improve efficiency)
        - Magnitude proportional to distance from target, capped at max
        """
        if state.confidence_score < self.policy.min_confidence_score:
            return BidRecommendation(
                campaign_id=state.campaign_id,
                platform=state.platform,
                current_bid=current_bid,
                recommended_bid=current_bid,
                change_pct=0.0,
                reasoning=f"Confidence too low ({state.confidence_score:.2f} < {self.policy.min_confidence_score}). Escalating instead of acting.",
                confidence=state.confidence_score,
            )

        effective_score = self.compute_effective_score(state)

        # Convert score to bid change direction and magnitude
        # Score > 1 = good performance → increase bid to capture more
        # Score < 1 = poor performance → decrease bid to improve efficiency
        raw_change = (effective_score - 1.0) * 0.5  # Scale factor

        # Bound by max change
        bounded_change = max(
            -self.policy.max_bid_change_pct,
            min(self.policy.max_bid_change_pct, raw_change)
        )

        # Apply diminishing returns dampening
        if self._is_saturating(state):
            bounded_change = min(bounded_change, 0.0)  # Don't increase if saturating

        recommended_bid = current_bid * (1 + bounded_change)

        reasoning = (
            f"CPA ${state.current_cpa:.2f} vs target ${state.target_cpa:.2f} "
            f"(effective_score={effective_score:.2f}). "
            f"Bid {'increase' if bounded_change > 0 else 'decrease'} by {abs(bounded_change):.1%}."
        )

        if self._is_saturating(state):
            reasoning += f" Saturation detected (frequency={state.frequency:.1f})."

        return BidRecommendation(
            campaign_id=state.campaign_id,
            platform=state.platform,
            current_bid=current_bid,
            recommended_bid=round(recommended_bid, 4),
            change_pct=bounded_change,
            reasoning=reasoning,
            confidence=state.confidence_score,
        )

    def recommend_budget_reallocation(
        self,
        channels: List[ChannelState],
        total_daily_budget: float,
    ) -> AllocationRecommendation:
        """
        Recommend budget shifts between campaigns based on relative performance.
        Bounded by max_budget_shift_pct of daily budget.
        """
        if not channels:
            return AllocationRecommendation(
                shifts={}, reasoning="No channels to optimize.", total_shift=0, requires_approval=False
            )

        # Score each channel
        scored = [(ch, self.compute_effective_score(ch)) for ch in channels]
        avg_score = sum(s for _, s in scored) / len(scored) if scored else 1.0

        shifts = {}
        total_shift_amount = 0.0

        for channel, score in scored:
            # Channels above average get more, below average get less
            deviation = (score - avg_score) / avg_score if avg_score > 0 else 0
            shift_pct = deviation * 0.1  # Conservative: 10% of deviation
            shift_amount = channel.spend * shift_pct

            # Cap individual shifts
            max_shift = total_daily_budget * self.policy.max_budget_shift_pct * 0.5
            shift_amount = max(-max_shift, min(max_shift, shift_amount))

            if abs(shift_amount) > 1.0:  # Only include meaningful shifts
                shifts[channel.campaign_id] = round(shift_amount, 2)
                total_shift_amount += abs(shift_amount)

        # Check if total shift exceeds approval threshold
        max_total = total_daily_budget * self.policy.max_budget_shift_pct
        requires_approval = total_shift_amount > max_total

        reasoning = (
            f"Reallocation across {len(shifts)} campaigns. "
            f"Total shift: ${total_shift_amount:.2f} "
            f"({'requires approval' if requires_approval else 'within limits'})."
        )

        return AllocationRecommendation(
            shifts=shifts,
            reasoning=reasoning,
            total_shift=total_shift_amount,
            requires_approval=requires_approval,
        )

    def detect_diminishing_returns(self, state: ChannelState) -> bool:
        """Detect if a channel is experiencing diminishing returns (audience saturation)."""
        return self._is_saturating(state)

    def _is_saturating(self, state: ChannelState) -> bool:
        """Check if audience frequency suggests saturation."""
        return state.frequency >= self.policy.saturation_frequency_threshold
