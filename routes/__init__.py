"""
FireWatch - Registro centralizado de blueprints
"""

from routes.main import main_bp
from routes.monitoring import monitoring_bp
from routes.sensors import sensors_bp
from routes.history import history_bp
from routes.config import config_bp
from routes.recipients import recipients_bp
from modules.routes_mobile import mobile_bp


def register_blueprints(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(monitoring_bp)
    app.register_blueprint(sensors_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(recipients_bp)
    app.register_blueprint(mobile_bp)
