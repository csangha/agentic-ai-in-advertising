"""
MSK Serverless Stack — event bus for multi-agent coordination.

Provides a Kafka cluster for agent-to-agent messaging, workflow events,
and state change notifications. Uses MSK Serverless for zero-management scaling.
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
    aws_ec2 as ec2,
    aws_msk as msk,
    aws_iam as iam,
    aws_logs as logs,
)
from constructs import Construct


class KafkaStack(Stack):
    """MSK Serverless cluster for the multi-agent event bus."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # VPC for MSK
        self.vpc = ec2.Vpc(
            self, "CoordinationVpc",
            max_azs=3,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
            ],
        )

        # Security group for MSK
        self.msk_sg = ec2.SecurityGroup(
            self, "MskSecurityGroup",
            vpc=self.vpc,
            description="Security group for MSK Serverless cluster",
            allow_all_outbound=True,
        )

        # Allow inbound Kafka traffic within VPC
        self.msk_sg.add_ingress_rule(
            ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            ec2.Port.tcp_range(9092, 9098),
            "Kafka broker ports from VPC",
        )

        # MSK Serverless Cluster
        self.cluster = msk.CfnServerlessCluster(
            self, "CoordinationEventBus",
            cluster_name="agent-coordination-bus",
            client_authentication=msk.CfnServerlessCluster.ClientAuthenticationProperty(
                sasl=msk.CfnServerlessCluster.SaslProperty(
                    iam=msk.CfnServerlessCluster.IamProperty(enabled=True),
                ),
            ),
            vpc_configs=[
                msk.CfnServerlessCluster.VpcConfigProperty(
                    subnet_ids=[
                        subnet.subnet_id
                        for subnet in self.vpc.private_subnets
                    ],
                    security_groups=[self.msk_sg.security_group_id],
                ),
            ],
        )

        # IAM policy for agents to produce/consume
        self.agent_kafka_policy = iam.ManagedPolicy(
            self, "AgentKafkaPolicy",
            statements=[
                iam.PolicyStatement(
                    actions=[
                        "kafka-cluster:Connect",
                        "kafka-cluster:DescribeCluster",
                    ],
                    resources=[self.cluster.attr_arn],
                ),
                iam.PolicyStatement(
                    actions=[
                        "kafka-cluster:CreateTopic",
                        "kafka-cluster:DescribeTopic",
                        "kafka-cluster:WriteData",
                        "kafka-cluster:ReadData",
                    ],
                    resources=[
                        f"{self.cluster.attr_arn}/*",
                    ],
                ),
            ],
        )

        # Outputs
        CfnOutput(self, "ClusterArn", value=self.cluster.attr_arn)
        CfnOutput(self, "AgentKafkaPolicyArn", value=self.agent_kafka_policy.managed_policy_arn)
