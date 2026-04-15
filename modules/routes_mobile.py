# modules/routes_mobile.py
# Endpoints exclusivos para la app Flutter móvil
# Recibe fotos/videos, corre el detector y devuelve evaluación de riesgo

import os
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

# Tipos de archivo permitidos para seguridad
ALLOWED_IMAGE_EXT = {'jpg', 'jpeg', 'png', 'webp'}
ALLOWED_VIDEO_EXT = {'mp4', 'mov', 'avi', 'mkv'}
MAX_FILE_MB = 50  # límite de tamaño en MB

mobile_bp = Blueprint('mobile', __name__, url_prefix='/api/mobile')


def _allowed_file(filename: str, media_type: str) -> bool:
    """Valida que la extensión del archivo sea permitida"""
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if media_type == 'image':
        return ext in ALLOWED_IMAGE_EXT
    if media_type == 'video':
        return ext in ALLOWED_VIDEO_EXT
    return False


def _risk_level(confidence: float) -> str:
    """Convierte confianza 0.0-1.0 a nivel de riesgo textual"""
    if confidence >= 0.85: return 'CRITICAL'
    if confidence >= 0.65: return 'HIGH'
    if confidence >= 0.40: return 'MEDIUM'
    return 'LOW'


def _recommendations(level: str) -> list:
    """Retorna recomendaciones según nivel de riesgo"""
    base = ['Mantén el sistema monitoreando', 'Registra el incidente']
    if level == 'CRITICAL':
        return ['🚨 Evacúa inmediatamente', '📞 Llama al 911', '🚫 No regreses sin autorización'] + base
    if level == 'ALTA':
        return ['⚠️ Alerta a personas cercanas', '🧯 Ten extinguidor listo'] + base
    if level == 'PRECAUCIÓN':
        return ['👁️ Monitorea de cerca', '🔍 Verifica la zona'] + base
    return ['✅ Sin riesgo aparente'] + base


@mobile_bp.route('/analyze', methods=['POST'])
def analyze_media():
    """
    Recibe foto o video desde Flutter, corre el modelo YOLOv8
    y retorna nivel de riesgo + confianza + recomendaciones.
    
    Form-data esperado:
      - file       : archivo binario (imagen o video)
      - type       : 'image' | 'video'
      - user_id    : string identificador del usuario (opcional)
    """
    # Importar módulos desde el contenedor de dependencias
    from services import container
    from extensions import socketio
    detector = container.detector
    history = container.history
    notifier = container.notifier
    fire_predictor = container.fire_predictor
    esp32 = container.esp32
    system_state = container.system_state

    # ── Validar que llegó un archivo ──────────────────────────────────────────
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No se recibió ningún archivo'}), 400

    file = request.files['file']
    media_type = request.form.get('type', 'image')   # 'image' o 'video'
    user_id = request.form.get('user_id', 'flutter_user')

    # ── Coordenadas GPS (opcionales) ─────────────────────────────────────────
    lat = None
    lng = None
    try:
        _lat = request.form.get('lat')
        _lng = request.form.get('lng')
        if _lat is not None and _lng is not None:
            lat = float(_lat)
            lng = float(_lng)
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                lat, lng = None, None
    except (ValueError, TypeError):
        pass

    if file.filename == '':
        return jsonify({'success': False, 'error': 'Nombre de archivo vacío'}), 400

    # ── Validar extensión ─────────────────────────────────────────────────────
    filename = secure_filename(file.filename)
    if not _allowed_file(filename, media_type):
        return jsonify({'success': False, 'error': f'Tipo de archivo no permitido para {media_type}'}), 400

    # ── Validar tamaño (antes de guardar) ─────────────────────────────────────
    file.seek(0, 2)                        # mover al final
    size_mb = file.tell() / (1024 * 1024)
    file.seek(0)                           # regresar al inicio
    if size_mb > MAX_FILE_MB:
        return jsonify({'success': False, 'error': f'Archivo demasiado grande ({size_mb:.1f}MB, máx {MAX_FILE_MB}MB)'}), 413

    # ── Guardar temporalmente ─────────────────────────────────────────────────
    unique_name = f"mobile_{uuid.uuid4().hex}_{filename}"
    upload_dir = os.path.join(current_app.root_path, 'screenshots', 'mobile')
    os.makedirs(upload_dir, exist_ok=True)
    save_path = os.path.join(upload_dir, unique_name)
    file.save(save_path)

    fire_found = False
    annotated_path = None
    try:
        # ── Analizar según tipo ───────────────────────────────────────────────

        if media_type == 'image':
            import cv2
            frame = cv2.imread(save_path)
            if frame is None:
                return jsonify({'success': False, 'error': 'No se pudo leer la imagen'}), 400

            # Usar el mismo detector YOLOv8 que usa el monitoreo en tiempo real
            threshold = float(fire_predictor._get_setting('detection_threshold', 0.5)
                              if hasattr(fire_predictor, '_get_setting') else 0.5)
            result = detector.detect(frame, threshold)
            confidence = result['confidence']
            fire_found = result['fire_detected']

            # Guardar frame anotado (con bounding boxes y confianza dibujados)
            if result.get('frame') is not None:
                ann_name = f"annotated_{uuid.uuid4().hex}_{filename}"
                annotated_path = os.path.join(upload_dir, ann_name)
                cv2.imwrite(annotated_path, result['frame'])

        else:  # video — analizar frames clave
            import cv2
            cap = cv2.VideoCapture(save_path)
            confidences = []
            best_frame = None
            frame_idx = 0
            sample_every = 15   # analizar 1 frame de cada 15 (~0.5s en 30fps)

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % sample_every == 0:
                    r = detector.detect(frame, 0.4)
                    confidences.append(r['confidence'])
                    # Guardar el frame con mayor confianza (anotado)
                    if not confidences or r['confidence'] >= max(confidences[:-1], default=0):
                        best_frame = r.get('frame')
                frame_idx += 1
            cap.release()

            # Confianza máxima encontrada en el video
            confidence = max(confidences) if confidences else 0.0
            fire_found = confidence >= 0.5

            # Guardar mejor frame anotado del video
            if best_frame is not None:
                ann_name = f"annotated_{uuid.uuid4().hex}.jpg"
                annotated_path = os.path.join(upload_dir, ann_name)
                cv2.imwrite(annotated_path, best_frame)

        # ── Calcular riesgo ───────────────────────────────────────────────────
        level = _risk_level(confidence)
        result_id = uuid.uuid4().hex[:8].upper()

        # ── Determinar qué imagen guardar en historial ────────────────────────
        # Preferir la anotada (con bounding boxes) si existe
        if annotated_path and os.path.exists(annotated_path):
            hist_image = f"mobile/{os.path.basename(annotated_path)}"
        else:
            hist_image = f"mobile/{unique_name}"

        # ── Guardar en historial (misma BD que el sistema web) ────────────────
        detection_id = history.save_detection({
            'timestamp': datetime.now().isoformat(),
            'confidence': confidence,
            'image_path': hist_image,
            'status': 'Fuego detectado' if fire_found else 'Sin fuego',
            'alert_sent': False,
            'esp32_triggered': False,
        })

        # ── Si hay fuego, notificar con ubicación, imagen anotada y ESP32 ────
        esp32_ok = False
        email_ok = False
        if fire_found and level in ('CRITICAL', 'HIGH'):
            alert_image = annotated_path if annotated_path and os.path.exists(annotated_path) else save_path
            email_ok = notifier.send_fire_alert(confidence, alert_image, lat=lat, lng=lng)

            # Activar alerta ESP32 (buzzer + LED)
            esp32_ok = esp32.activate()

            # Actualizar estado global para que el dashboard lo refleje
            system_state.update({'alert_active': True, 'fire_detected': True})

            if detection_id and detection_id != -1:
                history.update_detection(detection_id, {
                    'alert_sent': email_ok,
                    'esp32_triggered': esp32_ok,
                })

        # ── Emitir por WebSocket para que el dashboard web lo vea ─────────────
        ws_data = {
            'user_id': user_id,
            'media_type': media_type,
            'risk_level': level,
            'confidence': round(confidence * 100, 1),
            'fire_detected': fire_found,
            'timestamp': datetime.now().isoformat(),
        }
        if lat is not None and lng is not None:
            ws_data['lat'] = lat
            ws_data['lng'] = lng
        socketio.emit('mobile_detection', ws_data)

        # Emitir fire_alert para que la app Flutter reciba la notificación push
        if fire_found and level in ('CRITICAL', 'HIGH'):
            socketio.emit('fire_alert', {
                'confidence': confidence,
                'timestamp': datetime.now().isoformat(),
                'image_path': hist_image,
                'email_ok': email_ok,
                'esp32_ok': esp32_ok,
            })

        # ── Respuesta a Flutter ───────────────────────────────────────────────
        return jsonify({
            'success': True,
            'id': result_id,
            'timestamp': datetime.now().isoformat(),
            'risk_level': level,                          # CRITICAL | HIGH | MEDIUM | LOW
            'confidence': round(confidence * 100, 1),    # 0.0 - 100.0
            'fire_detected': fire_found,
            'label': 'fire' if fire_found else 'no_fire',
            'message': {
                'CRITICAL': '🔥 PELIGRO INMEDIATO — Evacúe el área',
                'HIGH':     '⚠️ Riesgo Alto — Contacte emergencias',
                'MEDIUM':   '⚡ Riesgo Moderado — Monitoree de cerca',
                'LOW':      '✅ Sin riesgo aparente',
            }.get(level, 'Análisis completado'),
            'recommendations': _recommendations(level),
            'media_type': media_type,
        }), 200

    except Exception as e:
        print(f"[Mobile API] Error analizando archivo: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': 'Error interno al analizar archivo'}), 500

    finally:
        # Limpiar archivos temporales si no es una detección de fuego
        # (si hubo fuego, se conservan como evidencia)
        if not fire_found:
            if os.path.exists(save_path):
                os.remove(save_path)
            if annotated_path and os.path.exists(annotated_path):
                os.remove(annotated_path)


@mobile_bp.route('/photos', methods=['GET'])
def list_photos():
    """
    Retorna la lista de fotos disponibles en el servidor con metadatos.
    Pensado para que Flutter muestre una galería de evidencias.

    Query params:
      - page     : página (default 1)
      - per_page : cantidad por página (default 20, max 50)
      - filter   : 'all' | 'fire' | 'no_fire' (default 'all')

    Response:
      {
        "success": true,
        "photos": [
          {
            "id": 1,
            "url": "/screenshots/fire_20260405_160847.jpg",
            "thumbnail_url": "/screenshots/fire_20260405_160847.jpg",
            "timestamp": "2026-04-05T16:08:47",
            "confidence": 0.856,
            "status": "Fuego detectado",
            "fire_detected": true,
            "source": "webcam" | "mobile"
          }, ...
        ],
        "total": 247,
        "page": 1,
        "pages": 13
      }
    """
    from services import container
    history = container.history

    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(int(request.args.get('per_page', 20)), 50)
        status_filter = request.args.get('filter', 'all')
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Parametros invalidos'}), 400

    # Mapear filtro a status de BD
    status_param = None
    if status_filter == 'fire':
        status_param = 'Fuego detectado'
    elif status_filter == 'no_fire':
        status_param = 'Sin fuego'

    result = history.get_detections(
        page=page,
        per_page=per_page,
        status=status_param,
    )

    photos = []
    for det in result.get('detections', []):
        image_path = det.get('image_path', '')
        if not image_path:
            continue

        # Construir URL relativa al servidor
        # image_path puede ser: "screenshots/fire_xxx.jpg", "fire_xxx.jpg" o "mobile/mobile_xxx.jpg"
        # Normalizar: quitar prefijo 'screenshots/' si existe, luego siempre usar /screenshots/
        cleaned = image_path
        if cleaned.startswith('screenshots/'):
            cleaned = cleaned[len('screenshots/'):]
        url_path = f"/screenshots/{cleaned}"

        # Determinar origen
        source = 'mobile' if 'mobile' in image_path else 'webcam'

        confidence = det.get('confidence', 0.0)
        fire_detected = confidence >= 0.4 or det.get('status', '') == 'Fuego detectado'

        photos.append({
            'id': det.get('id', 0),
            'url': url_path,
            'thumbnail_url': url_path,  # mismo archivo, Flutter redimensiona
            'timestamp': det.get('timestamp', ''),
            'confidence': round(confidence, 3) if confidence <= 1.0 else round(confidence / 100, 3),
            'status': det.get('status', ''),
            'fire_detected': fire_detected,
            'source': source,
        })

    return jsonify({
        'success': True,
        'photos': photos,
        'total': result.get('total', 0),
        'page': page,
        'per_page': per_page,
        'pages': result.get('pages', 0),
    }), 200


@mobile_bp.route('/status', methods=['GET'])
def mobile_status():
    """
    Endpoint de health-check para que Flutter verifique
    que el servidor está disponible antes de enviar archivos
    """
    from services import container
    state = container.system_state
    return jsonify({
        'online': True,
        'monitoring': state.get('monitoring', False),
        'fire_detected': state.get('fire_detected', False),
        'timestamp': datetime.now().isoformat(),
    }), 200