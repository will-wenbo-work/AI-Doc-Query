import os
import uuid
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3
from botocore.exceptions import BotoCoreError, ClientError

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from file_metadata.upload_metadata import UploadMetadata
from utils.storage import S3Storage
from dotenv import load_dotenv
from urllib.parse import quote_plus
import json

load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration via environment variables
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
S3_BUCKET = os.getenv('S3_BUCKET')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')  # SQLAlchemy-compatible URL
RDS_SECRET_ARN = os.getenv('RDS_SECRET_ARN') or os.getenv('RDS_SECRET_NAME')

# Initialize S3 storage helper
s3_storage = S3Storage(region=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY, bucket=S3_BUCKET)

# If DATABASE_URL is not provided, try to fetch DB credentials from AWS Secrets Manager
if not DATABASE_URL:
    if not RDS_SECRET_ARN:
        raise RuntimeError('DATABASE_URL not set and no RDS_SECRET_ARN / RDS_SECRET_NAME provided')
    try:
        sm = boto3.client('secretsmanager', region_name=AWS_REGION)
        resp = sm.get_secret_value(SecretId=RDS_SECRET_ARN)
        secret_string = resp.get('SecretString')
        if not secret_string:
            raise RuntimeError('secret has no SecretString')
        secret = json.loads(secret_string)
        db_user = secret.get('username') or secret.get('user')
        db_pass = secret.get('password')
        db_host = secret.get('host')
        db_port = secret.get('port') or '5432'
        db_name = secret.get('dbname') or secret.get('database') or secret.get('db')
        if not all([db_user, db_pass, db_host, db_name]):
            raise RuntimeError('secret missing username/password/host/dbname')
        enc_pass = quote_plus(db_pass)
        DATABASE_URL = f"postgresql+psycopg2://{db_user}:{enc_pass}@{db_host}:{db_port}/{db_name}?sslmode=require"
    except Exception as e:
        raise RuntimeError(f'failed to load DB credentials from Secrets Manager: {e}')

# Initialize file-metadata handler for uploads table (pass engine)
# try:
#     engine = create_engine(DATABASE_URL)
#     file_metadata = UploadMetadata(engine)
# except Exception as e:
#     raise RuntimeError(f'failed to initialize UploadMetadata: {e}')


@app.route('/upload_pdf', methods=['POST', 'OPTIONS'])
def upload_pdf():
    # Simple CORS preflight handled by flask-cors; keep OPTIONS for clarity
    if request.method == 'OPTIONS':
        return ('', 204)

    # Expect multipart form with 'file' and optional 'username'
    if 'file' not in request.files:
        return jsonify({'error': 'no file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'no selected file'}), 400

    username = request.form.get('username') or request.args.get('username') or 'anonymous'

    # Basic file metadata
    filename = file.filename
    content_type = file.content_type or ''
    fmt = content_type.split('/')[-1] if '/' in content_type else content_type

    # Create a unique object key for S3
    object_key = f"uploads/{uuid.uuid4().hex}_{filename}"

    try:
        # Upload file object stream directly to S3 using storage helper
        s3_storage.upload_fileobj(file.stream, object_key)
    except Exception as e:
        return jsonify({'error': 's3 upload failed', 'details': str(e)}), 500

    # Build public S3 URL via helper
    s3_url = s3_storage.get_public_url(object_key)

    # Persist file metadata to RDS
    try:
        record_id = UploadMetadata.insert_upload(filename=filename, username=username, file_format=fmt, s3_url=s3_url)
    except SQLAlchemyError as e:
        return jsonify({'error': 'db insert failed', 'details': str(e)}), 500

    return jsonify({'doc_id': record_id, 's3_url': s3_url})

@app.route('/get_healthness', methods=['GET'])
def get_healthness():
    try:
        # Check if the database connection is healthy
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            connection.execute('SELECT 1')
        return jsonify({'status': 'healthy'})
    except SQLAlchemyError as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500


if __name__ == '__main__':
    # Useful for local testing: flask app runs on port 8000 by default
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8000)), debug=True)
# backend APIs