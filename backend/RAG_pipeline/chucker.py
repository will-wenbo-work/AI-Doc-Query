import io
import logging
import os

from langchain_aws.embeddings import BedrockEmbeddings
from langchain_experimental.text_splitter import SemanticChunker
from pypdf import PdfReader

from AWS_utils import db as db_utils
from AWS_utils.s3 import S3Client
from AWS_utils.opensearch import OpenSearchVectorStore
from config import load_config


logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))

EMBEDDING_MODEL_ID = os.getenv('BEDROCK_EMBEDDING_MODEL_ID', 'amazon.titan-embed-text-v1')
EMBEDDING_DIMENSION = int(os.getenv('EMBEDDING_DIMENSION', '1536'))


def extract_pdf_text(pdf_bytes: bytes) -> str:
	reader = PdfReader(io.BytesIO(pdf_bytes))
	pages = []
	for page in reader.pages:
		text = page.extract_text() or ''
		if text:
			pages.append(text)
	return '\n'.join(pages)

class RagPipeline:
	def __init__(self, s3: S3Client, splitter: SemanticChunker, embeddings: BedrockEmbeddings, vector_store: OpenSearchVectorStore):
		self.s3 = s3
		self.splitter = splitter
		self.embeddings = embeddings
		self.vector_store = vector_store

	def process_pending(self, batch_size: int = 5) -> int:
		docs = db_utils.fetch_unprocessed_uploads(limit=batch_size)
		if not docs:
			logger.info('no pending documents to process')
			return 0
		processed = 0
		for doc in docs:
			doc_id = doc['doc_id']
			logger.info('processing %s', doc_id)
			try:
				pdf_bytes = self.s3.get_object_bytes(doc_id)
				text = extract_pdf_text(pdf_bytes)
				if not text.strip():
					raise RuntimeError('no extractable text found in PDF')
				chunk_texts = [chunk.strip() for chunk in self.splitter.split_text(text) if chunk.strip()]
				if not chunk_texts:
					raise RuntimeError('SemanticChunker produced zero chunks')
				vectors = self.embeddings.embed_documents(chunk_texts)
				if len(vectors) != len(chunk_texts):
					raise RuntimeError('embedding count does not match chunk count')
				records = []
				for idx, (chunk_text, embedding) in enumerate(zip(chunk_texts, vectors)):
					chunk_id = f"{doc_id}::chunk-{idx}"
					records.append(
						{
							'id': chunk_id,
							'doc_id': doc_id,
							'file_name': doc['file_name'],
							's3_url': doc['s3_url'],
							'chunk_index': idx,
							'text': chunk_text,
							'embedding': embedding,
							'uploader_id': doc.get('uploader_id'),
							'uploader_name': doc.get('uploader_name'),
						}
					)
				self.vector_store.delete_chunks_for_doc(doc_id)
				self.vector_store.upsert_chunks(records)
				db_utils.mark_upload_processed(
					doc_id,
					chunk_count=len(records),
					embedding_model=self.embeddings.model_id,
					metadata_patch={'vector_index': self.vector_store.index_name},
				)
				processed += 1
			except Exception as exc:
				logger.exception('failed to process %s', doc_id)
				db_utils.mark_upload_failed(doc_id, str(exc))
		return processed


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
