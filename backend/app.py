from flask import Flask, render_template, session, redirect
from utils import get_db_connection
from datetime import datetime
from auth.routes import auth_bp
from leave.routes import leave_bp
from document.routes import document_bp
from attendance.routes import attendance_bp
from dashboard.routes import dashboard_bp
from admin import admin_bp

app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')
app.secret_key = "secret123"

app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(leave_bp, url_prefix='/leave')
app.register_blueprint(document_bp, url_prefix='/document')
app.register_blueprint(attendance_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(admin_bp, url_prefix='/admin')



@app.route('/') 
def home():
    return render_template('login.html')





@app.template_filter('strftime')
def format_datetime(value, format='%Y-%m-%d'):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.strftime(format)

if __name__ == "__main__":
    app.run(debug=True)