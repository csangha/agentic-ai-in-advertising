# Pitch Acceleration & Competitive War Room

## What This Is

When an agency receives a new business pitch brief, this system activates parallel research agents that scan markets, map competitors, analyze sentiment, and synthesize findings — compressing 7-14 days of research into 48 hours.

## How It Works

```
Pitch Brief Submitted
        │
        ▼
┌───────────────────────┐
│ Research Orchestrator  │ (coordinates all agents)
└───┬───────┬───────┬───┘
    │       │       │
    ▼       ▼       ▼
┌──────┐ ┌──────┐ ┌──────┐
│Trend │ │Comp  │ │Senti-│   ← Run in PARALLEL
│Scout │ │Intel │ │ment  │
└──┬───┘ └──┬───┘ └──┬───┘
   │        │        │
   ▼        ▼        ▼
┌───────────────────────┐
│   Synthesis Agent     │ (cross-references, scores, ranks)
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ Ranked Opportunities  │
│ + Positioning Hypos   │
│ + Evidence Package    │
└───────────────────────┘
```

## Key Components

| Component | File | Purpose |
|-----------|------|---------|
| Research Orchestrator | `agents/research_orchestrator.py` | Activates agents, tracks progress, triggers synthesis |
| Trend Scout Agent | `agents/trend_scout/trend_scout_agent.py` | Search/social trend detection with velocity scoring |
| Trend Detector | `services/trend_detector.py` | Velocity computation, spike vs structural classification |
| Competitive Intel | `services/competitive_intel.py` | Creative classification, messaging shift detection |
| Sentiment Analyzer | `services/sentiment_analyzer.py` | 3-model ensemble with majority voting for accuracy |

## Output

After 48 hours, the system delivers:
1. **Ranked Opportunity Statements** — scored by market velocity × competitive gap × brand fit
2. **Positioning Hypotheses** — 3 strategic directions grounded in evidence
3. **Evidence Package** — stats, consumer quotes, trend charts, competitive examples (all with citations)

## Sample Data

- `sample_data/sample_pitch_brief.json` — FitPulse premium fitness tracker pitch brief
