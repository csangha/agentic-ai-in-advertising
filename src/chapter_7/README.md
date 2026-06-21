# Chapter 7: Optimization, Attribution & Incrementality

## Purpose

Chapter 7 addresses the hardest problem in advertising: knowing whether what you did actually changed anything that mattered. It combines fast tactical optimization with causal truth — ensuring the system doesn't just optimize confidently against reporting artifacts, but learns which actions genuinely create business value.

## Use Cases

| Use Case | Description |
|----------|-------------|
| [Optimization, Attribution & Incrementality](./optimization-attribution-incrementality/) | Three-loop optimization (fast/interpretive/causal), 5 attribution models, incrementality experiments |

## Key Concepts

- **Three-Loop Architecture**: Fast (15-min bids), Interpretive (daily attribution), Causal (monthly experiments)
- **Attribution ≠ Causation**: Attribution models are useful stories, not final truth
- **Incrementality**: The only way to know if advertising caused the outcome (not just correlated with it)
- **Loop Authority**: Causal > Interpretive > Fast (higher loops override lower when they conflict)
- **Evidence Decay**: Old incrementality results carry less weight over time
