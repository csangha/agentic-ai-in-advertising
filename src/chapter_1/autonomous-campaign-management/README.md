# Autonomous Campaign Management

## What This Is

A fully autonomous advertising campaign management system that operates across Meta, Google, TikTok, and Amazon Ads. Given a natural language brief (budget, target CPA, audience, constraints), the system autonomously:

1. **Interprets** the brief and generates platform-specific campaign configurations
2. **Launches** campaigns across all four platforms via APIs
3. **Monitors** performance metrics every 15 minutes
4. **Optimizes** bids and budgets within guardrail boundaries
5. **Detects** anomalies and takes corrective action
6. **Discovers** emerging trends and generates new creative variants
7. **Expands** into new audience segments with controlled testing
8. **Reports** daily summaries explaining every autonomous decision

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Human Interface (API :8000)                    │
│  (Brief Input, Approval Console, Reports, Override Controls)     │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│              Campaign Orchestrator (AgentCore :9000)              │
│  (LangGraph create_agent + Claude on Bedrock)                    │
└──────┬──────────┬──────────┬──────────┬─────────────────────────┘
       │          │          │          │
┌──────▼───┐ ┌───▼────┐ ┌───▼────┐ ┌───▼────┐
│ Planning │ │Monitor │ │Optimize│ │Creative│
│  :9001   │ │ :9001  │ │ :9002  │ │        │
└──────────┘ └────────┘ └────────┘ └────────┘
       │          │          │          │
┌──────▼──────────▼──────────▼──────────▼─────────────────────────┐
│              MCP Servers on AgentCore                             │
│  (Metrics Server, Guardrails Server, Amazon Ads MCP Server)      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│              Infrastructure (CDK-deployed)                        │
│  Aurora PostgreSQL │ OpenSearch Serverless │ Redis │ S3           │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| CDK Infrastructure | `infra/stacks/` | VPC, Aurora PostgreSQL, OpenSearch, Redis, S3, Secrets Manager |
| Campaign Orchestrator | `agents/orchestrator/` | Main LangGraph agent coordinating the agentic loop |
| Monitoring Agent | `agents/monitoring_agent/` | Ingests metrics, detects anomalies, tracks pacing |
| Optimization Agent | `agents/optimization_agent/` | Makes bid/budget decisions within guardrails |
| Planning Agent | `agents/planning_agent/` | Parses briefs, generates platform configs |
| Metrics MCP Server | `mcp_servers/metrics_server/` | Exposes campaign metrics as discoverable tools |
| Guardrails MCP Server | `mcp_servers/guardrails_server/` | Safety boundary enforcement tools |
| Guardrail Engine | `services/guardrail_engine.py` | 7 guardrail types (budget cap, CPA ceiling, bid limits, etc.) |
| Optimization Engine | `services/optimization_engine.py` | Effective score computation, bounded adjustments |
| Anomaly Detector | `services/anomaly_detector.py` | Z-score + rate-of-change detection |
| Pacing Engine | `services/pacing_engine.py` | Budget delivery tracking and projection |
| Brief Parser | `services/brief_parser.py` | LLM-powered brief interpretation |
| REST API | `api/main.py` | Human interface for campaign management |
| Data Models | `models/` | SQLAlchemy ORM (campaign, audit, guardrails, metrics, platforms) |
| Database Schema | `migrations/create_tables.sql` | PostgreSQL + TimescaleDB tables |
| Tests | `tests/` | Unit tests for guardrails, optimization, anomaly detection, pacing |
| Sample Data | `sample_data/` | Realistic test data for all components |

## How It Works

### The 15-Minute Optimization Cycle

Every 15 minutes, the system executes:

1. **Monitoring Agent** fetches latest metrics from all platforms
2. Metrics normalized into canonical schema (TimescaleDB)
3. **Anomaly Detector** checks for Z-score deviations (>2σ) and rate-of-change spikes (>50%/hour)
4. **Pacing Engine** verifies budget delivery is within 80-120% of expected
5. **Optimization Agent** computes bid/budget recommendations
6. **Guardrail Engine** validates EVERY proposed action before execution
7. Approved actions executed via platform MCP tools
8. All decisions logged to immutable audit trail with full reasoning

### Safety Guarantees (Guardrails)

| Guardrail | Rule | Type |
|-----------|------|------|
| Budget Cap | Total spend NEVER exceeds approved budget | Hard (blocks) |
| Bid Change Limit | Maximum ±15% per cycle | Hard (blocks) |
| CPA Circuit Breaker | Pause if CPA > 200% target for > 4 hours | Hard (blocks + escalates) |
| Spend Rate | Max 20% daily budget reallocation without approval | Soft (escalates) |
| Sentiment Floor | Halt creative gen if sentiment < 75% | Hard (blocks) |
| Audience Concentration | Min 70% budget on proven audiences | Hard (blocks) |
| Escalation Threshold | Actions affecting >30% budget need human approval | Soft (escalates) |

## Getting Started

```bash
# 1. Deploy infrastructure
cd infra
pip install -r requirements.txt
cdk deploy --all

# 2. Initialize database
psql -h <aurora-endpoint> -U campaign_admin -d campaign_mgmt -f ../migrations/create_tables.sql

# 3. Run the orchestrator locally
cd ../agents/orchestrator
cp .env.example .env  # Fill in your values
pip install -r requirements.txt
python campaign_orchestrator.py  # Runs on :9000

# 4. Run the API server
cd ../../api
pip install -r requirements.txt
uvicorn main:app --port 8000  # API docs at /docs

# 5. Test with sample brief
curl -X POST http://localhost:9000 \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Launch a premium fitness tracker campaign. $50,000 budget. Target affluent health-conscious consumers aged 25-55. Achieve $35 CPA."}'
```

## Sample Data

The `sample_data/` directory contains realistic test data:
- `sample_campaign_brief.json` — Natural language brief input
- `sample_parsed_brief.json` — LLM-extracted structured parameters
- `sample_campaign_state.json` — Active campaign with all metrics
- `sample_performance_metrics.json` — 24h performance by platform and creative
- `sample_guardrails.json` — Full guardrail configuration
- `sample_audit_entries.json` — Example autonomous decisions with reasoning
