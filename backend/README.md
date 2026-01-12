# Backend API

This service handles uploads and retrieval for the AI Doc Query stack.

## Endpoints

- `POST /api/upload` — Accepts multipart form-data with `file` (PDF) and optional `uploader_id` / `uploader_name`. Files are uploaded to S3 and a metadata row is stored in Postgres.
- `POST /api/chat/search` — Accepts JSON `{ "query": "...", "top_k": 5 }`. The query is embedded via Amazon Bedrock (LangChain) and searched against the OpenSearch vector index. Returns matching chunks plus metadata useful for grounding answers.

## Required environment variables

| Name | Description |
| --- | --- |
| `AWS_REGION` | AWS region for S3, Bedrock, and OpenSearch (default `us-east-1`). |
| `S3_BUCKET` | Bucket where uploaded PDFs are stored. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Optional if running on an IAM role with the required permissions. |
| `UPLOADS_DB_DSN` **or** (`DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME`, `DB_PORT`) | Connection info for the PostgreSQL `uploads` table. |
| `OPENSEARCH_HOST` | OpenSearch / AOSS endpoint (no protocol). Required for chat/search. |
| `OPENSEARCH_INDEX` | Name of the knn-enabled index (default `doc-embeddings`). |
| `OPENSEARCH_SERVICE` | SigV4 service identifier (`aoss` for serverless, `es` for provisioned domains). |
| `BEDROCK_EMBEDDING_MODEL_ID` | Embedding model used for both ingestion and search (default `amazon.titan-embed-text-v1`). |
| `BEDROCK_LLM_MODEL_ID` | Bedrock chat/completion model for answer generation (default `anthropic.claude-3-sonnet-20240229-v1:0`). |
| `BEDROCK_LLM_TEMPERATURE` | Optional decoding temperature for the chat model (default `0`). |
| `EMBEDDING_DIMENSION` | Expected vector length inside OpenSearch (default `1536`). |
| `PORT` | Flask port (default `8000`). |

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

export AWS_REGION=us-west-2
export S3_BUCKET=your-bucket
export UPLOADS_DB_DSN='postgresql://user:pass@db-host:5432/dbname'
export OPENSEARCH_HOST='domain.us-west-2.aoss.amazonaws.com'
export OPENSEARCH_INDEX='doc-embeddings'
# optional: BEDROCK_EMBEDDING_MODEL_ID, OPENSEARCH_SERVICE, PORT, AWS keys
python3 backend/app.py
```

The RAG ingestion pipeline (`backend/RAG_pipeline/chucker.py`) reads from the same Postgres table, chunks PDFs, creates embeddings, and pushes them into OpenSearch. `/api/chat/search` relies on that index to retrieve relevant chunks for user questions.