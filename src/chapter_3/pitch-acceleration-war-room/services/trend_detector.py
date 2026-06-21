"""
Trend Detector — identifies and classifies emerging trends.

Features:
- Velocity computation (7d and 30d growth rates)
- Trend classification: spike (ephemeral), seasonal (recurring), structural (lasting)
- Relevance scoring against category keywords
- Breakout detection using z-score on volume time series
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum
import math
import statistics


class TrendType(Enum):
    SPIKE = "spike"
    SEASONAL = "seasonal"
    STRUCTURAL = "structural"


class SignalSource(Enum):
    SEARCH = "search"
    SOCIAL = "social"
    NEWS = "news"
    CULTURAL = "cultural"


@dataclass
class TrendSignal:
    """A single data point in a trend time series."""
    timestamp: datetime
    volume: float
    source: SignalSource


@dataclass
class DetectedTrend:
    """A classified trend with velocity and relevance metrics."""
    trend_id: str
    keyword: str
    trend_type: TrendType
    velocity_7d: float  # % growth over 7 days
    velocity_30d: float  # % growth over 30 days
    current_volume: float
    baseline_volume: float
    breakout_score: float  # z-score from baseline
    relevance_score: float  # 0.0-1.0
    confidence: float
    first_detected: datetime = field(default_factory=datetime.utcnow)
    source: SignalSource = SignalSource.SEARCH
    classification_reason: str = ""


class TrendDetector:
    """
    Detects and classifies trends from time series volume data.

    Uses statistical methods:
    - Z-score for breakout detection (>2σ from 90-day baseline)
    - Velocity ratio for classification (spike vs structural)
    - Seasonal decomposition for recurring pattern detection
    """

    def __init__(
        self,
        breakout_threshold: float = 2.0,
        spike_velocity_ratio: float = 5.0,
        structural_min_days: int = 14,
        seasonal_correlation_threshold: float = 0.7,
    ):
        self.breakout_threshold = breakout_threshold
        self.spike_velocity_ratio = spike_velocity_ratio
        self.structural_min_days = structural_min_days
        self.seasonal_correlation_threshold = seasonal_correlation_threshold

    def compute_velocity(self, signals: list[TrendSignal], days: int = 7) -> float:
        """
        Compute velocity as percentage growth over the specified period.

        Returns growth rate as a decimal (0.5 = 50% growth).
        """
        if len(signals) < 2:
            return 0.0

        now = signals[-1].timestamp
        cutoff = now - timedelta(days=days)

        recent = [s.volume for s in signals if s.timestamp > cutoff]
        older = [s.volume for s in signals if s.timestamp <= cutoff]

        if not recent or not older:
            return 0.0

        avg_recent = statistics.mean(recent)
        avg_older = statistics.mean(older)

        if avg_older == 0:
            return 10.0 if avg_recent > 0 else 0.0

        return (avg_recent - avg_older) / avg_older

    def classify(
        self,
        keyword: str,
        signals: list[TrendSignal],
        category_keywords: list[str] = None,
        historical_signals: list[TrendSignal] = None,
    ) -> Optional[DetectedTrend]:
        """
        Classify a trend based on its velocity pattern and duration.

        Classification logic:
        - SPIKE: velocity_7d > 5x velocity_30d (sudden, likely ephemeral)
        - SEASONAL: correlates with same period in prior year
        - STRUCTURAL: sustained growth > 14 days without sharp spike pattern
        """
        if len(signals) < 7:
            return None

        velocity_7d = self.compute_velocity(signals, days=7)
        velocity_30d = self.compute_velocity(signals, days=30)

        # Compute baseline and breakout score
        volumes = [s.volume for s in signals]
        baseline = statistics.mean(volumes[:-7]) if len(volumes) > 7 else statistics.mean(volumes)
        std_dev = statistics.stdev(volumes) if len(volumes) > 1 else 1.0
        current_volume = statistics.mean(volumes[-3:])  # Last 3 data points

        if std_dev == 0:
            breakout_score = 0.0
        else:
            breakout_score = (current_volume - baseline) / std_dev

        # Not a breakout — skip
        if breakout_score < self.breakout_threshold:
            return None

        # Classify trend type
        trend_type = self._classify_type(velocity_7d, velocity_30d, signals, historical_signals)

        # Compute relevance
        relevance = self._compute_relevance(keyword, category_keywords or [])

        classification_reason = self._explain_classification(trend_type, velocity_7d, velocity_30d, breakout_score)

        return DetectedTrend(
            trend_id=f"trend-{keyword.replace(' ', '-').lower()}-{datetime.utcnow().strftime('%Y%m%d')}",
            keyword=keyword,
            trend_type=trend_type,
            velocity_7d=velocity_7d,
            velocity_30d=velocity_30d,
            current_volume=current_volume,
            baseline_volume=baseline,
            breakout_score=breakout_score,
            relevance_score=relevance,
            confidence=min(0.95, 0.5 + breakout_score * 0.15),
            source=signals[-1].source if signals else SignalSource.SEARCH,
            classification_reason=classification_reason,
        )

    def _classify_type(
        self,
        velocity_7d: float,
        velocity_30d: float,
        signals: list[TrendSignal],
        historical_signals: Optional[list[TrendSignal]],
    ) -> TrendType:
        """Determine if trend is spike, seasonal, or structural."""
        # Check for spike: very high short-term velocity vs longer term
        if velocity_30d != 0 and abs(velocity_7d / velocity_30d) > self.spike_velocity_ratio:
            return TrendType.SPIKE

        # Check for seasonal pattern (requires historical data)
        if historical_signals and self._is_seasonal(signals, historical_signals):
            return TrendType.SEASONAL

        # Default: if sustained growth over 14+ days, it's structural
        if len(signals) >= self.structural_min_days and velocity_30d > 0.1:
            return TrendType.STRUCTURAL

        # Short-lived growth defaults to spike
        return TrendType.SPIKE

    def _is_seasonal(
        self, current: list[TrendSignal], historical: list[TrendSignal]
    ) -> bool:
        """Check if current pattern correlates with same period last year."""
        if len(historical) < 30:
            return False

        # Compare current 30-day volume pattern to historical same-period
        current_volumes = [s.volume for s in current[-30:]]
        historical_volumes = [s.volume for s in historical[-30:]]

        if len(current_volumes) != len(historical_volumes):
            min_len = min(len(current_volumes), len(historical_volumes))
            current_volumes = current_volumes[:min_len]
            historical_volumes = historical_volumes[:min_len]

        if len(current_volumes) < 5:
            return False

        correlation = self._pearson_correlation(current_volumes, historical_volumes)
        return correlation >= self.seasonal_correlation_threshold

    def _compute_relevance(self, keyword: str, category_keywords: list[str]) -> float:
        """Compute relevance score based on keyword overlap with category."""
        if not category_keywords:
            return 0.5

        keyword_lower = keyword.lower()
        matches = sum(1 for ck in category_keywords if ck.lower() in keyword_lower or keyword_lower in ck.lower())
        return min(1.0, matches / max(len(category_keywords) * 0.3, 1))

    def _explain_classification(
        self, trend_type: TrendType, velocity_7d: float, velocity_30d: float, breakout_score: float
    ) -> str:
        """Generate human-readable classification reason."""
        if trend_type == TrendType.SPIKE:
            return f"Spike: 7d velocity ({velocity_7d:.0%}) >> 30d velocity ({velocity_30d:.0%}), breakout z={breakout_score:.1f}"
        elif trend_type == TrendType.SEASONAL:
            return f"Seasonal: pattern correlates with prior year, velocity_30d={velocity_30d:.0%}"
        else:
            return f"Structural: sustained growth over 14+ days, 30d velocity={velocity_30d:.0%}, z={breakout_score:.1f}"

    @staticmethod
    def _pearson_correlation(x: list[float], y: list[float]) -> float:
        """Compute Pearson correlation coefficient."""
        n = len(x)
        if n < 3:
            return 0.0
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        std_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
        std_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))
        if std_x == 0 or std_y == 0:
            return 0.0
        return cov / (std_x * std_y)
