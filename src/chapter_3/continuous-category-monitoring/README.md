# Continuous Category Monitoring

## What This Is

An always-on intelligence system for retained agency clients that replaces quarterly competitive reports with continuous monitoring. The system tracks competitor activity, demand signals, audience shifts, and share-of-voice changes — surfacing proactive alerts when high-confidence opportunities are detected.

## How It Works

```
┌───────────────────────────────────────────┐
│        Scheduled Monitoring Agents         │
│  (Weekly/Daily/Monthly cadences)          │
├───────────┬───────────┬───────────────────┤
│Competitor │  Demand   │   Audience        │
│  Monitor  │  Signal   │   Shift           │
│ (weekly)  │  (daily)  │  (weekly)         │
└─────┬─────┴─────┬─────┴─────┬─────────────┘
      │           │           │
      ▼           ▼           ▼
┌───────────────────────────────────────────┐
│        Alert Engine                        │
│  (convergence detection, scoring,          │
│   rate limiting, deduplication)            │
└─────────────────┬─────────────────────────┘
                  ▼
┌───────────────────────────────────────────┐
│  Proactive Alerts (max 3/week/client)     │
│  → Slack / Email / Dashboard              │
└───────────────────────────────────────────┘
```

## Key Components

| Component | File | Purpose |
|-----------|------|---------|
| Category Monitor Agent | `agents/category_monitor_agent.py` | Main LangGraph agent for monitoring coordination |
| Signal Aggregator | `services/signal_aggregator.py` | Collects and prioritizes signals from all sources |
| Alert Engine | `services/alert_engine.py` | Convergence detection, scoring, rate limiting |

## Alert Triggers

Alerts fire when 2+ independent signals converge:
- Competitor launches product + demand signal rises → **Opportunity alert**
- Competitor shifts messaging + consumer pain point emerges → **Positioning opportunity**
- Demand declining + competitor retrenching → **Market contraction warning**

## Sample Data

- `sample_data/sample_monitor_config.json` — Configuration for monitoring fitness wearables category
