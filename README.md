# FaceCard

FaceCard is a college-project prototype for facial recognition, bus fare collection, and an optional Arduino-controlled gate. It uses an internal Face Card ID (`FC-1001`, `FC-1002`, ...); it does not require government identity numbers.

## Architecture

- React + TypeScript + Vite serves the browser UI on port 8080.
- The browser requests camera permission, captures a frame, and uploads it to Flask on port 5001.
- Flask detects and compares faces using OpenCV, stores prototype users/journeys/transactions as local JSON, and optionally sends serial commands to an Arduino.
- The backend does not open a webcam or require an OpenCV desktop window. The browser camera is the camera input.

## Requirements

- Python 3.10 and Windows PowerShell for the commands below.
- Node.js and npm.
- Optional: Arduino Uno-compatible board, servo on pin 9, green LED on pin 11, red LED on pin 12.
- The backend dependencies pin `opencv-python==4.10.0.84`, verified in the project virtual environment. Avoid replacing it with OpenCV 5.x for this prototype.

## Backend Setup

From the project directory:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

The backend listens on `http://127.0.0.1:5001` by default. Its status endpoint is `GET /api/status`; `/` and `/api/health` are not defined and returning 404 there is expected.

## Frontend Setup

In a second terminal from the project directory:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite `Local` URL printed by the command, normally `http://localhost:8080`. The frontend defaults to port 5001 on the same hostname used to open Vite, so LAN access uses the computer's LAN hostname for both services. Set `VITE_API_BASE_URL` to a full API URL ending in `/api` when the backend is hosted elsewhere.

Camera permission requires `localhost` or a secure HTTPS context in the browser.

## Face Registration

The registration screen collects a name, route, stops, initial wallet load, and one browser-camera image. Flask creates the internal Face Card ID, verifies exactly one face in the image, and stores it locally under `backend/faces/FC-XXXX.jpg`. The API returns the same ID in `face_card_id` and in the user object's `id` field.

The recognition implementation is a simple histogram comparison with a configurable correlation threshold. It is a demonstration, not production-grade face authentication; it has no liveness check and can produce false matches.

## Trips, Fare, and Wallet

The gate scans a browser frame with `POST /api/recognize` (`frame` or `image` multipart field). Unknown/no-face scans send `R` to the Arduino when connected. A recognized face starts a trip with `POST /api/trips/start`; the route and boarding stop are validated, an active trip is recorded, and `G` is sent. A trip ends with `POST /api/trips/end`; fare is Rs.5 per stop by default, deducted once when the completed journey and transaction are recorded. Failed recognition, invalid trips, and insufficient balances do not deduct fare. Repeated trip operations are serialized in the backend process.

Dashboard and admin data endpoints:

| Frontend function | Method and endpoint | Request body | Response and UI behavior |
| --- | --- | --- | --- |
| `Register.handleSubmit` | `POST /api/register` JSON | `firstName`, `lastName`, `route`, `pickup`, `drop`, `walletAmount` | `{face_card_id, user}`; after face upload succeeds, stores that user as the current local session and opens registration success |
| `Register.handleSubmit` | `POST /api/register-face` multipart | `user_id` (the returned Face Card ID), `image` (JPEG) | `{status, face_card_id}`; success completes registration, errors are shown in a toast |
| `getSettingsRoutes` | `GET /api/settings/routes` | None | `{routes, fare_per_stop}`; populates route and stop options |
| `LiveCam.sendFrameForMatch` | `POST /api/recognize` multipart | `frame` (JPEG) | `{recognized, user_id, name, user}` or `{recognized: false, reason}`; match proceeds to trip start/end, denial stays on the scan view |
| `LiveCam.handleTripStart` | `POST /api/trips/start` JSON | `{user_id, boarding_stop}` | `status`, `journey_id`, `wallet`, `arduino_sent`, `mode`; shows grant or the backend denial message |
| `LiveCam.handleTripEnd` | `POST /api/trips/end` JSON | `{user_id, exit_stop}` | `fare`, `balance_after`, `journey_id`, `transaction_id`; shows exit result and updated balance |
| Dashboard storage helpers | `GET /api/users/{FC-ID}`, `/journeys`, `/transactions` | None | User wallet plus journey and transaction arrays; refreshes the signed-in local session and dashboard history |
| Admin page | `POST /api/admin/login` JSON; then `GET /api/users`, `/journeys`, `/transactions` | `{username, password}` for login | `{status, role}` on success; a 401 displays “Invalid credentials”; data endpoints populate admin tables |
| Gate status panel | `GET /api/status` | None | Backend status, Arduino connection/mode, uptime, and registered-face count |

Passenger registration creates a local browser session; there is no passenger password/login system. Admin login is also prototype-only. Change the example admin password in `.env` before use, and do not expose this backend to an untrusted network.

## Arduino Setup

Upload `arduino/gate_controller/gate_controller.ino` to the board. It uses 9600 baud and accepts `G` (green LED, open servo for five seconds, then close) and `R` (red LED, gate closed). Startup is gate-closed with both LEDs off.

Set the board's actual serial port in `backend/.env`, for example `ARDUINO_PORT=COM7`. With `ARDUINO_PORT` blank or a board disconnected, Flask remains available and reports simulation mode; gate results are then software-only.

**HARDWARE TEST REQUIRED:** Verify the selected COM port, wiring, servo direction, and physical gate behavior with the board connected. The prototype cannot confirm hardware actuation while the Arduino is unavailable.

## Configuration

Copy `backend/.env.example` to `backend/.env`. Supported settings are `BACKEND_PORT`, `ARDUINO_PORT`, `ARDUINO_BAUD`, `FACE_THRESHOLD`, `FARE_PER_STOP`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD`. Defaults are port 5001, simulation mode, 9600 baud, threshold 0.65, and Rs.5 per stop.

## Local Data and Privacy

The application creates local users, transaction, journey, and face-image data under `backend/data/` and `backend/faces/`. These paths are ignored by Git; only the safe demo `backend/data/settings.json` is intended to be versioned. Do not commit face images, real names tied to biometrics, wallet/transaction records, passwords, API keys, `.env` files, virtual environments, or `node_modules`. Use fictional data for demos and verify repository tracking before publishing.

The JSON files are suitable only for a single-process prototype. There is no database, robust passenger authentication, liveness detection, or production security/audit guarantee.