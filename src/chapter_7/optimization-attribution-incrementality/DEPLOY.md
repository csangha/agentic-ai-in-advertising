# Deployment Guide: Optimization, Attribution & Incrementality

## Prerequisites

- Chapter 1 + Chapter 6 infrastructure deployed (Aurora, measurement tables populated)
- Python 3.13+, Bedrock model access
- Historical campaign data (for attribution models)

## Step 1: Deploy Optimization Policy Agent

```bash
cd agents
pip install -r requirements.txt
agentcore configure -e optimization_policy_agent.py --protocol A2A --runtime PYTHON_3_13 -rf requirements.txt
agentcore deploy
# Port 9300
```

## Step 2: Initialize Default Policies

```bash
python -c "
from services.causal_policy_engine import CausalPolicyEngine
engine = CausalPolicyEngine()
# Initialize with default equal weights (no causal evidence yet)
policy = engine.get_default_policy('meta')
print(f'Meta policy: attr_weight={policy.attribution_weight}, causal_weight={policy.causal_weight}')
"
```

## Step 3: Run Attribution Models

```bash
python -c "
from services.attribution_service import AttributionService, Touchpoint, AttributionModel
from datetime import datetime, timedelta

svc = AttributionService()
# Sample path: user saw Meta ad, then Google search, then purchased
touchpoints = [
    Touchpoint('meta', 'meta', datetime(2026,1,15,10,0), 'impression', 'camp-meta-001'),
    Touchpoint('meta', 'meta', datetime(2026,1,16,14,0), 'click', 'camp-meta-001'),
    Touchpoint('google', 'google', datetime(2026,1,18,9,0), 'click', 'camp-google-001'),
    Touchpoint('amazon', 'amazon', datetime(2026,1,18,20,0), 'click', 'camp-amazon-001'),
]

# Run all models
results = svc.compute_all_models(touchpoints)
for r in results:
    print(f'{r.model.value}: {r.channel_contributions}')

# Check divergence
divergence = svc.compute_divergence(results)
print(f'Divergence (channels needing experiments): {divergence}')
"
```

## Step 4: Design an Incrementality Experiment

```bash
curl -X POST https://<optimization-policy-agent> \
  -d '{"prompt": "Design a geo-based incrementality experiment for Meta. Hypothesis: Meta upper-funnel drives 15% incremental lift. Treatment regions: NY, LA, CHI. Control: PHI, HOU, PHX. Duration: 28 days."}'
```

## Step 5: Ingest Experiment Results

```bash
# Load sample experiment result
curl -X POST https://<optimization-policy-agent> \
  -d @sample_data/sample_experiment_result.json
```

Or directly update the policy:
```bash
python -c "
from services.causal_policy_engine import CausalPolicyEngine, CausalEvidence
engine = CausalPolicyEngine()
evidence = CausalEvidence(
    channel='meta', source='geo_experiment',
    incremental_lift_pct=15.0, confidence=0.95,
    confidence_interval=(0.08, 0.22)
)
engine.ingest_evidence(evidence)
print('Policy updated with Meta incrementality evidence')
"
```

## Step 6: Test Three-Loop Decision

```bash
curl -X POST https://<optimization-policy-agent> \
  -d '{"prompt": "Given that Meta has proven 15% incremental lift and Google attribution looks strong but has no experiment yet — how should I allocate budget between them? Current spend: Meta $1200/day, Google $890/day."}'
```

## Running Locally

```bash
python agents/optimization_policy_agent.py  # Port 9300
```

## Key Principle

> Attribution tells you who gets credit. Incrementality tells you if the business changed because of the marketing at all.

The system uses attribution for fast directional decisions but NEVER treats it as causal proof. Only incrementality experiments can modify the causal policy.
