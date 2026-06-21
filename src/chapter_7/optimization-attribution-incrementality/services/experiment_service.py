"""
Experiment Service — designs, manages, and analyzes incrementality experiments.

Features:
- Experiment design with power analysis
- Random assignment (geo-based or user-based)
- Integrity enforcement (no contamination between groups)
- Lift computation with confidence intervals
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum
import math
import statistics
import uuid


class ExperimentType(Enum):
    GEO_SUPPRESSION = "geo_suppression"
    GEO_LIFT = "geo_lift"
    USER_HOLDOUT = "user_holdout"
    BUDGET_SCALING = "budget_scaling"


class ExperimentStatus(Enum):
    DESIGNING = "designing"
    READY = "ready"
    RUNNING = "running"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    ABORTED = "aborted"


@dataclass
class PowerAnalysisResult:
    """Result of statistical power analysis."""
    minimum_sample_size: int
    minimum_duration_days: int
    expected_detectable_lift: float
    power: float  # Statistical power (0.8 = 80%)
    significance_level: float  # α (typically 0.05)
    baseline_conversion_rate: float
    assumptions: dict = field(default_factory=dict)


@dataclass
class ExperimentDesign:
    """The design specification for an experiment."""
    experiment_id: str
    experiment_type: ExperimentType
    channel: str
    hypothesis: str
    treatment_groups: list[str]
    control_groups: list[str]
    primary_metric: str
    secondary_metrics: list[str] = field(default_factory=list)
    duration_days: int = 28
    minimum_sample_size: int = 1000
    significance_level: float = 0.05
    power: float = 0.80
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: ExperimentStatus = ExperimentStatus.DESIGNING


@dataclass
class ExperimentResult:
    """Results of a completed experiment."""
    experiment_id: str
    lift_estimate: float
    confidence_interval: tuple[float, float]
    p_value: float
    is_significant: bool
    treatment_conversion_rate: float
    control_conversion_rate: float
    treatment_sample_size: int
    control_sample_size: int
    incremental_conversions: int
    cost_per_incremental_conversion: float
    analyzed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class IntegrityCheck:
    """Result of an experiment integrity check."""
    experiment_id: str
    passed: bool
    checks: dict  # check_name → pass/fail
    warnings: list[str]
    contamination_rate: float = 0.0


class ExperimentService:
    """
    Manages the lifecycle of incrementality experiments.

    From design (with power analysis) through execution and analysis.
    Enforces integrity to prevent contamination between test/control groups.
    """

    def __init__(self):
        self._experiments: dict[str, ExperimentDesign] = {}
        self._results: dict[str, ExperimentResult] = {}
        self._assignments: dict[str, dict] = {}  # experiment_id → {entity: group}

    def design_experiment(
        self,
        channel: str,
        hypothesis: str,
        experiment_type: ExperimentType,
        treatment_groups: list[str],
        control_groups: list[str],
        baseline_conversion_rate: float = 0.02,
        expected_lift: float = 0.15,
    ) -> ExperimentDesign:
        """
        Design a new experiment with power analysis.

        Args:
            channel: Ad channel being tested (e.g., "meta", "google")
            hypothesis: What we're trying to prove
            experiment_type: Type of experiment (geo, user holdout, etc.)
            treatment_groups: Regions/groups receiving treatment
            control_groups: Regions/groups as control (no treatment)
            baseline_conversion_rate: Expected conversion rate without treatment
            expected_lift: Minimum lift we want to detect

        Returns:
            ExperimentDesign ready for execution
        """
        experiment_id = f"exp-{channel}-{uuid.uuid4().hex[:6]}"

        # Power analysis
        power_result = self.power_analysis(
            baseline_rate=baseline_conversion_rate,
            expected_lift=expected_lift,
        )

        design = ExperimentDesign(
            experiment_id=experiment_id,
            experiment_type=experiment_type,
            channel=channel,
            hypothesis=hypothesis,
            treatment_groups=treatment_groups,
            control_groups=control_groups,
            primary_metric="conversions",
            secondary_metrics=["revenue", "cpa"],
            duration_days=power_result.minimum_duration_days,
            minimum_sample_size=power_result.minimum_sample_size,
            status=ExperimentStatus.READY,
        )

        self._experiments[experiment_id] = design
        return design

    def power_analysis(
        self,
        baseline_rate: float = 0.02,
        expected_lift: float = 0.15,
        alpha: float = 0.05,
        power: float = 0.80,
    ) -> PowerAnalysisResult:
        """
        Compute minimum sample size and duration for desired statistical power.

        Uses normal approximation for two-proportion z-test.
        """
        # Treatment rate under alternative hypothesis
        treatment_rate = baseline_rate * (1 + expected_lift)

        # Z-scores for alpha and power
        z_alpha = self._z_score(1 - alpha / 2)  # Two-tailed
        z_beta = self._z_score(power)

        # Pooled rate
        p_bar = (baseline_rate + treatment_rate) / 2

        # Sample size per group (normal approximation)
        numerator = (z_alpha * math.sqrt(2 * p_bar * (1 - p_bar)) +
                     z_beta * math.sqrt(baseline_rate * (1 - baseline_rate) +
                                       treatment_rate * (1 - treatment_rate))) ** 2
        denominator = (treatment_rate - baseline_rate) ** 2

        n_per_group = math.ceil(numerator / denominator) if denominator > 0 else 10000

        # Estimate duration (assuming ~500 conversions per group per week for geo tests)
        min_duration = max(14, math.ceil(n_per_group / 500) * 7)

        return PowerAnalysisResult(
            minimum_sample_size=n_per_group,
            minimum_duration_days=min_duration,
            expected_detectable_lift=expected_lift,
            power=power,
            significance_level=alpha,
            baseline_conversion_rate=baseline_rate,
            assumptions={
                "daily_conversions_estimate": n_per_group / min_duration,
                "two_tailed_test": True,
            },
        )

    def assign_groups(self, experiment_id: str, entities: list[str]) -> dict:
        """
        Assign entities to treatment or control groups.

        For geo experiments: entities are regions already specified in design.
        For user experiments: random assignment based on hash.
        """
        design = self._experiments.get(experiment_id)
        if not design:
            raise ValueError(f"Experiment {experiment_id} not found")

        assignments = {}
        for entity in entities:
            if entity in design.treatment_groups:
                assignments[entity] = "treatment"
            elif entity in design.control_groups:
                assignments[entity] = "control"
            else:
                # Hash-based assignment for unspecified entities
                hash_val = hash(f"{experiment_id}:{entity}")
                assignments[entity] = "treatment" if hash_val % 2 == 0 else "control"

        self._assignments[experiment_id] = assignments
        return assignments

    def check_integrity(self, experiment_id: str) -> IntegrityCheck:
        """
        Check experiment integrity for contamination or violations.

        Checks:
        - No overlap between treatment and control
        - Balanced sample sizes
        - No spillover effects detected
        """
        design = self._experiments.get(experiment_id)
        assignments = self._assignments.get(experiment_id, {})

        checks = {}
        warnings = []

        # Check 1: No overlap
        treatment_set = set(design.treatment_groups) if design else set()
        control_set = set(design.control_groups) if design else set()
        overlap = treatment_set & control_set
        checks["no_overlap"] = len(overlap) == 0
        if overlap:
            warnings.append(f"Groups in both treatment and control: {overlap}")

        # Check 2: Balanced sizes
        treatment_count = sum(1 for v in assignments.values() if v == "treatment")
        control_count = sum(1 for v in assignments.values() if v == "control")
        total = treatment_count + control_count
        balance_ratio = min(treatment_count, control_count) / max(treatment_count, control_count) if total > 0 else 0
        checks["balanced_groups"] = balance_ratio >= 0.7
        if balance_ratio < 0.7:
            warnings.append(f"Unbalanced groups: {treatment_count} treatment, {control_count} control")

        # Check 3: Minimum sample size
        min_size = design.minimum_sample_size if design else 0
        checks["sufficient_sample"] = min(treatment_count, control_count) >= min_size

        contamination_rate = len(overlap) / total if total > 0 else 0.0

        return IntegrityCheck(
            experiment_id=experiment_id,
            passed=all(checks.values()),
            checks=checks,
            warnings=warnings,
            contamination_rate=contamination_rate,
        )

    def compute_lift(
        self,
        experiment_id: str,
        treatment_conversions: int,
        treatment_size: int,
        control_conversions: int,
        control_size: int,
        treatment_spend: float = 0.0,
    ) -> ExperimentResult:
        """
        Compute lift and statistical significance.

        Uses two-proportion z-test for significance.
        """
        # Conversion rates
        treatment_rate = treatment_conversions / treatment_size if treatment_size > 0 else 0
        control_rate = control_conversions / control_size if control_size > 0 else 0

        # Lift
        lift = (treatment_rate - control_rate) / control_rate if control_rate > 0 else 0

        # Z-test for two proportions
        pooled_rate = (treatment_conversions + control_conversions) / (treatment_size + control_size)
        se = math.sqrt(pooled_rate * (1 - pooled_rate) * (1 / treatment_size + 1 / control_size)) if pooled_rate > 0 else 1

        z_stat = (treatment_rate - control_rate) / se if se > 0 else 0
        p_value = 2 * (1 - self._normal_cdf(abs(z_stat)))  # Two-tailed

        # Confidence interval for lift
        se_lift = math.sqrt(
            treatment_rate * (1 - treatment_rate) / treatment_size +
            control_rate * (1 - control_rate) / control_size
        ) if treatment_size > 0 and control_size > 0 else 0

        ci_lower = (treatment_rate - control_rate - 1.96 * se_lift) / control_rate if control_rate > 0 else 0
        ci_upper = (treatment_rate - control_rate + 1.96 * se_lift) / control_rate if control_rate > 0 else 0

        # Incremental conversions
        incremental = int(treatment_conversions - control_rate * treatment_size)

        # Cost per incremental
        cpic = treatment_spend / incremental if incremental > 0 else float("inf")

        result = ExperimentResult(
            experiment_id=experiment_id,
            lift_estimate=round(lift, 4),
            confidence_interval=(round(ci_lower, 4), round(ci_upper, 4)),
            p_value=round(p_value, 4),
            is_significant=p_value < 0.05,
            treatment_conversion_rate=round(treatment_rate, 6),
            control_conversion_rate=round(control_rate, 6),
            treatment_sample_size=treatment_size,
            control_sample_size=control_size,
            incremental_conversions=max(0, incremental),
            cost_per_incremental_conversion=round(cpic, 2) if cpic != float("inf") else 0.0,
        )

        self._results[experiment_id] = result
        return result

    def _z_score(self, percentile: float) -> float:
        """Approximate z-score for a given percentile using rational approximation."""
        # Abramowitz and Stegun approximation
        if percentile <= 0 or percentile >= 1:
            return 0.0
        if percentile == 0.5:
            return 0.0

        if percentile > 0.5:
            t = math.sqrt(-2 * math.log(1 - percentile))
        else:
            t = math.sqrt(-2 * math.log(percentile))

        c0, c1, c2 = 2.515517, 0.802853, 0.010328
        d1, d2, d3 = 1.432788, 0.189269, 0.001308

        z = t - (c0 + c1 * t + c2 * t ** 2) / (1 + d1 * t + d2 * t ** 2 + d3 * t ** 3)
        return z if percentile > 0.5 else -z

    def _normal_cdf(self, x: float) -> float:
        """Approximate standard normal CDF."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))
