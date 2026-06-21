# Multi-Agent Creative Architecture

## What This Is

A multi-agent system that replicates and augments a creative department's workflow. Multiple specialized agents collaborate on the creative process, with the machine handling exploration and production while humans focus on judgment and storytelling.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│           Creative Director (Human Checkpoints)          │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│           Creative Orchestrator Agent                     │
│  (Workflow: Brief → Concept → Copy+Visual → Comply →     │
│   Approve → Production → Learn)                          │
└────┬──────────┬──────────┬──────────┬───────────────────┘
     │          │          │          │
┌────▼────┐ ┌──▼────┐ ┌───▼───┐ ┌───▼─────┐
│Concept  │ │ Copy  │ │Visual │ │Compli-  │
│Explorer │ │  Gen  │ │Concept│ │ ance    │
└─────────┘ └───────┘ └───────┘ └─────────┘
     │          │          │          │
┌────▼──────────▼──────────▼──────────▼───────────────────┐
│           Brand Knowledge Layer (OpenSearch RAG)          │
│  (Voice guidelines, past campaigns, performance data)     │
└─────────────────────────────────────────────────────────┘
```

## Key Components

| Component | File | Purpose |
|-----------|------|---------|
| Creative Orchestrator | `agents/creative_orchestrator.py` | Coordinates the full creative workflow |
| Concept Generator | `services/concept_generator.py` | Generates 10+ diverse territories with novelty scoring |
| Brand Voice Checker | `services/brand_voice_checker.py` | Embedding similarity against brand exemplars (min 0.7) |
| Compliance Checker | `services/compliance_checker.py` | FTC rules, platform policies, brand restrictions |
| Fatigue Detector | `services/creative_fatigue_detector.py` | CTR decline >20% from peak + frequency > 3.5 |

## Workflow

1. **Brief Input** → product, audience, tone, positioning, platforms
2. **Concept Exploration** → 10+ territories (diverse, ranked by resonance + novelty)
3. **🙋 Human Checkpoint** → Creative Director selects 2-3 territories
4. **Copy Generation** → 20+ variants per territory (brand voice enforced)
5. **Visual Concepts** → Mood boards, scene compositions, platform-specific formats
6. **Compliance Gate** → Every variant checked (pass/block with alternatives)
7. **🙋 Human Checkpoint** → CD approves final direction
8. **Production Scaling** → 50+ format variations (display, social, video, email)
9. **Performance Learning** → Results feed back into future concept generation

## Correctness Properties

- No variant reaches production with brand voice score < 0.7
- No variant bypasses compliance checking
- No two territories have embedding similarity > 0.85 (diversity guaranteed)
- Every production asset traces back to an approved territory (complete lineage)

## Sample Data

- `sample_data/sample_creative_brief.json` — FitPulse Pro creative brief with platform and format requirements
