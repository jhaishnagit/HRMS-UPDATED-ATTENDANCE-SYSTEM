from flask import Blueprint, request, jsonify, session
from utils import get_db_connection
import base64
import numpy as np
from PIL import Image, ImageEnhance
import io
import datetime
import time

attendance_bp = Blueprint('attendance', __name__)

# ── face_recognition import ─────────────────────────────
try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    print("CRITICAL WARNING: face_recognition not installed. ALL attendance will be BLOCKED.")


# ── OPTIMIZED HELPERS FOR SPEED ─────────────────────────────

def decode_base64_image(data_url: str) -> np.ndarray:
    """Faster decode + resize (Big speed improvement)"""
    try:
        if ',' in data_url:
            _, b64 = data_url.split(',', 1)
        else:
            b64 = data_url
            
        img_bytes = base64.b64decode(b64)
        img = Image.open(io.BytesIO(img_bytes)).convert('RGB')

        # Resize large camera images (very important for speed)
        if max(img.width, img.height) > 720:
            ratio = 720 / max(img.width, img.height)
            img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)

        return np.array(img)
    except Exception as e:
        raise ValueError(f"Invalid image data: {e}")


def preprocess_image(np_img: np.ndarray) -> np.ndarray:
    """Faster preprocessing"""
    img = Image.fromarray(np_img).convert('RGB')
    w, h = img.size

    # Reduced minimum size for faster processing
    min_dim = min(w, h)
    if min_dim < 240:          # Reduced from 300
        scale = 240 / min_dim
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # Light enhancement (faster)
    img = ImageEnhance.Contrast(img).enhance(1.15)
    img = ImageEnhance.Brightness(img).enhance(1.05)

    return np.array(img)


def get_face_encoding(np_img: np.ndarray, label="image"):
    """Optimized for SPEED"""
    np_img = preprocess_image(np_img)

    # HOG with lower upsampling (fastest)
    locations = face_recognition.face_locations(
        np_img, 
        model='hog', 
        number_of_times_to_upsample=1          # Reduced from 2
    )

    # CNN fallback only if needed
    if len(locations) == 0:
        print(f"[face_encoding] HOG failed in {label}, trying CNN…")
        locations = face_recognition.face_locations(
            np_img, 
            model='cnn', 
            number_of_times_to_upsample=0      # Reduced from 1
        )

    if len(locations) == 0:
        print(f"[face_encoding] No face in {label}")
        return None, "no_face"

    if len(locations) > 1:
        print(f"[face_encoding] {len(locations)} faces in {label}, picking largest")
        locations = [max(locations, key=lambda l: (l[2]-l[0]) * (l[1]-l[3]))]

    # Reduced jitters = Big speed gain
    encs = face_recognition.face_encodings(
        np_img, 
        locations,
        num_jitters=2,           # Reduced from 5
        model='large'
    )
    
    if not encs:
        return None, "encoding_failed"

    return encs[0], "ok"


def verify_face(stored_blob, captured_np: np.ndarray, tolerance=0.48):
    """Slightly stricter tolerance for better accuracy after speed optimization"""
    if not FACE_RECOGNITION_AVAILABLE:
        return False, "Face recognition not installed. Contact administrator."

    if not stored_blob:
        return False, "No profile photo on your account. Ask admin to upload your photo."

    # Decode stored profile
    try:
        stored_np = np.array(Image.open(io.BytesIO(bytes(stored_blob))).convert('RGB'))
    except Exception:
        return False, "Could not read your profile photo. Ask admin to re-upload."

    # Encode profile face
    stored_enc, stored_status = get_face_encoding(stored_np, label="profile")
    if stored_enc is None:
        msg_map = {
            "no_face": "No face found in your profile photo. Ask admin to upload a clear photo.",
            "encoding_failed": "Could not process your profile photo.",
        }
        return False, msg_map.get(stored_status, "Profile photo error.")

    # Encode live face
    live_enc, live_status = get_face_encoding(captured_np, label="live")
    if live_enc is None:
        msg_map = {
            "no_face": "No face detected by camera. Face the camera directly with good lighting.",
            "encoding_failed": "Could not process camera image.",
        }
        return False, msg_map.get(live_status, "Camera capture error.")

    # Compare
    distance = face_recognition.face_distance([stored_enc], live_enc)[0]
    print(f"[face_verify] distance={distance:.4f}  tolerance={tolerance}")

    if distance <= tolerance:
        return True, "Face matched"

    if distance <= tolerance + 0.10:
        print(f"[face_verify] NEAR MISS distance={distance:.4f}")

    return False, (
        "Face did not match. Please try:\n"
        "• Face the camera directly\n"
        "• Good lighting\n"
        "• Remove glasses/headwear\n"
        "• Move closer to camera"
    )


# ── Rest of your code remains exactly same ─────────────────────────────

_last_action_time: dict = {}

def _debounce_ok(user_id, action, gap=6):
    key = f"{user_id}_{action}"
    now = time.time()
    if now - _last_action_time.get(key, 0) < gap:
        return False
    _last_action_time[key] = now
    return True


def _save_photo(np_img: np.ndarray, filename_stem: str):
    try:
        import os
        folder = "static/uploads/attendance"
        os.makedirs(folder, exist_ok=True)
        path = f"{folder}/{filename_stem}.jpg"
        Image.fromarray(np_img).save(path, quality=85)
        return path
    except Exception as e:
        print(f"[_save_photo] Could not save: {e}")
        return None


@attendance_bp.route('/diagnose_face', methods=['GET'])
def diagnose_face():
    uid = request.args.get('user_id') or session.get('user_id')
    if not uid:
        return jsonify({'error': 'No user_id provided'}), 400

    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, face_image FROM users WHERE id = %s", (uid,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user or not user['face_image']:
        return jsonify({'user_id': uid, 'has_photo': False, 'face_detected': False,
                        'action': 'Admin must upload profile photo for this user'})

    try:
        np_img = np.array(Image.open(io.BytesIO(bytes(user['face_image']))).convert('RGB'))
        w, h = np_img.shape[1], np_img.shape[0]
        enc, status = get_face_encoding(np_img, label=f"user_{uid}_profile")
        return jsonify({
            'user_id': uid,
            'has_photo': True,
            'image_size': f"{w}x{h}",
            'face_detected': enc is not None,
            'status': status,
            'action': 'OK' if enc is not None else 'Re-upload a clear, well-lit profile photo'
        })
    except Exception as e:
        return jsonify({'user_id': uid, 'error': str(e)}), 500


# mark_login and mark_logout routes (unchanged)
@attendance_bp.route('/mark_login', methods=['POST'])
def mark_login():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401

    if not _debounce_ok(user_id, 'login'):
        return jsonify({'success': False, 'message': 'Please wait a few seconds before trying again.'}), 429

    data       = request.get_json(force=True) or {}
    image_data = data.get('image')
    latitude   = data.get('latitude')
    longitude  = data.get('longitude')

    if not image_data:
        return jsonify({'success': False, 'message': 'No image received. Please try again.'}), 400

    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT face_image FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        try:
            captured_np = decode_base64_image(image_data)
        except ValueError as e:
            return jsonify({'success': False, 'message': str(e)}), 400

        matched, msg = verify_face(user['face_image'], captured_np, tolerance=0.48)
        if not matched:
            return jsonify({'success': False, 'message': msg}), 200

        today = datetime.date.today()
        cursor.execute(
            "SELECT id FROM attendance WHERE user_id = %s AND DATE(login_time) = %s",
            (user_id, today)
        )
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'Attendance already marked for today.'}), 200

        photo_path = _save_photo(captured_np, f"login_{user_id}_{int(time.time())}")

        cursor.execute(
            """
            INSERT INTO attendance
                (user_id, login_time, login_photo_path,
                 login_latitude, login_longitude, attendance_status)
            VALUES (%s, NOW(), %s, %s, %s, 'Present')
            """,
            (user_id, photo_path, latitude, longitude)
        )
        conn.commit()
        return jsonify({'success': True, 'message': f'Login marked successfully! {msg}'}), 200

    except Exception as e:
        conn.rollback()
        print(f"[mark_login] ERROR user_id={user_id}: {e}")
        return jsonify({'success': False, 'message': 'Internal server error. Please try again.'}), 500
    finally:
        cursor.close()
        conn.close()


@attendance_bp.route('/mark_logout', methods=['POST'])
def mark_logout():
    # (Same as mark_login, just copy-paste from your original code)
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401

    if not _debounce_ok(user_id, 'logout'):
        return jsonify({'success': False, 'message': 'Please wait a few seconds before trying again.'}), 429

    data       = request.get_json(force=True) or {}
    image_data = data.get('image')
    latitude   = data.get('latitude')
    longitude  = data.get('longitude')

    if not image_data:
        return jsonify({'success': False, 'message': 'No image received. Please try again.'}), 400

    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT face_image FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        try:
            captured_np = decode_base64_image(image_data)
        except ValueError as e:
            return jsonify({'success': False, 'message': str(e)}), 400

        matched, msg = verify_face(user['face_image'], captured_np, tolerance=0.48)
        if not matched:
            return jsonify({'success': False, 'message': msg}), 200

        today = datetime.date.today()
        cursor.execute(
            "SELECT id FROM attendance WHERE user_id = %s AND DATE(login_time) = %s AND logout_time IS NULL",
            (user_id, today)
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'message': 'No active login found for today.'}), 200

        photo_path = _save_photo(captured_np, f"logout_{user_id}_{int(time.time())}")

        cursor.execute(
            """
            UPDATE attendance
            SET logout_time       = NOW(),
                logout_photo_path = %s,
                logout_latitude   = %s,
                logout_longitude  = %s
            WHERE id = %s
            """,
            (photo_path, latitude, longitude, row['id'])
        )
        conn.commit()
        return jsonify({'success': True, 'message': f'Logout marked successfully! {msg}'}), 200

    except Exception as e:
        conn.rollback()
        print(f"[mark_logout] ERROR user_id={user_id}: {e}")
        return jsonify({'success': False, 'message': 'Internal server error. Please try again.'}), 500
    finally:
        cursor.close()
        conn.close()


@attendance_bp.route('/submit_daily_status', methods=['POST'])
def submit_daily_status():
    # Your original code (unchanged)
    user_id = session.get('user_id')

    if not user_id:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401

    daily_status = request.form.get('daily_status')

    if not daily_status:
        return jsonify({'success': False, 'message': 'Please enter status'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        today = datetime.date.today()
        cursor.execute("""
            UPDATE attendance
            SET daily_status = %s,
                daily_status_submitted = 1
            WHERE user_id = %s AND DATE(login_time) = %s
        """, (daily_status, user_id, today))
        conn.commit()
        return jsonify({'success': True, 'message': 'Daily status submitted successfully!'})

    except Exception as e:
        conn.rollback()
        print("ERROR:", e)
        return jsonify({'success': False, 'message': 'Server error'}), 500

    finally:
        cursor.close()
        conn.close()