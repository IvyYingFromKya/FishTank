# backend/sensors.py

from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify
from sqlalchemy.sql import func

from models import db, Sensor, Reading

sensors_bp = Blueprint('sensors', __name__)


def _serialize_sensor(sensor: Sensor) -> dict:
    return {
        'sensor_id': sensor.sensor_id,
        'node_id': sensor.node_id,
        'location_id': sensor.location_id,
        'sensor_type_id': sensor.sensor_type_id,
        'sensor_status_id': sensor.sensor_status_id,
        'sensor_device_id': sensor.sensor_device_id,
        'sensor_device_path': sensor.sensor_device_path,
        'sensor_brand': sensor.sensor_brand,
        'sensor_model': sensor.sensor_model,
        'sensor_specification': sensor.sensor_specification,
        'sensor_pin': sensor.sensor_pin,
        'sensor_description': sensor.sensor_description,
        'name': sensor.name,
        'registered_on': sensor.registered_on,
    }


@sensors_bp.route('/', methods=['GET'])
def get_all_sensors():
    sensors = Sensor.query.order_by(Sensor.sensor_id.asc()).all()
    return jsonify([_serialize_sensor(s) for s in sensors])


@sensors_bp.route('/<int:sensor_id>', methods=['GET'])
def get_sensor(sensor_id):
    sensor = Sensor.query.get_or_404(sensor_id)
    return jsonify(_serialize_sensor(sensor))


@sensors_bp.route('/', methods=['POST'])
def add_sensor():
    data = request.get_json(silent=True) or {}

    new_sensor = Sensor(
        node_id=data['node_id'],
        location_id=data['location_id'],
        sensor_type_id=data['sensor_type_id'],
        sensor_status_id=data.get('sensor_status_id'),
        sensor_device_id=data.get('sensor_device_id'),
        sensor_device_path=data.get('sensor_device_path'),
        sensor_brand=data.get('sensor_brand'),
        sensor_model=data.get('sensor_model'),
        sensor_specification=data.get('sensor_specification'),
        sensor_pin=data.get('sensor_pin'),
        sensor_description=data.get('sensor_description'),
        name=data.get('name'),
        registered_on=data.get('registered_on') or datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
    )
    db.session.add(new_sensor)
    db.session.commit()
    return jsonify({'message': 'Sensor added successfully', 'sensor_id': new_sensor.sensor_id}), 201


@sensors_bp.route('/<int:sensor_id>', methods=['PUT'])
def update_sensor(sensor_id):
    data = request.get_json(silent=True) or {}
    sensor = Sensor.query.get_or_404(sensor_id)

    sensor.node_id = data.get('node_id', sensor.node_id)
    sensor.location_id = data.get('location_id', sensor.location_id)
    sensor.sensor_type_id = data.get('sensor_type_id', sensor.sensor_type_id)
    sensor.sensor_status_id = data.get('sensor_status_id', sensor.sensor_status_id)
    sensor.sensor_device_id = data.get('sensor_device_id', sensor.sensor_device_id)
    sensor.sensor_device_path = data.get('sensor_device_path', sensor.sensor_device_path)
    sensor.sensor_brand = data.get('sensor_brand', sensor.sensor_brand)
    sensor.sensor_model = data.get('sensor_model', sensor.sensor_model)
    sensor.sensor_specification = data.get('sensor_specification', sensor.sensor_specification)
    sensor.sensor_pin = data.get('sensor_pin', sensor.sensor_pin)
    sensor.sensor_description = data.get('sensor_description', sensor.sensor_description)
    sensor.name = data.get('name', sensor.name)
    sensor.registered_on = data.get('registered_on', sensor.registered_on)

    db.session.commit()
    return jsonify({'message': 'Sensor updated successfully'})


@sensors_bp.route('/<int:sensor_id>', methods=['DELETE'])
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
        Sensor.location_id,
    ).join(Sensor, Sensor.sensor_id == Reading.sensor_id).join(
        latest, (Reading.sensor_id == latest.c.sensor_id) & (Reading.timestamp == latest.c.timestamp)
    ).all()

    return jsonify([{
        'sensor_id': r.sensor_id,
        'temperature': r.temperature,
        'unit': r.unit,
        'timestamp': r.timestamp,
        'name': r.name,
        'location_id': r.location_id,
    } for r in results])


@sensors_bp.route('/api/sensor-data')
def get_sensor_data():
    range_str = (request.args.get('range') or '24H').upper()

    now = datetime.utcnow()
    if range_str == '7D':
        start_time = now - timedelta(days=7)
    elif range_str == '1M':
        start_time = now - timedelta(days=30)
    else:
        start_time = now - timedelta(hours=24)

    start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')

    readings = (
        db.session.query(Sensor.sensor_id, Sensor.name, Reading.timestamp, Reading.temperature)
        .join(Reading, Sensor.sensor_id == Reading.sensor_id)
        .filter(Reading.timestamp >= start_time_str)
        .order_by(Reading.timestamp.asc())
        .all()
    )

    result = {}
    for sid, name, ts, value in readings:
        if sid not in result:
            result[sid] = {'name': name or f'Sensor {sid}', 'data': [], 'timestamps': []}
        ts_dt = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S') if isinstance(ts, str) else ts
        result[sid]['data'].append(value)
        result[sid]['timestamps'].append(ts_dt.strftime('%H:%M' if range_str == '24H' else '%m-%d'))

    sensor_data = list(result.values())
    return jsonify({
        'labels': sensor_data[0]['timestamps'] if sensor_data else [],
        'datasets': [
            {
                'label': s['name'],
                'data': s['data'],
                'borderColor': f"#{hex(1000000 + i * 123456)[2:8]}",
                'backgroundColor': 'transparent',
                'tension': 0.3,
            }
            for i, s in enumerate(sensor_data)
        ],
    })
