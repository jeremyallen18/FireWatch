"""
FireWatch - Rutas de monitoreo
"""

from flask import Blueprint, jsonify, request

from services import container
from services import monitoring_service

monitoring_bp = Blueprint('monitoring', __name__)


@monitoring_bp.route('/api/start_monitoring', methods=['POST'])
def start_monitoring():
    source = (request.json or {}).get('source')
    result = monitoring_service.start(source)
    return jsonify(result)


@monitoring_bp.route('/api/stop_monitoring', methods=['POST'])
def stop_monitoring():
    result = monitoring_service.stop()
    return jsonify(result)


@monitoring_bp.route('/api/test_esp32', methods=['POST'])
def test_esp32():
    return jsonify(container.esp32.test_connection())


@monitoring_bp.route('/api/reset_alert', methods=['POST'])
def reset_alert():
    container.system_state.reset_alert()
    container.esp32.deactivate()
    from extensions import socketio
    socketio.emit('alert_reset', {})
    return jsonify({'success': True, 'message': 'Alerta reiniciada'})


@monitoring_bp.route('/api/system_state')
def get_system_state():
    return jsonify(container.system_state.snapshot())
