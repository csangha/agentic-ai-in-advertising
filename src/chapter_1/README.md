# Chapter 1: The Dawn of Agentic Intelligence

## Purpose

Chapter 1 introduces the foundational concept of agentic AI in advertising through a concrete scenario: Sarah Wang, a marketing manager, provides a high-level campaign brief on a Friday evening. By Monday morning, the AI system has autonomously launched campaigns across four platforms, optimized bids, detected trending conversations, generated new creative variants, and shifted budget toward winning segments — all within defined guardrails.

This chapter implements that vision as a fully deployable system.

## Use Cases

| Use Case | Description |
|----------|-------------|
| [Autonomous Campaign Management](./autonomous-campaign-management/) | End-to-end autonomous campaign system that interprets briefs, launches across platforms, monitors performance, optimizes in real-time, and reports decisions |

## Key Concepts Introduced

- **Agentic Loop**: Observe → Reason → Act → Evaluate → Repeat
- **Bounded Rationality**: Making satisfactory decisions under constraints of limited information
- **Guardrails**: Hard safety boundaries that autonomous agents cannot exceed
- **Closed-Loop Feedback**: Continuous measurement against objectives with dynamic correction
- **Goal Pursuit Under Constraints**: The defining characteristic of agentic intelligence

## Technology Foundation

This chapter establishes the core technology stack used across all subsequent chapters:

- **Amazon Bedrock AgentCore** — Agent deployment and runtime
- **LangGraph** — Agent orchestration framework
- **Claude on Bedrock** — Reasoning engine (via `ChatBedrock`)
- **MCP Protocol** — Standardized tool integration
- **A2A Protocol** — Agent-to-agent communication
- **Aurora PostgreSQL** — Structured data and time-series metrics
- **Amazon OpenSearch Serverless** — Vector search for experience memory
- **ElastiCache Redis** — Real-time state and inter-agent messaging

## Reading Order

Start here if you want to understand the complete system. This chapter contains the most detailed implementation (CDK infrastructure, all agents, MCP servers, services, API, tests, and sample data) and serves as the template for all subsequent chapters.
