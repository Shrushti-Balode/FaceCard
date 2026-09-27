/*
  gate_controller.ino — Face Ride Connect Gate Controller
  =========================================================
  NEWLY RECREATED — original Arduino code was not present in the repository.
  Recreated based on documented hardware requirements.

  Hardware:
    Pin 9  — Servo motor (gate)
    Pin 11 — Green LED (access granted)
    Pin 12 — Red LED   (access denied)
    Serial — 9600 baud (USB to PC running Python backend)

  Commands received from Python backend via serial:
    'G' — Grant access: open gate (servo 90°), green LED on, red LED off
    'R' — Reject access: close gate (servo 0°), red LED on, green LED off

  The gate auto-closes after GATE_OPEN_MS milliseconds.

  Upload this sketch to Arduino Uno/Nano before connecting the backend.
  Set ARDUINO_PORT=COM7 (or your actual port) in backend/.env
*/

#include <Servo.h>

// --- Pin definitions ---
const int SERVO_PIN     = 9;
const int GREEN_LED_PIN = 11;
const int RED_LED_PIN   = 12;

// --- Timing ---
const unsigned long GATE_OPEN_MS = 3000;  // Gate stays open for 3 seconds

// --- State ---
Servo gateServo;
bool gateOpen = false;
unsigned long gateOpenedAt = 0;

void setup() {
  Serial.begin(9600);

  gateServo.attach(SERVO_PIN);
  pinMode(GREEN_LED_PIN, OUTPUT);
  pinMode(RED_LED_PIN, OUTPUT);

  // Initial state: gate closed, red LED on
  closeGate();

  Serial.println("FaceCard Gate Controller Ready");
  Serial.println("Commands: G=Grant/Open, R=Reject/Close");
}

void loop() {
  // Read serial command from Python backend
  if (Serial.available() > 0) {
    char cmd = Serial.read();

    if (cmd == 'G') {
      grantAccess();
    } else if (cmd == 'R') {
      denyAccess();
    }
  }

  // Auto-close gate after GATE_OPEN_MS
  if (gateOpen && (millis() - gateOpenedAt >= GATE_OPEN_MS)) {
    closeGate();
    Serial.println("Gate auto-closed");
  }
}

// Open gate: servo to 90°, green LED on, red LED off
void grantAccess() {
  gateServo.write(90);
  digitalWrite(GREEN_LED_PIN, HIGH);
  digitalWrite(RED_LED_PIN, LOW);
  gateOpen = true;
  gateOpenedAt = millis();
  Serial.println("GRANTED: Gate open");
}

// Deny: keep gate closed, red LED on, green LED off
void denyAccess() {
  closeGate();
  Serial.println("DENIED: Gate closed");
}

// Close gate: servo to 0°, red LED on, green LED off
void closeGate() {
  gateServo.write(0);
  digitalWrite(RED_LED_PIN, HIGH);
  digitalWrite(GREEN_LED_PIN, LOW);
  gateOpen = false;
}
