from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, flash
from utils import get_db_connection, send_email
import logging
from datetime import datetime, date
import calendar

leave_bp = Blueprint('leave', __name__)


def get_working_days(start_date, end_date, conn):

    count = 0
    current = start_date

    cursor = conn.cursor(dictionary=True)

    while current <= end_date:

        # Skip only Sunday
        if current.weekday() != 6:

            # Check holiday
            cursor.execute("""
                SELECT * FROM holidays
                WHERE holiday_date = %s
            """, (current,))

            holiday = cursor.fetchone()

            # Count only if NOT holiday
            if not holiday:
                count += 1

        current = date.fromordinal(current.toordinal() + 1)

    cursor.close()

    return max(count, 1)


def ensure_leave_balance(conn, user_id):
    """Create leave_balance row if it doesn't exist (April-April cycle)."""
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM leave_balance WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    if not row:
        # Determine cycle start: April 1 of current or previous year
        today = date.today()
        if today.month >= 4:
            cycle_start = date(today.year, 4, 1)
        else:
            cycle_start = date(today.year - 1, 4, 1)

        cursor.execute("""
            INSERT INTO leave_balance (user_id, total_annual_leaves, paid_leaves, compensation_leaves, last_updated)
            VALUES (%s, 12, 12, 0, %s)
        """, (user_id, cycle_start))
        conn.commit()
        cursor.execute("SELECT * FROM leave_balance WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
    cursor.close()
    return row


def sync_monthly_carryforward(conn, user_id):
    """
    April-to-April leave cycle. Each month that has fully passed without
    any leave taken gets its 1-day allocation carried to compensation_leaves.
    
    Cycle: April 1 → March 31 next year (12 months = 12 paid leaves)
    Logic:
      - last_updated tracks up to which month we've processed
      - For each fully-elapsed month since last_updated, check if user took leave
      - If no leave in that month → add 1 to compensation, subtract 1 from paid
    """
    balance = ensure_leave_balance(conn, user_id)
    today = date.today()

    # Determine cycle start date
    if today.month >= 4:
        cycle_start = date(today.year, 4, 1)
    else:
        cycle_start = date(today.year - 1, 4, 1)

    last_updated = balance['last_updated'] or cycle_start
    # Don't go before cycle start
    if last_updated < cycle_start:
        last_updated = cycle_start

    cursor = conn.cursor(dictionary=True)

    months_to_process = []
    check = date(last_updated.year, last_updated.month, 1)

    while True:
        last_day = calendar.monthrange(check.year, check.month)[1]
        end_of_month = date(check.year, check.month, last_day)

        if end_of_month >= today:
            break  # Month not yet finished

        month_start = date(check.year, check.month, 1)

        # Check if user took any leave (Approved or Pending) in this month
        cursor.execute("""
            SELECT COALESCE(SUM(
                DATEDIFF(
                    LEAST(end_date, %s),
                    GREATEST(start_date, %s)
                ) + 1
            ), 0) as days_taken
            FROM leaves
            WHERE user_id = %s
              AND status IN ('Approved', 'Pending')
              AND start_date <= %s
              AND end_date >= %s
        """, (end_of_month, month_start, user_id, end_of_month, month_start))

        result = cursor.fetchone()
        days_taken = result['days_taken'] or 0

        if days_taken == 0:
            months_to_process.append(check)

        # Advance to next month
        if check.month == 12:
            check = date(check.year + 1, 1, 1)
        else:
            check = date(check.year, check.month + 1, 1)

    if months_to_process:
        comp_to_add = len(months_to_process)
        cursor.execute("""
            UPDATE leave_balance
            SET compensation_leaves = compensation_leaves + %s,
                paid_leaves = GREATEST(paid_leaves - %s, 0),
                last_updated = %s
            WHERE user_id = %s
        """, (comp_to_add, comp_to_add, today, user_id))
        conn.commit()
        logging.info(f"Carried {comp_to_add} month(s) to compensation for user {user_id}")

    cursor.close()
    return ensure_leave_balance(conn, user_id)


@leave_bp.route('/apply_leave', methods=['POST'])
def apply_leave():
    if 'user_id' not in session:
        return jsonify(success=False, message="Not logged in")

    leave_type = request.form.get('leave_type')
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    reason = request.form.get('reason')

    if not all([leave_type, start_date_str, end_date_str, reason]):
        return jsonify(success=False, message="All fields are required")

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify(success=False, message="Invalid date format")
    # ✅ BLOCK PAST DATES
    if start_date < date.today() or end_date < date.today():
        return jsonify(success=False, message="Past dates are not allowed")

    if start_date > end_date:
        return jsonify(success=False, message="End date cannot be before start date")

    # Validate: only 1 paid leave per month
    # Check which months the leave spans
    if leave_type == 'Paid Leave':
        months_spanned = set()
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:  # working day
                months_spanned.add((current.year, current.month))
            current = date.fromordinal(current.toordinal() + 1)

        if len(months_spanned) > 1:
            return jsonify(success=False, message="Paid leave can only be applied within a single calendar month (1 paid leave per month rule).")

    conn = get_db_connection()
    if not conn:
        return jsonify(success=False, message="Database error")

    cursor = conn.cursor(dictionary=True)
    try:
        user_id = session['user_id']

        # Sync carry-forward first
        balance = sync_monthly_carryforward(conn, user_id)

        # Total leave days
        total_days = (end_date - start_date).days + 1

        # # Holiday count
        # holiday_days = 0
        # current = start_date

        # while current <= end_date:
        
        #     cursor.execute("""
        #         SELECT * FROM holidays
        #         WHERE holiday_date = %s
        #     """, (current,))

        #     holiday = cursor.fetchone()

        #     if holiday:
        #         holiday_days += 1

        #     current = date.fromordinal(current.toordinal() + 1)

        # Holiday + Sunday count
        holiday_days = 0
        current = start_date
        
        while current <= end_date:
        
            # Check Sunday
            is_sunday = current.weekday() == 6
        
            # Check Holiday
            cursor.execute("""
                SELECT * FROM holidays
                WHERE holiday_date = %s
            """, (current,))
        
            holiday = cursor.fetchone()
        
            # Count Sunday OR Holiday
            if is_sunday or holiday:
                holiday_days += 1
        
            current = date.fromordinal(current.toordinal() + 1)
        
        paid_balance = balance['paid_leaves']

        # Check if user already used paid leave this month (1 per month rule)
        if leave_type == 'Paid Leave':
            cursor.execute("""
                SELECT COUNT(*) as cnt FROM leaves
                WHERE user_id = %s
                  AND status IN ('Approved', 'Pending')
                  AND used_paid_days > 0
                  AND MONTH(start_date) = MONTH(%s)
                  AND YEAR(start_date) = YEAR(%s)
            """, (user_id, start_date, start_date))
            result = cursor.fetchone()
            if result['cnt'] > 0:
                return jsonify(success=False, message="You have already used or applied for a paid leave this month. Only 1 paid leave is allowed per month.")

        # Determine paid vs unpaid split
        # Paid leaves are reserved: max 1 per month, and only if balance allows
        # if leave_type == 'Paid Leave' and paid_balance >= 1:
        #     paid_days = min(total_days, 1)  # Max 1 paid leave per month
        # else:
        #     paid_days = 0

        # unpaid_days = total_days - paid_days

        # NEW LOGIC (Paid → Compensation → Unpaid)

        comp_balance = balance['compensation_leaves']
        
        paid_days = 0
        comp_days = 0
        
        # Step 1: Paid leave (max 1 per month)
        if leave_type == 'Paid Leave' and paid_balance >= 1:
            paid_days = 1
        
        working_days = total_days - holiday_days

        remaining_days = working_days - paid_days
        
        # Step 2: Compensation leave
        if remaining_days > 0 and comp_balance > 0:
            comp_days = min(remaining_days, comp_balance)
        
        remaining_days -= comp_days
        
        # Step 3: Unpaid
        unpaid_days = remaining_days


        # Check existing leave dates
        cursor.execute("""
            SELECT id FROM leaves
            WHERE user_id = %s
            AND status IN ('Pending', 'Approved')
            AND (
                start_date <= %s
                AND end_date >= %s
            )
        """, (user_id, end_date, start_date))

        existing_leave = cursor.fetchone()

        if existing_leave:
            return jsonify(
                success=False,
                message="You already applied leave for these dates"
            )

        # Get user info for email
        cursor.execute("SELECT email, username FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        # Insert leave request with status Pending (no deduction yet — deduct on Approve)
        cursor.execute("""
    INSERT INTO leaves (
        user_id, leave_type, start_date, end_date, reason,
        total_days, holiday_days, used_paid_days, used_unpaid_days, used_comp_days, status
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Pending')
""", (
    user_id, leave_type, start_date, end_date, reason,
    total_days, holiday_days, paid_days, unpaid_days, comp_days
))

        conn.commit()

        # Send email to employee: leave request submitted
        if user:
            email_body = f"""
Dear {user['username']},

Your leave request has been successfully submitted and is pending approval.

Leave Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
  • Leave Type  : {leave_type}
  • From Date   : {start_date.strftime('%d %B %Y')}
  • To Date     : {end_date.strftime('%d %B %Y')}
  • Total Days  : {total_days} day(s)  ({paid_days} paid / {comp_days} comp / {unpaid_days} unpaid)
  • Reason      : {reason}
  • Status      : Pending Review
━━━━━━━━━━━━━━━━━━━━━━━━━━━

You will receive another email once your request has been reviewed by the admin.

For any queries, please contact HR.

Best regards,
HR Administration Team
            """
            try:
                send_email(user['email'], f"Leave Request Submitted – {leave_type}", email_body)
            except Exception as mail_err:
                logging.warning(f"Email send failed: {mail_err}")

        msg = f"Leave applied: {total_days} day(s) — {paid_days} paid, {unpaid_days} unpaid. You will receive a confirmation email shortly."
        return jsonify(success=True, message=msg,
                       paid_days=paid_days, unpaid_days=unpaid_days, total_days=total_days)
    except Exception as e:
        logging.error(f"Apply leave error: {e}")
        return jsonify(success=False, message=str(e))
    finally:
        cursor.close()
        conn.close()


@leave_bp.route('/leave_history', methods=['GET'])
def leave_history():
    """Return full leave history for the logged-in user as JSON."""
    if 'user_id' not in session:
        return jsonify(success=False, message="Not logged in")

    conn = get_db_connection()
    if not conn:
        return jsonify(success=False, message="Database error")

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id, leave_type, start_date, end_date, reason,
                   total_days, holiday_days, used_paid_days, used_unpaid_days,used_comp_days, status,
                   created_at
            FROM leaves
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (session['user_id'],))
        leaves = cursor.fetchall()

        # Convert dates to strings for JSON
        for l in leaves:
            l['start_date'] = str(l['start_date'])
            l['end_date'] = str(l['end_date'])
            l['created_at'] = l['created_at'].strftime('%d %b %Y') if l['created_at'] else ''

        return jsonify(success=True, leaves=leaves)
    except Exception as e:
        logging.error(f"Leave history error: {e}")
        return jsonify(success=False, message=str(e))
    finally:
        cursor.close()
        conn.close()

@leave_bp.route('/admin/update_leave_status/<int:leave_id>', methods=['POST'])
def update_leave_status(leave_id):

    status = request.form.get('status')
    remarks = request.form.get('remarks')

    conn = get_db_connection()

    if not conn:
        return jsonify(success=False, message="Database connection failed")

    cursor = conn.cursor(dictionary=True)

    try:

        cursor.execute("""
            UPDATE leaves
            SET status=%s, remarks=%s
            WHERE id=%s
        """, (status, remarks, leave_id))

        conn.commit()

        return jsonify(
            success=True,
            message=f"Leave {status.lower()} successfully"
        )

    except Exception as e:
        logging.error(f"Update leave status error: {e}")

        return jsonify(
            success=False,
            message=str(e)
        )

    finally:
        cursor.close()
        conn.close()