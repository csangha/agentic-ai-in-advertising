"""
Guardrails MCP Server — exposes guardrail checking tools to agents.

Deployed to Amazon Bedrock AgentCore. Agents MUST call check_guardrails
before executing any bid/budget/audience change.

Tools:
- check_guardrails: Evaluate a proposed action against all active guardrails
- get_guardrails: List all configured guardrails for a campaign
- evaluate_budget_cap: Hard budget limit check
- evaluate_cpa_circuit_breaker: CPA > 200% for > 4h check
"""

from mcp.server.fastmcp import FastMCP
from datetime import datetime
import json

mcp = FastMCP("campaign-guardrails", description="Campaign safety guardrail evaluation tools")


@mcp.tool()
def check_guardrails(
    campaign_id: str,
    action_type: str,
    proposed_change: str,
    current_metrics: str,
) -> str:
    """
    Evaluate a proposed action against ALL active guardrails for a campaign.
    This is the primary guardrail gate — every action must pass through here.

    Args:
        campaign_id: Campaign to check guardrails for
        action_type: Type of action (BID_CHANGE, BUDGET_REALLOC, AUDIENCE_EXPAND, etc.)
        proposed_change: JSON string with proposed change details (e.g., {"bid_change_pct": 0.12})
        current_metrics: JSON string with current campaign metrics

    Returns:
        JSON with pass/fail result, violation details if any, and whether escalation is required.
    """
    try:
        change = json.loads(proposed_change) if isinstance(proposed_change, str) else proposed_change
        metrics = json.loads(current_metrics) if isinstance(current_metrics, str) else current_metrics
    except json.JSONDecodeError:
        return json.dumps({
            "passed": False,
            "error": "Invalid JSON in proposed_change or current_metrics",
        })

    violations = []

    # Check 1: Budget cap (HARD LIMIT)
    total_spend = metrics.get("total_spend", 0)
    total_budget = metrics.get("total_budget", 50000)
    if total_spend >= total_budget:
        violations.append({
            "guardrail": "BUDGET_CAP",
            "message": f"Budget exhausted: ${total_spend:.2f} >= ${total_budget:.2f}",
            "action": "block",
            "severity": "CRITICAL",
        })

    # Check 2: Bid change limit (±15%)
    bid_change = abs(change.get("bid_change_pct", 0))
    if bid_change > 0.15:
        violations.append({
            "guardrail": "BID_CHANGE_LIMIT",
            "message": f"Bid change {bid_change:.1%} exceeds ±15% limit",
            "action": "block",
            "severity": "MEDIUM",
        })

    # Check 3: Spend rate (20% daily max reallocation)
    budget_shift = abs(change.get("budget_shift", 0))
    daily_budget = metrics.get("daily_budget", 2000)
    if daily_budget > 0 and budget_shift / daily_budget > 0.20:
        violations.append({
            "guardrail": "SPEND_RATE",
            "message": f"Budget shift ${budget_shift:.2f} exceeds 20% of daily budget ${daily_budget:.2f}",
            "action": "escalate",
            "severity": "HIGH",
        })

    # Check 4: CPA circuit breaker
    current_cpa = metrics.get("current_cpa", 0)
    target_cpa = metrics.get("target_cpa", 35)
    hours_above = metrics.get("hours_above_cpa_threshold", 0)
    if target_cpa > 0 and current_cpa > target_cpa * 2.0 and hours_above >= 4:
        violations.append({
            "guardrail": "CPA_CEILING",
            "message": f"CPA ${current_cpa:.2f} > 200% of target for {hours_above}h. PAUSE required.",
            "action": "block",
            "severity": "CRITICAL",
        })

    # Check 5: Escalation threshold (>30% of total budget)
    budget_impact = abs(change.get("budget_impact", 0))
    if total_budget > 0 and budget_impact / total_budget > 0.30:
        violations.append({
            "guardrail": "ESCALATION_THRESHOLD",
            "message": f"Action affects {budget_impact/total_budget:.1%} of total budget. Human approval required.",
            "action": "escalate",
            "severity": "HIGH",
        })

    passed = len(violations) == 0
    action_blocked = any(v["action"] == "block" for v in violations)
    escalation_required = any(v["action"] == "escalate" for v in violations)

    result = {
        "passed": passed,
        "action_blocked": action_blocked,
        "escalation_required": escalation_required,
        "violations": violations,
        "checked_at": datetime.utcnow().isoformat(),
        "campaign_id": campaign_id,
        "action_type": action_type,
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def get_guardrails(campaign_id: str) -> str:
    """
    List all configured guardrails for a campaign.

    Args:
        campaign_id: Campaign to retrieve guardrails for

    Returns:
        JSON list of all guardrail configurations.
    """
    # In production: query guardrails table for this campaign
    guardrails = [
        {"type": "BUDGET_CAP", "threshold": 50000, "action": "block", "hard_limit": True},
        {"type": "BID_CHANGE_LIMIT", "threshold_pct": 0.15, "action": "block", "hard_limit": True},
        {"type": "SPEND_RATE", "threshold_pct": 0.20, "action": "escalate", "hard_limit": False},
        {"type": "CPA_CEILING", "threshold_pct": 2.0, "duration_hours": 4, "action": "block", "hard_limit": True},
        {"type": "SENTIMENT_FLOOR", "threshold": 0.75, "action": "block", "hard_limit": True},
        {"type": "AUDIENCE_CONCENTRATION", "threshold_pct": 0.70, "action": "block", "hard_limit": True},
        {"type": "ESCALATION_THRESHOLD", "threshold_pct": 0.30, "action": "escalate", "hard_limit": False},
    ]
    result = {
        "campaign_id": campaign_id,
        "guardrails": guardrails,
        "total": len(guardrails),
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def evaluate_budget_cap(campaign_id: str, proposed_spend: float) -> str:
    """
    Check if a proposed spend amount would breach the hard budget cap.
    This is the absolute inviolable limit.

    Args:
        campaign_id: Campaign identifier
        proposed_spend: Total projected spend including proposed action

    Returns:
        JSON with pass/fail and remaining budget.
    """
    # In production: query campaign_states table
    budget_cap = 50000.00  # From campaign config

    result = {
        "campaign_id": campaign_id,
        "budget_cap": budget_cap,
        "proposed_spend": proposed_spend,
        "passed": proposed_spend <= budget_cap,
        "remaining": max(0, budget_cap - proposed_spend),
        "message": (
            "Within budget cap" if proposed_spend <= budget_cap
            else f"VIOLATION: ${proposed_spend:.2f} exceeds cap ${budget_cap:.2f}"
        ),
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def evaluate_cpa_circuit_breaker(campaign_id: str) -> str:
    """
    Check if the CPA circuit breaker should trigger.
    Triggers when CPA exceeds 200% of target for more than 4 consecutive hours.

    Args:
        campaign_id: Campaign identifier

    Returns:
        JSON with circuit breaker status and recommendation.
    """
    # In production: query time-series CPA data
    result = {
        "campaign_id": campaign_id,
        "circuit_breaker_triggered": False,
        "current_cpa": 36.42,
        "target_cpa": 35.00,
        "cpa_ratio": 1.04,
        "hours_above_threshold": 0,
        "threshold_ratio": 2.0,
        "threshold_hours": 4,
        "message": "CPA is within acceptable range (104% of target).",
        "checked_at": datetime.utcnow().isoformat(),
    }
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
