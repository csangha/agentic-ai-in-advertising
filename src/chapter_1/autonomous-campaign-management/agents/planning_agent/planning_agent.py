"""
Planning Agent — Campaign Brief Interpretation & Platform Configuration

Interprets marketing briefs and generates platform-specific campaign configurations.
Deployed as an A2A service on Amazon Bedrock AgentCore.

Responsibilities:
- Parse natural language briefs into structured campaign parameters
- Validate brief feasibility and detect contradictions
- Generate platform-specific configurations (Meta, Google, TikTok, Amazon)
- Estimate initial budget allocation across platforms
"""

import json
import os
import sys
import traceback
from datetime import datetime
from typing import Optional

import boto3
import uvicorn
from botocore.config import Config
from dotenv import load_dotenv
from fastapi import FastAPI, Request as FastAPIRequest
from langchain.agents import create_agent
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

load_dotenv()


# ============================================================================
# Logging
# ============================================================================

def log_info(message: str):
    print(f"[INFO] {datetime.now().isoformat()} - {message}", flush=True)


def log_error(message: str):
    print(f"[ERROR] {datetime.now().isoformat()} - {message}", file=sys.stderr, flush=True)


# ============================================================================
# Configuration
# ============================================================================

def load_config() -> dict:
    """Load configuration from Secrets Manager with env var fallback."""
    secret_name = os.getenv("SECRET_NAME", "campaign-mgmt/planning-agent")
    region_name = os.getenv("AWS_REGION", "us-east-1")

    if secret_name:
        try:
            log_info(f"Loading config from Secrets Manager: {secret_name}")
            sm = boto3.client("secretsmanager", region_name=region_name)
            response = sm.get_secret_value(SecretId=secret_name)
            config = json.loads(response["SecretString"])
            log_info("Configuration loaded from Secrets Manager")
            return config
        except Exception as e:
            log_error(f"Secrets Manager unavailable: {e}")
            log_info("Falling back to environment variables")

    return {
        "AWS_REGION": os.getenv("AWS_REGION", "us-east-1"),
        "MODEL_ID": os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514"),
        "DATABASE_URL": os.getenv("DATABASE_URL"),
    }


CONFIG = load_config()
AWS_REGION = CONFIG.get("AWS_REGION", "us-east-1")
MODEL_ID = CONFIG.get("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514")


# ============================================================================
# Tool Input Schemas
# ============================================================================

class ParseBriefInput(BaseModel):
    raw_text: str = Field(description="The raw campaign brief text from the marketing manager")


class ValidateBriefInput(BaseModel):
    brief_json: str = Field(description="JSON string of parsed brief parameters to validate")


class GeneratePlatformConfigsInput(BaseModel):
    brief_json: str = Field(description="JSON string of validated campaign brief")
    platforms: str = Field(description="Comma-separated list of platforms (meta, google, tiktok, amazon)")


class EstimateBudgetAllocationInput(BaseModel):
    total_budget: float = Field(description="Total campaign budget in USD")
    platforms: str = Field(description="Comma-separated list of target platforms")
    objective: str = Field(default="conversions", description="Primary campaign objective")
    audience_description: Optional[str] = Field(default=None, description="Target audience description")


# ============================================================================
# Tool Implementations
# ============================================================================

def parse_brief(raw_text: str) -> str:
    """
    Parse a natural language campaign brief into structured parameters.

    Extracts: budget, target CPA, audience, platforms, constraints, dates.
    """
    log_info(f"Parsing brief ({len(raw_text)} chars)")

    # Use Bedrock to extract structured data
    client = boto3.client("bedrock-runtime", region_name=AWS_REGION)

    extraction_prompt = f"""Extract structured parameters from this campaign brief.
Return a JSON object with: budget_total, daily_budget, target_cpa, target_roas,
audience_description, audience_segments (array), platforms (array: meta/google/tiktok/amazon),
objectives (array), constraints (object), sentiment_threshold (0-1), start_date, end_date,
flight_days, geo_targets (array), validation_errors (array of any issues).

BRIEF:
{raw_text}

Return ONLY valid JSON."""

    response = client.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2048,
            "temperature": 0.0,
            "messages": [{"role": "user", "content": extraction_prompt}],
        }),
    )

    body = json.loads(response["body"].read())
    text = body["content"][0]["text"]

    # Clean up potential markdown wrapping
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]

    log_info(f"Brief parsed successfully")
    return text.strip()


def validate_brief(brief_json: str) -> str:
    """
    Validate a parsed campaign brief for completeness and consistency.

    Checks: required fields, budget feasibility, platform compatibility, date logic.
    """
    log_info("Validating campaign brief")

    try:
        brief = json.loads(brief_json)
    except json.JSONDecodeError:
        return json.dumps({"valid": False, "errors": ["Invalid JSON input"]})

    errors = []

    # Required fields
    if not brief.get("budget_total") or brief["budget_total"] <= 0:
        errors.append("budget_total is required and must be positive")
    if not brief.get("target_cpa") or brief["target_cpa"] <= 0:
        errors.append("target_cpa is required and must be positive")
    if not brief.get("platforms"):
        errors.append("At least one platform must be specified")

    # Platform validation
    valid_platforms = {"meta", "google", "tiktok", "amazon"}
    if brief.get("platforms"):
        invalid = [p for p in brief["platforms"] if p not in valid_platforms]
        if invalid:
            errors.append(f"Invalid platforms: {invalid}")

    # Budget feasibility
    if brief.get("budget_total") and brief.get("target_cpa"):
        expected_convs = brief["budget_total"] / brief["target_cpa"]
        if expected_convs < 10:
            errors.append(
                f"Budget/CPA ratio yields ~{expected_convs:.0f} conversions — too few for optimization"
            )

    # Date logic
    if brief.get("start_date") and brief.get("end_date"):
        try:
            start = datetime.fromisoformat(brief["start_date"])
            end = datetime.fromisoformat(brief["end_date"])
            if end <= start:
                errors.append("end_date must be after start_date")
        except (ValueError, TypeError):
            errors.append("Invalid date format")

    result = {
        "valid": len(errors) == 0,
        "errors": errors,
        "brief": brief,
    }

    log_info(f"Validation result: valid={result['valid']}, errors={len(errors)}")
    return json.dumps(result)


def generate_platform_configs(brief_json: str, platforms: str) -> str:
    """
    Generate platform-specific campaign configurations from a validated brief.

    Creates targeting, bidding, and creative configs for each platform.
    """
    log_info(f"Generating platform configs for: {platforms}")

    brief = json.loads(brief_json)
    platform_list = [p.strip() for p in platforms.split(",")]

    # Use Bedrock to generate platform-specific configs
    client = boto3.client("bedrock-runtime", region_name=AWS_REGION)

    config_prompt = f"""Generate platform-specific campaign configurations for these platforms: {platform_list}

Campaign brief parameters:
{json.dumps(brief, indent=2)}

For each platform, generate a JSON config with:
- campaign_name: Descriptive campaign name
- objective: Platform-specific objective mapping
- bid_strategy: Recommended bid strategy
- targeting: Platform-specific audience targeting
- placements: Recommended ad placements
- budget_allocation_pct: Suggested % of total budget
- ad_format: Recommended ad formats
- optimization_goal: What to optimize for

Return a JSON object mapping platform name to its config.
Return ONLY valid JSON."""

    response = client.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "temperature": 0.1,
            "messages": [{"role": "user", "content": config_prompt}],
        }),
    )

    body = json.loads(response["body"].read())
    text = body["content"][0]["text"]

    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]

    log_info("Platform configs generated")
    return text.strip()


def estimate_budget_allocation(
    total_budget: float,
    platforms: str,
    objective: str = "conversions",
    audience_description: Optional[str] = None,
) -> str:
    """
    Estimate initial budget allocation across platforms.

    Uses heuristics based on platform strengths and campaign objectives.
    """
    log_info(f"Estimating budget allocation: ${total_budget} across {platforms}")

    platform_list = [p.strip() for p in platforms.split(",")]

    # Default allocation heuristics based on objective
    allocation_templates = {
        "conversions": {"meta": 0.35, "google": 0.35, "tiktok": 0.15, "amazon": 0.15},
        "awareness": {"meta": 0.30, "google": 0.20, "tiktok": 0.35, "amazon": 0.15},
        "traffic": {"meta": 0.25, "google": 0.40, "tiktok": 0.20, "amazon": 0.15},
        "engagement": {"meta": 0.35, "google": 0.15, "tiktok": 0.40, "amazon": 0.10},
    }

    template = allocation_templates.get(objective, allocation_templates["conversions"])

    # Filter to requested platforms and renormalize
    allocation = {p: template.get(p, 0.25) for p in platform_list}
    total_weight = sum(allocation.values())
    allocation = {p: round(w / total_weight, 4) for p, w in allocation.items()}

    # Convert to dollar amounts
    dollar_allocation = {p: round(total_budget * pct, 2) for p, pct in allocation.items()}

    result = {
        "total_budget": total_budget,
        "objective": objective,
        "allocation_pct": allocation,
        "allocation_usd": dollar_allocation,
        "platforms": platform_list,
        "note": "Initial allocation — will be optimized based on performance data",
    }

    log_info(f"Allocation: {dollar_allocation}")
    return json.dumps(result)


# ============================================================================
# LangChain Tools
# ============================================================================

tools = [
    StructuredTool(
        name="parse_brief",
        description="Parse a natural language campaign brief into structured parameters",
        func=parse_brief,
        args_schema=ParseBriefInput,
    ),
    StructuredTool(
        name="validate_brief",
        description="Validate a parsed campaign brief for completeness and consistency",
        func=validate_brief,
        args_schema=ValidateBriefInput,
    ),
    StructuredTool(
        name="generate_platform_configs",
        description="Generate platform-specific campaign configurations from a validated brief",
        func=generate_platform_configs,
        args_schema=GeneratePlatformConfigsInput,
    ),
    StructuredTool(
        name="estimate_budget_allocation",
        description="Estimate initial budget allocation across advertising platforms",
        func=estimate_budget_allocation,
        args_schema=EstimateBudgetAllocationInput,
    ),
]


# ============================================================================
# Agent Initialization
# ============================================================================

_graph = None


async def _initialize_agent():
    """Initialize the Planning Agent."""
    global _graph

    if _graph is not None:
        return _graph

    log_info("Initializing Planning Agent...")

    bedrock_config = Config(
        retries={"max_attempts": 3, "mode": "adaptive"},
        connect_timeout=5,
        read_timeout=60,
    )
    bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION, config=bedrock_config)

    llm = ChatBedrock(
        client=bedrock_client,
        model_id=MODEL_ID,
        model_kwargs={"temperature": 0.1, "max_tokens": 4096},
    )

    system_prompt = """You are the Planning Agent — responsible for interpreting campaign briefs and generating platform configurations.

## Your Role
1. Parse natural language campaign briefs into structured parameters
2. Validate briefs for completeness, feasibility, and consistency
3. Generate platform-specific campaign configurations
4. Estimate initial budget allocation across platforms

## Rules
- Always validate briefs before generating configs
- Flag any contradictions or unrealistic targets
- Ensure budget allocation sums to 100%
- Consider platform strengths when recommending allocations
- Default sentiment_threshold to 0.75 if not specified
"""

    _graph = create_agent(llm, tools, system_prompt=system_prompt)
    log_info("Planning Agent ready")
    return _graph


# ============================================================================
# A2A Server (FastAPI)
# ============================================================================

app = FastAPI(title="Planning Agent", version="1.0.0")


@app.post("/")
async def a2a_endpoint(request: FastAPIRequest):
    """A2A JSON-RPC endpoint for the Planning Agent."""
    try:
        body = await request.json()

        # Extract message text
        if "prompt" in body:
            text = body["prompt"]
        else:
            message = body.get("params", {}).get("message", {})
            parts = message.get("parts", [])
            text = next((p["text"] for p in parts if "text" in p), message.get("text", ""))

        log_info(f"Request: {text[:100]}...")

        graph = await _initialize_agent()
        result = await graph.ainvoke({"messages": [HumanMessage(content=text)]})
        response_text = result["messages"][-1].content if result.get("messages") else "No response"

        log_info(f"Response: {response_text[:200]}...")

        if "method" not in body:
            return {"response": response_text}
        return {
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "result": {
                "status": {
                    "message": {"role": "assistant", "parts": [{"kind": "text", "text": response_text}]}
                }
            },
        }

    except Exception as e:
        log_error(f"Error: {e}")
        log_error(traceback.format_exc())
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "agent": "planning-agent", "version": "1.0.0"}


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    port = int(os.getenv("AGENT_PORT", "9001"))
    log_info(f"Starting Planning Agent on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
