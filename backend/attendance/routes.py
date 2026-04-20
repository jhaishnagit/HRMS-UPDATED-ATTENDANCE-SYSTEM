from flask import Blueprint, request, jsonify, session
from utils import get_db_connection
from datetime import datetime

attendance_bp = Blueprint('attendance', __name__)

# ✅ LOGIN PHOTO (INSERT ATTENDANCE)
@attendance_bp.route('/login_photo', methods=['POST'])
def login_photo():
    try:
        if 'user_id' not in session:
            return jsonify({"success": False, "message": "Not logged in"})

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO attendance (user_id, login_time, attendance_status)
            VALUES (%s, %s, %s)
        """, (session['user_id'], datetime.now(), 'Present'))

        conn.commit()

        return jsonify({"success": True})

    except Exception as e:
        print("🔥 ERROR:", str(e))
        return jsonify({"success": False, "message": str(e)})


# ✅ LOGOUT PHOTO (UPDATE ATTENDANCE)
@attendance_bp.route('/logout_photo', methods=['POST'])
def logout_photo():
    try:
        if 'user_id' not in session:
            return jsonify({"success": False})

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE attendance 
            SET logout_time=%s 
            WHERE user_id=%s 
            ORDER BY id DESC LIMIT 1
        """, (datetime.now(), session['user_id']))

        conn.commit()

        return jsonify({"success": True})

    except Exception as e:
        print("🔥 ERROR:", str(e))
        return jsonify({"success": False, "message": str(e)})


@attendance_bp.route('/submit_daily_status', methods=['POST'])
def submit_daily_status():
    try:
        if 'user_id' not in session:
            return jsonify({"success": False})

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE attendance
            SET daily_status_submitted = 1
            WHERE user_id=%s
            ORDER BY id DESC LIMIT 1
        """, (session['user_id'],))

        conn.commit()

        return jsonify({"success": True})

    except Exception as e:
        print("🔥 ERROR:", str(e))
        return jsonify({"success": False, "message": str(e)})


# ✅ NOTIFICATIONS
@attendance_bp.route('/check_notifications')
def check_notifications():
    return jsonify({"success": True, "message": None})