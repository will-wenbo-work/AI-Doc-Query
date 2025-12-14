from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import uuid
import mimetypes


ALLOWED_EXT = {'pdf'}


def create_upload_blueprint(storage_client):
    """Return a Blueprint that exposes POST /upload for S3-only uploads.

    storage_client: required. Must implement:
      - upload_fileobj(fileobj, object_key, ExtraArgs=None)
      - get_public_url(object_key) -> str

    The route returns JSON: {"doc_id": <object_key>, "s3_url": <public_url>}.
    """

    bp = Blueprint('upload_api', __name__)

    @bp.route('/upload', methods=['POST'])
    def upload():
        # Basic multipart validation
        if 'file' not in request.files:
            return jsonify({'error': 'no file part'}), 400

        f = request.files['file']
        if not f or f.filename == '':
            return jsonify({'error': 'no selected file'}), 400

        # Sanitize filename and validate extension
        filename = secure_filename(f.filename)
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in ALLOWED_EXT:
            return jsonify({'error': 'unsupported file type', 'allowed': sorted(list(ALLOWED_EXT))}), 400

        # Require a storage client (S3)
        if storage_client is None:
            return jsonify({'error': 'storage client not configured'}), 500

        # Build object key and determine content type
        object_key = f"uploads/{uuid.uuid4().hex}_{filename}"
        content_type = f.mimetype or mimetypes.guess_type(filename)[0] or 'application/octet-stream'

        # Prefer the file.stream when available
        file_obj = getattr(f, 'stream', f)

        try:
            # Upload using the provided storage client
            storage_client.upload_fileobj(file_obj, object_key, ExtraArgs={'ContentType': content_type})
            s3_url = storage_client.get_public_url(object_key)
        except Exception as e:
            return jsonify({'error': 'upload failed', 'details': str(e)}), 500

        return jsonify({'doc_id': object_key, 's3_url': s3_url})

    return bp
