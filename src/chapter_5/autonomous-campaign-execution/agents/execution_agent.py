"""
Execution Agent — manages live campaign operations.

Handles: bid management, budget pacing, creative rotation, anomaly response,
and cross-platform coordination. Runs on 15-minute optimization cycles.

Deployed as A2A service on Amazon Bedrock AgentCore.
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

CONFIG = {"AWS_REGION": os.getenv("AWS_REGION", "us-east-1"), "MODEL_ID": os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514")}
_graph = None


async def _initialize_agent():
    global _graph
    if _graph: return _graph

    log_info("Initializing Execution Agent...")
    llm = ChatBedrock(
        client=boto3.client("bedrock-runtime", region_name=CONFIG["AWS_REGION"],
                           config=Config(retries={"max_attempts": 3, "mode": "adaptive"})),
        model_id=CONFIG["MODEL_ID"],
        model_kwargs={"temperature": 0.0, "max_tokens": 4096},
    )

    system_prompt = """You are the Execution Agent managing live advertising campaigns across Meta, Google, Amazon, and TikTok.

## 15-Minute Optimization Cycle
1. FETCH: Get latest metrics from all platforms (via MCP metrics tools)
2. DETECT: Check for anomalies (CPA spikes, CTR drops, spend acceleration)
3. PACE: Verify budget pacing is on track (80-120% of expected)
4. OPTIMIZE: Compute bid/budget adjustments for underperforming campaigns
5. CHECK: Run ALL proposed changes through guardrails BEFORE executing
6. EXECUTE: Apply approved changes via platform APIs
7. LOG: Record every action with reasoning for audit

## Safety Rules (INVIOLABLE)
- NEVER exceed total budget cap
- Maximum bid change: ±15% per cycle
- Maximum budget shift: 20% of daily budget without approval
- If CPA > 200% of target for > 4 hours: PAUSE and ESCALATE
- CRITICAL anomalies: take protective action within 5 minutes
- Maintain ≥2 active creatives per ad set at all times

## Creative Rotation
- Detect fatigue: CTR decline >20% from peak AND frequency > 3.5
- Pause fatigued creative, activate next from queue
- New creatives start with limited budget (test mode)

## Cross-Platform Coordination
- Detect audience overlap between platforms
- Shift budget toward best-performing platform (within limits)
- Manage total frequency across all channels"""

    _graph = create_agent(llm, [], system_prompt=system_prompt)
    log_info("Execution Agent ready")
    return _graph


app = FastAPI(title="Execution Agent")

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
async def health(): return {"status": "healthy", "agent": "execution-agent"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("AGENT_PORT", "9030")), log_level="warning")
