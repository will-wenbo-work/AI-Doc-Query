import boto3
import json
from botocore.exceptions import BotoCoreError, ClientError


class SecretsManager:
    def __init__(self, region_name: str = None):
        self.client = boto3.client('secretsmanager', region_name=region_name)

    def get_secret(self, secret_name: str) -> dict:
        try:
            resp = self.client.get_secret_value(SecretId=secret_name)
        except (BotoCoreError, ClientError) as e:
            raise RuntimeError(f'failed to get secret {secret_name}: {e}')
        secret_str = resp.get('SecretString')
        if not secret_str:
            raise RuntimeError('secret missing SecretString')
        return json.loads(secret_str)

    def get_rds_credentials(self, secret_name: str) -> dict:
        data = self.get_secret(secret_name)
        username = data.get('username') or data.get('user')
        password = data.get('password')
        host = data.get('host') or data.get('hostname')
        port = str(data.get('port') or data.get('db_port') or 5432)
        dbname = data.get('dbname') or data.get('database') or data.get('db')
        if not all([username, password, host, dbname]):
            raise RuntimeError('secret missing required DB fields')
        return {
            'username': username,
            'password': password,
            'host': host,
            'port': port,
            'dbname': dbname,
        }
