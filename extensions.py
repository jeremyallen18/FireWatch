"""
FireWatch - Extensiones compartidas
Instancias creadas aqui, inicializadas en la factory.
"""

from flask_socketio import SocketIO
from concurrent.futures import ThreadPoolExecutor

socketio = SocketIO()
executor = ThreadPoolExecutor(max_workers=4)
