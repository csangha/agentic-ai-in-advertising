"""
Governance Engine — policy enforcement, audit logging, and compliance.

Features:
- Policy enforcement (spending limits, approval requirements, guardrails)
- Comprehensive audit logging (every agent action recorded)
- Compliance queries (who did what, when, why)
- Monthly governance reports
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum
import hashlib
import json


class PolicyType(Enum):
    SPENDING_LIMIT = "spending_limit"
    APPROVAL_REQUIRED = "approval_required"
    RATE_LIMIT = "rate_limit"
    CONTENT_RESTRICTION = "content_restriction"
    DATA_ACCESS = "data_access"
    ESCALATION_RULE = "escalation_rule"


class PolicyDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    RATE_LIMITED = "rate_limited"


class AuditEventType(Enum):
    ACTION_EXECUTED = "action_executed"
    ACTION_BLOCKED = "action_blocked"
    POLICY_CHECKED = "policy_checked"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    ESCALATION = "escalation"
    CONFIG_CHANGED = "config_changed"
    EXPERIMENT_STARTED = "experiment_started"
    BUDGET_MODIFIED = "budget_modified"
    CREATIVE_DEPLOYED = "creative_deployed"


@dataclass
class GovernancePolicy:
    """A governance policy that constrains agent behavior."""
    policy_id: str
    policy_type: PolicyType
    name: str
    description: str
    conditions: dict  # Conditions under which policy applies
    enforcement: PolicyDecision  # What happens when triggered
    parameters: dict = field(default_factory=dict)
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = "system"


@dataclass
class AuditEntry:
    """A single audit log entry."""
    entry_id: str
    event_type: AuditEventType
    agent_id: str
    campaign_id: str
    action: str
    details: dict
    policy_applied: Optional[str] = None
    decision: Optional[PolicyDecision] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    organization_id: str = ""
    ip_address: str = ""
    session_id: str = ""


@dataclass
class PolicyCheckResult:
    """Result of checking an action against governance policies."""
    allowed: bool
    decision: PolicyDecision
    applicable_policies: list[str]
    violations: list[str]
    reasoning: str


@dataclass
class GovernanceReport:
    """Monthly governance report."""
    report_id: str
    organization_id: str
    period_start: datetime
    period_end: datetime
    total_actions: int
    actions_allowed: int
    actions_blocked: int
    actions_requiring_approval: int
    top_agents_by_action: dict
    policy_violation_summary: dict
    spending_summary: dict
    generated_at: datetime = field(default_factory=datetime.utcnow)


class GovernanceEngine:
    """
    Enforces governance policies and maintains comprehensive audit trail.

    Every agent action passes through the governance engine which:
    1. Checks applicable policies
    2. Allows, denies, or requires approval
    3. Logs the decision and outcome to the audit trail
    """

    def __init__(self, organization_id: str = "default"):
        self.organization_id = organization_id
        self._policies: dict[str, GovernancePolicy] = {}
        self._audit_log: list[AuditEntry] = []
        self._action_counts: dict[str, int] = {}  # "agent_id:action" → count today

        # Register default policies
        self._register_default_policies()

    def add_policy(self, policy: GovernancePolicy) -> None:
        """Add a governance policy."""
        self._policies[policy.policy_id] = policy

    def remove_policy(self, policy_id: str) -> bool:
        """Remove a governance policy."""
        if policy_id in self._policies:
            del self._policies[policy_id]
            return True
        return False

    def check_action(
        self,
        agent_id: str,
        action: str,
        campaign_id: str,
        context: dict = None,
    ) -> PolicyCheckResult:
        """
        Check if an action is allowed under current governance policies.

        Args:
            agent_id: The agent attempting the action
            action: Action being attempted (e.g., "adjust_bid", "shift_budget")
            campaign_id: Campaign this action affects
            context: Additional context (amount, platform, etc.)

        Returns:
            PolicyCheckResult with allow/deny decision and reasoning
        """
        context = context or {}
        applicable_policies = []
        violations = []
        decision = PolicyDecision.ALLOW

        for policy in self._policies.values():
            if not policy.enabled:
                continue

            if self._policy_applies(policy, agent_id, action, campaign_id, context):
                applicable_policies.append(policy.policy_id)

                # Check if action violates this policy
                violation = self._check_violation(policy, agent_id, action, context)
                if violation:
                    violations.append(violation)
                    # Most restrictive decision wins
                    if policy.enforcement == PolicyDecision.DENY:
                        decision = PolicyDecision.DENY
                    elif policy.enforcement == PolicyDecision.REQUIRE_APPROVAL and decision != PolicyDecision.DENY:
                        decision = PolicyDecision.REQUIRE_APPROVAL
                    elif policy.enforcement == PolicyDecision.RATE_LIMITED and decision == PolicyDecision.ALLOW:
                        decision = PolicyDecision.RATE_LIMITED

        allowed = decision == PolicyDecision.ALLOW
        reasoning = self._generate_reasoning(decision, applicable_policies, violations)

        # Log the policy check
        self._log_event(
            event_type=AuditEventType.POLICY_CHECKED,
            agent_id=agent_id,
            campaign_id=campaign_id,
            action=action,
            details={"context": context, "decision": decision.value, "violations": violations},
            policy_applied=applicable_policies[0] if applicable_policies else None,
            decision=decision,
        )

        return PolicyCheckResult(
            allowed=allowed,
            decision=decision,
            applicable_policies=applicable_policies,
            violations=violations,
            reasoning=reasoning,
        )

    def log_action(
        self,
        agent_id: str,
        campaign_id: str,
        action: str,
        details: dict,
        event_type: AuditEventType = AuditEventType.ACTION_EXECUTED,
    ) -> str:
        """Log an action to the audit trail. Returns entry_id."""
        return self._log_event(
            event_type=event_type,
            agent_id=agent_id,
            campaign_id=campaign_id,
            action=action,
            details=details,
        )

    def query_audit(
        self,
        agent_id: str = None,
        campaign_id: str = None,
        event_type: AuditEventType = None,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """
        Query the audit log with filters.

        Supports filtering by agent, campaign, event type, and date range.
        """
        results = self._audit_log.copy()

        if agent_id:
            results = [e for e in results if e.agent_id == agent_id]
        if campaign_id:
            results = [e for e in results if e.campaign_id == campaign_id]
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if start_date:
            results = [e for e in results if e.timestamp >= start_date]
        if end_date:
            results = [e for e in results if e.timestamp <= end_date]

        # Most recent first
        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results[:limit]

    def generate_monthly_report(
        self, month: int = None, year: int = None
    ) -> GovernanceReport:
        """Generate a monthly governance report."""
        now = datetime.utcnow()
        if month is None:
            month = now.month
        if year is None:
            year = now.year

        period_start = datetime(year, month, 1)
        if month == 12:
            period_end = datetime(year + 1, 1, 1)
        else:
            period_end = datetime(year, month + 1, 1)

        period_entries = [
            e for e in self._audit_log
            if period_start <= e.timestamp < period_end
        ]

        total = len(period_entries)
        allowed = sum(1 for e in period_entries if e.decision == PolicyDecision.ALLOW)
        blocked = sum(1 for e in period_entries if e.decision == PolicyDecision.DENY)
        approvals = sum(1 for e in period_entries if e.decision == PolicyDecision.REQUIRE_APPROVAL)

        # Top agents
        agent_counts: dict[str, int] = {}
        for entry in period_entries:
            agent_counts[entry.agent_id] = agent_counts.get(entry.agent_id, 0) + 1

        # Policy violations
        violation_counts: dict[str, int] = {}
        for entry in period_entries:
            if entry.policy_applied:
                violation_counts[entry.policy_applied] = violation_counts.get(entry.policy_applied, 0) + 1

        # Spending actions
        spend_entries = [
            e for e in period_entries
            if e.event_type == AuditEventType.BUDGET_MODIFIED
        ]

        return GovernanceReport(
            report_id=f"gov-{year}{month:02d}-{self.organization_id}",
            organization_id=self.organization_id,
            period_start=period_start,
            period_end=period_end,
            total_actions=total,
            actions_allowed=allowed,
            actions_blocked=blocked,
            actions_requiring_approval=approvals,
            top_agents_by_action=dict(sorted(agent_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            policy_violation_summary=violation_counts,
            spending_summary={"budget_modifications": len(spend_entries)},
        )

    def _policy_applies(
        self, policy: GovernancePolicy, agent_id: str, action: str,
        campaign_id: str, context: dict
    ) -> bool:
        """Check if a policy applies to this action."""
        conditions = policy.conditions

        # Check action match
        if "actions" in conditions:
            if action not in conditions["actions"]:
                return False

        # Check agent match
        if "agents" in conditions:
            if agent_id not in conditions["agents"] and "*" not in conditions["agents"]:
                return False

        # Check campaign match
        if "campaigns" in conditions:
            if campaign_id not in conditions["campaigns"] and "*" not in conditions["campaigns"]:
                return False

        return True

    def _check_violation(
        self, policy: GovernancePolicy, agent_id: str, action: str, context: dict
    ) -> Optional[str]:
        """Check if the action violates this specific policy."""
        params = policy.parameters

        if policy.policy_type == PolicyType.SPENDING_LIMIT:
            amount = context.get("amount", 0)
            limit = params.get("max_amount", float("inf"))
            if amount > limit:
                return f"Spending ${amount} exceeds limit ${limit}"

        elif policy.policy_type == PolicyType.RATE_LIMIT:
            key = f"{agent_id}:{action}"
            count = self._action_counts.get(key, 0)
            max_per_day = params.get("max_per_day", 100)
            if count >= max_per_day:
                return f"Rate limit exceeded: {count}/{max_per_day} actions today"

        elif policy.policy_type == PolicyType.APPROVAL_REQUIRED:
            # Always triggers approval requirement
            return f"Action '{action}' requires human approval per policy"

        return None

    def _log_event(
        self, event_type: AuditEventType, agent_id: str, campaign_id: str,
        action: str, details: dict, policy_applied: str = None,
        decision: PolicyDecision = None,
    ) -> str:
        """Create and store an audit entry."""
        entry_id = f"audit-{len(self._audit_log):08d}"
        entry = AuditEntry(
            entry_id=entry_id,
            event_type=event_type,
            agent_id=agent_id,
            campaign_id=campaign_id,
            action=action,
            details=details,
            policy_applied=policy_applied,
            decision=decision,
            organization_id=self.organization_id,
        )
        self._audit_log.append(entry)

        # Update action counts
        key = f"{agent_id}:{action}"
        self._action_counts[key] = self._action_counts.get(key, 0) + 1

        return entry_id

    def _generate_reasoning(
        self, decision: PolicyDecision, policies: list[str], violations: list[str]
    ) -> str:
        """Generate reasoning for a policy decision."""
        if decision == PolicyDecision.ALLOW:
            if policies:
                return f"Action allowed. Checked against {len(policies)} applicable policy(ies)."
            return "Action allowed. No applicable policies."
        elif decision == PolicyDecision.DENY:
            return f"Action DENIED. Violations: {'; '.join(violations)}"
        elif decision == PolicyDecision.REQUIRE_APPROVAL:
            return f"Action requires human approval. Reason: {'; '.join(violations)}"
        elif decision == PolicyDecision.RATE_LIMITED:
            return f"Action rate-limited. {'; '.join(violations)}"
        return "Unknown decision."

    def _register_default_policies(self) -> None:
        """Register standard governance policies."""
        defaults = [
            GovernancePolicy(
                policy_id="gov-spend-limit-single",
                policy_type=PolicyType.SPENDING_LIMIT,
                name="Single Action Spending Limit",
                description="No single agent action can commit more than $5,000",
                conditions={"actions": ["shift_budget", "increase_budget", "create_campaign"]},
                enforcement=PolicyDecision.REQUIRE_APPROVAL,
                parameters={"max_amount": 5000},
            ),
            GovernancePolicy(
                policy_id="gov-rate-limit-bids",
                policy_type=PolicyType.RATE_LIMIT,
                name="Bid Adjustment Rate Limit",
                description="Max 50 bid adjustments per agent per day",
                conditions={"actions": ["adjust_bid"]},
                enforcement=PolicyDecision.RATE_LIMITED,
                parameters={"max_per_day": 50},
            ),
            GovernancePolicy(
                policy_id="gov-campaign-pause-approval",
                policy_type=PolicyType.APPROVAL_REQUIRED,
                name="Campaign Pause Requires Approval",
                description="Pausing a campaign requires human approval",
                conditions={"actions": ["pause_campaign"]},
                enforcement=PolicyDecision.REQUIRE_APPROVAL,
                parameters={},
            ),
        ]
        for policy in defaults:
            self.add_policy(policy)
