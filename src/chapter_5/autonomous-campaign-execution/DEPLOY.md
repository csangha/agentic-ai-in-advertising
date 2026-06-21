# Deployment Guide: Autonomous Campaign Execution

## Prerequisites

- Chapter 1 infrastructure deployed (Aurora + TimescaleDB, Redis)
- MCP servers deployed (Metrics, Guardrails) from Chapter 1
- Python 3.13+, Bedrock model access
- Platform API credentials (Meta, Google, Amazon Ads, TikTok) in Secrets Manager

## Step 1: Deploy Execution Agent

```bash
cd agents
agentcore configure -e execution_agent.py --protocol A2A --runtime PYTHON_3_13
agentcore deploy
# Port 9030

# Set environment variables:
#   SECRET_NAME = campaign-mgmt/agent-config
#   AWS_REGION = us-east-1
```

## Step 2: Configure Platform Credentials

Ensure all platform credentials are in Secrets Manager:
```bash
# Meta
aws secretsmanager update-secret --secret-id campaign-mgmt/meta-ads-credentials ...
# Google
aws secretsmanager update-secret --secret-id campaign-mgmt/google-ads-credentials ...
# TikTok
aws secretsmanager update-secret --secret-id campaign-mgmt/tiktok-ads-credentials ...
# Amazon Ads (if not already done in Ch1)
aws secretsmanager update-secret --secret-id campaign-mgmt/amazon-ads-credentials ...
```

## Step 3: Start Optimization Cycles

The execution agent runs 15-minute cycles. Trigger manually or set up scheduling:

```bash
# Manual trigger
curl -X POST https://<execution-agent-endpoint> \
  -d '{"prompt": "Run optimization cycle for campaign camp-fitpulse-001"}'

# For continuous operation: use EventBridge to invoke every 15 minutes
aws events put-rule --name "execution-cycle" --schedule-expression "rate(15 minutes)"
```

## Step 4: Test with Sample Data

```bash
# Load sample metrics and test the optimization logic
curl -X POST https://<execution-agent-endpoint> \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Analyze these metrics and recommend optimizations: Meta CPA $34.28, Google CPA $35.60, Amazon CPA $37.50, TikTok CPA $50.08. Target CPA is $35."}'
```

## Step 5: Monitor Execution

```bash
# Check what the agent has done
curl -X POST https://<execution-agent-endpoint> \
  -d '{"prompt": "Show me all actions taken in the last 24 hours for camp-fitpulse-001"}'

# Check pacing
curl -X POST https://<execution-agent-endpoint> \
  -d '{"prompt": "What is the pacing status for camp-fitpulse-001?"}'
```

## Running Locally

```bash
python agents/execution_agent.py  # Port 9030
```

## Safety Notes

- The agent ALWAYS checks guardrails before executing
- CRITICAL anomalies trigger automatic protective action within 5 minutes
- All actions are logged to the immutable audit trail
- Budget cap is a hard stop — cannot be exceeded under any circumstance
