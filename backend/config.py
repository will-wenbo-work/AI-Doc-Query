import os
from dataclasses import dataclass


@dataclass
class Config:
    aws_region: str
    s3_bucket: str
    aws_access_key_id: str | None
    aws_secret_access_key: str | None
    database_url: str | None
    rds_secret_arn: str | None
    port: int


def load_config() -> Config:
    return Config(
        aws_region=os.getenv('AWS_REGION', 'us-east-1'),
        s3_bucket=os.getenv('S3_BUCKET'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        database_url=os.getenv('DATABASE_URL'),
        rds_secret_arn=os.getenv('RDS_SECRET_ARN') or os.getenv('RDS_SECRET_NAME'),
        port=int(os.getenv('PORT', '8000')),
    )
