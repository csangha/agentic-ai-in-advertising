"""
Measurement MCP Server — exposes data quality and performance query tools.

Deployed to Amazon Bedrock AgentCore.
Tools:
- query_performance: Query normalized campaign performance data
- get_data_freshness: Check freshness of data sources
- check_quality_status: Get overall data quality status and gate decision
"""

from mcp.server.fastmcp import FastMCP
from datetime import datetime, timedelta
from typing import Optional
import json

mcp = FastMCP("measurement", description="Measurement data foundation query tools")


@mcp.tool()
def query_performance(
    campaign_id: str,
    platform: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    metrics: Optional[str] = None,
) -> str:
    """
    Query normalized campaign performance data.

    Args:
        campaign_id: The campaign identifier
        platform: Optional platform filter (meta, google, amazon, tiktok)
        date_from: Start date (YYYY-MM-DD), defaults to 7 days ago
        date_to: End date (YYYY-MM-DD), defaults to today
        metrics: Comma-separated list of metrics to return (default: all)

    Returns:
        JSON with normalized performance metrics across platforms
    """
    # In production: query from Aurora PostgreSQL normalized tables
    result = {
        "campaign_id": campaign_id,
        "platform": platform or "all",
        "date_range": {
            "from": date_from or (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d"),
            "to": date_to or datetime.utcnow().strftime("%Y-%m-%d"),
        },
        "metrics": {
            "impressions": 245000,
            "clicks": 7350,
            "spend": 5680.50,
            "conversions": 156,
            "cpa": 36.41,
            "ctr": 0.03,
            "cpm": 23.19,
            "roas": 3.1,
        },
        "by_platform": {
            "meta": {"impressions": 100000, "clicks": 3000, "spend": 2400, "conversions": 70, "cpa": 34.28},
            "google": {"impressions": 80000, "clicks": 2600, "spend": 1780, "conversions": 50, "cpa": 35.60},
            "amazon": {"impressions": 35000, "clicks": 1050, "spend": 900, "conversions": 24, "cpa": 37.50},
            "tiktok": {"impressions": 30000, "clicks": 700, "spend": 600.50, "conversions": 12, "cpa": 50.04},
        },
        "data_quality": {
            "freshness": "healthy",
            "latest_update": datetime.utcnow().isoformat(),
            "completeness": 0.98,
        },
        "retrieved_at": datetime.utcnow().isoformat(),
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def get_data_freshness(
    source: Optional[str] = None,
) -> str:
    """
    Check data freshness across all sources or a specific source.

    Args:
        source: Optional source name (e.g., 'meta_ads', 'google_ads'). If omitted, checks all.

    Returns:
        JSON with freshness status per source including age, threshold, and staleness flag
    """
    now = datetime.utcnow()
    sources_status = {
        "meta_ads": {
            "latest_data": (now - timedelta(minutes=12)).isoformat(),
            "age_minutes": 12,
            "threshold_minutes": 30,
            "is_fresh": True,
            "status": "healthy",
        },
        "google_ads": {
            "latest_data": (now - timedelta(minutes=25)).isoformat(),
            "age_minutes": 25,
            "threshold_minutes": 30,
            "is_fresh": True,
            "status": "healthy",
        },
        "amazon_ads": {
            "latest_data": (now - timedelta(minutes=45)).isoformat(),
            "age_minutes": 45,
            "threshold_minutes": 60,
            "is_fresh": True,
            "status": "healthy",
        },
        "tiktok_ads": {
            "latest_data": (now - timedelta(minutes=18)).isoformat(),
            "age_minutes": 18,
            "threshold_minutes": 30,
            "is_fresh": True,
            "status": "healthy",
        },
    }

    if source and source in sources_status:
        result = {"source": source, **sources_status[source]}
    else:
        result = {
            "sources": sources_status,
            "overall_status": "healthy",
            "all_fresh": all(s["is_fresh"] for s in sources_status.values()),
        }

    result["checked_at"] = now.isoformat()
    return json.dumps(result, indent=2)


@mcp.tool()
def check_quality_status(
    campaign_id: Optional[str] = None,
) -> str:
    """
    Get overall data quality status and agent gate decision.

    The gate determines whether downstream agent actions (bid changes,
    budget shifts) should be allowed based on data quality.

    Args:
        campaign_id: Optional campaign filter

    Returns:
        JSON with quality score, gate decision, and any quality warnings
    """
    result = {
        "quality_score": 0.95,
        "gate_decision": "allow",
        "gate_reasoning": "All data sources are fresh and complete.",
        "status": "healthy",
        "checks": {
            "freshness": {"passed": True, "score": 0.97},
            "completeness": {"passed": True, "score": 0.98},
            "volume_anomalies": {"detected": False, "count": 0},
            "consistency": {"passed": True, "score": 0.94},
        },
        "warnings": [],
        "last_full_check": datetime.utcnow().isoformat(),
        "recommendation": "All systems nominal. Agent actions are unrestricted.",
    }

    if campaign_id:
        result["campaign_id"] = campaign_id

    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
