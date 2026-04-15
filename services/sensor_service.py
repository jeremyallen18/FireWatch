"""
FireWatch - Servicio de sensores
Orquesta la recepcion, persistencia, prediccion y notificacion de datos de sensores.
"""

from datetime import datetime

from extensions import socketio
from services import container
from services.alert_service import build_sensor_alert_email, send_sensor_alert_email


def process_sensor_alert(data: dict, validated: dict) -> dict:
    """Procesa una alerta de sensor del ESP32.
    Guarda datos, genera prediccion, emite WebSocket, envia correo.
    Retorna dict con resultado y prediccion.
    """
    alert_type = data.get('type', 'UNKNOWN')
    temperature = validated['temperature']
    humidity = validated['humidity']
    mq2_value = validated['mq2_value']

    # Guardar datos del sensor
    container.fire_predictor.save_sensor_data(
        temperature=temperature,
        humidity=humidity,
        mq2_value=mq2_value,
        location=data.get('location', 'Default'),
    )

    # Generar prediccion forzada desde la alerta del ESP32
    prediction = container.fire_predictor.predict_from_esp32_alert(
        alert_type=alert_type,
        mq2_value=mq2_value,
        temperature=temperature,
        humidity=humidity,
    )

    # Emitir actualizacion en tiempo real a traves de WebSocket
    socketio.emit('sensor_update', {
        'temperature': temperature,
        'humidity': humidity,
        'mq2_value': mq2_value,
        'prediction': prediction,
        'timestamp': datetime.now().isoformat(),
    }, skip_sid=True)

    # Construir y enviar correo de alerta
    subject, body_html = build_sensor_alert_email(
        alert_type, temperature, humidity, mq2_value, prediction,
    )
    send_sensor_alert_email(subject, body_html)

    return {
        'success': True,
        'message': f'Alerta {alert_type} recibida y procesada',
        'prediction': prediction,
        'timestamp': datetime.now().isoformat(),
    }


def save_sensor_data(data: dict, validated: dict) -> dict:
    """Guarda datos de sensores y retorna prediccion."""
    temperature = validated['temperature']
    humidity = validated['humidity']
    mq2_value = validated['mq2_value']

    container.fire_predictor.save_sensor_data(
        temperature=temperature,
        humidity=humidity,
        mq2_value=mq2_value,
        location=data.get('location', 'Default'),
        pressure=data.get('pressure'),
        co_level=data.get('co_level'),
        smoke_level=data.get('smoke_level'),
    )

    prediction = container.fire_predictor.predict_fire_risk(temperature, humidity, mq2_value)

    socketio.emit('sensor_update', {
        'temperature': temperature,
        'humidity': humidity,
        'mq2_value': mq2_value,
        'prediction': prediction,
        'timestamp': datetime.now().isoformat(),
    }, skip_sid=True)

    return {
        'success': True,
        'message': 'Datos guardados',
        'prediction': prediction,
    }


def get_latest_sensor_data() -> dict:
    """Obtiene ultimos datos de sensores con prediccion."""
    latest = container.fire_predictor._get_latest_sensor_data()
    if latest:
        prediction = container.fire_predictor.predict_fire_risk(
            latest['temperature'],
            latest['humidity'],
            latest['mq2_value'],
        )
        return {'data': latest, 'prediction': prediction}
    return {'data': None, 'message': 'No hay datos de sensores disponibles'}
