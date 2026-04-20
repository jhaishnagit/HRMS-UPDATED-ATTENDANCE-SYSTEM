from flask import Blueprint

legal_bp = Blueprint('legal', __name__)

@legal_bp.route('/check')
def check():
    return "Legal Service Working"