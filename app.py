from flask import Flask, request, render_template, jsonify, session, redirect, url_for, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import pooling, Error
import os
import geocoder
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import face_recognition
import numpy as np
import smtplib
from email.mime.text import MIMEText
import random
import base64

app = Flask(__name__)
app.secret_key = "Jhaishna123"

# MySQL Connection Pooling
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "jhaishna",
    "database": "gps_face_db",
    "port": 3306,
    "pool_name": "mypool",
    "pool_size": 5
}

try:
    connection_pool = mysql.connector.pooling.MySQLConnectionPool(**db_config)
    print("✅ Connection pool initialized successfully")
except Error as err:
    print(f"❌ Error creating connection pool: {err}")
    connection_pool = None

def get_db_connection():
    try:
        if connection_pool:
            conn = connection_pool.get_connection()
            print("✅ Successfully retrieved database connection")
            return conn
        else:
            raise Exception("Connection pool is not initialized.")
    except Exception as err:
        print(f"❌ Database connection failed: {err}")
        flash(f"Database connection failed: {err}", "error")
        return None

# Database initialization
def init_db():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            print("🛠️ Initializing database schema")
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
            conn.commit()
            print("✅ Database schema initialized successfully")
        except Error as err:
            print(f"❌ Error initializing database: {err}")
        finally:
            cursor.close()
            conn.close()

# Jinja2 custom filters
app.jinja_env.filters['strftime'] = lambda dt, fmt: dt.strftime(fmt) if dt else 'N/A'

@app.route('/')
def home():
    print("🏠 Accessing home route, redirecting to login")
    return redirect(url_for('login'))

@app.route('/check_admin', methods=['POST'])
def check_admin():
    email = request.json.get('email')
    print(f"🔍 Checking admin status for email: {email}")
    conn = get_db_connection()
    if not conn:
        print("❌ No database connection for check_admin")
        return jsonify({"is_admin": False})
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT is_admin FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        print(f"🔎 Admin check result: {user['is_admin'] if user else False}")
        return jsonify({"is_admin": user['is_admin'] if user else False})
    finally:
        cursor.close()
        conn.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        login_type = request.form.get('login_type')
        print(f"🔐 Login attempt: email={email}, login_type={login_type}")

        conn = get_db_connection()
        if not conn:
            flash("Database connection failed", "error")
            print("❌ Failed to get DB connection")
            return render_template('login.html')
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            print(f"🔎 User query result: {user['id'] if user else 'No user found'}")
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['is_admin'] = user['is_admin'] if login_type == 'admin' else False
                flash("Login successful!", "success")
                print("🔐 Session after login:", dict(session))
                return redirect(url_for('admin' if session['is_admin'] else 'dashboard'))
            else:
                flash("Invalid credentials", "error")
                print("❌ Invalid credentials provided")
        finally:
            cursor.close()
            conn.close()
    print("📄 Rendering login page")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        face_image = request.files.get('face_image')
        print(f"📝 Register attempt: username={username}, email={email}")

        if not all([username, email, password, face_image]):
            flash("All fields are required", "error")
            print("❌ Missing required fields")
            return render_template('register.html')

        face_image_data = face_image.read()

        conn = get_db_connection()
        if not conn:
            print("❌ No database connection for register")
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
            print(f"✅ User {username} registered successfully")
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            flash("Username or email already exists", "error")
            print(f"❌ Username or email already exists: {username}, {email}")
        finally:
            cursor.close()
            conn.close()
    print("📄 Rendering register page")
    return render_template('register.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        print(f"🔑 Forgot password request for email: {email}")
        conn = get_db_connection()
        if not conn:
            print("❌ No database connection for forgot_password")
            return render_template('forgot_password.html')
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            print(f"🔎 User lookup for forgot password: {'Found' if user else 'Not found'}")
            if user:
                otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
                session['otp'] = otp
                session['reset_email'] = email
                session['otp_sent'] = True
                print(f"🔐 Generated OTP: {otp}")

                sender = "kayalahimaja@gmail.com"
                msg = MIMEText(f"Your OTP for password reset is: {otp}\nValid for 10 minutes.")
                msg['Subject'] = "Password Reset OTP"
                msg['From'] = sender
                msg['To'] = email

                try:
                    with smtplib.SMTP('smtp.gmail.com', 587) as server:
                        server.starttls()
                        server.login(sender, "woxjwulhdindtvph")
                        server.send_message(msg)
                    flash("OTP sent to your email!", "success")
                    print(f"📧 OTP email sent to: {email}")
                    return redirect(url_for('forgot_password'))
                except smtplib.SMTPAuthenticationError:
                    flash("Failed to authenticate with email server", "error")
                    print("❌ SMTP authentication failed: Check email and app password")
                    return render_template('forgot_password.html')
                except smtplib.SMTPException as e:
                    flash(f"Failed to send email: {str(e)}", "error")
                    print(f"❌ SMTP error: {str(e)}")
                    return render_template('forgot_password.html')
                except Exception as e:
                    flash(f"Unexpected error sending email: {str(e)}", "error")
                    print(f"❌ Unexpected error in SMTP: {str(e)}")
                    return render_template('forgot_password.html')
            else:
                flash("Email not found", "error")
                print(f"❌ Email not found: {email}")
        finally:
            cursor.close()
            conn.close()
    print("📄 Rendering forgot_password page")
    return render_template('forgot_password.html')

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    otp = request.form.get('otp')
    print(f"🔐 Verifying OTP: {otp}")
    if otp == session.get('otp'):
        session.pop('otp')
        session['otp_verified'] = True
        flash("OTP verified!", "success")
        print("✅ OTP verified successfully")
        return redirect(url_for('reset_password'))
    else:
        flash("Invalid OTP", "error")
        print("❌ Invalid OTP provided")
        return redirect(url_for('forgot_password'))

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if not session.get('otp_verified'):
        print("❌ OTP not verified, redirecting to login")
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        print(f"🔑 Resetting password for email: {session.get('reset_email')}")
        conn = get_db_connection()
        if not conn:
            print("❌ No database connection for reset_password")
            return render_template('reset_password.html')
        try:
            cursor = conn.cursor()
            hashed_password = generate_password_hash(new_password)
            cursor.execute("UPDATE users SET password = %s WHERE email = %s", (hashed_password, session['reset_email']))
            conn.commit()
            session.pop('reset_email')
            session.pop('otp_verified')
            session.pop('otp_sent')
            flash("Password reset successful! Please login.", "success")
            print("✅ Password reset successful")
            return redirect(url_for('login'))
        finally:
            cursor.close()
            conn.close()
    print("📄 Rendering reset_password page")
    return render_template('reset_password.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('is_admin', False) is True:
        flash("Access denied", "error")
        print("🔐 Session after login:", dict(session))
        print("❌ Access denied: User not logged in or is admin")
        return redirect(url_for('login'))

    conn = get_db_connection()
    if not conn:
        print("❌ No database connection for dashboard")
        return render_template('dashboard.html', last_login=None, last_logout=None, rota_image_base64=None)

    cursor = conn.cursor(dictionary=True)
    try:
        print(f"🔍 Fetching user data for user_id: {session['user_id']}")
        cursor.execute("SELECT email, face_image, position, created_at FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        if not user:
            flash("User not found", "error")
            print(f"❌ User not found: user_id={session['user_id']}")
            return redirect(url_for('logout'))

        print(f"🔍 Fetching today's attendance for user_id: {session['user_id']}")
        cursor.execute("SELECT login_time, logout_time, daily_status_submitted FROM attendance WHERE user_id = %s AND DATE(login_time) = CURDATE()", (session['user_id'],))
        today_attendance = cursor.fetchone()
        can_login = not bool(today_attendance)
        daily_status_submitted = bool(today_attendance and today_attendance['daily_status_submitted'])
        attendance_submitted = bool(today_attendance and today_attendance['logout_time'])
        print(f"📅 Today's attendance: {'Found' if today_attendance else 'Not found'}, can_login={can_login}, daily_status_submitted={daily_status_submitted}, attendance_submitted={attendance_submitted}")

        print(f"🔍 Fetching last attendance for user_id: {session['user_id']}")
        cursor.execute("""
            SELECT login_time, logout_time 
            FROM attendance 
            WHERE user_id = %s 
            ORDER BY login_time DESC 
            LIMIT 1
        """, (session['user_id'],))
        last_attendance = cursor.fetchone()
        print(f"📅 Last attendance: {'Found' if last_attendance else 'Not found'}")

        print(f"🔍 Fetching 30-day attendance history for user_id: {session['user_id']}")
        cursor.execute("""
            SELECT DATE(login_time) as date, attendance_status 
            FROM attendance 
            WHERE user_id = %s AND login_time >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        """, (session['user_id'],))
        attendance_data = cursor.fetchall()
        attendance_records = []
        for i in range(30):
            date = (datetime.now() - timedelta(days=i)).date()
            record = next((r for r in attendance_data if r['date'] == date), None)
            attendance_records.append({'date': date, 'present': record['attendance_status'] == 'Present' if record else False})
        print(f"📅 Retrieved {len(attendance_records)} attendance records")

        print(f"🔍 Fetching notifications for user_id: {session['user_id']}")
        cursor.execute("SELECT message, created_at FROM notifications WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
        notifications = cursor.fetchall()
        print(f"🔔 Retrieved {len(notifications)} notifications")

        print(f"🔍 Fetching daily updates for user_id: {session['user_id']}")
        cursor.execute("SELECT update_message, submitted_at, verification_status FROM daily_updates WHERE user_id = %s ORDER BY submitted_at DESC", (session['user_id'],))
        daily_updates = cursor.fetchall()
        print(f"📝 Retrieved {len(daily_updates)} daily updates")

        print("🔍 Fetching latest rota image")
        cursor.execute("SELECT rota_image FROM rota ORDER BY uploaded_at DESC LIMIT 1")
        rota = cursor.fetchone()
        rota_image_base64 = base64.b64encode(rota['rota_image']).decode('utf-8') if rota and rota['rota_image'] else None
        print(f"📅 Rota image: {'Found' if rota else 'Not found'}")

        user_face_image_base64 = base64.b64encode(user['face_image']).decode('utf-8') if user['face_image'] else None
        print(f"🖼️ User face image: {'Found' if user['face_image'] else 'Not found'}")

        print("✅ Rendering dashboard template")
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
                              attendance_records=attendance_records,
                              notifications=notifications,
                              daily_updates=daily_updates,
                              rota_image_base64=rota_image_base64)
    except Exception as e:
        print(f"❌ Dashboard error: {str(e)}")
        flash(f"Error loading dashboard: {str(e)}", "error")
        return render_template('dashboard.html', last_login=None, last_logout=None, rota_image_base64=None)
    finally:
        cursor.close()
        conn.close()

@app.route('/login_photo', methods=['POST'])
def login_photo():
    if 'user_id' not in session:
        print("❌ Not logged in for login_photo")
        return jsonify({"success": False, "message": "Not logged in"})

    file = request.files.get('face_image')
    if not file:
        print("❌ No photo uploaded for login_photo")
        return jsonify({"success": False, "message": "No photo uploaded"})

    conn = get_db_connection()
    if not conn:
        print("❌ No database connection for login_photo")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor(dictionary=True)
    try:
        print(f"🔍 Fetching user face image for user_id: {session['user_id']}")
        cursor.execute("SELECT face_image FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()

        registered_image = face_recognition.load_image_file(BytesIO(user['face_image']))
        captured_image = face_recognition.load_image_file(file)
        registered_enc = face_recognition.face_encodings(registered_image)
        captured_enc = face_recognition.face_encodings(captured_image)

        if not registered_enc or not captured_enc or not face_recognition.compare_faces([registered_enc[0]], captured_enc[0])[0]:
            print("❌ Face verification failed for login")
            return jsonify({"success": False, "message": "Face verification failed"})

        uploads_dir = os.path.join(app.static_folder, 'Uploads')
        login_time = datetime.now()
        login_photo_path = os.path.join(uploads_dir, f"{session['username']}_login_{login_time.strftime('%Y%m%d%H%M%S')}.jpg")
        file.save(login_photo_path)
        print(f"🖼️ Login photo saved: {login_photo_path}")

        g = geocoder.ip('me')
        latitude, longitude = g.latlng if g.latlng else (0.0, 0.0)
        print(f"📍 Login location: ({latitude}, {longitude})")

        cursor.execute("""
            INSERT INTO attendance (user_id, login_time, login_photo_path, login_latitude, login_longitude, attendance_status) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (session['user_id'], login_time, login_photo_path, latitude, longitude, 'Present'))
        conn.commit()
        print("✅ Login recorded successfully")
        return jsonify({"success": True, "message": "Login recorded"})
    finally:
        cursor.close()
        conn.close()

@app.route('/submit_daily_status', methods=['POST'])
def submit_daily_status():
    if 'user_id' not in session:
        print("❌ Not logged in for submit_daily_status")
        return jsonify({"success": False, "message": "Not logged in"})

    daily_status = request.form.get('daily_status')
    if not daily_status:
        print("❌ Daily status is required")
        return jsonify({"success": False, "message": "Daily status is required"})

    conn = get_db_connection()
    if not conn:
        print("❌ No database connection for submit_daily_status")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor()
    try:
        print(f"📝 Submitting daily status for user_id: {session['user_id']}")
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
        print("✅ Daily status submitted successfully")
        return jsonify({"success": True, "message": "Daily status submitted"})
    finally:
        cursor.close()
        conn.close()

@app.route('/logout_photo', methods=['POST'])
def logout_photo():
    if 'user_id' not in session:
        print("❌ Not logged in for logout_photo")
        return jsonify({"success": False, "message": "Not logged in"})

    file = request.files.get('face_image')
    if not file:
        print("❌ No photo uploaded for logout_photo")
        return jsonify({"success": False, "message": "No photo uploaded"})

    conn = get_db_connection()
    if not conn:
        print("❌ No database connection for logout_photo")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor(dictionary=True)
    try:
        print(f"🔍 Checking daily status for user_id: {session['user_id']}")
        cursor.execute("SELECT daily_status_submitted FROM attendance WHERE user_id = %s AND DATE(login_time) = CURDATE()", (session['user_id'],))
        attendance = cursor.fetchone()
        if not attendance or not attendance['daily_status_submitted']:
            print("❌ Daily status not submitted")
            return jsonify({"success": False, "message": "Please submit your daily status report before logging out"})

        print(f"🔍 Fetching user face image for user_id: {session['user_id']}")
        cursor.execute("SELECT face_image FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()

        registered_image = face_recognition.load_image_file(BytesIO(user['face_image']))
        captured_image = face_recognition.load_image_file(file)
        registered_enc = face_recognition.face_encodings(registered_image)
        captured_enc = face_recognition.face_encodings(captured_image)

        if not registered_enc or not captured_enc or not face_recognition.compare_faces([registered_enc[0]], captured_enc[0])[0]:
            print("❌ Face verification failed for logout")
            return jsonify({"success": False, "message": "Face verification failed"})

        uploads_dir = os.path.join(app.static_folder, 'Uploads')
        logout_time = datetime.now()
        logout_photo_path = os.path.join(uploads_dir, f"{session['username']}_logout_{logout_time.strftime('%Y%m%d%H%M%S')}.jpg")
        file.save(logout_photo_path)
        print(f"🖼️ Logout photo saved: {logout_photo_path}")

        g = geocoder.ip('me')
        latitude, longitude = g.latlng if g.latlng else (0.0, 0.0)
        print(f"📍 Logout location: ({latitude}, {longitude})")

        cursor.execute("""
            UPDATE attendance 
            SET logout_time = %s, logout_photo_path = %s, logout_latitude = %s, logout_longitude = %s 
            WHERE user_id = %s AND logout_time IS NULL 
            ORDER BY login_time DESC 
            LIMIT 1
        """, (logout_time, logout_photo_path, latitude, longitude, session['user_id']))
        conn.commit()
        print("✅ Logout recorded successfully")
        return jsonify({"success": True, "message": "Logout recorded"})
    finally:
        cursor.close()
        conn.close()

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        print("❌ Not logged in for update_profile")
        return jsonify({"success": False, "message": "Not logged in"})

    email = request.form.get('email')
    face_image = request.files.get('face_image')
    position = request.form.get('position')
    print(f"🔄 Updating profile for user_id: {session['user_id']}, email={email}, position={position}")

    conn = get_db_connection()
    if not conn:
        print("❌ No database connection for update_profile")
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
            updates.append("face_image = %s")
            params.append(face_image_data)

        if updates:
            params.append(session['user_id'])
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
            print(f"🔄 Executing profile update query: {query}")
            cursor.execute(query, tuple(params))
            conn.commit()
            print("✅ Profile updated successfully")
            return jsonify({"success": True, "message": "Profile updated"})
        print("❌ No changes provided for profile update")
        return jsonify({"success": False, "message": "No changes provided"})
    except mysql.connector.IntegrityError:
        print("❌ Username or email already exists")
        return jsonify({"success": False, "message": "Email already exists"})
    finally:
        cursor.close()
        conn.close()

@app.route('/admin_update_user/<int:user_id>', methods=['POST'])
def admin_update_user(user_id):
    if not session.get('is_admin'):
        print("❌ Access denied for admin_update_user")
        return jsonify({"success": False, "message": "Access denied"})

    username = request.form.get('username')
    email = request.form.get('email')
    position = request.form.get('position')
    face_image = request.files.get('face_image')
    print(f"🔄 Admin updating user: user_id={user_id}, username={username}, email={email}")

    conn = get_db_connection()
    if not conn:
        print("❌ No database connection for admin_update_user")
        return jsonify({"success": False, "message": "Database error"})
    cursor = conn.cursor()
    try:
        updates = []
        params = []
        if username:
            updates.append("username = %s")
            params.append(username)
        if email:
            updates.append("email = %s")
            params.append(email)
        if position:
            updates.append("position = %s")
            params.append(position)
        if face_image:
            face_image_data = face_image.read()
            updates.append("face_image = %s")
            params.append(face_image_data)

        if updates:
            params.append(user_id)
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
            print(f"🔄 Executing admin user update query: {query}")
            cursor.execute(query, tuple(params))
            conn.commit()
            print("✅ User updated by admin")
            return jsonify({"success": True, "message": "User updated"})
        print("❌ No changes provided for admin user update")
        return jsonify({"success": False, "message": "No changes provided"})
    except mysql.connector.IntegrityError:
        print("❌ Username or email already exists for admin update")
        return jsonify({"success": False, "message": "Username or email already exists"})
    finally:
        cursor.close()
        conn.close()

@app.route('/upload_rota', methods=['POST'])
def upload_rota():
    if not session.get('is_admin'):
        print("❌ Access denied for upload_rota")
        return jsonify({"success": False, "message": "Access denied"})

    file = request.files.get('rota_image')
    if not file:
        print("❌ No file uploaded for rota")
        return jsonify({"success": False, "message": "No file uploaded"})

    rota_image_data = file.read()
    print("🖼️ Rota image received")

    conn = get_db_connection()
    if not conn:
        print("❌ No database connection for upload_rota")
        return jsonify({"success": False, "message": "Database error"})
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO rota (rota_image) VALUES (%s)", (rota_image_data,))
        conn.commit()
        print("✅ Rota uploaded successfully")
        return jsonify({"success": True, "message": "Rota uploaded successfully"})
    finally:
        cursor.close()
        conn.close()

@app.route('/send_notification', methods=['POST'])
def send_notification():
    if not session.get('is_admin'):
        print("❌ Access denied for send_notification")
        return jsonify({"success": False, "message": "Access denied"})

    message = request.form.get('message')
    if not message:
        print("❌ No message provided for notification")
        return jsonify({"success": False, "message": "No message provided"})

    conn = get_db_connection()
    if not conn:
        print("❌ No database connection for send_notification")
        return jsonify({"success": False, "message": "Database error"})
    cursor = conn.cursor(dictionary=True)
    try:
        print("🔍 Fetching non-admin users for notification")
        cursor.execute("SELECT id FROM users WHERE is_admin = 0")
        users = cursor.fetchall()
        if not users:
            print("❌ No non-admin users found")
            return jsonify({"success": False, "message": "No non-admin users found"})

        for user in users:
            print(f"🔔 Sending notification to user_id: {user['id']}")
            cursor.execute("INSERT INTO notifications (message, user_id) VALUES (%s, %s)", (message, user['id']))
        conn.commit()
        print("✅ Notifications sent successfully")
        return jsonify({"success": True, "message": "Notification sent to all users"})
    finally:
        cursor.close()
        conn.close()

@app.route('/check_notifications', methods=['GET'])
def check_notifications():
    if 'user_id' not in session or session.get('is_admin'):
        print("❌ Access denied or admin user for check_notifications")
        return jsonify({"success": False, "message": ""})

    conn = get_db_connection()
    if not conn:
        print("❌ No database connection for check_notifications")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor(dictionary=True)
    try:
        print(f"🔔 Checking notifications for user_id: {session['user_id']}")
        cursor.execute("""
            SELECT id, message 
            FROM notifications 
            WHERE user_id = %s AND is_read = 0 
            ORDER BY created_at DESC 
            LIMIT 1
        """, (session['user_id'],))
        notification = cursor.fetchone()
        if notification:
            print(f"🔔 Marking notification as read: id={notification['id']}")
            cursor.execute("UPDATE notifications SET is_read = 1, read_at = NOW() WHERE id = %s", (notification['id'],))
            conn.commit()
            print(f"✅ Notification read: {notification['message']}")
            return jsonify({"success": True, "message": notification['message']})
        print("🔔 No unread notifications found")
        return jsonify({"success": False, "message": ""})
    finally:
        cursor.close()
        conn.close()

@app.route('/admin')
def admin():
    if not session.get('is_admin'):
        flash("Access denied", "error")
        print("❌ Access denied for admin route")
        return redirect(url_for('login'))

    view = request.args.get('view', 'daily')
    search_query = request.args.get('search', '')
    print(f"🔍 Admin view: {view}, search_query: {search_query}")

    conn = get_db_connection()
    if not conn:
        print("❌ No database connection for admin")
        return render_template('admin.html', data=[], view=view, admin_profile=None, users=[], all_attendance=[], rota_image_base64=None)

    cursor = conn.cursor(dictionary=True)
    try:
        print(f"🔍 Fetching admin profile for user_id: {session['user_id']}")
        cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
        admin_profile = cursor.fetchone()
        admin_profile['face_image_base64'] = base64.b64encode(admin_profile['face_image']).decode('utf-8') if admin_profile['face_image'] else None
        print(f"🖼️ Admin profile image: {'Found' if admin_profile['face_image'] else 'Not found'}")

        print("🔍 Fetching non-admin users")
        cursor.execute("SELECT id, username, email, position, face_image FROM users WHERE is_admin = 0")
        users_raw = cursor.fetchall()
        users = []
        for user in users_raw:
            user['face_image_base64'] = base64.b64encode(user['face_image']).decode('utf-8') if user['face_image'] else None
            users.append(user)
        print(f"👥 Retrieved {len(users)} non-admin users")

        if view == 'daily':
            query = """
                SELECT u.username, u.position, a.id as attendance_id, a.user_id, a.login_time, a.logout_time, 
                       a.login_latitude, a.login_longitude, a.logout_latitude, a.logout_longitude,
                       a.daily_status_submitted, a.attendance_status,
                       TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
                FROM users u LEFT JOIN attendance a ON u.id = a.user_id
                WHERE DATE(a.login_time) = CURDATE()
                ORDER BY a.login_time DESC
            """
        elif view == 'weekly':
            query = """
                SELECT u.username, u.position, a.id as attendance_id, a.user_id, a.login_time, a.logout_time, 
                       a.login_latitude, a.login_longitude, a.logout_latitude, a.logout_longitude,
                       a.daily_status_submitted, a.attendance_status,
                       TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
                FROM users u LEFT JOIN attendance a ON u.id = a.user_id
                WHERE WEEK(a.login_time) = WEEK(CURDATE())
                ORDER BY a.login_time DESC
            """
        elif view == 'monthly':
            query = """
                SELECT u.username, u.position, a.id as attendance_id, a.user_id, a.login_time, a.logout_time, 
                       a.login_latitude, a.login_longitude, a.logout_latitude, a.logout_longitude,
                       a.daily_status_submitted, a.attendance_status,
                       TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
                FROM users u LEFT JOIN attendance a ON u.id = a.user_id
                WHERE MONTH(a.login_time) = MONTH(CURDATE())
                ORDER BY a.login_time DESC
            """
        else:  # yearly
            query = """
                SELECT u.username, u.position, a.id as attendance_id, a.user_id, a.login_time, a.logout_time, 
                       a.login_latitude, a.login_longitude, a.logout_latitude, a.logout_longitude,
                       a.daily_status_submitted, a.attendance_status,
                       TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
                FROM users u LEFT JOIN attendance a ON u.id = a.user_id
                WHERE YEAR(a.login_time) = YEAR(CURDATE())
                ORDER BY a.login_time DESC
            """
        print(f"🔍 Executing attendance query for view: {view}")
        cursor.execute(query)
        data = cursor.fetchall()

        for record in data:
            if record['seconds_worked']:
                hours = record['seconds_worked'] // 3600
                minutes = (record['seconds_worked'] % 3600) // 60
                seconds = record['seconds_worked'] % 60
                record['hours_worked'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                record['color'] = 'red' if hours < 9 else 'green'
            else:
                record['hours_worked'] = "N/A"
                record['color'] = 'black'
        print(f"📅 Processed {len(data)} attendance records for view: {view}")

        if search_query:
            print(f"🔍 Executing search query: {search_query}")
            cursor.execute("""
                SELECT u.username, u.position, a.id as attendance_id, a.user_id, a.login_time, a.logout_time, 
                       a.login_latitude, a.login_longitude, a.logout_latitude, a.logout_longitude,
                       a.daily_status_submitted, a.attendance_status,
                       TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
                FROM users u LEFT JOIN attendance a ON u.id = a.user_id
                WHERE u.username LIKE %s
                ORDER BY a.login_time DESC
            """, (f"%{search_query}%",))
        else:
            print("🔍 Fetching all attendance records")
            cursor.execute("""
                SELECT u.username, u.position, a.id as attendance_id, a.user_id, a.login_time, a.logout_time, 
                       a.login_latitude, a.login_longitude, a.logout_latitude, a.logout_longitude,
                       a.daily_status_submitted, a.attendance_status,
                       TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
                FROM users u LEFT JOIN attendance a ON u.id = a.user_id
                ORDER BY a.login_time DESC
            """)
        all_attendance = cursor.fetchall()

        for record in all_attendance:
            if record['seconds_worked']:
                hours = record['seconds_worked'] // 3600
                minutes = (record['seconds_worked'] % 3600) // 60
                seconds = record['seconds_worked'] % 60
                record['hours_worked'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                record['color'] = 'red' if hours < 9 else 'green'
            else:
                record['hours_worked'] = "N/A"
                record['color'] = 'black'
        print(f"📅 Processed {len(all_attendance)} total attendance records")

        print("🔍 Fetching latest rota image for admin")
        cursor.execute("SELECT rota_image FROM rota ORDER BY uploaded_at DESC LIMIT 1")
        rota = cursor.fetchone()
        rota_image_base64 = base64.b64encode(rota['rota_image']).decode('utf-8') if rota and rota['rota_image'] else None
        print(f"🖼️ Rota image: {'Found' if rota else 'Not found'}")

        print("🔍 Fetching read notifications")
        cursor.execute("""
            SELECT n.id, n.message, n.created_at, n.read_at, u.username 
            FROM notifications n 
            JOIN users u ON n.user_id = u.id 
            WHERE n.is_read = 1 
            ORDER BY n.read_at DESC
        """)
        read_notifications = cursor.fetchall()
        print(f"🔔 Retrieved {len(read_notifications)} read notifications")

        print("✅ Rendering admin template")
        return render_template('admin.html', data=data, view=view, admin_profile=admin_profile, users=users, all_attendance=all_attendance,
                              search_query=search_query, rota_image_base64=rota_image_base64, read_notifications=read_notifications)
    finally:
        cursor.close()
        conn.close()

@app.route('/update_attendance_status/<int:attendance_id>', methods=['POST'])
def update_attendance_status(attendance_id):
    if not session.get('is_admin'):
        print("❌ Access denied for update_attendance_status")
        return jsonify({"success": False, "message": "Access denied"})

    status = request.form.get('status')
    print(f"🔄 Updating attendance status: attendance_id={attendance_id}, status={status}")
    if status not in ['Present', 'Absent']:
        print("❌ Invalid status provided")
        return jsonify({"success": False, "message": "Invalid status"})

    conn = get_db_connection()
    if not conn:
        print("❌ No database connection for update_attendance_status")
        return jsonify({"success": False, "message": "Database error"})
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE attendance SET attendance_status = %s WHERE id = %s", (status, attendance_id))
        conn.commit()
        print("✅ Attendance status updated")
        return jsonify({"success": True, "message": "Attendance status updated"})
    finally:
        cursor.close()
        conn.close()

@app.route('/view_excel')
def view_excel():
    if not session.get('is_admin'):
        flash("Access denied", "error")
        print("❌ Access denied for view_excel")
        return redirect(url_for('login'))

    conn = get_db_connection()
    if not conn:
        flash("Database connection failed", "error")
        print("❌ No database connection for view_excel")
        return render_template('view_excel.html', table="")

    cursor = conn.cursor(dictionary=True)
    try:
        print("🔍 Fetching attendance data for Excel view")
        cursor.execute("""
            SELECT u.username, a.login_time, a.logout_time, a.daily_status_submitted, a.attendance_status,
                   TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
            FROM users u LEFT JOIN attendance a ON u.id = a.user_id
        """)
        data = cursor.fetchall()
        if not data:
            flash("No attendance data available", "warning")
            print("⚠️ No attendance data available")
            return render_template('view_excel.html', table="")

        for record in data:
            if record['seconds_worked']:
                hours = record['seconds_worked'] // 3600
                minutes = (record['seconds_worked'] % 3600) // 60
                seconds = record['seconds_worked'] % 60
                record['hours_worked'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                record['hours_worked'] = "N/A"
        print(f"📅 Processed {len(data)} attendance records for Excel view")

        df = pd.DataFrame(data)[['username', 'login_time', 'logout_time', 'daily_status_submitted', 'attendance_status', 'hours_worked']]
        html_table = df.to_html(index=False, classes='table table-striped')
        print("✅ Rendering Excel view template")
        return render_template('view_excel.html', table=html_table)
    except Exception as e:
        flash(f"Error generating table: {str(e)}", "error")
        print(f"❌ Error generating Excel table: {str(e)}")
        return render_template('view_excel.html', table="")
    finally:
        cursor.close()
        conn.close()

@app.route('/export_page')
def export_page():
    if not session.get('is_admin'):
        flash("Access denied", "error")
        print("❌ Access denied for export_page")
        return redirect(url_for('login'))
    print("📄 Rendering export page")
    return render_template('export.html')

@app.route('/export')
def export():
    if not session.get('is_admin'):
        flash("Access denied", "error")
        print("❌ Access denied for export")
        return redirect(url_for('login'))

    conn = get_db_connection()
    if not conn:
        flash("Database connection failed", "error")
        print("❌ No database connection for export")
        return redirect(url_for('admin'))

    cursor = conn.cursor(dictionary=True)
    try:
        print("🔍 Fetching attendance data for Excel export")
        cursor.execute("""
            SELECT u.username, a.login_time, a.logout_time, a.daily_status_submitted, a.attendance_status,
                   TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
            FROM users u LEFT JOIN attendance a ON u.id = a.user_id
        """)
        data = cursor.fetchall()
        if not data:
            flash("No attendance data to export", "warning")
            print("⚠️ No attendance data to export")
            return redirect(url_for('admin'))

        for record in data:
            if record['seconds_worked']:
                hours = record['seconds_worked'] // 3600
                minutes = (record['seconds_worked'] % 3600) // 60
                seconds = record['seconds_worked'] % 60
                record['hours_worked'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                record['hours_worked'] = "N/A"
        print(f"📅 Processed {len(data)} attendance records for export")

        df = pd.DataFrame(data)[['username', 'login_time', 'logout_time', 'daily_status_submitted', 'attendance_status', 'hours_worked']]
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Attendance', index=False)
            workbook = writer.book
            worksheet = writer.sheets['Attendance']
            worksheet.set_column('A:A', 20)
            worksheet.set_column('B:C', 20)
            worksheet.set_column('D:D', 30)
            worksheet.set_column('E:E', 15)
            worksheet.set_column('F:F', 15)
        output.seek(0)
        print("✅ Excel file generated successfully")
        return send_file(output, download_name='attendance.xlsx', as_attachment=True)
    except Exception as e:
        flash(f"Error generating Excel file: {str(e)}", "error")
        print(f"❌ Error generating Excel file: {str(e)}")
        return redirect(url_for('admin'))
    finally:
        cursor.close()
        conn.close()

@app.route('/logout')
def logout():
    print("🔐 Logging out user, clearing session")
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for('login'))

if __name__ == '__main__':
    uploads_dir = os.path.join(app.static_folder, 'Uploads')
    os.makedirs(uploads_dir, exist_ok=True)
    print("🛠️ Creating uploads directory if not exists")
    init_db()
    print("🚀 Starting Flask application on port 8000")
    app.run(debug=True, host='0.0.0.0', port=8000)
