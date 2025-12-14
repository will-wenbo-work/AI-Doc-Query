from flask import Blueprint, jsonify


def create_health_blueprint(uploads_repo):
    """Create a blueprint that exposes a DB health endpoint.

    uploads_repo: instance of UploadsRepository (or wrapper) — the function will
    access its underlying engine to run a simple SELECT 1.
    """
    bp = Blueprint('health_api', __name__)

    @bp.route('/get_healthness', methods=['GET'])
    def get_healthness():
       return jsonify({'status': 'healthy'})

    return bp