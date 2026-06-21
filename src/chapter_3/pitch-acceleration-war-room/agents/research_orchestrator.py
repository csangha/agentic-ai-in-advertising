"""
Research Orchestrator Agent — coordinates pitch research across specialist agents.

Activates Trend Scout, Competitive Intel, and Sentiment agents in parallel,
then synthesizes findings into prioritized opportunities.

Deployed as A2A service on Amazon Bedrock AgentCore.
"""

from langchain_core.messages import HumanMessage
from langchain_aws import ChatBedrock
from langchain.agents import create_agent
from langchain_core.tools import StructuredTool
from typing import Optional
from pydantic import Field, create_model
from dotenv import load_dotenv
from botocore.config import Config
import json, os, sys, boto3
from datetime import datetime
import uvicorn
from fastapi import FastAPI, Request as FastAPIRequest

load_dotenv()

def log_info(msg): print(f"[INFO] {datetime.now().isoformat()} - {msg}", flush=True)
def log_error(msg): print(f"[ERROR] {datetime.now().isoformat()} - {msg}", file=sys.stderr, flush=True)


def load_config() -> dict:
    secret_name = os.getenv("SECRET_NAME", "campaign-mgmt/agent-config")
    region = os.getenv("AWS_REGION", "us-east-1")
    try:
        sm = boto3.client("secretsmanager", region_name=region)
        return json.loads(sm.get_secret_value(SecretId=secret_name)["SecretString"])
    except Exception:
        return {"AWS_REGION": region, "MODEL_ID": os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514")}


CONFIG = load_config()
_graph = None


async def _initialize_agent():
    global _graph
    if _graph:
        return _graph

    log_info("Initializing Research Orchestrator Agent...")

    llm = ChatBedrock(
        client=boto3.client("bedrock-runtime", region_name=CONFIG.get("AWS_REGION", "us-east-1"),
                           config=Config(retries={"max_attempts": 3, "mode": "adaptive"})),
        model_id=CONFIG.get("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514"),
        model_kwargs={"temperature": 0.1, "max_tokens": 4096},
    )

    # In production: discover tools from MCP servers (trend_scout, competitive_intel, sentiment)
    # For now, define placeholder tools that will be replaced by MCP discovery
    tools = []

    system_prompt = """You are the Research Orchestrator for an advertising agency pitch acceleration system.

When a pitch brief arrives, you coordinate parallel research across:
1. Trend Scout — detects rising topics, search trends, cultural signals
2. Competitive Intelligence — maps competitor messaging, creative, spend
3. Sentiment & Narrative — analyzes consumer reviews, pain points, language

After all agents report, you synthesize findings into:
- Ranked opportunity statements (scored by market velocity × competitive emptiness × brand fit)
- Positioning hypotheses for the top 3 opportunities
- Evidence packages with source citations

Rules:
- All claims must have source attribution
- Flag contradictions between data sources explicitly
- Prioritize by: impact potential × time sensitivity × confidence
- Complete within 48 hours of brief submission"""

    _graph = create_agent(llm, tools, system_prompt=system_prompt)
    log_info("Research Orchestrator ready")
    return _graph


app = FastAPI(title="Research Orchestrator Agent")

@app.post("/")
async def a2a_endpoint(request: FastAPIRequest):
    body = await request.json()
    text = body.get("prompt", "") or next(
        (p["text"] for p in body.get("params", {}).get("message", {}).get("parts", []) if "text" in p), ""
    )
    graph = await _initialize_agent()
    result = await graph.ainvoke({"messages": [HumanMessage(content=text)]})
    resp = result["messages"][-1].content if result.get("messages") else "No response"
    if "method" in body:
        return {"jsonrpc": "2.0", "id": body.get("id"), "result": {"status": {"message": {"role": "assistant", "parts": [{"kind": "text", "text": resp}]}}}}
    return {"response": resp}

@app.get("/health")
async def health(): return {"status": "healthy", "agent": "research-orchestrator"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("AGENT_PORT", "9010")), log_level="warning")
