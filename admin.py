# admin.py
from flask import Blueprint, request, render_template, jsonify, session, flash, redirect, url_for, send_file
import mysql.connector
from mysql.connector import Error
import os
import pandas as pd
from io import BytesIO
from datetime import datetime
import base64
import logging
from dotenv import load_dotenv
import json
from utils import send_email

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
        return None

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin')
def admin():
    logging.info(f"Accessing admin route with session: {dict(session)}")
    if not session.get('is_admin'):
        flash("Access denied", "error")
        logging.error("Access denied for admin route")
        return redirect(url_for('login'))

    view = request.args.get('view', 'daily')
    search_query = request.args.get('search', '')
    logging.info(f"Admin view: {view}, search_query: {search_query}")

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for admin")
        flash("Database connection failed", "error")
        return render_template('admin.html', data=[], view=view, admin_profile=None, users=[], all_attendance=[], rota_image_base64=None)

    cursor = conn.cursor(dictionary=True)
    try:
        logging.info(f"Fetching admin profile for user_id: {session['user_id']}")
        cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
        admin_profile = cursor.fetchone()
        admin_profile['face_image_base64'] = base64.b64encode(admin_profile['face_image']).decode('utf-8') if admin_profile and admin_profile['face_image'] else None
        logging.info(f"Admin profile image: {'Found' if admin_profile and admin_profile['face_image'] else 'Not found'}")

        logging.info("Fetching non-admin users")
        cursor.execute("SELECT id, username, email, position, face_image FROM users WHERE is_admin = 0")
        users_raw = cursor.fetchall()
        users = []
        for user in users_raw:
            user['face_image_base64'] = base64.b64encode(user['face_image']).decode('utf-8') if user['face_image'] else None
            users.append(user)
        logging.info(f"Retrieved {len(users)} non-admin users")

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
        logging.info(f"Executing attendance query for view: {view}")
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
        logging.info(f"Processed {len(data)} attendance records for view: {view}")

        if search_query:
            logging.info(f"Executing search query: {search_query}")
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
            logging.info("Fetching all attendance records")
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
        logging.info(f"Processed {len(all_attendance)} total attendance records")

        logging.info("Fetching latest rota image for admin")
        cursor.execute("SELECT rota_image FROM rota ORDER BY uploaded_at DESC LIMIT 1")
        rota = cursor.fetchone()
        rota_image_base64 = base64.b64encode(rota['rota_image']).decode('utf-8') if rota and rota['rota_image'] else None
        logging.info(f"Rota image: {'Found' if rota else 'Not found'}")

        logging.info("Fetching read notifications")
        cursor.execute("""
            SELECT n.id, n.message, n.created_at, n.read_at, u.username 
            FROM notifications n 
            JOIN users u ON n.user_id = u.id 
            WHERE n.is_read = 1 
            ORDER BY n.read_at DESC
        """)
        read_notifications = cursor.fetchall()
        logging.info(f"Retrieved {len(read_notifications)} read notifications")

        logging.info("Rendering admin template")
        return render_template('admin.html', data=data, view=view, admin_profile=admin_profile, users=users, all_attendance=all_attendance,
                              search_query=search_query, rota_image_base64=rota_image_base64, read_notifications=read_notifications)
    except Exception as e:
        logging.error(f"Admin route error: {str(e)}")
        flash(f"Error loading admin page: {str(e)}", "error")
        return render_template('admin.html', data=[], view=view, admin_profile=None, users=[], all_attendance=[], rota_image_base64=None)
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@admin_bp.route('/admin_leaves')
def admin_leaves():
    if not session.get('is_admin'):
        flash("Access denied", "error")
        return redirect(url_for('login'))

    conn = get_db_connection()
    if not conn:
        flash("Database connection failed", "error")
        return render_template('admin_leaves.html', leaves=[])

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT l.id, l.leave_type, l.start_date, l.end_date, l.reason, l.status, l.created_at,
                   u.username, u.email 
            FROM leaves l 
            JOIN users u ON l.user_id = u.id 
            ORDER BY l.created_at DESC
        """)
        leaves = cursor.fetchall()
        return render_template('admin_leaves.html', leaves=leaves)
    except Exception as e:
        logging.error(f"Admin leaves error: {str(e)}")
        flash(f"Error loading leaves: {str(e)}", "error")
        return render_template('admin_leaves.html', leaves=[])
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@admin_bp.route('/update_leave_status/<int:leave_id>', methods=['POST'])
def update_leave_status(leave_id):
    if not session.get('is_admin'):
        return jsonify({"success": False, "message": "Access denied"})

    status = request.form.get('status')
    if status not in ['Approved', 'Rejected']:
        return jsonify({"success": False, "message": "Invalid status"})

    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor(dictionary=True)  # ← FIXED: dictionary cursor
    try:
        cursor.execute("SELECT user_id, leave_type, start_date, reason FROM leaves WHERE id = %s", (leave_id,))
        leave = cursor.fetchone()
        if not leave:
            return jsonify({"success": False, "message": "Leave not found"})

        cursor.execute("UPDATE leaves SET status = %s, updated_at = NOW() WHERE id = %s", (status, leave_id))
        conn.commit()

        # Fetch user info
        cursor.execute("SELECT email, username FROM users WHERE id = %s", (leave['user_id'],))
        user = cursor.fetchone()

        if user:
            status_lower = status.lower()
            leave_body = f"""
Dear {user['username']},

We are pleased to inform you that your leave request has been {status_lower}.

Leave Details:
- Type: {leave['leave_type']}
- Start Date: {leave['start_date']}
- Reason: {leave['reason']}

If {status_lower} == 'approved', please plan accordingly. If rejected, we appreciate your understanding and encourage resubmission if needed.

For any questions, contact HR.

Best regards,
HR Administration Team
            """
            send_email(user['email'], f"Leave Request {status}: {leave['leave_type']}", leave_body)

            cursor.execute("INSERT INTO notifications (message, user_id) VALUES (%s, %s)", 
                          (f"Your leave request has been {status_lower}.", leave['user_id']))
            conn.commit()

        logging.info(f"Leave status updated: ID {leave_id} to {status}")
        return jsonify({"success": True, "message": "Status updated successfully"})
    except Exception as e:
        logging.error(f"Update leave status error: {str(e)}")
        return jsonify({"success": False, "message": f"Error updating status: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@admin_bp.route('/admin_update_user/<int:user_id>', methods=['POST'])
def admin_update_user(user_id):
    if not session.get('is_admin'):
        logging.error("Access denied for admin_update_user")
        return jsonify({"success": False, "message": "Access denied"})

    username = request.form.get('username')
    email = request.form.get('email')
    position = request.form.get('position')
    face_image = request.files.get('face_image')
    logging.info(f"Admin updating user: user_id={user_id}, username={username}, email={email}")

    if not any([username, email, position, face_image]):
        logging.error("No changes provided for admin user update")
        return jsonify({"success": False, "message": "No changes provided"})

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for admin_update_user")
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
            if not face_image_data:
                logging.error("Invalid or empty face image")
                return jsonify({"success": False, "message": "Invalid face image"})
            updates.append("face_image = %s")
            params.append(face_image_data)

        params.append(user_id)
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
        logging.info(f"Executing admin user update query: {query}")
        cursor.execute(query, tuple(params))
        conn.commit()
        logging.info("User updated by admin")
        return jsonify({"success": True, "message": "User updated"})
    except mysql.connector.IntegrityError:
        logging.error("Username or email already exists for admin update")
        return jsonify({"success": False, "message": "Username or email already exists"})
    except Exception as e:
        logging.error(f"Admin user update error: {str(e)}")
        return jsonify({"success": False, "message": f"Error updating user: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@admin_bp.route('/upload_rota', methods=['POST'])
def upload_rota():
    if not session.get('is_admin'):
        logging.error("Access denied for upload_rota")
        return jsonify({"success": False, "message": "Access denied"})

    file = request.files.get('rota_image')
    if not file:
        logging.error("No file uploaded for rota")
        return jsonify({"success": False, "message": "No file uploaded"})

    rota_image_data = file.read()
    if not rota_image_data:
        logging.error("Invalid or empty rota image")
        return jsonify({"success": False, "message": "Invalid rota image"})

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for upload_rota")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO rota (rota_image) VALUES (%s)", (rota_image_data,))
        conn.commit()
        logging.info("Rota uploaded successfully")
        return jsonify({"success": True, "message": "Rota uploaded successfully"})
    except Exception as e:
        logging.error(f"Rota upload error: {str(e)}")
        return jsonify({"success": False, "message": f"Error uploading rota: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@admin_bp.route('/send_notification', methods=['POST'])
def send_notification():
    if not session.get('is_admin'):
        logging.error("Access denied for send_notification")
        return jsonify({"success": False, "message": "Access denied"})

    message = request.form.get('message')
    if not message:
        logging.error("No message provided for notification")
        return jsonify({"success": False, "message": "No message provided"})

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for send_notification")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor(dictionary=True)
    try:
        logging.info("Fetching non-admin users for notification")
        cursor.execute("SELECT id FROM users WHERE is_admin = 0")
        users = cursor.fetchall()
        if not users:
            logging.error("No non-admin users found")
            return jsonify({"success": False, "message": "No non-admin users found"})

        for user in users:
            logging.info(f"Sending notification to user_id: {user['id']}")
            cursor.execute("INSERT INTO notifications (message, user_id) VALUES (%s, %s)", (message, user['id']))
        conn.commit()
        logging.info("Notifications sent successfully")
        return jsonify({"success": True, "message": "Notification sent to all users"})
    except Exception as e:
        logging.error(f"Notification error: {str(e)}")
        return jsonify({"success": False, "message": f"Error sending notification: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@admin_bp.route('/update_attendance_status/<int:attendance_id>', methods=['POST'])
def update_attendance_status(attendance_id):
    if not session.get('is_admin'):
        logging.error("Access denied for update_attendance_status")
        return jsonify({"success": False, "message": "Access denied"})

    status = request.form.get('status')
    logging.info(f"Updating attendance status: attendance_id={attendance_id}, status={status}")
    if status not in ['Present', 'Absent']:
        logging.error("Invalid status provided")
        return jsonify({"success": False, "message": "Invalid status"})

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for update_attendance_status")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE attendance SET attendance_status = %s WHERE id = %s", (status, attendance_id))
        conn.commit()
        logging.info("Attendance status updated")
        return jsonify({"success": True, "message": "Attendance status updated"})
    except Exception as e:
        logging.error(f"Update attendance status error: {str(e)}")
        return jsonify({"success": False, "message": f"Error updating attendance status: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@admin_bp.route('/view_excel')
def view_excel():
    if not session.get('is_admin'):
        flash("Access denied", "error")
        logging.error("Access denied for view_excel")
        return redirect(url_for('login'))

    conn = get_db_connection()
    if not conn:
        flash("Database connection failed", "error")
        logging.error("No database connection for view_excel")
        return render_template('view_excel.html', table="")

    cursor = conn.cursor(dictionary=True)
    try:
        logging.info("Fetching attendance data for Excel view")
        cursor.execute("""
            SELECT u.username, a.login_time, a.logout_time, a.daily_status_submitted, a.attendance_status,
                   TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
            FROM users u LEFT JOIN attendance a ON u.id = a.user_id
        """)
        data = cursor.fetchall()
        if not data:
            flash("No attendance data available", "warning")
            logging.warning("No attendance data available")
            return render_template('view_excel.html', table="")

        for record in data:
            if record['seconds_worked']:
                hours = record['seconds_worked'] // 3600
                minutes = (record['seconds_worked'] % 3600) // 60
                seconds = record['seconds_worked'] % 60
                record['hours_worked'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                record['hours_worked'] = "N/A"
        logging.info(f"Processed {len(data)} attendance records for Excel view")

        df = pd.DataFrame(data)[['username', 'login_time', 'logout_time', 'daily_status_submitted', 'attendance_status', 'hours_worked']]
        html_table = df.to_html(index=False, classes='table table-striped')
        logging.info("Rendering Excel view template")
        return render_template('view_excel.html', table=html_table)
    except Exception as e:
        flash(f"Error generating table: {str(e)}", "error")
        logging.error(f"Error generating Excel table: {str(e)}")
        return render_template('view_excel.html', table="")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


@admin_bp.route('/approve_leave/<int:leave_id>', methods=['POST'])
def approve_leave(leave_id):
    if not session.get('is_admin'):
        return jsonify(success=False, message="Access denied")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT user_id, leave_type FROM leaves WHERE id = %s", (leave_id,))
        leave = cursor.fetchone()
        if not leave:
            return jsonify(success=False, message="Leave not found")

        # Deduct paid leave if applicable
        if leave['leave_type'] == 'Paid Leave':
            cursor.execute("""
                UPDATE leave_balance 
                SET paid_leaves = GREATEST(paid_leaves - 1, 0)
                WHERE user_id = %s
            """, (leave['user_id'],))

        cursor.execute("UPDATE leaves SET status = 'Approved' WHERE id = %s", (leave_id,))
        conn.commit()

        # Notify user
        cursor.execute("SELECT email, username FROM users WHERE id = %s", (leave['user_id'],))
        user = cursor.fetchone()
        if user:
            approve_body = f"""
Dear {user['username']},

Congratulations! Your leave request has been APPROVED by the administration.

Leave Details:
- Type: {leave['leave_type']}
- Period: [Start Date] to [End Date] (Note: Exact dates to be inserted if available)

We wish you a refreshing and productive break. Please ensure all handover tasks are completed before your leave begins.

If you have any questions, feel free to reach out to HR.

Warm regards,
HR Administration Team
            """
            send_email(user['email'], f"Leave Request Approved: {leave['leave_type']}", approve_body)

        return jsonify(success=True, message="Leave approved")
    except Exception as e:
        logging.error(f"Approve leave error: {e}")
        return jsonify(success=False, message="Error")
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/reject_leave/<int:leave_id>', methods=['POST'])
def reject_leave(leave_id):
    if not session.get('is_admin'):
        return jsonify(success=False)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE leaves SET status = 'Rejected' WHERE id = %s", (leave_id,))
        conn.commit()
        return jsonify(success=True, message="Leave rejected")
    except Exception as e:
        return jsonify(success=False)
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/export_page')
def export_page():
    if not session.get('is_admin'):
        flash("Access denied", "error")
        logging.error("Access denied for export_page")
        return redirect(url_for('login'))
    logging.info("Rendering export page")
    return render_template('export.html')

@admin_bp.route('/export')
def export():
    if not session.get('is_admin'):
        flash("Access denied", "error")
        logging.error("Access denied for export")
        return redirect(url_for('admin.admin'))

    conn = get_db_connection()
    if not conn:
        flash("Database connection failed", "error")
        logging.error("No database connection for export")
        return redirect(url_for('admin.admin'))

    cursor = conn.cursor(dictionary=True)
    try:
        logging.info("Fetching attendance data for Excel export")
        cursor.execute("""
            SELECT u.username, a.login_time, a.logout_time, a.daily_status_submitted, a.attendance_status,
                   TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
            FROM users u LEFT JOIN attendance a ON u.id = a.user_id
        """)
        data = cursor.fetchall()
        if not data:
            flash("No attendance data to export", "warning")
            logging.warning("No attendance data to export")
            return redirect(url_for('admin.admin'))

        for record in data:
            if record['seconds_worked']:
                hours = record['seconds_worked'] // 3600
                minutes = (record['seconds_worked'] % 3600) // 60
                seconds = record['seconds_worked'] % 60
                record['hours_worked'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                record['hours_worked'] = "N/A"
        logging.info(f"Processed {len(data)} attendance records for export")

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
        logging.info("Excel file generated successfully")
        return send_file(output, download_name='attendance.xlsx', as_attachment=True)
    except Exception as e:
        flash(f"Error generating Excel file: {str(e)}", "error")
        logging.error(f"Error generating Excel file: {str(e)}")
        return redirect(url_for('admin.admin'))
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
