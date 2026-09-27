"""
utils.py — Shared helper functions for the Face Ride Connect backend.
"""
import json
import threading
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

_file_lock = threading.Lock()


# ---------------------------------------------------------------------------
# JSON data helpers (atomic read/write)
# ---------------------------------------------------------------------------

def load_data(filename: str) -> list | dict:
    """Load JSON data from backend/data/<filename>. Returns [] or {} on error."""
    path = DATA_DIR / filename
    if not path.exists():
        if filename == "settings.json":
            default_settings = {
                "_note": "Auto-generated default settings",
                "fare_per_stop": 5,
                "bus_id": "BUS_12",
                "routes": {
                    "R1": { "name": "Route R1", "stops": ["Stop A", "Stop B", "Stop C", "Stop D"] }
                }
            }
            path.write_text(json.dumps(default_settings, indent=2), encoding="utf-8")
            return default_settings
        return []
    with _file_lock:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[utils] load_data error ({filename}):", e)
            return [] if filename != "settings.json" else {}


def save_data(filename: str, data: list | dict) -> bool:
    """Save JSON data to backend/data/<filename>. Returns True on success."""
    path = DATA_DIR / filename
    with _file_lock:
        try:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        except Exception as e:
            print(f"[utils] save_data error ({filename}):", e)
            return False


# ---------------------------------------------------------------------------
# Face Card ID generation
# ---------------------------------------------------------------------------

def generate_fc_id() -> str:
    """
    Generate the next sequential Face Card ID (FC-1001, FC-1002, …).
    Thread-safe: reads existing users to find the current max.
    """
    users = load_data("users.json")
    if not isinstance(users, list):
        users = []

    max_num = 1000
    for u in users:
        uid = u.get("id", "")
        if uid.startswith("FC-"):
            try:
                num = int(uid.split("-")[1])
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
    return f"FC-{max_num + 1}"


# ---------------------------------------------------------------------------
# Timestamp helper
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Sequential ID helpers for journeys and transactions
# ---------------------------------------------------------------------------

def generate_journey_id() -> str:
    journeys = load_data("journeys.json")
    if not isinstance(journeys, list):
        journeys = []
    return f"TRIP-{len(journeys) + 1:04d}"


def generate_transaction_id() -> str:
    transactions = load_data("transactions.json")
    if not isinstance(transactions, list):
        transactions = []
    return f"TXN-{len(transactions) + 1:04d}"


# ---------------------------------------------------------------------------
# Fare calculation
# ---------------------------------------------------------------------------

def calculate_fare(boarding_stop: str, exit_stop: str, route_id: str, fare_per_stop: int) -> dict:
    """
    Calculate fare based on number of stops between boarding and exit.
    Returns {"fare": int, "stops": int, "error": str|None}
    """
    settings = load_data("settings.json")
    routes = settings.get("routes", {})

    if route_id not in routes:
        return {"fare": 0, "stops": 0, "error": f"Unknown route: {route_id}"}

    stops_list = routes[route_id].get("stops", [])

    try:
        boarding_idx = stops_list.index(boarding_stop)
    except ValueError:
        return {"fare": 0, "stops": 0, "error": f"Boarding stop '{boarding_stop}' not in route {route_id}"}

    try:
        exit_idx = stops_list.index(exit_stop)
    except ValueError:
        return {"fare": 0, "stops": 0, "error": f"Exit stop '{exit_stop}' not in route {route_id}"}

    num_stops = abs(exit_idx - boarding_idx)
    if num_stops == 0:
        return {"fare": 0, "stops": 0, "error": "Boarding and exit stop are the same"}

    fare = num_stops * fare_per_stop
    return {"fare": fare, "stops": num_stops, "error": None}


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------

def get_user_by_id(fc_id: str) -> dict | None:
    users = load_data("users.json")
    if not isinstance(users, list):
        return None
    for u in users:
        if u.get("id") == fc_id:
            return u
    return None


def save_user(user: dict) -> bool:
    users = load_data("users.json")
    if not isinstance(users, list):
        users = []
    # Replace existing or append
    idx = next((i for i, u in enumerate(users) if u.get("id") == user["id"]), None)
    if idx is not None:
        users[idx] = user
    else:
        users.append(user)
    return save_data("users.json", users)


def check_active_trip(fc_id: str) -> dict | None:
    """Return the in-progress journey for a user, or None."""
    journeys = load_data("journeys.json")
    if not isinstance(journeys, list):
        return None
    for j in journeys:
        if j.get("user_id") == fc_id and j.get("status") == "in_progress":
            return j
    return None
