import re

from flask import Blueprint, request, render_template, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from utils import get_db_connection
import random
from utils import send_email

import logging


logging.basicConfig(level=logging.INFO)

def check_face(image_bytes):
    import cv2
    import numpy as np

    np_arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    )

    faces = face_cascade.detectMultiScale(gray, 1.1, 6)

    if len(faces) == 0:
        return "No face ❌"

    if len(faces) > 1:
        return "Multiple faces ❌"

    (x, y, w, h) = faces[0]
    img_h, img_w = gray.shape

    face_size = w * h
    image_size = img_w * img_h

    if face_size / image_size < 0.4:
        return "Face too small ❌ (Group photo not allowed)"

    return "OK"

auth_bp = Blueprint('auth', __name__)

# LOGIN
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            session['email'] = user['email']
            session['position'] = user['position']

            # ✅ Set modal flag only once on fresh login
            if user['is_admin'] == 1:
                session['show_admin_modal'] = True

            return redirect('/dashboard')
        else:
            flash("Invalid credentials")

    return render_template('login.html')


def validate_password(password):
    if len(password) < 8:
        return "Password must be at least 8 characters"

    if not any(c.isupper() for c in password):
        return "Add at least 1 uppercase letter"

    if not any(c.islower() for c in password):
        return "Add at least 1 lowercase letter"

    if not any(c.isdigit() for c in password):
        return "Add at least 1 number"

    if not any(c in "@#$%^&+=!" for c in password):
        return "Add at least 1 special character"

    return "OK"


# REGISTER
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():

    # Only admin can access register page
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Admin access required")
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        import re

        if not re.match("^[A-Za-z]+( [A-Za-z]+)*$", username):
            flash("Invalid username format")
            return redirect(url_for('auth.register'))

        email = request.form.get('email')
        raw_password = request.form.get('password')

        check = validate_password(raw_password)
        if check != "OK":
            flash(check)
            return redirect(url_for('auth.register'))

        password = generate_password_hash(raw_password)
        file = request.files.get('face_image')

        if not file or file.filename == "":
            flash("Please upload a face image")
            return redirect(url_for('auth.register'))

        allowed_types = ['image/jpeg', 'image/png', 'image/jpg']

        if file.content_type not in allowed_types:
            flash("Only JPG and PNG images are allowed")
            return redirect(url_for('auth.register'))

        image_data = file.read()

        result = check_face(image_data)

        if result == "No face ❌":
            flash("No face detected. Upload a clear face image")
            return redirect(url_for('auth.register'))

        if result == "Multiple faces ❌":
            flash("Group photo not allowed. Only one person")
            return redirect(url_for('auth.register'))

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash("Email already exists")
            return redirect(url_for('auth.register'))

        cursor.execute(
            "INSERT INTO users (username, email, password, face_image) VALUES (%s, %s, %s, %s)",
            (username, email, password, image_data)
        )
        conn.commit()

        flash("Registered successfully")
        return redirect('/auth/login')

    return render_template('register.html')


# LOGOUT
@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect('/auth/login')


# FORGOT PASSWORD
@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        logging.info(f"Forgot password request for email: {email}")
        if not email:
            flash("Email is required", "error")
            logging.error("Missing email for forgot password")
            return render_template('forgot_password.html')

        conn = get_db_connection()
        if not conn:
            logging.error("No database connection for forgot_password")
            flash("Database connection failed", "error")
            return render_template('forgot_password.html')
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, username FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            logging.info(f"User lookup for forgot password: {'Found' if user else 'Not found'}")
            if user:
                otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
                session['otp'] = otp
                session['reset_email'] = email
                session['otp_sent'] = True
                logging.info(f"Generated OTP: {otp}")

                otp_body = f"""
Dear {user['username']},

You have requested a password reset for your account. Please use the following one-time password (OTP) to proceed:

OTP: {otp}

This OTP is valid for the next 10 minutes. If you did not request this, please ignore this email.

For security reasons, do not share this OTP with anyone.

Best regards,
HR System Security Team
                """
                if send_email(email, "Password Reset OTP - HR System", otp_body):
                    flash("OTP sent to your email!", "success")
                    logging.info(f"OTP email sent to: {email}")
                    return redirect(url_for('auth.forgot_password'))
                else:
                    flash("Failed to send OTP. Please try again.", "error")
                    logging.error("Failed to send OTP email")
            else:
                flash("Email not found", "error")
                logging.error(f"Email not found: {email}")
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()
    logging.info("Rendering forgot_password page")
    return render_template('forgot_password.html')


@auth_bp.route('/verify_otp', methods=['POST'])
def verify_otp():
    otp = request.form.get('otp')
    logging.info(f"Verifying OTP: {otp}")
    if not otp:
        flash("OTP is required", "error")
        logging.error("Missing OTP")
        return redirect(url_for('forgot_password'))

    if otp == session.get('otp'):
        session.pop('otp', None)
        session['otp_verified'] = True
        flash("OTP verified!", "success")
        logging.info("OTP verified successfully")
        return redirect(url_for('auth.reset_password'))
    else:
        flash("Invalid OTP", "error")
        logging.error("Invalid OTP provided")
        return redirect(url_for('auth.forgot_password'))


@auth_bp.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if not session.get('otp_verified'):
        logging.error("OTP not verified, redirecting to login")
        flash("Please verify OTP first", "error")
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        if not new_password:
            flash("New password is required", "error")
            logging.error("Missing new password")
            return render_template('reset_password.html')
        check = validate_password(new_password)

        if check != "OK":
            flash(check)
            return render_template('reset_password.html')

        logging.info(f"Resetting password for email: {session.get('reset_email')}")
        conn = get_db_connection()
        if not conn:
            logging.error("No database connection for reset_password")
            flash("Database connection failed", "error")
            return render_template('reset_password.html')
        try:
            cursor = conn.cursor()
            hashed_password = generate_password_hash(new_password)
            cursor.execute("UPDATE users SET password = %s WHERE email = %s",
                           (hashed_password, session.get('reset_email')))
            conn.commit()
            session.pop('reset_email', None)
            session.pop('otp_verified', None)
            session.pop('otp_sent', None)
            flash("Password reset successful! Please login.", "success")
            logging.info("Password reset successful")
            return redirect(url_for('auth.login'))
        except Exception as e:
            logging.error(f"Reset password error: {str(e)}")
            flash(f"Reset password error: {str(e)}", "error")
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()
    logging.info("Rendering reset_password page")
    return render_template('reset_password.html')