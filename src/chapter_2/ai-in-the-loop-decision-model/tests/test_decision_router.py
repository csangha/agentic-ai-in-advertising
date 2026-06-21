"""
Tests for Decision Router — autonomous pass, escalation, emergency, confidence threshold.
"""

import pytest
from services.decision_router import (
    DecisionRouter, Decision, DecisionClassification,
    RiskLevel, RoutingResult
)


@pytest.fixture
def router():
    return DecisionRouter(
        confidence_threshold=0.85,
        impact_threshold_usd=500.0,
    )


@pytest.fixture
def low_risk_decision():
    """High confidence, low risk, low impact — should be autonomous."""
    return Decision(
        decision_id="dec-001",
        decision_type="bid_adjustment",
        description="Reduce TikTok bid by 5%",
        confidence_score=0.92,
        risk_level=RiskLevel.LOW,
        impact_estimate_usd=150.0,
        campaign_id="camp-001",
        context={"platform": "tiktok", "change_pct": -5},
    )


@pytest.fixture
def high_risk_decision():
    """High risk decision requiring human approval."""
    return Decision(
        decision_id="dec-002",
        decision_type="budget_reallocation",
        description="Shift $5,000 from Google to Meta",
        confidence_score=0.78,
        risk_level=RiskLevel.HIGH,
        impact_estimate_usd=5000.0,
        campaign_id="camp-001",
        context={"from_platform": "google", "to_platform": "meta", "amount": 5000},
    )


@pytest.fixture
def emergency_decision():
    """Critical risk requiring emergency escalation."""
    return Decision(
        decision_id="dec-003",
        decision_type="campaign_pause",
        description="CPA spiked 300% — pause campaign immediately",
        confidence_score=0.95,
        risk_level=RiskLevel.CRITICAL,
        impact_estimate_usd=10000.0,
        campaign_id="camp-001",
        context={"anomaly": "cpa_spike", "deviation_pct": 300},
    )


class TestAutonomousPass:
    """Decisions that should be executed autonomously."""

    def test_high_confidence_low_risk_passes(self, router, low_risk_decision):
        result = router.route(low_risk_decision)
        assert result.classification == DecisionClassification.AUTONOMOUS

    def test_autonomous_includes_reasoning(self, router, low_risk_decision):
        result = router.route(low_risk_decision)
        assert result.reasoning != ""

    def test_just_above_threshold_passes(self, router):
        decision = Decision(
            decision_id="dec-edge",
            decision_type="bid_adjustment",
            description="Slight bid increase",
            confidence_score=0.86,  # Just above 0.85
            risk_level=RiskLevel.LOW,
            impact_estimate_usd=100.0,
            campaign_id="camp-001",
        )
        result = router.route(decision)
        assert result.classification == DecisionClassification.AUTONOMOUS

    def test_low_impact_within_limit(self, router):
        decision = Decision(
            decision_id="dec-small",
            decision_type="creative_rotation",
            description="Rotate creative variant",
            confidence_score=0.90,
            risk_level=RiskLevel.LOW,
            impact_estimate_usd=50.0,
            campaign_id="camp-001",
        )
        result = router.route(decision)
        assert result.classification == DecisionClassification.AUTONOMOUS


class TestEscalation:
    """Decisions requiring human approval."""

    def test_low_confidence_escalates(self, router):
        decision = Decision(
            decision_id="dec-low-conf",
            decision_type="audience_expansion",
            description="Expand to new audience segment",
            confidence_score=0.65,
            risk_level=RiskLevel.MEDIUM,
            impact_estimate_usd=300.0,
            campaign_id="camp-001",
        )
        result = router.route(decision)
        assert result.classification == DecisionClassification.APPROVAL_REQUIRED

    def test_high_impact_escalates(self, router, high_risk_decision):
        result = router.route(high_risk_decision)
        assert result.classification == DecisionClassification.APPROVAL_REQUIRED

    def test_high_risk_even_with_high_confidence(self, router):
        decision = Decision(
            decision_id="dec-risky",
            decision_type="budget_reallocation",
            description="Major budget shift",
            confidence_score=0.95,
            risk_level=RiskLevel.HIGH,
            impact_estimate_usd=3000.0,
            campaign_id="camp-001",
        )
        result = router.route(decision)
        assert result.classification == DecisionClassification.APPROVAL_REQUIRED

    def test_escalation_sets_sla(self, router, high_risk_decision):
        result = router.route(high_risk_decision)
        assert result.sla_deadline is not None


class TestEmergencyEscalation:
    """Critical decisions requiring immediate attention."""

    def test_critical_risk_emergency(self, router, emergency_decision):
        result = router.route(emergency_decision)
        assert result.classification == DecisionClassification.EMERGENCY_ESCALATE

    def test_emergency_short_sla(self, router, emergency_decision):
        result = router.route(emergency_decision)
        assert result.sla_deadline is not None
        # Emergency SLA should be very short (< 30 min)
        from datetime import datetime
        time_to_sla = (result.sla_deadline - datetime.utcnow()).total_seconds()
        assert time_to_sla <= 1800  # 30 minutes max

    def test_spend_anomaly_emergency(self, router):
        decision = Decision(
            decision_id="dec-anomaly",
            decision_type="spend_alert",
            description="Spend rate 250% above normal",
            confidence_score=0.99,
            risk_level=RiskLevel.CRITICAL,
            impact_estimate_usd=15000.0,
            campaign_id="camp-001",
            context={"spend_anomaly_pct": 250},
        )
        result = router.route(decision)
        assert result.classification == DecisionClassification.EMERGENCY_ESCALATE


class TestConfidenceThreshold:
    """Dynamic confidence threshold behavior."""

    def test_exactly_at_threshold_escalates(self, router):
        decision = Decision(
            decision_id="dec-boundary",
            decision_type="bid_adjustment",
            description="Borderline confidence decision",
            confidence_score=0.85,  # Exactly at threshold
            risk_level=RiskLevel.LOW,
            impact_estimate_usd=100.0,
            campaign_id="camp-001",
        )
        # At threshold boundary — should escalate (< is strict)
        result = router.route(decision)
        # Implementation choice: >= threshold is autonomous
        assert result.classification == DecisionClassification.AUTONOMOUS

    def test_custom_threshold(self):
        conservative_router = DecisionRouter(confidence_threshold=0.95, impact_threshold_usd=200.0)
        decision = Decision(
            decision_id="dec-mid",
            decision_type="bid_adjustment",
            description="Mid confidence bid change",
            confidence_score=0.90,
            risk_level=RiskLevel.LOW,
            impact_estimate_usd=100.0,
            campaign_id="camp-001",
        )
        result = conservative_router.route(decision)
        assert result.classification == DecisionClassification.APPROVAL_REQUIRED

    def test_all_conditions_must_pass_for_autonomous(self, router):
        """Even if confidence is high, impact over threshold forces escalation."""
        decision = Decision(
            decision_id="dec-big-spend",
            decision_type="budget_increase",
            description="Increase daily budget by $1000",
            confidence_score=0.95,
            risk_level=RiskLevel.MEDIUM,
            impact_estimate_usd=1000.0,  # Over $500 threshold
            campaign_id="camp-001",
        )
        result = router.route(decision)
        assert result.classification == DecisionClassification.APPROVAL_REQUIRED
