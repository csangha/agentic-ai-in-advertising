"""
Optimization Policy Agent — causally-aware optimization decision-making.

Uses incrementality evidence to make better optimization decisions than
pure attribution-based approaches. Recommends spend allocation changes,
experiment designs, and policy updates.

Deployed as A2A service on Amazon Bedrock AgentCore. Port 9300.
"""

from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage
from langchain_aws import ChatBedrock
from langchain.agents import create_agent
from typing import Optional
from pydantic import Field, create_model
from dotenv import load_dotenv
from botocore.config import Config
import json
import os
import sys
import boto3
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Request as FastAPIRequest

load_dotenv()


def log_info(msg): print(f"[INFO] {datetime.now().isoformat()} - {msg}", flush=True)
def log_error(msg): print(f"[ERROR] {datetime.now().isoformat()} - {msg}", file=sys.stderr, flush=True)


def load_config() -> dict:
    secret_name = os.getenv("SECRET_NAME", "optimization-policy/agent-config")
    region = os.getenv("AWS_REGION", "us-east-1")
    try:
        sm = boto3.client("secretsmanager", region_name=region)
        resp = sm.get_secret_value(SecretId=secret_name)
        return json.loads(resp["SecretString"])
    except Exception:
        return {
            "AWS_REGION": region,
            "MODEL_ID": os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514"),
            "MCP_MEASUREMENT_ARN": os.getenv("MCP_MEASUREMENT_ARN"),
        }


CONFIG = load_config()
AWS_REGION = CONFIG.get("AWS_REGION", "us-east-1")

_agentcore_client = None


def get_agentcore_client():
    global _agentcore_client
    if not _agentcore_client:
        _agentcore_client = boto3.client(
            "bedrock-agentcore", region_name=AWS_REGION,
            config=Config(retries={"max_attempts": 3, "mode": "adaptive"}, read_timeout=30),
        )
    return _agentcore_client


def call_mcp(server_arn: str, method: str, params: dict = None) -> dict:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode()
    resp = get_agentcore_client().invoke_agent_runtime(
        agentRuntimeArn=server_arn, payload=payload,
        qualifier="DEFAULT", contentType="application/json",
        accept="application/json, text/event-stream",
    )
    raw = resp["response"].read().decode()
    if raw.startswith("data: "):
        for line in raw.strip().splitlines():
            if line.startswith("data: "):
                return json.loads(line[6:]).get("result", {})
    return json.loads(raw[raw.find("{"):]).get("result", {})


def create_mcp_tool(mcp_tool: dict, server_arn: str, prefix: str) -> StructuredTool:
    name = f"{prefix}_{mcp_tool['name']}"
    schema = mcp_tool.get("inputSchema", {})
    props = schema.get("properties", {})
    type_map = {"string": str, "integer": int, "number": float, "boolean": bool}
    fields = {
        k: (Optional[type_map.get(v.get("type", "string"), str)], Field(default=None, description=v.get("description", "")))
        for k, v in props.items()
    }
    Model = create_model(f"{name}_args", **fields) if fields else create_model(f"{name}_args")

    def func(**kwargs):
        filtered = {k: v for k, v in kwargs.items() if v is not None}
        result = call_mcp(server_arn, "tools/call", {"name": mcp_tool["name"], "arguments": filtered})
        content = result.get("content", [])
        if content and isinstance(content, list):
            return "\n".join(c.get("text", "") for c in content if c.get("type") == "text") or str(result)
        return str(result)

    return StructuredTool(name=name, description=mcp_tool.get("description", ""), func=func, args_schema=Model)


_graph = None


async def _initialize_agent():
    global _graph
    if _graph:
        return _graph

    log_info("Initializing Optimization Policy Agent...")
    tools = []

    measurement_arn = CONFIG.get("MCP_MEASUREMENT_ARN")
    if measurement_arn:
        call_mcp(measurement_arn, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "optimization-policy-agent", "version": "1.0.0"},
        })
        result = call_mcp(measurement_arn, "tools/list", {})
        for t in result.get("tools", []):
            tools.append(create_mcp_tool(t, measurement_arn, "measure"))
        log_info(f"Measurement MCP: {len(result.get('tools', []))} tools")

    llm = ChatBedrock(
        client=boto3.client(
            "bedrock-runtime", region_name=AWS_REGION,
            config=Config(retries={"max_attempts": 3, "mode": "adaptive"}),
        ),
        model_id=CONFIG.get("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514"),
        model_kwargs={"temperature": 0.0, "max_tokens": 4096},
    )

    system_prompt = """You are the Optimization Policy Agent — a causally-aware optimization engine.

Unlike traditional optimizers that rely solely on attribution (which can be biased),
you use incrementality evidence from experiments to make better decisions.

Your approach:
1. Compute effective scores that blend attribution + incrementality evidence
2. Weight evidence by freshness (recent experiments matter more)
3. Recommend spend allocation changes based on TRUE causal impact
4. Design new experiments when evidence is stale or missing
5. Flag channels where attribution overstates (or understates) true impact

Key concepts:
- EFFECTIVE SCORE: Blends attribution (frequent, possibly biased) with incrementality
  (causal, infrequent). Attribution weight decreases as incrementality evidence grows.
- EVIDENCE DECAY: Experiments lose weight over time (60-day half-life). Stale evidence
  (>90 days) triggers recommendation to re-test.
- POLICY ACTIONS: increase_spend, maintain_spend, decrease_spend, pause, test_further

For each recommendation, provide:
- Channel and tactic
- Effective score and components (attribution vs incrementality)
- Recommended action with confidence level
- Evidence freshness and next experiment suggestion
- Expected impact of the recommendation

Be data-driven. Clearly state when confidence is low and testing is needed.
Never recommend large spend shifts without strong incrementality evidence."""

    _graph = create_agent(llm, tools, system_prompt=system_prompt)
    log_info("Optimization Policy Agent ready")
    return _graph


app = FastAPI(title="Optimization Policy Agent")


@app.post("/")
async def a2a_endpoint(request: FastAPIRequest):
    body = await request.json()
    text = body.get("prompt") or ""
    parts = body.get("params", {}).get("message", {}).get("parts", [])
    if not text and parts:
        text = next((p["text"] for p in parts if "text" in p), "")

    graph = await _initialize_agent()
    result = await graph.ainvoke({"messages": [HumanMessage(content=text)]})
    resp = result["messages"][-1].content if result.get("messages") else "No data"

    if "method" in body:
        return {
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "result": {"status": {"message": {"role": "assistant", "parts": [{"kind": "text", "text": resp}]}}},
        }
    return {"response": resp}


@app.get("/health")
async def health():
    return {"status": "healthy", "agent": "optimization-policy-agent"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("AGENT_PORT", "9300")), log_level="warning")
