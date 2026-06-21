"""
Attribution Service — computes multiple attribution models for campaign performance.

Models: last-click, first-click, linear, time-decay, data-driven (Shapley).
Clearly labeled as "directional estimates" — NOT causal proof.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class AttributionModel(str, Enum):
    LAST_CLICK = "last_click"
    FIRST_CLICK = "first_click"
    LINEAR = "linear"
    TIME_DECAY = "time_decay"
    DATA_DRIVEN = "data_driven"


@dataclass
class Touchpoint:
    channel: str
    platform: str
    timestamp: datetime
    interaction_type: str  # "impression", "click", "view"
    campaign_id: str


@dataclass
class AttributionResult:
    model: AttributionModel
    channel_contributions: Dict[str, float]  # channel → fraction of credit (sums to 1.0)
    campaign_contributions: Dict[str, float]  # campaign → fraction
    computed_at: datetime
    note: str = "Directional estimate only. Not causal proof. See incrementality for causal evidence."


class AttributionService:
    """
    Computes attribution across multiple models.
    Designed for daily batch computation over touchpoint data.
    """

    def compute(
        self,
        touchpoints: List[Touchpoint],
        model: AttributionModel = AttributionModel.LINEAR,
    ) -> AttributionResult:
        """Compute attribution for a conversion path using the specified model."""
        if not touchpoints:
            return AttributionResult(model=model, channel_contributions={}, campaign_contributions={}, computed_at=datetime.utcnow())

        if model == AttributionModel.LAST_CLICK:
            return self._last_click(touchpoints)
        elif model == AttributionModel.FIRST_CLICK:
            return self._first_click(touchpoints)
        elif model == AttributionModel.LINEAR:
            return self._linear(touchpoints)
        elif model == AttributionModel.TIME_DECAY:
            return self._time_decay(touchpoints)
        elif model == AttributionModel.DATA_DRIVEN:
            return self._data_driven(touchpoints)
        else:
            return self._linear(touchpoints)

    def compute_all_models(self, touchpoints: List[Touchpoint]) -> List[AttributionResult]:
        """Compute all attribution models and return for comparison."""
        return [self.compute(touchpoints, model) for model in AttributionModel]

    def compute_divergence(self, results: List[AttributionResult]) -> Dict[str, float]:
        """
        Compute divergence between models — channels where models disagree most.
        High divergence = channel needs incrementality testing.
        """
        all_channels = set()
        for r in results:
            all_channels.update(r.channel_contributions.keys())

        divergence = {}
        for channel in all_channels:
            values = [r.channel_contributions.get(channel, 0) for r in results]
            if values:
                divergence[channel] = max(values) - min(values)

        return dict(sorted(divergence.items(), key=lambda x: x[1], reverse=True))

    def _last_click(self, touchpoints: List[Touchpoint]) -> AttributionResult:
        """100% credit to the last touchpoint."""
        last = sorted(touchpoints, key=lambda t: t.timestamp)[-1]
        return AttributionResult(
            model=AttributionModel.LAST_CLICK,
            channel_contributions={last.channel: 1.0},
            campaign_contributions={last.campaign_id: 1.0},
            computed_at=datetime.utcnow(),
        )

    def _first_click(self, touchpoints: List[Touchpoint]) -> AttributionResult:
        """100% credit to the first touchpoint."""
        first = sorted(touchpoints, key=lambda t: t.timestamp)[0]
        return AttributionResult(
            model=AttributionModel.FIRST_CLICK,
            channel_contributions={first.channel: 1.0},
            campaign_contributions={first.campaign_id: 1.0},
            computed_at=datetime.utcnow(),
        )

    def _linear(self, touchpoints: List[Touchpoint]) -> AttributionResult:
        """Equal credit to all touchpoints."""
        n = len(touchpoints)
        credit = 1.0 / n
        channels: Dict[str, float] = {}
        campaigns: Dict[str, float] = {}
        for tp in touchpoints:
            channels[tp.channel] = channels.get(tp.channel, 0) + credit
            campaigns[tp.campaign_id] = campaigns.get(tp.campaign_id, 0) + credit
        return AttributionResult(
            model=AttributionModel.LINEAR,
            channel_contributions=channels,
            campaign_contributions=campaigns,
            computed_at=datetime.utcnow(),
        )

    def _time_decay(self, touchpoints: List[Touchpoint], half_life_hours: float = 24) -> AttributionResult:
        """More credit to recent touchpoints (exponential decay)."""
        import math
        sorted_tp = sorted(touchpoints, key=lambda t: t.timestamp)
        if not sorted_tp:
            return AttributionResult(model=AttributionModel.TIME_DECAY, channel_contributions={}, campaign_contributions={}, computed_at=datetime.utcnow())

        latest = sorted_tp[-1].timestamp
        weights = []
        for tp in sorted_tp:
            hours_ago = (latest - tp.timestamp).total_seconds() / 3600
            weight = math.exp(-0.693 * hours_ago / half_life_hours)  # Half-life decay
            weights.append(weight)

        total_weight = sum(weights)
        channels: Dict[str, float] = {}
        campaigns: Dict[str, float] = {}
        for tp, w in zip(sorted_tp, weights):
            credit = w / total_weight
            channels[tp.channel] = channels.get(tp.channel, 0) + credit
            campaigns[tp.campaign_id] = campaigns.get(tp.campaign_id, 0) + credit

        return AttributionResult(
            model=AttributionModel.TIME_DECAY,
            channel_contributions=channels,
            campaign_contributions=campaigns,
            computed_at=datetime.utcnow(),
        )

    def _data_driven(self, touchpoints: List[Touchpoint]) -> AttributionResult:
        """Shapley value-based attribution (simplified)."""
        # Simplified: frequency-weighted with interaction type bonus
        # Production: use proper Shapley value computation over conversion paths
        weights = {"click": 2.0, "view": 0.5, "impression": 0.3}
        scored = [(tp, weights.get(tp.interaction_type, 1.0)) for tp in touchpoints]
        total = sum(w for _, w in scored)

        channels: Dict[str, float] = {}
        campaigns: Dict[str, float] = {}
        for tp, w in scored:
            credit = w / total if total > 0 else 0
            channels[tp.channel] = channels.get(tp.channel, 0) + credit
            campaigns[tp.campaign_id] = campaigns.get(tp.campaign_id, 0) + credit

        return AttributionResult(
            model=AttributionModel.DATA_DRIVEN,
            channel_contributions=channels,
            campaign_contributions=campaigns,
            computed_at=datetime.utcnow(),
        )
