# Agentic AI in Advertising — Code Repository

Companion code for **"The Autonomous Marketer: Building Agentic AI Systems That Think, Act, and Rewrite the Rules of Advertising"**.

This repository contains production-ready implementations of every use case described in the book — from autonomous campaign management to a full advertising operating system — built with **Amazon Bedrock AgentCore**, **LangGraph**, and the **Model Context Protocol (MCP)**.

## What's Inside

Eight chapters of working code demonstrating how to build agentic advertising systems that autonomously manage campaigns, generate creative, optimize budgets, and compound institutional learning over time.

| Chapter | Topic | Use Cases |
|---------|-------|-----------|
| [Chapter 1](src/chapter_1/) | The Dawn of Agentic Intelligence | Autonomous Campaign Management |
| [Chapter 2](src/chapter_2/) | Understanding Agentic AI | Multi-Agent Coordination, AI-in-the-Loop Decisions |
| [Chapter 3](src/chapter_3/) | Research & Strategic Planning | Pitch Acceleration, Continuous Category Monitoring |
| [Chapter 4](src/chapter_4/) | Agentic Creative Systems | Multi-Agent Creative Architecture |
| [Chapter 5](src/chapter_5/) | Campaign Execution | Autonomous Execution & Optimization |
| [Chapter 6](src/chapter_6/) | Measurement Systems | Data Foundation for Agentic Advertising |
| [Chapter 7](src/chapter_7/) | Optimization & Attribution | Three-Loop Optimization, Incrementality |
| [Chapter 8](src/chapter_8/) | The Operating System | End-to-End Agentic Advertising OS |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Human Interface (FastAPI)                          │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│              LangGraph Agents on Amazon Bedrock AgentCore             │
│  (Orchestrator, Research, Creative, Execution, Optimization)         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│              MCP Servers (Tools as Protocol)                          │
│  (Amazon Ads MCP, Metrics, Guardrails, Measurement, Coordination)    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│              AWS Infrastructure (CDK-Deployed)                        │
│  Aurora PostgreSQL │ OpenSearch Serverless │ ElastiCache │ S3 │ MSK  │
└─────────────────────────────────────────────────────────────────────┘
```

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Agent Framework | LangGraph (`create_agent`) |
| LLM | Anthropic Claude on Amazon Bedrock (`ChatBedrock`) |
| Agent Runtime | Amazon Bedrock AgentCore (A2A protocol) |
| Tool Protocol | Model Context Protocol (MCP) — AgentCore + Streamable HTTP |
| Ad Platforms | Amazon Ads MCP Server, Meta Ads API, Google Ads API, TikTok Ads API |
| Database | Amazon Aurora PostgreSQL Serverless v2 (+ TimescaleDB) |
| Vector Search | Amazon OpenSearch Serverless (vector search collection) |
| Cache | Amazon ElastiCache Redis Serverless |
| Event Bus | Amazon MSK Serverless (Kafka) |
| Object Storage | Amazon S3 |
| Secrets | AWS Secrets Manager |
| Infrastructure | AWS CDK (Python) |

## Getting Started

### Prerequisites

- AWS Account with access to Bedrock, AgentCore, Aurora, OpenSearch Serverless
- Python 3.13+
- AWS CDK CLI (`npm install -g aws-cdk`)
- Bedrock model access enabled: `anthropic.claude-sonnet-4-20250514`, `amazon.titan-embed-text-v2:0`

### Quick Start (Chapter 1)

```bash
# 1. Deploy infrastructure
cd src/chapter_1/autonomous-campaign-management/infra
pip install -r requirements.txt
cdk deploy --all

# 2. Initialize database
psql -h <aurora-endpoint> -U campaign_admin -d campaign_mgmt \
  -f ../migrations/create_tables.sql

# 3. Deploy MCP servers to AgentCore
cd ../mcp_servers/metrics_server
agentcore configure -e metrics_mcp_server.py --protocol MCP --runtime PYTHON_3_13 -rf requirements.txt
agentcore deploy

# 4. Deploy the Campaign Orchestrator agent
cd ../../agents/orchestrator
agentcore configure -e campaign_orchestrator.py --protocol A2A --runtime PYTHON_3_13 -rf requirements.txt
agentcore deploy

# 5. Run the API locally
cd ../../api
pip install -r requirements.txt
uvicorn main:app --port 8000
# → http://localhost:8000/docs

# 6. Test it
curl -X POST http://localhost:8000/campaigns \
  -H "Content-Type: application/json" \
  -d '{"raw_text": "Launch a premium fitness tracker campaign. $50,000 budget. Target affluent health-conscious consumers aged 25-55. Achieve $35 CPA.", "submitted_by": "sarah@agency.com"}'
```

See [src/DEPLOY.md](src/DEPLOY.md) for the complete deployment guide covering all chapters.

## Repository Structure

```
├── src/
│   ├── DEPLOY.md                    # Full deployment guide
│   ├── chapter_1/                   # Autonomous Campaign Management
│   │   └── autonomous-campaign-management/
│   │       ├── infra/               # CDK stacks (Aurora, OpenSearch, Redis, S3)
│   │       ├── agents/              # LangGraph agents (orchestrator, monitor, optimize, plan)
│   │       ├── mcp_servers/         # MCP tools (metrics, guardrails)
│   │       ├── services/            # Business logic (guardrails, optimization, anomaly, pacing)
│   │       ├── models/              # SQLAlchemy data models
│   │       ├── api/                 # FastAPI human interface
│   │       ├── migrations/          # PostgreSQL + TimescaleDB schema
│   │       ├── tests/               # Unit + property-based tests
│   │       ├── sample_data/         # Realistic test data
│   │       ├── README.md            # Use case documentation
│   │       └── DEPLOY.md            # Step-by-step deployment
│   ├── chapter_2/                   # Multi-Agent Coordination + AI-in-the-Loop
│   ├── chapter_3/                   # Research: Pitch Acceleration + Category Monitoring
│   ├── chapter_4/                   # Creative: Multi-Agent Creative Architecture
│   ├── chapter_5/                   # Execution: Autonomous Campaign Execution
│   ├── chapter_6/                   # Measurement: Data Foundation
│   ├── chapter_7/                   # Optimization: Attribution + Incrementality
│   └── chapter_8/                   # Operating System: End-to-End Integration
├── .gitignore
├── LICENSE
└── README.md                        # This file
```

## Key Patterns Used

Every agent in this repository follows the same pattern (from the [Amazon Ads MCP Server Workshop](https://advertising.amazon.com/API/docs/en-us/knowledge-hub/hands-on-workshops/amazon-ads-mcp-server/05-build-langgraph-agent)):

1. **Load config** from AWS Secrets Manager (with `.env` fallback for local dev)
2. **Initialize ChatBedrock** with Claude on Amazon Bedrock
3. **Discover MCP tools** via AgentCore `invoke_agent_runtime` (dynamic — adapts when tools change)
4. **Build LangGraph agent** with `create_agent` (ReAct pattern for reasoning + tool use)
5. **Expose FastAPI A2A endpoint** for inter-agent communication and AgentCore deployment
6. **Log to CloudWatch** with structured `[INFO]`/`[ERROR]` prefixes

## Who This Is For

- **Engineers** building agentic advertising systems — full code, real patterns, deployable
- **Architects** designing multi-agent ad-tech platforms — CDK infrastructure, coordination protocols
- **Marketing technologists** exploring autonomous campaign management — sample data, step-by-step guides
- **Students** of the book — working implementations of every concept discussed

## License

See [LICENSE](LICENSE) for details.

## Contributing

Issues and PRs welcome. If you encounter technical issues with examples, raise an issue on GitHub.
