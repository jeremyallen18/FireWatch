"""Configuración general de la aplicación FireWatch"""

import os
import secrets
from dotenv import load_dotenv

# Leer variables de entorno desde el archivo .env si existe
load_dotenv()


def _require_env(key: str, default: str = '') -> str:
    """Lee una variable de entorno; retorna default si no existe."""
    return os.environ.get(key, default)


class Config:
    SECRET_KEY = _require_env('SECRET_KEY') or secrets.token_hex(32)
    DEBUG = _require_env('FLASK_DEBUG', 'false').lower() in ('1', 'true', 'yes')

    # Base de datos MySQL
    DB_HOST = _require_env('DB_HOST', 'localhost')
    DB_PORT = int(_require_env('DB_PORT', '3306'))
    DB_USER = _require_env('DB_USER', 'root')
    DB_PASSWORD = _require_env('DB_PASSWORD')
    DB_NAME = _require_env('DB_NAME', 'firewatch_2')

    # Email (SMTP)
    SMTP_SERVER = _require_env('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(_require_env('SMTP_PORT', '587'))
    EMAIL_SENDER = _require_env('EMAIL_SENDER')
    EMAIL_RECIPIENT = _require_env('EMAIL_RECIPIENT')
    EMAIL_PASSWORD = _require_env('EMAIL_PASSWORD')

    # ESP32
    ESP32_IP = _require_env('ESP32_IP', '192.168.0.18')
    ESP32_PORT = int(_require_env('ESP32_PORT', '80'))
    ESP32_MODE = _require_env('ESP32_MODE', 'http')  # http, mqtt, serial

    # YOLO
    MODEL_PATH = _require_env('MODEL_PATH', 'models/best.pt')
    DEFAULT_THRESHOLD = float(_require_env('DEFAULT_THRESHOLD', '0.5'))

    # Sistema
    ALERT_COOLDOWN = int(_require_env('ALERT_COOLDOWN', '30'))
    CAMERA_SOURCE = int(_require_env('CAMERA_SOURCE', '0'))

    # Orígenes CORS permitidos (separados por coma en .env)
    ALLOWED_ORIGINS = [
        o.strip() for o in _require_env(
            'ALLOWED_ORIGINS',
            'http://localhost:5000,http://127.0.0.1:5000'
        ).split(',') if o.strip()
    ]
