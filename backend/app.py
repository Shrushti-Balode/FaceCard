"""
app.py — Face Ride Connect Backend (Phase 2)
============================================
Flask API server with:
  - Face recognition (histogram-based, OpenCV + Haar Cascade) — PROTOTYPE ONLY
  - FC-ID based user system (no Aadhaar)
  - Trip / fare / wallet / journey / transaction management
  - Arduino gate control via serial (graceful, non-crashing if disconnected)
  - Configurable via .env

Port: 5001 (default, configurable via BACKEND_PORT in .env)
"""

from flask import Flask, Response, request, jsonify
from flask_cors import CORS
import cv2
import numpy as np
from PIL import Image
import io
from pathlib import Path
import threading
import time
import json
import serial
import serial.serialutil

from config import (
    BACKEND_PORT, ARDUINO_PORT, ARDUINO_BAUD,
    FACE_THRESHOLD, FARE_PER_STOP,
    ADMIN_USERNAME, ADMIN_PASSWORD
)
from utils import (
    load_data, save_data,
    generate_fc_id, generate_journey_id, generate_transaction_id,
    now_iso, calculate_fare,
    get_user_by_id, save_user, check_active_trip
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
CORS(app, origins=["http://localhost:8080", "http://localhost:3000", "http://localhost:5173", "*"])

BASE_DIR = Path(__file__).parent.resolve()
FACES_DIR = BASE_DIR / "faces"
FACES_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Haar Cascade (face detection)
# ---------------------------------------------------------------------------
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
if face_cascade.empty():
    print("[WARN] Could not load haarcascade_frontalface_default.xml")

# ---------------------------------------------------------------------------
# Known faces (FC-ID -> histogram)  — loaded at startup and on registration
# ---------------------------------------------------------------------------
fc_id_to_name: dict[str, str] = {}
known_faces: dict[str, np.ndarray] = {}
faces_lock = threading.Lock()


def compute_histogram(face_img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
    cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
    return hist.flatten()


def load_known_faces():
    """Load all registered face images and build histogram dictionary."""
    global fc_id_to_name, known_faces
    new_names: dict[str, str] = {}
    new_faces: dict[str, np.ndarray] = {}

    # Load names from data/users.json
    users = load_data("users.json")
    if isinstance(users, list):
        for user in users:
            fc_id = user.get("id", "")
            name = user.get("name") or f"{user.get('firstName', '')} {user.get('lastName', '')}".strip() or "User"
            if fc_id:
                new_names[fc_id] = name

    # Load face images (FC-XXXX.jpg)
    print("\n[Face Recognition] Loading registered faces...")
    count = 0
    for img_path in FACES_DIR.glob("FC-*.jpg"):
        fc_id = img_path.stem  # e.g. FC-1001
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"   [WARN] Could not read {img_path.name}")
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5, minSize=(50, 50))
        if len(faces) > 0:
            x, y, w, h = faces[0]
            face_roi = img[y:y + h, x:x + w]
            new_faces[fc_id] = compute_histogram(face_roi)
            name = new_names.get(fc_id, fc_id)
            print(f"   LOADED -> {name} ({fc_id})")
            count += 1
        else:
            # Try loading the whole image as face ROI if face detection fails
            new_faces[fc_id] = compute_histogram(img)
            name = new_names.get(fc_id, fc_id)
            print(f"   LOADED (no face box) -> {name} ({fc_id})")
            count += 1

    with faces_lock:
        fc_id_to_name.clear()
        fc_id_to_name.update(new_names)
        known_faces.clear()
        known_faces.update(new_faces)

    print(f"   Total registered: {count}\n")


# ---------------------------------------------------------------------------
# Arduino serial (non-blocking, graceful)
# ---------------------------------------------------------------------------
arduino_serial: serial.Serial | None = None
arduino_lock = threading.Lock()
_arduino_connected = False
_arduino_last_attempt = 0.0
ARDUINO_RETRY_INTERVAL = 10  # seconds


def try_connect_arduino():
    """Attempt to connect/reconnect Arduino. Non-crashing."""
    global arduino_serial, _arduino_connected, _arduino_last_attempt
    now = time.time()
    if now - _arduino_last_attempt < ARDUINO_RETRY_INTERVAL:
        return
    _arduino_last_attempt = now

    with arduino_lock:
        try:
            if arduino_serial and arduino_serial.is_open:
                return  # Already connected
            arduino_serial = serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=1)
            _arduino_connected = True
            print(f"[Arduino] Connected on {ARDUINO_PORT} at {ARDUINO_BAUD} baud")
        except serial.serialutil.SerialException as e:
            arduino_serial = None
            _arduino_connected = False
            print(f"[Arduino] Not connected ({ARDUINO_PORT}): {e}")


def send_arduino_command(command: str) -> bool:
    """Send 'G' or 'R' to Arduino. Returns True if sent."""
    global arduino_serial, _arduino_connected
    try_connect_arduino()
    with arduino_lock:
        if arduino_serial and arduino_serial.is_open:
            try:
                arduino_serial.write(command.encode())
                arduino_serial.flush()
                print(f"[Arduino] Sent: {command}")
                return True
            except serial.serialutil.SerialException as e:
                print(f"[Arduino] Write error: {e}")
                arduino_serial = None
                _arduino_connected = False
    return False


def is_arduino_connected() -> bool:
    """Check if Arduino is currently connected."""
    global arduino_serial, _arduino_connected
    with arduino_lock:
        if arduino_serial and arduino_serial.is_open:
            return True
        _arduino_connected = False
        return False


# ---------------------------------------------------------------------------
# Camera loop (MJPEG stream)
# ---------------------------------------------------------------------------
camera_running = False
current_frame: np.ndarray | None = None
frame_lock = threading.Lock()
_start_time = time.time()


def cam_loop():
    global current_frame, camera_running
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    time.sleep(1)

    while camera_running:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces_detected = face_cascade.detectMultiScale(
            gray, scaleFactor=1.2, minNeighbors=6, minSize=(80, 80)
        )

        with faces_lock:
            local_known = dict(known_faces)
            local_names = dict(fc_id_to_name)

        for (x, y, w, h) in faces_detected:
            face_roi = frame[y:y + h, x:x + w]
            current_hist = compute_histogram(face_roi)

            best_match = None
            best_score = 0.0

            for fc_id, known_hist in local_known.items():
                score = float(cv2.compareHist(current_hist, known_hist, cv2.HISTCMP_CORREL))
                if score > best_score:
                    best_score = score
                    best_match = fc_id

            if best_match and best_score > FACE_THRESHOLD:
                name = local_names.get(best_match, best_match)
                color = (0, 255, 0)
                label = f"{name} ({best_match})"
            else:
                color = (0, 0, 255)
                label = "Unknown"

            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
            cv2.rectangle(frame, (x, y - 40), (x + w, y), color, -1)
            cv2.putText(frame, label, (x + 6, y - 10), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 2)

        status_text = f"Registered: {len(local_known)} | Arduino: {'OK' if is_arduino_connected() else 'OFF'}"
        cv2.putText(frame, status_text, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 200, 200), 2)

        with frame_lock:
            current_frame = frame.copy()

        time.sleep(0.01)

    cap.release()


# ===========================================================================
# ROUTES
# ===========================================================================

# ---------------------------------------------------------------------------
# Status / Health
# ---------------------------------------------------------------------------

@app.route("/api/status")
def api_status():
    return jsonify({
        "status": "ok",
        "arduino_connected": is_arduino_connected(),
        "camera_running": camera_running,
        "registered_faces": len(known_faces),
        "uptime_seconds": round(time.time() - _start_time),
        "port": BACKEND_PORT
    })


# ---------------------------------------------------------------------------
# Admin auth
# ---------------------------------------------------------------------------

@app.route("/api/admin/login", methods=["POST", "OPTIONS"])
def api_admin_login():
    if request.method == "OPTIONS":
        return "", 200
    data = request.get_json(silent=True) or {}
    if data.get("username") == ADMIN_USERNAME and data.get("password") == ADMIN_PASSWORD:
        return jsonify({"status": "success", "role": "admin"})
    return jsonify({"status": "error", "message": "Invalid credentials"}), 401


# ---------------------------------------------------------------------------
# Settings / Routes
# ---------------------------------------------------------------------------

@app.route("/api/settings/routes")
def api_routes():
    settings = load_data("settings.json")
    return jsonify({
        "routes": settings.get("routes", {}),
        "fare_per_stop": settings.get("fare_per_stop", FARE_PER_STOP)
    })


# ---------------------------------------------------------------------------
# User registration
# ---------------------------------------------------------------------------

@app.route("/api/register", methods=["POST", "OPTIONS"])
def api_register():
    if request.method == "OPTIONS":
        return "", 200
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"status": "error", "message": "JSON body required"}), 400

        first_name = str(data.get("firstName", "")).strip()
        last_name = str(data.get("lastName", "")).strip()
        route = str(data.get("route", "")).strip()
        pickup = str(data.get("pickup", "")).strip()
        drop = str(data.get("drop", "")).strip()
        wallet = float(data.get("walletAmount", data.get("wallet", 0)))

        if not first_name or not last_name:
            return jsonify({"status": "error", "message": "firstName and lastName are required"}), 400
        if not route or not pickup or not drop:
            return jsonify({"status": "error", "message": "route, pickup, and drop are required"}), 400
        if pickup == drop:
            return jsonify({"status": "error", "message": "Pickup and drop cannot be the same stop"}), 400

        # Validate route
        settings = load_data("settings.json")
        routes = settings.get("routes", {})
        if route not in routes:
            return jsonify({"status": "error", "message": f"Unknown route: {route}. Valid routes: {list(routes.keys())}"}), 400

        stops_list = routes[route].get("stops", [])
        if pickup not in stops_list:
            return jsonify({"status": "error", "message": f"Pickup '{pickup}' not in route {route}"}), 400
        if drop not in stops_list:
            return jsonify({"status": "error", "message": f"Drop '{drop}' not in route {route}"}), 400

        fc_id = generate_fc_id()
        user = {
            "id": fc_id,
            "firstName": first_name,
            "lastName": last_name,
            "name": f"{first_name} {last_name}",
            "route": route,
            "pickup": pickup,
            "drop": drop,
            "wallet": wallet,
            "isActive": True,
            "registeredAt": now_iso()
        }

        if not save_user(user):
            return jsonify({"status": "error", "message": "Failed to save user"}), 500

        # Create initial wallet load transaction if wallet > 0
        if wallet > 0:
            txn = {
                "transaction_id": generate_transaction_id(),
                "user_id": fc_id,
                "type": "wallet_load",
                "amount": wallet,
                "balance_after": wallet,
                "timestamp": now_iso(),
                "description": "Initial wallet load at registration"
            }
            txns = load_data("transactions.json")
            if isinstance(txns, list):
                txns.append(txn)
                save_data("transactions.json", txns)

        load_known_faces()
        print(f"[Register] New user: {fc_id} — {first_name} {last_name}")
        return jsonify({"status": "success", "face_card_id": fc_id, "user": user})

    except Exception as e:
        print("[/api/register] Error:", e)
        return jsonify({"status": "error", "message": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# Backward-compat alias: /save_user -> /api/register
# ---------------------------------------------------------------------------

@app.route("/save_user", methods=["POST", "OPTIONS"])
def save_user_compat():
    """Legacy endpoint — kept for backward compatibility. Delegates to /api/register."""
    if request.method == "OPTIONS":
        return "", 200
    try:
        data = request.get_json(silent=True) or {}
        # Old format had 'firstName', 'lastName', 'route', etc. — pass through
        # Map old 'wallet' key to 'walletAmount'
        if "wallet" in data and "walletAmount" not in data:
            data["walletAmount"] = data["wallet"]
        with app.test_request_context(json=data, method="POST"):
            pass
        # Re-route by updating the request data and calling register logic
        return api_register()
    except Exception as e:
        print("[/save_user] Error:", e)
        return jsonify({"status": "error"}), 500


# ---------------------------------------------------------------------------
# Face registration
# ---------------------------------------------------------------------------

@app.route("/api/register-face", methods=["POST", "OPTIONS"])
def api_register_face():
    if request.method == "OPTIONS":
        return "", 200
    try:
        fc_id = request.form.get("user_id", "").strip()
        if not fc_id or not fc_id.startswith("FC-"):
            return jsonify({"status": "error", "message": "Valid Face Card ID (FC-XXXX) required"}), 400

        if "image" not in request.files:
            return jsonify({"status": "error", "message": "No image file provided"}), 400

        file = request.files["image"]
        if file.filename == "":
            return jsonify({"status": "error", "message": "Empty image file"}), 400

        img_data = file.read()
        try:
            pil_img = Image.open(io.BytesIO(img_data)).convert("RGB")
        except Exception:
            return jsonify({"status": "error", "message": "Invalid image format"}), 400

        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        # Detect face
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        faces_found = face_cascade.detectMultiScale(gray, 1.3, 5, minSize=(50, 50))
        if len(faces_found) == 0:
            return jsonify({"status": "error", "message": "No face detected in the image. Please retake."}), 400
        if len(faces_found) > 1:
            return jsonify({"status": "error", "message": "Multiple faces detected. Please ensure only one face is visible."}), 400

        # Save face image as FC-XXXX.jpg
        save_path = FACES_DIR / f"{fc_id}.jpg"
        pil_img.save(save_path, "JPEG", quality=95)
        print(f"[Face] Saved -> {save_path}")

        # Reload known faces
        load_known_faces()

        return jsonify({"status": "success", "message": f"Face registered for {fc_id}", "face_card_id": fc_id})

    except Exception as e:
        print("[/api/register-face] Error:", e)
        return jsonify({"status": "error", "message": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# Backward-compat alias: /save_face -> /api/register-face
# ---------------------------------------------------------------------------

@app.route("/save_face", methods=["POST", "OPTIONS"])
def save_face_compat():
    """Legacy endpoint — kept for backward compatibility.
    Old code used 'username' (Aadhaar) as identifier.
    Now maps to FC-ID via user lookup or passes through if already FC-*.
    """
    if request.method == "OPTIONS":
        return "", 200
    try:
        # Support both old 'username' key and new 'user_id' key
        user_id = request.form.get("user_id", "").strip()
        username = request.form.get("username", "").strip()

        if not user_id and username:
            # Old code sent Aadhaar as username. In Phase 2 this shouldn't happen
            # but if it does, return a clear error.
            if username.startswith("FC-"):
                user_id = username
            else:
                return jsonify({
                    "status": "error",
                    "message": "Aadhaar-based face registration is no longer supported. Use face_card_id (FC-XXXX)."
                }), 400

        # Forward to new endpoint by mutating form (via internal call)
        # Since Flask doesn't easily allow modifying form data, rebuild and call directly
        from flask import request as req
        if "image" not in request.files:
            return jsonify({"status": "error", "message": "No image file"}), 400

        file = request.files["image"]
        img_data = file.read()

        if not user_id or not user_id.startswith("FC-"):
            return jsonify({"status": "error", "message": "Valid Face Card ID required"}), 400

        try:
            pil_img = Image.open(io.BytesIO(img_data)).convert("RGB")
        except Exception:
            return jsonify({"status": "error", "message": "Invalid image"}), 400

        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        faces_found = face_cascade.detectMultiScale(gray, 1.3, 5, minSize=(50, 50))

        if len(faces_found) == 0:
            return jsonify({"status": "error", "message": "No face detected in image"}), 400

        save_path = FACES_DIR / f"{user_id}.jpg"
        pil_img.save(save_path, "JPEG", quality=95)
        load_known_faces()

        return jsonify({"status": "success", "msg": "Face registered!", "face_card_id": user_id})

    except Exception as e:
        print("[/save_face] Error:", e)
        return jsonify({"status": "error", "msg": str(e)}), 500


# ---------------------------------------------------------------------------
# Face recognition
# ---------------------------------------------------------------------------

@app.route("/api/recognize", methods=["POST", "OPTIONS"])
def api_recognize():
    """
    POST an image frame; returns recognition result.
    This is a PROTOTYPE histogram-based recognition system.
    Accuracy is limited. Do not use in production.
    """
    if request.method == "OPTIONS":
        return "", 200
    try:
        if "frame" not in request.files and "image" not in request.files:
            return jsonify({"status": "error", "message": "No frame/image provided"}), 400

        file = request.files.get("frame") or request.files.get("image")
        img_data = file.read()

        try:
            pil_img = Image.open(io.BytesIO(img_data)).convert("RGB")
        except Exception:
            return jsonify({"status": "error", "message": "Invalid image"}), 400

        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        faces_found = face_cascade.detectMultiScale(gray, 1.2, 5, minSize=(80, 80))

        if len(faces_found) == 0:
            return jsonify({"recognized": False, "reason": "no_face"})

        if len(faces_found) > 1:
            return jsonify({"recognized": False, "reason": "multiple_faces",
                            "message": "Multiple faces detected. Please ensure only one person is in frame."})

        x, y, w, h = faces_found[0]
        face_roi = cv_img[y:y + h, x:x + w]
        current_hist = compute_histogram(face_roi)

        best_match = None
        best_score = 0.0

        with faces_lock:
            local_known = dict(known_faces)
            local_names = dict(fc_id_to_name)

        for fc_id, known_hist in local_known.items():
            score = float(cv2.compareHist(current_hist, known_hist, cv2.HISTCMP_CORREL))
            if score > best_score:
                best_score = score
                best_match = fc_id

        if best_match and best_score > FACE_THRESHOLD:
            user = get_user_by_id(best_match)
            return jsonify({
                "recognized": True,
                "user_id": best_match,
                "name": local_names.get(best_match, best_match),
                "confidence": round(best_score, 4),
                "user": user
            })
        else:
            return jsonify({
                "recognized": False,
                "reason": "unknown",
                "confidence": round(best_score, 4)
            })

    except Exception as e:
        print("[/api/recognize] Error:", e)
        return jsonify({"status": "error", "message": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# Get single user
# ---------------------------------------------------------------------------

@app.route("/api/users/<fc_id>")
def api_get_user(fc_id):
    user = get_user_by_id(fc_id)
    if not user:
        return jsonify({"status": "error", "message": f"User {fc_id} not found"}), 404
    return jsonify(user)


# ---------------------------------------------------------------------------
# Get all users (admin)
# ---------------------------------------------------------------------------

@app.route("/api/users")
def api_get_all_users():
    users = load_data("users.json")
    if not isinstance(users, list):
        users = []
    # Strip internal notes before returning
    clean = [{k: v for k, v in u.items() if not k.startswith("_")} for u in users]
    return jsonify(clean)


# ---------------------------------------------------------------------------
# Wallet balance
# ---------------------------------------------------------------------------

@app.route("/api/users/<fc_id>/wallet")
def api_get_wallet(fc_id):
    user = get_user_by_id(fc_id)
    if not user:
        return jsonify({"status": "error", "message": f"User {fc_id} not found"}), 404
    return jsonify({"user_id": fc_id, "wallet": user.get("wallet", 0)})


# ---------------------------------------------------------------------------
# Trip start
# ---------------------------------------------------------------------------

@app.route("/api/trips/start", methods=["POST", "OPTIONS"])
def api_trip_start():
    if request.method == "OPTIONS":
        return "", 200
    try:
        data = request.get_json(silent=True) or {}
        fc_id = data.get("user_id", "").strip()
        boarding_stop = data.get("boarding_stop", "").strip()

        if not fc_id:
            return jsonify({"status": "error", "message": "user_id required"}), 400
        if not boarding_stop:
            return jsonify({"status": "error", "message": "boarding_stop required"}), 400

        user = get_user_by_id(fc_id)
        if not user:
            return jsonify({"status": "error", "message": f"User {fc_id} not found"}), 404

        if not user.get("isActive", True):
            send_arduino_command("R")
            return jsonify({"status": "denied", "reason": "account_inactive",
                            "message": "Account is inactive"}), 403

        # Check for already-active trip
        active = check_active_trip(fc_id)
        if active:
            return jsonify({"status": "error", "message": "User already has an active trip",
                            "journey_id": active.get("journey_id")}), 409

        # Check minimum wallet balance (at least enough for 1 stop)
        settings = load_data("settings.json")
        fare_per_stop = settings.get("fare_per_stop", FARE_PER_STOP)
        min_balance = fare_per_stop

        if user.get("wallet", 0) < min_balance:
            send_arduino_command("R")
            return jsonify({
                "status": "denied",
                "reason": "insufficient_balance",
                "message": f"Insufficient wallet balance. Minimum Rs.{min_balance} required.",
                "wallet": user.get("wallet", 0)
            }), 402

        # Create journey record
        journey_id = generate_journey_id()
        journey = {
            "journey_id": journey_id,
            "user_id": fc_id,
            "boarding_stop": boarding_stop,
            "exit_stop": None,
            "route": user.get("route", ""),
            "stops": 0,
            "fare": 0,
            "started_at": now_iso(),
            "completed_at": None,
            "status": "in_progress"
        }

        journeys = load_data("journeys.json")
        if not isinstance(journeys, list):
            journeys = []
        journeys.append(journey)
        save_data("journeys.json", journeys)

        # Grant access
        arduino_sent = send_arduino_command("G")

        print(f"[Trip] Started: {journey_id} for {fc_id} at {boarding_stop}")
        return jsonify({
            "status": "granted",
            "journey_id": journey_id,
            "user_id": fc_id,
            "name": user.get("name", fc_id),
            "boarding_stop": boarding_stop,
            "wallet": user.get("wallet", 0),
            "arduino_sent": arduino_sent
        })

    except Exception as e:
        print("[/api/trips/start] Error:", e)
        return jsonify({"status": "error", "message": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# Trip end
# ---------------------------------------------------------------------------

@app.route("/api/trips/end", methods=["POST", "OPTIONS"])
def api_trip_end():
    if request.method == "OPTIONS":
        return "", 200
    try:
        data = request.get_json(silent=True) or {}
        fc_id = data.get("user_id", "").strip()
        exit_stop = data.get("exit_stop", "").strip()
        journey_id = data.get("journey_id", "").strip()

        if not fc_id or not exit_stop:
            return jsonify({"status": "error", "message": "user_id and exit_stop required"}), 400

        user = get_user_by_id(fc_id)
        if not user:
            return jsonify({"status": "error", "message": f"User {fc_id} not found"}), 404

        # Find the active journey
        journeys = load_data("journeys.json")
        if not isinstance(journeys, list):
            journeys = []

        journey = None
        journey_idx = None
        for i, j in enumerate(journeys):
            if j.get("user_id") == fc_id and j.get("status") == "in_progress":
                if journey_id and j.get("journey_id") != journey_id:
                    continue
                journey = j
                journey_idx = i
                break

        if journey is None:
            return jsonify({"status": "error", "message": "No active trip found for this user"}), 404

        # Calculate fare
        route_id = journey.get("route", user.get("route", ""))
        settings = load_data("settings.json")
        fare_per_stop = settings.get("fare_per_stop", FARE_PER_STOP)

        fare_result = calculate_fare(journey["boarding_stop"], exit_stop, route_id, fare_per_stop)
        if fare_result["error"]:
            return jsonify({"status": "error", "message": fare_result["error"]}), 400

        fare = fare_result["fare"]
        num_stops = fare_result["stops"]

        # Check wallet (atomic check + deduct)
        current_balance = user.get("wallet", 0)
        if current_balance < fare:
            return jsonify({
                "status": "error",
                "reason": "insufficient_balance",
                "message": f"Insufficient balance. Fare Rs.{fare}, balance Rs.{current_balance}",
                "fare": fare,
                "wallet": current_balance
            }), 402

        new_balance = round(current_balance - fare, 2)

        # Update user wallet
        user["wallet"] = new_balance
        save_user(user)

        # Update journey
        completed_at = now_iso()
        journeys[journey_idx].update({
            "exit_stop": exit_stop,
            "stops": num_stops,
            "fare": fare,
            "completed_at": completed_at,
            "status": "completed"
        })
        save_data("journeys.json", journeys)

        # Create transaction
        txn_id = generate_transaction_id()
        transaction = {
            "transaction_id": txn_id,
            "user_id": fc_id,
            "journey_id": journeys[journey_idx]["journey_id"],
            "type": "fare",
            "amount": fare,
            "balance_after": new_balance,
            "timestamp": completed_at,
            "description": f"Fare: {journey['boarding_stop']} -> {exit_stop} ({num_stops} stops)"
        }
        txns = load_data("transactions.json")
        if not isinstance(txns, list):
            txns = []
        txns.append(transaction)
        save_data("transactions.json", txns)

        # Send Arduino command (open gate for exit)
        arduino_sent = send_arduino_command("G")

        print(f"[Trip] Ended: {journeys[journey_idx]['journey_id']} | Fare: Rs.{fare} | Balance: Rs.{new_balance}")
        return jsonify({
            "status": "success",
            "journey_id": journeys[journey_idx]["journey_id"],
            "transaction_id": txn_id,
            "boarding_stop": journey["boarding_stop"],
            "exit_stop": exit_stop,
            "stops": num_stops,
            "fare": fare,
            "balance_before": current_balance,
            "balance_after": new_balance,
            "arduino_sent": arduino_sent
        })

    except Exception as e:
        print("[/api/trips/end] Error:", e)
        return jsonify({"status": "error", "message": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# Journey history
# ---------------------------------------------------------------------------

@app.route("/api/users/<fc_id>/journeys")
def api_user_journeys(fc_id):
    if not get_user_by_id(fc_id):
        return jsonify({"status": "error", "message": f"User {fc_id} not found"}), 404
    journeys = load_data("journeys.json")
    if not isinstance(journeys, list):
        journeys = []
    user_journeys = [j for j in journeys if j.get("user_id") == fc_id]
    return jsonify(user_journeys)


# ---------------------------------------------------------------------------
# Transaction history
# ---------------------------------------------------------------------------

@app.route("/api/users/<fc_id>/transactions")
def api_user_transactions(fc_id):
    if not get_user_by_id(fc_id):
        return jsonify({"status": "error", "message": f"User {fc_id} not found"}), 404
    txns = load_data("transactions.json")
    if not isinstance(txns, list):
        txns = []
    user_txns = [t for t in txns if t.get("user_id") == fc_id]
    return jsonify(user_txns)


# ---------------------------------------------------------------------------
# Admin: all journeys + all transactions
# ---------------------------------------------------------------------------

@app.route("/api/journeys")
def api_all_journeys():
    journeys = load_data("journeys.json")
    return jsonify(journeys if isinstance(journeys, list) else [])


@app.route("/api/transactions")
def api_all_transactions():
    txns = load_data("transactions.json")
    return jsonify(txns if isinstance(txns, list) else [])


# ---------------------------------------------------------------------------
# MJPEG Camera stream
# ---------------------------------------------------------------------------

@app.route("/admin/cam")
def video_feed():
    global camera_running
    if not camera_running:
        load_known_faces()
        camera_running = True
        threading.Thread(target=cam_loop, daemon=True).start()
        print("[Camera] Started")

    def gen():
        while True:
            with frame_lock:
                if current_frame is None:
                    time.sleep(0.1)
                    continue
                f = current_frame.copy()
            _, jpeg = cv2.imencode(".jpg", f, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"
            time.sleep(0.03)

    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


# ---------------------------------------------------------------------------
# Debug route (development only)
# ---------------------------------------------------------------------------

@app.route("/debug")
def debug():
    faces = list(FACES_DIR.glob("*.jpg"))
    return jsonify({
        "saved_faces": [f.name for f in faces],
        "fc_id_faces": [f.name for f in faces if f.stem.startswith("FC-")],
        "legacy_faces": [f.name for f in faces if not f.stem.startswith("FC-")],
        "total": len(faces),
        "fc_id_to_name": fc_id_to_name,
        "arduino_connected": is_arduino_connected(),
        "arduino_port": ARDUINO_PORT,
        "face_threshold": FACE_THRESHOLD,
        "fare_per_stop": FARE_PER_STOP
    })


# ===========================================================================
# Startup
# ===========================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("   FACE RIDE CONNECT — Phase 2 Backend")
    print(f"   Port: {BACKEND_PORT}")
    print(f"   Arduino: {ARDUINO_PORT} @ {ARDUINO_BAUD} baud")
    print(f"   Face threshold: {FACE_THRESHOLD}")
    print(f"   Fare per stop: Rs.{FARE_PER_STOP}")
    print("=" * 60 + "\n")

    load_known_faces()
    try_connect_arduino()

    app.run(host="0.0.0.0", port=BACKEND_PORT, threaded=True, debug=False)
