"""
Competitive Intelligence — analyzes competitor creative and messaging.

Features:
- Creative classification (format, tone, appeal type)
- Messaging shift detection (before/after comparison)
- Vulnerability analysis (gaps in competitor positioning)
- Share of voice tracking
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum


class AppealType(Enum):
    RATIONAL = "rational"
    EMOTIONAL = "emotional"
    SOCIAL_PROOF = "social_proof"
    FEAR = "fear"
    ASPIRATIONAL = "aspirational"
    HUMOR = "humor"


class ToneCategory(Enum):
    AUTHORITATIVE = "authoritative"
    FRIENDLY = "friendly"
    URGENT = "urgent"
    INSPIRATIONAL = "inspirational"
    CLINICAL = "clinical"
    PLAYFUL = "playful"


class VulnerabilityType(Enum):
    POSITIONING_GAP = "positioning_gap"
    AUDIENCE_NEGLECT = "audience_neglect"
    MESSAGE_FATIGUE = "message_fatigue"
    CHANNEL_ABSENCE = "channel_absence"
    VALUE_PROP_WEAKNESS = "value_prop_weakness"


@dataclass
class CompetitorCreative:
    """A single competitor creative observation."""
    creative_id: str
    competitor: str
    platform: str
    format: str  # video, static, carousel, story
    primary_message: str
    appeal_type: AppealType
    tone: ToneCategory
    call_to_action: str
    observed_at: datetime = field(default_factory=datetime.utcnow)
    estimated_spend: float = 0.0
    engagement_signals: dict = field(default_factory=dict)


@dataclass
class MessagingShift:
    """Detected change in competitor messaging strategy."""
    competitor: str
    shift_type: str  # "positioning", "tone", "audience", "value_prop"
    previous_state: str
    current_state: str
    confidence: float
    first_detected: datetime = field(default_factory=datetime.utcnow)
    evidence_count: int = 0
    strategic_implication: str = ""


@dataclass
class Vulnerability:
    """An exploitable gap in competitor positioning."""
    vulnerability_id: str
    vulnerability_type: VulnerabilityType
    competitor: str
    description: str
    opportunity_score: float  # 0.0-1.0
    audience_affected: str
    recommended_angle: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class CompetitiveSnapshot:
    """Point-in-time competitive landscape summary."""
    category: str
    snapshot_date: datetime
    competitors_analyzed: list[str]
    total_creatives_observed: int
    messaging_shifts: list[MessagingShift]
    vulnerabilities: list[Vulnerability]
    share_of_voice: dict  # competitor → % of total observed volume


class CompetitiveIntelligence:
    """
    Analyzes competitor creative and messaging to identify vulnerabilities.

    Tracks competitor output over time to detect messaging shifts and
    positioning gaps that can be exploited in the pitch.
    """

    def __init__(self, shift_detection_window_days: int = 30, min_creatives_for_shift: int = 5):
        self.shift_detection_window_days = shift_detection_window_days
        self.min_creatives_for_shift = min_creatives_for_shift
        self._creatives: list[CompetitorCreative] = []
        self._shifts: list[MessagingShift] = []

    def ingest_creative(self, creative: CompetitorCreative) -> None:
        """Add an observed competitor creative to the analysis corpus."""
        self._creatives.append(creative)

    def classify_creative(self, creative: CompetitorCreative) -> dict:
        """
        Classify a creative by format, tone, and appeal type.

        Returns structured classification with confidence scores.
        """
        return {
            "creative_id": creative.creative_id,
            "competitor": creative.competitor,
            "classification": {
                "format": creative.format,
                "appeal_type": creative.appeal_type.value,
                "tone": creative.tone.value,
                "has_cta": bool(creative.call_to_action),
            },
            "platform": creative.platform,
            "classified_at": datetime.utcnow().isoformat(),
        }

    def detect_messaging_shifts(self, competitor: str) -> list[MessagingShift]:
        """
        Detect if a competitor has shifted their messaging strategy.

        Compares recent creatives (last N days) to older creatives
        looking for changes in dominant tone, appeal type, or positioning.
        """
        competitor_creatives = [c for c in self._creatives if c.competitor == competitor]
        if len(competitor_creatives) < self.min_creatives_for_shift * 2:
            return []

        cutoff = datetime.utcnow() - timedelta(days=self.shift_detection_window_days)
        recent = [c for c in competitor_creatives if c.observed_at > cutoff]
        older = [c for c in competitor_creatives if c.observed_at <= cutoff]

        if len(recent) < self.min_creatives_for_shift or len(older) < self.min_creatives_for_shift:
            return []

        shifts = []

        # Check tone shift
        tone_shift = self._detect_category_shift(
            [c.tone.value for c in older],
            [c.tone.value for c in recent],
            "tone",
            competitor,
        )
        if tone_shift:
            shifts.append(tone_shift)

        # Check appeal type shift
        appeal_shift = self._detect_category_shift(
            [c.appeal_type.value for c in older],
            [c.appeal_type.value for c in recent],
            "appeal_type",
            competitor,
        )
        if appeal_shift:
            shifts.append(appeal_shift)

        self._shifts.extend(shifts)
        return shifts

    def analyze_vulnerabilities(self, competitors: list[str], category_keywords: list[str]) -> list[Vulnerability]:
        """
        Identify exploitable vulnerabilities across competitors.

        Looks for:
        - Positioning gaps (topics no one addresses)
        - Audience neglect (segments not targeted)
        - Message fatigue (same message repeated excessively)
        - Channel absence (platforms ignored)
        """
        vulnerabilities = []

        # Check for channel absence
        for competitor in competitors:
            comp_creatives = [c for c in self._creatives if c.competitor == competitor]
            if not comp_creatives:
                continue

            platforms_used = set(c.platform for c in comp_creatives)
            all_platforms = {"meta", "google", "tiktok", "amazon", "youtube", "pinterest"}
            missing = all_platforms - platforms_used

            for platform in missing:
                vulnerabilities.append(Vulnerability(
                    vulnerability_id=f"vuln-{competitor}-{platform}",
                    vulnerability_type=VulnerabilityType.CHANNEL_ABSENCE,
                    competitor=competitor,
                    description=f"{competitor} has no presence on {platform}",
                    opportunity_score=0.6,
                    audience_affected=f"{platform} users in target demographic",
                    recommended_angle=f"Establish presence on {platform} before {competitor}",
                    evidence=[f"0 creatives observed on {platform} in last {self.shift_detection_window_days} days"],
                ))

        # Check for message fatigue
        for competitor in competitors:
            comp_creatives = [c for c in self._creatives if c.competitor == competitor]
            if len(comp_creatives) < 5:
                continue

            # Count appeal type frequency
            appeal_counts: dict[str, int] = {}
            for c in comp_creatives:
                appeal_counts[c.appeal_type.value] = appeal_counts.get(c.appeal_type.value, 0) + 1

            total = len(comp_creatives)
            for appeal, count in appeal_counts.items():
                if count / total > 0.7:  # >70% same appeal = fatigue risk
                    vulnerabilities.append(Vulnerability(
                        vulnerability_id=f"vuln-{competitor}-fatigue-{appeal}",
                        vulnerability_type=VulnerabilityType.MESSAGE_FATIGUE,
                        competitor=competitor,
                        description=f"{competitor} over-relies on {appeal} appeal ({count}/{total} creatives)",
                        opportunity_score=0.7,
                        audience_affected="Audiences exposed to repetitive messaging",
                        recommended_angle=f"Use contrasting appeal type to stand out against {competitor}",
                        evidence=[f"{count}/{total} creatives use {appeal} appeal"],
                    ))

        return vulnerabilities

    def compute_share_of_voice(self, competitors: list[str], days: int = 30) -> dict:
        """Compute share of voice by estimated spend or creative volume."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        recent = [c for c in self._creatives if c.observed_at > cutoff]

        total = len(recent)
        if total == 0:
            return {comp: 0.0 for comp in competitors}

        sov = {}
        for comp in competitors:
            comp_count = sum(1 for c in recent if c.competitor == comp)
            sov[comp] = round(comp_count / total, 3)

        return sov

    def _detect_category_shift(
        self, older_values: list[str], recent_values: list[str], shift_type: str, competitor: str
    ) -> Optional[MessagingShift]:
        """Detect if the dominant category has changed."""
        older_dominant = max(set(older_values), key=older_values.count) if older_values else None
        recent_dominant = max(set(recent_values), key=recent_values.count) if recent_values else None

        if older_dominant and recent_dominant and older_dominant != recent_dominant:
            older_pct = older_values.count(older_dominant) / len(older_values)
            recent_pct = recent_values.count(recent_dominant) / len(recent_values)

            if older_pct > 0.4 and recent_pct > 0.4:
                return MessagingShift(
                    competitor=competitor,
                    shift_type=shift_type,
                    previous_state=older_dominant,
                    current_state=recent_dominant,
                    confidence=min(older_pct, recent_pct),
                    evidence_count=len(older_values) + len(recent_values),
                    strategic_implication=f"{competitor} shifted {shift_type} from {older_dominant} to {recent_dominant}",
                )
        return None
