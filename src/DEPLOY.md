# Deployment Guide: Agentic AI in Advertising

Complete deployment guide for all 8 chapters of the advertising AI system.

## Prerequisites

- AWS Account with access to: Bedrock, AgentCore, Aurora, OpenSearch Serverless, ElastiCache, MSK, S3
- AWS CDK CLI installed (`npm install -g aws-cdk`)
- Python 3.13+
- Bedrock model access enabled for: `anthropic.claude-sonnet-4-20250514`, `amazon.titan-embed-text-v2:0`
- (Optional) Amazon Ads API credentials for Amazon Ads MCP Server

## Quick Start

### 1. Deploy Infrastructure (Chapter 1 CDK)

```bash
cd src/chapter_1/autonomous-campaign-management/infra
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy all stacks
cdk deploy --all --require-approval never
```

This creates:
- Aurora PostgreSQL Serverless v2 (shared database)
- OpenSearch Serverless vector search collection
- ElastiCache Redis Serverless
- S3 buckets (raw data, audit, assets, reports)
- Secrets Manager secrets (fill in credentials after deploy)

### 2. Initialize Database

```bash
# Get the Aurora endpoint from CDK outputs
# Connect and run the migration script
psql -h <aurora-endpoint> -U campaign_admin -d campaign_mgmt -f src/chapter_1/autonomous-campaign-management/migrations/create_tables.sql
```

### 3. Configure Secrets

After CDK deploys, update the secrets in AWS Secrets Manager:

```bash
aws secretsmanager update-secret \
  --secret-id campaign-mgmt/agent-config \
  --secret-string '{
    "AWS_REGION": "us-east-1",
    "MODEL_ID": "us.anthropic.claude-sonnet-4-20250514",
    "MCP_METRICS_ARN": "<from agentcore deploy>",
    "MCP_GUARDRAILS_ARN": "<from agentcore deploy>",
    "OPENSEARCH_ENDPOINT": "<from CDK output>",
    "REDIS_ENDPOINT": "<from CDK output>"
  }'

# If using Amazon Ads MCP Server:
aws secretsmanager update-secret \
  --secret-id campaign-mgmt/amazon-ads-credentials \
  --secret-string '{
    "CLIENT_ID": "<your_client_id>",
    "CLIENT_SECRET": "<your_client_secret>",
    "REFRESH_TOKEN": "<your_refresh_token>"
  }'
```

### 4. Deploy MCP Servers to AgentCore

```bash
# Deploy Metrics MCP Server
cd src/chapter_1/autonomous-campaign-management/mcp_servers/metrics_server
pip install -r requirements.txt
agentcore configure -e metrics_mcp_server.py --protocol MCP --runtime PYTHON_3_13 -rf requirements.txt
agentcore deploy

# Deploy Guardrails MCP Server
cd ../guardrails_server
pip install -r requirements.txt
agentcore configure -e guardrails_mcp_server.py --protocol MCP --runtime PYTHON_3_13 -rf requirements.txt
agentcore deploy
```

Note the Runtime ARNs from each deploy — you'll need them for agent config.

### 5. Deploy Agents to AgentCore

```bash
# Deploy Campaign Orchestrator (Chapter 1 — main agent)
cd src/chapter_1/autonomous-campaign-management/agents/orchestrator
pip install -r requirements.txt
agentcore configure -e campaign_orchestrator.py --protocol A2A --runtime PYTHON_3_13 -rf requirements.txt
agentcore deploy

# Deploy Monitoring Agent
cd ../monitoring_agent
agentcore configure -e monitoring_agent.py --protocol A2A --runtime PYTHON_3_13 -rf requirements.txt
agentcore deploy

# Deploy Optimization Agent
cd ../optimization_agent
agentcore configure -e optimization_agent.py --protocol A2A --runtime PYTHON_3_13 -rf requirements.txt
agentcore deploy
```

Set environment variables in AgentCore console:
- `SECRET_NAME`: `campaign-mgmt/agent-config`
- `AWS_REGION`: `us-east-1`
- `TOOL_FILTER`: `campaign_management,reporting,account_management`

### 6. Run Locally (Development)

```bash
cd src/chapter_1/autonomous-campaign-management/agents/orchestrator
cp .env.example .env
# Edit .env with your values
pip install -r requirements.txt
python campaign_orchestrator.py
# Runs on http://localhost:9000
```

Test it:
```bash
curl -X POST http://localhost:9000 \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Launch a premium fitness tracker campaign. $50,000 budget. Target affluent health-conscious consumers aged 25-55. Achieve $35 CPA."}'
```

### 7. Run the API Server

```bash
cd src/chapter_1/autonomous-campaign-management/api
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# API docs at http://localhost:8000/docs
```

### 8. Run Tests

```bash
cd src/chapter_1/autonomous-campaign-management
pip install pytest
pytest tests/ -v
```

## Chapter-by-Chapter Deployment

Each chapter's agent follows the same pattern:

| Chapter | Agent | Port | Deploy Command |
|---------|-------|------|----------------|
| Ch 1 | Campaign Orchestrator | 9000 | `agentcore deploy` in agents/orchestrator/ |
| Ch 1 | Monitoring Agent | 9001 | `agentcore deploy` in agents/monitoring_agent/ |
| Ch 1 | Optimization Agent | 9002 | `agentcore deploy` in agents/optimization_agent/ |
| Ch 2 | Registry Agent | 9100 | `agentcore deploy` in agents/registry_agent/ |
| Ch 2 | Routing Agent | 9110 | `agentcore deploy` in agents/routing_agent/ |
| Ch 3 | Research Orchestrator | 9010 | `agentcore deploy` in agents/ |
| Ch 3 | Trend Scout | 9200 | `agentcore deploy` in agents/trend_scout/ |
| Ch 3 | Category Monitor | 9210 | `agentcore deploy` in agents/ |
| Ch 4 | Creative Orchestrator | 9020 | `agentcore deploy` in agents/ |
| Ch 5 | Execution Agent | 9030 | `agentcore deploy` in agents/ |
| Ch 7 | Optimization Policy | 9300 | `agentcore deploy` in agents/ |
| Ch 8 | System Orchestrator | 9000 | `agentcore deploy` in agents/ |

## Architecture Overview

```
User → API (FastAPI :8000) → Campaign Orchestrator (AgentCore)
                                    ↓
                    ┌───────────────┼───────────────┐
                    ↓               ↓               ↓
            Monitoring Agent   Optimization Agent   Creative Agent
                    ↓               ↓               ↓
            ┌───────┴───────┐  ┌───┴───┐    ┌─────┴─────┐
            │ Metrics MCP   │  │Guards │    │ Ads MCP   │
            │ Server        │  │MCP    │    │ Server    │
            └───────┬───────┘  └───┬───┘    └─────┬─────┘
                    ↓               ↓               ↓
            Aurora PostgreSQL   Redis Cache   Amazon Ads API
            OpenSearch          S3 Storage
```

## Troubleshooting

- **Agent not responding**: Check CloudWatch Logs for the runtime. Look for `[ERROR]` entries.
- **MCP tools not discovered**: Verify MCP server ARN in Secrets Manager matches deployed runtime.
- **Database connection failed**: Check VPC security groups allow inbound 5432 from agent subnets.
- **Bedrock model errors**: Ensure model access is enabled in Bedrock console for your region.
- **OAuth token errors (Amazon Ads)**: Verify CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN in Secrets Manager.
