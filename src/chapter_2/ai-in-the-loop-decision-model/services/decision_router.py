"""
Decision Router — routes agent actions to appropriate authority (autonomous vs human).

Computes risk score and resolves authority based on:
- Autonomy level configuration
- Decision magnitude
- Reversibility
- Agent confidence
- Novelty of situation
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional
import uuid


class Authority(str, Enum):
    AUTONOMOUS = "AUTONOMOUS"  # Agent proceeds without human
    ESCALATE = "ESCALATE"  # Queue for human approval
    EMERGENCY = "EMERGENCY"  # Execute protective action, then notify


@dataclass
class DecisionRequest:
    decision_id: str = field(default_factory=lambda: f"dec-{uuid.uuid4().hex[:8]}")
    agent_id: str = ""
    campaign_id: str = ""
    function_area: str = ""  # "bidding", "creative", "budget", "messaging", "targeting", "crisis"
    proposed_action: Dict = field(default_factory=dict)
    reasoning: str = ""
    confidence_score: float = 0.8
    magnitude: float = 0.0  # 0-1: how much budget % is affected
    reversibility: float = 1.0  # 0-1: how easily undone (1=trivial)
    novelty_factor: float = 1.0  # 1=familiar, 2=novel situation
    deadline: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RoutingResult:
    decision_id: str
    authority: Authority
    risk_score: float
    reasoning: str
    approval_sla_minutes: Optional[int] = None
    default_on_timeout: Optional[str] = None  # "auto_approve", "auto_reject", "escalate"


@dataclass
class AutonomyPolicy:
    function_area: str
    autonomy_level: int  # 1-5
    risk_threshold: float  # Escalation trigger
    confidence_minimum: float  # Below this, always escalate
    default_on_timeout: str = "auto_reject"
    timeout_minutes: int = 120


class DecisionRouter:
    """
    Routes every agent decision through risk assessment.
    Determines whether to proceed autonomously or escalate to human.
    """

    # Default autonomy policies per function
    DEFAULT_POLICIES = {
        "bidding_small": AutonomyPolicy("bidding_small", 4, 0.3, 0.6, "auto_approve", 60),
        "bidding_large": AutonomyPolicy("bidding_large", 3, 0.2, 0.7, "auto_reject", 120),
        "budget_small": AutonomyPolicy("budget_small", 3, 0.25, 0.6, "auto_reject", 120),
        "budget_large": AutonomyPolicy("budget_large", 2, 0.15, 0.7, "auto_reject", 180),
        "creative_pause": AutonomyPolicy("creative_pause", 4, 0.3, 0.6, "auto_approve", 60),
        "creative_launch": AutonomyPolicy("creative_launch", 3, 0.2, 0.7, "auto_reject", 120),
        "audience_test": AutonomyPolicy("audience_test", 3, 0.25, 0.6, "auto_reject", 120),
        "messaging": AutonomyPolicy("messaging", 2, 0.15, 0.8, "auto_reject", 240),
        "crisis": AutonomyPolicy("crisis", 1, 0.0, 0.9, "auto_reject", 30),
    }

    def __init__(self, custom_policies: Dict[str, AutonomyPolicy] = None):
        self.policies = {**self.DEFAULT_POLICIES, **(custom_policies or {})}

    def route(self, request: DecisionRequest) -> RoutingResult:
        """
        Route a decision request to the appropriate authority.
        Returns AUTONOMOUS, ESCALATE, or EMERGENCY.
        """
        policy = self._resolve_policy(request)
        risk_score = self._compute_risk_score(request)

        # Emergency: critical safety situations bypass normal routing
        if request.function_area == "crisis" or risk_score > 0.9:
            return RoutingResult(
                decision_id=request.decision_id,
                authority=Authority.EMERGENCY,
                risk_score=risk_score,
                reasoning="Critical situation. Executing protective action immediately.",
            )

        # Low confidence: always escalate regardless of autonomy level
        if request.confidence_score < policy.confidence_minimum:
            return RoutingResult(
                decision_id=request.decision_id,
                authority=Authority.ESCALATE,
                risk_score=risk_score,
                reasoning=(
                    f"Confidence {request.confidence_score:.2f} below minimum "
                    f"{policy.confidence_minimum:.2f}. Escalating for human judgment."
                ),
                approval_sla_minutes=policy.timeout_minutes,
                default_on_timeout=policy.default_on_timeout,
            )

        # Risk score exceeds threshold: escalate
        if risk_score > policy.risk_threshold:
            return RoutingResult(
                decision_id=request.decision_id,
                authority=Authority.ESCALATE,
                risk_score=risk_score,
                reasoning=(
                    f"Risk score {risk_score:.3f} exceeds threshold "
                    f"{policy.risk_threshold:.3f} for {request.function_area}."
                ),
                approval_sla_minutes=policy.timeout_minutes,
                default_on_timeout=policy.default_on_timeout,
            )

        # Autonomy level check
        if policy.autonomy_level >= 3:
            return RoutingResult(
                decision_id=request.decision_id,
                authority=Authority.AUTONOMOUS,
                risk_score=risk_score,
                reasoning=(
                    f"Within authority (level {policy.autonomy_level}, "
                    f"risk {risk_score:.3f} < {policy.risk_threshold:.3f}). Proceeding."
                ),
            )
        else:
            return RoutingResult(
                decision_id=request.decision_id,
                authority=Authority.ESCALATE,
                risk_score=risk_score,
                reasoning=(
                    f"Autonomy level {policy.autonomy_level} requires human approval "
                    f"for {request.function_area}."
                ),
                approval_sla_minutes=policy.timeout_minutes,
                default_on_timeout=policy.default_on_timeout,
            )

    def _compute_risk_score(self, request: DecisionRequest) -> float:
        """
        Risk = magnitude × (1 - reversibility) × (1 - confidence) × novelty_factor

        Returns 0-1 (higher = riskier).
        """
        risk = (
            request.magnitude
            * (1.0 - request.reversibility)
            * (1.0 - request.confidence_score)
            * request.novelty_factor
        )
        return min(1.0, max(0.0, risk))

    def _resolve_policy(self, request: DecisionRequest) -> AutonomyPolicy:
        """Resolve the most specific policy for this decision."""
        # Try exact match first
        if request.function_area in self.policies:
            return self.policies[request.function_area]

        # Try with magnitude suffix
        suffix = "_small" if request.magnitude < 0.2 else "_large"
        key = f"{request.function_area}{suffix}"
        if key in self.policies:
            return self.policies[key]

        # Default: conservative
        return AutonomyPolicy(request.function_area, 2, 0.2, 0.7, "auto_reject", 120)
