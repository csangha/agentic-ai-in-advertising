"""
Feedback Loop Registry — defines and triggers cross-layer feedback.

Features:
- Defines feedback loops between system layers
- Triggers feedback propagation when conditions are met
- Tracks loop execution and outcomes
- Prevents feedback storms with rate limiting
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Callable
from enum import Enum


class FeedbackDirection(Enum):
    MEASUREMENT_TO_CREATIVE = "measurement_to_creative"
    MEASUREMENT_TO_EXECUTION = "measurement_to_execution"
    OPTIMIZATION_TO_EXECUTION = "optimization_to_execution"
    OPTIMIZATION_TO_CREATIVE = "optimization_to_creative"
    EXECUTION_TO_STRATEGY = "execution_to_strategy"
    CREATIVE_TO_STRATEGY = "creative_to_strategy"
    LEARNING_TO_ALL = "learning_to_all"


class TriggerCondition(Enum):
    METRIC_THRESHOLD = "metric_threshold"
    TIME_ELAPSED = "time_elapsed"
    EVENT_OCCURRED = "event_occurred"
    EXPERIMENT_COMPLETED = "experiment_completed"
    ANOMALY_DETECTED = "anomaly_detected"


class FeedbackStatus(Enum):
    PENDING = "pending"
    TRIGGERED = "triggered"
    EXECUTED = "executed"
    SUPPRESSED = "suppressed"
    FAILED = "failed"


@dataclass
class FeedbackLoop:
    """Definition of a feedback loop between system layers."""
    loop_id: str
    name: str
    direction: FeedbackDirection
    source_layer: str
    target_layer: str
    trigger_condition: TriggerCondition
    trigger_params: dict = field(default_factory=dict)
    action_description: str = ""
    cooldown_minutes: int = 60  # Minimum time between triggers
    max_triggers_per_day: int = 10
    priority: int = 5  # 1-10
    enabled: bool = True


@dataclass
class FeedbackEvent:
    """A triggered feedback event."""
    event_id: str
    loop_id: str
    direction: FeedbackDirection
    trigger_data: dict
    action_taken: str
    status: FeedbackStatus
    source_agent: str = ""
    target_agent: str = ""
    triggered_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    result: dict = field(default_factory=dict)


class FeedbackLoopRegistry:
    """
    Manages cross-layer feedback loops in the advertising operating system.

    Feedback flows:
    - Measurement → Creative: fatigue signals trigger creative rotation
    - Measurement → Execution: data quality gates block/allow actions
    - Optimization → Execution: bid/budget recommendations flow to execution
    - Optimization → Creative: performance data informs creative scoring
    - Execution → Strategy: persistent underperformance triggers strategy review
    - Creative → Strategy: territory performance feeds back to positioning
    - Learning → All: experiment results update all layers
    """

    def __init__(self, max_triggers_per_day: int = 50):
        self.max_triggers_per_day = max_triggers_per_day
        self._loops: dict[str, FeedbackLoop] = {}
        self._events: list[FeedbackEvent] = []
        self._trigger_counts: dict[str, int] = {}  # loop_id → count today
        self._last_triggered: dict[str, datetime] = {}  # loop_id → last trigger time

        # Register default feedback loops
        self._register_default_loops()

    def register_loop(self, loop: FeedbackLoop) -> None:
        """Register a new feedback loop."""
        self._loops[loop.loop_id] = loop

    def get_loop(self, loop_id: str) -> Optional[FeedbackLoop]:
        """Get a feedback loop by ID."""
        return self._loops.get(loop_id)

    def get_all_loops(self) -> list[FeedbackLoop]:
        """Get all registered loops."""
        return list(self._loops.values())

    def trigger(
        self,
        loop_id: str,
        trigger_data: dict,
        source_agent: str = "",
    ) -> Optional[FeedbackEvent]:
        """
        Trigger a feedback loop if conditions are met.

        Checks:
        - Loop exists and is enabled
        - Cooldown period has elapsed
        - Daily trigger limit not exceeded

        Returns FeedbackEvent if triggered, None if suppressed.
        """
        loop = self._loops.get(loop_id)
        if not loop or not loop.enabled:
            return None

        # Check cooldown
        if self._is_in_cooldown(loop_id, loop.cooldown_minutes):
            return self._create_suppressed_event(loop, trigger_data, "cooldown_active")

        # Check daily limit
        if self._exceeds_daily_limit(loop_id, loop.max_triggers_per_day):
            return self._create_suppressed_event(loop, trigger_data, "daily_limit_exceeded")

        # Create and record event
        event = FeedbackEvent(
            event_id=f"fb-{loop_id}-{len(self._events):04d}",
            loop_id=loop_id,
            direction=loop.direction,
            trigger_data=trigger_data,
            action_taken=loop.action_description,
            status=FeedbackStatus.TRIGGERED,
            source_agent=source_agent,
        )

        self._events.append(event)
        self._last_triggered[loop_id] = datetime.utcnow()
        self._trigger_counts[loop_id] = self._trigger_counts.get(loop_id, 0) + 1

        return event

    def mark_executed(self, event_id: str, result: dict = None) -> None:
        """Mark a feedback event as successfully executed."""
        for event in self._events:
            if event.event_id == event_id:
                event.status = FeedbackStatus.EXECUTED
                event.completed_at = datetime.utcnow()
                event.result = result or {}
                break

    def mark_failed(self, event_id: str, error: str = "") -> None:
        """Mark a feedback event as failed."""
        for event in self._events:
            if event.event_id == event_id:
                event.status = FeedbackStatus.FAILED
                event.completed_at = datetime.utcnow()
                event.result = {"error": error}
                break

    def get_active_events(self) -> list[FeedbackEvent]:
        """Get all triggered but not yet completed events."""
        return [e for e in self._events if e.status == FeedbackStatus.TRIGGERED]

    def get_event_history(self, loop_id: str = None, hours: int = 24) -> list[FeedbackEvent]:
        """Get event history, optionally filtered by loop."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        events = [e for e in self._events if e.triggered_at > cutoff]
        if loop_id:
            events = [e for e in events if e.loop_id == loop_id]
        return events

    def get_stats(self) -> dict:
        """Get feedback loop statistics."""
        today = datetime.utcnow().date()
        today_events = [e for e in self._events if e.triggered_at.date() == today]

        return {
            "total_loops_registered": len(self._loops),
            "enabled_loops": sum(1 for l in self._loops.values() if l.enabled),
            "events_today": len(today_events),
            "triggered_today": sum(1 for e in today_events if e.status == FeedbackStatus.TRIGGERED),
            "executed_today": sum(1 for e in today_events if e.status == FeedbackStatus.EXECUTED),
            "suppressed_today": sum(1 for e in today_events if e.status == FeedbackStatus.SUPPRESSED),
            "failed_today": sum(1 for e in today_events if e.status == FeedbackStatus.FAILED),
        }

    def _is_in_cooldown(self, loop_id: str, cooldown_minutes: int) -> bool:
        """Check if loop is in cooldown period."""
        last = self._last_triggered.get(loop_id)
        if not last:
            return False
        elapsed = (datetime.utcnow() - last).total_seconds() / 60
        return elapsed < cooldown_minutes

    def _exceeds_daily_limit(self, loop_id: str, max_per_day: int) -> bool:
        """Check if daily trigger limit is exceeded."""
        count = self._trigger_counts.get(loop_id, 0)
        return count >= max_per_day

    def _create_suppressed_event(
        self, loop: FeedbackLoop, trigger_data: dict, reason: str
    ) -> FeedbackEvent:
        """Create a suppressed event for tracking."""
        event = FeedbackEvent(
            event_id=f"fb-{loop.loop_id}-sup-{len(self._events):04d}",
            loop_id=loop.loop_id,
            direction=loop.direction,
            trigger_data=trigger_data,
            action_taken=f"SUPPRESSED: {reason}",
            status=FeedbackStatus.SUPPRESSED,
        )
        self._events.append(event)
        return event

    def _register_default_loops(self) -> None:
        """Register the standard cross-layer feedback loops."""
        default_loops = [
            FeedbackLoop(
                loop_id="measurement-to-creative-fatigue",
                name="Creative Fatigue Detection",
                direction=FeedbackDirection.MEASUREMENT_TO_CREATIVE,
                source_layer="measurement",
                target_layer="creative",
                trigger_condition=TriggerCondition.METRIC_THRESHOLD,
                trigger_params={"metric": "creative_fatigue_score", "threshold": 0.6},
                action_description="Trigger creative rotation when fatigue detected",
                cooldown_minutes=240,
                priority=7,
            ),
            FeedbackLoop(
                loop_id="measurement-to-execution-quality",
                name="Data Quality Gate",
                direction=FeedbackDirection.MEASUREMENT_TO_EXECUTION,
                source_layer="measurement",
                target_layer="execution",
                trigger_condition=TriggerCondition.ANOMALY_DETECTED,
                trigger_params={"anomaly_type": "data_staleness"},
                action_description="Block execution actions when data is stale",
                cooldown_minutes=15,
                priority=9,
            ),
            FeedbackLoop(
                loop_id="optimization-to-execution-bids",
                name="Bid Recommendation Flow",
                direction=FeedbackDirection.OPTIMIZATION_TO_EXECUTION,
                source_layer="optimization",
                target_layer="execution",
                trigger_condition=TriggerCondition.TIME_ELAPSED,
                trigger_params={"interval_minutes": 60},
                action_description="Push bid recommendations to execution layer",
                cooldown_minutes=30,
                priority=6,
            ),
            FeedbackLoop(
                loop_id="optimization-to-creative-scoring",
                name="Creative Performance Scoring",
                direction=FeedbackDirection.OPTIMIZATION_TO_CREATIVE,
                source_layer="optimization",
                target_layer="creative",
                trigger_condition=TriggerCondition.TIME_ELAPSED,
                trigger_params={"interval_minutes": 360},
                action_description="Update creative territory scores from performance data",
                cooldown_minutes=120,
                priority=4,
            ),
            FeedbackLoop(
                loop_id="execution-to-strategy-underperformance",
                name="Strategy Escalation",
                direction=FeedbackDirection.EXECUTION_TO_STRATEGY,
                source_layer="execution",
                target_layer="strategy",
                trigger_condition=TriggerCondition.METRIC_THRESHOLD,
                trigger_params={"metric": "cpa_vs_target_ratio", "threshold": 1.5},
                action_description="Escalate to strategy when CPA persistently exceeds target by 50%",
                cooldown_minutes=1440,  # Once per day max
                priority=8,
            ),
            FeedbackLoop(
                loop_id="learning-to-all-experiment",
                name="Experiment Result Propagation",
                direction=FeedbackDirection.LEARNING_TO_ALL,
                source_layer="learning",
                target_layer="all",
                trigger_condition=TriggerCondition.EXPERIMENT_COMPLETED,
                trigger_params={},
                action_description="Propagate experiment results to update all layer policies",
                cooldown_minutes=0,  # No cooldown for experiments
                priority=10,
            ),
        ]

        for loop in default_loops:
            self.register_loop(loop)
