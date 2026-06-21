"""
Metric Normalizer — transforms platform-specific metrics into canonical schema.

Features:
- Platform-specific field mapping (Meta, Google, Amazon, TikTok)
- Data type coercion (string → numeric)
- Derived metric computation (CTR, CPA, ROAS)
- Validation and quality flags
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any
from enum import Enum


class SourcePlatform(Enum):
    META = "meta"
    GOOGLE = "google"
    AMAZON = "amazon"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"


@dataclass
class CanonicalMetric:
    """Canonical (normalized) metric record."""
    record_id: str
    campaign_id: str
    platform: SourcePlatform
    date: str  # YYYY-MM-DD
    impressions: int = 0
    clicks: int = 0
    spend: float = 0.0
    conversions: int = 0
    revenue: float = 0.0
    ctr: float = 0.0
    cpc: float = 0.0
    cpa: float = 0.0
    cpm: float = 0.0
    roas: float = 0.0
    reach: int = 0
    frequency: float = 0.0
    video_views: int = 0
    video_completions: int = 0
    normalized_at: datetime = field(default_factory=datetime.utcnow)
    quality_flags: list[str] = field(default_factory=list)
    raw_source: str = ""  # Reference to original data


@dataclass
class NormalizationResult:
    """Result of a normalization operation."""
    records: list[CanonicalMetric]
    total_raw_records: int
    successfully_normalized: int
    failed_records: int
    quality_warnings: list[str]
    platform: SourcePlatform
    processed_at: datetime = field(default_factory=datetime.utcnow)


class MetricNormalizer:
    """
    Normalizes platform-specific advertising metrics into a canonical schema.

    Each platform has different field names, data types, and available metrics.
    This normalizer maps them all to a unified CanonicalMetric format.
    """

    # Field mappings: platform field → canonical field
    FIELD_MAPS = {
        SourcePlatform.META: {
            "campaign_id": "campaign_id",
            "date_start": "date",
            "impressions": "impressions",
            "clicks": "clicks",
            "spend": "spend",
            "ctr": "ctr",
            "cpc": "cpc",
            "cpm": "cpm",
            "reach": "reach",
            "frequency": "frequency",
            "video_p100_watched_actions": "video_completions",
            "video_play_actions": "video_views",
        },
        SourcePlatform.GOOGLE: {
            "campaign_id": "campaign_id",
            "segments_date": "date",
            "metrics_impressions": "impressions",
            "metrics_clicks": "clicks",
            "metrics_cost_micros": "spend",  # Needs conversion from micros
            "metrics_conversions": "conversions",
            "metrics_conversions_value": "revenue",
            "metrics_ctr": "ctr",
            "metrics_average_cpc": "cpc",
            "metrics_video_views": "video_views",
            "metrics_video_quartile_p100_rate": "video_completions",
        },
        SourcePlatform.AMAZON: {
            "campaignId": "campaign_id",
            "date": "date",
            "impressions": "impressions",
            "clicks": "clicks",
            "cost": "spend",
            "purchases14d": "conversions",
            "sales14d": "revenue",
            "clickThroughRate": "ctr",
            "costPerClick": "cpc",
        },
        SourcePlatform.TIKTOK: {
            "campaign_id": "campaign_id",
            "stat_time_day": "date",
            "show_cnt": "impressions",
            "click_cnt": "clicks",
            "spend": "spend",
            "convert_cnt": "conversions",
            "total_purchase_value": "revenue",
            "ctr": "ctr",
            "cpc": "cpc",
            "cpm": "cpm",
            "reach": "reach",
            "frequency": "frequency",
            "video_play_actions": "video_views",
            "video_watched_6s": "video_completions",
        },
    }

    def __init__(self):
        self._normalization_count = 0

    def normalize(self, platform: SourcePlatform, raw_records: list[dict]) -> NormalizationResult:
        """
        Normalize raw platform records into canonical format.

        Args:
            platform: Source platform
            raw_records: List of raw API response records

        Returns:
            NormalizationResult with normalized records and quality info
        """
        results = []
        failed = 0
        warnings = []

        field_map = self.FIELD_MAPS.get(platform, {})

        for i, raw in enumerate(raw_records):
            try:
                canonical = self._normalize_record(platform, raw, field_map, i)
                # Compute derived metrics
                canonical = self._compute_derived(canonical)
                # Validate
                quality_flags = self._validate(canonical)
                canonical.quality_flags = quality_flags
                if quality_flags:
                    warnings.extend(quality_flags)
                results.append(canonical)
            except Exception as e:
                failed += 1
                warnings.append(f"Record {i} failed: {str(e)}")

        return NormalizationResult(
            records=results,
            total_raw_records=len(raw_records),
            successfully_normalized=len(results),
            failed_records=failed,
            quality_warnings=warnings,
            platform=platform,
        )

    def normalize_meta(self, raw_records: list[dict]) -> NormalizationResult:
        """Convenience method for Meta (Facebook) normalization."""
        return self.normalize(SourcePlatform.META, raw_records)

    def normalize_google(self, raw_records: list[dict]) -> NormalizationResult:
        """Convenience method for Google Ads normalization."""
        return self.normalize(SourcePlatform.GOOGLE, raw_records)

    def _normalize_record(
        self, platform: SourcePlatform, raw: dict, field_map: dict, index: int
    ) -> CanonicalMetric:
        """Normalize a single raw record."""
        self._normalization_count += 1
        record_id = f"norm-{platform.value}-{self._normalization_count:08d}"

        # Map fields
        mapped: dict[str, Any] = {"record_id": record_id, "platform": platform}

        for raw_field, canonical_field in field_map.items():
            value = self._extract_nested(raw, raw_field)
            if value is not None:
                mapped[canonical_field] = self._coerce_type(canonical_field, value, platform)

        # Handle platform-specific quirks
        mapped = self._apply_platform_transforms(platform, raw, mapped)

        # Extract conversions from Meta's nested 'actions' array
        if platform == SourcePlatform.META and "actions" in raw:
            conversions = self._extract_meta_conversions(raw["actions"])
            mapped["conversions"] = conversions

        return CanonicalMetric(**{k: v for k, v in mapped.items() if k in CanonicalMetric.__dataclass_fields__})

    def _extract_nested(self, data: dict, field_path: str) -> Any:
        """Extract a value, handling nested keys with underscore separators."""
        # Try direct key first
        if field_path in data:
            return data[field_path]

        # Try dot notation
        parts = field_path.split("_", 1)
        if len(parts) == 2 and parts[0] in data:
            nested = data[parts[0]]
            if isinstance(nested, dict) and parts[1] in nested:
                return nested[parts[1]]

        return None

    def _coerce_type(self, field_name: str, value: Any, platform: SourcePlatform) -> Any:
        """Coerce value to the expected type for the canonical field."""
        int_fields = {"impressions", "clicks", "conversions", "reach", "video_views", "video_completions"}
        float_fields = {"spend", "ctr", "cpc", "cpa", "cpm", "roas", "frequency", "revenue"}

        if field_name in int_fields:
            try:
                return int(float(str(value).replace(",", "")))
            except (ValueError, TypeError):
                return 0

        if field_name in float_fields:
            try:
                result = float(str(value).replace(",", "").replace("$", ""))
                # Google cost is in micros
                if platform == SourcePlatform.GOOGLE and field_name == "spend":
                    result = result / 1_000_000
                return round(result, 4)
            except (ValueError, TypeError):
                return 0.0

        return value

    def _apply_platform_transforms(
        self, platform: SourcePlatform, raw: dict, mapped: dict
    ) -> dict:
        """Apply platform-specific transformations."""
        if platform == SourcePlatform.META:
            # Meta sometimes returns date range, use start date
            if "date_start" in raw:
                mapped["date"] = raw["date_start"]

        elif platform == SourcePlatform.GOOGLE:
            # Google uses segments.date format
            if "segments" in raw and isinstance(raw["segments"], dict):
                mapped["date"] = raw["segments"].get("date", mapped.get("date", ""))

        elif platform == SourcePlatform.TIKTOK:
            # TikTok stat_time_day is in different format
            date_val = mapped.get("date", "")
            if "T" in str(date_val):
                mapped["date"] = str(date_val).split("T")[0]

        return mapped

    def _extract_meta_conversions(self, actions: list) -> int:
        """Extract purchase conversions from Meta's actions array."""
        if not isinstance(actions, list):
            return 0

        for action in actions:
            if isinstance(action, dict):
                action_type = action.get("action_type", "")
                if action_type in ("purchase", "offsite_conversion.fb_pixel_purchase"):
                    try:
                        return int(action.get("value", 0))
                    except (ValueError, TypeError):
                        pass
        return 0

    def _compute_derived(self, metric: CanonicalMetric) -> CanonicalMetric:
        """Compute derived metrics that may not be provided by the platform."""
        # CTR
        if metric.ctr == 0 and metric.impressions > 0:
            metric.ctr = round(metric.clicks / metric.impressions, 6)

        # CPC
        if metric.cpc == 0 and metric.clicks > 0:
            metric.cpc = round(metric.spend / metric.clicks, 4)

        # CPA
        if metric.cpa == 0 and metric.conversions > 0:
            metric.cpa = round(metric.spend / metric.conversions, 2)

        # CPM
        if metric.cpm == 0 and metric.impressions > 0:
            metric.cpm = round((metric.spend / metric.impressions) * 1000, 2)

        # ROAS
        if metric.roas == 0 and metric.spend > 0 and metric.revenue > 0:
            metric.roas = round(metric.revenue / metric.spend, 2)

        return metric

    def _validate(self, metric: CanonicalMetric) -> list[str]:
        """Validate a canonical metric record and return quality flags."""
        flags = []

        if metric.impressions > 0 and metric.clicks > metric.impressions:
            flags.append("clicks_exceed_impressions")

        if metric.ctr > 1.0:
            flags.append("ctr_exceeds_100pct")

        if metric.spend < 0:
            flags.append("negative_spend")

        if metric.impressions == 0 and metric.spend > 0:
            flags.append("spend_without_impressions")

        if not metric.date or len(metric.date) != 10:
            flags.append("invalid_date_format")

        return flags
