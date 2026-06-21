"""
Database Stack: Aurora PostgreSQL Serverless v2 for campaign management.

Stores:
- Campaign state and lifecycle
- Audit log (immutable append-only)
- Performance metrics (TimescaleDB hypertables)
- Guardrail configurations
- Decision history
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    aws_rds as rds,
    aws_ec2 as ec2,
    CfnOutput,
)
from constructs import Construct


class DatabaseStack(Stack):
    """Aurora PostgreSQL Serverless v2 with TimescaleDB support."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Aurora PostgreSQL Serverless v2 cluster
        self.cluster = rds.DatabaseCluster(
            self, "CampaignDb",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_15_4,
            ),
            default_database_name="campaign_mgmt",
            credentials=rds.Credentials.from_generated_secret(
                "campaign_admin",
                secret_name="campaign-mgmt/db-credentials",
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
            ),
            serverless_v2_min_capacity=0.5,
            serverless_v2_max_capacity=8,
            writer=rds.ClusterInstance.serverless_v2(
                "Writer",
                auto_minor_version_upgrade=True,
            ),
            readers=[
                rds.ClusterInstance.serverless_v2(
                    "Reader",
                    scale_with_writer=True,
                ),
            ],
            storage_encrypted=True,
            backup=rds.BackupProps(retention=Duration.days(7)),
            removal_policy=RemovalPolicy.SNAPSHOT,
            deletion_protection=False,  # Set True for production
        )

        # Outputs
        CfnOutput(
            self, "ClusterEndpoint",
            value=self.cluster.cluster_endpoint.hostname,
            description="Aurora PostgreSQL cluster endpoint",
        )
        CfnOutput(
            self, "ClusterReaderEndpoint",
            value=self.cluster.cluster_read_endpoint.hostname,
            description="Aurora PostgreSQL reader endpoint",
        )
        CfnOutput(
            self, "SecretArn",
            value=self.cluster.secret.secret_arn,
            description="Database credentials secret ARN",
        )
