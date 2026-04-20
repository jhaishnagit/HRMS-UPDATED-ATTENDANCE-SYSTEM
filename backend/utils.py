# utils.py
import os
import smtplib
import logging
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)

def send_email(to_email, subject, body):
    sender = os.environ.get("SMTP_SENDER")
    password = os.environ.get("SMTP_PASSWORD")
    server_host = os.environ.get("SMTP_SERVER", "smtp.zoho.com")
    server_port = int(os.environ.get("SMTP_PORT", 587))

    if not sender or not password:
        logging.error("SMTP credentials not configured in environment")
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email

    try:
        with smtplib.SMTP(server_host, server_port) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
        logging.info(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        logging.error(f"Failed to send email: {e}")
        return False
# utils.py
import os
import smtplib
import logging
from email.mime.text import MIMEText
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

load_dotenv()

logging.basicConfig(level=logging.INFO)

# ================= EMAIL FUNCTION =================
def send_email(to_email, subject, body):
    sender = os.environ.get("SMTP_SENDER")
    password = os.environ.get("SMTP_PASSWORD")
    server_host = os.environ.get("SMTP_SERVER", "smtp.zoho.com")
    server_port = int(os.environ.get("SMTP_PORT", 587))

    if not sender or not password:
        logging.error("SMTP credentials not configured")
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email

    try:
        with smtplib.SMTP(server_host, server_port) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
        logging.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        logging.error(f"Email error: {e}")
        return False


# ================= DATABASE FUNCTION =================
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database=os.environ.get("DB_NAME", "gps_face_db"),
            port=int(os.environ.get("DB_PORT", 3306))
        )
        return conn
    except Error as e:
        logging.error(f"DB Error: {e}")
        return None