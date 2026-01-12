# RAG Pipeline (Chunker)

This module finds documents that have been uploaded to S3 but have not yet been chunked/embedded. For each pending document it:

1. Pulls the PDF bytes directly from S3.
2. Extracts text and performs semantic-style chunking with overlap.
3. Generates embeddings with Amazon Bedrock (default `amazon.titan-embed-text-v1`).
4. Stores the vectors and metadata in an Amazon OpenSearch (vector) index.
5. Updates the `uploads` table to reflect `is_chunked`/`is_embedded` along with the embedding model and index name.

## Environment variables

| Name | Description |
| --- | --- |
| `AWS_REGION` | AWS region for S3, Bedrock, and OpenSearch auth. |
| `S3_BUCKET` | Bucket where the PDFs live. |
| `UPLOADS_DB_DSN` or `DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_NAME` | Connection info for the PostgreSQL database holding the `uploads` table. |
| `OPENSEARCH_HOST` | Domain or endpoint of the OpenSearch collection/cluster (no protocol). |
| `OPENSEARCH_INDEX` | Target knn-enabled index (default `doc-embeddings`). |
| `OPENSEARCH_SERVICE` | SigV4 service identifier. Use `aoss` for OpenSearch Serverless (default) or `es` for provisioned domains. |
| `BEDROCK_EMBEDDING_MODEL_ID` | Optional override for the Bedrock embedding model (default `amazon.titan-embed-text-v1`). |
| `RAG_BATCH_SIZE` | Number of documents processed per run (default `5`). |
| `LOG_LEVEL` | Optional logging level (default `INFO`). |

## Running locally

```bash
# install deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

export AWS_REGION=us-west-2
export S3_BUCKET=your-bucket
export UPLOADS_DB_DSN='postgresql://user:pass@database-1.ct4soaqaq2qo.us-west-2.rds.amazonaws.com:5432/db'
export OPENSEARCH_HOST='your-search-domain.us-west-2.aoss.amazonaws.com'
export OPENSEARCH_INDEX='doc-embeddings'
python backend/RAG_pipeline/chucker.py
```

Ensure that the OpenSearch collection/index has vector search enabled. The script will auto-create the index (knn vector, FAISS/HNSW) if it is missing.

## Vector schema

Each chunk document stored in OpenSearch includes:

- `doc_id`: the S3 object key / upload identifier.
- `file_name`: original filename.
- `s3_url`: original S3 URL for fast download during retrieval.
- `chunk_index`: numeric order of the chunk.
- `text`: chunk text body.
- `embedding`: `knn_vector` of size 1536.
- `uploader_id` / `uploader_name`: (optional) metadata for filtering.

## Status updates

After successful ingestion the pipeline updates the `uploads` table via `mark_upload_processed`, setting `is_chunked`, `is_embedded`, `chunk_count`, and `embedding_model`. Failures are recorded with `status='failed'` plus the error text in `notes` for later inspection.
