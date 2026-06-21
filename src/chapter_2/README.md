# Chapter 2: Understanding Agentic AI — Technology and Capabilities

## Purpose

Chapter 2 establishes the technical foundations that make agentic advertising possible: how agents communicate with each other (A2A), how they access tools (MCP), how they maintain shared state, and how organizations control how much autonomy to grant. It answers two critical questions:

1. **How do multiple specialized agents coordinate?** (Multi-Agent Coordination)
2. **How much autonomy should agents have?** (AI-in-the-Loop Decision Model)

## Use Cases

| Use Case | Description |
|----------|-------------|
| [Multi-Agent Coordination](./multi-agent-coordination/) | Agent registry, A2A messaging, shared state, vector memory, workflow DAG execution |
| [AI-in-the-Loop Decision Model](./ai-in-the-loop-decision-model/) | Autonomy levels, risk-based decision routing, approval workflows, outcome tracking |

## Key Concepts

- **A2A Protocol**: Agent-to-Agent communication via JSON-RPC (discovery, task delegation, broadcast)
- **MCP Protocol**: Agent-to-Tool communication via standardized schema (tool discovery, invocation, permissions)
- **Shared Memory**: Multiple memory patterns (state store, event log, vector memory, blackboard)
- **Autonomy Spectrum**: 5 levels from fully human-controlled to fully autonomous
- **Bounded Autonomy**: Agents operate freely within defined risk boundaries
- **Decision Routing**: Every action assessed for risk before execution (autonomous vs escalate vs emergency)

## How This Connects to Other Chapters

- Chapter 1 uses these coordination patterns implicitly (orchestrator calling sub-agents)
- Chapters 3-7 deploy specialized agents that register with this coordination system
- Chapter 8 integrates everything through the operating system layer built on these primitives
