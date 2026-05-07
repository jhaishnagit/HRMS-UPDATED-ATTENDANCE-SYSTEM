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
    sender = os.getenv("MAIL_USERNAME")
    password = os.getenv("MAIL_PASSWORD")
    smtp_server = os.getenv("MAIL_SERVER", "smtp.zoho.com")
    smtp_port = int(os.getenv("MAIL_PORT", 587))

    print("DEBUG USER:", sender)   # 👈 debug
    print("DEBUG PASS:", password)

    if not sender or not password:
        logging.error("SMTP credentials missing")
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)

        logging.info(f"Email sent to {to_email}")
        return True

    except Exception as e:
        print("❌ EMAIL ERROR:", e)   # 👈 IMPORTANT
        return False


# ================= DATABASE FUNCTION =================
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "gps_face_db"),
            port=int(os.getenv("DB_PORT", 3306))
        )
        return conn
    except Error as e:
        logging.error(f"DB Error: {e}")
        return None