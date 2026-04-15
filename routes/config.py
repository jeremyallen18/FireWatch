"""
FireWatch - Rutas de configuracion
"""

from flask import Blueprint, jsonify, request

from services import container
from services.config_service import get_all_public_settings, save_section_config, save_settings

config_bp = Blueprint('config', __name__)


@config_bp.route('/api/config')
def api_get_config():
    return jsonify(get_all_public_settings())


@config_bp.route('/api/config/<path:section>', methods=['POST'])
def api_save_config(section):
    data = request.json or {}
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
