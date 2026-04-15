"""
FireWatch - Servicio de configuracion
"""

from services import container
from core.validators import validate_config_section

EMAIL_CONFIG_KEYS = {'smtp_server', 'smtp_port', 'email_sender', 'email_recipient', 'email_password'}


def filter_public_settings(settings: dict) -> dict:
    return {k: v for k, v in settings.items() if k not in EMAIL_CONFIG_KEYS}


def get_all_public_settings() -> dict:
    return filter_public_settings(container.db_manager.get_all_settings())


def save_section_config(section: str, data: dict) -> dict:
    """Valida y guarda configuracion de una seccion.
    Retorna {'success': bool, 'message': str}.
    """
    if section == 'email':
        return {'success': False, 'message': 'La configuracion de correo solo se gestiona en el backend'}

    errors = validate_config_section(section, data)
    if errors:
        return {'success': False, 'message': '; '.join(errors)}

    for key, value in data.items():
        if key in EMAIL_CONFIG_KEYS:
            continue
        container.db_manager.save_setting(key, value)

    return {'success': True, 'message': 'Configuracion guardada'}


def save_settings(data: dict) -> dict:
    """Guarda settings generales (filtra campos de email)."""
    for key, value in (data or {}).items():
        if key in EMAIL_CONFIG_KEYS:
            continue
        container.db_manager.save_setting(key, value)
    return {'success': True, 'message': 'Configuracion guardada'}
