# backend/sensors.py

from flask import Blueprint, request, jsonify
from models import db, Sensor, Reading
from datetime import datetime, timedelta
from sqlalchemy.sql import func

sensors_bp = Blueprint('sensors', __name__)

@sensors_bp.route('/', methods=['GET'])
def get_all_sensors():
    sensors = Sensor.query.all()
    return jsonify([{
        'sensor_id': s.sensor_id,
        'node_id': s.node_id,
        'name': s.name,
        'location': s.location,
        'description': s.description,
        'sampling_rate': s.sampling_rate,
        'status': s.status,
        'last_calibrated': s.last_calibrated.isoformat() if s.last_calibrated else None
    } for s in sensors])

@sensors_bp.route('/<sensor_id>', methods=['GET'])
def get_sensor(sensor_id):
    sensor = Sensor.query.get_or_404(sensor_id)
    return jsonify({
        'sensor_id': sensor.sensor_id,
        'node_id': sensor.node_id,
        'name': sensor.name,
        'location': sensor.location,
        'description': sensor.description,
        'sampling_rate': sensor.sampling_rate,
        'status': sensor.status,
        'last_calibrated': sensor.last_calibrated.isoformat() if sensor.last_calibrated else None
    })

@sensors_bp.route('/', methods=['POST'])
def add_sensor():
    data = request.json
    new_sensor = Sensor(
        sensor_id=data['sensor_id'],
        node_id=data['node_id'],
        name=data['name'],
        location=data['location'],
        description=data.get('description', ''),
        sampling_rate=data['sampling_rate'],
        status=data.get('status', 'active'),
        last_calibrated=datetime.fromisoformat(data['last_calibrated']) if data.get('last_calibrated') else None
    )
    db.session.add(new_sensor)
    db.session.commit()
    return jsonify({'message': 'Sensor added successfully'}), 201

@sensors_bp.route('/<sensor_id>', methods=['PUT'])
def update_sensor(sensor_id):
    data = request.json
    sensor = Sensor.query.get_or_404(sensor_id)
    sensor.node_id = data.get('node_id', sensor.node_id)
    sensor.name = data.get('name', sensor.name)
    sensor.location = data.get('location', sensor.location)
    sensor.description = data.get('description', sensor.description)
    sensor.sampling_rate = data.get('sampling_rate', sensor.sampling_rate)
    sensor.status = data.get('status', sensor.status)
    if data.get('last_calibrated'):
        sensor.last_calibrated = datetime.fromisoformat(data['last_calibrated'])
    db.session.commit()
    return jsonify({'message': 'Sensor updated successfully'})

@sensors_bp.route('/<sensor_id>', methods=['DELETE'])
def delete_sensor(sensor_id):
    sensor = Sensor.query.get_or_404(sensor_id)
    db.session.delete(sensor)
    db.session.commit()
    return jsonify({'message': 'Sensor deleted successfully'})

@sensors_bp.route('/latest', methods=['GET'])
def latest_sensor_readings():
    latest = db.session.query(
        Reading.sensor_id,
        func.max(Reading.timestamp).label('timestamp')
    ).group_by(Reading.sensor_id).subquery()

    results = db.session.query(
        Reading.sensor_id,
        Reading.temperature,
        Reading.unit,
        Reading.timestamp,
        Sensor.name,
        Sensor.location
    ).join(Sensor, Sensor.sensor_id == Reading.sensor_id).join(
        latest, (Reading.sensor_id == latest.c.sensor_id) & (Reading.timestamp == latest.c.timestamp)
    ).all()

    return jsonify([{
        'sensor_id': r.sensor_id,
        'temperature': r.temperature,
        'unit': r.unit,
        'timestamp': r.timestamp.isoformat(),
        'name': r.name,
        'location': r.location
    } for r in results])

@sensors_bp.route('/api/sensor-data')
def get_sensor_data():
    sensor_type = request.args.get('type', 'temperature')
    range_str = request.args.get('range', '24H')

    now = datetime.utcnow()
    if range_str == '7D':
        start_time = now - timedelta(days=7)
    elif range_str == '1M':
        start_time = now - timedelta(days=30)
    else:
        start_time = now - timedelta(hours=24)

    readings = (
        db.session.query(Sensor.name, Sensor.sensor_type, Sensor.id, SensorReading.timestamp, SensorReading.value)
        .join(SensorReading, Sensor.id == SensorReading.sensor_id)
        .filter(Sensor.sensor_type == sensor_type)
        .filter(SensorReading.timestamp >= start_time)
        .order_by(SensorReading.timestamp.asc())
        .all()
    )

    # Group by sensor
    result = {}
    for name, sensor_type, sid, ts, val in readings:
        if sid not in result:
            result[sid] = {"name": name or f"Sensor {sid}", "data": [], "timestamps": []}
        result[sid]["data"].append(val)
        result[sid]["timestamps"].append(ts.strftime("%H:%M" if range_str == "24H" else "%m-%d"))

    # Package into Chart.js format
    sensor_data = list(result.values())
    return jsonify({
        "labels": sensor_data[0]["timestamps"] if sensor_data else [],
        "datasets": [
            {
                "label": s["name"],
                "data": s["data"],
                "borderColor": f"#{hex(1000000 + i * 123456)[2:8]}",
                "backgroundColor": "transparent",
                "tension": 0.3
            }
            for i, s in enumerate(sensor_data)
        ]
    })
