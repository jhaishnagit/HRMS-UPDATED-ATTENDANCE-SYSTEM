"""
birthday_mailer.py
==================
Auto Birthday Email Scheduler for the Attendance System.

HOW IT WORKS:
- A background scheduler checks every day at 9:00 AM
- It finds all employees whose birthday is TODAY
- It sends a warm birthday wish email to each of them
- Works with Flask + APScheduler + SMTP (Gmail / Zoho)

SETUP:
1. pip install apscheduler
2. Add your SMTP config to app.config (see below)
3. Import and call init_birthday_scheduler(app) in your main app.py
4. Make sure your User model has a `date_of_birth` column (Date type)
"""

from flask import Blueprint
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import date
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

birthday_bp = Blueprint('birthday', __name__)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# BIRTHDAY EMAIL HTML TEMPLATE
# ─────────────────────────────────────────────
def build_birthday_email(employee_name: str) -> str:
    """Returns a beautiful HTML birthday email."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Happy Birthday!</title>
</head>
<body style="margin:0;padding:0;background:#f4f7fa;font-family:'Segoe UI',Arial,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f7fa;padding:40px 0;">
  <tr>
    <td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#fff;border-radius:20px;overflow:hidden;
                    box-shadow:0 8px 32px rgba(0,0,0,0.10);max-width:600px;width:100%;">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#1e3a8a,#2563eb);padding:40px 40px 60px;text-align:center;position:relative;">
            <div style="font-size:64px;margin-bottom:10px;">🎂</div>
            <h1 style="color:#fff;margin:0;font-size:2rem;font-weight:700;letter-spacing:-0.5px;">
                Happy Birthday!
            </h1>
            <p style="color:rgba(255,255,255,0.85);margin:8px 0 0;font-size:1rem;">
                Wishing you a wonderful day
            </p>
          </td>
        </tr>

        <!-- Wave divider -->
        <tr>
          <td style="background:linear-gradient(135deg,#1e3a8a,#2563eb);padding:0;line-height:0;">
            <svg viewBox="0 0 600 40" xmlns="http://www.w3.org/2000/svg" style="display:block;width:100%;">
              <path d="M0,40 C150,0 450,60 600,20 L600,0 L0,0 Z" fill="#fff"/>
            </svg>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:32px 48px 40px;">
            <p style="color:#374151;font-size:1.05rem;line-height:1.7;margin:0 0 20px;">
              Dear <strong style="color:#1e3a8a;">{employee_name}</strong>,
            </p>
            <p style="color:#374151;font-size:1rem;line-height:1.75;margin:0 0 20px;">
              On behalf of the entire team, we want to wish you a very
              <strong style="color:#2563eb;">Happy Birthday! 🎉</strong>
              Today is your special day, and we hope it's filled with joy,
              laughter, and wonderful moments.
            </p>
            <p style="color:#374151;font-size:1rem;line-height:1.75;margin:0 0 32px;">
              Your contributions make a real difference every single day.
              We're truly grateful to have you as part of our team. Here's
              to another amazing year ahead — full of growth, success, and
              happiness! 🥳
            </p>

            <!-- Confetti divider -->
            <div style="text-align:center;font-size:1.8rem;margin:0 0 28px;letter-spacing:8px;">
                🎈🎊🎁🥂🎈
            </div>

            <!-- Warm message box -->
            <div style="background:linear-gradient(135deg,#eff6ff,#dbeafe);border-left:4px solid #3b82f6;
                        border-radius:12px;padding:20px 24px;margin-bottom:24px;">
              <p style="color:#1e3a8a;font-size:0.95rem;margin:0;line-height:1.7;font-style:italic;">
                "May this birthday be just the beginning of a year filled with
                happy memories, wonderful moments, and shining dreams."
              </p>
            </div>

            <p style="color:#6b7280;font-size:0.9rem;margin:0;line-height:1.6;">
                With warm wishes,<br>
                <strong style="color:#1e3a8a;">Your Team 💙</strong>
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f8fafc;padding:20px 48px;border-top:1px solid #e8ecf0;text-align:center;">
            <p style="color:#9ca3af;font-size:0.78rem;margin:0;line-height:1.6;">
              This is an automated birthday greeting from your company's attendance system.<br>
              Please do not reply to this email.
            </p>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>

</body>
</html>"""


# ─────────────────────────────────────────────
# SEND EMAIL FUNCTION
# ─────────────────────────────────────────────
def send_birthday_email(app, employee_name: str, employee_email: str):
    """Send birthday wish email to a single employee."""
    try:
        smtp_host   = app.config.get('MAIL_SERVER', 'smtp.gmail.com')
        smtp_port   = app.config.get('MAIL_PORT', 587)
        smtp_user   = app.config.get('MAIL_USERNAME', '')
        smtp_pass   = app.config.get('MAIL_PASSWORD', '')
        sender_name = app.config.get('MAIL_SENDER_NAME', 'Your Company')
        use_tls     = app.config.get('MAIL_USE_TLS', True)

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'🎂 Happy Birthday, {employee_name}! 🎉'
        msg['From']    = f'{sender_name} <{smtp_user}>'
        msg['To']      = employee_email

        html_body = build_birthday_email(employee_name)
        msg.attach(MIMEText(html_body, 'html'))

        server = smtplib.SMTP(smtp_host, smtp_port)
        server.ehlo()

        if use_tls:
            server.starttls()
            server.ehlo()

        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, employee_email, msg.as_string())
        server.quit()
      
        logger.info(f'[BirthdayMailer] ✅ Sent birthday email to {employee_name} ({employee_email})')
        return True

    except Exception as e:
        logger.error(f'[BirthdayMailer] ❌ Failed to send to {employee_name} ({employee_email}): {e}')
        return False


# ─────────────────────────────────────────────
# DAILY BIRTHDAY CHECK JOB
# ─────────────────────────────────────────────
from utils import get_db_connection

def check_and_send_birthday_emails(app):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        from datetime import date
        today = date.today()

        cursor.execute("""
            SELECT username, email, dob
            FROM users
            WHERE DAY(dob) = %s AND MONTH(dob) = %s
        """, (today.day, today.month))

        users = cursor.fetchall()

        if not users:
            print("No birthdays today")
            return

        for user in users:
          if send_birthday_email(app, user['username'], user['email']):
            print("✅ Email sent to", user['email'])
          else:
             print("❌ Email failed for", user['email'])

        cursor.close()
        conn.close()

    except Exception as e:
        print("ERROR:", e)
# ─────────────────────────────────────────────
# INITIALIZE SCHEDULER — call this in app.py
# ─────────────────────────────────────────────
def init_birthday_scheduler(app):
    """
    Initialize and start the background birthday scheduler.
    Call this once after creating your Flask app.

    Usage in app.py:
        from birthday_mailer import init_birthday_scheduler
        init_birthday_scheduler(app)
    """
    scheduler = BackgroundScheduler(timezone='Asia/Kolkata')  # Change timezone if needed

    # Run every day at 9:00 AM
    scheduler.add_job(
        func=check_and_send_birthday_emails,
        args=[app],
        trigger=CronTrigger(hour=10, minute=56),
        id='birthday_email_job',
        name='Daily Birthday Email Sender',
        replace_existing=True
    )

    scheduler.start()
    logger.info('[BirthdayMailer] 🗓️  Birthday scheduler started — runs daily at 10:56 AM')

    # Prevent scheduler from running during Flask reloader restarts
    import atexit
    atexit.register(lambda: scheduler.shutdown(wait=False))

    return scheduler


# ─────────────────────────────────────────────
# MANUAL TRIGGER ROUTE (admin only - optional)
# ─────────────────────────────────────────────
@birthday_bp.route('/admin/trigger-birthday-emails', methods=['GET'])
def trigger_birthday_emails():
    """
    Optional: Admin route to manually trigger birthday email sending.
    Protect this with @login_required and admin check in production.
    """
    from flask import jsonify, current_app
    check_and_send_birthday_emails(current_app._get_current_object())
    return jsonify({'success': True, 'message': 'Birthday emails triggered successfully'})