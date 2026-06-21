"""
Bid Manager — autonomous bid optimization with guardrails.

Features:
- Target CPA bidding strategy
- Bounded changes (±15% per adjustment)
- Time-of-day multipliers
- Platform-specific bid logic
- Minimum/maximum bid enforcement
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum
import math


class BidStrategy(Enum):
    TARGET_CPA = "target_cpa"
    TARGET_ROAS = "target_roas"
    MAXIMIZE_CONVERSIONS = "maximize_conversions"
    MANUAL = "manual"


class BidDirection(Enum):
    INCREASE = "increase"
    DECREASE = "decrease"
    HOLD = "hold"


@dataclass
class BidContext:
    """Current context for a bid decision."""
    campaign_id: str
    platform: str
    ad_group_id: str
    current_bid: float
    current_cpa: float
    target_cpa: float
    conversions_last_24h: int
    spend_last_24h: float
    impressions_last_24h: int
    hour_of_day: int  # 0-23
    day_of_week: int  # 0=Monday, 6=Sunday
    competition_index: float = 1.0  # 1.0 = normal, >1 = high competition


@dataclass
class BidAdjustment:
    """A computed bid adjustment with reasoning."""
    campaign_id: str
    platform: str
    ad_group_id: str
    previous_bid: float
    new_bid: float
    change_pct: float
    direction: BidDirection
    reasoning: str
    time_multiplier: float = 1.0
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    guardrail_applied: bool = False
    guardrail_reason: str = ""


@dataclass
class BidManagerConfig:
    """Configuration for the bid manager."""
    strategy: BidStrategy = BidStrategy.TARGET_CPA
    max_change_pct: float = 0.15  # ±15% per adjustment
    min_bid: float = 0.10
    max_bid: float = 50.00
    min_conversions_for_adjustment: int = 5
    learning_rate: float = 0.1  # How aggressively to chase target
    time_of_day_enabled: bool = True


class BidManager:
    """
    Manages bid optimization with target CPA strategy and guardrails.

    Key constraints:
    - No single adjustment exceeds ±15%
    - Time-of-day multipliers applied for hourly optimization
    - Minimum data threshold before adjustments
    - Min/max bid bounds enforced
    """

    # Time-of-day performance multipliers (index = hour)
    # Values > 1.0 = historically higher conversion rate
    DEFAULT_TIME_MULTIPLIERS = [
        0.6, 0.5, 0.4, 0.4, 0.5, 0.6,  # 00-05 (low activity)
        0.8, 0.9, 1.1, 1.2, 1.3, 1.2,  # 06-11 (morning ramp)
        1.1, 1.2, 1.3, 1.3, 1.2, 1.1,  # 12-17 (afternoon)
        1.3, 1.4, 1.5, 1.4, 1.2, 0.9,  # 18-23 (evening peak)
    ]

    def __init__(self, config: Optional[BidManagerConfig] = None):
        self.config = config or BidManagerConfig()
        self._adjustment_history: list[BidAdjustment] = []
        self._time_multipliers = self.DEFAULT_TIME_MULTIPLIERS.copy()

    def compute_adjustment(self, context: BidContext) -> BidAdjustment:
        """
        Compute optimal bid adjustment given current performance context.

        Uses target CPA strategy with bounded changes.
        """
        # Check minimum data threshold
        if context.conversions_last_24h < self.config.min_conversions_for_adjustment:
            return BidAdjustment(
                campaign_id=context.campaign_id,
                platform=context.platform,
                ad_group_id=context.ad_group_id,
                previous_bid=context.current_bid,
                new_bid=context.current_bid,
                change_pct=0.0,
                direction=BidDirection.HOLD,
                reasoning=f"Insufficient conversions ({context.conversions_last_24h}) for adjustment. Min: {self.config.min_conversions_for_adjustment}",
                confidence=0.3,
            )

        # Compute raw adjustment based on CPA gap
        cpa_ratio = context.current_cpa / context.target_cpa
        raw_change = self._compute_raw_change(cpa_ratio)

        # Apply time-of-day multiplier
        time_mult = 1.0
        if self.config.time_of_day_enabled:
            time_mult = self._get_time_multiplier(context.hour_of_day)
            raw_change *= time_mult

        # Apply competition adjustment
        raw_change *= context.competition_index

        # Bound the change
        bounded_change, guardrail_applied = self._bound_change(raw_change)

        # Compute new bid
        new_bid = context.current_bid * (1 + bounded_change)
        new_bid = self._enforce_bid_bounds(new_bid)

        # Final change percentage
        actual_change = (new_bid - context.current_bid) / context.current_bid if context.current_bid > 0 else 0.0

        # Determine direction
        if actual_change > 0.001:
            direction = BidDirection.INCREASE
        elif actual_change < -0.001:
            direction = BidDirection.DECREASE
        else:
            direction = BidDirection.HOLD

        # Reasoning
        reasoning = self._generate_reasoning(
            context, cpa_ratio, bounded_change, time_mult, direction
        )

        # Confidence based on data volume
        confidence = min(0.95, 0.5 + context.conversions_last_24h * 0.02)

        adjustment = BidAdjustment(
            campaign_id=context.campaign_id,
            platform=context.platform,
            ad_group_id=context.ad_group_id,
            previous_bid=context.current_bid,
            new_bid=round(new_bid, 2),
            change_pct=round(actual_change, 4),
            direction=direction,
            reasoning=reasoning,
            time_multiplier=time_mult,
            confidence=confidence,
            guardrail_applied=guardrail_applied,
            guardrail_reason=f"Change bounded to ±{self.config.max_change_pct:.0%}" if guardrail_applied else "",
        )

        self._adjustment_history.append(adjustment)
        return adjustment

    def _compute_raw_change(self, cpa_ratio: float) -> float:
        """
        Compute raw bid change from CPA ratio.

        Logic:
        - CPA > target → decrease bid (negative change)
        - CPA < target → increase bid (positive change)
        - Uses logarithmic scaling to dampen extreme changes
        """
        if cpa_ratio <= 0:
            return 0.0

        # Inverse: if CPA is above target, we want to reduce bid
        # log(1/cpa_ratio) gives negative when CPA > target, positive when CPA < target
        raw = math.log(1 / cpa_ratio) * self.config.learning_rate
        return raw

    def _bound_change(self, raw_change: float) -> tuple[float, bool]:
        """Enforce ±15% maximum change per adjustment."""
        max_change = self.config.max_change_pct
        if abs(raw_change) > max_change:
            bounded = max_change if raw_change > 0 else -max_change
            return bounded, True
        return raw_change, False

    def _enforce_bid_bounds(self, bid: float) -> float:
        """Enforce minimum and maximum bid limits."""
        return max(self.config.min_bid, min(self.config.max_bid, bid))

    def _get_time_multiplier(self, hour: int) -> float:
        """Get time-of-day performance multiplier."""
        if 0 <= hour < len(self._time_multipliers):
            return self._time_multipliers[hour]
        return 1.0

    def set_time_multipliers(self, multipliers: list[float]) -> None:
        """Update time-of-day multipliers from learned performance data."""
        if len(multipliers) == 24:
            self._time_multipliers = multipliers

    def _generate_reasoning(
        self, context: BidContext, cpa_ratio: float, change: float,
        time_mult: float, direction: BidDirection
    ) -> str:
        """Generate human-readable reasoning for the adjustment."""
        if direction == BidDirection.HOLD:
            return "Bid held — CPA is within acceptable range of target."

        cpa_status = "above" if cpa_ratio > 1 else "below"
        deviation = abs(cpa_ratio - 1) * 100

        parts = [f"CPA ${context.current_cpa:.2f} is {deviation:.0f}% {cpa_status} target ${context.target_cpa:.2f}."]

        if direction == BidDirection.DECREASE:
            parts.append(f"Decreasing bid by {abs(change):.1%} to reduce CPA.")
        else:
            parts.append(f"Increasing bid by {change:.1%} to capture more conversions at favorable CPA.")

        if time_mult != 1.0:
            parts.append(f"Time multiplier: {time_mult:.2f} (hour {context.hour_of_day}).")

        return " ".join(parts)

    def get_adjustment_history(self, campaign_id: str, hours: int = 24) -> list[BidAdjustment]:
        """Get recent adjustment history for a campaign."""
        cutoff = datetime.utcnow()
        from datetime import timedelta
        cutoff = cutoff - timedelta(hours=hours)
        return [
            a for a in self._adjustment_history
            if a.campaign_id == campaign_id and a.timestamp > cutoff
        ]
