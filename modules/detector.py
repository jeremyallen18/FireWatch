"""
Módulo de Detección de Fuego con YOLO
FireWatch - detector.py
"""

import cv2
import numpy as np
import os
import time


class ScreenFilter:
    """
    Filtro multi-señal para detectar pantallas (TV, teléfono, monitor) y evitar
    falsas alarmas por fuego mostrado en ellas.

    Combina tres señales independientes:
      1. Detección de rectángulos con bordes rectos (Canny + approxPolyDP)
      2. Análisis de uniformidad de borde/bisel alrededor del rectángulo
      3. Análisis de textura dentro de la detección de fuego (fuego real es
         orgánico e irregular; en pantalla es más suave y con gradientes uniformes)

    Cada señal aporta un puntaje parcial.  El puntaje total determina cuánto se
    penaliza la confianza del detector de fuego.
    """

    # ── Umbrales configurables ──────────────────────────────────────────
    RECT_MIN_AREA_RATIO = 0.01   # Mínimo 1% del frame para ser pantalla
    RECT_MAX_AREA_RATIO = 0.85   # Máximo 85%
    RECT_ASPECT_MIN = 0.3        # Aspect ratio mínimo (vertical phone)
    RECT_ASPECT_MAX = 3.0        # Aspect ratio máximo (ultrawide)
    RECT_APPROX_VERTICES = (4, 6)  # Vértices esperados de un rectángulo
    RECT_SOLIDITY_MIN = 0.80     # Solidity mínima (area / convex hull area)

    BEZEL_BAND_PX = 12           # Píxeles hacia afuera para buscar bisel
    BEZEL_STD_MAX = 35.0         # Desviación estándar máxima del bisel

    TEXTURE_LAPLACIAN_THRESH = 18.0  # Varianza Laplaciana baja → pantalla
    TEXTURE_BLOCK_SIZE = 16

    # Pesos de cada señal para el puntaje total (suman 1.0)
    W_RECT = 0.45
    W_BEZEL = 0.25
    W_TEXTURE = 0.30

    # Si el puntaje total supera este umbral, la detección se considera en pantalla
    SCREEN_SCORE_THRESHOLD = 0.45

    def __init__(self):
        self.enabled = True

    # ── API pública ─────────────────────────────────────────────────────

    def detect_screens(self, frame: np.ndarray) -> list:
        """
        Detecta rectángulos candidatos a pantalla en el frame.
        Retorna lista de bounding boxes [(x1,y1,x2,y2), ...] de pantallas.
        """
        if not self.enabled:
            return []

        try:
            return self._find_screen_rects(frame)
        except Exception as e:
            print(f"[ScreenFilter] Error detectando pantallas: {e}")
            return []

    def score_detection_on_screen(
        self,
        frame: np.ndarray,
        fire_box: tuple,
        screen_rects: list,
    ) -> float:
        """
        Calcula un puntaje (0.0–1.0) de cuán probable es que la detección
        de fuego en `fire_box` provenga de una pantalla.

        Args:
            frame: frame BGR completo
            fire_box: (x1, y1, x2, y2) de la detección de fuego
            screen_rects: lista de (x1,y1,x2,y2) de pantallas detectadas

        Returns:
            Puntaje 0.0 (fuego real) a 1.0 (fuego en pantalla).
        """
        if not self.enabled or not screen_rects:
            return 0.0

        fx1, fy1, fx2, fy2 = fire_box

        best_score = 0.0
        for sx1, sy1, sx2, sy2 in screen_rects:
            # ── Señal 1: Cobertura geométrica ──────────────────────────
            overlap = self._iou_containment(fire_box, (sx1, sy1, sx2, sy2))
            rect_score = min(overlap / 0.6, 1.0)  # 60%+ cobertura → score 1.0

            # ── Señal 2: Uniformidad de bisel ──────────────────────────
            bezel_score = self._bezel_uniformity(frame, (sx1, sy1, sx2, sy2))

            # ── Señal 3: Textura del fuego (suave → pantalla) ─────────
            texture_score = self._texture_smoothness(frame, fire_box)

            total = (
                self.W_RECT * rect_score
                + self.W_BEZEL * bezel_score
                + self.W_TEXTURE * texture_score
            )
            best_score = max(best_score, total)

        return round(best_score, 3)

    def visualize_screens(self, frame: np.ndarray, screen_rects: list) -> np.ndarray:
        """Dibuja las pantallas detectadas para debugging."""
        result = frame.copy()
        for (x1, y1, x2, y2) in screen_rects:
            cv2.rectangle(result, (x1, y1), (x2, y2), (255, 0, 0), 2)
            cv2.putText(result, "PANTALLA", (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        return result

    # ── Detección de rectángulos de pantalla ────────────────────────────

    def _find_screen_rects(self, frame: np.ndarray) -> list:
        """Encuentra rectángulos que parecen pantallas usando detección de bordes."""
        h, w = frame.shape[:2]
        frame_area = h * w
        min_area = frame_area * self.RECT_MIN_AREA_RATIO
        max_area = frame_area * self.RECT_MAX_AREA_RATIO

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Blur para reducir ruido antes de Canny
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Canny con umbral adaptativo basado en la mediana
        median_val = np.median(blurred)
        low_thresh = int(max(0, 0.5 * median_val))
        high_thresh = int(min(255, 1.3 * median_val))
        edges = cv2.Canny(blurred, low_thresh, high_thresh)

        # Cerrar gaps en los bordes
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        edges = cv2.dilate(edges, kernel, iterations=2)
        edges = cv2.erode(edges, kernel, iterations=1)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        rects = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if not (min_area < area < max_area):
                continue

            # Aproximar polígono — pantallas son ~4 lados
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.03 * peri, True)
            n_vertices = len(approx)

            if not (self.RECT_APPROX_VERTICES[0] <= n_vertices <= self.RECT_APPROX_VERTICES[1]):
                continue

            # Solidez: area real vs convex hull
            hull_area = cv2.contourArea(cv2.convexHull(contour))
            solidity = area / hull_area if hull_area > 0 else 0
            if solidity < self.RECT_SOLIDITY_MIN:
                continue

            # Aspect ratio del bounding rect
            x, y, rw, rh = cv2.boundingRect(approx)
            aspect = rw / rh if rh > 0 else 0
            if not (self.RECT_ASPECT_MIN < aspect < self.RECT_ASPECT_MAX):
                continue

            rects.append((x, y, x + rw, y + rh))

        # Eliminar rectángulos duplicados/muy superpuestos
        return self._nms_rects(rects, iou_thresh=0.5)

    # ── Señal: uniformidad de bisel ─────────────────────────────────────

    def _bezel_uniformity(self, frame: np.ndarray, screen_rect: tuple) -> float:
        """
        Mide cuán uniforme es la banda justo afuera del rectángulo.
        Pantallas reales tienen marco/bisel de color uniforme.
        Retorna 0.0 (no uniforme) a 1.0 (muy uniforme = probable pantalla).
        """
        h, w = frame.shape[:2]
        sx1, sy1, sx2, sy2 = screen_rect
        band = self.BEZEL_BAND_PX

        # Expandir rect para obtener banda exterior
        ox1 = max(0, sx1 - band)
        oy1 = max(0, sy1 - band)
        ox2 = min(w, sx2 + band)
        oy2 = min(h, sy2 + band)

        # Crear máscara de la banda (exterior - interior)
        outer_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.rectangle(outer_mask, (ox1, oy1), (ox2, oy2), 255, -1)
        cv2.rectangle(outer_mask, (sx1, sy1), (sx2, sy2), 0, -1)

        # Extraer píxeles de la banda
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        band_pixels = gray[outer_mask > 0]

        if len(band_pixels) < 20:
            return 0.0

        std = np.std(band_pixels.astype(np.float32))
        # Menor desviación → más uniforme → mayor score
        score = max(0.0, 1.0 - std / self.BEZEL_STD_MAX)
        return score

    # ── Señal: suavidad de textura del fuego ────────────────────────────

    def _texture_smoothness(self, frame: np.ndarray, fire_box: tuple) -> float:
        """
        Analiza la textura dentro de la bounding box de fuego.
        Fuego real tiene alta varianza en Laplaciano (bordes orgánicos).
        Fuego en pantalla tiende a ser más suave (menor varianza).
        Retorna 0.0 (textura orgánica = fuego real) a 1.0 (suave = pantalla).
        """
        h, w = frame.shape[:2]
        fx1, fy1, fx2, fy2 = (
            max(0, fire_box[0]), max(0, fire_box[1]),
            min(w, fire_box[2]), min(h, fire_box[3]),
        )

        roi = frame[fy1:fy2, fx1:fx2]
        if roi.size == 0 or roi.shape[0] < 8 or roi.shape[1] < 8:
            return 0.0

        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        laplacian = cv2.Laplacian(gray_roi, cv2.CV_64F)
        variance = laplacian.var()

        # Baja varianza → suave → probable pantalla
        if variance < self.TEXTURE_LAPLACIAN_THRESH:
            return 1.0
        elif variance < self.TEXTURE_LAPLACIAN_THRESH * 3:
            # Transición gradual
            return max(0.0, 1.0 - (variance - self.TEXTURE_LAPLACIAN_THRESH) /
                        (self.TEXTURE_LAPLACIAN_THRESH * 2))
        return 0.0

    # ── Utilidades ──────────────────────────────────────────────────────

    @staticmethod
    def _iou_containment(box_a: tuple, box_b: tuple) -> float:
        """
        Calcula qué fracción de box_a está contenida dentro de box_b.
        (No es IoU simétrico — es containment de A en B.)
        """
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b

        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)

        if ix1 >= ix2 or iy1 >= iy2:
            return 0.0

        inter_area = (ix2 - ix1) * (iy2 - iy1)
        a_area = (ax2 - ax1) * (ay2 - ay1)
        return inter_area / a_area if a_area > 0 else 0.0

    @staticmethod
    def _nms_rects(rects: list, iou_thresh: float = 0.5) -> list:
        """Non-maximum suppression simple para rectángulos."""
        if not rects:
            return []

        # Ordenar por área descendente
        rects = sorted(rects, key=lambda r: (r[2]-r[0])*(r[3]-r[1]), reverse=True)
        keep = []

        for rect in rects:
            discard = False
            for kept in keep:
                # Calcular IoU estándar
                ix1 = max(rect[0], kept[0])
                iy1 = max(rect[1], kept[1])
                ix2 = min(rect[2], kept[2])
                iy2 = min(rect[3], kept[3])
                if ix1 < ix2 and iy1 < iy2:
                    inter = (ix2-ix1) * (iy2-iy1)
                    area_a = (rect[2]-rect[0]) * (rect[3]-rect[1])
                    area_b = (kept[2]-kept[0]) * (kept[3]-kept[1])
                    iou = inter / (area_a + area_b - inter)
                    if iou > iou_thresh:
                        discard = True
                        break
            if not discard:
                keep.append(rect)

        return keep


class FireDetector:
    """
    Módulo de detección de fuego usando YOLO.
    Si el modelo no está disponible, opera en modo simulación para desarrollo.
    """

    def __init__(self):
        self.model = None
        self.model_path = None
        self.simulation_mode = False
        self.model_loaded = False  # Bandera para carga lazy
        self.model_path_config = None
        self.screen_filter = ScreenFilter()  # Agregar filtro de pantallas
        self._init_model_path()

    def _init_model_path(self):
        """Inicializa la ruta del modelo sin cargarlo"""
        try:
            from config.settings import Config
            self.model_path_config = Config.MODEL_PATH
        except Exception:
            self.model_path_config = 'models/best.pt'

        if not os.path.isabs(self.model_path_config):
            self.model_path_config = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 
                self.model_path_config
            )

    def _ensure_model_loaded(self):
        """Carga el modelo la primera vez que se necesita (lazy loading)"""
        if self.model_loaded:
            return

        self.model_loaded = True
        self._load_model()

    def _load_model(self):
        """Intenta cargar el modelo YOLO"""
        model_path = self.model_path_config

        if os.path.exists(model_path):
            try:
                import torch
                from ultralytics import YOLO

                # Registrar clases faltantes como placeholders antes de no descargar
                try:
                    from ultralytics.utils import loss
                    # Crear stubs para clases que podrían estar en old checkpoints
                    if not hasattr(loss, 'DFLoss'):
                        loss.DFLoss = type('DFLoss', (object,), {})
                    if not hasattr(loss, 'BboxLoss'):
                        loss.BboxLoss = type('BboxLoss', (object,), {})
                    if not hasattr(loss, 'ClsLoss'):
                        loss.ClsLoss = type('ClsLoss', (object,), {})
                except (ImportError, AttributeError):
                    pass

                # Permitir weights_only=False
                original_load = torch.load
                def patched_load(f, *args, **kwargs):
                    if 'weights_only' not in kwargs:
                        kwargs['weights_only'] = False
                    return original_load(f, *args, **kwargs)
                
                torch.load = patched_load
                try:
                    self.model = YOLO(model_path)
                    self.model_path = model_path
                    print(f"[YOLO] Modelo cargado: {model_path}")
                finally:
                    torch.load = original_load

            except ImportError:
                print("[YOLO] ultralytics no instalado, modo simulación activado")
                self.simulation_mode = True

            except Exception as e:
                print(f"[YOLO] Error al cargar modelo: {e} — modo simulación activado")
                self.simulation_mode = True
        else:
            print(f"[YOLO] Modelo no encontrado en {model_path} — modo simulación activado")
            self.simulation_mode = True

    def reload_model(self, path: str) -> dict:
        """Recarga el modelo desde una nueva ruta"""
        if os.path.exists(path):
            try:
                from ultralytics import YOLO
                self.model = YOLO(path)
                self.model_path = path
                self.simulation_mode = False
                self.model_loaded = True
                return {'success': True, 'message': f'Modelo cargado: {path}'}
            except Exception as e:
                return {'success': False, 'message': str(e)}
        return {'success': False, 'message': 'Ruta no encontrada'}

    def detect(self, frame: np.ndarray, threshold: float = 0.5) -> dict:
        """
        Ejecuta inferencia sobre un frame con filtro de pantallas multi-señal.
        Retorna: frame anotado, fire_detected (bool), confidence (float)
        """
        self._ensure_model_loaded()

        if self.simulation_mode:
            return self._simulate(frame)

        try:
            # 1. Detectar rectángulos de pantalla en el frame
            screen_rects = self.screen_filter.detect_screens(frame)

            # 2. Ejecutar YOLO
            results = self.model(frame, conf=threshold, verbose=False)
            annotated = results[0].plot()

            fire_detected = False
            max_conf = 0.0
            boxes_count = 0

            # 3. Evaluar cada detección contra las pantallas
            for box in results[0].boxes:
                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0]
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

                # Calcular puntaje de "fuego en pantalla"
                screen_score = self.screen_filter.score_detection_on_screen(
                    frame, (x1, y1, x2, y2), screen_rects
                )

                # Penalizar confianza proporcionalmente al puntaje
                if screen_score >= ScreenFilter.SCREEN_SCORE_THRESHOLD:
                    # Penalización fuerte: a score 1.0 la confianza cae a 0
                    adjusted_conf = conf * (1.0 - screen_score)
                else:
                    adjusted_conf = conf

                if adjusted_conf >= threshold:
                    fire_detected = True
                    max_conf = max(max_conf, adjusted_conf)
                    boxes_count += 1
                elif screen_score >= ScreenFilter.SCREEN_SCORE_THRESHOLD:
                    # Anotar visualmente que se filtró como pantalla
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 0, 0), 2)
                    cv2.putText(
                        annotated,
                        f"PANTALLA ({screen_score:.0%})",
                        (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2,
                    )

            return {
                'frame': annotated,
                'fire_detected': fire_detected,
                'confidence': round(max_conf, 3),
                'boxes': boxes_count,
                'screens_detected': len(screen_rects) > 0,
                'screen_rects': len(screen_rects),
            }

        except Exception as e:
            print(f"[YOLO] Error en inferencia: {e}")
            return self._no_detection(frame)

    def _simulate(self, frame: np.ndarray) -> dict:
        """Simulación para entorno de desarrollo sin modelo"""
        # Simula una detección ocasional (1 vez cada ~5 segundos a 30fps)
        fire_detected = (int(time.time()) % 15 == 0)
        confidence = np.random.uniform(0.75, 0.95) if fire_detected else 0.0

        annotated = frame.copy()

        if fire_detected:
            h, w = frame.shape[:2]
            x1, y1 = int(w * 0.2), int(h * 0.2)
            x2, y2 = int(w * 0.7), int(h * 0.75)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 60, 255), 3)
            label = f"Fuego {confidence:.0%}"
            cv2.putText(annotated, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 60, 255), 2)
            
            # Overlay semitransparente
            overlay = annotated.copy()
            cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 60, 255), -1)
            cv2.addWeighted(overlay, 0.15, annotated, 0.85, 0, annotated)

        # Watermark de simulación
        cv2.putText(annotated, "SIMULACION", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)

        return {
            'frame': annotated,
            'fire_detected': fire_detected,
            'confidence': round(confidence, 3),
            'boxes': 1 if fire_detected else 0
        }

    def _no_detection(self, frame: np.ndarray) -> dict:
        return {
            'frame': frame,
            'fire_detected': False,
            'confidence': 0.0,
            'boxes': 0,
            'screens_detected': False
        }
    
    def set_screen_filter(self, enabled: bool) -> dict:
        """
        Activa o desactiva el filtro de pantallas.
        """
        self.screen_filter.enabled = enabled
        return {
            'success': True,
            'message': f"Filtro de pantallas {'activado' if enabled else 'desactivado'}",
        }

    def get_screen_filter_status(self) -> dict:
        """Retorna estado del filtro de pantallas"""
        return {
            'enabled': self.screen_filter.enabled,
            'score_threshold': ScreenFilter.SCREEN_SCORE_THRESHOLD,
        }

    def get_model_info(self) -> dict:
        return {
            'simulation_mode': self.simulation_mode,
            'model_path': self.model_path,
            'loaded': self.model is not None
        }