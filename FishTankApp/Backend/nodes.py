# backend/nodes.py

from flask import Blueprint, request, jsonify
from models import db, Node
from datetime import datetime

nodes_bp = Blueprint('nodes', __name__)

@nodes_bp.route('/', methods=['GET'])
def get_all_nodes():
    nodes = Node.query.all()
    return jsonify([{
        'node_id': n.node_id,
        'node_name': n.node_name,
        'hostname': n.hostname,
        'ip_address': n.ip_address,
        'node_os': n.node_os,
        'node_firmware_version': n.node_firmware_version,
        'location_id': n.location_id,
        'node_status_id': n.node_status_id,
        'shared_folder_path': n.shared_folder_path,
        'shared_folder_alias': n.shared_folder_alias,
        'local_drive_name': n.local_drive_name,
        'local_drive_path': n.local_drive_path,
        'description': n.description,
        'registered_on': n.registered_on
    } for n in nodes])

@nodes_bp.route('/<int:node_id>', methods=['GET'])
def get_node(node_id):
    node = Node.query.get_or_404(node_id)
    return jsonify({
        'node_id': node.node_id,
        'node_name': node.node_name,
        'hostname': node.hostname,
        'ip_address': node.ip_address,
        'node_os': node.node_os,
        'node_firmware_version': node.node_firmware_version,
        'location_id': node.location_id,
        'node_status_id': node.node_status_id,
        'shared_folder_path': node.shared_folder_path,
        'shared_folder_alias': node.shared_folder_alias,
        'local_drive_name': node.local_drive_name,
        'local_drive_path': node.local_drive_path,
        'description': node.description,
        'registered_on': node.registered_on
    })

@nodes_bp.route('/', methods=['POST'])
def add_node():
    data = request.json
    new_node = Node(
        node_name=data.get('node_name'),
        hostname=data['hostname'],
        ip_address=data['ip_address'],
        node_os=data.get('node_os'),
        node_firmware_version=data.get('node_firmware_version'),
        location_id=data['location_id'],
        node_status_id=data['node_status_id'],
        shared_folder_path=data.get('shared_folder_path'),
        shared_folder_alias=data.get('shared_folder_alias'),
        local_drive_name=data.get('local_drive_name'),
        local_drive_path=data.get('local_drive_path'),
        description=data.get('description', ''),
        registered_on=data.get('registered_on', datetime.utcnow().isoformat())
    )
    db.session.add(new_node)
    db.session.commit()
    return jsonify({'message': 'Node added successfully'}), 201

@nodes_bp.route('/<int:node_id>', methods=['PUT'])
def update_node(node_id):
    data = request.json
    node = Node.query.get_or_404(node_id)

    node.node_name = data.get('node_name', node.node_name)
    node.hostname = data.get('hostname', node.hostname)
    node.ip_address = data.get('ip_address', node.ip_address)
    node.node_os = data.get('node_os', node.node_os)
    node.node_firmware_version = data.get('node_firmware_version', node.node_firmware_version)
    node.location_id = data.get('location_id', node.location_id)
    node.node_status_id = data.get('node_status_id', node.node_status_id)
    node.shared_folder_path = data.get('shared_folder_path', node.shared_folder_path)
    node.shared_folder_alias = data.get('shared_folder_alias', node.shared_folder_alias)
    node.local_drive_name = data.get('local_drive_name', node.local_drive_name)
    node.local_drive_path = data.get('local_drive_path', node.local_drive_path)
    node.description = data.get('description', node.description)
    node.registered_on = data.get('registered_on', node.registered_on)

    db.session.commit()
    return jsonify({'message': 'Node updated successfully'})

@nodes_bp.route('/<int:node_id>', methods=['DELETE'])
def delete_node(node_id):
    node = Node.query.get_or_404(node_id)
    db.session.delete(node)
    db.session.commit()
    return jsonify({'message': 'Node deleted successfully'})
