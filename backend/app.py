import os
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, render_template, session, redirect
from utils import get_db_connection
from datetime import datetime
from auth.routes import auth_bp
from leave.routes import leave_bp
from document.routes import document_bp
from attendance.routes import attendance_bp
from dashboard.routes import dashboard_bp
from admin import admin_bp
from birthday_mailer import init_birthday_scheduler, birthday_bp  
from payslip.routes import payslip_bp # ← NEW



app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')
app.secret_key = "secret123"

app.config.update(
    MAIL_SERVER   = os.getenv("MAIL_SERVER"),
    MAIL_PORT     = int(os.getenv("MAIL_PORT", 587)),
    MAIL_USE_TLS  = True,
    MAIL_USERNAME = os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD"),
)
app.register_blueprint(auth_bp,        url_prefix='/auth')
app.register_blueprint(leave_bp,       url_prefix='/leave')
app.register_blueprint(document_bp,    url_prefix='/document')
app.register_blueprint(attendance_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(admin_bp,       url_prefix='/admin')
app.register_blueprint(birthday_bp)                                # ← NEW
app.register_blueprint(payslip_bp, url_prefix="/payslip")


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
    init_birthday_scheduler(app)
    app.run(host="0.0.0.0", port=5000, debug=True)