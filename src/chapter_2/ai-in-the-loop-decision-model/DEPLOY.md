# Deployment Guide: AI-in-the-Loop Decision Model

## Prerequisites

- Chapter 1 infrastructure deployed (Aurora, Redis)
- Python 3.13+, Bedrock model access

## Step 1: Deploy Routing Agent

```bash
cd agents/routing_agent
pip install -r requirements.txt
agentcore configure -e routing_agent.py --protocol A2A --runtime PYTHON_3_13 -rf requirements.txt
agentcore deploy

# Set environment variables:
#   SECRET_NAME = campaign-mgmt/agent-config
#   AWS_REGION = us-east-1
```

## Step 2: Configure Autonomy Policies

Policies are defined in `services/decision_router.py`. For custom policies per client, update the database or pass custom policies at initialization.

## Step 3: Test Decision Routing

```bash
# Test autonomous routing (low risk, high confidence)
curl -X POST https://<routing-agent-endpoint> \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Route decision: bid change -8% on TikTok for camp-fitpulse-001. Confidence 0.82, magnitude 0.04, reversibility 0.9"}'

# Test escalation (low confidence)
curl -X POST https://<routing-agent-endpoint> \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Route decision: reallocate $8000 from TikTok to Meta. Confidence 0.55, magnitude 0.35"}'
```

## Step 4: Set Up Approval Notifications

Configure Slack/email notifications in the approval queue:
```bash
# Update secrets with notification config
aws secretsmanager update-secret \
  --secret-id campaign-mgmt/agent-config \
  --secret-string '{"SLACK_WEBHOOK": "https://hooks.slack.com/...", ...}'
```

## Running Locally

```bash
cd agents/routing_agent
python routing_agent.py  # Port 9110
```

## Running Tests

```bash
pytest tests/test_decision_router.py -v
```
