# Chapter 4: Agentic Creative Systems

## Purpose

Chapter 4 implements a multi-agent creative architecture that mirrors a digital creative department. Instead of one AI generating ads, specialized agents handle different phases: concept exploration, copy generation, visual direction, compliance checking, and production scaling — coordinated by a creative orchestrator with human checkpoints at key decision points.

## Use Cases

| Use Case | Description |
|----------|-------------|
| [Multi-Agent Creative Architecture](./multi-agent-creative-architecture/) | Concept → Copy → Visual → Compliance → Production pipeline with learning loop |

## Key Concepts

- **Creative Territories**: High-level conceptual directions (not final ads) — diverse and ranked
- **Brand Voice RAG**: Generated copy checked against brand exemplars via embedding similarity
- **Diversity Enforcement**: No two territories with embedding similarity > 0.85
- **Human Checkpoints**: Creative Director reviews after concept generation and before production
- **Creative Learning Loop**: Performance data feeds back to inform future concept generation
- **Production Scaling**: One approved concept → 50+ format variations in 30 minutes
