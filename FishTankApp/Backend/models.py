# backend/models.py

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime



db = SQLAlchemy()

class Location(db.Model):
    __tablename__ = 'locations'
    location_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    address_1 = db.Column(db.String)
    address_2 = db.Column(db.String)
    notes = db.Column(db.String)
    content = db.Column(db.String)
    description = db.Column(db.String)
    nodes = db.relationship("Node", back_populates="location")
    
class NodeStatus(db.Model):
    __tablename__ = 'node_status'
    node_status_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String, nullable=False)
    description = db.Column(db.String)
    nodes = db.relationship("Node", back_populates="status")

class Node(db.Model):
    __tablename__ = 'nodes'
    node_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    node_name = db.Column(db.String)
    hostname = db.Column(db.String, nullable=False)
    ip_address = db.Column(db.String, nullable=False)
    node_os = db.Column(db.String)
    node_firmware_version = db.Column(db.String)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.location_id'), nullable=False)
    node_status_id = db.Column(db.Integer, db.ForeignKey('node_status.node_status_id'), nullable=False)
    shared_folder_path = db.Column(db.String)
    shared_folder_alias = db.Column(db.String)
    local_drive_name = db.Column(db.String)
    local_drive_path = db.Column(db.String)
    description = db.Column(db.String)
    registered_on = db.Column(db.DateTime, default=datetime.utcnow)
    
    
    
    location = db.relationship("Location", back_populates="nodes")
    status = db.relationship("NodeStatus", back_populates="nodes")

class SensorType(db.Model):
    __tablename__ = 'sensor_type'
    sensor_type_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sensor_type = db.Column(db.String, nullable=False)
    sensor_type_description = db.Column(db.String)

class SensorStatus(db.Model):
    __tablename__ = 'sensor_status'
    status_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sensor_id = db.Column(db.Integer, db.ForeignKey('sensors.sensor_id'))
    timestamp = db.Column(db.String, nullable=False)
    status_code = db.Column(db.String)
    message = db.Column(db.String)

class Sensor(db.Model):
    __tablename__ = 'sensors'
    sensor_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    node_id = db.Column(db.Integer, db.ForeignKey('nodes.node_id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.location_id'), nullable=False)
    sensor_type_id = db.Column(db.Integer, db.ForeignKey('sensor_type.sensor_type_id'), nullable=False)
    sensor_status_id = db.Column(db.Integer, db.ForeignKey('sensor_status.status_id'))
    sensor_device_id = db.Column(db.String)
    sensor_device_path = db.Column(db.String)
    sensor_brand = db.Column(db.String)
    sensor_model = db.Column(db.String)
    sensor_specification = db.Column(db.String)
    sensor_pin = db.Column(db.String)
    sensor_description = db.Column(db.String)
    name = db.Column(db.String)
    registered_on = db.Column(db.String)

class Log(db.Model):
    __tablename__ = 'logs'
    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    node_id = db.Column(db.Integer, db.ForeignKey('nodes.node_id'), nullable=False)
    timestamp = db.Column(db.String, nullable=False)
    level = db.Column(db.String)
    message = db.Column(db.String)

class Reading(db.Model):
    __tablename__ = 'readings'
    reading_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sensor_id = db.Column(db.Integer, db.ForeignKey('sensors.sensor_id'), nullable=False)
    timestamp = db.Column(db.String, nullable=False)
    temperature = db.Column(db.Float)
    unit = db.Column(db.String)
    valid = db.Column(db.Boolean)

class Setting(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String, unique=True, nullable=False)
    value = db.Column(db.String)

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def is_authenticated(self):
        return True
    def is_active(self):
        return True
    def is_anonymous(self):
        return False
    def get_id(self):
        return str(self.id)
