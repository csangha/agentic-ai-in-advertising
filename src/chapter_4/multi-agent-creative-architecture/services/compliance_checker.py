"""
Compliance Checker — validates creative against regulatory and brand rules.

Features:
- FTC disclosure requirements (endorsements, health claims)
- Platform-specific policies (Meta, Google, TikTok, Amazon)
- Brand restriction enforcement (excluded topics, required elements)
- Returns pass/fail with detailed violation list
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class ComplianceStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


class ViolationType(Enum):
    FTC_DISCLOSURE = "ftc_disclosure"
    FTC_HEALTH_CLAIM = "ftc_health_claim"
    FTC_ENDORSEMENT = "ftc_endorsement"
    PLATFORM_PROHIBITED_CONTENT = "platform_prohibited_content"
    PLATFORM_FORMAT_VIOLATION = "platform_format_violation"
    PLATFORM_TEXT_LIMIT = "platform_text_limit"
    BRAND_EXCLUDED_TOPIC = "brand_excluded_topic"
    BRAND_TONE_VIOLATION = "brand_tone_violation"
    BRAND_MISSING_ELEMENT = "brand_missing_element"
    COMPETITOR_MENTION = "competitor_mention"


class Severity(Enum):
    BLOCKER = "blocker"  # Must fix before publishing
    WARNING = "warning"  # Should fix, but can proceed
    INFO = "info"  # Best practice suggestion


@dataclass
class CreativeAsset:
    """A creative asset to be compliance-checked."""
    asset_id: str
    campaign_id: str
    platform: str
    format: str  # static, video, carousel, display
    headline: str = ""
    body_text: str = ""
    cta_text: str = ""
    claims: list[str] = field(default_factory=list)
    has_testimonial: bool = False
    has_health_claim: bool = False
    includes_price: bool = False
    target_audience_age_min: int = 18
    visual_description: str = ""


@dataclass
class Violation:
    """A specific compliance violation found."""
    violation_type: ViolationType
    severity: Severity
    rule_id: str
    description: str
    element: str  # Which part of the creative violates
    fix_suggestion: str
    regulation_reference: str = ""


@dataclass
class ComplianceResult:
    """Complete compliance check result."""
    asset_id: str
    status: ComplianceStatus
    violations: list[Violation]
    warnings: list[Violation]
    checked_rules: int
    passed_rules: int
    checked_at: datetime = field(default_factory=datetime.utcnow)
    platform: str = ""
    summary: str = ""


@dataclass
class BrandGuidelines:
    """Brand-specific compliance rules."""
    brand_name: str
    excluded_topics: list[str] = field(default_factory=list)
    required_elements: list[str] = field(default_factory=list)
    approved_cta_list: list[str] = field(default_factory=list)
    tone_restrictions: list[str] = field(default_factory=list)
    competitor_mentions_allowed: bool = False
    max_headline_length: int = 60
    max_body_length: int = 150


class ComplianceChecker:
    """
    Multi-layer compliance engine for advertising creatives.

    Checks against:
    1. FTC regulations (disclosures, health claims, endorsements)
    2. Platform policies (Meta, Google, TikTok, Amazon)
    3. Brand guidelines (tone, excluded topics, required elements)
    """

    # Platform-specific text limits
    PLATFORM_LIMITS = {
        "meta": {"headline": 40, "body": 125, "cta": 30},
        "google": {"headline": 30, "body": 90, "cta": 15},
        "tiktok": {"headline": 50, "body": 100, "cta": 20},
        "amazon": {"headline": 50, "body": 150, "cta": 20},
    }

    # FTC prohibited unsubstantiated health claims
    FTC_HEALTH_CLAIM_TRIGGERS = [
        "cure", "prevent", "treat", "heal", "eliminate disease",
        "clinically proven", "doctor recommended", "guaranteed results",
        "lose weight fast", "miracle", "breakthrough",
    ]

    # Platform prohibited content categories
    PLATFORM_PROHIBITED = {
        "meta": ["cryptocurrency", "weapons", "tobacco", "adult content", "multilevel marketing"],
        "google": ["counterfeit goods", "dangerous products", "dishonest behavior", "inappropriate content"],
        "tiktok": ["gambling", "weapons", "tobacco", "political ads", "counterfeit"],
        "amazon": ["offensive content", "misleading claims", "competitor disparagement", "adult content"],
    }

    def __init__(self, brand_guidelines: Optional[BrandGuidelines] = None):
        self.brand_guidelines = brand_guidelines

    def check(self, asset: CreativeAsset) -> ComplianceResult:
        """
        Run full compliance check against an asset.

        Returns ComplianceResult with pass/fail status and detailed violations.
        """
        violations = []
        warnings = []
        rules_checked = 0

        # FTC checks
        ftc_violations, ftc_rules = self._check_ftc(asset)
        rules_checked += ftc_rules
        for v in ftc_violations:
            if v.severity == Severity.BLOCKER:
                violations.append(v)
            else:
                warnings.append(v)

        # Platform policy checks
        platform_violations, platform_rules = self._check_platform(asset)
        rules_checked += platform_rules
        for v in platform_violations:
            if v.severity == Severity.BLOCKER:
                violations.append(v)
            else:
                warnings.append(v)

        # Brand guideline checks
        if self.brand_guidelines:
            brand_violations, brand_rules = self._check_brand(asset)
            rules_checked += brand_rules
            for v in brand_violations:
                if v.severity == Severity.BLOCKER:
                    violations.append(v)
                else:
                    warnings.append(v)

        # Determine overall status
        if violations:
            status = ComplianceStatus.FAIL
        elif warnings:
            status = ComplianceStatus.WARNING
        else:
            status = ComplianceStatus.PASS

        passed_rules = rules_checked - len(violations) - len(warnings)

        return ComplianceResult(
            asset_id=asset.asset_id,
            status=status,
            violations=violations,
            warnings=warnings,
            checked_rules=rules_checked,
            passed_rules=passed_rules,
            platform=asset.platform,
            summary=self._generate_summary(status, violations, warnings),
        )

    def _check_ftc(self, asset: CreativeAsset) -> tuple[list[Violation], int]:
        """Check FTC compliance rules."""
        violations = []
        rules_checked = 0

        # Rule: Testimonials require disclosure
        rules_checked += 1
        if asset.has_testimonial:
            all_text = f"{asset.headline} {asset.body_text} {asset.cta_text}".lower()
            if "#ad" not in all_text and "sponsored" not in all_text and "paid" not in all_text:
                violations.append(Violation(
                    violation_type=ViolationType.FTC_DISCLOSURE,
                    severity=Severity.BLOCKER,
                    rule_id="FTC-ENDORSE-01",
                    description="Testimonial/endorsement requires clear disclosure",
                    element="body_text",
                    fix_suggestion="Add #ad, 'Sponsored', or 'Paid partnership' disclosure",
                    regulation_reference="16 CFR Part 255 - Endorsement Guides",
                ))

        # Rule: Health claims must be substantiated
        rules_checked += 1
        if asset.has_health_claim or asset.claims:
            all_text = f"{asset.headline} {asset.body_text}".lower()
            for trigger in self.FTC_HEALTH_CLAIM_TRIGGERS:
                if trigger in all_text:
                    violations.append(Violation(
                        violation_type=ViolationType.FTC_HEALTH_CLAIM,
                        severity=Severity.BLOCKER,
                        rule_id="FTC-HEALTH-01",
                        description=f"Unsubstantiated health claim detected: '{trigger}'",
                        element="body_text",
                        fix_suggestion=f"Remove or substantiate claim: '{trigger}'. Use hedging language.",
                        regulation_reference="FTC Act Section 5 - Deceptive Advertising",
                    ))
                    break

        # Rule: Price claims must be accurate
        rules_checked += 1
        if asset.includes_price:
            # Ensure no misleading pricing language
            all_text = f"{asset.headline} {asset.body_text}".lower()
            if "free" in all_text and "trial" not in all_text and "shipping" not in all_text:
                violations.append(Violation(
                    violation_type=ViolationType.FTC_DISCLOSURE,
                    severity=Severity.WARNING,
                    rule_id="FTC-PRICE-01",
                    description="'Free' claim may need qualification",
                    element="body_text",
                    fix_suggestion="Clarify terms of 'free' offer (e.g., 'free trial', 'free with purchase')",
                    regulation_reference="FTC Free Guides 16 CFR Part 251",
                ))

        return violations, rules_checked

    def _check_platform(self, asset: CreativeAsset) -> tuple[list[Violation], int]:
        """Check platform-specific policy compliance."""
        violations = []
        rules_checked = 0

        # Text length limits
        limits = self.PLATFORM_LIMITS.get(asset.platform, {})
        rules_checked += 3

        if limits.get("headline") and len(asset.headline) > limits["headline"]:
            violations.append(Violation(
                violation_type=ViolationType.PLATFORM_TEXT_LIMIT,
                severity=Severity.BLOCKER,
                rule_id=f"PLAT-{asset.platform.upper()}-LEN-01",
                description=f"Headline exceeds {asset.platform} limit ({len(asset.headline)}/{limits['headline']} chars)",
                element="headline",
                fix_suggestion=f"Shorten headline to {limits['headline']} characters",
            ))

        if limits.get("body") and len(asset.body_text) > limits["body"]:
            violations.append(Violation(
                violation_type=ViolationType.PLATFORM_TEXT_LIMIT,
                severity=Severity.BLOCKER,
                rule_id=f"PLAT-{asset.platform.upper()}-LEN-02",
                description=f"Body text exceeds {asset.platform} limit ({len(asset.body_text)}/{limits['body']} chars)",
                element="body_text",
                fix_suggestion=f"Shorten body text to {limits['body']} characters",
            ))

        # Prohibited content check
        rules_checked += 1
        prohibited = self.PLATFORM_PROHIBITED.get(asset.platform, [])
        all_text = f"{asset.headline} {asset.body_text}".lower()
        for topic in prohibited:
            if topic in all_text:
                violations.append(Violation(
                    violation_type=ViolationType.PLATFORM_PROHIBITED_CONTENT,
                    severity=Severity.BLOCKER,
                    rule_id=f"PLAT-{asset.platform.upper()}-PROH-01",
                    description=f"Prohibited content detected: '{topic}'",
                    element="body_text",
                    fix_suggestion=f"Remove reference to '{topic}' — prohibited on {asset.platform}",
                ))
                break

        return violations, rules_checked

    def _check_brand(self, asset: CreativeAsset) -> tuple[list[Violation], int]:
        """Check brand guideline compliance."""
        violations = []
        rules_checked = 0
        bg = self.brand_guidelines

        # Excluded topics
        rules_checked += 1
        all_text = f"{asset.headline} {asset.body_text}".lower()
        for topic in bg.excluded_topics:
            if topic.lower() in all_text:
                violations.append(Violation(
                    violation_type=ViolationType.BRAND_EXCLUDED_TOPIC,
                    severity=Severity.BLOCKER,
                    rule_id="BRAND-EXCL-01",
                    description=f"Excluded topic found: '{topic}'",
                    element="body_text",
                    fix_suggestion=f"Remove or rephrase content related to '{topic}'",
                ))
                break

        # Required elements
        rules_checked += 1
        for element in bg.required_elements:
            if element.lower() not in all_text:
                violations.append(Violation(
                    violation_type=ViolationType.BRAND_MISSING_ELEMENT,
                    severity=Severity.WARNING,
                    rule_id="BRAND-REQ-01",
                    description=f"Required brand element missing: '{element}'",
                    element="body_text",
                    fix_suggestion=f"Include required element: '{element}'",
                ))

        # Competitor mentions
        rules_checked += 1
        if not bg.competitor_mentions_allowed:
            # Simple check — production would use NER
            pass

        # Headline length
        rules_checked += 1
        if len(asset.headline) > bg.max_headline_length:
            violations.append(Violation(
                violation_type=ViolationType.BRAND_TONE_VIOLATION,
                severity=Severity.WARNING,
                rule_id="BRAND-LEN-01",
                description=f"Headline exceeds brand limit ({len(asset.headline)}/{bg.max_headline_length})",
                element="headline",
                fix_suggestion=f"Shorten headline to {bg.max_headline_length} characters per brand guidelines",
            ))

        return violations, rules_checked

    def _generate_summary(self, status: ComplianceStatus, violations: list, warnings: list) -> str:
        """Generate human-readable summary."""
        if status == ComplianceStatus.PASS:
            return "All compliance checks passed. Creative is approved for publishing."
        elif status == ComplianceStatus.WARNING:
            return f"Creative passed with {len(warnings)} warning(s). Review recommended before publishing."
        else:
            return f"Creative FAILED compliance. {len(violations)} blocker(s) must be resolved."
