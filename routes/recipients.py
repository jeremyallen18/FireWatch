"""
FireWatch - Rutas de gestion de destinatarios
"""

from flask import Blueprint, jsonify, request

from services import container
from core.responses import error_response

recipients_bp = Blueprint('recipients', __name__)


@recipients_bp.route('/api/recipients', methods=['GET'])
def get_recipients():
    recipients = container.db_manager.get_recipients(active_only=False)
    return jsonify({'success': True, 'recipients': recipients})


@recipients_bp.route('/api/recipients', methods=['POST'])
def add_recipient():
    data = request.json or {}
    email = data.get('email', '').strip()
    name = data.get('name', '').strip()

    if not email:
        return error_response('Email es requerido')

    result = container.db_manager.add_recipient(email, name)
    return jsonify(result), (200 if result['success'] else 400)


@recipients_bp.route('/api/recipients/<int:recipient_id>', methods=['PUT'])
def update_recipient(recipient_id):
    data = request.json or {}
    email = data.get('email', '').strip() if data.get('email') is not None else None
    name = data.get('name', '').strip() if data.get('name') is not None else None

    result = container.db_manager.update_recipient(recipient_id, email, name)
    return jsonify(result), (200 if result['success'] else 400)


@recipients_bp.route('/api/recipients/<int:recipient_id>', methods=['DELETE'])
def delete_recipient(recipient_id):
    result = container.db_manager.delete_recipient(recipient_id)
    return jsonify(result), (200 if result['success'] else 400)


@recipients_bp.route('/api/recipients/<int:recipient_id>/toggle', methods=['POST'])
def toggle_recipient_active(recipient_id):
    data = request.json or {}
    is_active = data.get('is_active', True)

    result = container.db_manager.toggle_recipient_active(recipient_id, is_active)
    return jsonify(result), (200 if result['success'] else 400)
