"""
FireWatch - Servicio de monitoreo
Bucles de monitoreo de camara y sensores, manejo de alertas de fuego.
"""

import cv2
import base64
import time
from datetime import datetime

from extensions import socketio, executor
from services import container


def start(source):
    """Inicia los hilos de monitoreo de camara y sensores."""
    state = container.system_state
    if not state.start_monitoring():
        return {'success': False, 'message': 'El monitoreo ya esta activo'}

    if source is None:
        source = container.db_manager.get_setting(
            'camera_source', state.camera_source
        )
    state.camera_source = int(source) if isinstance(source, str) and source.isdigit() else source

    socketio.start_background_task(monitor_loop, source)
    socketio.start_background_task(sensor_monitor_loop)

    socketio.emit('system_status', {
        'status': 'monitoring',
        'message': 'Monitoreo iniciado',
        'state': state.snapshot(),
    })
    return {'success': True, 'message': 'Monitoreo iniciado'}


def stop():
    """Detiene el monitoreo."""
    state = container.system_state
    state.stop_monitoring()
    socketio.emit('system_status', {'status': 'idle', 'message': 'Monitoreo detenido'})
    return {'success': True, 'message': 'Monitoreo detenido'}


# ── Bucles en background ────────────────────────────────────


def sensor_monitor_loop():
    """Bucle para monitorear sensores del ESP32 periodicamente."""
    state = container.system_state
    print("[SENSOR] Iniciando monitoreo de sensores ESP32")

    while not state.stop_event.is_set():
        try:
            sensor_data = container.esp32.get_sensor_data()

            if sensor_data['success']:
                temperature = sensor_data['temperature']
                humidity = sensor_data['humidity']
                mq2_value = sensor_data['mq2_value']

                container.fire_predictor.save_sensor_data(
                    temperature=temperature,
                    humidity=humidity,
                    mq2_value=mq2_value,
                    location='ESP32',
                )

                prediction = container.fire_predictor.predict_fire_risk(
                    temperature, humidity, mq2_value,
                )

                socketio.emit('sensor_update', {
                    'temperature': temperature,
                    'humidity': humidity,
                    'mq2_value': mq2_value,
                    'prediction': prediction,
                    'timestamp': datetime.now().isoformat(),
                }, skip_sid=True)

                print(f"[SENSOR] Datos obtenidos: T={temperature}°C, H={humidity}%, MQ2={mq2_value}")
            else:
                print(f"[SENSOR] Error obteniendo datos: {sensor_data.get('message', 'Unknown')}")

        except Exception as e:
            print(f"[SENSOR] Error en bucle de monitoreo: {e}")

        time.sleep(30)


def monitor_loop(source):
    """Bucle principal de deteccion por camara."""
    state = container.system_state

    if isinstance(source, str) and source.isdigit():
        source = int(source)

    print(f"[CAM] Intentando abrir la camara con source={source!r}")
    cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        print(f"[CAM] No se pudo abrir la camara con source={source!r}")
        state.set('monitoring', False)
        socketio.emit('error', {'message': f'No se pudo abrir la camara: source={source}'})
        return

    print(f"[CAM] Camara abierta correctamente con source={source!r}")
    last_alert_time = 0
    cooldown = int(container.db_manager.get_setting('alert_cooldown', 30))
    threshold = float(container.db_manager.get_setting('detection_threshold', 0.5))

    while not state.stop_event.is_set():
        try:
            ret, frame = cap.read()
            if not ret:
                print(f"[CAM] Lectura de frame fallida en source={source!r}")
                break

            state.increment_frame_count()

            result = container.detector.detect(frame, threshold)
            annotated_frame = result['frame']

            _, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_b64 = base64.b64encode(buffer).decode('utf-8')

            socketio.emit('video_frame', {
                'frame': frame_b64,
                'fire_detected': result['fire_detected'],
                'confidence': result['confidence'],
                'timestamp': datetime.now().isoformat(),
            }, skip_sid=True)

            socketio.emit('frame_result', {
                'confidence': result['confidence'],
                'fire_detected': result['fire_detected'],
                'label': 'Fuego' if result['fire_detected'] else None,
            }, skip_sid=True)

            state.update_detection(result['fire_detected'], result['confidence'])

            if result['fire_detected']:
                current_time = time.time()
                state.set('last_detection', datetime.now().isoformat())

                if current_time - last_alert_time > cooldown:
                    last_alert_time = current_time
                    state.set_alert(result['confidence'])

                    img_path = container.file_manager.save_screenshot(annotated_frame)
                    full_img_path = (
                        container.file_manager.get_screenshot_full_path(img_path)
                        if img_path else None
                    )

                    detection_id = container.history.save_detection({
                        'timestamp': datetime.now().isoformat(),
                        'confidence': result['confidence'],
                        'image_path': img_path if img_path else '',
                        'status': 'Fuego detectado',
                        'alert_sent': False,
                        'esp32_triggered': False,
                    })

                    if detection_id == -1:
                        print("[ALERT] Error al guardar deteccion en BD")
                    else:
                        executor.submit(
                            handle_fire_alert, detection_id,
                            result['confidence'], full_img_path,
                        )

            time.sleep(0.03)

        except Exception as e:
            print(f"[CAM] Error en bucle de monitoreo: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(0.1)

    cap.release()
    state.set('monitoring', False)


def handle_fire_alert(detection_id, confidence, img_path):
    """Procesa la alerta sin bloquear el bucle de monitoreo."""
    state = container.system_state
    try:
        esp32_ok = False
        if state.is_monitoring:
            esp32_ok = container.esp32.activate()

        email_ok = container.notifier.send_fire_alert(confidence, img_path)
        container.history.update_detection(detection_id, {
            'alert_sent': email_ok,
            'esp32_triggered': esp32_ok,
        })

        stats = container.history.get_stats()
        socketio.emit('stats_update', {
            'total': stats.get('today', 0),
            'alerts': stats.get('alerts_sent', 0),
            'avg_conf': stats.get('avg_confidence', 0),
        }, skip_sid=True)

        socketio.emit('fire_alert', {
            'confidence': confidence,
            'timestamp': datetime.now().isoformat(),
            'image_path': img_path,
            'email_ok': email_ok,
            'esp32_ok': esp32_ok,
        }, skip_sid=True)

    except Exception as e:
        print(f"[ALERT] Error en handle_fire_alert: {e}")
        import traceback
        traceback.print_exc()
