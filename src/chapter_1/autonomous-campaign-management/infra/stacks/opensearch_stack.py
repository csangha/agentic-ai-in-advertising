"""
OpenSearch Serverless Stack: Vector search for campaign memory and embeddings.

Used for:
- Campaign experience similarity search
- Brand voice embedding retrieval (RAG)
- Creative performance pattern matching
- Trend similarity matching
"""

from aws_cdk import (
    Stack,
    aws_opensearchserverless as oss,
    aws_iam as iam,
    CfnOutput,
)
from constructs import Construct
import json


class OpenSearchStack(Stack):
    """Amazon OpenSearch Serverless with vector search collection."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        collection_name = "campaign-memory"

        # Encryption policy (required for serverless collections)
        encryption_policy = oss.CfnSecurityPolicy(
            self, "EncryptionPolicy",
            name="campaign-memory-encryption",
            type="encryption",
            policy=json.dumps({
                "Rules": [
                    {
                        "ResourceType": "collection",
                        "Resource": [f"collection/{collection_name}"],
                    }
                ],
                "AWSOwnedKey": True,
            }),
        )

        # Network policy (allow public access for development; restrict in production)
        network_policy = oss.CfnSecurityPolicy(
            self, "NetworkPolicy",
            name="campaign-memory-network",
            type="network",
            policy=json.dumps([
                {
                    "Rules": [
                        {
                            "ResourceType": "collection",
                            "Resource": [f"collection/{collection_name}"],
                        },
                        {
                            "ResourceType": "dashboard",
                            "Resource": [f"collection/{collection_name}"],
                        },
                    ],
                    "AllowFromPublic": True,
                }
            ]),
        )

        # Vector search collection
        self.collection = oss.CfnCollection(
            self, "CampaignMemoryCollection",
            name=collection_name,
            description="Vector search collection for campaign experience memory and RAG",
            type="VECTORSEARCH",
        )

        self.collection.add_dependency(encryption_policy)
        self.collection.add_dependency(network_policy)

        # Data access policy (allow the agent execution roles)
        # In production, restrict to specific IAM roles
        data_access_policy = oss.CfnAccessPolicy(
            self, "DataAccessPolicy",
            name="campaign-memory-access",
            type="data",
            policy=json.dumps([
                {
                    "Rules": [
                        {
                            "ResourceType": "collection",
                            "Resource": [f"collection/{collection_name}"],
                            "Permission": [
                                "aoss:CreateCollectionItems",
                                "aoss:UpdateCollectionItems",
                                "aoss:DescribeCollectionItems",
                                "aoss:DeleteCollectionItems",
                            ],
                        },
                        {
                            "ResourceType": "index",
                            "Resource": [f"index/{collection_name}/*"],
                            "Permission": [
                                "aoss:CreateIndex",
                                "aoss:UpdateIndex",
                                "aoss:DescribeIndex",
                                "aoss:ReadDocument",
                                "aoss:WriteDocument",
                            ],
                        },
                    ],
                    "Principal": [f"arn:aws:iam::{Stack.of(self).account}:root"],
                }
            ]),
        )

        # Outputs
        CfnOutput(
            self, "CollectionEndpoint",
            value=self.collection.attr_collection_endpoint,
            description="OpenSearch Serverless collection endpoint",
        )
        CfnOutput(
            self, "CollectionArn",
            value=self.collection.attr_arn,
            description="OpenSearch Serverless collection ARN",
        )
