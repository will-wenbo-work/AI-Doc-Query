import os
import boto3
from botocore.exceptions import BotoCoreError, ClientError


class S3Client:
    def __init__(self, bucket: str, region: str = None, aws_access_key_id: str | None = None, aws_secret_access_key: str | None = None):
        self.bucket = bucket
        self.region = region
        self.client = boto3.client('s3', region_name=region, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)

    def upload_fileobj(self, fileobj, object_key: str, ExtraArgs: dict | None = None):
        if not self.bucket:
            raise RuntimeError('S3 bucket not configured')
        self.client.upload_fileobj(fileobj, self.bucket, object_key, ExtraArgs=ExtraArgs or {})

    def get_public_url(self, object_key: str) -> str:
        if not self.bucket:
            raise RuntimeError('S3 bucket not configured')
        if not self.region or self.region == 'us-east-1':
            return f"https://{self.bucket}.s3.amazonaws.com/{object_key}"
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{object_key}"
