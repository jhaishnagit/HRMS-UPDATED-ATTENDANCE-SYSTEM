# app.py
from flask import Flask, request, render_template, jsonify, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import Error
import os
import cv2
import geocoder
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import face_recognition
import numpy as np
import random
import base64
import logging
from dotenv import load_dotenv
import json
from utils import send_email  # Import from utils.py

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "default_secret_key_123")  # Fallback for development

# MySQL Configuration
db_config = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "jhaishna"),
    "database": os.environ.get("DB_NAME", "gps_face_db"),
    "port": int(os.environ.get("DB_PORT", 3306))
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        if conn.is_connected():
            logging.info("Successfully established database connection")
            return conn
        else:
            logging.error("Failed to establish database connection")
            return None
    except Error as err:
        logging.error(f"Database connection failed: {err}")
        flash(f"Database connection failed: {err}", "error")
        return None

# Database initialization - ADD leave_balance table
def init_db():
    conn = get_db_connection()
    if not conn:
        logging.error("Cannot initialize database: No connection")
        return
    try:
        cursor = conn.cursor()
        logging.info("Initializing database schema")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE,
                email VARCHAR(100) UNIQUE,
                password VARCHAR(255),
                face_image LONGBLOB,
                position VARCHAR(100) DEFAULT 'Employee',
                is_admin BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                login_time DATETIME,
                logout_time DATETIME,
                login_photo_path VARCHAR(255),
                logout_photo_path VARCHAR(255),
                login_latitude FLOAT,
                login_longitude FLOAT,
                logout_latitude FLOAT,
                logout_longitude FLOAT,
                daily_status_submitted TINYINT(1) DEFAULT 0,
                admin_verified TINYINT(1) DEFAULT 0,
                attendance_status ENUM('Present', 'Absent') DEFAULT 'Absent',
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rota (
                id INT AUTO_INCREMENT PRIMARY KEY,
                rota_image LONGBLOB,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id INT,
                is_read BOOLEAN DEFAULT 0,
                read_at TIMESTAMP NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_updates (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                update_message TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verification_status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leaves (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                leave_type ENUM('Paid Leave', 'Sick Leave', 'Emergency Leave'),
                start_date DATE,
                end_date DATE,
                reason TEXT,
                status ENUM('Pending', 'Approved', 'Rejected') DEFAULT 'Pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        # NEW: Leave Balance Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leave_balance (
                user_id INT PRIMARY KEY,
                paid_leaves INT DEFAULT 0,
                last_updated_month INT DEFAULT 0,
                last_updated_year INT DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        conn.commit()
        logging.info("Database schema initialized successfully (including leave_balance)")
    except Error as err:
        logging.error(f"Error initializing database: {err}")
        flash(f"Error initializing database: {err}", "error")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# Jinja2 custom filters
app.jinja_env.filters['strftime'] = lambda dt, fmt: dt.strftime(fmt) if dt else 'N/A'

# Import and register admin blueprint
from admin import admin_bp
app.register_blueprint(admin_bp)

@app.route('/')
def home():
    logging.info("Accessing home route, redirecting to login")
    return redirect(url_for('login'))

# ==================== LOGIN ROUTE ====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if not email or not password:
            flash("Email and password are required", "error")
            return render_template('login.html')

        conn = get_db_connection()
        if not conn:
            flash("Database connection failed", "error")
            return render_template('login.html')
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['email'] = user['email']
                session['is_admin'] = bool(user['is_admin'])
                session.pop('acting_as_user', None)
                session.permanent = True

                if user['is_admin']:
                    flash("Login successful! Choose your role.", "success")
                    return redirect(url_for('login') + '?show_modal=true')
                else:
                    flash("Login successful!", "success")
                    return redirect(url_for('dashboard'))
            else:
                flash("Invalid credentials", "error")
        except Exception as e:
            logging.error(f"Error in login: {str(e)}")
            flash(f"Login error: {str(e)}", "error")
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()
    return render_template('login.html')

@app.route('/choose_dashboard', methods=['POST'])
def choose_dashboard():
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({"success": False})
    role = request.form.get('role')
    if role == 'admin':
        session.pop('acting_as_user', None)
        return jsonify({"success": True, "redirect": url_for('admin.admin')})
    elif role == 'user':
        session['acting_as_user'] = True
        return jsonify({"success": True, "redirect": url_for('dashboard')})
    return jsonify({"success": False})

# ==================== DASHBOARD WITH LEAVE BALANCE ====================
def update_paid_leave_balance(user_id):
    """Add 1 paid leave per month with carry-forward"""
    conn = get_db_connection()
    if not conn:
        return
    cursor = conn.cursor(dictionary=True)
    now = datetime.now()
    current_month = now.month
    current_year = now.year
    try:
        cursor.execute("SELECT * FROM leave_balance WHERE user_id = %s", (user_id,))
        record = cursor.fetchone()
        if not record:
            cursor.execute("""
                INSERT INTO leave_balance (user_id, paid_leaves, last_updated_month, last_updated_year)
                VALUES (%s, 1, %s, %s)
            """, (user_id, current_month, current_year))
        else:
            months_diff = (current_year - record['last_updated_year']) * 12 + (current_month - record['last_updated_month'])
            if months_diff > 0:
                new_balance = record['paid_leaves'] + months_diff
                cursor.execute("""
                    UPDATE leave_balance SET paid_leaves = %s, last_updated_month = %s, last_updated_year = %s
                    WHERE user_id = %s
                """, (new_balance, current_month, current_year, user_id))
        conn.commit()
    except Exception as e:
        logging.error(f"Error updating leave balance for user {user_id}: {e}")
    finally:
        cursor.close()
        conn.close()

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash("Please login to continue", "error")
        return redirect(url_for('login'))

    if session.get('is_admin') and not session.get('acting_as_user'):
        flash("Admins must choose a role", "error")
        return redirect(url_for('login') + '?show_modal=true')

    # Update paid leave balance automatically
    update_paid_leave_balance(session['user_id'])

    conn = get_db_connection()
    if not conn:
        flash("Database connection failed", "error")
        return render_template('dashboard.html')

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT email, face_image, position, created_at FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        if not user:
            flash("User not found", "error")
            return redirect(url_for('logout'))

        # Attendance logic (unchanged)
        cursor.execute("SELECT login_time, logout_time, daily_status_submitted FROM attendance WHERE user_id = %s AND DATE(login_time) = CURDATE()", (session['user_id'],))
        today_attendance = cursor.fetchone()
        can_login = not bool(today_attendance)
        daily_status_submitted = bool(today_attendance and today_attendance['daily_status_submitted'])
        attendance_submitted = bool(today_attendance and today_attendance['logout_time'])

        cursor.execute("SELECT login_time, logout_time FROM attendance WHERE user_id = %s ORDER BY login_time DESC LIMIT 1", (session['user_id'],))
        last_attendance = cursor.fetchone()

        cursor.execute("""
            SELECT DATE(login_time) as date, attendance_status 
            FROM attendance 
            WHERE user_id = %s AND login_time >= DATE_SUB(CURDATE(), INTERVAL 180 DAY)
            ORDER BY date
        """, (session['user_id'],))
        attendance_data = cursor.fetchall()
        attendance_map = {r['date'].isoformat(): r['attendance_status'] == 'Present' for r in attendance_data}
        attendance_json = json.dumps(attendance_map)

        cursor.execute("SELECT message, created_at FROM notifications WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
        notifications = cursor.fetchall()

        cursor.execute("SELECT update_message, submitted_at, verification_status FROM daily_updates WHERE user_id = %s ORDER BY submitted_at DESC", (session['user_id'],))
        daily_updates = cursor.fetchall()

        cursor.execute("SELECT rota_image FROM rota ORDER BY uploaded_at DESC LIMIT 1")
        rota = cursor.fetchone()
        rota_image_base64 = base64.b64encode(rota['rota_image']).decode('utf-8') if rota and rota['rota_image'] else None

        # Leave History
        cursor.execute("""
            SELECT leave_type, start_date, end_date, status, created_at, reason 
            FROM leaves WHERE user_id = %s ORDER BY created_at DESC
        """, (session['user_id'],))
        user_leaves = cursor.fetchall()

        # Paid Leave Balance
        cursor.execute("SELECT paid_leaves FROM leave_balance WHERE user_id = %s", (session['user_id'],))
        balance_row = cursor.fetchone()
        paid_leave_balance = balance_row['paid_leaves'] if balance_row else 0

        user_face_image_base64 = base64.b64encode(user['face_image']).decode('utf-8') if user['face_image'] else None

        return render_template('dashboard.html',
                              user_email=user['email'],
                              user_face_image_base64=user_face_image_base64,
                              user_position=user['position'],
                              created_at=user['created_at'],
                              last_login=last_attendance['login_time'] if last_attendance else None,
                              last_logout=last_attendance['logout_time'] if last_attendance else None,
                              can_login=can_login,
                              daily_status_submitted=daily_status_submitted,
                              attendance_submitted=attendance_submitted,
                              attendance_data=attendance_json,
                              notifications=notifications,
                              daily_updates=daily_updates,
                              rota_image_base64=rota_image_base64,
                              user_leaves=user_leaves,
                              paid_leave_balance=paid_leave_balance)
    except Exception as e:
        logging.error(f"Dashboard error: {str(e)}")
        flash(f"Error loading dashboard: {str(e)}", "error")
        return render_template('dashboard.html')
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# ==================== APPLY LEAVE WITH BALANCE CHECK ====================
@app.route('/apply_leave', methods=['POST'])
def apply_leave():
    if 'user_id' not in session:
        return jsonify(success=False, message="Not logged in")

    leave_type = request.form.get('leave_type')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    reason = request.form.get('reason')

    if not all([leave_type, start_date, end_date, reason]):
        return jsonify(success=False, message="All fields are required")

    conn = get_db_connection()
    if not conn:
        return jsonify(success=False, message="Database error")

    cursor = conn.cursor(dictionary=True)
    try:
        # Check paid leave balance
        if leave_type == 'Paid Leave':
            cursor.execute("SELECT paid_leaves FROM leave_balance WHERE user_id = %s", (session['user_id'],))
            balance = cursor.fetchone()
            if not balance or balance['paid_leaves'] <= 0:
                return jsonify(success=False, message="No paid leave available")

        # Insert leave request
        cursor.execute("""
            INSERT INTO leaves (user_id, leave_type, start_date, end_date, reason)
            VALUES (%s, %s, %s, %s, %s)
        """, (session['user_id'], leave_type, start_date, end_date, reason))
        conn.commit()

        # Notify admin
        cursor.execute("SELECT email, username FROM users WHERE is_admin = 1 LIMIT 1")
        admin = cursor.fetchone()
        if admin:
            admin_body = f"""
Dear Admin,

A new leave request has been submitted by {session['username']} for your review.

Leave Details:
- Type: {leave_type}
- Start Date: {start_date}
- End Date: {end_date}
- Reason: {reason}

Please log in to the admin dashboard to approve or reject this request.

Best regards,
HR System
            """
            send_email(admin['email'], f"New Leave Request: {leave_type} from {session['username']}", admin_body)

        # Confirmation to user
        user_body = f"""
Dear {session['username']},

Thank you for submitting your leave request. It has been received and is now pending approval by the administrator.

Leave Details:
- Type: {leave_type}
- Start Date: {start_date}
- End Date: {end_date}
- Reason: {reason}

You will be notified via email once a decision has been made.

If you have any questions, please contact HR.

Best regards,
HR System
        """
        send_email(session['email'], f"Leave Request Submitted: {leave_type}", user_body)

        return jsonify(success=True, message="Leave request submitted successfully")
    except Exception as e:
        logging.error(f"Apply leave error: {e}")
        return jsonify(success=False, message="Failed to submit leave request")
    finally:
        cursor.close()
        conn.close()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        face_image = request.files.get('face_image')
        logging.info(f"Register attempt: username={username}, email={email}")

        if not all([username, email, password, face_image]):
            flash("All fields are required", "error")
            logging.error("Missing required fields")
            return render_template('register.html')

        face_image_data = face_image.read()
        if not face_image_data:
            flash("Invalid face image", "error")
            logging.error("Invalid or empty face image")
            return render_template('register.html')

        conn = get_db_connection()
        if not conn:
            logging.error("No database connection for register")
            flash("Database connection failed", "error")
            return render_template('register.html')

        try:
            cursor = conn.cursor()
            hashed_password = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (username, email, password, face_image, is_admin) VALUES (%s, %s, %s, %s, %s)",
                (username, email, hashed_password, face_image_data, 0)
            )
            conn.commit()
            flash("Registration successful! Please login.", "success")
            logging.info(f"User {username} registered successfully")
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            flash("Username or email already exists", "error")
            logging.error(f"Username or email already exists: {username}, {email}")
        except Exception as e:
            flash(f"Registration error: {str(e)}", "error")
            logging.error(f"Registration error: {str(e)}")
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()
    logging.info("Rendering register page")
    return render_template('register.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
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
                    return redirect(url_for('forgot_password'))
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

@app.route('/verify_otp', methods=['POST'])
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
        return redirect(url_for('reset_password'))
    else:
        flash("Invalid OTP", "error")
        logging.error("Invalid OTP provided")
        return redirect(url_for('forgot_password'))

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if not session.get('otp_verified'):
        logging.error("OTP not verified, redirecting to login")
        flash("Please verify OTP first", "error")
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        if not new_password:
            flash("New password is required", "error")
            logging.error("Missing new password")
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
            cursor.execute("UPDATE users SET password = %s WHERE email = %s", (hashed_password, session.get('reset_email')))
            conn.commit()
            session.pop('reset_email', None)
            session.pop('otp_verified', None)
            session.pop('otp_sent', None)
            flash("Password reset successful! Please login.", "success")
            logging.info("Password reset successful")
            return redirect(url_for('login'))
        except Exception as e:
            logging.error(f"Reset password error: {str(e)}")
            flash(f"Reset password error: {str(e)}", "error")
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()
    logging.info("Rendering reset_password page")
    return render_template('reset_password.html')

@app.route('/login_photo', methods=['POST'])
def login_photo():
    if 'user_id' not in session:
        logging.error("Not logged in for login_photo")
        return jsonify({"success": False, "message": "Not logged in"})

    file = request.files.get('face_image')
    if not file:
        logging.error("No photo uploaded for login_photo")
        return jsonify({"success": False, "message": "No photo uploaded"})

    latitude = float(request.form.get('latitude', 0.0))
    longitude = float(request.form.get('longitude', 0.0))

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for login_photo")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor(dictionary=True)
    try:
        logging.info(f"Fetching user face image for user_id: {session['user_id']}")
        cursor.execute("SELECT face_image FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()

        if not user or not user['face_image']:
            logging.error("No registered face image found")
            return jsonify({"success": False, "message": "No registered face image"})

        registered_image = face_recognition.load_image_file(BytesIO(user['face_image']))
        captured_image = face_recognition.load_image_file(file)
        registered_enc = face_recognition.face_encodings(registered_image)
        captured_enc = face_recognition.face_encodings(captured_image)

        if not registered_enc or not captured_enc or not face_recognition.compare_faces([registered_enc[0]], captured_enc[0])[0]:
            logging.error("Face verification failed for login")
            return jsonify({"success": False, "message": "Face verification failed"})

        uploads_dir = os.path.join(app.static_folder, 'Uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        login_time = datetime.now()
        login_photo_path = os.path.join(uploads_dir, f"{session['username']}_login_{login_time.strftime('%Y%m%d%H%M%S')}.jpg")
        file.save(login_photo_path)
        logging.info(f"Login photo saved: {login_photo_path}")

        logging.info(f"Login location: ({latitude}, {longitude})")

        cursor.execute("""
            INSERT INTO attendance (user_id, login_time, login_photo_path, login_latitude, login_longitude, attendance_status) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (session['user_id'], login_time, login_photo_path, latitude, longitude, 'Present'))
        conn.commit()

        with open(login_photo_path, 'rb') as image_file:
            login_photo_base64 = base64.b64encode(image_file.read()).decode('utf-8')

        logging.info("Login recorded successfully")
        return jsonify({
            "success": True,
            "message": "Login recorded",
            "login_photo": login_photo_base64
        })
    except Exception as e:
        logging.error(f"Login photo error: {str(e)}")
        return jsonify({"success": False, "message": f"Error processing login: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/submit_daily_status', methods=['POST'])
def submit_daily_status():
    if 'user_id' not in session:
        logging.error("Not logged in for submit_daily_status")
        return jsonify({"success": False, "message": "Not logged in"})

    daily_status = request.form.get('daily_status')
    if not daily_status:
        logging.error("Daily status is required")
        return jsonify({"success": False, "message": "Daily status is required"})

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for submit_daily_status")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor()
    try:
        logging.info(f"Submitting daily status for user_id: {session['user_id']}")
        cursor.execute("""
            INSERT INTO daily_updates (user_id, update_message) 
            VALUES (%s, %s)
        """, (session['user_id'], daily_status))
        cursor.execute("""
            UPDATE attendance 
            SET daily_status_submitted = 1 
            WHERE user_id = %s AND DATE(login_time) = CURDATE() AND logout_time IS NULL
        """, (session['user_id'],))
        conn.commit()
        logging.info("Daily status submitted successfully")
        return jsonify({"success": True, "message": "Daily status submitted"})
    except Exception as e:
        logging.error(f"Submit daily status error: {str(e)}")
        return jsonify({"success": False, "message": f"Error submitting daily status: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/logout_photo', methods=['POST'])
def logout_photo():
    if 'user_id' not in session:
        logging.error("Not logged in for logout_photo")
        return jsonify({"success": False, "message": "Not logged in"})

    file = request.files.get('face_image')
    if not file:
        logging.error("No photo uploaded for logout_photo")
        return jsonify({"success": False, "message": "No photo uploaded"})

    latitude = float(request.form.get('latitude', 0.0))
    longitude = float(request.form.get('longitude', 0.0))

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for logout_photo")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor(dictionary=True)
    try:
        logging.info(f"Checking daily status for user_id: {session['user_id']}")
        cursor.execute("SELECT daily_status_submitted FROM attendance WHERE user_id = %s AND DATE(login_time) = CURDATE()", (session['user_id'],))
        attendance = cursor.fetchone()
        if not attendance or not attendance['daily_status_submitted']:
            logging.error("Daily status not submitted")
            return jsonify({"success": False, "message": "Please submit your daily status report before logging out"})

        logging.info(f"Fetching user face image for user_id: {session['user_id']}")
        cursor.execute("SELECT face_image FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()

        if not user or not user['face_image']:
            logging.error("No registered face image found")
            return jsonify({"success": False, "message": "No registered face image"})

        registered_image = face_recognition.load_image_file(BytesIO(user['face_image']))
        captured_image = face_recognition.load_image_file(file)
        registered_enc = face_recognition.face_encodings(registered_image)
        captured_enc = face_recognition.face_encodings(captured_image)

        if not registered_enc or not captured_enc or not face_recognition.compare_faces([registered_enc[0]], captured_enc[0])[0]:
            logging.error("Face verification failed for logout")
            return jsonify({"success": False, "message": "Face verification failed"})

        uploads_dir = os.path.join(app.static_folder, 'Uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        logout_time = datetime.now()
        logout_photo_path = os.path.join(uploads_dir, f"{session['username']}_logout_{logout_time.strftime('%Y%m%d%H%M%S')}.jpg")
        file.save(logout_photo_path)
        logging.info(f"Logout photo saved: {logout_photo_path}")

        logging.info(f"Logout location: ({latitude}, {longitude})")

        cursor.execute("""
            UPDATE attendance 
            SET logout_time = %s, logout_photo_path = %s, logout_latitude = %s, logout_longitude = %s 
            WHERE user_id = %s AND logout_time IS NULL 
            ORDER BY login_time DESC 
            LIMIT 1
        """, (logout_time, logout_photo_path, latitude, longitude, session['user_id']))
        conn.commit()

        with open(logout_photo_path, 'rb') as image_file:
            logout_photo_base64 = base64.b64encode(image_file.read()).decode('utf-8')

        logging.info("Logout recorded successfully")
        return jsonify({
            "success": True,
            "message": "Logout recorded",
            "logout_photo": logout_photo_base64
        })
    except Exception as e:
        logging.error(f"Logout photo error: {str(e)}")
        return jsonify({"success": False, "message": f"Error processing logout: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        logging.error("Not logged in for update_profile")
        return jsonify({"success": False, "message": "Not logged in"})

    email = request.form.get('email')
    face_image = request.files.get('face_image')
    position = request.form.get('position')
    logging.info(f"Updating profile for user_id: {session['user_id']}, email={email}, position={position}")

    if not any([email, face_image, position]):
        logging.error("No changes provided for profile update")
        return jsonify({"success": False, "message": "No changes provided"})

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for update_profile")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor()
    try:
        updates = []
        params = []
        if email:
            updates.append("email = %s")
            params.append(email)
        if position:
            updates.append("position = %s")
            params.append(position)
        if face_image:
            face_image_data = face_image.read()
            if not face_image_data:
                logging.error("Invalid or empty face image")
                return jsonify({"success": False, "message": "Invalid face image"})
            updates.append("face_image = %s")
            params.append(face_image_data)

        params.append(session['user_id'])
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
        logging.info(f"Executing profile update query: {query}")
        cursor.execute(query, tuple(params))
        conn.commit()

        cursor.execute("SELECT username, email, position FROM users WHERE id = %s", (session['user_id'],))
        user_data = cursor.fetchone()
        session['username'] = user_data['username']
        session['email'] = user_data['email']
        session['position'] = user_data['position']
        logging.info("Profile updated successfully")
        return jsonify({"success": True, "message": "Profile updated"})
    except mysql.connector.IntegrityError:
        logging.error("Username or email already exists")
        return jsonify({"success": False, "message": "Email already exists"})
    except Exception as e:
        logging.error(f"Profile update error: {str(e)}")
        return jsonify({"success": False, "message": f"Error updating profile: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/check_notifications', methods=['GET'])
def check_notifications():
    if 'user_id' not in session or session.get('is_admin'):
        logging.error("Access denied or admin user for check_notifications")
        return jsonify({"success": False, "message": ""})

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for check_notifications")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor(dictionary=True)
    try:
        logging.info(f"Checking notifications for user_id: {session['user_id']}")
        cursor.execute("""
            SELECT id, message 
            FROM notifications 
            WHERE user_id = %s AND is_read = 0 
            ORDER BY created_at DESC 
            LIMIT 1
        """, (session['user_id'],))
        notification = cursor.fetchone()
        if notification:
            logging.info(f"Marking notification as read: id={notification['id']}")
            cursor.execute("UPDATE notifications SET is_read = 1, read_at = NOW() WHERE id = %s", (notification['id'],))
            conn.commit()
            logging.info(f"Notification read: {notification['message']}")
            return jsonify({"success": True, "message": notification['message']})
        logging.info("No unread notifications found")
        return jsonify({"success": False, "message": ""})
    except Exception as e:
        logging.error(f"Check notifications error: {str(e)}")
        return jsonify({"success": False, "message": f"Error checking notifications: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/logout')
def logout():
    logging.info("Logging out user, clearing session")
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for('login'))


if __name__ == '__main__':
    uploads_dir = os.path.join(app.static_folder, 'Uploads')
    os.makedirs(uploads_dir, exist_ok=True)
    init_db()

    app.run(debug=False, host='0.0.0.0', port=8000)
