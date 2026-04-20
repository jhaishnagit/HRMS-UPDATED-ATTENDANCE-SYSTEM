from flask import Blueprint, request, jsonify, session
import os
from datetime import datetime

document_bp = Blueprint('document', __name__)

@document_bp.route('/upload', methods=['POST'])
def upload():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Not logged in"})

    file = request.files.get('file')

    if not file:
        return jsonify({"success": False, "message": "No file"})

    upload_folder = "uploads"
    os.makedirs(upload_folder, exist_ok=True)

    filename = f"{session['user_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
    path = os.path.join(upload_folder, filename)

    file.save(path)

    return jsonify({"success": True, "message": "Uploaded"})