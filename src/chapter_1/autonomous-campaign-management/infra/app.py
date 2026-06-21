#!/usr/bin/env python3
"""
CDK Application for Chapter 1: Autonomous Campaign Management

Deploys the full infrastructure stack:
- Aurora PostgreSQL (with TimescaleDB)
- Amazon OpenSearch Serverless (vector search)
- ElastiCache Redis
- S3 buckets (raw data, assets, audit)
- Secrets Manager
- IAM roles for Bedrock AgentCore agents
"""

import aws_cdk as cdk
from stacks.network_stack import NetworkStack
from stacks.database_stack import DatabaseStack
from stacks.opensearch_stack import OpenSearchStack
from stacks.cache_stack import CacheStack
from stacks.storage_stack import StorageStack
from stacks.secrets_stack import SecretsStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account") or None,
    region=app.node.try_get_context("region") or "us-east-1",
)

# Network foundation
network = NetworkStack(app, "CampaignMgmt-Network", env=env)

# Core infrastructure
database = DatabaseStack(
    app, "CampaignMgmt-Database",
    vpc=network.vpc,
    env=env,
)

opensearch = OpenSearchStack(
    app, "CampaignMgmt-OpenSearch",
    env=env,
)

cache = CacheStack(
    app, "CampaignMgmt-Cache",
    vpc=network.vpc,
    env=env,
)

storage = StorageStack(
    app, "CampaignMgmt-Storage",
    env=env,
)

secrets = SecretsStack(
    app, "CampaignMgmt-Secrets",
    env=env,
)

app.synth()
