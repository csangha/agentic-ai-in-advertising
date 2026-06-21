# Deployment Guide: Autonomous Campaign Management

## Prerequisites

- AWS Account with Bedrock, AgentCore, Aurora, OpenSearch Serverless, ElastiCache, S3 access
- AWS CDK CLI (`npm install -g aws-cdk`)
- Python 3.13+
- Bedrock model access: `anthropic.claude-sonnet-4-20250514`, `amazon.titan-embed-text-v2:0`
- (Optional) Amazon Ads API credentials

## Step 1: Deploy Infrastructure (CDK)

```bash
cd infra
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy all stacks
cdk deploy --all --require-approval never
```

**Outputs to note:**
- `CampaignMgmt-Database.ClusterEndpoint` → Aurora PostgreSQL endpoint
- `CampaignMgmt-Database.SecretArn` → DB credentials secret
- `CampaignMgmt-OpenSearch.CollectionEndpoint` → OpenSearch endpoint
- `CampaignMgmt-Cache.RedisEndpoint` → Redis endpoint
- `CampaignMgmt-Storage.RawBucketName` → S3 raw data bucket

## Step 2: Initialize Database

```bash
# Get credentials from Secrets Manager
aws secretsmanager get-secret-value --secret-id campaign-mgmt/db-credentials --query SecretString --output text

# Connect and run schema migration
psql -h <ClusterEndpoint> -U campaign_admin -d campaign_mgmt -f migrations/create_tables.sql
```

## Step 3: Configure Secrets

```bash
# Update agent config with real values from CDK outputs
aws secretsmanager update-secret \
  --secret-id campaign-mgmt/agent-config \
  --secret-string '{
    "AWS_REGION": "us-east-1",
    "MODEL_ID": "us.anthropic.claude-sonnet-4-20250514",
    "MCP_METRICS_ARN": "DEPLOY_IN_STEP_4",
    "MCP_GUARDRAILS_ARN": "DEPLOY_IN_STEP_4",
    "OPENSEARCH_ENDPOINT": "<CollectionEndpoint>",
    "REDIS_ENDPOINT": "<RedisEndpoint>"
  }'

# (Optional) Amazon Ads credentials
aws secretsmanager update-secret \
  --secret-id campaign-mgmt/amazon-ads-credentials \
  --secret-string '{
    "CLIENT_ID": "<your_client_id>",
    "CLIENT_SECRET": "<your_client_secret>",
    "REFRESH_TOKEN": "<your_refresh_token>"
  }'
```

## Step 4: Deploy MCP Servers to AgentCore

```bash
# Metrics MCP Server
cd mcp_servers/metrics_server
pip install -r requirements.txt
agentcore configure -e metrics_mcp_server.py --protocol MCP --runtime PYTHON_3_13 -rf requirements.txt
agentcore deploy
# Note the Runtime ARN → update MCP_METRICS_ARN in secrets

# Guardrails MCP Server
cd ../guardrails_server
pip install -r requirements.txt
agentcore configure -e guardrails_mcp_server.py --protocol MCP --runtime PYTHON_3_13 -rf requirements.txt
agentcore deploy
# Note the Runtime ARN → update MCP_GUARDRAILS_ARN in secrets
```

After deploying both MCP servers, update the agent-config secret with the ARNs:
```bash
aws secretsmanager update-secret \
  --secret-id campaign-mgmt/agent-config \
  --secret-string '{
    "AWS_REGION": "us-east-1",
    "MODEL_ID": "us.anthropic.claude-sonnet-4-20250514",
    "MCP_METRICS_ARN": "<metrics_runtime_arn>",
    "MCP_GUARDRAILS_ARN": "<guardrails_runtime_arn>",
    "OPENSEARCH_ENDPOINT": "<endpoint>",
    "REDIS_ENDPOINT": "<endpoint>"
  }'
```

## Step 5: Deploy Agents to AgentCore

```bash
# Campaign Orchestrator (main agent)
cd agents/orchestrator
pip install -r requirements.txt
agentcore configure -e campaign_orchestrator.py --protocol A2A --runtime PYTHON_3_13 -rf requirements.txt
agentcore deploy

# Set environment variables in AgentCore console:
#   SECRET_NAME = campaign-mgmt/agent-config
#   AWS_REGION = us-east-1
#   TOOL_FILTER = campaign_management,reporting,account_management

# Monitoring Agent
cd ../monitoring_agent
agentcore configure -e monitoring_agent.py --protocol A2A --runtime PYTHON_3_13 -rf requirements.txt
agentcore deploy

# Optimization Agent
cd ../optimization_agent
agentcore configure -e optimization_agent.py --protocol A2A --runtime PYTHON_3_13 -rf requirements.txt
agentcore deploy
```

## Step 6: Deploy API Server

```bash
cd api
pip install -r requirements.txt

# Run locally for testing
uvicorn main:app --host 0.0.0.0 --port 8000
# API docs: http://localhost:8000/docs

# For production: deploy to ECS/Fargate or Lambda with API Gateway
```

## Step 7: Verify Deployment

```bash
# Test the orchestrator directly
curl -X POST https://<agentcore-endpoint>/campaign-orchestrator \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the current performance of campaign camp-fitpulse-001?"}'

# Test via API
curl -X POST http://localhost:8000/campaigns \
  -H "Content-Type: application/json" \
  -d '{"raw_text": "Launch a premium fitness tracker campaign. $50,000 budget. Target affluent health-conscious consumers aged 25-55. Achieve $35 CPA.", "submitted_by": "sarah@agency.com"}'

# Check health endpoints
curl http://localhost:8000/health
curl https://<agentcore-endpoint>/campaign-orchestrator/health
```

## Step 8: Load Sample Data (for testing)

```bash
# Insert sample guardrails
psql -h <endpoint> -U campaign_admin -d campaign_mgmt -c "
INSERT INTO guardrails (guardrail_id, campaign_id, guardrail_type, threshold_value, threshold_pct, action_on_breach, is_hard_limit)
VALUES
  ('gr-001', 'camp-fitpulse-001', 'BUDGET_CAP', 50000, NULL, 'block', true),
  ('gr-002', 'camp-fitpulse-001', 'BID_CHANGE_LIMIT', NULL, 0.15, 'block', true),
  ('gr-003', 'camp-fitpulse-001', 'CPA_CEILING', NULL, 2.0, 'block', true),
  ('gr-004', 'camp-fitpulse-001', 'SPEND_RATE', NULL, 0.20, 'escalate', false);
"
```

## Running Locally (Development Mode)

For local development without deploying to AgentCore:

```bash
cd agents/orchestrator
cp .env.example .env
# Edit .env — set AWS credentials and model ID
# MCP ARNs can be left empty (agent will skip MCP tools and use LLM-only mode)

pip install -r requirements.txt
python campaign_orchestrator.py
# Runs on http://localhost:9000
```

## Teardown

```bash
cd infra
cdk destroy --all
```
