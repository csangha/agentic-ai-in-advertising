# Autonomous Campaign Execution

## What This Is

The execution layer managing live campaigns through continuous 15-minute optimization cycles. Handles bid management, budget pacing, creative rotation, anomaly detection/response, and cross-platform coordination.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│        Execution Agent (15-min cycle)                  │
│  FETCH → DETECT → PACE → OPTIMIZE → CHECK → EXECUTE  │
└────┬──────────┬──────────┬──────────┬────────────────┘
     │          │          │          │
┌────▼────┐ ┌──▼────┐ ┌───▼───┐ ┌───▼─────────┐
│  Bid    │ │Pacing │ │Creatve│ │Cross-Platform│
│ Manager │ │Engine │ │Rotator│ │ Coordinator  │
└─────────┘ └───────┘ └───────┘ └─────────────┘
     │          │          │          │
     ▼          ▼          ▼          ▼
┌──────────────────────────────────────────────────────┐
│    Platform APIs (Meta, Google, Amazon, TikTok)       │
└──────────────────────────────────────────────────────┘
```

## Key Components

| Component | File | Purpose |
|-----------|------|---------|
| Execution Agent | `agents/execution_agent.py` | Main LangGraph agent running the 15-min cycle |
| Bid Manager | `services/bid_manager.py` | Target CPA strategy, ±15% bounds, time-of-day multipliers |
| Creative Rotator | `services/creative_rotator.py` | Fatigue detection, queue management, min 2 active enforcement |
| Cross-Platform Coordinator | `services/cross_platform_coordinator.py` | Unified view, budget shifting, overlap/frequency management |

## The 15-Minute Cycle

Every 15 minutes:
1. **FETCH** — Pull latest metrics from all platforms
2. **DETECT** — Check for anomalies (Z-score >2σ, rate-of-change >50%/hr)
3. **PACE** — Verify budget delivery is within 80-120% of expected
4. **OPTIMIZE** — Compute bid/budget recommendations
5. **CHECK** — Every proposed change passes through guardrails
6. **EXECUTE** — Apply approved changes via platform APIs
7. **LOG** — Record every decision with full reasoning

## Safety Properties

- Total spend NEVER exceeds budget cap (hard stop)
- Daily spend stays within 80-120% of planned allocation
- No ad set runs with fewer than 2 active creatives
- CRITICAL anomalies trigger protective action within 5 minutes

## Sample Data

- `sample_data/sample_campaign_metrics.json` — 24h metrics across 4 platforms with target CPA $35
