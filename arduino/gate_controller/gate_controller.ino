/*
  gate_controller.ino
  ====================

  Existing hardware / protocol PRESERVED:

    Pin 9  -> Servo
    Pin 11 -> Green LED
    Pin 12 -> Red LED

    Serial:
      9600 baud
      'G' = Grant access
      'R' = Reject access

  Added:

    16x2 LCD in 4-bit mode

    LCD RS -> D7
    LCD E  -> D8
    LCD D4 -> D2
    LCD D5 -> D3
    LCD D6 -> D4
    LCD D7 -> D5

  LCD behavior:

    On G:
      Welcome to bus
      Balance: Rs 42

    On R:
      Face not
      validated!

  Gate automatically closes after 3 seconds.
*/

#include <Servo.h>
#include <LiquidCrystal.h>

// =====================================================
// EXISTING PIN DEFINITIONS
// DO NOT CHANGE THESE
// =====================================================

const int SERVO_PIN     = 9;
const int GREEN_LED_PIN = 11;
const int RED_LED_PIN   = 12;

// =====================================================
// LCD PIN DEFINITIONS
// LiquidCrystal(RS, E, D4, D5, D6, D7)
// =====================================================

LiquidCrystal lcd(7, 8, 2, 3, 4, 5);

// =====================================================
// TIMING
// =====================================================

const unsigned long GATE_OPEN_MS = 3000;

// =====================================================
// STATE
// =====================================================

Servo gateServo;

bool gateOpen = false;
unsigned long gateOpenedAt = 0;


// =====================================================
// SETUP
// =====================================================

void setup() {

  // Keep original serial communication
  Serial.begin(9600);

  // Servo
  gateServo.attach(SERVO_PIN);

  // LEDs
  pinMode(GREEN_LED_PIN, OUTPUT);
  pinMode(RED_LED_PIN, OUTPUT);

  // LCD
  lcd.begin(16, 2);

  // Initial state
  closeGate();

  // Keep original startup messages
  Serial.println("FaceCard Gate Controller Ready");
  Serial.println("Commands: G=Grant/Open, R=Reject/Close");
}


// =====================================================
// MAIN LOOP
// =====================================================

void loop() {

  // Check for command from computer
  if (Serial.available() > 0) {

    char cmd = Serial.read();

    // Grant access
    if (cmd == 'G') {
      grantAccess();
    }

    // Reject access
    else if (cmd == 'R') {
      denyAccess();
    }
  }

  // Automatically close gate after 3 seconds
  if (gateOpen &&
      (millis() - gateOpenedAt >= GATE_OPEN_MS)) {

    closeGate();

    Serial.println("Gate auto-closed");
  }
}


// =====================================================
// GRANT ACCESS
// =====================================================

void grantAccess() {

  // Open servo
  gateServo.write(90);

  // Green ON
  digitalWrite(GREEN_LED_PIN, HIGH);

  // Red OFF
  digitalWrite(RED_LED_PIN, LOW);

  // Record gate opening time
  gateOpen = true;
  gateOpenedAt = millis();

  // LCD message
  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("Welcome to bus");

  lcd.setCursor(0, 1);
  lcd.print("Balance: Rs 42");

  // Original serial response
  Serial.println("GRANTED: Gate open");
}


// =====================================================
// DENY ACCESS
// =====================================================

void denyAccess() {

  // Close gate and set red LED
  closeGate();

  // LCD message
  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("Face not");

  lcd.setCursor(0, 1);
  lcd.print("validated!");

  // Original serial response
  Serial.println("DENIED: Gate closed");
}


// =====================================================
// CLOSE GATE
// =====================================================

void closeGate() {

  // Servo closed
  gateServo.write(0);

  // Red ON
  digitalWrite(RED_LED_PIN, HIGH);

  // Green OFF
  digitalWrite(GREEN_LED_PIN, LOW);

  // Update state
  gateOpen = false;

  // Standby LCD screen
  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("Scan your face");

  lcd.setCursor(0, 1);
  lcd.print("Waiting...");
}