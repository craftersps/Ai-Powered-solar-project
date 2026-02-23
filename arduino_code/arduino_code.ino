/*
 * IoT Environmental Monitoring System with Solar Tracker, Dust Sensor, and Air Pressure
 * 
 * Sensors:
 * - DHT11: Temperature & Humidity (Pin 2)
 * - LDR Sensors: Solar tracking (A0, A1)
 * - Sharp GP2Y1014AU0F: Dust/Air Quality (A2, Digital Pin 7)
 * - MPS20N0040D + HX710B: Air Pressure (Pin 11, 12)
 * - Servo Motor: Solar panel positioning (Pin 9)
 * 
 * Sends JSON data via Serial to Python server
 */

#include <DHT.h>
#include <Servo.h>

// ============================================
// PIN DEFINITIONS
// ============================================

// DHT Sensor
#define DHTPIN 2
#define DHTTYPE DHT11

// Solar Tracker LDRs
#define LDR_LEFT A0
#define LDR_RIGHT A1

// Dust Sensor
#define DUST_SENSOR_PIN A2
#define DUST_LED_PIN 7

// Air Pressure Sensor (HX710B)
#define DOUT_PIN 12
#define SCK_PIN 11

// Servo Motor
#define SERVO_PIN 9

// ============================================
// SENSOR OBJECTS
// ============================================

DHT dht(DHTPIN, DHTTYPE);
Servo solarTracker;

// ============================================
// AIR PRESSURE VARIABLES
// ============================================

long zeroOffset = 0;
float scaleFactor = 25000.0;   // RAW counts per kPa
float lastPressure = 0;        // Store last valid pressure reading

// ============================================
// SOLAR TRACKER CONFIGURATION
// ============================================

int servoPosition = 90;        // Current servo angle
const int CENTER_POSITION = 90; // Center/home position
const int TOLERANCE = 30;       // Light difference threshold
const int STEP_SIZE = 1;        // Movement increment
const int MIN_ANGLE = 30;       // Minimum servo angle
const int MAX_ANGLE = 150;      // Maximum servo angle

// ============================================
// DUST SENSOR TIMING (microseconds)
// ============================================

const int SAMPLING_TIME = 280;  // Time to sample signal
const int DELTA_TIME = 40;      // Delay after sampling
const int SLEEP_TIME = 9680;    // LED off time

// ============================================
// TIMING CONTROL
// ============================================

unsigned long lastDHTUpdate = 0;
unsigned long lastPressureUpdate = 0;
const unsigned long DHT_INTERVAL = 2000;      // Read DHT every 2 seconds
const unsigned long PRESSURE_INTERVAL = 5000; // Read pressure every 5 seconds (less frequent)

// ============================================
// AIR PRESSURE FUNCTIONS
// ============================================

// ---------- READ HX710B (OPTIMIZED) ----------
long readHX710B() {
  unsigned long data = 0;

  uint32_t timeout = millis();
  while (digitalRead(DOUT_PIN) == HIGH) {
    if (millis() - timeout > 100) return 0;  // Shorter timeout to not block servo
  }

  for (int i = 0; i < 24; i++) {
    digitalWrite(SCK_PIN, HIGH);
    delayMicroseconds(1);
    data = (data << 1) | digitalRead(DOUT_PIN);
    digitalWrite(SCK_PIN, LOW);
    delayMicroseconds(1);
  }

  // 25th pulse → select channel
  digitalWrite(SCK_PIN, HIGH);
  delayMicroseconds(1);
  digitalWrite(SCK_PIN, LOW);

  long result = (long)data;
  if (data & 0x800000) result |= 0xFF000000;

  return result;
}

// ---------- AVERAGE FILTER (OPTIMIZED) ----------
long readAverage(byte samples = 5) {  // Reduced from 12 to 5 samples
  long sum = 0;
  byte valid = 0;

  for (byte i = 0; i < samples; i++) {
    long v = readHX710B();
    if (v != 0) {
      sum += v;
      valid++;
    }
    delay(2);  // Reduced from 8ms to 2ms - much faster!
  }

  if (valid == 0) return 0;
  return sum / valid;
}

// ---------- AUTO ZERO ----------
void calibrateZero() {
  Serial.println("{\"status\":\"info\",\"msg\":\"Keep sensor open to air...\"}");
  delay(3000);

  zeroOffset = readAverage(20);  // More samples during calibration is OK

  Serial.print("{\"status\":\"info\",\"msg\":\"Zero offset = ");
  Serial.print(zeroOffset);
  Serial.println("\"}");
  Serial.println("{\"status\":\"info\",\"msg\":\"Zero calibration done\"}");
}

// ============================================
// SETUP
// ============================================

void setup() {
  // Initialize serial communication
  Serial.begin(9600);
  delay(1000);
  
  // Initialize DHT sensor
  dht.begin();
  
  // Initialize dust sensor LED pin
  pinMode(DUST_LED_PIN, OUTPUT);
  
  // Initialize air pressure sensor
  pinMode(DOUT_PIN, INPUT);
  pinMode(SCK_PIN, OUTPUT);
  
  // Initialize and center solar tracker
  solarTracker.attach(SERVO_PIN);
  solarTracker.write(servoPosition);
  
  // Calibrate pressure sensor
  calibrateZero();
  
  // Startup delay for sensor stabilization
  delay(1000);
  
  // Send ready message
  Serial.println("{\"status\":\"READY\",\"msg\":\"IoT Environmental Monitor Started\"}");
}

// ============================================
// MAIN LOOP
// ============================================

void loop() {
  // ============================================
  // SOLAR TRACKER - Continuous Operation (HIGHEST PRIORITY)
  // ============================================
  
  int leftLDR = analogRead(LDR_LEFT);
  int rightLDR = analogRead(LDR_RIGHT);
  
  // Calculate light intensity (assumes HIGH = BRIGHT)
  // If your LDRs are inverted (HIGH = DARK), uncomment these:
  // leftLDR = 1023 - leftLDR;
  // rightLDR = 1023 - rightLDR;
  
  int lightDifference = leftLDR - rightLDR;
  String trackerAction = "";
  
  // REVERSED LOGIC for backwards mounted servo
  if (lightDifference > TOLERANCE) {
    // LEFT is brighter → move servo RIGHT (increase angle)
    servoPosition += STEP_SIZE;
    trackerAction = "RIGHT";
  }
  else if (lightDifference < -TOLERANCE) {
    // RIGHT is brighter → move servo LEFT (decrease angle)
    servoPosition -= STEP_SIZE;
    trackerAction = "LEFT";
  }
  else {
    // Light is balanced → return to center
    if (servoPosition > CENTER_POSITION) {
      servoPosition -= STEP_SIZE;
      trackerAction = "RETURN_LEFT";
    } else if (servoPosition < CENTER_POSITION) {
      servoPosition += STEP_SIZE;
      trackerAction = "RETURN_RIGHT";
    } else {
      trackerAction = "CENTER";
    }
  }
  
  // Constrain servo position to safe limits
  servoPosition = constrain(servoPosition, MIN_ANGLE, MAX_ANGLE);
  solarTracker.write(servoPosition);
  
  // ============================================
  // DUST SENSOR - Continuous Reading
  // ============================================
  
  // Turn on LED
  digitalWrite(DUST_LED_PIN, LOW);
  delayMicroseconds(SAMPLING_TIME);
  
  // Read dust sensor value
  int dustRaw = analogRead(DUST_SENSOR_PIN);
  
  delayMicroseconds(DELTA_TIME);
  
  // Turn off LED
  digitalWrite(DUST_LED_PIN, HIGH);
  delayMicroseconds(SLEEP_TIME);
  
  // Convert to voltage (0-5V mapped to 0-1023)
  float dustVoltage = dustRaw * (5.0 / 1024.0);
  
  // Convert to dust density (µg/m³)
  // Linear equation from datasheet
  float dustDensity = (170.0 * dustVoltage) - 0.1;
  
  // Ensure non-negative values
  if (dustDensity < 0) {
    dustDensity = 0;
  }
  
  // ============================================
  // AIR PRESSURE - Timed Reading (Every 5 seconds to not interfere with servo)
  // ============================================
  
  if (millis() - lastPressureUpdate >= PRESSURE_INTERVAL) {
    lastPressureUpdate = millis();
    
    long raw = readAverage(5);  // Fast reading: only 5 samples with 2ms delay = 10ms total

    // Convert to pressure
    float pressure_kPa = (raw - zeroOffset) / scaleFactor;

    // Clamp to sensor limits (0-40 kPa)
    if (pressure_kPa < 0) pressure_kPa = 0;
    if (pressure_kPa > 40) pressure_kPa = 40;
    
    lastPressure = pressure_kPa;  // Store for use in JSON output
  }
  
  // ============================================
  // DHT SENSOR - Timed Reading (Every 2 seconds)
  // ============================================
  
  if (millis() - lastDHTUpdate >= DHT_INTERVAL) {
    lastDHTUpdate = millis();
    
    float temperature = dht.readTemperature();
    float humidity = dht.readHumidity();
    
    // Check if readings are valid
    if (isnan(temperature) || isnan(humidity)) {
      Serial.println("{\"error\":\"DHT sensor read failed\"}");
    } else {
      // ============================================
      // SEND JSON DATA
      // ============================================
      
      Serial.print("{");
      
      // Environmental data
      Serial.print("\"temp\":");
      Serial.print(temperature, 1);
      
      Serial.print(",\"hum\":");
      Serial.print(humidity, 0);
      
      Serial.print(",\"dust\":");
      Serial.print(dustDensity, 2);
      
      // Air pressure data (use last stored value)
      Serial.print(",\"pressure\":");
      Serial.print(lastPressure, 3);
      
      Serial.print(",\"time\":");
      Serial.print(millis() / 1000);
      
      // Solar tracker data
      Serial.print(",\"tracker\":{");
      Serial.print("\"angle\":");
      Serial.print(servoPosition);
      
      Serial.print(",\"ldr_left\":");
      Serial.print(leftLDR);
      
      Serial.print(",\"ldr_right\":");
      Serial.print(rightLDR);
      
      Serial.print(",\"diff\":");
      Serial.print(lightDifference);
      
      Serial.print(",\"action\":\"");
      Serial.print(trackerAction);
      Serial.print("\"");
      
      Serial.print(",\"status\":\"");
      if (abs(lightDifference) <= TOLERANCE && servoPosition == CENTER_POSITION) {
        Serial.print("CENTERED");
      } else if (trackerAction.startsWith("RETURN")) {
        Serial.print("RETURNING");
      } else if (trackerAction == "LEFT" || trackerAction == "RIGHT") {
        Serial.print("TRACKING");
      } else {
        Serial.print("IDLE");
      }
      Serial.print("\"");
      
      Serial.print("}");
      Serial.println("}");
    }
  }
  
  // Small delay for stability (50ms) - IMPORTANT: Keep servo responsive
  delay(50);
}
