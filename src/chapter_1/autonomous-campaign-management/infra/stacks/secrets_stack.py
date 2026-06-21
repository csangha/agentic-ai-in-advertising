"""
Secrets Stack: AWS Secrets Manager for agent configuration and API credentials.

Stores:
- Platform API credentials (Meta, Google, Amazon Ads, TikTok)
- Agent runtime configuration (model IDs, MCP ARNs)
- Database connection strings (auto-created by Aurora)
- OpenSearch endpoints
"""

from aws_cdk import (
    Stack,
    aws_secretsmanager as sm,
    CfnOutput,
)
from constructs import Construct
import json


class SecretsStack(Stack):
    """Secrets Manager secrets for campaign management agents."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Agent configuration secret (loaded by agents at startup)
        self.agent_config_secret = sm.Secret(
            self, "AgentConfigSecret",
            secret_name="campaign-mgmt/agent-config",
            description="Configuration for campaign management LangGraph agents",
            generate_secret_string=sm.SecretStringGenerator(
                secret_string_template=json.dumps({
                    "AWS_REGION": "us-east-1",
                    "MODEL_ID": "us.anthropic.claude-sonnet-4-20250514",
                    "MCP_KB_ARN": "PLACEHOLDER",
                    "OPENSEARCH_ENDPOINT": "PLACEHOLDER",
                    "REDIS_ENDPOINT": "PLACEHOLDER",
                }),
                generate_string_key="api_key_placeholder",
            ),
        )

        # Amazon Ads API credentials
        self.ads_credentials_secret = sm.Secret(
            self, "AdsCredentialsSecret",
            secret_name="campaign-mgmt/amazon-ads-credentials",
            description="Amazon Ads API OAuth credentials",
            generate_secret_string=sm.SecretStringGenerator(
                secret_string_template=json.dumps({
                    "CLIENT_ID": "PLACEHOLDER",
                    "CLIENT_SECRET": "PLACEHOLDER",
                    "REFRESH_TOKEN": "PLACEHOLDER",
                }),
                generate_string_key="placeholder",
            ),
        )

        # Meta Ads API credentials
        self.meta_credentials_secret = sm.Secret(
            self, "MetaCredentialsSecret",
            secret_name="campaign-mgmt/meta-ads-credentials",
            description="Meta Ads API credentials",
            generate_secret_string=sm.SecretStringGenerator(
                secret_string_template=json.dumps({
                    "ACCESS_TOKEN": "PLACEHOLDER",
                    "APP_SECRET": "PLACEHOLDER",
                    "ACCOUNT_ID": "PLACEHOLDER",
                }),
                generate_string_key="placeholder",
            ),
        )

        # Google Ads API credentials
        self.google_credentials_secret = sm.Secret(
            self, "GoogleCredentialsSecret",
            secret_name="campaign-mgmt/google-ads-credentials",
            description="Google Ads API credentials",
            generate_secret_string=sm.SecretStringGenerator(
                secret_string_template=json.dumps({
                    "DEVELOPER_TOKEN": "PLACEHOLDER",
                    "CLIENT_ID": "PLACEHOLDER",
                    "CLIENT_SECRET": "PLACEHOLDER",
                    "REFRESH_TOKEN": "PLACEHOLDER",
                    "CUSTOMER_ID": "PLACEHOLDER",
                }),
                generate_string_key="placeholder",
            ),
        )

        # TikTok Ads API credentials
        self.tiktok_credentials_secret = sm.Secret(
            self, "TikTokCredentialsSecret",
            secret_name="campaign-mgmt/tiktok-ads-credentials",
            description="TikTok Ads API credentials",
            generate_secret_string=sm.SecretStringGenerator(
                secret_string_template=json.dumps({
                    "APP_ID": "PLACEHOLDER",
                    "APP_SECRET": "PLACEHOLDER",
                    "ACCESS_TOKEN": "PLACEHOLDER",
                    "ADVERTISER_ID": "PLACEHOLDER",
                }),
                generate_string_key="placeholder",
            ),
        )

        # Outputs
        CfnOutput(
            self, "AgentConfigSecretArn",
            value=self.agent_config_secret.secret_arn,
        )
        CfnOutput(
            self, "AdsCredentialsSecretArn",
            value=self.ads_credentials_secret.secret_arn,
        )
