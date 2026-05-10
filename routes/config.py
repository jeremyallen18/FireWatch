"""
FireWatch - Rutas de configuracion
"""

from flask import Blueprint, jsonify, request

from services import container
from services import powerbi_service
from services.config_service import get_all_public_settings, save_section_config, save_settings

config_bp = Blueprint('config', __name__)


@config_bp.route('/api/config')
def api_get_config():
    return jsonify(get_all_public_settings())


@config_bp.route('/api/config/<path:section>', methods=['POST'])
def api_save_config(section):
    data = request.json or {}

    if section == 'powerbi':
        return api_save_powerbi()

    result = save_section_config(section, data)
    status = 200 if result['success'] else 400
    return jsonify(result), status


@config_bp.route('/api/test-db')
def api_test_db():
    return jsonify(container.db_manager.test_connection())


@config_bp.route('/api/test-esp32')
def api_test_esp32():
    return jsonify(container.esp32.test_connection())


@config_bp.route('/api/test-email')
def api_test_email():
    return jsonify(container.notifier.send_test_email())


@config_bp.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify(get_all_public_settings())


@config_bp.route('/api/settings', methods=['POST'])
def post_settings():
    data = request.json
    result = save_settings(data)
    return jsonify(result)


@config_bp.route('/api/test_email', methods=['POST'])
def test_email():
    return jsonify(container.notifier.send_test_email())


@config_bp.route('/api/test_db', methods=['POST'])
def test_db():
    return jsonify(container.db_manager.test_connection())


@config_bp.route('/api/test-powerbi', methods=['POST'])
def api_test_powerbi():
    """Envia un dato de prueba al streaming dataset de Power BI."""
    return jsonify(powerbi_service.test_connection())


def api_save_powerbi():
    """Guarda la configuracion de Power BI."""
    data = request.json or {}
    push_url = (data.get('powerbi_push_url') or '').strip()
    enabled = bool(data.get('powerbi_enabled', False))

    if enabled and not push_url:
        return jsonify({'success': False, 'message': 'La URL de Power BI es requerida'}), 400

    if push_url and len(push_url) > 2048:
        return jsonify({'success': False, 'message': 'La URL no puede exceder 2048 caracteres'}), 400

    container.db_manager.save_setting('powerbi_push_url', push_url)
    container.db_manager.save_setting('powerbi_enabled', str(enabled).lower())
    powerbi_service.reload_config()

    return jsonify({'success': True, 'message': 'Configuracion de Power BI guardada'})
