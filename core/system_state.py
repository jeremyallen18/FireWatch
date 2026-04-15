"""
FireWatch - Gestor de estado del sistema
Encapsula el estado global con locks para thread-safety.
"""

import threading
from datetime import datetime


class SystemState:
    """Estado centralizado del sistema con acceso thread-safe."""

    def __init__(self):
        self._lock = threading.Lock()
        self._state = {
            "monitoring": False,
            "fire_detected": False,
            "alert_active": False,
            "last_detection": None,
            "confidence": 0.0,
            "frame_count": 0,
            "camera_source": 0,
        }
        self.stop_event = threading.Event()

    # ── Lectura ──────────────────────────────────────────────

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._state)

    def get(self, key, default=None):
        with self._lock:
            return self._state.get(key, default)

    # ── Escritura atómica ────────────────────────────────────

    def set(self, key, value):
        with self._lock:
            self._state[key] = value

    def update(self, data: dict):
        with self._lock:
            self._state.update(data)

    # ── Acciones de dominio ──────────────────────────────────

    def start_monitoring(self):
        with self._lock:
            if self._state["monitoring"]:
                return False
            self._state["monitoring"] = True
        self.stop_event.clear()
        return True

    def stop_monitoring(self):
        self.stop_event.set()
        with self._lock:
            self._state["monitoring"] = False
            self._state["fire_detected"] = False
            self._state["alert_active"] = False

    def set_alert(self, confidence: float):
        with self._lock:
            self._state["alert_active"] = True
            self._state["confidence"] = confidence
            self._state["last_detection"] = datetime.now().isoformat()

    def reset_alert(self):
        with self._lock:
            self._state["alert_active"] = False
            self._state["fire_detected"] = False

    def update_detection(self, fire_detected: bool, confidence: float):
        with self._lock:
            self._state["confidence"] = confidence
            self._state["fire_detected"] = fire_detected

    def increment_frame_count(self):
        with self._lock:
            self._state["frame_count"] += 1

    @property
    def is_monitoring(self) -> bool:
        with self._lock:
            return self._state["monitoring"]

    @property
    def camera_source(self):
        with self._lock:
            return self._state["camera_source"]

    @camera_source.setter
    def camera_source(self, value):
        with self._lock:
            self._state["camera_source"] = value
