"""
Cross-Platform Coordinator — unified view and management across ad platforms.

Features:
- Unified performance view (normalize metrics across platforms)
- Budget shifting between platforms based on performance
- Audience overlap detection
- Cross-platform frequency management
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum


class Platform(Enum):
    META = "meta"
    GOOGLE = "google"
    AMAZON = "amazon"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"


@dataclass
class PlatformMetrics:
    """Normalized metrics for a platform."""
    platform: Platform
    spend: float
    impressions: int
    clicks: int
    conversions: int
    cpa: float
    ctr: float
    roas: float = 0.0
    frequency: float = 0.0
    reach: int = 0
    budget_allocation_pct: float = 0.0
    efficiency_score: float = 0.0  # 0-1, normalized


@dataclass
class BudgetShiftRecommendation:
    """A recommendation to shift budget between platforms."""
    campaign_id: str
    from_platform: Platform
    to_platform: Platform
    amount: float
    amount_pct_of_total: float
    reasoning: str
    expected_impact: str
    confidence: float
    priority: int = 0  # 1-10


@dataclass
class OverlapDetection:
    """Detected audience overlap between platforms."""
    platform_a: Platform
    platform_b: Platform
    estimated_overlap_pct: float
    overlap_audience_size: int
    excess_frequency: float
    recommendation: str


@dataclass
class UnifiedCampaignView:
    """Cross-platform campaign summary."""
    campaign_id: str
    total_spend: float
    total_budget: float
    total_conversions: int
    blended_cpa: float
    blended_ctr: float
    blended_roas: float
    platforms: list[PlatformMetrics]
    cross_platform_frequency: float
    overlap_detections: list[OverlapDetection]
    budget_shift_recommendations: list[BudgetShiftRecommendation]
    generated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CoordinatorConfig:
    """Configuration for cross-platform coordination."""
    max_budget_shift_pct: float = 0.20  # Max 20% shift in one action
    min_spend_for_evaluation: float = 100.0  # Min spend before evaluating platform
    frequency_cap: float = 4.0  # Cross-platform frequency cap
    efficiency_weight: float = 0.6  # Weight for CPA efficiency
    volume_weight: float = 0.4  # Weight for conversion volume
    overlap_threshold: float = 0.30  # 30% overlap = action needed


class CrossPlatformCoordinator:
    """
    Coordinates campaign execution across multiple ad platforms.

    Provides:
    - Unified performance view with normalized metrics
    - Dynamic budget allocation based on platform efficiency
    - Overlap detection to prevent audience fatigue
    - Cross-platform frequency management
    """

    def __init__(self, config: Optional[CoordinatorConfig] = None):
        self.config = config or CoordinatorConfig()

    def build_unified_view(
        self, campaign_id: str, platform_data: dict[str, dict], total_budget: float
    ) -> UnifiedCampaignView:
        """
        Build a unified cross-platform view from per-platform metrics.

        Args:
            campaign_id: Campaign identifier
            platform_data: Dict of platform name → metrics dict
            total_budget: Total campaign budget

        Returns:
            UnifiedCampaignView with normalized metrics and recommendations
        """
        platforms = []
        total_spend = 0.0
        total_conversions = 0
        total_clicks = 0
        total_impressions = 0

        for platform_name, metrics in platform_data.items():
            platform = Platform(platform_name)
            spend = metrics.get("spend", 0.0)
            conversions = metrics.get("conversions", 0)
            impressions = metrics.get("impressions", 0)
            clicks = metrics.get("clicks", 0)
            cpa = metrics.get("cpa", 0.0)
            ctr = metrics.get("ctr", 0.0)
            frequency = metrics.get("frequency", 0.0)

            total_spend += spend
            total_conversions += conversions
            total_clicks += clicks
            total_impressions += impressions

            platforms.append(PlatformMetrics(
                platform=platform,
                spend=spend,
                impressions=impressions,
                clicks=clicks,
                conversions=conversions,
                cpa=cpa,
                ctr=ctr,
                frequency=frequency,
                budget_allocation_pct=spend / total_budget if total_budget > 0 else 0.0,
            ))

        # Compute efficiency scores
        platforms = self._compute_efficiency_scores(platforms)

        # Blended metrics
        blended_cpa = total_spend / total_conversions if total_conversions > 0 else 0.0
        blended_ctr = total_clicks / total_impressions if total_impressions > 0 else 0.0
        blended_roas = sum(m.roas * m.spend for m in platforms) / total_spend if total_spend > 0 else 0.0

        # Cross-platform frequency estimate
        cross_frequency = self._estimate_cross_platform_frequency(platforms)

        # Detect overlaps
        overlaps = self._detect_overlaps(platforms)

        # Budget shift recommendations
        recommendations = self._recommend_budget_shifts(campaign_id, platforms, total_budget)

        return UnifiedCampaignView(
            campaign_id=campaign_id,
            total_spend=total_spend,
            total_budget=total_budget,
            total_conversions=total_conversions,
            blended_cpa=round(blended_cpa, 2),
            blended_ctr=round(blended_ctr, 4),
            blended_roas=round(blended_roas, 2),
            platforms=platforms,
            cross_platform_frequency=cross_frequency,
            overlap_detections=overlaps,
            budget_shift_recommendations=recommendations,
        )

    def recommend_budget_shift(
        self, campaign_id: str, platforms: list[PlatformMetrics], total_budget: float
    ) -> list[BudgetShiftRecommendation]:
        """Generate budget shift recommendations based on platform efficiency."""
        return self._recommend_budget_shifts(campaign_id, platforms, total_budget)

    def _compute_efficiency_scores(self, platforms: list[PlatformMetrics]) -> list[PlatformMetrics]:
        """Compute normalized efficiency score (0-1) for each platform."""
        if not platforms:
            return platforms

        # Lower CPA = better efficiency
        cpas = [p.cpa for p in platforms if p.cpa > 0]
        if not cpas:
            return platforms

        min_cpa = min(cpas)
        max_cpa = max(cpas)
        cpa_range = max_cpa - min_cpa if max_cpa > min_cpa else 1.0

        for platform in platforms:
            if platform.cpa > 0:
                # Invert: lower CPA → higher score
                cpa_score = 1.0 - (platform.cpa - min_cpa) / cpa_range
            else:
                cpa_score = 0.5

            # Volume score based on conversions
            max_conv = max(p.conversions for p in platforms)
            vol_score = platform.conversions / max_conv if max_conv > 0 else 0.0

            platform.efficiency_score = round(
                cpa_score * self.config.efficiency_weight + vol_score * self.config.volume_weight, 3
            )

        return platforms

    def _estimate_cross_platform_frequency(self, platforms: list[PlatformMetrics]) -> float:
        """Estimate total cross-platform frequency for the target audience."""
        # Simplified: weighted sum with overlap factor
        total_frequency = sum(p.frequency for p in platforms)
        # Assume ~30% overlap between platforms
        overlap_factor = 0.7  # Reduces total since some impressions hit same users
        return round(total_frequency * overlap_factor, 1)

    def _detect_overlaps(self, platforms: list[PlatformMetrics]) -> list[OverlapDetection]:
        """Detect audience overlap between platform pairs."""
        overlaps = []

        # Known platform overlap estimates (based on industry data)
        overlap_matrix = {
            (Platform.META, Platform.GOOGLE): 0.35,
            (Platform.META, Platform.TIKTOK): 0.25,
            (Platform.META, Platform.YOUTUBE): 0.40,
            (Platform.GOOGLE, Platform.YOUTUBE): 0.50,
            (Platform.GOOGLE, Platform.AMAZON): 0.20,
            (Platform.TIKTOK, Platform.YOUTUBE): 0.30,
        }

        active_platforms = [p for p in platforms if p.spend > self.config.min_spend_for_evaluation]

        for i, p1 in enumerate(active_platforms):
            for p2 in active_platforms[i + 1:]:
                pair = (p1.platform, p2.platform)
                reverse_pair = (p2.platform, p1.platform)
                overlap_pct = overlap_matrix.get(pair, overlap_matrix.get(reverse_pair, 0.15))

                if overlap_pct >= self.config.overlap_threshold:
                    combined_freq = p1.frequency + p2.frequency
                    excess = max(0, combined_freq * overlap_pct - self.config.frequency_cap)

                    overlaps.append(OverlapDetection(
                        platform_a=p1.platform,
                        platform_b=p2.platform,
                        estimated_overlap_pct=overlap_pct,
                        overlap_audience_size=int(min(p1.reach, p2.reach) * overlap_pct),
                        excess_frequency=round(excess, 1),
                        recommendation=self._overlap_recommendation(p1, p2, excess),
                    ))

        return overlaps

    def _recommend_budget_shifts(
        self, campaign_id: str, platforms: list[PlatformMetrics], total_budget: float
    ) -> list[BudgetShiftRecommendation]:
        """Generate budget shift recommendations."""
        recommendations = []

        if len(platforms) < 2:
            return recommendations

        # Find best and worst performing platforms
        eligible = [p for p in platforms if p.spend >= self.config.min_spend_for_evaluation]
        if len(eligible) < 2:
            return recommendations

        sorted_by_efficiency = sorted(eligible, key=lambda p: p.efficiency_score, reverse=True)
        best = sorted_by_efficiency[0]
        worst = sorted_by_efficiency[-1]

        # Only recommend if meaningful efficiency gap
        if best.efficiency_score - worst.efficiency_score > 0.2:
            shift_amount = min(
                worst.spend * self.config.max_budget_shift_pct,
                total_budget * 0.05,  # Never shift more than 5% of total in one action
            )

            recommendations.append(BudgetShiftRecommendation(
                campaign_id=campaign_id,
                from_platform=worst.platform,
                to_platform=best.platform,
                amount=round(shift_amount, 2),
                amount_pct_of_total=round(shift_amount / total_budget, 4) if total_budget > 0 else 0.0,
                reasoning=(
                    f"{best.platform.value} efficiency score ({best.efficiency_score:.2f}) "
                    f"significantly outperforms {worst.platform.value} ({worst.efficiency_score:.2f}). "
                    f"CPA: ${best.cpa:.2f} vs ${worst.cpa:.2f}"
                ),
                expected_impact=f"Estimated CPA reduction of ${(worst.cpa - best.cpa) * 0.3:.2f}",
                confidence=min(0.85, (best.efficiency_score - worst.efficiency_score)),
                priority=7,
            ))

        return recommendations

    def _overlap_recommendation(
        self, p1: PlatformMetrics, p2: PlatformMetrics, excess_frequency: float
    ) -> str:
        """Generate recommendation for overlap management."""
        if excess_frequency > 2.0:
            return (
                f"High overlap between {p1.platform.value} and {p2.platform.value}. "
                f"Consider audience exclusions or reduce combined frequency cap."
            )
        elif excess_frequency > 0:
            return (
                f"Moderate overlap detected. Monitor cross-platform frequency and "
                f"consider sequential messaging strategy."
            )
        return "Overlap within acceptable range. No action needed."
