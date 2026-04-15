"""
FireWatch - Rutas de sensores
"""

from flask import Blueprint, jsonify, request

from services import container
from services import sensor_service
from core.validators import validate_sensor_data
from core.responses import error_response

sensors_bp = Blueprint('sensors', __name__)


@sensors_bp.route('/api/sensor-alert', methods=['POST'])
def api_sensor_alert():
    """Recibe alertas de sensores del ESP32 (MQ2, DHT22)."""
    try:
        data = request.json or {}

        validated, errors = validate_sensor_data(data)
        if errors:
            return error_response(errors[0])

        result = sensor_service.process_sensor_alert(data, validated)
        return jsonify(result), 200

    except Exception as e:
        print(f"[Sensor Alert] Error: {e}")
        return error_response('Error interno al procesar alerta', 500)


@sensors_bp.route('/api/sensor-data', methods=['GET', 'POST'])
def sensor_data():
    """GET: Ultimas lecturas. POST: Nuevas lecturas."""
    if request.method == 'POST':
        try:
            data = request.json or {}

            validated, errors = validate_sensor_data(data)
            if errors:
                return error_response(errors[0])

            result = sensor_service.save_sensor_data(data, validated)
            return jsonify(result), 200

        except Exception as e:
            print(f"[Sensor Data] Error: {e}")
            return error_response('Error interno al guardar datos', 500)

    else:
        try:
            result = sensor_service.get_latest_sensor_data()
            return jsonify(result), 200
        except Exception as e:
            print(f"[Sensor Data GET] Error: {e}")
            return error_response('Error al obtener datos de sensores', 500)


@sensors_bp.route('/api/fire-risk', methods=['GET'])
def get_fire_risk():
    try:
        prediction = container.fire_predictor.predict_fire_risk()
        return jsonify(prediction), 200
    except Exception as e:
        print(f"[Fire Risk] Error: {e}")
        return error_response('Error al calcular riesgo', 500)


@sensors_bp.route('/api/sensor-stats', methods=['GET'])
def get_sensor_stats():
    try:
        try:
            days = int(request.args.get('days', 7))
        except (ValueError, TypeError):
            return error_response('Parametro days debe ser un numero')

        if days < 1 or days > 365:
            return error_response('Days debe estar entre 1 y 365')

        stats = container.fire_predictor.get_statistics(days)
        return jsonify({'success': True, 'days': days, 'data': stats}), 200

    except Exception as e:
        print(f"[Sensor Stats] Error: {e}")
        return error_response('Error al obtener estadisticas', 500)


@sensors_bp.route('/api/screen-filter', methods=['GET'])
def api_get_screen_filter():
    return jsonify(container.detector.get_screen_filter_status())


@sensors_bp.route('/api/screen-filter', methods=['POST'])
def api_set_screen_filter():
    data = request.json or {}
    enabled = data.get('enabled', True)
    result = container.detector.set_screen_filter(bool(enabled))
    return jsonify(result), (200 if result['success'] else 400)
