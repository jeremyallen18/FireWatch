"""
FireWatch - Eventos SocketIO
"""

from datetime import datetime
from flask_socketio import emit

from extensions import socketio
from services import container


def register_socket_events():
    """Registra los manejadores de eventos SocketIO."""

    @socketio.on('connect')
    def on_connect():
        emit('system_status', {
            'status': 'connected',
            'state': container.system_state.snapshot(),
        })

    @socketio.on('ping')
    def on_ping():
        emit('pong', {'timestamp': datetime.now().isoformat()})
