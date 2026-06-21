# Deployment Guide: Pitch Acceleration & War Room

## Prerequisites

- Chapter 1 infrastructure deployed (Aurora, OpenSearch, Redis)
- Python 3.13+, Bedrock model access
- (Optional) API keys for: Google Trends, Reddit, social listening platforms

## Step 1: Deploy Research Orchestrator Agent

```bash
cd agents
pip install -r requirements.txt  # (create if not present: same as Ch1 agent deps)
agentcore configure -e research_orchestrator.py --protocol A2A --runtime PYTHON_3_13
agentcore deploy
# Port 9010
```

## Step 2: Deploy Trend Scout Agent

```bash
cd agents/trend_scout
pip install -r requirements.txt
agentcore configure -e trend_scout_agent.py --protocol A2A --runtime PYTHON_3_13 -rf requirements.txt
agentcore deploy
# Port 9200
```

## Step 3: Configure API Keys

```bash
aws secretsmanager update-secret \
  --secret-id campaign-mgmt/agent-config \
  --secret-string '{
    ...,
    "GOOGLE_TRENDS_KEY": "<optional>",
    "REDDIT_CLIENT_ID": "<your_reddit_app_id>",
    "REDDIT_CLIENT_SECRET": "<your_reddit_secret>"
  }'
```

## Step 4: Submit a Pitch Brief

```bash
# Using sample data
curl -X POST https://<research-orchestrator-endpoint> \
  -H "Content-Type: application/json" \
  -d @sample_data/sample_pitch_brief.json
```

Or as a prompt:
```bash
curl -X POST https://<research-orchestrator-endpoint> \
  -H "Content-Type: application/json" \
  -d '{"prompt": "New pitch brief: FitPulse premium fitness tracker. Competitors: Fitbit, Apple Watch, Garmin. Target: affluent health-conscious 25-55. Key questions: positioning gaps, underserved segments, emerging narratives. Timeline: 10 days, URGENT."}'
```

## Running Locally

```bash
cd agents
python research_orchestrator.py  # Port 9010

cd agents/trend_scout
python trend_scout_agent.py  # Port 9200
```

## Expected Output

Within 48 hours (or immediately in simulation mode), you'll receive:
1. Ranked opportunity statements with confidence scores
2. Positioning hypotheses for top 3 opportunities
3. Evidence package with source citations
