import sqlite3
from datetime import datetime, timedelta
import random

# Connect to the SQLite database
conn = sqlite3.connect("instance/sensor_data.db")
cur = conn.cursor()

# Sample node
node_id = "pi-lab-a"
cur.execute("""
INSERT OR IGNORE INTO nodes (node_id, hostname, ip_address, location, description, status, registered_on)
VALUES (?, ?, ?, ?, ?, ?, ?)
""", (
    node_id,
    "raspberrypi1",
    "192.168.137.101",
    "Aquarium Room",
    "Main temperature node for tank monitoring",
    "active",
    datetime.utcnow().isoformat()
))

# Sample sensors
sensor_data = [
    ("28-00000abcde1", node_id, "Tank A", "Tank Left", "Monitors left tank temperature", 2, "active", datetime.utcnow().isoformat()),
    ("28-00000abcde2", node_id, "Tank B", "Tank Right", "Monitors right tank temperature", 2, "active", datetime.utcnow().isoformat())
]

cur.executemany("""
INSERT OR IGNORE INTO sensors (sensor_id, node_id, name, location, description, sampling_rate, status, last_calibrated)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", sensor_data)

# Generate readings for each sensor (past 1 hour, every 5 minutes)
now = datetime.utcnow()
reading_entries = []
for sensor_id, *_ in sensor_data:
    for i in range(12):  # 12 readings per hour
        timestamp = now - timedelta(minutes=i*5)
        temperature = round(22.0 + random.uniform(-1.0, 1.0), 2)
        reading_entries.append((sensor_id, timestamp.isoformat(), temperature, "°C", 1))

cur.executemany("""
INSERT INTO readings (sensor_id, timestamp, temperature, unit, valid)
VALUES (?, ?, ?, ?, ?)
""", reading_entries)

# Sample sensor status updates
status_entries = [
    ("28-00000abcde1", datetime.utcnow().isoformat(), "OK", "Sensor operating normally"),
    ("28-00000abcde2", datetime.utcnow().isoformat(), "OK", "Sensor operating normally")
]

cur.executemany("""
INSERT INTO sensor_status (sensor_id, timestamp, status_code, message)
VALUES (?, ?, ?, ?)
""", status_entries)

# Sample logs
log_entries = [
    (node_id, datetime.utcnow().isoformat(), "INFO", "Node started"),
    (node_id, datetime.utcnow().isoformat(), "INFO", "Initial sensor sync complete"),
    (None, datetime.utcnow().isoformat(), "WARN", "Minor delay in data collection")
]

cur.executemany("""
INSERT INTO logs (node_id, timestamp, level, message)
VALUES (?, ?, ?, ?)
""", log_entries)

# Commit and close
conn.commit()
conn.close()

"✅ Sample data inserted into all tables in 'sensor_system.db' for dashboard testing."
