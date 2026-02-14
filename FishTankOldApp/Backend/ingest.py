# backend/ingest.py

from flask import Blueprint, jsonify
from models import db, Node, Reading
import os
import pandas as pd
from datetime import datetime

ingest_bp = Blueprint('ingest', __name__)

@ingest_bp.route('/run', methods=['POST'])
def ingest_csv_files():
    nodes = Node.query.all()
    processed_files = []

    for node in nodes:
        node_path = node.ip_address  # Or node.mapped_drive if available
        if not os.path.exists(node_path):
            continue  # Skip if path is unreachable

        for file in os.listdir(node_path):
            if not file.endswith('.csv'):
                continue

            file_path = os.path.join(node_path, file)
            try:
                df = pd.read_csv(file_path)
                for _, row in df.iterrows():
                    if {'sensor_id', 'timestamp', 'temperature', 'unit'}.issubset(row):
                        continue  # Malformed row

                    reading = Reading(
                        sensor_id=row['sensor_id'],
                        timestamp=datetime.fromisoformat(row['timestamp']),
                        temperature=row['temperature'],
                        unit=row.get('unit', '°C'),
                        valid=True
                    )
                    db.session.add(reading)

                db.session.commit()
                processed_files.append(file)
            except Exception as e:
                print(f"Failed to process {file_path}: {str(e)}")

    return jsonify({'message': 'Ingestion complete', 'processed_files': processed_files})
