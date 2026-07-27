from flask import Blueprint, request, jsonify, session, send_file
from utils import get_db_connection
import io

payslip_bp = Blueprint("payslip", __name__)


# ----------------------------
# Upload Payslip (called from Node.js)
# ----------------------------
@payslip_bp.route("/upload", methods=["POST"])
def upload_payslip():

    email = request.form.get("email")
    month = request.form.get("month")
    year = request.form.get("year")

    pdf = request.files.get("pdf")

    if not email or not pdf:
        return jsonify({
            "success": False,
            "message": "Email or PDF missing"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT id FROM users WHERE email=%s",
        (email,)
    )

    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()

        return jsonify({
            "success": False,
            "message": "Employee not found"
        }), 404

    pdf_data = pdf.read()

    cursor.execute(
        """
        INSERT INTO payslips
        (user_id, month, year, pdf_file)
        VALUES (%s, %s, %s, %s)
        """,
        (
            user["id"],
            month,
            year,
            pdf_data
        )
    )

    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Payslip Saved Successfully"
    })


# ----------------------------
# List Logged-in User Payslips
# ----------------------------
@payslip_bp.route("/list", methods=["GET"])
def list_payslips():

    if "user_id" not in session:
        return jsonify([]), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT id, month, year, created_at
        FROM payslips
        WHERE user_id=%s
        ORDER BY created_at DESC
        """,
        (session["user_id"],)
    )

    payslips = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(payslips)


# ----------------------------
# Download Payslip
# ----------------------------
@payslip_bp.route("/download/<int:payslip_id>", methods=["GET"])
def download_payslip(payslip_id):

    if "user_id" not in session:
        return "Unauthorized", 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT pdf_file, month, year
        FROM payslips
        WHERE id=%s
        AND user_id=%s
        """,
        (
            payslip_id,
            session["user_id"]
        )
    )

    payslip = cursor.fetchone()

    cursor.close()
    conn.close()

    if not payslip:
        return "Payslip Not Found", 404

    return send_file(
        io.BytesIO(payslip["pdf_file"]),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{payslip['month']}_{payslip['year']}.pdf"
    )