"""
Guardrail Engine — evaluates proposed actions against campaign safety boundaries.

Every autonomous action MUST pass through this engine before execution.
Guardrails are hard constraints (not optimization targets).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import List, Optional


class GuardrailType(str, Enum):
    BUDGET_CAP = "BUDGET_CAP"
    CPA_CEILING = "CPA_CEILING"
    SPEND_RATE = "SPEND_RATE"
    BID_CHANGE_LIMIT = "BID_CHANGE_LIMIT"
    SENTIMENT_FLOOR = "SENTIMENT_FLOOR"
    BRAND_SAFETY = "BRAND_SAFETY"
    AUDIENCE_CONCENTRATION = "AUDIENCE_CONCENTRATION"
    ESCALATION_THRESHOLD = "ESCALATION_THRESHOLD"


@dataclass
class GuardrailConfig:
    guardrail_id: str
    campaign_id: str
    guardrail_type: GuardrailType
    threshold_value: float
    threshold_pct: Optional[float] = None
    threshold_duration_hours: Optional[float] = None
    action_on_breach: str = "block"  # block, alert, escalate, reduce
    is_hard_limit: bool = True
    enabled: bool = True


@dataclass
class GuardrailResult:
    passed: bool
    guardrail_id: Optional[str] = None
    guardrail_type: Optional[str] = None
    violation_message: Optional[str] = None
    current_value: Optional[float] = None
    threshold: Optional[float] = None
    action_blocked: bool = False
    escalation_required: bool = False


@dataclass
class ActionProposal:
    campaign_id: str
    action_type: str  # BID_CHANGE, BUDGET_REALLOC, AUDIENCE_EXPAND, etc.
    proposed_change: dict
    current_metrics: dict


class GuardrailEngine:
    """
    Evaluates proposed agent actions against all configured guardrails.
    Returns pass/fail with detailed violation information.
    """

    def __init__(self, guardrails: List[GuardrailConfig]):
        self.guardrails = [g for g in guardrails if g.enabled]

    def evaluate(self, proposal: ActionProposal) -> GuardrailResult:
        """
        Check a proposed action against ALL active guardrails.
        Returns the first violation found, or a pass result.
        """
        campaign_guardrails = [
            g for g in self.guardrails if g.campaign_id == proposal.campaign_id
        ]

        for guardrail in campaign_guardrails:
            result = self._check_single(guardrail, proposal)
            if not result.passed:
                return result

        return GuardrailResult(passed=True)

    def _check_single(self, guardrail: GuardrailConfig, proposal: ActionProposal) -> GuardrailResult:
        """Dispatch to the appropriate guardrail checker."""
        checkers = {
            GuardrailType.BUDGET_CAP: self._check_budget_cap,
            GuardrailType.CPA_CEILING: self._check_cpa_ceiling,
            GuardrailType.SPEND_RATE: self._check_spend_rate,
            GuardrailType.BID_CHANGE_LIMIT: self._check_bid_change_limit,
            GuardrailType.SENTIMENT_FLOOR: self._check_sentiment_floor,
            GuardrailType.AUDIENCE_CONCENTRATION: self._check_audience_concentration,
            GuardrailType.ESCALATION_THRESHOLD: self._check_escalation_threshold,
        }

        checker = checkers.get(guardrail.guardrail_type)
        if checker is None:
            return GuardrailResult(passed=True)

        return checker(guardrail, proposal)

    def _check_budget_cap(self, guardrail: GuardrailConfig, proposal: ActionProposal) -> GuardrailResult:
        """
        HARD LIMIT: Total spend must NEVER exceed budget cap.
        This is inviolable regardless of any other consideration.
        """
        current_spend = proposal.current_metrics.get("total_spend", 0)
        proposed_additional = proposal.proposed_change.get("additional_spend", 0)
        projected_spend = current_spend + proposed_additional

        if projected_spend > guardrail.threshold_value:
            return GuardrailResult(
                passed=False,
                guardrail_id=guardrail.guardrail_id,
                guardrail_type=guardrail.guardrail_type.value,
                violation_message=f"Budget cap exceeded: projected ${projected_spend:.2f} > cap ${guardrail.threshold_value:.2f}",
                current_value=projected_spend,
                threshold=guardrail.threshold_value,
                action_blocked=True,
                escalation_required=False,
            )
        return GuardrailResult(passed=True)

    def _check_cpa_ceiling(self, guardrail: GuardrailConfig, proposal: ActionProposal) -> GuardrailResult:
        """
        Circuit breaker: If CPA exceeds 200% of target for >4 hours, PAUSE + ESCALATE.
        """
        current_cpa = proposal.current_metrics.get("current_cpa", 0)
        target_cpa = proposal.current_metrics.get("target_cpa", 1)
        cpa_ratio = current_cpa / target_cpa if target_cpa > 0 else 0

        threshold_ratio = guardrail.threshold_pct or 2.0  # Default 200%
        duration_hours = guardrail.threshold_duration_hours or 4.0

        # Check if CPA has been above threshold for the duration
        hours_above = proposal.current_metrics.get("hours_above_cpa_threshold", 0)

        if cpa_ratio > threshold_ratio and hours_above >= duration_hours:
            return GuardrailResult(
                passed=False,
                guardrail_id=guardrail.guardrail_id,
                guardrail_type=guardrail.guardrail_type.value,
                violation_message=(
                    f"CPA circuit breaker: CPA ${current_cpa:.2f} is {cpa_ratio:.0%} of target "
                    f"for {hours_above:.1f}h (threshold: {threshold_ratio:.0%} for {duration_hours}h)"
                ),
                current_value=cpa_ratio,
                threshold=threshold_ratio,
                action_blocked=True,
                escalation_required=True,
            )
        return GuardrailResult(passed=True)

    def _check_spend_rate(self, guardrail: GuardrailConfig, proposal: ActionProposal) -> GuardrailResult:
        """
        Spend rate limiter: Cannot reallocate more than 20% of daily budget without approval.
        """
        daily_budget = proposal.current_metrics.get("daily_budget", 0)
        reallocation_amount = abs(proposal.proposed_change.get("budget_shift", 0))
        max_shift_pct = guardrail.threshold_pct or 0.20

        if daily_budget > 0:
            shift_pct = reallocation_amount / daily_budget
            if shift_pct > max_shift_pct:
                return GuardrailResult(
                    passed=False,
                    guardrail_id=guardrail.guardrail_id,
                    guardrail_type=guardrail.guardrail_type.value,
                    violation_message=(
                        f"Spend rate limit: reallocation {shift_pct:.1%} exceeds "
                        f"max {max_shift_pct:.1%} of daily budget without approval"
                    ),
                    current_value=shift_pct,
                    threshold=max_shift_pct,
                    action_blocked=False,
                    escalation_required=True,
                )
        return GuardrailResult(passed=True)

    def _check_bid_change_limit(self, guardrail: GuardrailConfig, proposal: ActionProposal) -> GuardrailResult:
        """
        Bid change limit: Maximum ±15% per optimization cycle.
        """
        bid_change_pct = abs(proposal.proposed_change.get("bid_change_pct", 0))
        max_change = guardrail.threshold_pct or 0.15

        if bid_change_pct > max_change:
            return GuardrailResult(
                passed=False,
                guardrail_id=guardrail.guardrail_id,
                guardrail_type=guardrail.guardrail_type.value,
                violation_message=(
                    f"Bid change limit: {bid_change_pct:.1%} exceeds max ±{max_change:.1%} per cycle"
                ),
                current_value=bid_change_pct,
                threshold=max_change,
                action_blocked=True,
                escalation_required=False,
            )
        return GuardrailResult(passed=True)

    def _check_sentiment_floor(self, guardrail: GuardrailConfig, proposal: ActionProposal) -> GuardrailResult:
        """
        Sentiment floor: Block creative generation if sentiment drops below threshold.
        """
        current_sentiment = proposal.current_metrics.get("current_sentiment", 1.0)
        threshold = guardrail.threshold_value or 0.75

        if current_sentiment < threshold:
            return GuardrailResult(
                passed=False,
                guardrail_id=guardrail.guardrail_id,
                guardrail_type=guardrail.guardrail_type.value,
                violation_message=(
                    f"Sentiment floor breach: current {current_sentiment:.2f} < threshold {threshold:.2f}"
                ),
                current_value=current_sentiment,
                threshold=threshold,
                action_blocked=True,
                escalation_required=True,
            )
        return GuardrailResult(passed=True)

    def _check_audience_concentration(self, guardrail: GuardrailConfig, proposal: ActionProposal) -> GuardrailResult:
        """
        Audience concentration: Maintain minimum 70% on proven audiences.
        """
        proven_audience_pct = proposal.current_metrics.get("proven_audience_budget_pct", 1.0)
        min_proven_pct = guardrail.threshold_pct or 0.70

        if proven_audience_pct < min_proven_pct:
            return GuardrailResult(
                passed=False,
                guardrail_id=guardrail.guardrail_id,
                guardrail_type=guardrail.guardrail_type.value,
                violation_message=(
                    f"Audience concentration: proven audience at {proven_audience_pct:.1%}, "
                    f"minimum required is {min_proven_pct:.1%}"
                ),
                current_value=proven_audience_pct,
                threshold=min_proven_pct,
                action_blocked=True,
                escalation_required=False,
            )
        return GuardrailResult(passed=True)

    def _check_escalation_threshold(self, guardrail: GuardrailConfig, proposal: ActionProposal) -> GuardrailResult:
        """
        Escalation: Any action affecting >30% of total budget requires human approval.
        """
        total_budget = proposal.current_metrics.get("total_budget", 0)
        impact_amount = abs(proposal.proposed_change.get("budget_impact", 0))
        max_pct = guardrail.threshold_pct or 0.30

        if total_budget > 0:
            impact_pct = impact_amount / total_budget
            if impact_pct > max_pct:
                return GuardrailResult(
                    passed=False,
                    guardrail_id=guardrail.guardrail_id,
                    guardrail_type=guardrail.guardrail_type.value,
                    violation_message=(
                        f"Escalation threshold: action affects {impact_pct:.1%} of total budget "
                        f"(>{max_pct:.1%} requires human approval)"
                    ),
                    current_value=impact_pct,
                    threshold=max_pct,
                    action_blocked=False,
                    escalation_required=True,
                )
        return GuardrailResult(passed=True)
