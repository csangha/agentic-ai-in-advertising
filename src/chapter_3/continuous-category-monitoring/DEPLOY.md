# Deployment Guide: Continuous Category Monitoring

## Prerequisites

- Chapter 1 infrastructure deployed
- Python 3.13+, Bedrock model access
- Redis (for scheduling via Celery)

## Step 1: Deploy Category Monitor Agent

```bash
cd agents
agentcore configure -e category_monitor_agent.py --protocol A2A --runtime PYTHON_3_13
agentcore deploy
# Port 9210
```

## Step 2: Configure a Monitor

```bash
# Use sample config
curl -X POST https://<monitor-agent-endpoint> \
  -H "Content-Type: application/json" \
  -d @sample_data/sample_monitor_config.json
```

Or as a prompt:
```bash
curl -X POST https://<monitor-agent-endpoint> \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Set up continuous monitoring for client FitPulse. Category: fitness wearables. Competitors: Fitbit, Apple Watch, Garmin, Whoop, Oura. Keywords: fitness tracker, health wearable, sleep tracking. Max 3 alerts per week."}'
```

## Step 3: Configure Alert Delivery

Set up Slack/email for alerts:
```bash
aws secretsmanager update-secret \
  --secret-id campaign-mgmt/agent-config \
  --secret-string '{..., "SLACK_WEBHOOK": "https://hooks.slack.com/...", "ALERT_EMAIL": "team@agency.com"}'
```

## Step 4: Verify Monitoring

```bash
# Check monitor status
curl -X POST https://<monitor-agent-endpoint> \
  -d '{"prompt": "What is the current status of monitoring for FitPulse?"}'

# Get latest signals
curl -X POST https://<monitor-agent-endpoint> \
  -d '{"prompt": "Show me the top signals detected for FitPulse this week."}'
```

## Running Locally

```bash
python agents/category_monitor_agent.py  # Port 9210
```

## Scheduling

In production, monitoring agents run on schedules:
- Competitor monitor: weekly (full scan), daily (change detection)
- Demand signals: daily
- Audience shifts: weekly
- SOV tracking: monthly

Use Celery + Redis or EventBridge for scheduling.
