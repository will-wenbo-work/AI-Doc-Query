import os
from flask import Flask
from flask_cors import CORS
from sqlalchemy import create_engine
from dotenv import load_dotenv
from langchain_aws.embeddings import BedrockEmbeddings
from langchain_aws.chat_models import ChatBedrock
from config import load_config
from AWS_utils.s3 import S3Client
from AWS_utils.secrets import SecretsManager
from AWS_utils.opensearch import OpenSearchVectorStore
from backend.API_handler.upload import create_upload_blueprint
from backend.API_handler.get_healthness import create_health_blueprint
from backend.API_handler.chat import create_chat_blueprint


load_dotenv()

def create_app():
    cfg = load_config()
    app = Flask(__name__)
    CORS(app)
    # create infra
    s3 = S3Client(bucket=cfg.s3_bucket, region=cfg.aws_region)
    secrets_mgr = SecretsManager(region_name=cfg.aws_region)

    embedding_model_id = os.getenv('BEDROCK_EMBEDDING_MODEL_ID', 'amazon.titan-embed-text-v1')
    llm_model_id = os.getenv('BEDROCK_LLM_MODEL_ID', 'anthropic.claude-3-sonnet-20240229-v1:0')
    llm_temperature = float(os.getenv('BEDROCK_LLM_TEMPERATURE', '0'))
    embedding_dimension = int(os.getenv('EMBEDDING_DIMENSION', '1536'))
    opensearch_host = os.getenv('OPENSEARCH_HOST')
    opensearch_index = os.getenv('OPENSEARCH_INDEX', 'doc-embeddings')
    opensearch_service = os.getenv('OPENSEARCH_SERVICE', 'aoss')
    if not opensearch_host:
        raise RuntimeError('OPENSEARCH_HOST env var is required to enable chat/search API')

    embeddings = BedrockEmbeddings(model_id=embedding_model_id, region_name=cfg.aws_region)
    llm = ChatBedrock(model_id=llm_model_id, region_name=cfg.aws_region, temperature=llm_temperature)
    vector_store = OpenSearchVectorStore(
        opensearch_host,
        opensearch_index,
        region=cfg.aws_region,
        service=opensearch_service,
        dimension=embedding_dimension,
    )


    # register the blueprint with optional prefix
    app.register_blueprint(create_upload_blueprint(storage_client=s3), url_prefix='/api')
    app.register_blueprint(
        create_chat_blueprint(embeddings=embeddings, vector_store=vector_store, llm=llm),
        url_prefix='/api'
    )

    return app



if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=8000, debug=True)