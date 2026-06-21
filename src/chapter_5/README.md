# Chapter 5: Campaign Execution — The Campaign as a Living System

## Purpose

Chapter 5 implements the execution layer that manages live campaigns. Unlike traditional advertising where campaigns are static after launch, this system treats campaigns as living organisms — continuously adapting bids, rotating creatives, pacing budgets, and responding to anomalies in real-time.

## Use Cases

| Use Case | Description |
|----------|-------------|
| [Autonomous Campaign Execution](./autonomous-campaign-execution/) | Real-time bid management, pacing, creative rotation, anomaly response, cross-platform coordination |

## Key Concepts

- **15-Minute Optimization Cycles**: The system acts every 15 minutes (not daily or weekly)
- **Campaign as Living System**: Campaigns evolve while running (creative, targeting, budget all shift)
- **Agent Competition**: Your optimization agents compete with other advertisers' agents in auctions
- **Guardrails Before Every Action**: No change executes without passing safety checks
- **Cross-Platform Coordination**: Budget shifts toward best-performing platform in real-time
