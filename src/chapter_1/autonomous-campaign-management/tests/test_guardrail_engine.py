"""
Tests for the Guardrail Engine — ensures safety boundaries are never violated.
"""

import pytest
from services.guardrail_engine import (
    GuardrailEngine, GuardrailConfig, GuardrailType, ActionProposal, GuardrailResult
)


@pytest.fixture
def default_guardrails():
    """Standard guardrail configuration for testing."""
    return [
        GuardrailConfig(
            guardrail_id="gr-budget",
            campaign_id="camp-001",
            guardrail_type=GuardrailType.BUDGET_CAP,
            threshold_value=50000.0,
        ),
        GuardrailConfig(
            guardrail_id="gr-bid",
            campaign_id="camp-001",
            guardrail_type=GuardrailType.BID_CHANGE_LIMIT,
            threshold_value=0,
            threshold_pct=0.15,
        ),
        GuardrailConfig(
            guardrail_id="gr-cpa",
            campaign_id="camp-001",
            guardrail_type=GuardrailType.CPA_CEILING,
            threshold_value=0,
            threshold_pct=2.0,
            threshold_duration_hours=4.0,
        ),
        GuardrailConfig(
            guardrail_id="gr-spend-rate",
            campaign_id="camp-001",
            guardrail_type=GuardrailType.SPEND_RATE,
            threshold_value=0,
            threshold_pct=0.20,
            is_hard_limit=False,
        ),
        GuardrailConfig(
            guardrail_id="gr-audience",
            campaign_id="camp-001",
            guardrail_type=GuardrailType.AUDIENCE_CONCENTRATION,
            threshold_value=0,
            threshold_pct=0.70,
        ),
    ]


@pytest.fixture
def engine(default_guardrails):
    return GuardrailEngine(default_guardrails)


class TestBudgetCap:
    """Budget cap is a HARD LIMIT — never exceeded."""

    def test_within_budget_passes(self, engine):
        proposal = ActionProposal(
            campaign_id="camp-001",
            action_type="BUDGET_REALLOC",
            proposed_change={"additional_spend": 1000},
            current_metrics={"total_spend": 40000},
        )
        result = engine.evaluate(proposal)
        assert result.passed is True

    def test_at_budget_passes(self, engine):
        proposal = ActionProposal(
            campaign_id="camp-001",
            action_type="BUDGET_REALLOC",
            proposed_change={"additional_spend": 0},
            current_metrics={"total_spend": 50000},
        )
        result = engine.evaluate(proposal)
        assert result.passed is True

    def test_exceeds_budget_blocked(self, engine):
        proposal = ActionProposal(
            campaign_id="camp-001",
            action_type="BUDGET_REALLOC",
            proposed_change={"additional_spend": 5000},
            current_metrics={"total_spend": 48000},
        )
        result = engine.evaluate(proposal)
        assert result.passed is False
        assert result.action_blocked is True
        assert result.guardrail_type == "BUDGET_CAP"

    def test_exactly_at_limit_passes(self, engine):
        proposal = ActionProposal(
            campaign_id="camp-001",
            action_type="BUDGET_REALLOC",
            proposed_change={"additional_spend": 2000},
            current_metrics={"total_spend": 48000},
        )
        result = engine.evaluate(proposal)
        assert result.passed is True


class TestBidChangeLimit:
    """Bid changes bounded to ±15% per cycle."""

    def test_within_limit_passes(self, engine):
        proposal = ActionProposal(
            campaign_id="camp-001",
            action_type="BID_CHANGE",
            proposed_change={"bid_change_pct": 0.12},
            current_metrics={"total_spend": 20000},
        )
        result = engine.evaluate(proposal)
        assert result.passed is True

    def test_at_limit_passes(self, engine):
        proposal = ActionProposal(
            campaign_id="camp-001",
            action_type="BID_CHANGE",
            proposed_change={"bid_change_pct": 0.15},
            current_metrics={"total_spend": 20000},
        )
        result = engine.evaluate(proposal)
        assert result.passed is True

    def test_exceeds_limit_blocked(self, engine):
        proposal = ActionProposal(
            campaign_id="camp-001",
            action_type="BID_CHANGE",
            proposed_change={"bid_change_pct": 0.25},
            current_metrics={"total_spend": 20000},
        )
        result = engine.evaluate(proposal)
        assert result.passed is False
        assert result.action_blocked is True
        assert result.guardrail_type == "BID_CHANGE_LIMIT"

    def test_negative_bid_change_within_limit(self, engine):
        proposal = ActionProposal(
            campaign_id="camp-001",
            action_type="BID_CHANGE",
            proposed_change={"bid_change_pct": -0.10},
            current_metrics={"total_spend": 20000},
        )
        result = engine.evaluate(proposal)
        assert result.passed is True


class TestCPACircuitBreaker:
    """CPA circuit breaker: >200% of target for >4 hours triggers PAUSE."""

    def test_cpa_normal_passes(self, engine):
        proposal = ActionProposal(
            campaign_id="camp-001",
            action_type="BID_CHANGE",
            proposed_change={"bid_change_pct": 0.05},
            current_metrics={
                "total_spend": 20000,
                "current_cpa": 40,
                "target_cpa": 35,
                "hours_above_cpa_threshold": 0,
            },
        )
        result = engine.evaluate(proposal)
        assert result.passed is True

    def test_cpa_high_but_short_duration_passes(self, engine):
        proposal = ActionProposal(
            campaign_id="camp-001",
            action_type="BID_CHANGE",
            proposed_change={"bid_change_pct": 0.05},
            current_metrics={
                "total_spend": 20000,
                "current_cpa": 80,
                "target_cpa": 35,
                "hours_above_cpa_threshold": 2,
            },
        )
        result = engine.evaluate(proposal)
        assert result.passed is True  # Not yet 4 hours

    def test_cpa_circuit_breaker_triggers(self, engine):
        proposal = ActionProposal(
            campaign_id="camp-001",
            action_type="BID_CHANGE",
            proposed_change={"bid_change_pct": 0.05},
            current_metrics={
                "total_spend": 20000,
                "current_cpa": 80,
                "target_cpa": 35,
                "hours_above_cpa_threshold": 5,
            },
        )
        result = engine.evaluate(proposal)
        assert result.passed is False
        assert result.action_blocked is True
        assert result.escalation_required is True
        assert result.guardrail_type == "CPA_CEILING"


class TestSpendRate:
    """Spend rate: >20% daily budget reallocation requires escalation."""

    def test_small_reallocation_passes(self, engine):
        proposal = ActionProposal(
            campaign_id="camp-001",
            action_type="BUDGET_REALLOC",
            proposed_change={"budget_shift": 200, "additional_spend": 0},
            current_metrics={"total_spend": 20000, "daily_budget": 2000},
        )
        result = engine.evaluate(proposal)
        assert result.passed is True

    def test_large_reallocation_escalates(self, engine):
        proposal = ActionProposal(
            campaign_id="camp-001",
            action_type="BUDGET_REALLOC",
            proposed_change={"budget_shift": 600, "additional_spend": 0},
            current_metrics={"total_spend": 20000, "daily_budget": 2000},
        )
        result = engine.evaluate(proposal)
        assert result.passed is False
        assert result.escalation_required is True
        assert result.action_blocked is False  # Soft limit


class TestAudienceConcentration:
    """Proven audience must be ≥70% of budget."""

    def test_sufficient_proven_audience_passes(self, engine):
        proposal = ActionProposal(
            campaign_id="camp-001",
            action_type="AUDIENCE_EXPAND",
            proposed_change={},
            current_metrics={"total_spend": 20000, "proven_audience_budget_pct": 0.80},
        )
        result = engine.evaluate(proposal)
        assert result.passed is True

    def test_insufficient_proven_audience_blocked(self, engine):
        proposal = ActionProposal(
            campaign_id="camp-001",
            action_type="AUDIENCE_EXPAND",
            proposed_change={},
            current_metrics={"total_spend": 20000, "proven_audience_budget_pct": 0.60},
        )
        result = engine.evaluate(proposal)
        assert result.passed is False
        assert result.guardrail_type == "AUDIENCE_CONCENTRATION"
