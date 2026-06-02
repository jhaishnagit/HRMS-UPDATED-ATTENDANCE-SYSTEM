from flask import Blueprint, render_template, session, redirect, request
from utils import get_db_connection
import base64
from datetime import datetime, timedelta
import pytz
from leave.routes import sync_monthly_carryforward
import re   


dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/auth/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # USER
    cursor.execute("SELECT * FROM users WHERE id=%s", (session['user_id'],))
    user = cursor.fetchone()

    user_face_image_base64 = None
    if user and user.get('face_image'):
        user_face_image_base64 = base64.b64encode(user['face_image']).decode('utf-8')

    # ATTENDANCE
    india = pytz.timezone('Asia/Kolkata')
    today = datetime.now(india).date()

    cursor.execute("""
        SELECT * FROM attendance
        WHERE user_id=%s AND DATE(login_time)=%s
        ORDER BY id DESC LIMIT 1
    """, (session['user_id'], today))

    attendance = cursor.fetchone()

    last_login = None
    last_logout = None
    daily_status_submitted = False
    logout_done = False
    can_login = False

    if not attendance:
        can_login = True
    else:
        last_login = attendance.get('login_time')
        last_logout = attendance.get('logout_time')
        daily_status_submitted = attendance.get('daily_status_submitted') == 1
        logout_done = last_logout is not None

    # CALENDAR
    cursor.execute("""
        SELECT DATE(login_time) as date, attendance_status
        FROM attendance
        WHERE user_id=%s
    """, (session['user_id'],))

    records = cursor.fetchall()
    calendar_data = {}
    # Get holiday dates
    cursor.execute("SELECT holiday_date FROM holidays")
    holiday_rows = cursor.fetchall()

    holiday_dates = []

    for h in holiday_rows:
        holiday_dates.append(str(h['holiday_date']))

    start_date = today.replace(day=1)
    next_month = today.replace(month=today.month % 12 + 1, day=1)
    end_date = next_month - timedelta(days=1)

    current = start_date
    # while current <= end_date:
    #     calendar_data[str(current)] = False
    #     current += timedelta(days=1)
    while current <= end_date:

    # Future dates should stay empty
        if current > today:
            calendar_data[str(current)] = "future"
        else:
            calendar_data[str(current)] = "absent"

        current += timedelta(days=1)

    for r in records:
        if r['date'] and r['attendance_status']:
             calendar_data[str(r['date'])] = r['attendance_status'].lower()

    # LEAVES
    balance = sync_monthly_carryforward(conn, session['user_id'])

    cursor.execute("""
        SELECT leave_type, start_date, end_date, total_days,
               used_paid_days, used_unpaid_days, status, created_at
        FROM leaves
        WHERE user_id=%s
        ORDER BY created_at DESC
    """, (session['user_id'],))

    user_leaves = cursor.fetchall()

    # ROTA image
    cursor.execute("SELECT rota_image FROM rota ORDER BY id DESC LIMIT 1")
    rota_row = cursor.fetchone()
    rota_image_base64 = None
    if rota_row and rota_row.get('rota_image'):
        rota_image_base64 = base64.b64encode(rota_row['rota_image']).decode('utf-8')

    # HOLIDAY TABLE
    # HOLIDAY TABLE
    cursor.execute("SELECT holiday_table FROM rota ORDER BY id DESC LIMIT 1")
    holiday_row = cursor.fetchone()
    
    if holiday_row and holiday_row.get('holiday_table'):
        holiday_table = holiday_row['holiday_table']
    else:
        holiday_table = ""   # safe fallback
    
    def fix_date(match):
        date_part = match.group().split(" ")[0]
        y, m, d = date_part.split("-")
        return f"{d}-{m}-{y}"
    
    holiday_table = re.sub(
        r"\d{4}-\d{2}-\d{2}(?:\s\d{2}:\d{2}:\d{2})?",
        fix_date,
        holiday_table
) 

    # NOTIFICATIONS
    cursor.execute("""
        SELECT id, message, created_at, is_read
        FROM notifications
        WHERE user_id=%s
        ORDER BY created_at DESC
        LIMIT 20
    """, (session['user_id'],))
    notifications = cursor.fetchall()

    paid_leave_balance = balance.get('paid_leaves', 0) if balance else 0
    compensation_leaves = balance.get('compensation_leaves', 0) if balance else 0

    cursor.execute("""
        SELECT email, position, created_at
        FROM users WHERE id=%s
    """, (session['user_id'],))
    extra = cursor.fetchone()
    user_email = extra['email'] if extra else ''
    user_position = extra['position'] if extra else ''
    created_at = extra['created_at'] if extra else None

    # DAILY TASK HISTORY
    cursor.execute("""
        SELECT *
        FROM daily_tasks
        WHERE employee_id = %s
        ORDER BY created_at DESC
    """, (session['user_id'],))
    
    tasks = cursor.fetchall()



    # LATEST UPCOMING HOLIDAY
    cursor.execute("""
        SELECT holiday_name, holiday_date
        FROM holidays
        WHERE holiday_date >= CURDATE()
        ORDER BY holiday_date ASC
        LIMIT 1
    """)
    
    latest_holiday = cursor.fetchone()

    cursor.close()
    conn.close()


    # ✅ Read flag and immediately delete it — False on every refresh after first load
    show_modal = session.pop('show_admin_modal', False)

    return render_template(
        'dashboard.html',
        tasks=tasks,
        show_modal=show_modal,
        user=user,
        created_at=created_at,
        user_email=user_email,
        user_position=user_position,
        user_face_image_base64=user_face_image_base64,
        calendar_data=calendar_data,
        last_login=last_login,
        last_logout=last_logout,
        daily_status_submitted=daily_status_submitted,
        logout_done=logout_done,
        can_login=can_login,
        user_leaves=user_leaves,
        rota_image_base64=rota_image_base64,
        holiday_table=holiday_table,
        notifications=notifications,
        paid_leave_balance=paid_leave_balance,
        compensation_leaves=compensation_leaves,
        holiday_dates=holiday_dates,
        latest_holiday=latest_holiday
    )


@dashboard_bp.route('/check_admin')
def check_admin():
    user_id = session.get('user_id')

    if not user_id:
        return {"is_admin": 0}

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if user and user['is_admin'] == 1:
        return {"is_admin": 1}
    else:
        return {"is_admin": 0}
    

@dashboard_bp.route('/add-task', methods=['POST'])
def add_task():

    project_name = request.form.get('project_name')

    task_name = request.form.get('task_name')
    
    from_date = request.form.get('from_date')
    
    to_date = request.form.get('to_date')
    
    time_period = f"{from_date} To {to_date}"

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""

        INSERT INTO daily_tasks
        (
            employee_id,
            project_name,
            task_name,
            time_period
        )

        VALUES (%s, %s, %s, %s)

    """, (

        session['user_id'],
        project_name,
        task_name,
        time_period

    ))

    conn.commit()
    cursor.close()

    conn.close()

    return redirect('/dashboard#daily-tasks')