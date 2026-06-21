"""
Creative Orchestrator Agent — coordinates the multi-agent creative workflow.

Workflow: Brief → Concept Exploration → Human Selection → Copy + Visual → Compliance → Production

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
def log_error(msg): print(f"[ERROR] {datetime.now().isoformat()} - {msg}", file=sys.stderr, flush=True)

CONFIG = {"AWS_REGION": os.getenv("AWS_REGION", "us-east-1"), "MODEL_ID": os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514")}
_graph = None


async def _initialize_agent():
    global _graph
    if _graph: return _graph

    log_info("Initializing Creative Orchestrator...")
    llm = ChatBedrock(
        client=boto3.client("bedrock-runtime", region_name=CONFIG["AWS_REGION"],
                           config=Config(retries={"max_attempts": 3, "mode": "adaptive"})),
        model_id=CONFIG["MODEL_ID"],
        model_kwargs={"temperature": 0.3, "max_tokens": 4096},
    )

    system_prompt = """You are the Creative Orchestrator for an advertising agency's AI creative system.

## Your Workflow
1. Receive creative brief (product, audience, emotional tone, positioning)
2. Generate 10+ concept territories (diverse, ranked by resonance + novelty)
3. Present territories to Creative Director for selection
4. For selected territories: generate copy variations (20+ per territory) + visual concepts
5. Run compliance checks on all generated content
6. Scale approved creative across platforms and formats
7. After launch: ingest performance data and feed learnings back

## Creative Generation Rules
- Maintain brand voice (retrieve guidelines via RAG before generating)
- Ensure diversity: no two territories should have embedding similarity > 0.85
- All copy must pass compliance before reaching production
- Tag every variant: message_theme, hook_type, emotional_tone, cta_type
- Voice consistency score must be > 0.7 for all output

## Platform Awareness
- Meta: emotional, story-driven, visual-first
- Google: intent-matched, feature-benefit, clear CTAs
- TikTok: authentic, trend-aware, short-form, casual
- Amazon: product-focused, comparison-ready, conversion-optimized"""

    _graph = create_agent(llm, [], system_prompt=system_prompt)
    log_info("Creative Orchestrator ready")
    return _graph


app = FastAPI(title="Creative Orchestrator Agent")

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
async def health(): return {"status": "healthy", "agent": "creative-orchestrator"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("AGENT_PORT", "9020")), log_level="warning")
