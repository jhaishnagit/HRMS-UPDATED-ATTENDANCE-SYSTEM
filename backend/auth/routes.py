from flask import Blueprint, request, render_template, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from utils import get_db_connection
import random

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
            session['email'] = user['email']
            session['position'] = user['position']
        
            # 🔥 ADD THIS LINE
            session['is_admin'] = 1 if user['position'] == 'Admin' else 0

            return redirect('/dashboard')
        else:
            flash("Invalid credentials")

    return render_template('login.html')


# REGISTER
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = generate_password_hash(request.form.get('password'))

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO users (username,email,password) VALUES (%s,%s,%s)",
            (username, email, password)
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

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        if user:
            # simple reset (for now)
            new_password = "123456"
            hashed = generate_password_hash(new_password)

            cursor.execute(
                "UPDATE users SET password=%s WHERE email=%s",
                (hashed, email)
            )
            conn.commit()

            flash("Password reset to 123456")
            return redirect('/auth/login')
        else:
            flash("Email not found")

    return render_template('forgot_password.html')