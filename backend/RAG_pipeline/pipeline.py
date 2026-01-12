import logging
from typing import List

from langchain_aws.embeddings import BedrockEmbeddings
from langchain_experimental.text_splitter import SemanticChunker

from AWS_utils import db as db_utils
from AWS_utils.opensearch import OpenSearchVectorStore
from AWS_utils.s3 import S3Client
from text_utils import extract_pdf_text

logger = logging.getLogger(__name__)


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
                records: List[dict] = []
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
