"""
Alert Engine — manages alert generation, scoring, rate limiting, and deduplication.

Features:
- Convergence detection (multiple competitors shifting similarly)
- Alert scoring (significance + confidence)
- Rate limiting (max 3 alerts per week per client)
- Deduplication (suppress similar alerts within window)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum
import hashlib


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ACTION_NEEDED = "action_needed"


class AlertType(Enum):
    COMPETITOR_SHIFT = "competitor_shift"
    TREND_BREAKOUT = "trend_breakout"
    CONVERGENCE = "convergence"
    SENTIMENT_SHIFT = "sentiment_shift"
    NEW_ENTRANT = "new_entrant"


@dataclass
class AlertSignal:
    """A raw signal that may generate an alert."""
    signal_id: str
    signal_type: AlertType
    source: str  # competitor name or data source
    description: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    detected_at: datetime = field(default_factory=datetime.utcnow)
    category: str = ""
    client_id: str = ""


@dataclass
class Alert:
    """A scored and validated alert ready for delivery."""
    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    description: str
    confidence: float
    significance_score: float  # Combined score
    strategic_implication: str
    recommended_response: str
    evidence: list[str]
    client_id: str
    category: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    delivered: bool = False
    delivery_channels: list[str] = field(default_factory=list)


@dataclass
class ConvergenceEvent:
    """Multiple competitors shifting toward the same positioning."""
    event_id: str
    competitors: list[str]
    convergence_target: str  # What they're converging toward
    confidence: float
    first_detected: datetime = field(default_factory=datetime.utcnow)
    signal_count: int = 0


class AlertEngine:
    """
    Manages alert lifecycle: scoring, deduplication, rate limiting, delivery.

    Ensures strategy teams get high-signal, low-noise alerts.
    """

    def __init__(
        self,
        max_alerts_per_week: int = 3,
        min_confidence: float = 0.7,
        dedup_window_hours: int = 72,
    ):
        self.max_alerts_per_week = max_alerts_per_week
        self.min_confidence = min_confidence
        self.dedup_window_hours = dedup_window_hours
        self._alerts: list[Alert] = []
        self._signals: list[AlertSignal] = []
        self._delivered_hashes: dict[str, datetime] = {}  # hash → last delivered

    def ingest_signal(self, signal: AlertSignal) -> Optional[Alert]:
        """
        Process a raw signal and determine if it should generate an alert.

        Returns Alert if signal passes scoring, dedup, and rate limit checks.
        Returns None if signal is suppressed.
        """
        self._signals.append(signal)

        # Check minimum confidence
        if signal.confidence < self.min_confidence:
            return None

        # Score significance
        significance = self._score_significance(signal)

        # Check deduplication
        if self._is_duplicate(signal):
            return None

        # Check rate limit
        if self._is_rate_limited(signal.client_id):
            return None

        # Generate alert
        alert = self._create_alert(signal, significance)
        self._alerts.append(alert)
        self._record_delivery(signal)

        return alert

    def detect_convergence(self, signals: list[AlertSignal]) -> list[ConvergenceEvent]:
        """
        Detect when multiple competitors are shifting toward the same positioning.

        Looks for 2+ competitors with similar shift signals within a time window.
        """
        events = []

        # Group competitor shift signals by category and time window
        shift_signals = [s for s in signals if s.signal_type == AlertType.COMPETITOR_SHIFT]

        # Group by description similarity (simplified — production uses embeddings)
        groups: dict[str, list[AlertSignal]] = {}
        for signal in shift_signals:
            # Use simplified grouping key
            key = f"{signal.category}:{signal.description[:50].lower()}"
            if key not in groups:
                groups[key] = []
            groups[key].append(signal)

        for key, group in groups.items():
            unique_sources = set(s.source for s in group)
            if len(unique_sources) >= 2:
                events.append(ConvergenceEvent(
                    event_id=f"conv-{hashlib.md5(key.encode()).hexdigest()[:8]}",
                    competitors=list(unique_sources),
                    convergence_target=group[0].description,
                    confidence=min(s.confidence for s in group),
                    signal_count=len(group),
                ))

        return events

    def _score_significance(self, signal: AlertSignal) -> float:
        """
        Score the significance of a signal (0.0-1.0).

        Factors:
        - Confidence of the detection
        - Type (convergence > shift > breakout > sentiment)
        - Evidence strength (more evidence = higher score)
        """
        type_weights = {
            AlertType.CONVERGENCE: 1.0,
            AlertType.COMPETITOR_SHIFT: 0.8,
            AlertType.TREND_BREAKOUT: 0.7,
            AlertType.NEW_ENTRANT: 0.9,
            AlertType.SENTIMENT_SHIFT: 0.6,
        }

        type_weight = type_weights.get(signal.signal_type, 0.5)
        evidence_weight = min(1.0, len(signal.evidence) * 0.2)
        confidence_weight = signal.confidence

        return (type_weight * 0.4 + evidence_weight * 0.3 + confidence_weight * 0.3)

    def _is_duplicate(self, signal: AlertSignal) -> bool:
        """Check if a similar alert was recently delivered."""
        dedup_key = self._compute_dedup_hash(signal)
        last_delivered = self._delivered_hashes.get(dedup_key)

        if last_delivered is None:
            return False

        cutoff = datetime.utcnow() - timedelta(hours=self.dedup_window_hours)
        return last_delivered > cutoff

    def _is_rate_limited(self, client_id: str) -> bool:
        """Check if client has exceeded weekly alert limit."""
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_alerts = [
            a for a in self._alerts
            if a.client_id == client_id and a.created_at > week_ago and a.delivered
        ]
        return len(recent_alerts) >= self.max_alerts_per_week

    def _create_alert(self, signal: AlertSignal, significance: float) -> Alert:
        """Create a structured alert from a validated signal."""
        severity = self._classify_severity(significance)

        return Alert(
            alert_id=f"alert-{hashlib.md5(signal.signal_id.encode()).hexdigest()[:8]}",
            alert_type=signal.signal_type,
            severity=severity,
            title=f"{signal.signal_type.value}: {signal.source}",
            description=signal.description,
            confidence=signal.confidence,
            significance_score=significance,
            strategic_implication=self._generate_implication(signal),
            recommended_response=self._generate_recommendation(signal),
            evidence=signal.evidence,
            client_id=signal.client_id,
            category=signal.category,
            delivered=True,
        )

    def _classify_severity(self, significance: float) -> AlertSeverity:
        """Map significance score to severity level."""
        if significance >= 0.8:
            return AlertSeverity.ACTION_NEEDED
        elif significance >= 0.6:
            return AlertSeverity.WARNING
        return AlertSeverity.INFO

    def _compute_dedup_hash(self, signal: AlertSignal) -> str:
        """Compute hash for deduplication."""
        content = f"{signal.client_id}:{signal.signal_type.value}:{signal.source}:{signal.description[:100]}"
        return hashlib.md5(content.encode()).hexdigest()

    def _record_delivery(self, signal: AlertSignal) -> None:
        """Record that an alert was delivered for dedup tracking."""
        dedup_key = self._compute_dedup_hash(signal)
        self._delivered_hashes[dedup_key] = datetime.utcnow()

    def _generate_implication(self, signal: AlertSignal) -> str:
        """Generate strategic implication text."""
        implications = {
            AlertType.COMPETITOR_SHIFT: f"{signal.source} is repositioning — monitor for audience impact",
            AlertType.TREND_BREAKOUT: f"Emerging trend may create new positioning opportunity",
            AlertType.CONVERGENCE: f"Multiple competitors converging — differentiation opportunity",
            AlertType.SENTIMENT_SHIFT: f"Market sentiment changing — messaging may need adjustment",
            AlertType.NEW_ENTRANT: f"New competitor entering category — assess threat level",
        }
        return implications.get(signal.signal_type, "Assess impact on current strategy")

    def _generate_recommendation(self, signal: AlertSignal) -> str:
        """Generate recommended response."""
        recommendations = {
            AlertType.COMPETITOR_SHIFT: "Review current positioning for differentiation gaps",
            AlertType.TREND_BREAKOUT: "Evaluate trend relevance for content calendar",
            AlertType.CONVERGENCE: "Identify white space positions competitors are abandoning",
            AlertType.SENTIMENT_SHIFT: "Run audience research to validate sentiment change",
            AlertType.NEW_ENTRANT: "Analyze new entrant value proposition and target overlap",
        }
        return recommendations.get(signal.signal_type, "Review and assess")

    def get_alert_history(self, client_id: str, days: int = 30) -> list[Alert]:
        """Get alert history for a client."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        return [a for a in self._alerts if a.client_id == client_id and a.created_at > cutoff]

    def get_stats(self, client_id: str) -> dict:
        """Get alert engine statistics for a client."""
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent = [a for a in self._alerts if a.client_id == client_id and a.created_at > week_ago]
        return {
            "alerts_this_week": len(recent),
            "max_per_week": self.max_alerts_per_week,
            "remaining_budget": max(0, self.max_alerts_per_week - len(recent)),
            "total_signals_processed": len([s for s in self._signals if s.client_id == client_id]),
            "total_alerts_generated": len([a for a in self._alerts if a.client_id == client_id]),
        }
