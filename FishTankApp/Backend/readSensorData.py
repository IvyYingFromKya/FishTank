import csv
import os
import sqlite3
import tempfile
import time
from contextlib import closing

# === Configuration ===
MAPPED_DRIVE_ROOT = "S:\\"  # Update this if you're using different drives
DATABASE_PATH = ".\\instance\\sensor_data.db"
READ_INTERVAL_SECONDS = 5  # seconds

# Shared-folder lock mitigation
COPY_RETRIES = 5
COPY_RETRY_DELAY_SECONDS = 0.5
FILE_STABLE_SECONDS = 2  # skip files modified very recently (likely still being written)


def _is_stable_file(file_path: str) -> bool:
    """Avoid reading files that are still being actively written."""
    try:
        return (time.time() - os.path.getmtime(file_path)) >= FILE_STABLE_SECONDS
    except OSError:
        return False


def _copy_to_temp_with_retry(file_path: str) -> str | None:
    """Create a local temp snapshot of the network file with retry for transient locks."""
    suffix = os.path.splitext(file_path)[1] or ".csv"

    for attempt in range(1, COPY_RETRIES + 1):
        try:
            fd, temp_path = tempfile.mkstemp(suffix=suffix)
            os.close(fd)

            # binary copy to avoid newline/encoding surprises while snapshotting
            with open(file_path, "rb") as src, open(temp_path, "wb") as dst:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    dst.write(chunk)

            return temp_path
        except (PermissionError, OSError) as exc:
            print(f"[WARN] File lock/access issue ({attempt}/{COPY_RETRIES}) for {file_path}: {exc}")
            if 'temp_path' in locals() and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            time.sleep(COPY_RETRY_DELAY_SECONDS)

    print(f"[WARN] Skipping locked file after retries: {file_path}")
    return None


def _iter_data_files(root_path: str):
    """
    Yield candidate data files recursively.

    Supports:
    - New format: year/month/day/hour.csv
    - Legacy format: .data files
    """
    for dirpath, _, filenames in os.walk(root_path):
        for filename in filenames:
            lower = filename.lower()
            if lower.endswith('.csv') or lower.endswith('.data'):
                yield os.path.join(dirpath, filename)


def _parse_reading_line(parts: list[str], fallback_sensor_id: str | None = None):
    """
    Accept both formats:
    1) legacy: timestamp,temperature
    2) current: sensor_id,timestamp,sensor_type,sensor_reading
    """
    parts = [p.strip() for p in parts]

    # Current format
    if len(parts) >= 4:
        sensor_id = parts[0]
        timestamp = parts[1]
        sensor_type = parts[2].lower()
        reading = float(parts[3])

        if sensor_type not in ("temperature", "temp"):
            return None  # Ignore non-temperature rows for current DB schema

        return sensor_id, timestamp, reading

    # Legacy format
    if len(parts) >= 2 and fallback_sensor_id:
        timestamp = parts[0]
        reading = float(parts[1])
        return fallback_sensor_id, timestamp, reading

    return None


def read_sensor_data_and_store():
    with closing(sqlite3.connect(DATABASE_PATH, timeout=30)) as conn:
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA journal_mode = WAL")
        cursor = conn.cursor()

        insert_count = 0
        print(f"\n🔍 Scanning root directory: {MAPPED_DRIVE_ROOT}\n")

        if not os.path.isdir(MAPPED_DRIVE_ROOT):
            print(f"[WARN] Shared path not reachable: {MAPPED_DRIVE_ROOT}")
            return

        for file_path in _iter_data_files(MAPPED_DRIVE_ROOT):
            if not _is_stable_file(file_path):
                print(f"[INFO] Skipping in-progress file: {file_path}")
                continue

            print(f"📄 Processing: {file_path}")
            temp_path = _copy_to_temp_with_retry(file_path)
            if not temp_path:
                continue

            # Best-effort fallback for legacy folder layout where top dir was sensor_id
            rel_parts = os.path.normpath(file_path).split(os.sep)
            fallback_sensor_id = rel_parts[-5] if len(rel_parts) >= 5 else None

            try:
                with open(temp_path, "r", newline="") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if not row:
                            continue

                        try:
                            parsed = _parse_reading_line(row, fallback_sensor_id=fallback_sensor_id)
                            if not parsed:
                                continue

                            sensor_id, timestamp, temperature = parsed

                            cursor.execute(
                                """
                                SELECT 1 FROM readings
                                WHERE sensor_id = ? AND timestamp = ?
                                """,
                                (sensor_id, timestamp),
                            )

                            if cursor.fetchone():
                                continue

                            cursor.execute(
                                """
                                INSERT INTO readings (sensor_id, timestamp, temperature, unit, valid)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (sensor_id, timestamp, temperature, '°C', 1),
                            )
                            insert_count += 1
                        except (ValueError, sqlite3.Error) as exc:
                            print(f"[WARN] Skipped row {row}: {exc}")
            except Exception as exc:
                print(f"[ERROR] Failed to process {file_path}: {exc}")
            finally:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

        conn.commit()
        print(f"\n✅ {insert_count} new record(s) written to database.\n")


def main_loop():
    while True:
        print("🔁 Starting sync cycle...")
        read_sensor_data_and_store()
        print(f"⏳ Waiting {READ_INTERVAL_SECONDS} seconds before next sync...\n")
        time.sleep(READ_INTERVAL_SECONDS)


if __name__ == "__main__":
    main_loop()
