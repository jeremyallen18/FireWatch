"""
Módulo de Historial de Detecciones
FireWatch - history_manager.py
"""

import csv
import io
from datetime import datetime
from modules.database_manager import DBManager
from modules.report_generator import ReportGenerator


class HistoryManager:
    """Gestiona el historial de detecciones de fuego"""

    def __init__(self):
        self.db = DBManager()

    def save_detection(self, data: dict) -> int:
        """Guarda una detección y retorna su ID"""
        conn = self.db.get_conn()
        if not conn:
            return -1
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO firewatch_2.detections 
                (timestamp, confidence, image_path, video_path, status, alert_sent, esp32_triggered)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                data.get('timestamp', datetime.now().isoformat()),
                data.get('confidence', 0.0),
                data.get('image_path', ''),
                data.get('video_path', ''),
                data.get('status', 'Fuego detectado'),
                data.get('alert_sent', False),
                data.get('esp32_triggered', False),
            ))
            detection_id = cursor.lastrowid
            conn.commit()
            return detection_id
        except Exception as e:
            print(f"[History] Error al guardar: {e}")
            return -1
        finally:
            conn.close()

    def update_detection(self, detection_id: int, data: dict):
        """Actualiza campos de una detección existente"""
        conn = self.db.get_conn()
        if not conn:
            return
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE firewatch_2.detections SET alert_sent=%s, esp32_triggered=%s WHERE id=%s
            """, (data.get('alert_sent', False), data.get('esp32_triggered', False), detection_id))
            conn.commit()
        except Exception as e:
            print(f"[History] Error al actualizar: {e}")
        finally:
            conn.close()

    def get_detections(self, page=1, per_page=20, date_from=None, date_to=None,
                       min_confidence=None, status=None) -> dict:
        """Retorna detecciones paginadas con filtros opcionales"""
        conn = self.db.get_conn()
        if not conn:
            return self._demo_detections(page, per_page)

        try:
            cursor = conn.cursor(dictionary=True)
            conditions = []
            params = []

            if date_from:
                conditions.append("DATE(timestamp) >= %s")
                params.append(date_from)
            if date_to:
                conditions.append("DATE(timestamp) <= %s")
                params.append(date_to)
            if min_confidence is not None:
                conditions.append("confidence >= %s")
                params.append(min_confidence)
            if status:
                conditions.append("status = %s")
                params.append(status)

            where = "WHERE " + " AND ".join(conditions) if conditions else ""

            # Total
            cursor.execute(f"SELECT COUNT(*) as total FROM firewatch_2.detections {where}", params)
            total = cursor.fetchone()['total']

            # Paginado
            offset = (page - 1) * per_page
            cursor.execute(
                f"SELECT * FROM firewatch_2.detections {where} ORDER BY timestamp DESC LIMIT %s OFFSET %s",
                params + [per_page, offset]
            )
            rows = cursor.fetchall()

            # Serializar datetimes
            for row in rows:
                for k, v in row.items():
                    if isinstance(v, datetime):
                        row[k] = v.isoformat()

            return {
                'detections': rows,
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page
            }
        except Exception as e:
            print(f"[History] Error al obtener: {e}")
            return self._demo_detections(page, per_page)
        finally:
            conn.close()

    def get_detection_by_id(self, detection_id: int) -> dict:
        conn = self.db.get_conn()
        if not conn:
            return None
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM firewatch_2.detections WHERE id = %s", (detection_id,))
            row = cursor.fetchone()
            if row:
                for k, v in row.items():
                    if isinstance(v, datetime):
                        row[k] = v.isoformat()
            return row
        finally:
            conn.close()

    def get_stats(self) -> dict:
        conn = self.db.get_conn()
        if not conn:
            return {'total': 0, 'today': 0, 'avg_confidence': 0, 'alerts_sent': 0}
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(DATE(timestamp) = CURDATE()) as today,
                    AVG(confidence) as avg_confidence,
                    SUM(alert_sent) as alerts_sent
                FROM detections
            """)
            row = cursor.fetchone()
            if not row:
                return {'total': 0, 'today': 0, 'avg_confidence': 0, 'alerts_sent': 0}
            # Convertir a tipos nativos Python para JSON serialization
            return {
                'total': int(row.get('total') or 0),
                'today': int(row.get('today') or 0),
                'avg_confidence': float(row.get('avg_confidence') or 0),
                'alerts_sent': int(row.get('alerts_sent') or 0)
            }
        except Exception as e:
            print(f"[History] Stats error: {e}")
            return {'total': 0, 'today': 0, 'avg_confidence': 0, 'alerts_sent': 0}
        finally:
            conn.close()

    def export_csv(self) -> str:
        conn = self.db.get_conn()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Fecha/Hora', 'Confianza', 'Estado', 'Ruta Imagen',
                         'Email Enviado', 'ESP32 Activado'])

        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT id, timestamp, confidence, status, image_path, alert_sent, esp32_triggered FROM firewatch_2.detections ORDER BY timestamp DESC")
                for row in cursor.fetchall():
                    writer.writerow(row)
            finally:
                conn.close()
        else:
            # Demo data
            import random
            from datetime import timedelta
            for i in range(10):
                ts = datetime.now() - timedelta(hours=i*3)
                writer.writerow([i+1, ts, round(random.uniform(0.7, 0.98), 2),
                                  'Fuego detectado', f'screenshots/fire_{i}.jpg', True, True])

        return output.getvalue()

    def export_pdf(self) -> bytes:
        """
        Genera un reporte PDF profesional en memoria
        Utiliza ReportGenerator para manejar gráficos e imágenes
        """
        try:
            # Obtener datos de detecciones
            conn = self.db.get_conn()
            detections_data = []
            
            if conn:
                try:
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("""
                        SELECT id, timestamp, confidence, status, image_path, alert_sent, esp32_triggered 
                        FROM firewatch_2.detections ORDER BY timestamp DESC LIMIT 100
                    """)
                    detections_data = cursor.fetchall()
                finally:
                    conn.close()
            else:
                # Demo data si no hay BD
                import random
                from datetime import timedelta
                for i in range(20):
                    detections_data.append({
                        'id': i + 1,
                        'timestamp': (datetime.now() - timedelta(hours=i*2)).isoformat(),
                        'confidence': round(random.uniform(0.7, 0.98), 3),
                        'status': 'Fuego detectado',
                        'image_path': f'fire_{i}.jpg',
                        'alert_sent': random.choice([0, 1]),
                        'esp32_triggered': random.choice([0, 1]),
                    })
            
            # Obtener estadísticas
            stats = self.get_stats()
            
            # Usar generador de reportes
            generator = ReportGenerator(self.db)
            pdf_bytes = generator.generate_pdf(detections_data, stats)
            
            return pdf_bytes
            
        except Exception as e:
            print(f"[History] Error en export_pdf: {e}")
            raise

    def _demo_detections(self, page, per_page) -> dict:
        """Datos demo cuando no hay BD disponible"""
        import random
        from datetime import timedelta
        detections = []
        for i in range(per_page):
            idx = (page - 1) * per_page + i + 1
            ts = datetime.now() - timedelta(hours=idx * 2)
            detections.append({
                'id': idx,
                'timestamp': ts.isoformat(),
                'confidence': round(random.uniform(0.65, 0.98), 3),
                'status': 'Fuego detectado',
                'image_path': f'screenshots/fire_{idx:04d}.jpg',
                'alert_sent': random.choice([True, False]),
                'esp32_triggered': random.choice([True, False]),
            })
        return {
            'detections': detections,
            'total': 100,
            'page': page,
            'per_page': per_page,
            'pages': 5
        }
