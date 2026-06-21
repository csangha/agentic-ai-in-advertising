"""
Network Stack: VPC and networking for the campaign management system.
"""

from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    CfnOutput,
)
from constructs import Construct


class NetworkStack(Stack):
    """Creates the VPC and networking infrastructure."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # VPC with public and private subnets
        self.vpc = ec2.Vpc(
            self, "CampaignMgmtVpc",
            vpc_name="campaign-mgmt-vpc",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
        )

        # Security group for database access
        self.db_security_group = ec2.SecurityGroup(
            self, "DbSecurityGroup",
            vpc=self.vpc,
            description="Security group for Aurora PostgreSQL",
            allow_all_outbound=True,
        )

        # Allow inbound PostgreSQL from private subnets
        self.db_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(5432),
            description="PostgreSQL from VPC",
        )

        # Security group for Redis access
        self.cache_security_group = ec2.SecurityGroup(
            self, "CacheSecurityGroup",
            vpc=self.vpc,
            description="Security group for ElastiCache Redis",
            allow_all_outbound=True,
        )

        self.cache_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(6379),
            description="Redis from VPC",
        )

        # Outputs
        CfnOutput(self, "VpcId", value=self.vpc.vpc_id)
