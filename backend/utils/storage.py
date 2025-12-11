import boto3
from botocore.exceptions import BotoCoreError, ClientError
import os


class S3Storage:
    """Simple S3 helper encapsulating upload and URL generation.

    Example:
        s3 = S3Storage(region, access_key, secret_key, bucket)
        s3.upload_fileobj(fileobj, 'uploads/key_filename')
        url = s3.get_public_url('uploads/key_filename')
    """

    def __init__(self, region=None, aws_access_key_id=None, aws_secret_access_key=None, bucket=None):
        self.region = region or os.getenv('AWS_REGION', 'us-east-1')
        self.bucket = bucket or os.getenv('S3_BUCKET')
        # boto3 will also pick up credentials from environment or IAM role if not provided
        self.client = boto3.client(
            's3',
            region_name=self.region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

    def upload_fileobj(self, fileobj, object_key, ExtraArgs=None):
        """Upload a file-like object to S3 under `object_key` in configured bucket.

        Raises botocore exceptions on failure.
        """
        if not self.bucket:
            raise RuntimeError('S3 bucket not configured')
        # fileobj should be a file-like object supporting read()/seek()
        self.client.upload_fileobj(fileobj, self.bucket, object_key, ExtraArgs=ExtraArgs or {})

    def get_public_url(self, object_key):
        """Return a public S3 URL for the object. If bucket is in us-east-1 the URL format differs slightly."""
        if not self.bucket:
            raise RuntimeError('S3 bucket not configured')
        if self.region == 'us-east-1':
            return f"https://{self.bucket}.s3.amazonaws.com/{object_key}"
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{object_key}"
