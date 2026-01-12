-- Create uploads table for recording S3 uploads
-- Note: this uses pgcrypto's gen_random_uuid(); enable with:
--   CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS uploads (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  doc_id text NOT NULL,
  file_name text NOT NULL,
  s3_url text NOT NULL,
  uploader_id text NULL,
  uploader_name text NULL,
  uploaded_at timestamptz NOT NULL DEFAULT now(),
  content_type text NULL,
  size_bytes bigint NULL,
  is_chunked boolean NOT NULL DEFAULT false,
  chunk_count integer NULL,
  is_embedded boolean NOT NULL DEFAULT false,
  embedding_model text NULL,
  metadata jsonb NULL,
  status text DEFAULT 'uploaded',
  notes text NULL
);

CREATE INDEX IF NOT EXISTS idx_uploads_uploaded_at ON uploads (uploaded_at);
CREATE INDEX IF NOT EXISTS idx_uploads_uploader_id ON uploads (uploader_id);
CREATE INDEX IF NOT EXISTS idx_uploads_doc_id ON uploads (doc_id);
