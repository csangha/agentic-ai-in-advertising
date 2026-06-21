"""
Tests for the Pacing Engine — ensures budget delivery is tracked correctly.
"""

import pytest
from datetime import datetime, timedelta
from services.pacing_engine import PacingEngine, PacingStrategy, PacingStatus


@pytest.fixture
def engine():
    return PacingEngine()


class TestPacingComputation:
    """Pacing ratio and status calculation."""

    def test_on_track_even_pacing(self, engine):
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)
        now = datetime(2026, 1, 16)  # Halfway

        result = engine.compute_pacing(
            campaign_id="camp-001",
            total_budget=30000,
            total_spent=15000,  # Exactly half = on track
            start_date=start, end_date=end,
            strategy=PacingStrategy.EVEN, now=now,
        )
        assert result.status == PacingStatus.ON_TRACK
        assert 0.90 <= result.pacing_ratio <= 1.10

    def test_over_pacing_detected(self, engine):
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)
        now = datetime(2026, 1, 11)  # ~1/3 through

        result = engine.compute_pacing(
            campaign_id="camp-001",
            total_budget=30000,
            total_spent=18000,  # Spent 60% in first third
            start_date=start, end_date=end,
            strategy=PacingStrategy.EVEN, now=now,
        )
        assert result.status in [PacingStatus.OVER_PACING, PacingStatus.CRITICAL_OVER]
        assert result.pacing_ratio > 1.20

    def test_under_pacing_detected(self, engine):
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)
        now = datetime(2026, 1, 21)  # ~2/3 through

        result = engine.compute_pacing(
            campaign_id="camp-001",
            total_budget=30000,
            total_spent=8000,  # Spent only 27% at 2/3 mark
            start_date=start, end_date=end,
            strategy=PacingStrategy.EVEN, now=now,
        )
        assert result.status == PacingStatus.UNDER_PACING
        assert result.pacing_ratio < 0.80

    def test_exhausted_budget(self, engine):
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)
        now = datetime(2026, 1, 15)

        result = engine.compute_pacing(
            campaign_id="camp-001",
            total_budget=30000,
            total_spent=30000,  # All spent
            start_date=start, end_date=end,
            strategy=PacingStrategy.EVEN, now=now,
        )
        assert result.status == PacingStatus.EXHAUSTED
        assert result.budget_remaining == 0


class TestPacingStrategies:
    """Different pacing strategies produce different expected spend curves."""

    def test_front_loaded_expects_more_early(self, engine):
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)
        now = datetime(2026, 1, 8)  # ~25% through

        front = engine.compute_pacing(
            campaign_id="camp-001", total_budget=30000, total_spent=10000,
            start_date=start, end_date=end,
            strategy=PacingStrategy.FRONT_LOADED, now=now,
        )
        even = engine.compute_pacing(
            campaign_id="camp-001", total_budget=30000, total_spent=10000,
            start_date=start, end_date=end,
            strategy=PacingStrategy.EVEN, now=now,
        )
        # Front-loaded expects MORE spend early, so same actual spend looks more on-track
        assert front.expected_spend > even.expected_spend

    def test_back_loaded_expects_less_early(self, engine):
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)
        now = datetime(2026, 1, 8)

        back = engine.compute_pacing(
            campaign_id="camp-001", total_budget=30000, total_spent=5000,
            start_date=start, end_date=end,
            strategy=PacingStrategy.BACK_LOADED, now=now,
        )
        even = engine.compute_pacing(
            campaign_id="camp-001", total_budget=30000, total_spent=5000,
            start_date=start, end_date=end,
            strategy=PacingStrategy.EVEN, now=now,
        )
        assert back.expected_spend < even.expected_spend


class TestProjections:
    """Exhaustion date projections."""

    def test_projects_exhaustion_date(self, engine):
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)
        now = datetime(2026, 1, 11)

        result = engine.compute_pacing(
            campaign_id="camp-001", total_budget=30000, total_spent=15000,
            start_date=start, end_date=end,
            strategy=PacingStrategy.EVEN, now=now,
        )
        # Spending $1500/day for 10 days = projects running out in ~20 days total
        assert result.projected_exhaustion_date is not None

    def test_daily_budget_needed_calculation(self, engine):
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)
        now = datetime(2026, 1, 21)  # 10 days remaining

        result = engine.compute_pacing(
            campaign_id="camp-001", total_budget=30000, total_spent=20000,
            start_date=start, end_date=end,
            strategy=PacingStrategy.EVEN, now=now,
        )
        # $10,000 remaining / 10 days = $1,000/day needed
        assert abs(result.daily_budget_needed - 1000) < 10
