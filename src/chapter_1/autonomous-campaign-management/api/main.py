"""
Campaign Management API — Human interface for the autonomous campaign system.

Endpoints for:
- Campaign lifecycle (create, approve, pause, complete)
- Audit trail (view decisions, explanations, rollback)
- Guardrail management
- Reporting (daily summaries, performance)
- Override controls
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
import uuid

app = FastAPI(
    title="Autonomous Campaign Management API",
    version="1.0.0",
    description="Human interface for managing autonomous advertising campaigns",
)


# ============================================================================
# Request/Response Models
# ============================================================================

class CampaignBriefRequest(BaseModel):
    """Request to create a new campaign from a natural language brief."""
    raw_text: str = Field(..., description="Natural language campaign brief")
    submitted_by: str = Field(..., description="Email/ID of the submitter")


class CampaignResponse(BaseModel):
    campaign_id: str
    status: str
    budget_total: float
    target_cpa: float
    current_cpa: Optional[float] = None
    budget_spent: Optional[float] = None
    budget_remaining: Optional[float] = None
    platforms: List[str] = []
    created_at: str
    updated_at: str


class ApprovalRequest(BaseModel):
    approved_by: str
    modifications: Optional[Dict] = None
    comments: Optional[str] = None


class GuardrailUpdateRequest(BaseModel):
    guardrail_type: str
    threshold_value: Optional[float] = None
    threshold_pct: Optional[float] = None
    action_on_breach: str = "block"
    enabled: bool = True


class AuditEntryResponse(BaseModel):
    entry_id: str
    timestamp: str
    agent: str
    action_type: str
    reasoning: str
    pre_state: Optional[Dict] = None
    post_state: Optional[Dict] = None
    reversible: bool = True
    reversed: bool = False


class DailyReportResponse(BaseModel):
    campaign_id: str
    report_date: str
    summary: str
    actions_taken: List[Dict]
    performance_change: Dict
    budget_status: Dict
    anomalies: List[Dict]
    recommendations: List[str]


# ============================================================================
# Campaign Lifecycle Endpoints
# ============================================================================

@app.post("/campaigns", response_model=CampaignResponse, status_code=201)
async def create_campaign(brief: CampaignBriefRequest):
    """
    Create a new campaign from a natural language brief.
    The brief is parsed by the Planning Agent and a campaign object is created in DRAFT state.
    """
    campaign_id = f"camp-{uuid.uuid4().hex[:8]}"

    # In production: invoke Planning Agent to parse brief, then store in DB
    return CampaignResponse(
        campaign_id=campaign_id,
        status="DRAFT",
        budget_total=50000.00,
        target_cpa=35.00,
        platforms=["meta", "google", "tiktok", "amazon"],
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
    )


@app.get("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: str):
    """Get current state of a campaign."""
    # In production: query campaign_states table
    return CampaignResponse(
        campaign_id=campaign_id,
        status="ACTIVE",
        budget_total=50000.00,
        target_cpa=35.00,
        current_cpa=36.42,
        budget_spent=4820.50,
        budget_remaining=45179.50,
        platforms=["meta", "google", "tiktok", "amazon"],
        created_at="2026-01-15T10:00:00",
        updated_at=datetime.utcnow().isoformat(),
    )


@app.post("/campaigns/{campaign_id}/approve")
async def approve_campaign(campaign_id: str, approval: ApprovalRequest):
    """Approve a DRAFT campaign for launch. Transitions to APPROVED → LAUNCHING."""
    # In production: validate campaign is in DRAFT, apply modifications, update status
    return {
        "campaign_id": campaign_id,
        "status": "APPROVED",
        "approved_by": approval.approved_by,
        "approved_at": datetime.utcnow().isoformat(),
        "message": "Campaign approved. Launch will begin within 15 minutes.",
    }


@app.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(campaign_id: str, reason: Optional[str] = None):
    """
    Emergency pause — immediately stops all platform campaigns.
    Can be triggered by humans or by guardrail engine.
    """
    return {
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "paused_at": datetime.utcnow().isoformat(),
        "reason": reason or "Manual pause requested",
        "message": "All platform campaigns paused. Resume requires explicit approval.",
    }


# ============================================================================
# Audit and Explainability Endpoints
# ============================================================================

@app.get("/campaigns/{campaign_id}/audit", response_model=List[AuditEntryResponse])
async def get_audit_trail(
    campaign_id: str,
    limit: int = Query(default=50, le=500),
    action_type: Optional[str] = None,
    agent: Optional[str] = None,
):
    """
    Get the audit trail for a campaign — every autonomous decision logged.
    Supports filtering by action type and agent.
    """
    # In production: query audit_log table
    return [
        AuditEntryResponse(
            entry_id="aud-001",
            timestamp=datetime.utcnow().isoformat(),
            agent="optimization_agent",
            action_type="BID_CHANGE",
            reasoning="CPA $38.50 exceeds target $35.00 by 10%. Reducing bid by 8% on TikTok to improve efficiency.",
            pre_state={"bid": 2.50, "cpa": 38.50},
            post_state={"bid": 2.30, "cpa": 38.50},
            reversible=True,
            reversed=False,
        )
    ]


@app.post("/campaigns/{campaign_id}/rollback/{entry_id}")
async def rollback_action(campaign_id: str, entry_id: str, reason: str = ""):
    """Rollback a specific autonomous action to its pre-action state."""
    return {
        "campaign_id": campaign_id,
        "entry_id": entry_id,
        "status": "rolled_back",
        "rolled_back_at": datetime.utcnow().isoformat(),
        "reason": reason,
        "message": "Action rolled back. Pre-action state restored.",
    }


# ============================================================================
# Reporting Endpoints
# ============================================================================

@app.get("/campaigns/{campaign_id}/report/daily", response_model=DailyReportResponse)
async def get_daily_report(campaign_id: str, date: Optional[str] = None):
    """
    Get the daily summary report — LLM-synthesized narrative of what happened.
    Includes actions taken, performance changes, and recommendations.
    """
    return DailyReportResponse(
        campaign_id=campaign_id,
        report_date=date or datetime.utcnow().strftime("%Y-%m-%d"),
        summary=(
            "Campaign performed well today. CPA improved from $38.50 to $36.42 across platforms. "
            "TikTok bid was reduced due to underperformance. Meta and Google continue strong. "
            "No anomalies detected. Budget pacing is on track."
        ),
        actions_taken=[
            {"action": "BID_CHANGE", "platform": "tiktok", "detail": "Reduced bid by 8%", "time": "14:30"},
            {"action": "CREATIVE_ROTATION", "platform": "meta", "detail": "Paused fatigued creative crt-002", "time": "16:00"},
        ],
        performance_change={
            "cpa_change": -2.08,
            "cpa_current": 36.42,
            "spend_today": 1920.50,
            "conversions_today": 53,
        },
        budget_status={
            "pacing": "ON_TRACK",
            "spent_total": 4820.50,
            "remaining": 45179.50,
            "days_remaining": 25,
        },
        anomalies=[],
        recommendations=[
            "Consider scaling Meta budget — strong CPA performance",
            "Monitor TikTok creative fatigue — crt-002 showing decline",
        ],
    )


# ============================================================================
# Guardrail Management Endpoints
# ============================================================================

@app.get("/campaigns/{campaign_id}/guardrails")
async def get_guardrails(campaign_id: str):
    """List all configured guardrails for a campaign."""
    return {
        "campaign_id": campaign_id,
        "guardrails": [
            {"type": "BUDGET_CAP", "threshold": 50000, "hard_limit": True, "enabled": True},
            {"type": "BID_CHANGE_LIMIT", "threshold_pct": 0.15, "hard_limit": True, "enabled": True},
            {"type": "CPA_CEILING", "threshold_pct": 2.0, "duration_hours": 4, "hard_limit": True, "enabled": True},
            {"type": "SPEND_RATE", "threshold_pct": 0.20, "hard_limit": False, "enabled": True},
            {"type": "SENTIMENT_FLOOR", "threshold": 0.75, "hard_limit": True, "enabled": True},
        ],
    }


@app.put("/campaigns/{campaign_id}/guardrails")
async def update_guardrails(campaign_id: str, guardrails: List[GuardrailUpdateRequest]):
    """Update guardrail configuration for a campaign."""
    return {
        "campaign_id": campaign_id,
        "updated": len(guardrails),
        "message": "Guardrails updated. Changes effective immediately.",
    }


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "campaign-management-api", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
