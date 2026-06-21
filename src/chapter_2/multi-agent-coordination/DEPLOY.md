# Deployment Guide: Multi-Agent Coordination

## Prerequisites

- Chapter 1 infrastructure deployed (Aurora, OpenSearch, Redis)
- AWS CDK CLI, Python 3.13+
- Bedrock model access enabled

## Step 1: Deploy Additional Infrastructure (Kafka)

```bash
cd infra
pip install -r requirements.txt
cdk deploy --all
```

This adds MSK Serverless (Kafka) for the event bus on top of Chapter 1's shared infra.

## Step 2: Deploy Coordination MCP Server

```bash
cd mcp_servers/coordination_server
pip install -r requirements.txt
agentcore configure -e coordination_mcp_server.py --protocol MCP --runtime PYTHON_3_13 -rf requirements.txt
agentcore deploy
# Note the Runtime ARN
```

## Step 3: Deploy Registry Agent

```bash
cd agents/registry_agent
pip install -r requirements.txt
agentcore configure -e registry_agent.py --protocol A2A --runtime PYTHON_3_13 -rf requirements.txt
agentcore deploy

# Set environment variables:
#   SECRET_NAME = campaign-mgmt/agent-config
#   AWS_REGION = us-east-1
```

## Step 4: Register Agents

Once the registry agent is running, register all other agents:

```bash
curl -X POST https://<registry-agent-endpoint> \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Register agent: Campaign Orchestrator, capabilities: campaign_management, endpoint: arn:aws:bedrock-agentcore:us-east-1:123:runtime/campaign-orchestrator"}'
```

Or use the sample data:
```bash
# Load sample agent cards for testing
cat sample_data/sample_agent_cards.json
```

## Step 5: Test Workflow Execution

```bash
# Submit a workflow definition
curl -X POST https://<registry-agent-endpoint> \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Execute workflow: trend-response for campaign camp-fitpulse-001. Trend: fitness accountability partners, velocity: 340%"}'
```

## Running Locally

```bash
cd agents/registry_agent
cp .env.example .env
pip install -r requirements.txt
python registry_agent.py  # Port 9100
```

## Running Tests

```bash
cd tests
pip install pytest
pytest test_agent_registry.py test_shared_state.py test_workflow_engine.py -v
```
