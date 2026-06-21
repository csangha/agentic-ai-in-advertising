"""
Cache Stack: ElastiCache Redis for real-time state and inter-agent messaging.

Used for:
- Campaign hot state (current metrics, pacing status)
- Agent rate limiting (token bucket per platform)
- Inter-agent message passing (Redis Streams)
- Temporary locks for optimistic concurrency
"""

from aws_cdk import (
    Stack,
    aws_elasticache as elasticache,
    aws_ec2 as ec2,
    CfnOutput,
)
from constructs import Construct


class CacheStack(Stack):
    """ElastiCache Redis Serverless for campaign management."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Subnet group for Redis
        private_subnet_ids = [
            subnet.subnet_id
            for subnet in vpc.select_subnets(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ).subnets
        ]

        subnet_group = elasticache.CfnSubnetGroup(
            self, "RedisSubnetGroup",
            description="Subnet group for campaign management Redis",
            subnet_ids=private_subnet_ids,
            cache_subnet_group_name="campaign-mgmt-redis-subnets",
        )

        # Security group for Redis
        redis_sg = ec2.SecurityGroup(
            self, "RedisSG",
            vpc=vpc,
            description="Security group for campaign management Redis",
            allow_all_outbound=True,
        )

        redis_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(6379),
            description="Redis access from VPC",
        )

        # ElastiCache Redis Serverless
        self.redis = elasticache.CfnServerlessCache(
            self, "CampaignRedis",
            engine="redis",
            serverless_cache_name="campaign-mgmt-cache",
            description="Redis cache for campaign management agents",
            major_engine_version="7",
            cache_usage_limits=elasticache.CfnServerlessCache.CacheUsageLimitsProperty(
                data_storage=elasticache.CfnServerlessCache.DataStorageProperty(
                    maximum=5,
                    minimum=1,
                    unit="GB",
                ),
                ecpu_per_second=elasticache.CfnServerlessCache.ECPUPerSecondProperty(
                    maximum=5000,
                    minimum=1000,
                ),
            ),
            security_group_ids=[redis_sg.security_group_id],
            subnet_ids=private_subnet_ids,
        )

        # Outputs
        CfnOutput(
            self, "RedisEndpoint",
            value=self.redis.attr_endpoint_address,
            description="Redis serverless endpoint",
        )
