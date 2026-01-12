# Backend API

This service powers both document ingestion (upload + metadata logging) and question answering via retrieval-augmented generation (RAG).

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

export AWS_REGION=us-west-2
export S3_BUCKET=your-bucket
export UPLOADS_DB_DSN='postgresql://user:pass@db-host:5432/dbname'
export OPENSEARCH_HOST='domain.us-west-2.aoss.amazonaws.com'
export OPENSEARCH_INDEX='doc-embeddings'
# optional overrides: BEDROCK_* vars, OPENSEARCH_SERVICE, PORT, AWS keys
python3 backend/app.py
```

### Upload a PDF

```bash
curl -X POST http://localhost:8000/api/upload \
	-F "file=@docs/sample.pdf" \
	-F "uploader_id=alice" \
	-F "uploader_name=Alice"
```

### Ask a question

```bash
curl -X POST http://localhost:8000/api/chat/search \
	-H 'Content-Type: application/json' \
	-d '{"query":"What does sample.pdf say about onboarding?","top_k":3}'
```

The response includes the retrieved chunks (`results`) and the Bedrock-generated answer grounded in those chunks.

## Endpoints

| Route | Description |
| --- | --- |
| `POST /api/upload` | Accepts multipart `file` (PDF). Saves to S3 and inserts a row in the `uploads` table with metadata like uploader, doc id, and processing flags. |
| `POST /api/chat/search` | Accepts JSON `{ "query": "...", "top_k": 5 }`. Embeds the question via Bedrock (LangChain), runs kNN over the OpenSearch vector index, feeds results plus explicit instructions into a Bedrock chat model, and returns `{query, top_k, results, answer}`. |

## Environment variables

| Name | Description |
| --- | --- |
| `AWS_REGION` | AWS region for S3, Bedrock, and OpenSearch (default `us-east-1`). |
| `S3_BUCKET` | Bucket where uploaded PDFs are stored. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Optional if running on an IAM role with the required permissions. |
| `UPLOADS_DB_DSN` **or** (`DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME`, `DB_PORT`) | Connection info for the PostgreSQL `uploads` table. |
| `OPENSEARCH_HOST` | OpenSearch / AOSS endpoint (no protocol). Required for retrieval. |
| `OPENSEARCH_INDEX` | Name of the knn-enabled index (default `doc-embeddings`). |
| `OPENSEARCH_SERVICE` | SigV4 service identifier (`aoss` for serverless, `es` for provisioned domains). |
| `BEDROCK_EMBEDDING_MODEL_ID` | Embedding model for both ingestion and search (default `amazon.titan-embed-text-v1`). |
| `BEDROCK_LLM_MODEL_ID` | Bedrock chat/completion model for answer generation (default `anthropic.claude-3-sonnet-20240229-v1:0`). |
| `BEDROCK_LLM_TEMPERATURE` | Optional decoding temperature for the chat model (default `0`). |
| `EMBEDDING_DIMENSION` | Vector length stored in OpenSearch (default `1536`). |
| `PORT` | Flask port (default `8000`). |

## RAG ingestion pipeline

The upload metadata drives `backend/RAG_pipeline/chucker.py`:

1. Fetches unprocessed rows from the `uploads` table.
2. Downloads each PDF from S3, extracts text, and runs LangChain's `SemanticChunker`.
3. Generates embeddings via Bedrock and writes chunk vectors (with metadata) into OpenSearch.
4. Updates the `uploads` table flags (`is_chunked`, `is_embedded`, `chunk_count`, etc.).

Run it manually or via a scheduler:

```bash
python backend/RAG_pipeline/chucker.py
```

Once embedded, `/api/chat/search` can retrieve those chunks and instruct the Bedrock LLM to answer with citations like `[1]`, `[2]` referencing the returned segments.