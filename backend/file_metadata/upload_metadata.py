from datetime import datetime
import uuid
from sqlalchemy import (
    MetaData,
    Table,
    Column,
    String,
    DateTime,
)
from sqlalchemy.exc import SQLAlchemyError


class UploadMetadata:
    """Encapsulates creation and insertion of file metadata records into the `uploads` table.

    Construction options:
    - pass a SQLAlchemy Engine instance
    - pass a database URL string
    - pass a `secret_arn` plus a `secrets_manager` instance (which must implement `get_rds_credentials(secret_arn)`)
    """

    def __init__(self, database_engine=None, secret_arn: str = None, secrets_manager=None):
        # Accept either an engine, a database URL string, or a secret ARN + secrets manager
        from sqlalchemy import create_engine

        if database_engine:
            if isinstance(database_engine, str):
                self.engine = create_engine(database_engine)
            else:
                self.engine = database_engine
        elif secret_arn and secrets_manager is not None:
            # secrets_manager must provide get_rds_credentials(secret_arn) -> dict
            creds = secrets_manager.get_rds_credentials(secret_arn)
            user = creds['username']
            pwd = creds['password']
            host = creds['host']
            port = creds.get('port', '5432')
            dbname = creds['dbname']
            from urllib.parse import quote_plus

            enc = quote_plus(pwd)
            url = f"postgresql+psycopg2://{user}:{enc}@{host}:{port}/{dbname}?sslmode=require"
            self.engine = create_engine(url)
        else:
            raise ValueError('UploadMetadata requires database_engine or (secret_arn and secrets_manager)')

        self.metadata = MetaData()

        self.uploads_table = Table(
            'uploads',
            self.metadata,
            Column('id', String(64), primary_key=True),
            Column('filename', String(512), nullable=False),
            Column('upload_time', DateTime, nullable=False),
            Column('username', String(128), nullable=True),
            Column('file_format', String(64), nullable=True),
            Column('s3_url', String(1024), nullable=False),
        )

        # Ensure table exists
        self.metadata.create_all(self.engine)

    def insert_upload(self, filename, username, file_format, s3_url, record_id=None, upload_time=None):
        """Insert a new file metadata record and return the generated id."""
        if record_id is None:
            record_id = uuid.uuid4().hex
        if upload_time is None:
            upload_time = datetime.utcnow()

        ins = self.uploads_table.insert().values(
            id=record_id,
            filename=filename,
            upload_time=upload_time,
            username=username,
            file_format=file_format,
            s3_url=s3_url,
        )
        try:
            with self.engine.begin() as conn:
                conn.execute(ins)
        except SQLAlchemyError:
            raise

        return record_id
