# Optimization, Attribution & Incrementality

## What This Is

A causally-aware optimization system operating at three speeds:
- **Fast Loop** (15 min) — tactical bid/budget adjustments from observed metrics
- **Interpretive Loop** (daily) — attribution-weighted channel allocation
- **Causal Loop** (monthly) — incrementality experiments that correct the system when attribution misleads

## Architecture

```
┌──────────────────────────────────────────────────────┐
│           Optimization Policy Engine                  │
│  effective_score = efficiency × attr_weight           │
│                  + causal_modifier × causal_weight    │
└────────┬────────────────┬─────────────────┬──────────┘
         │                │                 │
┌────────▼──────┐ ┌──────▼───────┐ ┌───────▼───────┐
│  Fast Loop    │ │ Interpretive │ │ Causal Loop   │
│  (15 min)     │ │ (daily)      │ │ (monthly)     │
│  bids/pacing  │ │ attribution  │ │ experiments   │
│               │ │ allocation   │ │ policy update │
└───────────────┘ └──────────────┘ └───────────────┘
         │                │                 │
         ▼                ▼                 ▼
┌──────────────────────────────────────────────────────┐
│           Measurement Foundation (Chapter 6)          │
└──────────────────────────────────────────────────────┘
```

## Key Components

| Component | File | Purpose |
|-----------|------|---------|
| Attribution Service | `services/attribution_service.py` | 5 models (last-click, first-click, linear, time-decay, data-driven) + divergence analysis |
| Experiment Service | `services/experiment_service.py` | Design, assignment, integrity, lift computation |
| Causal Policy Engine | `services/causal_policy_engine.py` | Effective scores, evidence decay, policy updates |
| Optimization Agent | `agents/optimization_policy_agent.py` | LangGraph agent for causally-aware decisions |

## The Three Loops

| Loop | Speed | Inputs | Decisions | Authority |
|------|-------|--------|-----------|-----------|
| Fast | 15 min | Observed metrics | Bid adjustments, pacing | Lowest |
| Interpretive | Daily | Attribution results | Channel budget allocation | Medium |
| Causal | Monthly | Experiment results | Policy weights, floors/ceilings | Highest |

## Attribution Models

All labeled as "directional estimates" — never presented as causal proof:
1. **Last-click** — 100% credit to final touchpoint
2. **First-click** — 100% credit to first touchpoint
3. **Linear** — Equal credit to all touchpoints
4. **Time-decay** — More credit to recent (exponential with 24h half-life)
5. **Data-driven** — Shapley value approximation (interaction-weighted)

## Incrementality Testing

- **Holdout tests** — Suppress ads to a control group, measure lift
- **Geo tests** — Suppress in some regions, compare to control regions
- **Synthetic controls** — Statistical counterfactual estimation

Results are stored as "causal evidence" with confidence intervals and decay over time.

## Sample Data

- `sample_data/sample_experiment_result.json` — Geo suppression experiment showing Meta drives 15% incremental lift
