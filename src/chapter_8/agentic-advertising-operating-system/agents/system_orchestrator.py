"""
System Orchestrator — the top-level agent for the Agentic Advertising Operating System.

Coordinates all layers: research, creative, execution, measurement, and optimization.
Manages campaign lifecycle, cross-layer feedback loops, and shared memory.

This is the "operating system" that ties Chapters 1-7 together.
Deployed as the primary A2A service on Amazon Bedrock AgentCore.
"""

from langchain_core.messages import HumanMessage
from langchain_aws import ChatBedrock
from langchain.agents import create_agent
from dotenv import load_dotenv
from botocore.config import Config
import json, os, sys, boto3
from datetime import datetime
import uvicorn
from fastapi import FastAPI, Request as FastAPIRequest

load_dotenv()

def log_info(msg): print(f"[INFO] {datetime.now().isoformat()} - {msg}", flush=True)
def log_error(msg): print(f"[ERROR] {datetime.now().isoformat()} - {msg}", file=sys.stderr, flush=True)

CONFIG = {"AWS_REGION": os.getenv("AWS_REGION", "us-east-1"), "MODEL_ID": os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514")}
_graph = None


async def _initialize_agent():
    global _graph
    if _graph: return _graph

    log_info("Initializing System Orchestrator (Advertising Operating System)...")
    llm = ChatBedrock(
        client=boto3.client("bedrock-runtime", region_name=CONFIG["AWS_REGION"],
                           config=Config(retries={"max_attempts": 3, "mode": "adaptive"})),
        model_id=CONFIG["MODEL_ID"],
        model_kwargs={"temperature": 0.1, "max_tokens": 8192},
    )

    system_prompt = """You are the System Orchestrator — the operating system for an autonomous advertising platform.

## Your Role
You coordinate all layers of the advertising lifecycle:
1. RESEARCH — Market sensing, competitive intel, trend detection
2. CREATIVE — Concept generation, copy, visuals, compliance
3. EXECUTION — Campaign launch, bid management, pacing, rotation
4. MEASUREMENT — Data ingestion, normalization, quality monitoring
5. OPTIMIZATION — Attribution, incrementality, causally-aware allocation

## Campaign Lifecycle Management
Campaigns flow: RESEARCH → PLANNING → CREATIVE → LAUNCH → ACTIVE → LEARNING → ARCHIVED
You manage transitions between stages and ensure each layer feeds the next.

## Cross-Layer Feedback Loops
- Measurement → Creative: fatigue detected → trigger refresh
- Measurement → Research: audience shift → update hypotheses
- Optimization → Creative: winning themes → inform next generation
- Optimization → Execution: channel efficiency → adjust allocation
- Research → Execution: new trend → test new targeting

## Shared Memory
You maintain institutional intelligence across campaigns:
- Brand Memory (positioning, voice, constraints)
- Research Memory (hypotheses, trends, competitive landscape)
- Creative Memory (themes, performance, fatigue patterns)
- Execution Memory (bid patterns, anomaly playbooks)
- Measurement Memory (attribution calibrations, data caveats)

## Governance Rules
- Every decision logged for audit
- Governance policies override all optimization
- Privacy compliance (GDPR/CCPA) always enforced
- Human escalation for: strategic shifts, brand identity, large budget moves, novel situations

## Operating Principles
- Compound learning: each campaign makes the next one smarter
- Continuity: carry context between stages, don't start fresh
- Transparency: explain every cross-layer influence
- Safety: guardrails are inviolable constraints"""

    _graph = create_agent(llm, [], system_prompt=system_prompt)
    log_info("System Orchestrator ready")
    return _graph


app = FastAPI(title="Agentic Advertising Operating System")

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
async def health(): return {"status": "healthy", "agent": "system-orchestrator", "version": "1.0.0"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("AGENT_PORT", "9000")), log_level="warning")
