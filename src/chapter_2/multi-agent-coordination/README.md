# Multi-Agent Coordination Architecture

## What This Is

A coordination platform that enables specialized advertising agents to discover each other, exchange structured messages, share state, store institutional memory, and execute coordinated multi-step workflows. Think of it as the "operating system plumbing" that connects all the specialized agents from other chapters.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 Workflow Engine (DAG Executor)                │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              A2A Message Bus (Kafka + AgentCore)              │
│  (Request/Response, Fire-and-Forget, Broadcast)              │
├──────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │Research │  │Creative │  │Execute  │  │Optimize │       │
│  │ Agent   │  │ Agent   │  │ Agent   │  │ Agent   │       │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘       │
└───────┼─────────────┼─────────────┼─────────────┼───────────┘
        │             │             │             │
┌───────▼─────────────▼─────────────▼─────────────▼───────────┐
│                 Shared Memory Layer                           │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌──────────────┐      │
│  │ State  │  │ Event  │  │Vector  │  │ Blackboard   │      │
│  │ Store  │  │  Log   │  │Memory  │  │ (Workspace)  │      │
│  └────────┘  └────────┘  └────────┘  └──────────────┘      │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              MCP Tool Layer (AgentCore)                       │
│  (Platform APIs, Analytics, Creative Tools, Compliance)       │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

| Component | File | Purpose |
|-----------|------|---------|
| Agent Registry | `services/agent_registry.py` | Register agents with capabilities, discover by query, monitor health via heartbeat |
| Message Bus | `services/message_bus.py` | A2A messaging: request/response, broadcast, priority queuing, at-least-once delivery |
| Shared State | `services/shared_state.py` | Namespace-partitioned state with optimistic concurrency control (OCC) |
| Vector Memory | `services/vector_memory.py` | Semantic similarity search using OpenSearch Serverless + Bedrock Titan Embeddings |
| Workflow Engine | `services/workflow_engine.py` | DAG-based multi-agent workflow execution with checkpointing and conditional branching |
| Registry Agent | `agents/registry_agent/` | LangGraph agent managing the registry (deployed on AgentCore) |
| Coordination MCP | `mcp_servers/coordination_server/` | MCP tools: register, discover, send_message, read/write state, search memory |

## How It Works

1. **Agent Registration**: Each agent registers its AgentCard (capabilities, endpoint, tools needed)
2. **Discovery**: Agents find each other by capability ("who can generate creative?") or task
3. **Messaging**: Agents communicate via A2A JSON-RPC (sync for queries, async for tasks)
4. **Shared State**: All agents read/write campaign state through the shared store (OCC prevents conflicts)
5. **Vector Memory**: Past experiences stored as embeddings — agents query "have we seen this before?"
6. **Workflows**: Multi-step processes (trend → creative → compliance → launch) executed as DAGs

## Sample Data

- `sample_data/sample_agent_cards.json` — 5 registered agents with capabilities
- `sample_data/sample_workflow_definition.json` — Trend Response Workflow (4 steps, conditional branching)
