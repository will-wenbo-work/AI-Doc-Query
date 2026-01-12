import os
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import Json


def _get_dsn():
    # Prefer a full DSN in env var, otherwise construct from separate vars
    dsn = os.environ.get('UPLOADS_DB_DSN')
    if dsn:
        return dsn
    user = os.environ.get('DB_USER')
    password = os.environ.get('DB_PASSWORD')
    host = os.environ.get('DB_HOST')
    port = os.environ.get('DB_PORT') or '5432'
    dbname = os.environ.get('DB_NAME')
    if not all([user, password, host, dbname]):
        raise RuntimeError('database DSN not configured; set UPLOADS_DB_DSN or DB_USER/DB_PASSWORD/DB_HOST/DB_NAME')
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"


@contextmanager
def get_conn():
    dsn = _get_dsn()
    conn = psycopg2.connect(dsn, connect_timeout=5)
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


def insert_upload_record(
    doc_id,
    file_name,
    s3_url,
    uploader_id=None,
    uploader_name=None,
    content_type=None,
    size_bytes=None,
    is_chunked=False,
    chunk_count=None,
    is_embedded=False,
    embedding_model=None,
    metadata=None,
    status='uploaded',
    notes=None,
):
    sql = """
    INSERT INTO uploads (
      doc_id, file_name, s3_url, uploader_id, uploader_name,
      content_type, size_bytes, is_chunked, chunk_count,
      is_embedded, embedding_model, metadata, status, notes
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    RETURNING id, uploaded_at
    """
    params = (
        doc_id,
        file_name,
        s3_url,
        uploader_id,
        uploader_name,
        content_type,
        size_bytes,
        is_chunked,
        chunk_count,
        is_embedded,
        embedding_model,
        Json(metadata) if metadata is not None else None,
        status,
        notes,
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            conn.commit()
            return {'id': str(row[0]), 'uploaded_at': row[1].isoformat()}


def fetch_unprocessed_uploads(limit: int = 10):
    sql = """
    SELECT id, doc_id, file_name, s3_url, uploader_id, uploader_name
    FROM uploads
    WHERE COALESCE(is_chunked, false) = false OR COALESCE(is_embedded, false) = false
    ORDER BY uploaded_at ASC
    LIMIT %s
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
            columns = ['id', 'doc_id', 'file_name', 's3_url', 'uploader_id', 'uploader_name']
            return [dict(zip(columns, row)) for row in rows]


def mark_upload_processed(doc_id: str, chunk_count: int, embedding_model: str, metadata_patch: dict | None = None):
    sql = """
    UPDATE uploads
    SET is_chunked = true,
        chunk_count = %s,
        is_embedded = true,
        embedding_model = %s,
        status = 'embedded',
        metadata = CASE
          WHEN %s IS NULL THEN metadata
          ELSE COALESCE(metadata, '{}'::jsonb) || %s
        END
    WHERE doc_id = %s
    """
    patch = Json(metadata_patch) if metadata_patch is not None else None
    params = (chunk_count, embedding_model, patch, patch, doc_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()


def mark_upload_failed(doc_id: str, notes: str):
    sql = """
    UPDATE uploads
    SET status = 'failed',
        notes = %s
    WHERE doc_id = %s
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (notes, doc_id))
            conn.commit()
