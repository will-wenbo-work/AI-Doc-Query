import logging
import os

from langchain_aws.embeddings import BedrockEmbeddings
from langchain_experimental.text_splitter import SemanticChunker

from AWS_utils.s3 import S3Client
from AWS_utils.opensearch import OpenSearchVectorStore
from config import load_config
from pipeline import RagPipeline


logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))

EMBEDDING_MODEL_ID = os.getenv('BEDROCK_EMBEDDING_MODEL_ID', 'amazon.titan-embed-text-v1')
EMBEDDING_DIMENSION = int(os.getenv('EMBEDDING_DIMENSION', '1536'))
def build_pipeline() -> RagPipeline:
	config = load_config()
	s3_client = S3Client(
		bucket=config.s3_bucket,
		region=config.aws_region,
		aws_access_key_id=config.aws_access_key_id,
		aws_secret_access_key=config.aws_secret_access_key,
	)
	embeddings = BedrockEmbeddings(model_id=EMBEDDING_MODEL_ID, region_name=config.aws_region)
	splitter = SemanticChunker(embeddings)
	opensearch_host = os.environ.get('OPENSEARCH_HOST')
	index_name = os.environ.get('OPENSEARCH_INDEX', 'doc-embeddings')
	if not opensearch_host:
		raise RuntimeError('OPENSEARCH_HOST env var is required for the RAG pipeline')
	service = os.environ.get('OPENSEARCH_SERVICE', 'aoss')
	vector_store = OpenSearchVectorStore(
		opensearch_host,
		index_name,
		region=config.aws_region,
		service=service,
		dimension=EMBEDDING_DIMENSION,
	)
	return RagPipeline(s3_client, splitter, embeddings, vector_store)


def main():
	batch_size = int(os.getenv('RAG_BATCH_SIZE', '5'))
	pipeline = build_pipeline()
	processed = pipeline.process_pending(batch_size=batch_size)
	logger.info('processed %s document(s)', processed)


if __name__ == '__main__':
	main()
