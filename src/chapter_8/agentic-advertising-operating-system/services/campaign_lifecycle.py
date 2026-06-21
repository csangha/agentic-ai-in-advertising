"""
Campaign Lifecycle Manager — state machine for campaign stages.

Features:
- State machine: RESEARCH → PLANNING → CREATIVE → LAUNCH → ACTIVE → LEARNING → ARCHIVED
- Transition validation (only valid transitions allowed)
- Stage gate criteria (must be met before progression)
- Audit trail of all transitions
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class LifecycleStage(Enum):
    RESEARCH = "RESEARCH"
    PLANNING = "PLANNING"
    CREATIVE = "CREATIVE"
    LAUNCH = "LAUNCH"
    ACTIVE = "ACTIVE"
    LEARNING = "LEARNING"
    ARCHIVED = "ARCHIVED"


@dataclass
class StageGate:
    """Criteria that must be met to exit a stage."""
    stage: LifecycleStage
    required_criteria: list[str]
    optional_criteria: list[str] = field(default_factory=list)


@dataclass
class TransitionRecord:
    """Record of a stage transition."""
    campaign_id: str
    from_stage: LifecycleStage
    to_stage: LifecycleStage
    triggered_by: str  # Agent or user ID
    reason: str
    gate_criteria_met: list[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CampaignState:
    """Current lifecycle state of a campaign."""
    campaign_id: str
    current_stage: LifecycleStage
    entered_stage_at: datetime = field(default_factory=datetime.utcnow)
    transition_history: list[TransitionRecord] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class TransitionResult:
    """Result of a transition attempt."""
    success: bool
    campaign_id: str
    new_stage: Optional[LifecycleStage] = None
    previous_stage: Optional[LifecycleStage] = None
    error: str = ""
    unmet_criteria: list[str] = field(default_factory=list)


class CampaignLifecycleManager:
    """
    Manages campaign lifecycle as a state machine.

    Valid transitions:
    RESEARCH → PLANNING → CREATIVE → LAUNCH → ACTIVE → LEARNING → ARCHIVED

    Special transitions:
    - ACTIVE → LEARNING (pause for analysis)
    - LEARNING → ACTIVE (resume after learning)
    - Any stage → ARCHIVED (emergency archival)
    """

    # Valid transitions (from → set of valid to)
    VALID_TRANSITIONS = {
        LifecycleStage.RESEARCH: {LifecycleStage.PLANNING, LifecycleStage.ARCHIVED},
        LifecycleStage.PLANNING: {LifecycleStage.CREATIVE, LifecycleStage.RESEARCH, LifecycleStage.ARCHIVED},
        LifecycleStage.CREATIVE: {LifecycleStage.LAUNCH, LifecycleStage.PLANNING, LifecycleStage.ARCHIVED},
        LifecycleStage.LAUNCH: {LifecycleStage.ACTIVE, LifecycleStage.CREATIVE, LifecycleStage.ARCHIVED},
        LifecycleStage.ACTIVE: {LifecycleStage.LEARNING, LifecycleStage.ARCHIVED},
        LifecycleStage.LEARNING: {LifecycleStage.ACTIVE, LifecycleStage.ARCHIVED},
        LifecycleStage.ARCHIVED: set(),  # Terminal state
    }

    # Stage gate criteria
    STAGE_GATES = {
        LifecycleStage.RESEARCH: StageGate(
            stage=LifecycleStage.RESEARCH,
            required_criteria=[
                "research_brief_completed",
                "target_audience_defined",
                "competitive_analysis_done",
            ],
            optional_criteria=["trend_analysis_done"],
        ),
        LifecycleStage.PLANNING: StageGate(
            stage=LifecycleStage.PLANNING,
            required_criteria=[
                "strategy_approved",
                "budget_allocated",
                "platforms_selected",
                "kpis_defined",
            ],
        ),
        LifecycleStage.CREATIVE: StageGate(
            stage=LifecycleStage.CREATIVE,
            required_criteria=[
                "creative_brief_approved",
                "min_3_concepts_generated",
                "compliance_check_passed",
                "brand_review_done",
            ],
        ),
        LifecycleStage.LAUNCH: StageGate(
            stage=LifecycleStage.LAUNCH,
            required_criteria=[
                "creatives_uploaded",
                "targeting_configured",
                "tracking_verified",
                "guardrails_configured",
            ],
        ),
        LifecycleStage.ACTIVE: StageGate(
            stage=LifecycleStage.ACTIVE,
            required_criteria=[
                "monitoring_confirmed",
                "data_flowing",
            ],
        ),
        LifecycleStage.LEARNING: StageGate(
            stage=LifecycleStage.LEARNING,
            required_criteria=[
                "learning_objectives_defined",
                "data_analyzed",
            ],
        ),
    }

    def __init__(self):
        self._campaigns: dict[str, CampaignState] = {}

    def create_campaign(self, campaign_id: str, metadata: dict = None) -> CampaignState:
        """Create a new campaign in RESEARCH stage."""
        state = CampaignState(
            campaign_id=campaign_id,
            current_stage=LifecycleStage.RESEARCH,
            metadata=metadata or {},
        )
        self._campaigns[campaign_id] = state
        return state

    def get_state(self, campaign_id: str) -> Optional[CampaignState]:
        """Get current campaign state."""
        return self._campaigns.get(campaign_id)

    def transition(
        self,
        campaign_id: str,
        to_stage: LifecycleStage,
        triggered_by: str,
        reason: str,
        criteria_met: list[str] = None,
        force: bool = False,
    ) -> TransitionResult:
        """
        Attempt to transition a campaign to a new stage.

        Validates:
        1. Transition is valid from current stage
        2. Stage gate criteria are met (unless forced)

        Args:
            campaign_id: Campaign to transition
            to_stage: Target stage
            triggered_by: Who triggered (agent_id or user_id)
            reason: Why transitioning
            criteria_met: List of gate criteria that are satisfied
            force: Skip gate validation (for emergency transitions)

        Returns:
            TransitionResult with success/failure and details
        """
        state = self._campaigns.get(campaign_id)
        if not state:
            return TransitionResult(success=False, campaign_id=campaign_id, error="Campaign not found")

        from_stage = state.current_stage

        # Validate transition is allowed
        valid_targets = self.VALID_TRANSITIONS.get(from_stage, set())
        if to_stage not in valid_targets:
            return TransitionResult(
                success=False,
                campaign_id=campaign_id,
                previous_stage=from_stage,
                error=f"Invalid transition: {from_stage.value} → {to_stage.value}. Valid targets: {[s.value for s in valid_targets]}",
            )

        # Check stage gate criteria (for exiting current stage)
        if not force:
            gate = self.STAGE_GATES.get(from_stage)
            if gate:
                criteria_met = criteria_met or []
                unmet = [c for c in gate.required_criteria if c not in criteria_met]
                if unmet:
                    return TransitionResult(
                        success=False,
                        campaign_id=campaign_id,
                        previous_stage=from_stage,
                        error=f"Stage gate criteria not met for exiting {from_stage.value}",
                        unmet_criteria=unmet,
                    )

        # Execute transition
        record = TransitionRecord(
            campaign_id=campaign_id,
            from_stage=from_stage,
            to_stage=to_stage,
            triggered_by=triggered_by,
            reason=reason,
            gate_criteria_met=criteria_met or [],
        )

        state.current_stage = to_stage
        state.entered_stage_at = datetime.utcnow()
        state.transition_history.append(record)

        return TransitionResult(
            success=True,
            campaign_id=campaign_id,
            new_stage=to_stage,
            previous_stage=from_stage,
        )

    def get_required_criteria(self, campaign_id: str) -> list[str]:
        """Get the criteria required to exit the current stage."""
        state = self._campaigns.get(campaign_id)
        if not state:
            return []

        gate = self.STAGE_GATES.get(state.current_stage)
        return gate.required_criteria if gate else []

    def get_transition_history(self, campaign_id: str) -> list[TransitionRecord]:
        """Get full transition history for a campaign."""
        state = self._campaigns.get(campaign_id)
        return state.transition_history if state else []

    def get_campaigns_in_stage(self, stage: LifecycleStage) -> list[str]:
        """Get all campaigns currently in a specific stage."""
        return [
            campaign_id for campaign_id, state in self._campaigns.items()
            if state.current_stage == stage
        ]

    def archive_campaign(self, campaign_id: str, triggered_by: str, reason: str) -> TransitionResult:
        """Emergency archive — valid from any stage."""
        return self.transition(
            campaign_id=campaign_id,
            to_stage=LifecycleStage.ARCHIVED,
            triggered_by=triggered_by,
            reason=reason,
            force=True,
        )
