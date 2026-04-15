"""
FireWatch - Rutas principales (paginas y archivos estaticos)
"""

import os
from flask import Blueprint, render_template, jsonify, send_file, current_app

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return render_template('dashboard.html')


@main_bp.route('/historial')
def historial():
    return render_template('history.html')


@main_bp.route('/estadisticas')
def estadisticas():
    return render_template('statistics.html')


@main_bp.route('/configuracion')
def configuracion():
    return render_template('settings.html')


@main_bp.route('/video_feed')
def video_feed():
    placeholder = os.path.join(current_app.static_folder, 'images', 'no-signal.svg')
    return send_file(placeholder, mimetype='image/svg+xml')


@main_bp.route('/screenshots/<path:filename>')
def screenshot_file(filename):
    # root_path apunta al directorio donde esta app.py (raiz del proyecto)
    screenshots_dir = os.path.join(current_app.root_path, 'screenshots')

    if filename.startswith('screenshots/'):
        filename = filename[len('screenshots/'):]

    safe_path = os.path.realpath(os.path.join(screenshots_dir, filename))
    if not safe_path.startswith(os.path.realpath(screenshots_dir)):
        return jsonify({'error': 'Acceso denegado'}), 403
    return send_file(safe_path)
