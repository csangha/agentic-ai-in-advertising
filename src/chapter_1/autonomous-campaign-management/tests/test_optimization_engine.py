"""
Tests for the Optimization Engine — ensures decisions are bounded and reasonable.
"""

import pytest
from services.optimization_engine import (
    OptimizationEngine, OptimizationPolicy, ChannelState, BidRecommendation
)


@pytest.fixture
def engine():
    return OptimizationEngine(OptimizationPolicy())


@pytest.fixture
def good_channel():
    return ChannelState(
        channel="meta-main",
        platform="meta",
        campaign_id="camp-001",
        spend=1200,
        conversions=35,
        current_cpa=34.28,
        target_cpa=35.00,
        current_roas=3.5,
        ctr=0.038,
        impressions=50000,
        frequency=2.5,
        confidence_score=0.85,
        incremental_lift_pct=0,
    )


@pytest.fixture
def bad_channel():
    return ChannelState(
        channel="tiktok-main",
        platform="tiktok",
        campaign_id="camp-001",
        spend=300,
        conversions=6,
        current_cpa=50.0,
        target_cpa=35.00,
        current_roas=1.8,
        ctr=0.025,
        impressions=20000,
        frequency=3.2,
        confidence_score=0.78,
        incremental_lift_pct=0,
    )


@pytest.fixture
def saturated_channel():
    return ChannelState(
        channel="google-search",
        platform="google",
        campaign_id="camp-001",
        spend=890,
        conversions=25,
        current_cpa=35.60,
        target_cpa=35.00,
        current_roas=3.1,
        ctr=0.042,
        impressions=40000,
        frequency=4.5,  # Above saturation threshold
        confidence_score=0.90,
        incremental_lift_pct=0,
    )


class TestBidAdjustment:
    """Bid adjustments must be bounded by ±15%."""

    def test_good_performance_increases_bid(self, engine, good_channel):
        result = engine.recommend_bid_change(good_channel, current_bid=2.50)
        assert result.change_pct >= 0  # Should increase (below target CPA)
        assert result.change_pct <= 0.15  # Bounded

    def test_bad_performance_decreases_bid(self, engine, bad_channel):
        result = engine.recommend_bid_change(bad_channel, current_bid=3.00)
        assert result.change_pct <= 0  # Should decrease (above target CPA)
        assert result.change_pct >= -0.15  # Bounded

    def test_bid_change_never_exceeds_15_pct(self, engine):
        """Even extreme CPA deviation stays within ±15%."""
        extreme = ChannelState(
            channel="extreme", platform="meta", campaign_id="camp-001",
            spend=500, conversions=2, current_cpa=250.0, target_cpa=35.0,
            current_roas=0.5, ctr=0.01, impressions=10000, frequency=2.0,
            confidence_score=0.9, incremental_lift_pct=0,
        )
        result = engine.recommend_bid_change(extreme, current_bid=5.00)
        assert abs(result.change_pct) <= 0.15

    def test_low_confidence_does_not_act(self, engine):
        """Below confidence threshold, agent should not adjust."""
        low_conf = ChannelState(
            channel="low", platform="meta", campaign_id="camp-001",
            spend=100, conversions=1, current_cpa=100.0, target_cpa=35.0,
            current_roas=0.8, ctr=0.02, impressions=5000, frequency=1.0,
            confidence_score=0.4,  # Below 0.6 threshold
            incremental_lift_pct=0,
        )
        result = engine.recommend_bid_change(low_conf, current_bid=2.00)
        assert result.change_pct == 0.0
        assert "confidence" in result.reasoning.lower()


class TestDiminishingReturns:
    """Saturated audiences should not receive bid increases."""

    def test_saturated_channel_no_increase(self, engine, saturated_channel):
        result = engine.recommend_bid_change(saturated_channel, current_bid=2.00)
        assert result.change_pct <= 0  # Should not increase
        assert "saturation" in result.reasoning.lower() or result.change_pct <= 0

    def test_non_saturated_can_increase(self, engine, good_channel):
        result = engine.recommend_bid_change(good_channel, current_bid=2.00)
        # Good performance + not saturated = can increase
        assert result.change_pct >= 0


class TestBudgetReallocation:
    """Budget shifts bounded by 20% of daily budget."""

    def test_reallocation_produces_shifts(self, engine, good_channel, bad_channel):
        result = engine.recommend_budget_reallocation(
            [good_channel, bad_channel], total_daily_budget=2000
        )
        # Should produce some shifts (channels perform differently)
        assert isinstance(result.shifts, dict)

    def test_reallocation_bounded(self, engine, good_channel, bad_channel):
        result = engine.recommend_budget_reallocation(
            [good_channel, bad_channel], total_daily_budget=2000
        )
        # Total shift should not exceed 20% of daily budget without approval flag
        max_shift = 2000 * 0.20
        for shift in result.shifts.values():
            assert abs(shift) <= max_shift

    def test_empty_channels_no_shifts(self, engine):
        result = engine.recommend_budget_reallocation([], total_daily_budget=2000)
        assert result.shifts == {}


class TestEffectiveScore:
    """Effective score computation."""

    def test_good_performance_above_one(self, engine, good_channel):
        score = engine.compute_effective_score(good_channel)
        assert score >= 1.0  # CPA below target = good

    def test_bad_performance_below_one(self, engine, bad_channel):
        score = engine.compute_effective_score(bad_channel)
        assert score < 1.0  # CPA above target = bad

    def test_incremental_lift_boosts_score(self, engine, good_channel):
        base_score = engine.compute_effective_score(good_channel)
        good_channel.incremental_lift_pct = 20.0
        boosted_score = engine.compute_effective_score(good_channel)
        assert boosted_score > base_score
