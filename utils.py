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
    server_host = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
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