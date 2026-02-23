# API Reference

All endpoints are served by the Flask server at `http://localhost:5000`.

---

## `GET /api/data`

Returns the single most recent sensor reading.

**Response:**
```json
{
  "temperature": 38.2,
  "humidity": 45,
  "dust": 67.3,
  "pressure": 18.4,
  "connected": true,
  "time": "14:32:05",
  "uptime": 3600,
  "tracker": {
    "angle": 95,
    "ldr_left": 512,
    "ldr_right": 498,
    "diff": 14,
    "action": "CENTER",
    "status": "CENTERED"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `temperature` | float | °C, from DHT11 |
| `humidity` | float | %, from DHT11 |
| `dust` | float | µg/m³, from Sharp GP2Y1014 |
| `pressure` | float | kPa differential (0–40), from MPS20N0040D |
| `connected` | bool | Whether Arduino is actively sending data |
| `tracker.angle` | int | Current servo angle (30–150°) |
| `tracker.ldr_left` | int | Left LDR reading (0–1023) |
| `tracker.ldr_right` | int | Right LDR reading (0–1023) |
| `tracker.diff` | int | ldr_left - ldr_right |
| `tracker.action` | string | `LEFT`, `RIGHT`, or `CENTER` |
| `tracker.status` | string | `TRACKING` or `CENTERED` |

---

## `GET /api/history/<hours>`

Returns all stored readings from the last `hours` hours, ordered newest first.

**Example:** `GET /api/history/24` → last 24 hours

**Response:**
```json
[
  {
    "timestamp": "2024-01-15 14:30:00",
    "temperature": 37.8,
    "humidity": 46,
    "dust": 65.1,
    "pressure": 18.2,
    "solar_angle": 94,
    "ldr_left": 510,
    "ldr_right": 501
  },
  ...
]
```

---

## `GET /api/alerts/<count>`

Returns the last `count` alerts that fired, ordered newest first.

**Example:** `GET /api/alerts/20` → last 20 alerts

**Response:**
```json
[
  {
    "level": "critical",
    "sensor": "temperature",
    "message": "Temperature exceeded 40°C — current: 41.2°C",
    "value": 41.2,
    "threshold": 40,
    "timestamp": "2024-01-15 14:28:00"
  },
  ...
]
```

| `level` value | Meaning |
|--------------|---------|
| `"warning"` | Sensor approaching dangerous range |
| `"critical"` | Sensor in dangerous range |

---

## `GET /api/weather`

Returns current weather for Muscat, Oman from Open-Meteo. Cached for 10 minutes.

**Response:**
```json
{
  "temp": 41,
  "feels_like": 44,
  "description": "Clear sky",
  "wind_speed": 18,
  "wind_direction": "NW",
  "humidity": 38,
  "pressure": 1008,
  "visibility": 10,
  "icon": "01d",
  "uv_index": 9,
  "precipitation_probability": 0
}
```

---

## `GET /api/export/csv/<days>`

Downloads a CSV file containing all readings from the last `days` days.

**Example:** `GET /api/export/csv/7` → 7-day CSV download

**CSV columns:**
```
timestamp, temperature, humidity, dust, pressure, solar_angle, ldr_left, ldr_right
```

**Headers returned:**
```
Content-Type: text/csv
Content-Disposition: attachment; filename="sensor_data_7days.csv"
```

---

## `GET /api/db/stats`

Returns statistics about the SQLite database.

**Response:**
```json
{
  "total_readings": 43847,
  "oldest_reading": "2024-01-01 08:00:00",
  "newest_reading": "2024-01-15 14:32:00",
  "db_size_mb": 12.4,
  "readings_today": 3210,
  "uptime_hours": 336
}
```

---

## Alert Thresholds Reference

| Sensor | Warning | Critical |
|--------|---------|----------|
| Temperature | > 35°C | > 40°C |
| Humidity high | > 70% | > 80% |
| Humidity low | < 30% | — |
| Dust (PM2.5) | > 140 µg/m³ | > 180 µg/m³ |
| Pressure high | > 30 kPa | > 35 kPa |
| Pressure low | < 5 kPa | < 2 kPa |

WHO annual PM2.5 safe limit: **15 µg/m³**
