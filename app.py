"""
FireWatch - Sistema de Detección de Incendios
Aplicación principal Flask
"""

from flask import Flask, render_template, jsonify, request, Response, send_file
from flask_socketio import SocketIO, emit
import cv2
import threading
import time
import json
import os
import base64
from datetime import datetime
import io
from concurrent.futures import ThreadPoolExecutor
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config.settings import Config
from config.database import DatabaseManager
from modules.detector import FireDetector
from modules.notifier import EmailNotifier
from modules.esp32_controller import ESP32Controller
from modules.history_manager import HistoryManager
from modules.database_manager import DBManager
from modules.file_manager import FileManager
from modules.fire_predictor import FirePredictor
from modules.routes_mobile import mobile_bp

EMAIL_CONFIG_KEYS = {'smtp_server', 'smtp_port', 'email_sender', 'email_recipient', 'email_password'}

def filter_public_settings(settings):
    return {k: v for k, v in settings.items() if k not in EMAIL_CONFIG_KEYS}

# ─── FUNCIONES VALIDADORAS ─────────────────────────────────────────────────────

def validate_float_range(value, min_val, max_val, field_name):
    """Valida que un valor sea float dentro de rango"""
    try:
        float_val = float(value)
        if float_val < min_val or float_val > max_val:
            return None, f'{field_name} debe estar entre {min_val} y {max_val}'
        return float_val, None
    except (ValueError, TypeError):
        return None, f'{field_name} debe ser un número válido'

def validate_int_range(value, min_val, max_val, field_name):
    """Valida que un valor sea int dentro de rango"""
    try:
        int_val = int(value)
        if int_val < min_val or int_val > max_val:
            return None, f'{field_name} debe estar entre {min_val} y {max_val}'
        return int_val, None
    except (ValueError, TypeError):
        return None, f'{field_name} debe ser un número entero válido'

def validate_string_length(value, max_length, field_name):
    """Valida longitud máxima de string"""
    if isinstance(value, str) and len(value) > max_length:
        return None, f'{field_name} no puede exceder {max_length} caracteres'
    return str(value), None

app = Flask(__name__)
app.config.from_object(Config)
socketio = SocketIO(app, cors_allowed_origins=Config.ALLOWED_ORIGINS, async_mode='threading')
app.register_blueprint(mobile_bp)


# ─── SECURITY HEADERS ─────────────────────────────────────────────────────────

@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

# Módulos globales
detector = FireDetector()
notifier = EmailNotifier()
esp32 = ESP32Controller()
history = HistoryManager()
db_manager = DBManager()
file_manager = FileManager(os.path.dirname(__file__))
fire_predictor = FirePredictor()

# Inyectar db_manager en notifier para acceder a destinatarios
notifier.set_db_manager(db_manager)

executor = ThreadPoolExecutor(max_workers=4)
state_lock = threading.Lock()

# Inicializar base de datos
db_manager.init_db()

# Estado del sistema
system_state = {
    "monitoring": False,
    "fire_detected": False,
    "alert_active": False,
    "last_detection": None,
    "confidence": 0.0,
    "frame_count": 0,
    "camera_source": 0
}

monitoring_thread = None
sensor_thread = None
stop_event = threading.Event()

# ─── RUTAS PRINCIPALES ─────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/historial')
def historial():
    return render_template('history.html')

@app.route('/estadisticas')
def estadisticas():
    return render_template('statistics.html')

@app.route('/configuracion')
def configuracion():
    return render_template('settings.html')



# ─── API - MONITOREO ────────────────────────────────────────────────────────────

@app.route('/api/start_monitoring', methods=['POST'])
def start_monitoring():
    global monitoring_thread, sensor_thread, stop_event
    with state_lock:
        if system_state['monitoring']:
            return jsonify({'success': False, 'message': 'El monitoreo ya está activo'})
        system_state['monitoring'] = True
    
    stop_event.clear()
    source = request.json.get('source')
    if source is None:
        source = db_manager.get_setting('camera_source', system_state['camera_source'])
    system_state['camera_source'] = int(source) if isinstance(source, str) and source.isdigit() else source

    monitoring_thread = socketio.start_background_task(monitor_loop, source)
    sensor_thread = socketio.start_background_task(sensor_monitor_loop)
    
    socketio.emit('system_status', {'status': 'monitoring', 'message': 'Monitoreo iniciado', 'state': system_state})
    return jsonify({'success': True, 'message': 'Monitoreo iniciado'})


@app.route('/api/stop_monitoring', methods=['POST'])
def stop_monitoring():
    stop_event.set()
    with state_lock:
        system_state['monitoring'] = False
        system_state['fire_detected'] = False
        system_state['alert_active'] = False
    socketio.emit('system_status', {'status': 'idle', 'message': 'Monitoreo detenido'})
    return jsonify({'success': True, 'message': 'Monitoreo detenido'})


@app.route('/api/test_esp32', methods=['POST'])
def test_esp32():
    result = esp32.test_connection()
    return jsonify(result)


@app.route('/api/reset_alert', methods=['POST'])
def reset_alert():
    system_state['alert_active'] = False
    system_state['fire_detected'] = False
    esp32.deactivate()
    socketio.emit('alert_reset', {})
    return jsonify({'success': True, 'message': 'Alerta reiniciada'})


@app.route('/api/system_state')
def get_system_state():
    return jsonify(system_state)

@app.route('/video_feed')
def video_feed():
    """Ruta auxiliar para el placeholder de video cuando no existe feed MJPEG."""
    placeholder = os.path.join(app.static_folder, 'images', 'no-signal.svg')
    return send_file(placeholder, mimetype='image/svg+xml')

@app.route('/screenshots/<path:filename>')
def screenshot_file(filename):
    screenshots_dir = os.path.join(os.path.dirname(__file__), 'screenshots')
    # Quitar prefijo 'screenshots/' duplicado si existe (datos legacy en BD)
    if filename.startswith('screenshots/'):
        filename = filename[len('screenshots/'):]
    # Prevenir path traversal: resolver ruta y verificar que queda dentro de screenshots_dir
    safe_path = os.path.realpath(os.path.join(screenshots_dir, filename))
    if not safe_path.startswith(os.path.realpath(screenshots_dir)):
        return jsonify({'error': 'Acceso denegado'}), 403
    return send_file(safe_path)

@app.route('/api/config')
def api_get_config():
    return jsonify(filter_public_settings(db_manager.get_all_settings()))

@app.route('/api/config/<path:section>', methods=['POST'])
def api_save_config(section):
    if section == 'email':
        return jsonify({'success': False, 'message': 'La configuración de correo solo se gestiona en el backend'})

    data = request.json or {}
    errors = []
    
    # Validar configuración según sección
    if section == 'detection':
        if 'detection_threshold' in data:
            val, err = validate_float_range(data['detection_threshold'], 0.0, 1.0, 'Threshold')
            if err:
                errors.append(err)
            else:
                data['detection_threshold'] = val
        
        if 'alert_cooldown' in data:
            val, err = validate_int_range(data['alert_cooldown'], 1, 3600, 'Cooldown')
            if err:
                errors.append(err)
            else:
                data['alert_cooldown'] = val
        
        if 'camera_source' in data:
            val, err = validate_int_range(data['camera_source'], 0, 10, 'Camera source')
            if err:
                errors.append(err)
            else:
                data['camera_source'] = val
        
        if 'model_path' in data:
            val, err = validate_string_length(data['model_path'], 500, 'Model path')
            if err:
                errors.append(err)
    
    elif section == 'esp32':
        if 'esp32_port' in data:
            val, err = validate_int_range(data['esp32_port'], 1, 65535, 'ESP32 port')
            if err:
                errors.append(err)
            else:
                data['esp32_port'] = val
        
        if 'esp32_ip' in data:
            val, err = validate_string_length(data['esp32_ip'], 255, 'ESP32 IP')
            if err:
                errors.append(err)
    
    elif section == 'db':
        if 'db_port' in data:
            val, err = validate_int_range(data['db_port'], 1, 65535, 'DB port')
            if err:
                errors.append(err)
            else:
                data['db_port'] = val
        
        for field in ['db_host', 'db_user', 'db_name']:
            if field in data:
                val, err = validate_string_length(data[field], 255, field)
                if err:
                    errors.append(err)
    
    if errors:
        return jsonify({'success': False, 'message': '; '.join(errors)}), 400
    
    for key, value in data.items():
        if key in EMAIL_CONFIG_KEYS:
            continue
        db_manager.save_setting(key, value)
    return jsonify({'success': True, 'message': 'Configuración guardada'})

@app.route('/api/test-db')
def api_test_db():
    return jsonify(db_manager.test_connection())

@app.route('/api/test-esp32')
def api_test_esp32():
    return jsonify(esp32.test_connection())

@app.route('/api/test-email')
def api_test_email():
    return jsonify(notifier.send_test_email())

# ─── API - FILTRO DE PANTALLAS ────────────────────────────────────────────────

@app.route('/api/screen-filter', methods=['GET'])
def api_get_screen_filter():
    """Obtiene estado del filtro de pantallas"""
    return jsonify(detector.get_screen_filter_status())

@app.route('/api/screen-filter', methods=['POST'])
def api_set_screen_filter():
    """Configura el filtro de pantallas"""
    data = request.json or {}
    enabled = data.get('enabled', True)

    result = detector.set_screen_filter(bool(enabled))
    return jsonify(result), (200 if result['success'] else 400)

@app.route('/api/sensor-alert', methods=['POST'])
def api_sensor_alert():
    """Recibe alertas de sensores del ESP32 (MQ2, DHT22), guarda datos y envía correo"""
    try:
        data = request.json or {}
        alert_type = data.get('type', 'UNKNOWN')
        
        # Validar rangos de sensores
        temp_val, temp_err = validate_float_range(data.get('temperature', 0), -50, 60, 'Temperatura')
        if temp_err:
            return jsonify({'success': False, 'message': temp_err}), 400
        
        hum_val, hum_err = validate_float_range(data.get('humidity', 0), 0, 100, 'Humedad')
        if hum_err:
            return jsonify({'success': False, 'message': hum_err}), 400
        
        mq2_val, mq2_err = validate_int_range(data.get('mq2_value', 0), 0, 4095, 'MQ2')
        if mq2_err:
            return jsonify({'success': False, 'message': mq2_err}), 400
        
        temperature = temp_val
        humidity = hum_val
        mq2_value = mq2_val
        
        # Guardar datos del sensor
        fire_predictor.save_sensor_data(
            temperature=temperature,
            humidity=humidity,
            mq2_value=mq2_value,
            location=data.get('location', 'Default'),
        )
        
        # Generar predicción forzada desde la alerta del ESP32.
        # A diferencia de predict_fire_risk(), este método eleva el nivel de riesgo
        # al mínimo que corresponde al tipo de alarma que el hardware ya disparó
        # (CRITICAL para MQ2_HIGH, HIGH para TEMP_HIGH), evitando subrepresentar
        # en el dashboard lo que el ESP32 ya consideró peligroso.
        prediction = fire_predictor.predict_from_esp32_alert(
            alert_type=alert_type,
            mq2_value=mq2_value,
            temperature=temperature,
            humidity=humidity,
        )
        
        # Emitir actualización en tiempo real a través de WebSocket
        with app.app_context():
            socketio.emit('sensor_update', {
                'temperature': temperature,
                'humidity': humidity,
                'mq2_value': mq2_value,
                'prediction': prediction,
                'timestamp': datetime.now().isoformat()
            }, skip_sid=True)
        
        # Crear mensaje de alerta basado en tipo
        if alert_type == 'MQ2_HIGH':
            subject_prefix = "🚨 ALERTA DE GAS/HUMO DETECTADO"
            alert_desc = f"Nivel de gases/humo alto: {mq2_value} ppm"
        elif alert_type == 'TEMP_HIGH':
            subject_prefix = "🌡️ ALERTA TEMPERATURA ALTA"
            alert_desc = f"Temperatura peligrosa: {temperature}°C"
        else:
            subject_prefix = "⚠️ ALERTA DEL SENSOR"
            alert_desc = alert_type
        
        # Construir correo HTML
        msg = MIMEMultipart()
        msg['From'] = Config.EMAIL_SENDER
        msg['To'] = Config.EMAIL_RECIPIENT
        msg['Subject'] = f"{subject_prefix} - FireWatch [{datetime.now().strftime('%H:%M:%S')}]"
        
        body = f"""
        <html><body style="font-family:Arial,sans-serif;color:#222;background:#f5f5f5;margin:0;padding:20px;">
        <div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;box-shadow:0 4px 6px rgba(0,0,0,0.1);">
            <div style="background:#ff6b35;padding:20px;border-radius:12px 12px 0 0;color:white;text-align:center;">
                <h1 style="margin:0;font-size:24px;">⚠️ ALERTA DEL SISTEMA ESP32</h1>
            </div>
            
            <div style="padding:24px;">
                <p style="font-size:16px;color:#333;margin:0 0 20px 0;">
                    <strong>{alert_desc}</strong>
                </p>
                
                <table style="width:100%;border-collapse:collapse;margin:20px 0;">
                    <tr style="background:#f9f9f9;">
                        <td style="padding:12px;border-bottom:1px solid #eee;font-weight:bold;width:35%;">Fecha/Hora:</td>
                        <td style="padding:12px;border-bottom:1px solid #eee;">{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</td>
                    </tr>
                    <tr>
                        <td style="padding:12px;border-bottom:1px solid #eee;font-weight:bold;">Tipo de Alerta:</td>
                        <td style="padding:12px;border-bottom:1px solid #eee;">{alert_type}</td>
                    </tr>
                    <tr style="background:#f9f9f9;">
                        <td style="padding:12px;border-bottom:1px solid #eee;font-weight:bold;">Temperatura:</td>
                        <td style="padding:12px;border-bottom:1px solid #eee;">{temperature:.1f}°C</td>
                    </tr>
                    <tr>
                        <td style="padding:12px;border-bottom:1px solid #eee;font-weight:bold;">Humedad:</td>
                        <td style="padding:12px;border-bottom:1px solid #eee;">{humidity:.1f}%</td>
                    </tr>
                    <tr style="background:#f9f9f9;">
                        <td style="padding:12px;border-bottom:1px solid #eee;font-weight:bold;">Nivel MQ2 (Gas):</td>
                        <td style="padding:12px;border-bottom:1px solid #eee;"><span style="background:#ff6b35;color:white;padding:4px 12px;border-radius:4px;font-weight:bold;">{mq2_value}</span></td>
                    </tr>
                    <tr>
                        <td style="padding:12px;font-weight:bold;">Riesgo Predicho:</td>
                        <td style="padding:12px;"><span style="background:{_risk_color(prediction['prediction'])};color:white;padding:4px 12px;border-radius:4px;font-weight:bold;">{prediction['prediction']} ({prediction['risk_percentage']:.1f}%)</span></td>
                    </tr>
                </table>
                
                <div style="background:#fff3cd;border-left:4px solid #ff9800;padding:12px;margin-top:20px;border-radius:4px;">
                    <p style="margin:0;font-size:14px;color:#333;">
                        ⚠️ <strong>Acción Inmediata:</strong> Verifica la zona y toma medidas de seguridad.
                    </p>
                </div>
            </div>
            
            <div style="background:#f5f5f5;padding:16px;border-radius:0 0 12px 12px;text-align:center;border-top:1px solid #eee;">
                <p style="margin:0;font-size:12px;color:#999;">
                    FireWatch — Sistema Automático de Monitoreo de Incendios y Gases
                </p>
            </div>
        </div>
        </body></html>
        """
        msg.attach(MIMEText(body, 'html'))
        
        # Enviar correo
        try:
            import smtplib
            with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(Config.EMAIL_SENDER, Config.EMAIL_PASSWORD)
                smtp.sendmail(Config.EMAIL_SENDER, Config.EMAIL_RECIPIENT, msg.as_string())
                print(f"[Sensor Alert] Correo enviado: {alert_type}")
        except Exception as e:
            print(f"[Sensor Alert] Error enviando correo: {e}")
        
        return jsonify({
            'success': True, 
            'message': f'Alerta {alert_type} recibida y procesada',
            'prediction': prediction,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        print(f"[Sensor Alert] Error: {e}")
        return jsonify({'success': False, 'message': 'Error interno al procesar alerta'}), 500

def _risk_color(risk_level: str) -> str:
    """Retorna color hexadecimal basado en nivel de riesgo"""
    colors = {
        'CRITICAL': '#cc0000',
        'HIGH': '#ff6b35',
        'MEDIUM': '#ff9800',
        'LOW': '#ffc107',
        'MINIMAL': '#4caf50',
    }
    return colors.get(risk_level, '#999999')

# ─── API - ESTADÍSTICAS DE SENSORES ────────────────────────────────────────────

@app.route('/api/fire-risk', methods=['GET'])
def get_fire_risk():
    """Obtiene predicción actual de riesgo de incendio"""
    try:
        prediction = fire_predictor.predict_fire_risk()
        return jsonify(prediction), 200
    except Exception as e:
        print(f"[Fire Risk] Error: {e}")
        return jsonify({'success': False, 'message': 'Error al calcular riesgo'}), 500

@app.route('/api/sensor-data', methods=['GET', 'POST'])
def sensor_data():
    """
    GET: Obtiene últimas lecturas de sensores
    POST: Recibe nuevas lecturas de sensores (alternativa a sensor-alert)
    """
    if request.method == 'POST':
        try:
            data = request.json or {}
            
            # Validar rangos de sensores
            temp_val, temp_err = validate_float_range(data.get('temperature', 0), -50, 60, 'Temperatura')
            if temp_err:
                return jsonify({'success': False, 'message': temp_err}), 400
            
            hum_val, hum_err = validate_float_range(data.get('humidity', 0), 0, 100, 'Humedad')
            if hum_err:
                return jsonify({'success': False, 'message': hum_err}), 400
            
            mq2_val, mq2_err = validate_int_range(data.get('mq2_value', 0), 0, 4095, 'MQ2')
            if mq2_err:
                return jsonify({'success': False, 'message': mq2_err}), 400
            
            temperature = temp_val
            humidity = hum_val
            mq2_value = mq2_val
            
            # Guardar datos
            fire_predictor.save_sensor_data(
                temperature=temperature,
                humidity=humidity,
                mq2_value=mq2_value,
                location=data.get('location', 'Default'),
                pressure=data.get('pressure'),
                co_level=data.get('co_level'),
                smoke_level=data.get('smoke_level'),
            )
            
            # Obtener predicción
            prediction = fire_predictor.predict_fire_risk(temperature, humidity, mq2_value)
            
            # Emitir actualización WebSocket
            with app.app_context():
                socketio.emit('sensor_update', {
                    'temperature': temperature,
                    'humidity': humidity,
                    'mq2_value': mq2_value,
                    'prediction': prediction,
                    'timestamp': datetime.now().isoformat()
                }, skip_sid=True)
            
            return jsonify({
                'success': True,
                'message': 'Datos guardados',
                'prediction': prediction
            }), 200
        except Exception as e:
            print(f"[Sensor Data] Error: {e}")
            return jsonify({'success': False, 'message': 'Error interno al guardar datos'}), 500
    
    else:  # GET
        try:
            latest = fire_predictor._get_latest_sensor_data()
            if latest:
                prediction = fire_predictor.predict_fire_risk(
                    latest['temperature'],
                    latest['humidity'],
                    latest['mq2_value']
                )
                return jsonify({
                    'data': latest,
                    'prediction': prediction
                }), 200
            else:
                return jsonify({
                    'data': None,
                    'message': 'No hay datos de sensores disponibles'
                }), 200
        except Exception as e:
            print(f"[Sensor Data GET] Error: {e}")
            return jsonify({'success': False, 'message': 'Error al obtener datos de sensores'}), 500

@app.route('/api/sensor-stats', methods=['GET'])
def get_sensor_stats():
    """Obtiene estadísticas de sensores de los últimos días"""
    try:
        try:
            days = int(request.args.get('days', 7))
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Parámetro days debe ser un número'}), 400
        
        if days < 1 or days > 365:
            return jsonify({'success': False, 'message': 'Days debe estar entre 1 y 365'}), 400
        
        stats = fire_predictor.get_statistics(days)
        return jsonify({
            'success': True,
            'days': days,
            'data': stats
        }), 200
    except Exception as e:
        print(f"[Sensor Stats] Error: {e}")
        return jsonify({'success': False, 'message': 'Error al obtener estadísticas'}), 500

# ─── API - HISTORIAL ────────────────────────────────────────────────────────────

@app.route('/api/detections')
def get_detections():
    try:
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)  # Limitar paginación
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Parámetros de paginación inválidos'}), 400

    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    min_confidence = request.args.get('min_confidence', type=float)
    status = request.args.get('status')

    result = history.get_detections(
        page=page, per_page=per_page,
        date_from=date_from, date_to=date_to,
        min_confidence=min_confidence, status=status
    )
    return jsonify(result)


@app.route('/api/detections/<int:detection_id>')
def get_detection(detection_id):
    detection = history.get_detection_by_id(detection_id)
    if detection:
        return jsonify(detection)
    return jsonify({'error': 'No encontrado'}), 404


@app.route('/api/export/csv')
def export_csv():
    csv_data = history.export_csv()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=detecciones.csv'}
    )


@app.route('/api/export/pdf')
def export_pdf():
    """Genera y descarga un reporte PDF profesional con formato formal"""
    try:
        pdf_data = history.export_pdf()
        filename = f"firewatch_reporte_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        return Response(
            pdf_data,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment;filename={filename}'}
        )
    except Exception as e:
        print(f"[PDF Export] Error: {e}")
        return jsonify({'error': 'Error al generar PDF'}), 500


@app.route('/api/send-report-email', methods=['POST'])
def send_report_email():
    """Genera un reporte PDF y lo envía por correo al destinatario especificado"""
    try:
        data = request.json or {}
        recipient = data.get('recipient', '').strip()
        
        if not recipient:
            return jsonify({'success': False, 'message': 'Especifica un correo destinatario'}), 400
        
        # Generar PDF
        pdf_data = history.export_pdf()
        
        # Obtener estadísticas
        stats = history.get_stats()
        
        # Enviar por correo
        result = notifier.send_report_email(pdf_data, recipient, stats)
        
        if result['success']:
            print(f"[Report] Reporte enviado a {recipient}")
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        print(f"[Report Email] Error: {e}")
        return jsonify({'success': False, 'message': 'Error al enviar reporte'}), 500


@app.route('/api/stats')
def get_stats():
    stats = history.get_stats()
    # Asegurar que los valores son números, no None
    return jsonify({
        'total': int(stats.get('total') or 0),
        'today': int(stats.get('today') or 0),
        'avg_confidence': float(stats.get('avg_confidence') or 0),
        'alerts_sent': int(stats.get('alerts_sent') or 0)
    })

# ─── API - CONFIGURACIÓN ────────────────────────────────────────────────────────

@app.route('/api/settings', methods=['GET'])
def get_settings():
    settings = filter_public_settings(db_manager.get_all_settings())
    return jsonify(settings)


@app.route('/api/settings', methods=['POST'])
def save_settings():
    data = request.json
    for key, value in (data or {}).items():
        if key in EMAIL_CONFIG_KEYS:
            continue
        db_manager.save_setting(key, value)
    return jsonify({'success': True, 'message': 'Configuración guardada'})


@app.route('/api/test_email', methods=['POST'])
def test_email():
    result = notifier.send_test_email()
    return jsonify(result)


@app.route('/api/test_db', methods=['POST'])
def test_db():
    result = db_manager.test_connection()
    return jsonify(result)


# ─── ENDPOINTS PARA GESTIÓN DE DESTINATARIOS ──────────────────────────────

@app.route('/api/recipients', methods=['GET'])
def get_recipients():
    """Obtiene lista de destinatarios de alertas"""
    recipients = db_manager.get_recipients(active_only=False)
    return jsonify({'success': True, 'recipients': recipients})


@app.route('/api/recipients', methods=['POST'])
def add_recipient():
    """Agrega un nuevo destinatario"""
    data = request.json or {}
    email = data.get('email', '').strip()
    name = data.get('name', '').strip()
    
    if not email:
        return jsonify({'success': False, 'message': 'Email es requerido'}), 400
    
    result = db_manager.add_recipient(email, name)
    return jsonify(result), (200 if result['success'] else 400)


@app.route('/api/recipients/<int:recipient_id>', methods=['PUT'])
def update_recipient(recipient_id):
    """Actualiza un destinatario"""
    data = request.json or {}
    email = data.get('email', '').strip() if data.get('email') is not None else None
    name = data.get('name', '').strip() if data.get('name') is not None else None
    
    result = db_manager.update_recipient(recipient_id, email, name)
    return jsonify(result), (200 if result['success'] else 400)


@app.route('/api/recipients/<int:recipient_id>', methods=['DELETE'])
def delete_recipient(recipient_id):
    """Elimina un destinatario"""
    result = db_manager.delete_recipient(recipient_id)
    return jsonify(result), (200 if result['success'] else 400)


@app.route('/api/recipients/<int:recipient_id>/toggle', methods=['POST'])
def toggle_recipient_active(recipient_id):
    """Activa o desactiva un destinatario"""
    data = request.json or {}
    is_active = data.get('is_active', True)
    
    result = db_manager.toggle_recipient_active(recipient_id, is_active)
    return jsonify(result), (200 if result['success'] else 400)


# ─── BUCLE DE MONITOREO ─────────────────────────────────────────────────────────

def sensor_monitor_loop():
    """Bucle para monitorear sensores del ESP32 periódicamente"""
    print("[SENSOR] Iniciando monitoreo de sensores ESP32")
    
    while not stop_event.is_set():
        try:
            # Obtener datos de sensores
            sensor_data = esp32.get_sensor_data()
            
            if sensor_data['success']:
                temperature = sensor_data['temperature']
                humidity = sensor_data['humidity']
                mq2_value = sensor_data['mq2_value']
                
                # Guardar datos
                fire_predictor.save_sensor_data(
                    temperature=temperature,
                    humidity=humidity,
                    mq2_value=mq2_value,
                    location='ESP32'
                )
                
                # Obtener predicción
                prediction = fire_predictor.predict_fire_risk(temperature, humidity, mq2_value)
                
                # Emitir actualización WebSocket
                with app.app_context():
                    socketio.emit('sensor_update', {
                        'temperature': temperature,
                        'humidity': humidity,
                        'mq2_value': mq2_value,
                        'prediction': prediction,
                        'timestamp': datetime.now().isoformat()
                    }, skip_sid=True)
                
                print(f"[SENSOR] Datos obtenidos: T={temperature}°C, H={humidity}%, MQ2={mq2_value}")
            else:
                print(f"[SENSOR] Error obteniendo datos: {sensor_data.get('message', 'Unknown')}")
        
        except Exception as e:
            print(f"[SENSOR] Error en bucle de monitoreo: {e}")
        
        # Esperar 30 segundos antes de la siguiente lectura
        time.sleep(30)

def monitor_loop(source):
    """Bucle principal de detección"""
    # Aceptar índices de cámara como texto desde el frontend
    if isinstance(source, str) and source.isdigit():
        source = int(source)

    print(f"[CAM] Intentando abrir la cámara con source={source!r}")
    cap = cv2.VideoCapture(source)
    
    if not cap.isOpened():
        print(f"[CAM] No se pudo abrir la cámara con source={source!r}")
        with state_lock:
            system_state['monitoring'] = False
        socketio.emit('error', {'message': f'No se pudo abrir la cámara: source={source}'})
        return

    print(f"[CAM] Cámara abierta correctamente con source={source!r}")
    last_alert_time = 0
    cooldown = int(db_manager.get_setting('alert_cooldown', 30))
    threshold = float(db_manager.get_setting('detection_threshold', 0.5))
    
    while not stop_event.is_set():
        try:
            ret, frame = cap.read()
            if not ret:
                print(f"[CAM] Lectura de frame fallida en source={source!r} después de {system_state['frame_count']} frames")
                break
            
            with state_lock:
                system_state['frame_count'] += 1
            
            # Inferencia YOLO
            result = detector.detect(frame, threshold)
            annotated_frame = result['frame']
            
            # Codificar frame como JPEG → base64
            _, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_b64 = base64.b64encode(buffer).decode('utf-8')
            
            # Emitir evento dentro de contexto de aplicación
            with app.app_context():
                # Emitir frame vía WebSocket
                socketio.emit('video_frame', {
                    'frame': frame_b64,
                    'fire_detected': result['fire_detected'],
                    'confidence': result['confidence'],
                    'timestamp': datetime.now().isoformat()
                }, skip_sid=True)
                
                # Emitir resultado del frame para actualizar UI
                socketio.emit('frame_result', {
                    'confidence': result['confidence'],
                    'fire_detected': result['fire_detected'],
                    'label': 'Fuego' if result['fire_detected'] else None
                }, skip_sid=True)
            
            with state_lock:
                system_state['confidence'] = result['confidence']
                system_state['fire_detected'] = result['fire_detected']
            
            # Lógica de alerta
            if result['fire_detected']:
                current_time = time.time()
                with state_lock:
                    system_state['last_detection'] = datetime.now().isoformat()
                
                if current_time - last_alert_time > cooldown:
                    last_alert_time = current_time
                    with state_lock:
                        system_state['alert_active'] = True
                    
                    # Guardar screenshot usando FileManager
                    img_path = file_manager.save_screenshot(annotated_frame)
                    full_img_path = file_manager.get_screenshot_full_path(img_path) if img_path else None
                    
                    # Guardar en BD
                    detection_id = history.save_detection({
                        'timestamp': datetime.now().isoformat(),
                        'confidence': result['confidence'],
                        'image_path': img_path if img_path else '',
                        'status': 'Fuego detectado',
                        'alert_sent': False,
                        'esp32_triggered': False
                    })
                    
                    if detection_id == -1:
                        print("[ALERT] Error al guardar detección en BD")
                    else:
                        # Ejecutar alerta en thread pool
                        executor.submit(handle_fire_alert, detection_id, result['confidence'], full_img_path)
            
            time.sleep(0.03)  # ~30 FPS
        
        except Exception as e:
            print(f"[CAM] Error en bucle de monitoreo: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(0.1)  # Esperar antes de reintentar
    
    cap.release()
    with state_lock:
        system_state['monitoring'] = False


def handle_fire_alert(detection_id, confidence, img_path):
    """Procesa la alerta sin bloquear el bucle de monitoreo."""
    try:
        esp32_ok = False
        with state_lock:
            should_activate_esp32 = system_state.get('monitoring', False)

        if should_activate_esp32:
            esp32_ok = esp32.activate()

        email_ok = notifier.send_fire_alert(confidence, img_path)
        history.update_detection(detection_id, {
            'alert_sent': email_ok,
            'esp32_triggered': esp32_ok
        })
        
        # Emitir eventos dentro de contexto de aplicación Flask
        with app.app_context():
            # Obtener estadísticas actualizadas
            stats = history.get_stats()
            socketio.emit('stats_update', {
                'total': stats.get('today', 0),
                'alerts': stats.get('alerts_sent', 0),
                'avg_conf': stats.get('avg_confidence', 0)
            }, skip_sid=True)
            
            socketio.emit('fire_alert', {
                'confidence': confidence,
                'timestamp': datetime.now().isoformat(),
                'image_path': img_path,
                'email_ok': email_ok,
                'esp32_ok': esp32_ok
            }, skip_sid=True)
    except Exception as e:
        print(f"[ALERT] Error en handle_fire_alert: {e}")
        import traceback
        traceback.print_exc()


# ─── SOCKET.IO EVENTOS ─────────────────────────────────────────────────────────

@socketio.on('connect')
def on_connect():
    emit('system_status', {
        'status': 'connected',
        'state': system_state
    })

@socketio.on('ping')
def on_ping():
    emit('pong', {'timestamp': datetime.now().isoformat()})


if __name__ == '__main__':
    # Inicializar BD
    db_manager.init_db()
    # Detectar cámara USB configurada por defecto
    try:
        system_state['camera_source'] = int(db_manager.get_setting('camera_source', Config.CAMERA_SOURCE))
    except ValueError:
        system_state['camera_source'] = Config.CAMERA_SOURCE
    print("FireWatch iniciado en http://localhost:5000")
    socketio.run(app, debug=Config.DEBUG, host='0.0.0.0', port=5000)