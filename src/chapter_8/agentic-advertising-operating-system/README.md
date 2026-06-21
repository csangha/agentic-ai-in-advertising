# Agentic Advertising Operating System — End-to-End Architecture

## What This Is

The production environment that coordinates all advertising AI layers into one continuously learning system. Research informs creative. Creative performance informs optimization. Optimization insights feed back to research. All of it remembers.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 Governance & Audit Layer                      │
│  (Policy enforcement, compliance, immutable audit log)        │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                 System Orchestrator Agent                     │
│  (Campaign lifecycle, feedback routing, error recovery)       │
└──────┬──────────┬──────────┬──────────┬──────────┬──────────┘
       │          │          │          │          │
┌──────▼───┐ ┌───▼────┐ ┌───▼────┐ ┌───▼────┐ ┌───▼──────┐
│ Research │ │Creative│ │Execute │ │Measure │ │Optimize  │
│ (Ch 3)   │ │(Ch 4)  │ │(Ch 5)  │ │(Ch 6)  │ │(Ch 7)    │
└──────────┘ └────────┘ └────────┘ └────────┘ └──────────┘
       │          │          │          │          │
┌──────▼──────────▼──────────▼──────────▼──────────▼──────────┐
│                 SHARED MEMORY (Center of System)              │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐ │
│  │ Brand  │ │Research│ │Creative│ │Execute │ │Measuremnt│ │
│  │ Memory │ │ Memory │ │ Memory │ │ Memory │ │  Memory  │ │
│  └────────┘ └────────┘ └────────┘ └────────┘ └──────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

| Component | File | Purpose |
|-----------|------|---------|
| System Orchestrator | `agents/system_orchestrator.py` | Top-level LangGraph agent coordinating all layers |
| Shared Memory Manager | `services/shared_memory_manager.py` | 5 memory types, grow-only semantics, cross-layer access |
| Campaign Lifecycle | `services/campaign_lifecycle.py` | 7-stage state machine with gate criteria and audit |
| Feedback Loop Registry | `services/feedback_loop_registry.py` | 6 default feedback loops with cooldowns and rate limiting |
| Governance Engine | `services/governance_engine.py` | Policy enforcement, audit logging, compliance queries |

## Campaign Lifecycle

```
RESEARCH → PLANNING → CREATIVE → LAUNCH → ACTIVE → LEARNING → ARCHIVED
```

Each transition has gate criteria (e.g., can't launch without approved creative + guardrails configured).

## Cross-Layer Feedback Loops

| # | Source → Target | Trigger | Action |
|---|-----------------|---------|--------|
| 1 | Measurement → Creative | Creative fatigue detected | Trigger creative refresh |
| 2 | Measurement → Research | Audience shift detected | Update hypotheses |
| 3 | Optimization → Creative | Winning themes identified | Inform next generation |
| 4 | Optimization → Execution | Channel efficiency changed | Adjust allocation |
| 5 | Research → Execution | New trend detected | Test new targeting |
| 6 | Creative → Research | Performance by positioning | Validate strategy hypotheses |

## Shared Memory Types

| Memory | Contents | Updated By |
|--------|----------|------------|
| Brand | Positioning, voice guidelines, compliance rules | Humans (admin) |
| Research | Prior hypotheses, trend histories, competitive evolution | Research agents |
| Creative | Territories, performance matrix, fatigue patterns | Creative learning loop |
| Execution | Bid patterns, anomaly playbooks, platform behaviors | Execution agents |
| Measurement | Attribution calibrations, experiment results, data caveats | Measurement/optimization |

## Correctness Properties

- **Memory Monotonicity**: Shared memory only grows — never deleted without admin action
- **Feedback Attribution**: Every cross-layer influence traceable to specific source
- **State Consistency**: All agents observe same campaign state at any given time
- **Governance Supremacy**: Governance policies override any agent decision
- **Resumability**: After failure, system resumes from last consistent state within 5 minutes

## Sample Data

- `sample_data/sample_campaign_object.json` — Full campaign object showing all layers in ACTIVE stage
