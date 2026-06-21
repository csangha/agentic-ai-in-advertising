# AI-in-the-Loop Decision Model

## What This Is

An autonomy management system that dynamically routes advertising decisions between AI agents and human operators. Instead of "fully autonomous" or "fully human-controlled," this implements a spectrum where risk, reversibility, confidence, and track record determine who decides.

## Architecture

```
┌──────────────────────────────────────────────────┐
│            Human Review Interface                  │
│  (Approval Queue, Mobile Notifications, Batch)    │
└────────────────────┬─────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────┐
│            Decision Routing Engine                 │
│  Risk Score = magnitude × (1-reversibility)       │
│              × (1-confidence) × novelty           │
└────────┬───────────────────────────────┬─────────┘
         │                               │
         ▼                               ▼
┌────────────────┐             ┌─────────────────┐
│  AUTONOMOUS    │             │   ESCALATE      │
│  (proceed)     │             │   (queue for    │
│                │             │    human)       │
└────────┬───────┘             └────────┬────────┘
         │                               │
         ▼                               ▼
┌────────────────────────────────────────────────────┐
│            Outcome Tracker                          │
│  (quality scores, calibration, autonomy adjustment) │
└────────────────────────────────────────────────────┘
```

## Key Components

| Component | File | Purpose |
|-----------|------|---------|
| Decision Router | `services/decision_router.py` | Computes risk score, resolves authority (autonomous/escalate/emergency) |
| Approval Queue | `services/approval_queue.py` | SLA-enforced queue with priority, batch approval, timeout defaults |
| Outcome Tracker | `services/outcome_tracker.py` | Records outcomes, computes quality scores, recommends autonomy changes |
| Routing Agent | `agents/routing_agent/` | LangGraph agent wrapping the routing logic for A2A access |

## Decision Routing Logic

```
Risk Score = magnitude × (1 - reversibility) × (1 - confidence) × novelty_factor

If risk > threshold OR confidence < minimum → ESCALATE
If function = "crisis" OR risk > 0.9 → EMERGENCY
Otherwise → AUTONOMOUS
```

## Autonomy Levels

| Level | Meaning | Example |
|-------|---------|---------|
| 1 | Human decides entirely | Crisis response, brand repositioning |
| 2 | Agent recommends, human approves | Large budget shifts, messaging changes |
| 3 | Agent acts within narrow bounds, human monitors | Bid adjustments ±25%, audience tests |
| 4 | Agent acts freely, human alerted on patterns | Bid adjustments ±10%, creative pausing |
| 5 | Fully autonomous | (Rarely used in practice) |

## Sample Data

- `sample_data/sample_decision_requests.json` — 3 example decisions showing autonomous, escalation, and emergency routing
