# Deployment Guide: Agentic Advertising Operating System

## Prerequisites

- ALL prior chapters deployed (Ch1-Ch7 provide the layer-specific agents and services)
- Full infrastructure running (Aurora, OpenSearch, Redis, MSK, S3)
- All MCP servers deployed to AgentCore
- All layer agents running (research, creative, execution, measurement, optimization)

## Step 1: Deploy System Orchestrator

This is the top-level agent that coordinates all other agents:

```bash
cd agents
agentcore configure -e system_orchestrator.py --protocol A2A --runtime PYTHON_3_13
agentcore deploy
# Port 9000 (primary endpoint for the full system)

# Set environment variables:
#   SECRET_NAME = campaign-mgmt/agent-config
#   AWS_REGION = us-east-1
```

## Step 2: Initialize Shared Memory

```bash
python -c "
from services.shared_memory_manager import SharedMemoryManager, MemoryType

mgr = SharedMemoryManager()

# Seed Brand Memory
mgr.write(MemoryType.BRAND, 'positioning', 'Performance without compromise — fitness tech for busy professionals', 'org-acme', 'admin')
mgr.write(MemoryType.BRAND, 'voice_tone', 'Empowering yet approachable. Never condescending. Data-informed, not data-obsessed.', 'org-acme', 'admin')
mgr.write(MemoryType.BRAND, 'restrictions', {'prohibited_claims': ['guaranteed weight loss', 'medical device'], 'prohibited_topics': ['body shaming', 'extreme dieting']}, 'org-acme', 'admin')

print(f'Memory stats: {mgr.memory_stats()}')
"
```

## Step 3: Register Feedback Loops

```bash
python -c "
from services.feedback_loop_registry import FeedbackLoopRegistry

registry = FeedbackLoopRegistry()
loops = registry.get_active_loops()
print(f'{len(loops)} default feedback loops registered:')
for loop in loops:
    print(f'  {loop.source_layer} → {loop.target_layer}: {loop.trigger}')
"
```

## Step 4: Create a Campaign (Full Lifecycle)

```bash
# Start a campaign from research phase
curl -X POST https://<system-orchestrator-endpoint> \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Start a new campaign for FitPulse Pro fitness tracker. Budget $50,000. Target affluent health-conscious consumers 30-50 in US metros. Achieve $35 CPA. Begin with market research phase."}'
```

The system will:
1. Activate research agents (trend scout, competitive intel, sentiment)
2. Synthesize findings into opportunities
3. Transition to PLANNING → generate strategy and creative brief
4. Activate creative agents (concept exploration, copy, visuals)
5. Await human approval on creative direction
6. Launch across platforms
7. Begin 15-minute optimization cycles
8. Feed learnings back into shared memory

## Step 5: Monitor the Operating System

```bash
# Check campaign lifecycle status
curl -X POST https://<system-orchestrator-endpoint> \
  -d '{"prompt": "What is the current lifecycle stage and health of campaign camp-fitpulse-001?"}'

# View feedback loop activity
curl -X POST https://<system-orchestrator-endpoint> \
  -d '{"prompt": "Show me recent cross-layer feedback events for the last 24 hours."}'

# View shared memory contents
curl -X POST https://<system-orchestrator-endpoint> \
  -d '{"prompt": "What learnings have we accumulated for the FitPulse brand?"}'
```

## Step 6: Test with Sample Campaign Object

```bash
# Load the full sample campaign object showing all layers
cat sample_data/sample_campaign_object.json

# Ask the system to analyze it
curl -X POST https://<system-orchestrator-endpoint> \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Analyze this campaign state and recommend next actions based on learnings: accountability theme outperforms by 22%, TikTok CPA too high."}'
```

## Running Locally

```bash
python agents/system_orchestrator.py  # Port 9000
```

## Full System Health Check

```bash
# Check all layer agents are healthy
for port in 9000 9001 9002 9010 9020 9030 9100 9200 9210 9300; do
  echo "Port $port: $(curl -s http://localhost:$port/health | python -c 'import sys,json; print(json.load(sys.stdin).get(\"status\",\"ERROR\"))' 2>/dev/null || echo 'UNREACHABLE')"
done
```

## Architecture Verification

The operating system is working correctly when:
- Research findings automatically populate creative briefs
- Creative performance data feeds back to inform next campaign's concept generation
- Optimization policy updates propagate to all active campaigns
- Shared memory grows with each campaign cycle (never shrinks)
- Every cross-layer feedback event is logged in the audit trail
- Governance policies block unauthorized actions regardless of optimization pressure
