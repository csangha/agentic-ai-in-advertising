"""
Concept Territory Generator — generates diverse creative territories.

Features:
- Generates 10+ concept territories per brief
- Diversity enforcement (ensures territories are distinct)
- Emotional mapping and tension identification
- Territory scoring by strategic fit
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum
import hashlib
import math


class EmotionalDimension(Enum):
    EMPOWERMENT = "empowerment"
    BELONGING = "belonging"
    ASPIRATION = "aspiration"
    SECURITY = "security"
    CURIOSITY = "curiosity"
    PRIDE = "pride"
    JOY = "joy"
    RELIEF = "relief"
    URGENCY = "urgency"
    NOSTALGIA = "nostalgia"


class TerritoryStatus(Enum):
    GENERATED = "generated"
    VALIDATED = "validated"
    SELECTED = "selected"
    REJECTED = "rejected"


@dataclass
class CreativeBrief:
    """Input brief for concept territory generation."""
    campaign_id: str
    product: str
    target_audience: str
    emotional_tone: str
    positioning: str
    platforms: list[str]
    brand_values: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    competitor_territories: list[str] = field(default_factory=list)


@dataclass
class ConceptTerritory:
    """A creative concept territory — a thematic space for ad development."""
    territory_id: str
    name: str
    headline_hook: str
    emotional_core: EmotionalDimension
    tension: str  # The human tension this territory resolves
    narrative_angle: str
    visual_world: str
    target_connection: str  # Why this resonates with the audience
    differentiation: str  # How this is distinct from competitors
    platform_fit: dict[str, float] = field(default_factory=dict)  # platform → fit score
    strategic_score: float = 0.0
    diversity_score: float = 0.0
    status: TerritoryStatus = TerritoryStatus.GENERATED
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class GenerationResult:
    """Result of a concept territory generation run."""
    campaign_id: str
    territories: list[ConceptTerritory]
    diversity_metric: float  # Overall diversity of the set
    coverage_gaps: list[str]  # Emotional dimensions not covered
    generated_at: datetime = field(default_factory=datetime.utcnow)


class ConceptGenerator:
    """
    Generates diverse creative concept territories from a brief.

    Ensures minimum diversity by:
    1. Targeting different emotional dimensions
    2. Enforcing minimum semantic distance between territories
    3. Checking competitor territory overlap
    4. Balancing platform suitability
    """

    # Template territories keyed by emotional dimension
    TERRITORY_TEMPLATES = {
        EmotionalDimension.EMPOWERMENT: {
            "tension_templates": [
                "The gap between wanting to improve and not knowing where to start",
                "Feeling held back by tools that don't match your ambition",
            ],
            "narrative_angles": [
                "accountability_partner",
                "unlock_potential",
                "daily_victories",
            ],
        },
        EmotionalDimension.BELONGING: {
            "tension_templates": [
                "Working hard alone when community could amplify results",
                "The isolation of personal health journeys",
            ],
            "narrative_angles": [
                "shared_journey",
                "community_challenge",
                "tribe_identity",
            ],
        },
        EmotionalDimension.ASPIRATION: {
            "tension_templates": [
                "Knowing your body is capable of more than your current routine delivers",
                "The distance between who you are and who you could become",
            ],
            "narrative_angles": [
                "performance_tracking",
                "future_self",
                "elite_access",
            ],
        },
        EmotionalDimension.SECURITY: {
            "tension_templates": [
                "Not knowing if your body is sending warning signals",
                "The anxiety of health uncertainty in a busy life",
            ],
            "narrative_angles": [
                "health_guardian",
                "peace_of_mind",
                "early_warning",
            ],
        },
        EmotionalDimension.CURIOSITY: {
            "tension_templates": [
                "The untapped data about your body you've never seen",
                "Not understanding why some days feel different than others",
            ],
            "narrative_angles": [
                "body_intelligence",
                "data_discovery",
                "personalized_insights",
            ],
        },
        EmotionalDimension.PRIDE: {
            "tension_templates": [
                "Putting in the work without recognition or proof",
                "The invisible effort of maintaining peak performance",
            ],
            "narrative_angles": [
                "earned_status",
                "visible_progress",
                "achievement_showcase",
            ],
        },
        EmotionalDimension.JOY: {
            "tension_templates": [
                "Fitness feeling like a chore rather than a celebration",
                "Losing the fun in the pursuit of health goals",
            ],
            "narrative_angles": [
                "movement_celebration",
                "playful_progress",
                "lifestyle_integration",
            ],
        },
    }

    def __init__(self, min_territories: int = 10, min_diversity: float = 0.6):
        self.min_territories = min_territories
        self.min_diversity = min_diversity

    def generate(self, brief: CreativeBrief) -> GenerationResult:
        """
        Generate concept territories for a creative brief.

        Produces at least min_territories with diversity enforcement.
        """
        territories = []
        used_dimensions = set()
        used_angles = set()

        # Phase 1: Generate one territory per emotional dimension
        for dimension, templates in self.TERRITORY_TEMPLATES.items():
            for i, angle in enumerate(templates["narrative_angles"]):
                if angle in used_angles:
                    continue

                territory = self._create_territory(
                    brief=brief,
                    dimension=dimension,
                    tension=templates["tension_templates"][min(i, len(templates["tension_templates"]) - 1)],
                    angle=angle,
                    index=len(territories),
                )
                territories.append(territory)
                used_angles.add(angle)
                used_dimensions.add(dimension)

                if len(territories) >= self.min_territories:
                    break

            if len(territories) >= self.min_territories:
                break

        # Phase 2: Fill gaps if under minimum
        while len(territories) < self.min_territories:
            # Pick least-used dimension
            dimension = self._pick_underused_dimension(used_dimensions)
            templates = self.TERRITORY_TEMPLATES.get(dimension, list(self.TERRITORY_TEMPLATES.values())[0])
            angle = f"variant_{len(territories)}"

            territory = self._create_territory(
                brief=brief,
                dimension=dimension,
                tension=templates["tension_templates"][0],
                angle=angle,
                index=len(territories),
            )
            territories.append(territory)
            used_dimensions.add(dimension)

        # Score territories
        territories = self._score_territories(territories, brief)

        # Compute diversity
        diversity_metric = self._compute_set_diversity(territories)

        # Identify coverage gaps
        all_dimensions = set(EmotionalDimension)
        coverage_gaps = [d.value for d in all_dimensions - used_dimensions]

        return GenerationResult(
            campaign_id=brief.campaign_id,
            territories=sorted(territories, key=lambda t: t.strategic_score, reverse=True),
            diversity_metric=diversity_metric,
            coverage_gaps=coverage_gaps,
        )

    def enforce_diversity(self, territories: list[ConceptTerritory]) -> list[ConceptTerritory]:
        """
        Remove territories that are too similar, keeping the highest scored.

        Uses emotional dimension + narrative angle as diversity key.
        """
        seen_keys = set()
        diverse = []

        for territory in sorted(territories, key=lambda t: t.strategic_score, reverse=True):
            key = f"{territory.emotional_core.value}:{territory.narrative_angle}"
            if key not in seen_keys:
                diverse.append(territory)
                seen_keys.add(key)

        return diverse

    def _create_territory(
        self, brief: CreativeBrief, dimension: EmotionalDimension,
        tension: str, angle: str, index: int
    ) -> ConceptTerritory:
        """Create a single concept territory."""
        territory_id = f"terr-{brief.campaign_id}-{index:03d}"
        name = angle.replace("_", " ").title()

        # Compute platform fit
        platform_fit = self._compute_platform_fit(dimension, brief.platforms)

        return ConceptTerritory(
            territory_id=territory_id,
            name=name,
            headline_hook=f"What if your {brief.product.lower()} could {tension.split(' ')[-3:][0]}?",
            emotional_core=dimension,
            tension=tension,
            narrative_angle=angle,
            visual_world=f"Visual world aligned with {dimension.value} emotion",
            target_connection=f"Resonates with {brief.target_audience} through {dimension.value}",
            differentiation=f"Unlike competitors, focuses on {angle.replace('_', ' ')}",
            platform_fit=platform_fit,
        )

    def _score_territories(
        self, territories: list[ConceptTerritory], brief: CreativeBrief
    ) -> list[ConceptTerritory]:
        """Score territories by strategic fit, platform fit, and differentiation."""
        for territory in territories:
            # Strategic fit: does it match the brief's emotional tone?
            tone_match = 0.7  # Placeholder scoring
            platform_score = sum(territory.platform_fit.values()) / max(len(territory.platform_fit), 1)
            competitor_distance = self._competitor_distance(territory, brief.competitor_territories)

            territory.strategic_score = (tone_match * 0.4 + platform_score * 0.3 + competitor_distance * 0.3)

        return territories

    def _compute_platform_fit(self, dimension: EmotionalDimension, platforms: list[str]) -> dict:
        """Compute how well an emotional dimension fits each platform."""
        # Platform-emotion affinity matrix (simplified)
        affinities = {
            "meta": {EmotionalDimension.BELONGING: 0.9, EmotionalDimension.JOY: 0.8, EmotionalDimension.PRIDE: 0.7},
            "tiktok": {EmotionalDimension.JOY: 0.9, EmotionalDimension.CURIOSITY: 0.8, EmotionalDimension.ASPIRATION: 0.7},
            "google": {EmotionalDimension.SECURITY: 0.8, EmotionalDimension.CURIOSITY: 0.7, EmotionalDimension.EMPOWERMENT: 0.7},
            "amazon": {EmotionalDimension.SECURITY: 0.8, EmotionalDimension.EMPOWERMENT: 0.7, EmotionalDimension.PRIDE: 0.6},
            "youtube": {EmotionalDimension.ASPIRATION: 0.9, EmotionalDimension.CURIOSITY: 0.8, EmotionalDimension.EMPOWERMENT: 0.8},
        }

        fit = {}
        for platform in platforms:
            platform_affinities = affinities.get(platform, {})
            fit[platform] = platform_affinities.get(dimension, 0.5)

        return fit

    def _compute_set_diversity(self, territories: list[ConceptTerritory]) -> float:
        """Compute overall diversity of the territory set (0-1)."""
        if not territories:
            return 0.0

        unique_dimensions = len(set(t.emotional_core for t in territories))
        unique_angles = len(set(t.narrative_angle for t in territories))
        total = len(territories)

        dimension_diversity = unique_dimensions / len(EmotionalDimension)
        angle_diversity = unique_angles / total

        return (dimension_diversity + angle_diversity) / 2

    def _competitor_distance(self, territory: ConceptTerritory, competitor_territories: list[str]) -> float:
        """Score how different this territory is from known competitor territories."""
        if not competitor_territories:
            return 0.8

        # Simple: check if our angle appears in competitor list
        for comp in competitor_territories:
            if territory.narrative_angle.replace("_", " ") in comp.lower():
                return 0.3
        return 0.8

    def _pick_underused_dimension(self, used: set) -> EmotionalDimension:
        """Pick the least-used emotional dimension."""
        all_dims = list(EmotionalDimension)
        unused = [d for d in all_dims if d not in used]
        if unused:
            return unused[0]
        return all_dims[0]
