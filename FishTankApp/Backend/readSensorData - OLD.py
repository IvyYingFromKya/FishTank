import os
import sqlite3
import shutil
import tempfile
import time

# === Configuration ===
MAPPED_DRIVE_ROOT = "S:\\"
DATABASE_PATH = ".\\instance\\sensor_data.db"
READ_INTERVAL_SECONDS = 5  # seconds

def read_sensor_data_and_store():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    insert_count = 0

    print(f"\n🔍 Scanning root directory: {MAPPED_DRIVE_ROOT}\n")

    for sensor_id in os.listdir(MAPPED_DRIVE_ROOT):
        sensor_path = os.path.join(MAPPED_DRIVE_ROOT, sensor_id)
        print(f"📁 Sensor ID: {sensor_id} → {sensor_path}")
        if not os.path.isdir(sensor_path):
            continue

        for year in os.listdir(sensor_path):
            year_path = os.path.join(sensor_path, year)
            print(f"  📅 Year: {year} → {year_path}")
            if not os.path.isdir(year_path):
                continue

            for month in os.listdir(year_path):
                month_path = os.path.join(year_path, month)
                if not os.path.isdir(month_path):
                    continue

                for day in os.listdir(month_path):
                    day_path = os.path.join(month_path, day)
                    if not os.path.isdir(day_path):
                        continue

                    for filename in os.listdir(day_path):
                        if filename.endswith(".data"):
                            file_path = os.path.join(day_path, filename)
                            print(f"📄 Reading original file: {file_path}")

                            # Create a new temp file for each attempt
                            try:
                                fd, temp_path = tempfile.mkstemp(suffix=".data")
                                os.close(fd)  # Close immediately
                                shutil.copyfile(file_path, temp_path)
                                print(f"🗂️  Temporary copy created at: {temp_path}")
                            except Exception as e:
                                print(f"[ERROR] Failed to copy to temp file: {e}")
                                continue

                            # Read from the new temp file
                            try:
                                with open(temp_path, "r") as f:
                                    for line in f:
                                        line = line.strip()
                                        if not line:
                                            continue

                                        print(f"🧾 Line read: {line}")

                                        try:
                                            parts = line.split(",")
                                            if len(parts) < 2:
                                                raise ValueError("Not enough values")

                                            timestamp = parts[0]
                                            temp = float(parts[1])  # Ignore Fahrenheit (3rd column)

                                            # Check for duplicate
                                            cursor.execute("""
                                                SELECT 1 FROM readings
                                                WHERE sensor_id = ? AND timestamp = ?
                                            """, (sensor_id, timestamp))

                                            if not cursor.fetchone():
                                                cursor.execute("""
                                                    INSERT INTO readings (sensor_id, timestamp, temperature, unit, valid)
                                                    VALUES (?, ?, ?, '°C', 1)
                                                """, (sensor_id, timestamp, temp))
                                                insert_count += 1
                                                print(f"✅ INSERTED: [{sensor_id}] {timestamp} → {temp}°C")
                                            else:
                                                print(f"⏭️ SKIPPED (Duplicate): [{sensor_id}] {timestamp}")
                                        except ValueError:
                                            print(f"[WARN] Malformed line skipped: {line}")
                            except Exception as e:
                                print(f"[ERROR] Failed to read temp file: {e}")
                            finally:
                                try:
                                    os.remove(temp_path)
                                    print(f"🧹 Deleted temp file: {temp_path}")
                                except Exception:
                                    print(f"[WARN] Failed to delete temp file {temp_path}")

    conn.commit()
    conn.close()
    print(f"\n✅ {insert_count} new record(s) written to database.\n")

def main_loop():
    while True:
        print("🔁 Starting sync cycle...")
        read_sensor_data_and_store()
        print(f"⏳ Waiting {READ_INTERVAL_SECONDS} seconds before next sync...\n")
        time.sleep(READ_INTERVAL_SECONDS)

if __name__ == "__main__":
    main_loop()
