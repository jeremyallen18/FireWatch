"""
FireWatch - Contenedor de dependencias
Inicializado una sola vez en la application factory.
Los servicios y rutas acceden a las dependencias a traves de este modulo.
"""

import os

from modules.detector import FireDetector
from modules.notifier import EmailNotifier
from modules.esp32_controller import ESP32Controller
from modules.history_manager import HistoryManager
from modules.database_manager import DBManager
from modules.file_manager import FileManager
from modules.fire_predictor import FirePredictor
from core.system_state import SystemState

# ── Infraestructura ──────────────────────────────────────

detector = None
notifier = None
esp32 = None
history = None
db_manager = None
file_manager = None
fire_predictor = None

# ── Core ─────────────────────────────────────────────────

system_state = None


def init(base_dir: str):
    """Crea e inicializa todas las dependencias."""
    global detector, notifier, esp32, history, db_manager
    global file_manager, fire_predictor, system_state

    system_state = SystemState()

    detector = FireDetector()
    notifier = EmailNotifier()
    esp32 = ESP32Controller()
    history = HistoryManager()
    db_manager = DBManager()
    file_manager = FileManager(base_dir)
    fire_predictor = FirePredictor()

    # Inyectar db_manager en notifier para acceder a destinatarios
    notifier.set_db_manager(db_manager)

    # Inicializar base de datos
    db_manager.init_db()
