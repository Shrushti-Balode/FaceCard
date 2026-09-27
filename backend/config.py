"""
config.py — Load backend configuration from .env file.
All configurable values are centralised here.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the backend directory
_env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)

# Flask
BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "5001"))

# Arduino serial
ARDUINO_PORT: str = os.getenv("ARDUINO_PORT", "COM7")
ARDUINO_BAUD: int = int(os.getenv("ARDUINO_BAUD", "9600"))

# Face recognition
FACE_THRESHOLD: float = float(os.getenv("FACE_THRESHOLD", "0.65"))

# Fare
FARE_PER_STOP: int = int(os.getenv("FARE_PER_STOP", "5"))

# Admin
ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "changeme")
