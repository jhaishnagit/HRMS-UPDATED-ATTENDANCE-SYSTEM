from flask import Blueprint, app, render_template, session, redirect
from utils import get_db_connection
import base64
from datetime import datetime, date, timedelta
import pytz
from leave.routes import sync_monthly_carryforward

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/auth/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # USER DATA
    cursor.execute("SELECT * FROM users WHERE id=%s", (session['user_id'],))
    user = cursor.fetchone()

    # Profile Image
    user_face_image_base64 = None
    if user and user.get('face_image'):
        user_face_image_base64 = base64.b64encode(user['face_image']).decode('utf-8')

    # TODAY ATTENDANCE
    india = pytz.timezone('Asia/Kolkata')
    today = datetime.now(india).date()

    cursor.execute("""
        SELECT * FROM attendance
        WHERE user_id=%s 
        AND DATE(login_time)=%s
        ORDER BY id DESC LIMIT 1
    """, (session['user_id'], today))

    attendance = cursor.fetchone()

    # DEFAULT VALUES
    last_login = None
    last_logout = None
    daily_status_submitted = False
    logout_done = False
    can_login = False

    # LOGIN FLOW LOGIC
    if not attendance:
        can_login = True
    else:
        last_login = attendance.get('login_time')
        last_logout = attendance.get('logout_time')
        daily_status_submitted = attendance.get('daily_status_submitted') == 1
        logout_done = last_logout is not None

        if last_login and not daily_status_submitted:
            can_login = False
        elif daily_status_submitted and not logout_done:
            can_login = False
        elif logout_done:
            can_login = False
            

    # CALENDAR DATA
    cursor.execute("""
        SELECT DATE(login_time) as date, attendance_status
        FROM attendance
        WHERE user_id=%s
    """, (session['user_id'],))

    records = cursor.fetchall()
    calendar_data = {}

    start_date = today.replace(day=1)
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    end_date = next_month - timedelta(days=1)

    current = start_date
    while current <= end_date:
        calendar_data[str(current)] = False
        current += timedelta(days=1)

    for r in records:
        if r['date']:
            calendar_data[str(r['date'])] = True

    # ── LEAVE DATA ──────────────────────────────────────────────
    balance = sync_monthly_carryforward(conn, session['user_id'])  # ← inside function now
    paid_leave_balance  = balance['paid_leaves']
    compensation_leaves = balance['compensation_leaves']
    total_leaves        = balance['total_annual_leaves']

    cursor.execute("""
        SELECT leave_type, start_date, end_date, total_days,
               used_paid_days, used_unpaid_days, status, created_at
        FROM leaves
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (session['user_id'],))
    user_leaves = cursor.fetchall()
    # ────────────────────────────────────────────────────────────

    cursor.close()
    conn.close()

    return render_template(
        'dashboard.html',
        user=user,
        created_at=user.get('created_at'),
        user_face_image_base64=user_face_image_base64,
        last_login=last_login,
        last_logout=last_logout,
        calendar_data=calendar_data,
        daily_status_submitted=daily_status_submitted,
        logout_done=logout_done,
        can_login=can_login,
        # ── new leave variables ──
        paid_leave_balance=paid_leave_balance,
        compensation_leaves=compensation_leaves,
        total_leaves=total_leaves,
        user_leaves=user_leaves,
    )

@dashboard_bp.route('/check_admin')
def check_admin():
    return {"is_admin": session.get('is_admin', 0)}