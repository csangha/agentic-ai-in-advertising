"""
Pacing Engine — budget delivery tracking and projection.

Monitors spend velocity against the planned curve and detects over/under-delivery.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


class PacingStatus(str, Enum):
    ON_TRACK = "ON_TRACK"
    OVER_PACING = "OVER_PACING"
    UNDER_PACING = "UNDER_PACING"
    CRITICAL_OVER = "CRITICAL_OVER"
    EXHAUSTED = "EXHAUSTED"


class PacingStrategy(str, Enum):
    EVEN = "even"
    FRONT_LOADED = "front_loaded"
    BACK_LOADED = "back_loaded"
    PERFORMANCE_ADAPTIVE = "performance_adaptive"


@dataclass
class PacingResult:
    campaign_id: str
    status: PacingStatus
    expected_spend: float
    actual_spend: float
    pacing_ratio: float  # actual / expected (1.0 = on track)
    budget_remaining: float
    days_remaining: int
    projected_exhaustion_date: Optional[datetime]
    daily_budget_needed: float  # To finish on time
    recommendation: str


class PacingEngine:
    """
    Computes budget pacing status and projects delivery.
    """

    def __init__(
        self,
        over_pacing_threshold: float = 1.20,  # 120% of expected
        under_pacing_threshold: float = 0.80,  # 80% of expected
        critical_over_threshold: float = 1.50,  # 150% of expected
    ):
        self.over_pacing_threshold = over_pacing_threshold
        self.under_pacing_threshold = under_pacing_threshold
        self.critical_over_threshold = critical_over_threshold

    def compute_pacing(
        self,
        campaign_id: str,
        total_budget: float,
        total_spent: float,
        start_date: datetime,
        end_date: datetime,
        strategy: PacingStrategy = PacingStrategy.EVEN,
        now: Optional[datetime] = None,
    ) -> PacingResult:
        """
        Compute pacing status for a campaign.

        Args:
            campaign_id: Campaign identifier
            total_budget: Total approved budget
            total_spent: Amount spent so far
            start_date: Campaign start date
            end_date: Campaign end date
            strategy: Pacing strategy
            now: Current time (defaults to utcnow)

        Returns:
            PacingResult with status, projections, and recommendations
        """
        now = now or datetime.utcnow()

        # Campaign duration
        total_days = max(1, (end_date - start_date).days)
        elapsed_days = max(0, (now - start_date).days)
        days_remaining = max(0, (end_date - now).days)

        # Compute expected spend based on strategy
        expected_spend = self._compute_expected_spend(
            total_budget, total_days, elapsed_days, strategy
        )

        # Pacing ratio
        pacing_ratio = total_spent / expected_spend if expected_spend > 0 else 0

        # Budget remaining
        budget_remaining = max(0, total_budget - total_spent)

        # Status classification
        status = self._classify_status(pacing_ratio, budget_remaining)

        # Projected exhaustion
        projected_exhaustion = self._project_exhaustion(
            total_spent, budget_remaining, elapsed_days, start_date
        )

        # Daily budget needed to finish on time
        daily_needed = budget_remaining / days_remaining if days_remaining > 0 else 0

        # Recommendation
        recommendation = self._generate_recommendation(
            status, pacing_ratio, daily_needed, days_remaining
        )

        return PacingResult(
            campaign_id=campaign_id,
            status=status,
            expected_spend=round(expected_spend, 2),
            actual_spend=round(total_spent, 2),
            pacing_ratio=round(pacing_ratio, 4),
            budget_remaining=round(budget_remaining, 2),
            days_remaining=days_remaining,
            projected_exhaustion_date=projected_exhaustion,
            daily_budget_needed=round(daily_needed, 2),
            recommendation=recommendation,
        )

    def _compute_expected_spend(
        self,
        total_budget: float,
        total_days: int,
        elapsed_days: int,
        strategy: PacingStrategy,
    ) -> float:
        """Compute expected spend at this point in time based on strategy."""
        progress = elapsed_days / total_days if total_days > 0 else 0

        if strategy == PacingStrategy.EVEN:
            # Linear: spend evenly across flight
            return total_budget * progress

        elif strategy == PacingStrategy.FRONT_LOADED:
            # Front-loaded: 60% in first half, 40% in second half
            if progress <= 0.5:
                return total_budget * 0.6 * (progress / 0.5)
            else:
                return total_budget * 0.6 + total_budget * 0.4 * ((progress - 0.5) / 0.5)

        elif strategy == PacingStrategy.BACK_LOADED:
            # Back-loaded: 40% in first half, 60% in second half
            if progress <= 0.5:
                return total_budget * 0.4 * (progress / 0.5)
            else:
                return total_budget * 0.4 + total_budget * 0.6 * ((progress - 0.5) / 0.5)

        elif strategy == PacingStrategy.PERFORMANCE_ADAPTIVE:
            # Adaptive: same as even but with wider tolerance bands
            return total_budget * progress

        return total_budget * progress

    def _classify_status(self, pacing_ratio: float, budget_remaining: float) -> PacingStatus:
        """Classify pacing health."""
        if budget_remaining <= 0:
            return PacingStatus.EXHAUSTED
        elif pacing_ratio >= self.critical_over_threshold:
            return PacingStatus.CRITICAL_OVER
        elif pacing_ratio >= self.over_pacing_threshold:
            return PacingStatus.OVER_PACING
        elif pacing_ratio <= self.under_pacing_threshold:
            return PacingStatus.UNDER_PACING
        else:
            return PacingStatus.ON_TRACK

    def _project_exhaustion(
        self,
        total_spent: float,
        budget_remaining: float,
        elapsed_days: int,
        start_date: datetime,
    ) -> Optional[datetime]:
        """Project when budget will be exhausted at current run rate."""
        if elapsed_days <= 0 or total_spent <= 0:
            return None

        daily_run_rate = total_spent / elapsed_days
        if daily_run_rate <= 0:
            return None

        days_until_exhaustion = budget_remaining / daily_run_rate
        return start_date + timedelta(days=elapsed_days + days_until_exhaustion)

    def _generate_recommendation(
        self,
        status: PacingStatus,
        pacing_ratio: float,
        daily_needed: float,
        days_remaining: int,
    ) -> str:
        """Generate actionable recommendation."""
        if status == PacingStatus.ON_TRACK:
            return "Pacing is healthy. No adjustment needed."
        elif status == PacingStatus.OVER_PACING:
            return f"Over-pacing at {pacing_ratio:.0%}. Reduce bids by {(pacing_ratio - 1) * 50:.0f}% to normalize."
        elif status == PacingStatus.CRITICAL_OVER:
            return f"CRITICAL over-pacing at {pacing_ratio:.0%}. Immediately reduce bids or pause low-performers."
        elif status == PacingStatus.UNDER_PACING:
            return (
                f"Under-pacing at {pacing_ratio:.0%}. "
                f"Need ${daily_needed:.2f}/day for remaining {days_remaining} days. Consider bid increases."
            )
        elif status == PacingStatus.EXHAUSTED:
            return "Budget exhausted. Campaign should be paused."
        return "Unable to determine recommendation."
