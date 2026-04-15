"""
FireWatch - Sistema de Deteccion de Incendios
Application Factory
"""

import os

from flask import Flask

from config.settings import Config
from extensions import socketio
from services import container
from routes import register_blueprints
from routes.sockets import register_socket_events


def create_app() -> Flask:
    """Crea y configura la aplicacion Flask."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # ── Extensiones ──────────────────────────────────────
    socketio.init_app(
        app,
        cors_allowed_origins=Config.ALLOWED_ORIGINS,
        async_mode='threading',
    )

    # ── Dependencias (container) ─────────────────────────
    base_dir = os.path.dirname(__file__)
    container.init(base_dir)

    # ── Blueprints ───────────────────────────────────────
    register_blueprints(app)

    # ── SocketIO events ──────────────────────────────────
    register_socket_events()

    # ── Security headers ─────────────────────────────────
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    return app


# ── Punto de entrada ─────────────────────────────────────

app = create_app()

if __name__ == '__main__':
    try:
        container.system_state.camera_source = int(
            container.db_manager.get_setting('camera_source', Config.CAMERA_SOURCE)
        )
    except ValueError:
        container.system_state.camera_source = Config.CAMERA_SOURCE

    print("FireWatch iniciado en http://localhost:5000")
    socketio.run(app, debug=Config.DEBUG, host='0.0.0.0', port=5000)
