#!/usr/bin/env python3
"""
CDK Application for Chapter 2: Multi-Agent Coordination

Deploys coordination infrastructure:
- References Ch1 shared state (Aurora PostgreSQL)
- References Ch1 OpenSearch (vector memory)
- References Ch1 Redis (distributed cache/locks)
- MSK Serverless (Kafka) for event bus / message bus
"""

import aws_cdk as cdk
from stacks.kafka_stack import KafkaStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account") or None,
    region=app.node.try_get_context("region") or "us-east-1",
)

# Kafka (MSK Serverless) for multi-agent event bus
kafka = KafkaStack(app, "MultiAgentCoord-Kafka", env=env)

app.synth()
