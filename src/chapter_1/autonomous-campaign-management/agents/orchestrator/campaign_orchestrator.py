"""
Campaign Orchestrator Agent — LangGraph Agent on Amazon Bedrock AgentCore

The main orchestrator that coordinates the agentic loop:
Observe → Reason → Act → Evaluate → Repeat

Connects to MCP servers deployed on AgentCore to:
- Create and manage campaigns across platforms (Amazon Ads MCP Server)
- Query performance metrics (custom metrics MCP server)
- Check guardrails (guardrail MCP server)
- Generate creative variants (creative MCP server)

Deployed as an A2A service on Bedrock AgentCore.
"""

from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_aws import ChatBedrock
from typing import Optional
from pydantic import Field, create_model
from dotenv import load_dotenv
from botocore.config import Config
import json
import os
import sys
import traceback
import boto3
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Request as FastAPIRequest

load_dotenv()


# ============================================================================
# CloudWatch-Compatible Logging
# ============================================================================

def log_info(message: str):
    """Log info message to stdout (CloudWatch Logs)."""
    print(f"[INFO] {datetime.now().isoformat()} - {message}", flush=True)


def log_error(message: str):
    """Log error message to stderr (CloudWatch Logs)."""
    print(f"[ERROR] {datetime.now().isoformat()} - {message}", file=sys.stderr, flush=True)


# ============================================================================
# Configuration Loader (Secrets Manager with env var fallback)
# ============================================================================

def load_config() -> dict:
    """
    Load configuration from AWS Secrets Manager.
    Falls back to environment variables for local development.

    Expected secret structure:
    {
        "AWS_REGION": "us-east-1",
        "MODEL_ID": "us.anthropic.claude-sonnet-4-20250514",
        "MCP_METRICS_ARN": "arn:aws:bedrock-agentcore:...:runtime/metrics-server",
        "MCP_GUARDRAILS_ARN": "arn:aws:bedrock-agentcore:...:runtime/guardrails-server",
        "CLIENT_ID": "<amazon_ads_client_id>",
        "CLIENT_SECRET": "<amazon_ads_client_secret>",
        "REFRESH_TOKEN": "<amazon_ads_refresh_token>",
        "DB_SECRET_ARN": "arn:aws:secretsmanager:...",
        "OPENSEARCH_ENDPOINT": "https://...",
        "REDIS_ENDPOINT": "..."
    }
    """
    secret_name = os.getenv("SECRET_NAME", "campaign-mgmt/agent-config")
    region_name = os.getenv("AWS_REGION", "us-east-1")

    if secret_name:
        try:
            log_info(f"Loading config from Secrets Manager: {secret_name}")
            session = boto3.session.Session()
            sm_client = session.client("secretsmanager", region_name=region_name)
            response = sm_client.get_secret_value(SecretId=secret_name)
            config = json.loads(response["SecretString"])
            log_info("Configuration loaded from Secrets Manager")
            return config
        except Exception as e:
            log_error(f"Secrets Manager unavailable: {e}")
            log_info("Falling back to environment variables")

    return {
        "AWS_REGION": os.getenv("AWS_REGION", "us-east-1"),
        "MODEL_ID": os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514"),
        "MCP_METRICS_ARN": os.getenv("MCP_METRICS_ARN"),
        "MCP_GUARDRAILS_ARN": os.getenv("MCP_GUARDRAILS_ARN"),
        "CLIENT_ID": os.getenv("CLIENT_ID"),
        "CLIENT_SECRET": os.getenv("CLIENT_SECRET"),
        "REFRESH_TOKEN": os.getenv("REFRESH_TOKEN"),
    }


CONFIG = load_config()
AWS_REGION = CONFIG.get("AWS_REGION", "us-east-1")
MODEL_ID = CONFIG.get("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514")

# MCP Server ARNs (deployed on AgentCore)
MCP_SERVERS = {
    "metrics": CONFIG.get("MCP_METRICS_ARN"),
    "guardrails": CONFIG.get("MCP_GUARDRAILS_ARN"),
}

log_info(f"AWS Region: {AWS_REGION}")
log_info(f"Model ID: {MODEL_ID}")
log_info(f"MCP Servers: {list(k for k, v in MCP_SERVERS.items() if v)}")


# ============================================================================
# MCP Server Communication via AgentCore
# ============================================================================

_agentcore_client = None


def get_agentcore_client():
    """Get or create the Bedrock AgentCore boto3 client (singleton)."""
    global _agentcore_client
    if _agentcore_client is None:
        config = Config(
            retries={"max_attempts": 3, "mode": "adaptive"},
            connect_timeout=5,
            read_timeout=30,
        )
        _agentcore_client = boto3.client(
            "bedrock-agentcore",
            region_name=AWS_REGION,
            config=config,
        )
        log_info("Bedrock AgentCore client initialized")
    return _agentcore_client


def call_mcp_server(server_name: str, method: str, params: dict = None) -> dict:
    """
    Call an MCP server method via Bedrock AgentCore invoke_agent_runtime.

    Args:
        server_name: Key in MCP_SERVERS (e.g., 'metrics', 'guardrails')
        method: MCP method (e.g., 'tools/list', 'tools/call')
        params: Optional parameters for the method

    Returns:
        The result from the MCP JSON-RPC response.
    """
    runtime_arn = MCP_SERVERS.get(server_name)
    if not runtime_arn:
        raise ValueError(f"Unknown or unconfigured MCP server: {server_name}")

    mcp_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {},
    }

    payload = json.dumps(mcp_request).encode("utf-8")

    try:
        client = get_agentcore_client()
        response = client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            payload=payload,
            qualifier="DEFAULT",
            contentType="application/json",
            accept="application/json, text/event-stream",
        )

        raw = response["response"].read().decode()

        # Handle SSE or plain JSON response formats
        if raw.startswith("data: "):
            for line in raw.strip().splitlines():
                if line.startswith("data: "):
                    json_data = json.loads(line[6:])
                    return json_data.get("result", json_data)
        else:
            json_data = json.loads(raw[raw.find("{"):])
            return json_data.get("result", json_data)

    except Exception as e:
        log_error(f"MCP call to {server_name}.{method} failed: {e}")
        raise


# ============================================================================
# MCP Tool → LangChain StructuredTool Conversion
# ============================================================================

def create_langchain_tool(mcp_tool: dict, server_name: str) -> StructuredTool:
    """
    Convert an MCP tool definition into a LangChain StructuredTool.

    Args:
        mcp_tool: Tool definition from MCP tools/list response.
        server_name: Name prefix to avoid collisions across servers.

    Returns:
        A LangChain StructuredTool that invokes the MCP tool via AgentCore.
    """
    tool_name = f"{server_name}_{mcp_tool['name']}"
    tool_description = mcp_tool.get("description", f"MCP tool: {mcp_tool['name']}")
    input_schema = mcp_tool.get("inputSchema", {})

    def tool_func(**kwargs):
        try:
            filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
            log_info(f"Calling {server_name}.{mcp_tool['name']} with args: {filtered_kwargs}")

            result = call_mcp_server(
                server_name,
                "tools/call",
                {"name": mcp_tool["name"], "arguments": filtered_kwargs},
            )

            log_info(f"Result for {tool_name}: {str(result)[:200]}...")

            # Extract text content from the MCP response
            content = result.get("content", [])
            if not content or not isinstance(content, list):
                return str(result)

            text_parts = (
                c.get("text", "") for c in content if c.get("type") == "text"
            )
            response = "\n".join(text_parts) or str(result)
            return response

        except Exception as e:
            log_error(f"Error executing {tool_name}: {e}")
            log_error(traceback.format_exc())
            return f"Error executing {tool_name}: {str(e)}"

    # Build Pydantic model from MCP input schema
    properties = input_schema.get("properties", {})
    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    fields = {
        name: (
            Optional[type_map.get(info.get("type", "string"), str)],
            Field(default=None, description=info.get("description", "")),
        )
        for name, info in properties.items()
    }

    ArgsSchema = (
        create_model(f"{tool_name}_args", **fields)
        if fields
        else create_model(f"{tool_name}_args")
    )

    return StructuredTool(
        name=tool_name,
        description=tool_description,
        func=tool_func,
        args_schema=ArgsSchema,
    )


# ============================================================================
# Agent Initialization (Lazy — runs once on first request)
# ============================================================================

from langchain.agents import create_agent

_graph = None
_tools = None


async def _initialize_agent():
    """Initialize the Campaign Orchestrator agent on first request."""
    global _graph, _tools

    if _graph is not None:
        return _graph

    log_info("=" * 60)
    log_info("INITIALIZING CAMPAIGN ORCHESTRATOR AGENT")
    log_info("=" * 60)

    all_tools = []

    # ------------------------------------------------------------------
    # 1. Discover tools from MCP servers deployed on AgentCore
    # ------------------------------------------------------------------
    for server_name, server_arn in MCP_SERVERS.items():
        if not server_arn:
            log_info(f"Skipping {server_name}: ARN not configured")
            continue

        try:
            log_info(f"Discovering tools on MCP server: {server_name}")

            # MCP protocol handshake
            call_mcp_server(server_name, "initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "campaign-orchestrator", "version": "1.0.0"},
            })

            # Discover available tools
            tools_result = call_mcp_server(server_name, "tools/list", {})
            server_tools = tools_result.get("tools", [])

            # Convert each MCP tool to a LangChain StructuredTool
            for tool in server_tools:
                langchain_tool = create_langchain_tool(tool, server_name)
                all_tools.append(langchain_tool)

            log_info(f"{server_name}: {len(server_tools)} tools loaded")

        except Exception as e:
            log_error(f"Failed to initialize {server_name}: {e}")
            log_error(traceback.format_exc())

    # ------------------------------------------------------------------
    # 2. Connect to Amazon Ads MCP Server (Streamable HTTP)
    # ------------------------------------------------------------------
    client_id = CONFIG.get("CLIENT_ID")
    client_secret = CONFIG.get("CLIENT_SECRET")
    refresh_token = CONFIG.get("REFRESH_TOKEN")

    if client_id and client_secret and refresh_token:
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
            import requests

            log_info("Obtaining OAuth token for Amazon Ads MCP Server...")
            auth_response = requests.post(
                "https://api.amazon.com/auth/o2/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )

            if auth_response.status_code == 200:
                access_token = auth_response.json()["access_token"]
                log_info("Access token obtained, connecting to Ads MCP Server...")

                mcp_client = MultiServerMCPClient({
                    "amzn-ads": {
                        "url": "https://advertising-ai.amazon.com/mcp",
                        "transport": "streamable_http",
                        "headers": {
                            "Authorization": access_token,
                            "Amazon-Ads-ClientId": client_id,
                            "Accept": "application/json, text/event-stream",
                        },
                    }
                })

                ads_tools = await mcp_client.get_tools()
                log_info(f"Amazon Ads MCP Server: {len(ads_tools)} tools discovered")

                # Filter to campaign management tools
                tool_filter = os.getenv("TOOL_FILTER", "campaign_management,reporting,account_management")
                allowed_groups = [g.strip() for g in tool_filter.split(",") if g.strip()]
                if allowed_groups:
                    ads_tools = [t for t in ads_tools if any(t.name.startswith(g) for g in allowed_groups)]
                    log_info(f"Ads tools after filtering: {len(ads_tools)}")

                all_tools.extend(ads_tools)
            else:
                log_error(f"OAuth failed: {auth_response.status_code}")

        except Exception as e:
            log_error(f"Failed to connect to Ads MCP Server: {e}")
            log_error(traceback.format_exc())
    else:
        log_info("Amazon Ads credentials not configured, skipping")

    _tools = all_tools
    log_info(f"Total tools loaded: {len(_tools)}")

    # ------------------------------------------------------------------
    # 3. Initialize ChatBedrock with Claude
    # ------------------------------------------------------------------
    log_info(f"Initializing ChatBedrock with model: {MODEL_ID}")

    bedrock_config = Config(
        retries={"max_attempts": 3, "mode": "adaptive"},
        connect_timeout=5,
        read_timeout=60,
    )
    bedrock_client = boto3.client(
        "bedrock-runtime",
        region_name=AWS_REGION,
        config=bedrock_config,
    )

    llm = ChatBedrock(
        client=bedrock_client,
        model_id=MODEL_ID,
        model_kwargs={
            "temperature": 0.1,
            "max_tokens": 4096,
        },
    )

    # ------------------------------------------------------------------
    # 4. Create the ReAct agent graph
    # ------------------------------------------------------------------
    system_prompt = """You are the Campaign Orchestrator — an autonomous advertising campaign management agent.

## Your Role
You manage the full campaign lifecycle: interpreting briefs, launching campaigns across platforms,
monitoring performance, optimizing bids/budgets, detecting anomalies, and reporting results.

## Available Capabilities
- Query campaign performance metrics across Meta, Google, Amazon, and TikTok
- Check and enforce guardrails (budget caps, CPA ceilings, spend rate limits)
- Adjust bids and budgets within configured boundaries
- Create and manage campaigns on Amazon Ads
- Detect performance anomalies and take corrective action
- Generate daily reports explaining autonomous decisions

## Operating Rules
1. ALWAYS check guardrails before executing any bid/budget change.
2. NEVER exceed the configured maximum bid change (±15% per cycle).
3. NEVER exceed total budget cap under any circumstance.
4. If CPA exceeds 200% of target for >4 hours, PAUSE affected campaigns and ESCALATE.
5. Log every decision with reasoning for the audit trail.
6. When uncertain (confidence < 0.6), ESCALATE to human rather than act.
7. Provide clear explanations for all actions taken.

## Decision Framework
For each optimization cycle:
1. OBSERVE: Fetch latest metrics from all platforms
2. REASON: Identify underperforming campaigns, anomalies, opportunities
3. ACT: Adjust bids/budgets within guardrails (or escalate if beyond authority)
4. EVALUATE: Compare outcomes to expectations from previous cycle
"""

    _graph = create_agent(
        llm,
        _tools,
        system_prompt=system_prompt,
    )

    log_info("Campaign Orchestrator Agent ready")
    log_info("=" * 60)

    return _graph


# ============================================================================
# A2A Server (FastAPI)
# ============================================================================

def extract_message_text(body: dict) -> str:
    """Extract the user's text from an A2A request."""
    if "prompt" in body:
        return body["prompt"]
    message = body.get("params", {}).get("message", {})
    for part in message.get("parts", []):
        if "text" in part:
            return part["text"]
    return message.get("text", "")


def format_a2a_response(text: str, request_id) -> dict:
    """Format the agent's response as A2A JSON-RPC."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "status": {
                "message": {
                    "role": "assistant",
                    "parts": [{"kind": "text", "text": text}],
                }
            }
        },
    }


app = FastAPI(title="Campaign Orchestrator Agent", version="1.0.0")


@app.post("/")
async def a2a_endpoint(request: FastAPIRequest):
    """A2A JSON-RPC endpoint for the Campaign Orchestrator."""
    try:
        body = await request.json()
        text = extract_message_text(body)

        log_info(f"Request: {text[:100]}...")

        graph = await _initialize_agent()
        result = await graph.ainvoke({"messages": [HumanMessage(content=text)]})

        response_text = (
            result["messages"][-1].content if result.get("messages") else "No response"
        )

        log_info(f"Response: {response_text[:200]}...")

        if "method" not in body:
            return {"response": response_text}
        else:
            return format_a2a_response(response_text, body.get("id"))

    except Exception as e:
        log_error(f"Error: {e}")
        log_error(traceback.format_exc())
        return {
            "jsonrpc": "2.0",
            "id": body.get("id") if "body" in dir() else None,
            "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
        }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "agent": "campaign-orchestrator", "version": "1.0.0"}


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    port = int(os.getenv("AGENT_PORT", "9000"))
    log_info(f"Starting Campaign Orchestrator Agent on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
