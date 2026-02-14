# backend/config.py

from flask import Blueprint, request, jsonify
from models import db, Setting

config_bp = Blueprint('config', __name__)

@config_bp.route('/', methods=['GET'])
def get_all_settings():
    settings = Setting.query.all()
    return jsonify([{'key': s.key, 'value': s.value} for s in settings])

@config_bp.route('/', methods=['POST'])
def create_or_update_setting():
    data = request.json
    setting = Setting.query.filter_by(key=data['key']).first()
    if setting:
        setting.value = data['value']
    else:
        setting = Setting(key=data['key'], value=data['value'])
        db.session.add(setting)
    db.session.commit()
    return jsonify({'message': 'Setting saved'})

@config_bp.route('/<key>', methods=['DELETE'])
def delete_setting(key):
    setting = Setting.query.filter_by(key=key).first_or_404()
    db.session.delete(setting)
    db.session.commit()
    return jsonify({'message': 'Setting deleted'})
