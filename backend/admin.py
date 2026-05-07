# admin.py
from fileinput import filename

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

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
            return conn
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
        return redirect(url_for('auth.login'))

    view = request.args.get('view', 'daily')
    search_query = request.args.get('search', '')

    conn = get_db_connection()
    if not conn:
        flash("Database connection failed", "error")
        return render_template('admin.html', data=[], view=view, admin_profile=None,
                               users=[], all_attendance=[], rota_image_base64=None,
                               holiday_table=None)

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
        admin_profile = cursor.fetchone()
        admin_profile['face_image_base64'] = base64.b64encode(admin_profile['face_image']).decode('utf-8') \
            if admin_profile and admin_profile['face_image'] else None

        cursor.execute("SELECT id, username, email, position, face_image FROM users WHERE is_admin = 0")
        users_raw = cursor.fetchall()
        users = []
        for user in users_raw:
            user['face_image_base64'] = base64.b64encode(user['face_image']).decode('utf-8') \
                if user['face_image'] else None
            users.append(user)

        view_filters = {
            'daily': "DATE(a.login_time) = CURDATE()",
            'weekly': "WEEK(a.login_time) = WEEK(CURDATE())",
            'monthly': "MONTH(a.login_time) = MONTH(CURDATE())",
            'yearly': "YEAR(a.login_time) = YEAR(CURDATE())",
        }
        where_clause = view_filters.get(view, "DATE(a.login_time) = CURDATE()")

        query = f"""
            SELECT u.username, u.position, a.id as attendance_id, a.user_id, a.login_time, a.logout_time,
                   a.login_latitude, a.login_longitude, a.logout_latitude, a.logout_longitude,
                   a.daily_status_submitted, a.attendance_status,
                   TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
            FROM users u LEFT JOIN attendance a ON u.id = a.user_id
            WHERE {where_clause}
            ORDER BY a.login_time DESC
        """
        cursor.execute(query)
        data = cursor.fetchall()

        def process_records(records):
            for record in records:
                if record['seconds_worked']:
                    h = record['seconds_worked'] // 3600
                    m = (record['seconds_worked'] % 3600) // 60
                    s = record['seconds_worked'] % 60
                    record['hours_worked'] = f"{h:02d}:{m:02d}:{s:02d}"
                    record['color'] = 'red' if h < 9 else 'green'
                else:
                    record['hours_worked'] = "N/A"
                    record['color'] = 'black'

        # 👉 Only ONE query (this is the fix)

        if search_query:
            cursor.execute("""
                SELECT u.username, u.position,
                       a.id as attendance_id, a.user_id,
                       a.login_time, a.logout_time,
                       a.daily_status_submitted, a.attendance_status,
                       TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
                FROM users u
                INNER JOIN attendance a ON u.id = a.user_id
                WHERE u.username LIKE %s
                ORDER BY a.login_time DESC
            """, (f"%{search_query}%",))
        else:
            cursor.execute(query)

        data = cursor.fetchall()

        # process data
        process_records(data)

        # use same data everywhere
        all_attendance = data

        # ── Rota (image) ──────────────────────────────────────────────────
        cursor.execute("SELECT rota_image FROM rota ORDER BY id DESC LIMIT 1")
        rota_row = cursor.fetchone()
        rota_image_base64 = None
        if rota_row and rota_row.get('rota_image'):
            rota_image_base64 = base64.b64encode(rota_row['rota_image']).decode('utf-8')

        # ── Holiday table (HTML string) ───────────────────────────────────
        cursor.execute("SELECT holiday_table FROM rota ORDER BY id DESC LIMIT 1")
        holiday_row = cursor.fetchone()
        holiday_table = None
        if holiday_row and holiday_row.get('holiday_table'):
            holiday_table = holiday_row['holiday_table']

        cursor.execute("""
            SELECT n.id, n.message, n.created_at, n.read_at, u.username
            FROM notifications n
            JOIN users u ON n.user_id = u.id
            WHERE n.is_read = 1
            ORDER BY n.read_at DESC
        """)
        read_notifications = cursor.fetchall()

        return render_template('admin.html', data=data, view=view, admin_profile=admin_profile,
                               users=users, all_attendance=all_attendance, search_query=search_query,
                               rota_image_base64=rota_image_base64,
                               holiday_table=holiday_table,
                               read_notifications=read_notifications)
    except Exception as e:
        logging.error(f"Admin route error: {str(e)}")
        flash(f"Error loading admin page: {str(e)}", "error")
        return render_template('admin.html', data=[], view=view, admin_profile=None,
                               users=[], all_attendance=[], rota_image_base64=None,
                               holiday_table=None)
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
            SELECT l.id, l.leave_type, l.start_date, l.end_date, l.reason,
                   l.status, l.created_at, l.total_days, l.used_paid_days, l.used_unpaid_days,l.used_comp_days,
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

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT l.*, u.email, u.username
            FROM leaves l
            JOIN users u ON l.user_id = u.id
            WHERE l.id = %s
        """, (leave_id,))
        leave = cursor.fetchone()

        if not leave:
            return jsonify({"success": False, "message": "Leave not found"})

        if leave['status'] != 'Pending':
            return jsonify({"success": False, "message": f"Leave is already {leave['status']}"})

        if status == 'Approved':
            # paid_to_deduct = leave['used_paid_days'] or 0
            # if paid_to_deduct > 0:
            #     cursor.execute("""
            #         UPDATE leave_balance
            #         SET paid_leaves = GREATEST(paid_leaves - %s, 0)
            #         WHERE user_id = %s
            #     """, (paid_to_deduct, leave['user_id']))
            paid_to_deduct = leave['used_paid_days'] or 0
            comp_to_deduct = leave.get('used_comp_days', 0) or 0

            cursor.execute("""
                UPDATE leave_balance
                SET 
                    paid_leaves = GREATEST(paid_leaves - %s, 0),
                    compensation_leaves = GREATEST(compensation_leaves - %s, 0)
                WHERE user_id = %s
            """, (paid_to_deduct, comp_to_deduct, leave['user_id']))

            cursor.execute("UPDATE leaves SET status = 'Approved', updated_at = NOW() WHERE id = %s", (leave_id,))
            conn.commit()

            email_subject = f"✅ Leave Request Approved – {leave['leave_type']}"
            email_body = f"""
Dear {leave['username']},

Great news! Your leave request has been APPROVED by the administration.

Leave Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
  • Leave Type  : {leave['leave_type']}
  • From Date   : {leave['start_date']}
  • To Date     : {leave['end_date']}
  • Total Days  : {leave['total_days']} day(s)  ({paid_to_deduct} paid / {leave.get('used_comp_days',0)} comp / {leave['used_unpaid_days']} unpaid)
  • Reason      : {leave['reason']}
  • Status      : ✅ APPROVED
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Please ensure all pending tasks are handed over before your leave begins.

Warm regards,
HR Administration Team
            """
        else:
            cursor.execute("UPDATE leaves SET status = 'Rejected', updated_at = NOW() WHERE id = %s", (leave_id,))
            conn.commit()

            email_subject = f"❌ Leave Request Rejected – {leave['leave_type']}"
            email_body = f"""
Dear {leave['username']},

We regret to inform you that your leave request has been REJECTED by the administration.

Leave Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
  • Leave Type  : {leave['leave_type']}
  • From Date   : {leave['start_date']}
  • To Date     : {leave['end_date']}
  • Total Days  : {leave['total_days']} day(s)
  • Reason      : {leave['reason']}
  • Status      : ❌ REJECTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your leave balances remain unchanged.

Regards,
HR Administration Team
            """

        try:
            send_email(leave['email'], email_subject, email_body)
        except Exception as mail_err:
            logging.warning(f"Email failed: {mail_err}")

        cursor.execute(
            "INSERT INTO notifications (message, user_id) VALUES (%s, %s)",
            (f"Your leave request ({leave['leave_type']}) has been {status.lower()}.", leave['user_id'])
        )
        conn.commit()

        return jsonify({"success": True, "message": f"Leave {status.lower()} successfully"})

    except Exception as e:
        logging.error(f"Update leave status error: {str(e)}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


@admin_bp.route('/approve_leave/<int:leave_id>', methods=['POST'])
def approve_leave(leave_id):
    conn = get_db_connection()
    if not conn:
        return jsonify(success=False, message="Database error")

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT l.*, u.email, u.username
            FROM leaves l JOIN users u ON l.user_id = u.id
            WHERE l.id = %s
        """, (leave_id,))
        leave = cursor.fetchone()
        if not leave:
            return jsonify(success=False, message="Leave not found")

        paid_to_deduct = leave['used_paid_days'] or 0
        comp_to_deduct = leave.get('used_comp_days', 0) or 0

        cursor.execute("""
            UPDATE leave_balance
            SET 
                paid_leaves = GREATEST(paid_leaves - %s, 0),
                compensation_leaves = GREATEST(compensation_leaves - %s, 0)
            WHERE user_id = %s
        """, (paid_to_deduct, comp_to_deduct, leave['user_id']))

        cursor.execute("UPDATE leaves SET status = 'Approved', updated_at = NOW() WHERE id = %s", (leave_id,))
        conn.commit()

        email_body = f"""
Dear {leave['username']},

Your leave request has been APPROVED.

  • Leave Type : {leave['leave_type']}
  • From       : {leave['start_date']}  To: {leave['end_date']}
  • Days       : {leave['total_days']}  ({paid_to_deduct} paid / {leave.get('used_comp_days', 0)} comp / {leave['used_unpaid_days']} unpaid)

Warm regards,
HR Administration Team
        """
        try:
            send_email(leave['email'], f"✅ Leave Approved – {leave['leave_type']}", email_body)
        except Exception as me:
            logging.warning(f"Email failed: {me}")

        cursor.execute("INSERT INTO notifications (message, user_id) VALUES (%s, %s)",
                       (f"Your {leave['leave_type']} has been approved.", leave['user_id']))
        conn.commit()

        return jsonify(success=True, message="Leave approved")
    except Exception as e:
        logging.error(f"Approve leave error: {e}")
        return jsonify(success=False, message=str(e))
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/reject_leave/<int:leave_id>', methods=['POST'])
def reject_leave(leave_id):
    conn = get_db_connection()
    if not conn:
        return jsonify(success=False, message="Database error")

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT l.*, u.email, u.username
            FROM leaves l JOIN users u ON l.user_id = u.id
            WHERE l.id = %s
        """, (leave_id,))
        leave = cursor.fetchone()
        if not leave:
            return jsonify(success=False, message="Leave not found")

        cursor.execute("UPDATE leaves SET status = 'Rejected', updated_at = NOW() WHERE id = %s", (leave_id,))
        conn.commit()

        email_body = f"""
Dear {leave['username']},

Unfortunately, your leave request has been REJECTED.

  • Leave Type : {leave['leave_type']}
  • From       : {leave['start_date']}  To: {leave['end_date']}

Your leave balance remains unchanged.

Regards,
HR Administration Team
        """
        try:
            send_email(leave['email'], f"❌ Leave Rejected – {leave['leave_type']}", email_body)
        except Exception as me:
            logging.warning(f"Email failed: {me}")

        cursor.execute("INSERT INTO notifications (message, user_id) VALUES (%s, %s)",
                       (f"Your {leave['leave_type']} has been rejected.", leave['user_id']))
        conn.commit()

        return jsonify(success=True, message="Leave rejected")
    except Exception as e:
        logging.error(f"Reject leave error: {e}")
        return jsonify(success=False, message=str(e))
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/admin_update_user/<int:user_id>', methods=['POST'])
def admin_update_user(user_id):
    if not session.get('is_admin'):
        return jsonify({"success": False, "message": "Access denied"})

    username = request.form.get('username')
    email = request.form.get('email')
    position = request.form.get('position')
    face_image = request.files.get('face_image')

    if not username and not email and not position and not face_image:
        return jsonify({"success": False, "message": "No changes provided"})

    conn = get_db_connection()
    if not conn:
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
        if position is not None:
            if position.strip() == "":
                return jsonify({"success": False, "message": "Position is required"})
            updates.append("position = %s")
            params.append(position)
        if face_image:
            face_image_data = face_image.read()
            if not face_image_data:
                return jsonify({"success": False, "message": "Invalid face image"})
            updates.append("face_image = %s")
            params.append(face_image_data)

        params.append(user_id)
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
        cursor.execute(query, tuple(params))
        conn.commit()
        return jsonify({"success": True, "message": "User updated"})
    except mysql.connector.IntegrityError:
        return jsonify({"success": False, "message": "Username or email already exists"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


@admin_bp.route('/upload_rota', methods=['POST'])
def upload_rota():
    if not session.get('is_admin'):
        return jsonify({"success": False, "message": "Access denied"})

    file = request.files.get('rota_image')
    if not file:
        return jsonify({"success": False, "message": "No file uploaded"})

    rota_image_data = file.read()
    if not rota_image_data:
        return jsonify({"success": False, "message": "Invalid rota image"})

    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO rota (rota_image) VALUES (%s)", (rota_image_data,))
        conn.commit()
        return jsonify({"success": True, "message": "Rota uploaded successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


@admin_bp.route('/upload_holiday', methods=['POST'])
def upload_holiday():
    if not session.get('is_admin'):
        return jsonify({"success": False, "message": "Access denied"})

    file = request.files.get('holiday_image')
    if not file:
        return jsonify({"success": False, "message": "No file uploaded"})

    filename = file.filename.lower()
    allowed_extensions = ['.xls', '.xlsx', '.csv']
    file_ext = os.path.splitext(filename)[1]
    
    if file_ext not in allowed_extensions:
        return jsonify({"success": False, "message": "Only Excel or CSV files allowed"})
    
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)

        # Clean up empty rows/cols
        df.dropna(how='all', inplace=True)
        df.fillna('', inplace=True)

        # Convert to styled HTML table
        table_html = df.to_html(
            classes='holiday-data-table',
            index=False,
            border=0,
            escape=True
        )

        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "message": "Database error"})

        cursor = conn.cursor()
        # Keep only the latest holiday table — clear old, insert new
        cursor.execute("DELETE FROM rota")
        cursor.execute("INSERT INTO rota (holiday_table) VALUES (%s)", (table_html,))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"success": True, "message": "Holiday list uploaded successfully!"})

    except Exception as e:
        logging.error(f"upload_holiday error: {e}")
        return jsonify({"success": False, "message": f"Failed to process file: {str(e)}"})


@admin_bp.route('/send_notification', methods=['POST'])
def send_notification():
    if not session.get('is_admin'):
        return jsonify({"success": False, "message": "Access denied"})

    message = request.form.get('message')
    if not message:
        return jsonify({"success": False, "message": "No message provided"})

    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE is_admin = 0")
        users = cursor.fetchall()
        if not users:
            return jsonify({"success": False, "message": "No non-admin users found"})

        for user in users:
            cursor.execute("INSERT INTO notifications (message, user_id) VALUES (%s, %s)", (message, user['id']))
        conn.commit()
        return jsonify({"success": True, "message": "Notification sent to all users"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


@admin_bp.route('/update_attendance_status/<int:attendance_id>', methods=['POST'])
def update_attendance_status(attendance_id):
    if not session.get('is_admin'):
        return jsonify({"success": False, "message": "Access denied"})

    status = request.form.get('status')
    if status not in ['Present', 'Absent']:
        return jsonify({"success": False, "message": "Invalid status"})

    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE attendance SET attendance_status = %s WHERE id = %s", (status, attendance_id))
        conn.commit()
        return jsonify({"success": True, "message": "Attendance status updated"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


@admin_bp.route('/view_excel')
def view_excel():
    if not session.get('is_admin'):
        flash("Access denied", "error")
        return redirect(url_for('login'))

    conn = get_db_connection()
    if not conn:
        flash("Database connection failed", "error")
        return render_template('view_excel.html', table="")

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT u.username, a.login_time, a.logout_time, a.daily_status_submitted, a.attendance_status,
                   TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
            FROM users u LEFT JOIN attendance a ON u.id = a.user_id
        """)
        data = cursor.fetchall()
        if not data:
            flash("No attendance data available", "warning")
            return render_template('view_excel.html', table="")

        for record in data:
            if record['seconds_worked']:
                h = record['seconds_worked'] // 3600
                m = (record['seconds_worked'] % 3600) // 60
                s = record['seconds_worked'] % 60
                record['hours_worked'] = f"{h:02d}:{m:02d}:{s:02d}"
            else:
                record['hours_worked'] = "N/A"

        df = pd.DataFrame(data)[['username', 'login_time', 'logout_time',
                                  'daily_status_submitted', 'attendance_status', 'hours_worked']]
        html_table = df.to_html(index=False, classes='table table-striped')
        return render_template('view_excel.html', table=html_table)
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
        return render_template('view_excel.html', table="")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


@admin_bp.route('/export_page')
def export_page():
    if not session.get('is_admin'):
        flash("Access denied", "error")
        return redirect(url_for('login'))
    return render_template('export.html')


@admin_bp.route('/export')
def export():
    if not session.get('is_admin'):
        flash("Access denied", "error")
        return redirect(url_for('admin.admin'))

    conn = get_db_connection()
    if not conn:
        flash("Database connection failed", "error")
        return redirect(url_for('admin.admin'))

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT u.username, a.login_time, a.logout_time, a.daily_status_submitted, a.attendance_status,
                   TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
            FROM users u LEFT JOIN attendance a ON u.id = a.user_id
        """)
        data = cursor.fetchall()
        if not data:
            flash("No attendance data to export", "warning")
            return redirect(url_for('admin.admin'))

        for record in data:
            if record['seconds_worked']:
                h = record['seconds_worked'] // 3600
                m = (record['seconds_worked'] % 3600) // 60
                s = record['seconds_worked'] % 60
                record['hours_worked'] = f"{h:02d}:{m:02d}:{s:02d}"
            else:
                record['hours_worked'] = "N/A"

        df = pd.DataFrame(data)[['username', 'login_time', 'logout_time',
                                  'daily_status_submitted', 'attendance_status', 'hours_worked']]
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Attendance', index=False)
            worksheet = writer.sheets['Attendance']
            for col, width in [('A:A', 20), ('B:C', 20), ('D:D', 30), ('E:E', 15), ('F:F', 15)]:
                worksheet.set_column(col, width)
        output.seek(0)
        return send_file(output, download_name='attendance.xlsx', as_attachment=True)
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for('admin.admin'))
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@admin_bp.route('/update_profile', methods=['POST'])
def update_profile():
    if not session.get('user_id'):
        return jsonify({"success": False, "message": "Not logged in"})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        email = request.form.get('email')
        face_image = request.files.get('face_image')

        if face_image and face_image.filename != '':
            image_data = face_image.read()
            cursor.execute("""
                UPDATE users SET email=%s, face_image=%s WHERE id=%s
            """, (email, image_data, session['user_id']))
        else:
            cursor.execute("""
                UPDATE users SET email=%s WHERE id=%s
            """, (email, session['user_id']))

        conn.commit()
        return jsonify({"success": True})

    except Exception as e:
        conn.rollback()
        print("ERROR:", e)
        return jsonify({"success": False, "message": "Error updating profile"})

    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if not session.get('is_admin'):
        return jsonify({"success": False, "message": "Access denied"})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # delete child records first
        cursor.execute("DELETE FROM leave_balance WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM leaves WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM attendance WHERE user_id = %s", (user_id,))

        # then delete user
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    finally:
        cursor.close()
        conn.close()