# Wiring Guide

Complete wiring reference for all 5 sensors.

---

## Full Pinout Table

| Arduino Pin | Connected To | Notes |
|-------------|-------------|-------|
| `5V` | DHT11 VCC, GP2Y VCC & V-LED, HX710B VCC, Servo VCC | All sensors share 5V |
| `GND` | All sensor GNDs | Common ground |
| `Pin 2` | DHT11 DATA | Requires 10kΩ pull-up to 5V |
| `Pin 7` | GP2Y1014 Pin 3 (LED) | Pulse control — goes HIGH for 280µs |
| `Pin 9` | SG90 Servo signal (yellow/orange wire) | PWM pin required |
| `Pin 11` | HX710B SCK | Clock line |
| `Pin 12` | HX710B DOUT | Data line |
| `A0` | LDR Left (junction with 10kΩ to GND) | Analog read 0–1023 |
| `A1` | LDR Right (junction with 10kΩ to GND) | Analog read 0–1023 |
| `A2` | GP2Y1014 Pin 5 (Vo) | Analog voltage output |

---

## Sensor-by-Sensor Wiring

### DHT11 — Temperature & Humidity

```
DHT11 (facing front, 3 pins)

  [VCC]  → Arduino 5V
  [DATA] → Arduino Pin 2
           └── also connect 10kΩ resistor from DATA to 5V (pull-up)
  [GND]  → Arduino GND
```

---

### Sharp GP2Y1014AU0F — Dust Sensor

The GP2Y1014 has 6 pins. Looking at the connector with the notch facing up:

```
Pin 1 (V-LED)     → 150Ω resistor → Arduino 5V
Pin 2 (LED-GND)   → Arduino GND
Pin 3 (LED)       → Arduino Pin 7   ← pulse control
Pin 4 (GND)       → Arduino GND
Pin 5 (Vo)        → Arduino A2      ← analog signal output
Pin 6 (VCC)       → Arduino 5V
```

> ⚠️ **The 150Ω resistor on Pin 1 is mandatory.** Without it the internal IR LED burns out quickly.

---

### MPS20N0040D + HX710B — Pressure Sensor

```
HX710B board:
  VCC  → Arduino 5V
  GND  → Arduino GND
  DOUT → Arduino Pin 12
  SCK  → Arduino Pin 11
  A+   → MPS20N0040D positive port (red wire)
  A-   → MPS20N0040D negative port (black wire)
```

The MPS20N0040D has two small ports (brass fittings). Leave both ports open for free-air differential measurement. Connect tubing to measure pressure of a specific gas or liquid.

---

### LDR Solar Tracker — Dual Light Sensors

Each LDR uses a voltage divider with a 10kΩ resistor:

```
Left LDR:
  5V ──── [LDR] ──┬── Arduino A0
                  │
                [10kΩ]
                  │
                 GND

Right LDR:
  5V ──── [LDR] ──┬── Arduino A1
                  │
                [10kΩ]
                  │
                 GND
```

Mount the LDRs on either side of a small vertical divider (a piece of cardboard works). The divider creates shadow on one LDR when light comes from the side, giving a clear left/right signal.

---

### SG90 Servo — Panel Rotation

```
SG90 wire colors:
  Brown / Black → Arduino GND
  Red           → Arduino 5V
  Orange/Yellow → Arduino Pin 9 (PWM signal)
```

The servo should be mounted so it can rotate the solar panel from 30° to 150° (120° total sweep).

---

## Power Considerations

The Arduino 5V pin can supply roughly **400–500mA** total. Here's the current budget:

| Component | Typical Current |
|-----------|----------------|
| DHT11 | 1–2.5mA |
| Sharp GP2Y1014 (pulsed) | 20mA (peak, very brief) |
| HX710B | 1.5mA |
| SG90 Servo (moving) | 100–250mA |
| LDRs | <1mA |
| **Total** | **~130–270mA** |

This is within the Arduino's limit for light loads. However, if the servo is under mechanical load or you add more components, use an **external 5V power supply** for the servo.
