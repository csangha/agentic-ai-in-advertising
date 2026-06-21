# Deployment Guide: Multi-Agent Creative Architecture

## Prerequisites

- Chapter 1 infrastructure deployed (Aurora, OpenSearch for brand knowledge RAG)
- Python 3.13+, Bedrock model access
- Bedrock image generation access (Stability AI or Titan Image) — optional for visual concepts

## Step 1: Index Brand Knowledge

Before the creative system can generate on-brand content, load brand guidelines into OpenSearch:

```bash
# Use the brand voice checker to index exemplars
python -c "
from services.brand_voice_checker import BrandVoiceChecker
checker = BrandVoiceChecker()
checker.load_exemplars([
    'Empower your fitness journey with precision tracking that adapts to your life.',
    'FitPulse: where technology meets wellness, designed for the modern athlete.',
    'Track smarter. Train better. Live fully. FitPulse Pro.',
])
print('Brand exemplars indexed.')
"
```

## Step 2: Deploy Creative Orchestrator Agent

```bash
cd agents
agentcore configure -e creative_orchestrator.py --protocol A2A --runtime PYTHON_3_13
agentcore deploy
# Port 9020
```

## Step 3: Submit a Creative Brief

```bash
curl -X POST https://<creative-orchestrator-endpoint> \
  -H "Content-Type: application/json" \
  -d @sample_data/sample_creative_brief.json
```

Or as a prompt:
```bash
curl -X POST https://<creative-orchestrator-endpoint> \
  -d '{"prompt": "Generate creative territories for FitPulse Pro. Target: health-conscious professionals 30-50. Tone: empowering yet approachable. Positioning: the fitness tracker that adapts to your life. Platforms: Meta, Google, TikTok, Amazon."}'
```

## Step 4: Review Territories (Human Checkpoint)

The system generates 10+ concept territories. Review and select:
```bash
curl -X POST https://<creative-orchestrator-endpoint> \
  -d '{"prompt": "I select territories 1 (accountability partner) and 3 (lifestyle integration). Generate 20 copy variations for each."}'
```

## Step 5: Compliance Check

All generated copy automatically passes through compliance. Check results:
```bash
curl -X POST https://<creative-orchestrator-endpoint> \
  -d '{"prompt": "Show compliance check results for the latest generated copy."}'
```

## Running Locally

```bash
python agents/creative_orchestrator.py  # Port 9020
```

## Running Tests

```bash
# Test brand voice checker
python -c "
from services.brand_voice_checker import BrandVoiceChecker
checker = BrandVoiceChecker()
checker.load_exemplars(['Empower your fitness journey with precision.'])
result = checker.check('Track your workouts with cutting-edge technology.')
print(f'Voice score: {result.score}, Passed: {result.passed}')
"
```
