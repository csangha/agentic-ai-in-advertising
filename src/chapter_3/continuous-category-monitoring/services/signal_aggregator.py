"""
Signal Aggregator — continuous monitoring of market signals for retained clients.

Aggregates:
- Competitor creative shifts (weekly)
- Search demand velocity (daily)
- Social conversation trends (daily)
- Share of voice changes (monthly)
- Audience segment shifts (weekly)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
import uuid


class SignalType(str, Enum):
    COMPETITOR_SHIFT = "COMPETITOR_SHIFT"
    DEMAND_SIGNAL = "DEMAND_SIGNAL"
    AUDIENCE_SHIFT = "AUDIENCE_SHIFT"
    SOV_CHANGE = "SOV_CHANGE"
    TREND_EMERGING = "TREND_EMERGING"


class Significance(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class MarketSignal:
    signal_id: str = field(default_factory=lambda: f"sig-{uuid.uuid4().hex[:8]}")
    signal_type: SignalType = SignalType.DEMAND_SIGNAL
    title: str = ""
    description: str = ""
    evidence: List[Dict] = field(default_factory=list)
    velocity_pct: float = 0.0  # % above baseline
    significance: Significance = Significance.LOW
    confidence: float = 0.0
    detected_at: datetime = field(default_factory=datetime.utcnow)
    source: str = ""


class SignalAggregator:
    """Aggregates and prioritizes market signals from multiple sources."""

    def __init__(self, significance_threshold: float = 0.5):
        self.threshold = significance_threshold
        self._signals: List[MarketSignal] = []

    def add_signal(self, signal: MarketSignal) -> MarketSignal:
        """Add a new signal and compute significance."""
        signal.significance = self._classify_significance(signal)
        self._signals.append(signal)
        return signal

    def get_convergent_signals(self, min_signals: int = 2) -> List[List[MarketSignal]]:
        """Find signal clusters where 2+ signals converge (same theme, different sources)."""
        # Simplified: group by overlapping keywords in description
        # Production: use embedding similarity clustering
        clusters = []
        used = set()
        for i, sig_a in enumerate(self._signals):
            if i in used or sig_a.significance == Significance.LOW:
                continue
            cluster = [sig_a]
            used.add(i)
            for j, sig_b in enumerate(self._signals):
                if j in used or j == i:
                    continue
                if self._signals_related(sig_a, sig_b):
                    cluster.append(sig_b)
                    used.add(j)
            if len(cluster) >= min_signals:
                clusters.append(cluster)
        return clusters

    def get_top_signals(self, limit: int = 10, min_significance: Significance = Significance.MEDIUM) -> List[MarketSignal]:
        """Get top signals above significance threshold, sorted by velocity."""
        sig_order = {Significance.HIGH: 0, Significance.MEDIUM: 1, Significance.LOW: 2}
        min_order = sig_order.get(min_significance, 1)
        filtered = [s for s in self._signals if sig_order.get(s.significance, 2) <= min_order]
        filtered.sort(key=lambda s: s.velocity_pct, reverse=True)
        return filtered[:limit]

    def _classify_significance(self, signal: MarketSignal) -> Significance:
        if signal.velocity_pct >= 200 and signal.confidence >= 0.8:
            return Significance.HIGH
        elif signal.velocity_pct >= 100 or signal.confidence >= 0.7:
            return Significance.MEDIUM
        return Significance.LOW

    def _signals_related(self, a: MarketSignal, b: MarketSignal) -> bool:
        """Check if two signals are related (simplified keyword overlap)."""
        words_a = set(a.title.lower().split())
        words_b = set(b.title.lower().split())
        overlap = len(words_a & words_b)
        return overlap >= 2
