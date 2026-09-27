"""
app.py — FaceCard Prototype Backend
============================================
Flask API server with:
  - Face recognition (histogram-based, OpenCV + Haar Cascade) — PROTOTYPE ONLY
    - Internal Face Card ID based user system
  - Trip / fare / wallet / journey / transaction management
  - Arduino gate control via serial (graceful, non-crashing if disconnected)
  - Configurable via .env

Port: 5001 (default, configurable via BACKEND_PORT in .env)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import cv2
import numpy as np
from PIL import Image
import io
from pathlib import Path
import threading
import time
import json
import re
from functools import wraps
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
else:
    print("[Face Detection] Cascade loaded: YES")

# ---------------------------------------------------------------------------
# LBPH Face Recognizer — replaces broken histogram approach
# ---------------------------------------------------------------------------
fc_id_to_name: dict[str, str] = {}
fc_id_list: list[str] = []         # index -> fc_id for LBPH label mapping
lbph_recognizer = None             # cv2.face.LBPHFaceRecognizer
faces_lock = threading.Lock()
_mutation_lock = threading.Lock()

FACE_RESIZE = (200, 200)           # All face crops normalized to this size


def serialize_mutation(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        with _mutation_lock:
            return handler(*args, **kwargs)
    return wrapped


def extract_face_gray(img_bgr: np.ndarray, scaleFactor=1.3, minNeighbors=5, minSize=(50, 50)):
    """Detect a face and return (gray_crop_200x200, box) or (None, None)."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor, minNeighbors, minSize=minSize)
    if len(faces) == 0:
        return None, None
    x, y, w, h = faces[0]
    face_gray = gray[y:y + h, x:x + w]
    face_gray = cv2.resize(face_gray, FACE_RESIZE)
    return face_gray, (x, y, w, h)


def load_known_faces():
    """Load all registered face images and train the LBPH recognizer."""
    global fc_id_to_name, fc_id_list, lbph_recognizer

    new_names: dict[str, str] = {}

    # Load names from data/users.json
    users = load_data("users.json")
    if isinstance(users, list):
        for user in users:
            fc_id = user.get("id", "")
            name = user.get("name") or f"{user.get('firstName', '')} {user.get('lastName', '')}".strip() or "User"
            if fc_id:
                new_names[fc_id] = name

    # Collect face images
    print("\n[Face Recognition] Loading registered faces...")
    train_images: list[np.ndarray] = []
    train_labels: list[int] = []
    new_fc_id_list: list[str] = []

    for img_path in sorted(FACES_DIR.glob("FC-*.jpg")):
        fc_id = img_path.stem
        name = new_names.get(fc_id, fc_id)
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"   FAILED  -> {fc_id} | Could not read image")
            continue

        face_gray, box = extract_face_gray(img, scaleFactor=1.3, minNeighbors=5, minSize=(50, 50))
        face_detected = face_gray is not None

        if not face_detected:
            # Fallback: use whole image resized
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            face_gray = cv2.resize(gray, FACE_RESIZE)

        label_idx = len(new_fc_id_list)
        new_fc_id_list.append(fc_id)
        train_images.append(face_gray)
        train_labels.append(label_idx)

        print(f"   LOADED  -> {name} ({fc_id}) | Face detected: {'YES' if face_detected else 'NO (fallback)'} | Encoding: YES")

    if train_images:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train(train_images, np.array(train_labels))
    else:
        recognizer = None
        print("   [WARN] No face images loaded — recognizer not trained")

    with faces_lock:
        fc_id_to_name.clear()
        fc_id_to_name.update(new_names)
        fc_id_list.clear()
        fc_id_list.extend(new_fc_id_list)
        lbph_recognizer = recognizer

    print(f"   Total registered: {len(train_images)}\n")


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
    if not ARDUINO_PORT:
        _arduino_connected = False
        return False

    now = time.time()
    if now - _arduino_last_attempt < ARDUINO_RETRY_INTERVAL:
        return False
    _arduino_last_attempt = now

    with arduino_lock:
        try:
            if arduino_serial and arduino_serial.is_open:
                return True
            arduino_serial = serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=1)
            _arduino_connected = True
            print(f"[Arduino] Connected on {ARDUINO_PORT} at {ARDUINO_BAUD} baud")
            return True
        except (serial.serialutil.SerialException, OSError) as e:
            arduino_serial = None
            _arduino_connected = False
            print(f"[Arduino] Not connected ({ARDUINO_PORT}): {e}")
            return False


def send_arduino_command(command: str) -> bool:
    """Send 'G' or 'R' to Arduino. Returns True if sent."""
    global arduino_serial, _arduino_connected
    if command not in {"G", "R"}:
        return False
    try_connect_arduino()
    with arduino_lock:
        if arduino_serial and arduino_serial.is_open:
            try:
                # Append newline to command for robust parsing in Arduino
                arduino_serial.write((command + "\n").encode())
                arduino_serial.flush()
                print(f"[Arduino] Sent: {command}")
                return True
            except (serial.serialutil.SerialException, OSError) as e:
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
# ---------------------------------------------------------------------------
# Runtime status
# ---------------------------------------------------------------------------
_start_time = time.time()


# ===========================================================================
# ROUTES
# ===========================================================================

# ---------------------------------------------------------------------------
# Status / Health
# ---------------------------------------------------------------------------

@app.route("/api/status")
def api_status():
    arduino_connected = is_arduino_connected()
    return jsonify({
        "status": "ok",
        "arduino_connected": arduino_connected,
        "arduino_mode": "hardware" if arduino_connected else "simulation",
        "arduino_port": ARDUINO_PORT,
        "arduino_baud": ARDUINO_BAUD,
        "recognition_mode": "lbph",
        "registered_faces": len(fc_id_list),
        "face_threshold": FACE_THRESHOLD,
        "uptime_seconds": round(time.time() - _start_time),
        "port": BACKEND_PORT
    })


# ---------------------------------------------------------------------------
# Debug: face status (no private data)
# ---------------------------------------------------------------------------

@app.route("/api/face-status")
def api_face_status():
    with faces_lock:
        local_ids = list(fc_id_list)
        local_names = dict(fc_id_to_name)
        trained = lbph_recognizer is not None
    faces_info = [
        {"fc_id": fc_id, "name": local_names.get(fc_id, fc_id), "encoding_loaded": True}
        for fc_id in local_ids
    ]
    return jsonify({
        "registered_count": len(local_ids),
        "recognizer_trained": trained,
        "threshold": FACE_THRESHOLD,
        "faces": faces_info
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
@serialize_mutation
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
        try:
            wallet = float(data.get("walletAmount", data.get("wallet", 0)))
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "walletAmount must be a number"}), 400
        if not np.isfinite(wallet) or wallet < 0:
            return jsonify({"status": "error", "message": "walletAmount must be a non-negative number"}), 400

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
# Face registration
# ---------------------------------------------------------------------------

@app.route("/api/register-face", methods=["POST", "OPTIONS"])
def api_register_face():
    if request.method == "OPTIONS":
        return "", 200
    try:
        fc_id = request.form.get("user_id", "").strip()
        if not re.fullmatch(r"FC-\d{4,}", fc_id):
            return jsonify({"status": "error", "message": "Valid Face Card ID (FC-XXXX) required"}), 400
        if not get_user_by_id(fc_id):
            return jsonify({"status": "error", "message": "Face Card ID is not registered"}), 404

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
# Face recognition
# ---------------------------------------------------------------------------

@app.route("/api/recognize", methods=["POST", "OPTIONS"])
def api_recognize():
    """
    POST an image frame; returns recognition result.
    Uses LBPH (Local Binary Pattern Histograms) — more reliable than histogram correlation.
    """
    if request.method == "OPTIONS":
        return "", 200
    try:
        print("[Recognition] Frame received")

        if "frame" not in request.files and "image" not in request.files:
            return jsonify({"status": "error", "message": "No frame/image provided"}), 400

        file = request.files.get("frame") or request.files.get("image")
        img_data = file.read()

        try:
            pil_img = Image.open(io.BytesIO(img_data)).convert("RGB")
        except Exception:
            return jsonify({"status": "error", "message": "Invalid image"}), 400

        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        print(f"[Recognition] Image decoded: {cv_img.shape[1]}x{cv_img.shape[0]} channels={cv_img.shape[2]}")

        # --- Face detection ---
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        faces_found = face_cascade.detectMultiScale(gray, 1.2, 4, minSize=(60, 60))
        print(f"[Recognition] Faces detected: {len(faces_found)}")

        if len(faces_found) == 0:
            send_arduino_command("R")
            print("[Recognition] RESULT: NO FACE")
            return jsonify({"recognized": False, "reason": "no_face",
                            "message": "No face detected in frame"})

        if len(faces_found) > 1:
            send_arduino_command("R")
            print("[Recognition] RESULT: MULTIPLE FACES")
            return jsonify({"recognized": False, "reason": "multiple_faces",
                            "message": "Multiple faces detected — only one person allowed"})

        # --- Crop and normalize face ---
        x, y, w, h = faces_found[0]
        face_gray = gray[y:y + h, x:x + w]
        face_gray = cv2.resize(face_gray, FACE_RESIZE)

        # --- LBPH prediction ---
        with faces_lock:
            recognizer = lbph_recognizer
            local_names = dict(fc_id_to_name)
            local_fc_ids = list(fc_id_list)

        if recognizer is None or not local_fc_ids:
            send_arduino_command("R")
            print("[Recognition] RESULT: NO RECOGNIZER (no registered faces)")
            return jsonify({"recognized": False, "reason": "no_registered_faces"})

        print(f"[Recognition] Comparing against {len(local_fc_ids)} registered face(s)...")
        label, confidence = recognizer.predict(face_gray)
        predicted_fc_id = local_fc_ids[label] if label < len(local_fc_ids) else None
        predicted_name = local_names.get(predicted_fc_id, predicted_fc_id) if predicted_fc_id else "?"

        print(f"[Recognition] Best match: {predicted_name} ({predicted_fc_id})")
        print(f"[Recognition] Confidence: {confidence:.2f} (lower=better, threshold<{FACE_THRESHOLD})")

        # LBPH confidence: lower = better match. Typical same-person: 10-60, strangers: 80+
        if confidence < FACE_THRESHOLD:
            user = get_user_by_id(predicted_fc_id)
            if not user:
                send_arduino_command("R")
                print("[Recognition] RESULT: ACCOUNT NOT FOUND")
                return jsonify({"recognized": False, "reason": "account_not_found"})
            print(f"[Recognition] RESULT: RECOGNIZED — {predicted_name} ({predicted_fc_id})")
            return jsonify({
                "recognized": True,
                "user_id": predicted_fc_id,
                "name": predicted_name,
                "confidence": round(confidence, 2),
                "user": user
            })
        else:
            send_arduino_command("R")
            print(f"[Recognition] RESULT: UNKNOWN (confidence {confidence:.2f} >= threshold {FACE_THRESHOLD})")
            return jsonify({
                "recognized": False,
                "reason": "unknown",
                "confidence": round(confidence, 2)
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
@serialize_mutation
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

        settings = load_data("settings.json")
        route_stops = settings.get("routes", {}).get(user.get("route", ""), {}).get("stops", [])
        if boarding_stop not in route_stops:
            send_arduino_command("R")
            return jsonify({"status": "denied", "reason": "invalid_stop",
                            "message": "Boarding stop is not on the user's route"}), 400

        # Check for already-active trip
        active = check_active_trip(fc_id)
        if active:
            return jsonify({"status": "error", "message": "User already has an active trip",
                            "journey_id": active.get("journey_id")}), 409

        # Check minimum wallet balance (at least enough for 1 stop)
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
        if not save_data("journeys.json", journeys):
            return jsonify({"status": "error", "message": "Could not record trip start"}), 500

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
            "arduino_sent": arduino_sent,
            "mode": "hardware" if arduino_sent else "simulation"
        })

    except Exception as e:
        print("[/api/trips/start] Error:", e)
        return jsonify({"status": "error", "message": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# Trip end
# ---------------------------------------------------------------------------

@app.route("/api/trips/end", methods=["POST", "OPTIONS"])
@serialize_mutation
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
        original_journeys = [dict(item) for item in journeys]

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
            send_arduino_command("R")
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

        # Update journey
        completed_at = now_iso()
        journeys[journey_idx].update({
            "exit_stop": exit_stop,
            "stops": num_stops,
            "fare": fare,
            "completed_at": completed_at,
            "status": "completed"
        })
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
        original_txns = [dict(item) for item in txns]
        txns.append(transaction)

        if not save_data("journeys.json", journeys):
            return jsonify({"status": "error", "message": "Could not record completed trip"}), 500
        if not save_data("transactions.json", txns):
            save_data("journeys.json", original_journeys)
            return jsonify({"status": "error", "message": "Could not record fare transaction"}), 500
        if not save_user(user):
            save_data("journeys.json", original_journeys)
            save_data("transactions.json", original_txns)
            return jsonify({"status": "error", "message": "Could not update wallet balance"}), 500

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
            "arduino_sent": arduino_sent,
            "mode": "hardware" if arduino_sent else "simulation"
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


# ===========================================================================
# Startup
# ===========================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("   FaceCard — Prototype Backend")
    print(f"   Port: {BACKEND_PORT}")
    print(f"   Arduino: {ARDUINO_PORT or 'simulation mode'} @ {ARDUINO_BAUD} baud")
    print(f"   Face threshold: {FACE_THRESHOLD}")
    print(f"   Fare per stop: Rs.{FARE_PER_STOP}")
    print("=" * 60 + "\n")

    load_known_faces()
    if ARDUINO_PORT:
        try_connect_arduino()
    else:
        print("[Arduino] No port configured; running in simulation mode")

    app.run(host="0.0.0.0", port=BACKEND_PORT, threaded=True, debug=False)
