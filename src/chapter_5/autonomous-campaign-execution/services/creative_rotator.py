"""
Creative Rotator — manages creative lifecycle and rotation strategy.

Features:
- Fatigue detection integration (triggers rotation)
- Queue management (ensures replacements are ready)
- Minimum active creatives enforcement
- Smooth rotation (ramp up new, ramp down old)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum


class CreativeState(Enum):
    QUEUED = "queued"  # Ready for deployment
    RAMPING_UP = "ramping_up"  # Being introduced (low impression share)
    ACTIVE = "active"  # Fully active
    RAMPING_DOWN = "ramping_down"  # Being phased out
    PAUSED = "paused"  # Temporarily paused
    RETIRED = "retired"  # Permanently removed


@dataclass
class Creative:
    """A creative variant in the rotation system."""
    creative_id: str
    campaign_id: str
    territory: str  # Concept territory it belongs to
    format: str
    platform: str
    state: CreativeState = CreativeState.QUEUED
    impression_share: float = 0.0  # 0.0-1.0 of budget
    activated_at: Optional[datetime] = None
    fatigue_score: float = 0.0
    performance_score: float = 0.5  # 0-1, higher is better
    days_active: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RotationAction:
    """A rotation action to execute."""
    action_type: str  # "activate", "pause", "retire", "adjust_share"
    creative_id: str
    campaign_id: str
    new_state: Optional[CreativeState] = None
    new_impression_share: Optional[float] = None
    reasoning: str = ""
    priority: int = 0  # Higher = more urgent
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RotationConfig:
    """Configuration for the rotation system."""
    min_active_creatives: int = 3
    max_active_creatives: int = 8
    ramp_up_days: int = 2
    ramp_down_days: int = 2
    fatigue_threshold: float = 0.6  # Score above this triggers rotation
    min_days_before_rotation: int = 3  # Minimum time before a creative can be rotated
    performance_weight: float = 0.6  # Weight for performance in share allocation
    recency_weight: float = 0.4  # Weight for freshness in share allocation


class CreativeRotator:
    """
    Manages creative rotation to maintain campaign freshness and performance.

    Ensures:
    - Minimum active creatives at all times
    - Smooth transitions (ramp up/down over multiple days)
    - Performance-based impression share allocation
    - Proactive queue management
    """

    def __init__(self, config: Optional[RotationConfig] = None):
        self.config = config or RotationConfig()
        self._creatives: dict[str, Creative] = {}
        self._action_log: list[RotationAction] = []

    def add_creative(self, creative: Creative) -> None:
        """Add a creative to the rotation system."""
        self._creatives[creative.creative_id] = creative

    def get_active_creatives(self, campaign_id: str) -> list[Creative]:
        """Get all active creatives for a campaign."""
        return [
            c for c in self._creatives.values()
            if c.campaign_id == campaign_id and c.state in (CreativeState.ACTIVE, CreativeState.RAMPING_UP)
        ]

    def get_queue(self, campaign_id: str) -> list[Creative]:
        """Get queued creatives ready for activation."""
        return [
            c for c in self._creatives.values()
            if c.campaign_id == campaign_id and c.state == CreativeState.QUEUED
        ]

    def evaluate_rotation(self, campaign_id: str) -> list[RotationAction]:
        """
        Evaluate whether any rotation actions are needed.

        Returns list of actions to execute.
        """
        actions = []
        active = self.get_active_creatives(campaign_id)
        queued = self.get_queue(campaign_id)

        # Check for fatigued creatives
        fatigued = [c for c in active if c.fatigue_score >= self.config.fatigue_threshold]

        # Check minimum active constraint
        active_count = len(active)

        # Phase out fatigued creatives (but maintain minimum)
        for creative in fatigued:
            if creative.days_active < self.config.min_days_before_rotation:
                continue

            if active_count - 1 >= self.config.min_active_creatives or queued:
                actions.append(RotationAction(
                    action_type="pause",
                    creative_id=creative.creative_id,
                    campaign_id=campaign_id,
                    new_state=CreativeState.RAMPING_DOWN,
                    reasoning=f"Fatigue score {creative.fatigue_score:.2f} exceeds threshold {self.config.fatigue_threshold}",
                    priority=int(creative.fatigue_score * 10),
                ))
                active_count -= 1

        # Activate queued creatives if under minimum or replacing fatigued
        slots_available = self.config.max_active_creatives - active_count
        replacements_needed = max(0, self.config.min_active_creatives - active_count + len(fatigued))
        to_activate = min(len(queued), max(slots_available, replacements_needed))

        for creative in queued[:to_activate]:
            actions.append(RotationAction(
                action_type="activate",
                creative_id=creative.creative_id,
                campaign_id=campaign_id,
                new_state=CreativeState.RAMPING_UP,
                new_impression_share=self._compute_ramp_up_share(active_count),
                reasoning="Activated to replace fatigued creative or fill minimum requirement",
                priority=5,
            ))

        # Rebalance impression shares among active
        if active:
            share_actions = self._rebalance_shares(active, campaign_id)
            actions.extend(share_actions)

        self._action_log.extend(actions)
        return actions

    def execute_action(self, action: RotationAction) -> bool:
        """Execute a rotation action."""
        creative = self._creatives.get(action.creative_id)
        if not creative:
            return False

        if action.new_state:
            creative.state = action.new_state
            if action.new_state == CreativeState.ACTIVE:
                creative.activated_at = datetime.utcnow()

        if action.new_impression_share is not None:
            creative.impression_share = action.new_impression_share

        return True

    def update_fatigue_scores(self, scores: dict[str, float]) -> None:
        """Update fatigue scores from the fatigue detector."""
        for creative_id, score in scores.items():
            if creative_id in self._creatives:
                self._creatives[creative_id].fatigue_score = score

    def update_performance_scores(self, scores: dict[str, float]) -> None:
        """Update performance scores based on latest metrics."""
        for creative_id, score in scores.items():
            if creative_id in self._creatives:
                self._creatives[creative_id].performance_score = score

    def _rebalance_shares(self, active: list[Creative], campaign_id: str) -> list[RotationAction]:
        """Rebalance impression shares based on performance."""
        if not active:
            return []

        actions = []
        total_score = sum(c.performance_score for c in active)

        if total_score == 0:
            # Equal distribution
            equal_share = 1.0 / len(active)
            for creative in active:
                if abs(creative.impression_share - equal_share) > 0.05:
                    actions.append(RotationAction(
                        action_type="adjust_share",
                        creative_id=creative.creative_id,
                        campaign_id=campaign_id,
                        new_impression_share=round(equal_share, 3),
                        reasoning="Equal distribution (no performance data)",
                    ))
        else:
            # Performance-weighted distribution
            for creative in active:
                target_share = creative.performance_score / total_score
                if abs(creative.impression_share - target_share) > 0.05:
                    actions.append(RotationAction(
                        action_type="adjust_share",
                        creative_id=creative.creative_id,
                        campaign_id=campaign_id,
                        new_impression_share=round(target_share, 3),
                        reasoning=f"Performance-based allocation (score: {creative.performance_score:.2f})",
                    ))

        return actions

    def _compute_ramp_up_share(self, current_active_count: int) -> float:
        """Compute initial impression share for a new creative."""
        if current_active_count == 0:
            return 1.0
        # Start at a small share and ramp up
        return min(0.2, 1.0 / (current_active_count + 1))

    def get_health_status(self, campaign_id: str) -> dict:
        """Get rotation health status for a campaign."""
        active = self.get_active_creatives(campaign_id)
        queued = self.get_queue(campaign_id)
        fatigued = [c for c in active if c.fatigue_score >= self.config.fatigue_threshold]

        return {
            "campaign_id": campaign_id,
            "active_creatives": len(active),
            "min_required": self.config.min_active_creatives,
            "queued_replacements": len(queued),
            "fatigued_count": len(fatigued),
            "healthy": len(active) >= self.config.min_active_creatives and len(queued) > 0,
            "needs_attention": len(queued) == 0 and len(fatigued) > 0,
        }
