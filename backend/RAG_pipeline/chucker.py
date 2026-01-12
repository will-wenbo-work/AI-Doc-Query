import io
import json
import logging
import os
from dataclasses import dataclass
from typing import List

import boto3
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


@dataclass
class Chunk:
	chunk_id: str
	text: str
	index: int


class SemanticChunker:
	def __init__(self, min_chars: int = 400, max_chars: int = 1400, overlap: int = 150):
		self.min_chars = min_chars
		self.max_chars = max_chars
		self.overlap = overlap

	def chunk(self, text: str, doc_id: str) -> List[Chunk]:
		normalized = text.replace('\r', '\n')
		paragraphs = [p.strip() for p in normalized.split('\n') if p.strip()]
		chunks: List[Chunk] = []
		current = []
		current_len = 0
		for para in paragraphs:
			para_len = len(para)
			if current_len + para_len + 1 <= self.max_chars:
				current.append(para)
				current_len += para_len + 1
			else:
				if current:
					chunk_text = '\n'.join(current)
					chunk_index = len(chunks)
					chunk_id = f"{doc_id}::chunk-{chunk_index}"
					chunks.append(Chunk(chunk_id=chunk_id, text=chunk_text, index=chunk_index))
					if self.overlap:
						overlap_text = chunk_text[-self.overlap :]
						current = [overlap_text, para]
						current_len = len(overlap_text) + para_len + 1
					else:
						current = [para]
						current_len = para_len + 1
				else:
					chunk_index = len(chunks)
					chunk_id = f"{doc_id}::chunk-{chunk_index}"
					chunks.append(Chunk(chunk_id=chunk_id, text=para[:self.max_chars], index=chunk_index))
					remainder = para[self.max_chars - self.overlap :] if self.overlap < self.max_chars else ''
					current = [remainder] if remainder else []
					current_len = len(remainder)
		if current:
			chunk_index = len(chunks)
			chunk_id = f"{doc_id}::chunk-{chunk_index}"
			chunks.append(Chunk(chunk_id=chunk_id, text='\n'.join(current), index=chunk_index))
		filtered = []
		for chunk in chunks:
			if len(chunk.text) < self.min_chars and filtered:
				filtered[-1] = Chunk(
					chunk_id=filtered[-1].chunk_id,
					text=f"{filtered[-1].text}\n{chunk.text}",
					index=filtered[-1].index,
				)
			else:
				filtered.append(chunk)
		for idx, chunk in enumerate(filtered):
			filtered[idx] = Chunk(chunk_id=chunk.chunk_id, text=chunk.text.strip(), index=idx)
		return [chunk for chunk in filtered if chunk.text]


class BedrockEmbedder:
	def __init__(self, region: str, model_id: str = EMBEDDING_MODEL_ID):
		self.model_id = model_id
		self.client = boto3.client('bedrock-runtime', region_name=region)

	def embed(self, texts: List[str]) -> List[List[float]]:
		vectors: List[List[float]] = []
		for text in texts:
			payload = json.dumps({'inputText': text[:6000]})
			response = self.client.invoke_model(modelId=self.model_id, body=payload)
			body = json.loads(response['body'].read())
			vector = body.get('embedding')
			if not vector:
				raise RuntimeError('bedrock response missing embedding vector')
			vectors.append([float(v) for v in vector])
		return vectors


class RagPipeline:
	def __init__(self, s3: S3Client, chunker: SemanticChunker, embedder: BedrockEmbedder, vector_store: OpenSearchVectorStore):
		self.s3 = s3
		self.chunker = chunker
		self.embedder = embedder
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
				chunks = self.chunker.chunk(text, doc_id)
				if not chunks:
					raise RuntimeError('chunker produced zero chunks')
				embeddings = self.embedder.embed([chunk.text for chunk in chunks])
				records = []
				for chunk, embedding in zip(chunks, embeddings):
					records.append(
						{
							'id': chunk.chunk_id,
							'doc_id': doc_id,
							'file_name': doc['file_name'],
							's3_url': doc['s3_url'],
							'chunk_index': chunk.index,
							'text': chunk.text,
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
					embedding_model=self.embedder.model_id,
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
	chunker = SemanticChunker()
	embedder = BedrockEmbedder(region=config.aws_region, model_id=EMBEDDING_MODEL_ID)
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
	return RagPipeline(s3_client, chunker, embedder, vector_store)


def main():
	batch_size = int(os.getenv('RAG_BATCH_SIZE', '5'))
	pipeline = build_pipeline()
	processed = pipeline.process_pending(batch_size=batch_size)
	logger.info('processed %s document(s)', processed)


if __name__ == '__main__':
	main()
