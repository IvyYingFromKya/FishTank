import sqlite3
import os
import time
from datetime import datetime

MAPPED_DRIVE_PATH = "S:\\"  # Replace with actual mapped drive path
DB_PATH = "Fishtank.db"
CONFIG_PATH = "system_config.txt"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS readings (
            reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id TEXT,
            timestamp DATETIME,
            temperature REAL,
            unit TEXT DEFAULT '°C',
            valid BOOLEAN,
            UNIQUE(sensor_id, timestamp)
        );
    ''')
    conn.commit()
    conn.close()

def wait_for_file_access(filepath, timeout=30):
    start_time = time.time()
    while True:
        try:
            with open(filepath, 'r'):
                return True
        except IOError:
            if time.time() - start_time > timeout:
                print(f"Timeout waiting for file: {filepath}")
                return False
            time.sleep(1)

def parse_data_file(filepath, sensor_id):
    readings = []
    if not wait_for_file_access(filepath):
        return readings
    try:
        with open(filepath, 'r') as file:
            lines = file.readlines()
        for line in lines:
            try:
                timestamp_str, temp_str, _ = line.strip().split(',')
                timestamp = datetime.fromisoformat(timestamp_str)
                temperature = float(temp_str)
                readings.append((sensor_id, timestamp, temperature, '°C', True))
            except Exception as e:
                print(f"Failed to parse line: {line}. Error: {e}")
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
    return readings

def harvest_data():
    new_entries = 0
    for sensor_id in os.listdir(MAPPED_DRIVE_PATH):
        sensor_path = os.path.join(MAPPED_DRIVE_PATH, sensor_id)
        if not os.path.isdir(sensor_path):
            continue
        for year in os.listdir(sensor_path):
            for month in os.listdir(os.path.join(sensor_path, year)):
                for day in os.listdir(os.path.join(sensor_path, year, month)):
                    data_dir = os.path.join(sensor_path, year, month, day)
                    if not os.path.isdir(data_dir):
                        continue
                    for file in os.listdir(data_dir):
                        if file.endswith(".data"):
                            filepath = os.path.join(data_dir, file)
                            readings = parse_data_file(filepath, sensor_id)
                            if readings:
                                try:
                                    conn = sqlite3.connect(DB_PATH)
                                    cur = conn.cursor()
                                    for reading in readings:
                                        try:
                                            cur.execute('''
                                                INSERT OR IGNORE INTO readings (sensor_id, timestamp, temperature, unit, valid)
                                                VALUES (?, ?, ?, ?, ?)
                                            ''', reading)
                                            new_entries += cur.rowcount
                                        except Exception as e:
                                            print(f"DB insert failed for {reading}: {e}")
                                    conn.commit()
                                    conn.close()
                                except Exception as db_err:
                                    print(f"Database error: {db_err}")
    print(f"{new_entries} new readings added.")

def read_config():
    try:
        with open(CONFIG_PATH, 'r') as f:
            for line in f:
                if line.startswith("INTERVAL_SECONDS"):
                    return int(line.strip().split('=')[1])
    except Exception as e:
        print(f"Failed to read config: {e}")
    return 60

def main():
    init_db()
    interval = read_config()
    while True:
        harvest_data()
        print(f"Sleeping for {interval} seconds...")
        time.sleep(interval)

# Uncomment to run the script
if __name__ == "__main__":
    main()

