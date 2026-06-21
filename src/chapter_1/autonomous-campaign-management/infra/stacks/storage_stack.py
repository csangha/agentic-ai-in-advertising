"""
Storage Stack: S3 buckets for raw data, assets, and audit archives.

Buckets:
- Raw API responses (partitioned: source/entity/date/)
- Generated creative assets
- Audit log archives (immutable)
- Campaign reports and deliverables
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    aws_s3 as s3,
    CfnOutput,
)
from constructs import Construct


class StorageStack(Stack):
    """S3 storage infrastructure for campaign management."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Raw API response storage (partitioned by source/entity/date)
        self.raw_bucket = s3.Bucket(
            self, "RawDataBucket",
            bucket_name=None,  # Auto-generated unique name
            versioned=False,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="TransitionToIA",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(30),
                        ),
                    ],
                ),
                s3.LifecycleRule(
                    id="ExpireAfter90Days",
                    expiration=Duration.days(90),
                ),
            ],
        )

        # Audit log archive (immutable — Object Lock for compliance)
        self.audit_bucket = s3.Bucket(
            self, "AuditBucket",
            bucket_name=None,
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.RETAIN,
            object_lock_enabled=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="TransitionToGlacier",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90),
                        ),
                    ],
                ),
            ],
        )

        # Creative assets storage
        self.assets_bucket = s3.Bucket(
            self, "AssetsBucket",
            bucket_name=None,
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Reports and deliverables
        self.reports_bucket = s3.Bucket(
            self, "ReportsBucket",
            bucket_name=None,
            versioned=False,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.DESTROY,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ExpireReports",
                    expiration=Duration.days(365),
                ),
            ],
        )

        # Outputs
        CfnOutput(self, "RawBucketName", value=self.raw_bucket.bucket_name)
        CfnOutput(self, "AuditBucketName", value=self.audit_bucket.bucket_name)
        CfnOutput(self, "AssetsBucketName", value=self.assets_bucket.bucket_name)
        CfnOutput(self, "ReportsBucketName", value=self.reports_bucket.bucket_name)
