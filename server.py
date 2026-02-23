"""
IoT Environmental Monitoring System - Server with Open-Meteo Weather API
Version: 4.1 (Free Weather API - No key needed!)

Features:
- Arduino serial communication with REAL connection status
- 5 Sensors: Temperature, Humidity, Dust, Air Pressure, Solar Tracker
- SQLite database storage
- RESTful API endpoints
- Open-Meteo weather integration (FREE!)
- Data export (CSV/JSON)
"""

from flask import Flask, render_template, jsonify, Response
from io import StringIO
import serial
import serial.tools.list_ports
import threading
import time
import json
import sqlite3
from datetime import datetime, timedelta
import os
import csv
import requests

app = Flask(__name__)

# ============================================
# DATABASE SCHEMA WITH AIR PRESSURE
# ============================================

def init_database():
    """Initialize SQLite database with air pressure column"""
    conn = sqlite3.connect('environmental_data.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='readings'")
        table_exists = cursor.fetchone()
        
        if table_exists:
            cursor.execute("PRAGMA table_info(readings)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            print(f"📊 Existing columns: {column_names}")
            
            # Add new columns if missing
            columns_to_add = {
                'dust_density': 'REAL',
                'air_pressure': 'REAL',
                'tracker_angle': 'REAL',
                'ldr_left': 'INTEGER',
                'ldr_right': 'INTEGER',
                'light_diff': 'INTEGER',
                'tracker_status': 'TEXT'
            }
            
            for col_name, col_type in columns_to_add.items():
                if col_name not in column_names:
                    print(f"➕ Adding {col_name} column...")
                    cursor.execute(f"ALTER TABLE readings ADD COLUMN {col_name} {col_type}")
        else:
            print("🆕 Creating new readings table...")
            cursor.execute('''
                CREATE TABLE readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    temperature REAL,
                    humidity REAL,
                    dust_density REAL,
                    air_pressure REAL,
                    tracker_angle REAL,
                    ldr_left INTEGER,
                    ldr_right INTEGER,
                    light_diff INTEGER,
                    tracker_status TEXT,
                    status TEXT
                )
            ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                message TEXT,
                level TEXT
            )
        ''')
        
        conn.commit()
        print("✅ Database initialized successfully!")
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        print("🔄 Recreating database...")
        
        cursor.execute("DROP TABLE IF EXISTS readings")
        cursor.execute("DROP TABLE IF EXISTS alerts")
        
        cursor.execute('''
            CREATE TABLE readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                temperature REAL,
                humidity REAL,
                dust_density REAL,
                air_pressure REAL,
                tracker_angle REAL,
                ldr_left INTEGER,
                ldr_right INTEGER,
                light_diff INTEGER,
                tracker_status TEXT,
                status TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                message TEXT,
                level TEXT
            )
        ''')
        
        conn.commit()
        print("✅ Database recreated!")
    
    finally:
        conn.close()

# ============================================
# DATABASE OPERATIONS
# ============================================

def save_reading(temp, hum, dust, pressure, tracker_angle, ldr_left, ldr_right, light_diff, tracker_status, status):
    """Save sensor reading to database with air pressure"""
    try:
        conn = sqlite3.connect('environmental_data.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO readings 
            (temperature, humidity, dust_density, air_pressure, tracker_angle, ldr_left, ldr_right, 
             light_diff, tracker_status, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (temp, hum, dust, pressure, tracker_angle, ldr_left, ldr_right, light_diff, tracker_status, status))
        
        conn.commit()
        conn.close()
        print(f"💾 Saved: T={temp}°C, H={hum}%, Dust={dust}µg/m³, Pressure={pressure}kPa, Angle={tracker_angle}°")
        return True
        
    except Exception as e:
        print(f"❌ Failed to save reading: {e}")
        return False

def save_alert(message, level="INFO"):
    """Save alert to database"""
    try:
        conn = sqlite3.connect('environmental_data.db')
        cursor = conn.cursor()
        
        cursor.execute('INSERT INTO alerts (message, level) VALUES (?, ?)', (message, level))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Failed to save alert: {e}")
        return False

# ============================================
# CURRENT DATA STORAGE
# ============================================

current_data = {
    'temperature': 0,
    'humidity': 0,
    'dust': 0,
    'pressure': 0,
    'time': '--:--:--',
    'status': 'Starting...',
    'alert': '',
    'connected': False,
    'tracker': {
        'angle': 90,
        'ldr_left': 0,
        'ldr_right': 0,
        'diff': 0,
        'action': 'CENTER',
        'status': 'INITIALIZING'
    }
}

# ============================================
# ARDUINO COMMUNICATION
# ============================================

def find_arduino_port():
    """Automatically detect Arduino port"""
    ports = serial.tools.list_ports.comports()
    
    for port in ports:
        print(f"🔍 Found port: {port.device} - {port.description}")
        
        if any(keyword in port.description.lower() for keyword in ['arduino', 'ch340', 'usb']):
            return port.device
    
    common_ports = ['COM3', 'COM4', 'COM5', 'COM6', '/dev/ttyUSB0', '/dev/ttyACM0']
    for port in common_ports:
        try:
            test_ser = serial.Serial(port, 9600, timeout=0.1)
            test_ser.close()
            return port
        except:
            continue
    
    return None

def read_arduino():
    """Main Arduino data reading thread"""
    global current_data
    
    current_data['connected'] = False
    current_data['status'] = 'Searching for Arduino...'
    
    arduino_found = False
    
    while True:
        try:
            port = find_arduino_port()
            
            if port is None:
                if not arduino_found:
                    print("=" * 60)
                    print("❌ NO ARDUINO FOUND!")
                    print("=" * 60)
                
                current_data['connected'] = False
                current_data['status'] = '❌ Arduino NOT connected - Check USB!'
                time.sleep(5)
                continue
            
            print(f"🔍 Found potential Arduino on {port}...")
            
            try:
                ser = serial.Serial(port, 9600, timeout=2)
                time.sleep(2)
                
                print("⏳ Waiting for data from Arduino...")
                data_received = False
                timeout_counter = 0
                
                while timeout_counter < 10:
                    if ser.in_waiting > 0:
                        line = ser.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            print(f"✅ Data received: {line[:50]}...")
                            data_received = True
                            arduino_found = True
                            break
                    time.sleep(1)
                    timeout_counter += 1
                    print(f"   Waiting... ({timeout_counter}/10)")
                
                if not data_received:
                    print("❌ No data from Arduino!")
                    ser.close()
                    current_data['connected'] = False
                    current_data['status'] = '❌ No data - Upload sketch!'
                    time.sleep(5)
                    continue
                
                print("=" * 60)
                print("✅ ARDUINO CONNECTED AND WORKING!")
                print("=" * 60)
                
                current_data['connected'] = True
                current_data['status'] = 'Connected ✓'
                
                # Read loop
                while True:
                    try:
                        if ser.in_waiting > 0:
                            line = ser.readline().decode('utf-8', errors='ignore').strip()
                            
                            if not line or line == '':
                                continue
                            
                            print(f"📡 Received: {line}")
                            
                            try:
                                data = json.loads(line)
                                
                                if 'status' in data and 'msg' in data:
                                    print(f"ℹ️ {data['msg']}")
                                    continue
                                
                                if 'error' in data:
                                    print(f"⚠️ {data['error']}")
                                    current_data['alert'] = data['error']
                                    continue
                                
                                if 'temp' in data and 'hum' in data:
                                    current_data['temperature'] = data['temp']
                                    current_data['humidity'] = data['hum']
                                    current_data['dust'] = data.get('dust', 0)
                                    current_data['pressure'] = data.get('pressure', 0)
                                    current_data['time'] = datetime.now().strftime('%H:%M:%S')
                                    current_data['status'] = 'Active ✓'
                                    current_data['connected'] = True
                                    
                                    if 'tracker' in data:
                                        current_data['tracker'] = data['tracker']
                                    
                                    alert_msg = ""
                                    if data['temp'] > 40:
                                        alert_msg = "🔥 High temperature!"
                                        save_alert(f"High temperature: {data['temp']}°C", "WARNING")
                                    elif data['hum'] > 80:
                                        alert_msg = "💧 High humidity!"
                                        save_alert(f"High humidity: {data['hum']}%", "WARNING")
                                    elif data.get('dust', 0) > 150:
                                        alert_msg = "🌫️ Poor air quality!"
                                        save_alert(f"High dust: {data.get('dust')}µg/m³", "WARNING")
                                    elif data.get('pressure', 0) > 35 or data.get('pressure', 0) < 5:
                                        alert_msg = "⚠️ Abnormal air pressure!"
                                        save_alert(f"Pressure: {data.get('pressure')}kPa", "WARNING")
                                    else:
                                        alert_msg = "✅ All systems normal"
                                    
                                    current_data['alert'] = alert_msg
                                    
                                    tracker = current_data['tracker']
                                    save_reading(
                                        data['temp'],
                                        data['hum'],
                                        data.get('dust', 0),
                                        data.get('pressure', 0),
                                        tracker.get('angle', 90),
                                        tracker.get('ldr_left', 0),
                                        tracker.get('ldr_right', 0),
                                        tracker.get('diff', 0),
                                        tracker.get('status', 'UNKNOWN'),
                                        'OK'
                                    )
                                    
                            except json.JSONDecodeError as e:
                                print(f"⚠️ Invalid JSON: {line}")
                                continue
                        
                        time.sleep(0.1)
                        
                    except Exception as e:
                        print(f"❌ Read error: {e}")
                        current_data['connected'] = False
                        current_data['status'] = 'Connection lost'
                        break
                
            except serial.SerialException as e:
                print(f"❌ Serial port error: {e}")
                current_data['connected'] = False
                current_data['status'] = f'Serial error'
                time.sleep(5)
                continue
            
        except Exception as e:
            print(f"❌ Connection error: {e}")
            current_data['connected'] = False
            current_data['status'] = 'Disconnected'
            time.sleep(5)

# ============================================
# WEB ROUTES
# ============================================

@app.route('/')
def index():
    """Serve dashboard"""
    return render_template('dashboard.html')

@app.route('/api/data')
def get_data():
    """Get current sensor data"""
    return jsonify(current_data)

@app.route('/api/history')
@app.route('/api/history/<int:hours>')
def get_history(hours=24):
    """Get historical data"""
    try:
        conn = sqlite3.connect('environmental_data.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT timestamp, temperature, humidity, dust_density, air_pressure, tracker_angle
            FROM readings 
            WHERE timestamp > datetime('now', '-' || ? || ' hours')
            ORDER BY timestamp DESC
            LIMIT 1000
        ''', (hours,))
        
        rows = cursor.fetchall()
        conn.close()
        
        data = []
        for row in rows:
            data.append({
                'timestamp': row[0],
                'temperature': row[1],
                'humidity': row[2],
                'dust': row[3],
                'pressure': row[4],
                'tracker_angle': row[5]
            })
        
        return jsonify(data)
        
    except Exception as e:
        print(f"❌ History error: {e}")
        return jsonify({'error': str(e)})

@app.route('/api/export/csv')
@app.route('/api/export/csv/<int:days>')
def export_csv(days=7):
    """Export data as CSV with air pressure"""
    try:
        conn = sqlite3.connect('environmental_data.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT timestamp, temperature, humidity, dust_density, air_pressure,
                   tracker_angle, ldr_left, ldr_right, light_diff, tracker_status
            FROM readings 
            WHERE timestamp > datetime('now', '-' || ? || ' days')
            ORDER BY timestamp DESC
        ''', (days,))
        
        rows = cursor.fetchall()
        conn.close()
        
        output = StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'Timestamp', 'Temperature (°C)', 'Humidity (%)', 'Dust (µg/m³)', 'Air Pressure (kPa)',
            'Panel Angle (°)', 'Left LDR', 'Right LDR', 'Light Diff', 'Tracker Status'
        ])
        
        for row in rows:
            writer.writerow(row)
        
        filename = f"environmental_data_last_{days}_days.csv"
        
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/weather')
def get_weather():
    """Get weather data from Open-Meteo API (FREE - No API key needed!)"""
    try:
        # Muscat, Oman coordinates
        lat = 23.5841
        lon = 58.4078
        
        # Open-Meteo API endpoint
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": ["temperature_2m", "relative_humidity_2m", "pressure_msl", 
                       "wind_speed_10m", "weather_code"],
            "timezone": "auto"
        }
        
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            current = data['current']
            
            # Weather code to description mapping
            weather_descriptions = {
                0: 'Clear sky',
                1: 'Mainly clear',
                2: 'Partly cloudy',
                3: 'Overcast',
                45: 'Foggy',
                48: 'Depositing rime fog',
                51: 'Light drizzle',
                53: 'Moderate drizzle',
                55: 'Dense drizzle',
                61: 'Slight rain',
                63: 'Moderate rain',
                65: 'Heavy rain',
                71: 'Slight snow',
                73: 'Moderate snow',
                75: 'Heavy snow',
                77: 'Snow grains',
                80: 'Slight rain showers',
                81: 'Moderate rain showers',
                82: 'Violent rain showers',
                85: 'Slight snow showers',
                86: 'Heavy snow showers',
                95: 'Thunderstorm',
                96: 'Thunderstorm with slight hail',
                99: 'Thunderstorm with heavy hail'
            }
            
            # Weather code to icon mapping
            weather_icons = {
                0: '01d',  # Clear
                1: '02d',  # Mainly clear
                2: '03d',  # Partly cloudy
                3: '04d',  # Overcast
                45: '50d', # Fog
                48: '50d', # Fog
                51: '09d', # Drizzle
                53: '09d',
                55: '09d',
                61: '10d', # Rain
                63: '10d',
                65: '10d',
                71: '13d', # Snow
                73: '13d',
                75: '13d',
                77: '13d',
                80: '09d', # Showers
                81: '09d',
                82: '09d',
                85: '13d',
                86: '13d',
                95: '11d', # Thunderstorm
                96: '11d',
                99: '11d'
            }
            
            weather_code = current.get('weather_code', 0)
            
            return jsonify({
                'temp': round(current.get('temperature_2m', 0), 1),
                'description': weather_descriptions.get(weather_code, 'Unknown'),
                'wind_speed': round(current.get('wind_speed_10m', 0), 1),
                'humidity': round(current.get('relative_humidity_2m', 0)),
                'pressure': round(current.get('pressure_msl', 0)),
                'visibility': 10,  # Open-Meteo doesn't provide this, default to 10km
                'icon': weather_icons.get(weather_code, '01d'),
                'source': 'Open-Meteo (Free API)'
            })
        else:
            raise Exception(f'API returned status {response.status_code}')
            
    except Exception as e:
        print(f"❌ Weather fetch error: {e}")
        # Return mock data as fallback
        return jsonify({
            'temp': 28,
            'description': 'Clear sky',
            'wind_speed': 12,
            'humidity': 45,
            'pressure': 1013,
            'visibility': 10,
            'icon': '01d',
            'error': str(e),
            'source': 'Mock data (API unavailable)'
        })

@app.route('/api/alerts')
@app.route('/api/alerts/<int:limit>')
def get_alerts(limit=50):
    """Get recent alerts from database"""
    try:
        conn = sqlite3.connect('environmental_data.db')
        cursor = conn.cursor()

        cursor.execute('''
            SELECT timestamp, message, level
            FROM alerts
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))

        rows = cursor.fetchall()
        conn.close()

        data = []
        for row in rows:
            data.append({
                'timestamp': row[0],
                'message': row[1],
                'level': row[2]
            })

        return jsonify(data)

    except Exception as e:
        print(f"❌ Alerts fetch error: {e}")
        return jsonify({'error': str(e)})

@app.route('/api/db/stats')
def get_db_stats():
    """Get database statistics"""
    try:
        conn = sqlite3.connect('environmental_data.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM readings')
        total_readings = cursor.fetchone()[0]
        
        cursor.execute('SELECT MIN(timestamp), MAX(timestamp) FROM readings')
        time_range = cursor.fetchone()
        
        conn.close()
        
        return jsonify({
            'total_readings': total_readings,
            'oldest_reading': time_range[0],
            'newest_reading': time_range[1]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})

# ============================================
# STARTUP
# ============================================

print("=" * 60)
print("🌤️  OPEN-METEO WEATHER API - FREE & NO API KEY NEEDED!")
print("=" * 60)

init_database()
print("📊 Database ready!")
print("")
print("=" * 60)
print("🚀 Starting IoT Environmental Monitor...")
print("📊 Database: environmental_data.db")
print("🌐 Dashboard: http://localhost:5000")
print("🌤️  Weather: Open-Meteo API (Free)")
print("=" * 60)
print("")

arduino_thread = threading.Thread(target=read_arduino, daemon=True)
arduino_thread.start()

# ============================================
# RUN SERVER
# ============================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)