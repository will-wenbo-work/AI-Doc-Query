# Backend - Upload API

This backend exposes a single endpoint used by the frontend:

- `POST /upload_pdf` — accepts multipart form-data with `file` and optional `username`. Uploads the received file to S3 and stores a metadata record in the configured RDS database.

Environment variables (required):

- `S3_BUCKET` — target S3 bucket name
- `AWS_REGION` — AWS region (default `us-east-1`)
- `AWS_ACCESS_KEY_ID` — AWS access key id (optional if using instance role)
- `AWS_SECRET_ACCESS_KEY` — AWS secret access key (optional if using instance role)
- `DATABASE_URL` — SQLAlchemy-compatible database URI, e.g. `postgresql+psycopg2://user:pass@host:5432/dbname`

Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

Run locally (development)

```bash
# from repo root
export S3_BUCKET=your-bucket
export DATABASE_URL='postgresql+psycopg2://user:pass@host:5432/db'
# (optional) set AWS keys
# export AWS_ACCESS_KEY_ID=...
# export AWS_SECRET_ACCESS_KEY=...
python3 backend/app.py
```

Notes

- The code will create a table named `uploads` if it does not already exist. Columns: `id`, `filename`, `upload_time`, `username`, `file_format`, `s3_url`.
- The S3 object URL stored is the public S3 URL pattern. If your bucket is private, you should generate presigned URLs when needed.