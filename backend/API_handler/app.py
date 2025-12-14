import os
from flask import Flask
from flask_cors import CORS
from sqlalchemy import create_engine
from dotenv import load_dotenv
from config import load_config
from AWS_utils.s3 import S3Client
from AWS_utils.secrets import SecretsManager
from backend.API_handler.upload import create_upload_blueprint
from backend.API_handler.get_healthness import create_health_blueprint


load_dotenv()

def create_app():
    cfg = load_config()
    app = Flask(__name__)
    CORS(app)
    # create infra
    s3 = S3Client(bucket=cfg.s3_bucket, region=cfg.aws_region)
    secrets_mgr = SecretsManager(region_name=cfg.aws_region)


    # register the blueprint with optional prefix
    app.register_blueprint(create_upload_blueprint(storage_client=s3), url_prefix='/api')    # Register health-check blueprint (uses repo for DB check)

    return app



if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=8000, debug=True)