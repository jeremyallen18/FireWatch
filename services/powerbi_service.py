"""
FireWatch - Servicio de Power BI
Envia datos de sensores en tiempo real al streaming dataset de Power BI.
"""

import threading
from datetime import datetime

import requests

from services import container


_push_url = None
_enabled = False
_lock = threading.Lock()


def _load_config():
    """Carga la configuracion de Power BI desde la BD."""
    global _push_url, _enabled
    try:
        settings = container.db_manager.get_all_settings()
        _push_url = settings.get('powerbi_push_url', '').strip()
        _enabled = settings.get('powerbi_enabled', 'false').lower() in ('1', 'true', 'yes')
    except Exception:
        _push_url = ''
        _enabled = False


def reload_config():
    """Recarga la configuracion (llamar tras guardar settings)."""
    with _lock:
        _load_config()


def is_configured() -> bool:
    with _lock:
        if _push_url is None:
            _load_config()
        return _enabled and bool(_push_url)


def push_sensor_data(temperature: float, humidity: float, mq2_value: float,
                     prediction: dict | None = None):
    """Envia una lectura de sensor al streaming dataset de Power BI.
    Se ejecuta en un hilo separado para no bloquear la respuesta HTTP.
    """
    if not is_configured():
        return

    with _lock:
        url = _push_url

    risk_level = ''
    risk_score = 0.0
    if prediction:
        risk_level = prediction.get('risk_level', '')
        risk_score = prediction.get('risk_score', 0.0)

    payload = [{
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "temperature": round(temperature, 2),
        "humidity": round(humidity, 2),
        "mq2_value": round(mq2_value, 2),
        "risk_level": risk_level,
        "risk_score": round(risk_score, 4),
    }]

    thread = threading.Thread(
        target=_send_to_powerbi,
        args=(url, payload),
        daemon=True,
    )
    thread.start()


def _send_to_powerbi(url: str, payload: list):
    """POST al endpoint de streaming de Power BI."""
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code not in (200, 204):
            print(f"[Power BI] Respuesta inesperada: {resp.status_code} — {resp.text[:200]}")
    except requests.RequestException as e:
        print(f"[Power BI] Error al enviar datos: {e}")


def test_connection() -> dict:
    """Envia un dato de prueba y verifica la respuesta."""
    with _lock:
        if _push_url is None:
            _load_config()
        url = _push_url

    if not url:
        return {'success': False, 'message': 'No se ha configurado la URL de Power BI'}

    test_payload = [{
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "temperature": 25.0,
        "humidity": 50.0,
        "mq2_value": 100.0,
        "risk_level": "LOW",
        "risk_score": 0.1,
    }]

    try:
        resp = requests.post(url, json=test_payload, timeout=10)
        if resp.status_code in (200, 204):
            return {'success': True, 'message': 'Conexion exitosa con Power BI'}
        return {
            'success': False,
            'message': f'Power BI respondio con codigo {resp.status_code}',
        }
    except requests.ConnectionError:
        return {'success': False, 'message': 'No se pudo conectar a Power BI (URL invalida o sin red)'}
    except requests.Timeout:
        return {'success': False, 'message': 'Timeout al conectar con Power BI'}
    except requests.RequestException as e:
        return {'success': False, 'message': f'Error: {e}'}
