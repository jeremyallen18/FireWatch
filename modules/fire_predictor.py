"""
Módulo de Predicción de Incendios
FireWatch - fire_predictor.py
"""

import numpy as np
from datetime import datetime
from typing import Dict, List
from modules.database_manager import DBManager


class FirePredictor:
    """
    Predictor de riesgo de incendio basado en datos de sensores.

    Umbrales sincronizados con el firmware ESP32 v2.1:
      - Temperatura warning : 30 °C  (TEMP_THRESHOLD del Arduino)
      - Temperatura crítica : 40 °C
      - MQ2 warning         : 1000   (MQ2_THRESHOLD del Arduino)
      - MQ2 crítico         : 2000
    """

    TEMP_WARNING      = 30.0
    TEMP_CRITICAL     = 40.0
    HUMIDITY_WARNING  = 35.0
    HUMIDITY_CRITICAL = 25.0
    MQ2_WARNING       = 1000
    MQ2_CRITICAL      = 2000

    WEIGHT_TEMP     = 0.30
    WEIGHT_HUMIDITY = 0.20
    WEIGHT_MQ2      = 0.35
    WEIGHT_TREND    = 0.15

    def __init__(self):
        self.db = DBManager()

    # ── Predicción principal ──────────────────────────────────────────

    def predict_fire_risk(self,
                          temperature: float = None,
                          humidity: float = None,
                          mq2_value: int = None,
                          hours_back: int = 24) -> Dict:
        if temperature is None or humidity is None or mq2_value is None:
            latest = self._get_latest_sensor_data()
            if latest:
                temperature = temperature or latest.get('temperature', 20)
                humidity    = humidity    or latest.get('humidity', 50)
                mq2_value   = mq2_value   or latest.get('mq2_value', 0)
            else:
                return self._default_prediction()

        historical = self._get_sensor_history(hours_back)

        temp_risk     = self._calculate_temperature_risk(temperature, historical)
        humidity_risk = self._calculate_humidity_risk(humidity, historical)
        mq2_risk      = self._calculate_mq2_risk(mq2_value, historical)
        trend_risk    = self._calculate_trend_risk(historical)

        total_risk = (
            self.WEIGHT_TEMP     * temp_risk     +
            self.WEIGHT_HUMIDITY * humidity_risk +
            self.WEIGHT_MQ2      * mq2_risk      +
            self.WEIGHT_TREND    * trend_risk
        )

        prediction_level  = self._classify_risk(total_risk)
        reasons           = self._generate_risk_reasons(
            temperature, humidity, mq2_value,
            temp_risk, humidity_risk, mq2_risk, trend_risk,
        )
        recommendations   = self._generate_recommendations(prediction_level, reasons)

        return {
            'prediction':      prediction_level,
            'risk_score':      round(total_risk, 2),
            'risk_percentage': round(total_risk, 1),
            'components': {
                'temperature_risk': round(temp_risk, 2),
                'humidity_risk':    round(humidity_risk, 2),
                'mq2_risk':         round(mq2_risk, 2),
                'trend_risk':       round(trend_risk, 2),
            },
            'current_values': {
                'temperature': temperature,
                'humidity':    humidity,
                'mq2_value':   mq2_value,
            },
            'reasons':         reasons,
            'recommendations': recommendations,
            'timestamp':       datetime.now().isoformat(),
        }

    # ── Predicción forzada desde alerta del ESP32 ─────────────────────

    def predict_from_esp32_alert(self,
                                 alert_type: str,
                                 mq2_value: int,
                                 temperature: float,
                                 humidity: float) -> Dict:
        """
        Eleva el nivel de riesgo al mínimo que corresponde al tipo de alarma
        que el hardware ya disparó, sin subrepresentar en el dashboard lo que
        el ESP32 consideró peligroso.
          - MQ2_HIGH  → CRITICAL (≥ 80 %)
          - TEMP_HIGH → HIGH     (≥ 65 %)
        """
        base = self.predict_fire_risk(temperature, humidity, mq2_value)

        if alert_type == 'MQ2_HIGH':
            base['prediction']      = 'CRITICAL'
            base['risk_percentage'] = max(base['risk_percentage'], 80.0)
            base['risk_score']      = max(base['risk_score'],      80.0)
            base['reasons'].insert(0, '🔴 Alarma MQ2 activada en ESP32')
        elif alert_type == 'TEMP_HIGH':
            base['prediction']      = 'HIGH'
            base['risk_percentage'] = max(base['risk_percentage'], 65.0)
            base['risk_score']      = max(base['risk_score'],      65.0)
            base['reasons'].insert(0, '🟠 Alarma de temperatura activada en ESP32')

        return base

    # ── Acceso a base de datos ────────────────────────────────────────

    def _get_latest_sensor_data(self) -> Dict:
        conn = self.db.get_conn()
        if not conn:
            return None
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT temperature, humidity, mq2_value, timestamp
                FROM sensor_data
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                return {
                    'temperature': float(row['temperature'] or 20),
                    'humidity':    float(row['humidity']    or 50),
                    'mq2_value':   int(row['mq2_value']     or 0),
                    'timestamp':   row['timestamp'],
                }
        except Exception as e:
            print(f"[FirePredictor] Error obteniendo datos: {e}")
        finally:
            conn.close()
        return None

    def _get_sensor_history(self, hours: int = 24) -> List[Dict]:
        conn = self.db.get_conn()
        if not conn:
            return []
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT timestamp, temperature, humidity, mq2_value
                FROM sensor_data
                WHERE timestamp >= DATE_SUB(NOW(), INTERVAL %s HOUR)
                ORDER BY timestamp ASC
            """, (int(hours),))
            return [
                {
                    'timestamp':   row['timestamp'],
                    'temperature': float(row['temperature'] or 20),
                    'humidity':    float(row['humidity']    or 50),
                    'mq2_value':   int(row['mq2_value']     or 0),
                }
                for row in cursor.fetchall()
            ]
        except Exception as e:
            print(f"[FirePredictor] Error obteniendo historial: {e}")
            return []
        finally:
            conn.close()

    # ── Cálculo de componentes de riesgo ─────────────────────────────

    def _calculate_temperature_risk(self, temp: float, historical: List) -> float:
        if temp >= self.TEMP_CRITICAL:
            risk = 100.0
        elif temp >= self.TEMP_WARNING:             # 30–40 → 50–100
            risk = 50.0 + (temp - self.TEMP_WARNING) * 5.0
        elif temp >= 25:                            # 25–30 → 25–50
            risk = 25.0 + (temp - 25) * 5.0
        elif temp >= 20:
            risk = 10.0
        else:
            risk = 5.0

        if len(historical) >= 2:
            recent     = historical[-5:] if len(historical) >= 5 else historical
            avg_recent = np.mean([d['temperature'] for d in recent])
            if avg_recent - historical[0]['temperature'] > 5:
                risk = min(100.0, risk * 1.3)

        return min(100.0, risk)

    def _calculate_humidity_risk(self, humidity: float, historical: List) -> float:
        if humidity <= self.HUMIDITY_CRITICAL:
            risk = 100.0
        elif humidity <= self.HUMIDITY_WARNING:
            risk = 50.0 + (self.HUMIDITY_WARNING - humidity) * 2
        elif humidity <= 40:
            risk = 25.0 + (40 - humidity) * 1
        elif humidity <= 60:
            risk = 10.0
        else:
            risk = 5.0

        if len(historical) >= 2:
            recent     = historical[-5:] if len(historical) >= 5 else historical
            avg_recent = np.mean([d['humidity'] for d in recent])
            if historical[0]['humidity'] - avg_recent > 15:
                risk = min(100.0, risk * 1.2)

        return min(100.0, risk)

    def _calculate_mq2_risk(self, mq2: int, historical: List) -> float:
        if mq2 >= self.MQ2_CRITICAL:
            risk = 100.0
        elif mq2 >= self.MQ2_WARNING:               # 1000–2000 → 50–100
            risk = 50.0 + (mq2 - self.MQ2_WARNING) * 0.05
        elif mq2 >= 500:
            risk = 15.0 + (mq2 - 500) * 0.07
        else:
            risk = (mq2 / 4095.0) * 100 * 0.3

        if len(historical) >= 2:
            recent     = historical[-5:] if len(historical) >= 5 else historical
            avg_recent = np.mean([d['mq2_value'] for d in recent])
            if avg_recent - historical[0]['mq2_value'] > 500:
                risk = min(100.0, risk * 1.4)

        return min(100.0, risk)

    def _calculate_trend_risk(self, historical: List) -> float:
        """Analiza volatilidad y velocidad de cambio en los últimos registros."""
        if len(historical) < 3:
            return 0.0

        trend_risk = 0.0
        temps    = [d['temperature'] for d in historical]
        mq2_vals = [d['mq2_value']   for d in historical]

        if np.std(temps) > 8:
            trend_risk += 20
        if np.std(mq2_vals) > 800:
            trend_risk += 30

        recent = historical[-3:]
        if abs(recent[-1]['temperature'] - recent[0]['temperature']) > 6:
            trend_risk += 20
        if abs(recent[-1]['mq2_value'] - recent[0]['mq2_value']) > 1000:
            trend_risk += 25

        return min(100.0, trend_risk)

    # ── Clasificación y mensajes ──────────────────────────────────────

    def _classify_risk(self, risk_score: float) -> str:
        if risk_score >= 80:   return 'CRITICAL'
        if risk_score >= 60:   return 'HIGH'
        if risk_score >= 40:   return 'MEDIUM'
        if risk_score >= 20:   return 'LOW'
        return 'MINIMAL'

    def _generate_risk_reasons(self, temp, humidity, mq2,
                                temp_risk, humidity_risk, mq2_risk, trend_risk) -> List[str]:
        reasons = []

        if temp >= self.TEMP_CRITICAL:
            reasons.append(f"🔴 Temperatura crítica: {temp}°C (límite: {self.TEMP_CRITICAL}°C)")
        elif temp >= self.TEMP_WARNING:
            reasons.append(f"🟡 Temperatura alta: {temp}°C (advertencia en {self.TEMP_WARNING}°C)")

        if humidity <= self.HUMIDITY_CRITICAL:
            reasons.append(f"🔴 Humedad crítica: {humidity}% (material muy seco)")
        elif humidity <= self.HUMIDITY_WARNING:
            reasons.append(f"🟡 Humedad baja: {humidity}% (riesgo de sequedad)")

        if mq2 >= self.MQ2_CRITICAL:
            reasons.append(f"🔴 Gases/humo crítico: {mq2} ppm (límite: {self.MQ2_CRITICAL})")
        elif mq2 >= self.MQ2_WARNING:
            reasons.append(f"🟡 Gases/humo elevado: {mq2} ppm (advertencia en {self.MQ2_WARNING})")

        if trend_risk > 40:
            reasons.append("⚠️ Cambios rápidos detectados en los sensores")

        if not reasons:
            reasons.append("✅ Condiciones normales")

        return reasons

    def _generate_recommendations(self, level: str, reasons: List[str]) -> List[str]:
        if level == 'CRITICAL':
            return [
                "🚨 ESTADO CRÍTICO - Verificar inmediatamente",
                "✓ Contactar a autoridades si hay humo visible",
                "✓ Preparar equipo de extinción",
                "✓ Evacuar si hay peligro inminente",
            ]
        if level == 'HIGH':
            return [
                "⚠️ Alertar a operadores del sistema",
                "✓ Mantener vigilancia cercana",
                "✓ Aumentar frecuencia de chequeos",
                "✓ Preparar sistema de extinción automático",
            ]
        if level == 'MEDIUM':
            return [
                "📋 Monitoreo normalizado",
                "✓ Continuar vigilancia regular",
                "✓ Revisar áreas de riesgo",
                "✓ Mantener sistemas de emergencia listos",
            ]
        return [
            "✅ Situación bajo control",
            "✓ Continuar monitoreo estándar",
            "✓ Mantener sistemas operacionales",
        ]

    def _default_prediction(self) -> Dict:
        return {
            'prediction':      'UNKNOWN',
            'risk_score':      0.0,
            'risk_percentage': 0.0,
            'components': {
                'temperature_risk': 0.0,
                'humidity_risk':    0.0,
                'mq2_risk':         0.0,
                'trend_risk':       0.0,
            },
            'current_values': {
                'temperature': None,
                'humidity':    None,
                'mq2_value':   None,
            },
            'reasons':         ['No hay datos de sensores disponibles'],
            'recommendations': ['Verificar conexión con sensores ESP32'],
            'timestamp':       datetime.now().isoformat(),
        }

    # ── Persistencia ──────────────────────────────────────────────────

    def save_sensor_data(self, temperature: float, humidity: float,
                         mq2_value: int, **kwargs) -> int:
        conn = self.db.get_conn()
        if not conn:
            return None
        try:
            prediction_data = self.predict_fire_risk(temperature, humidity, mq2_value)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sensor_data
                (temperature, humidity, mq2_value, fire_risk_score, prediction,
                 pressure, co_level, smoke_level, location, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                temperature,
                humidity,
                mq2_value,
                prediction_data['risk_score'],
                prediction_data['prediction'],
                kwargs.get('pressure'),
                kwargs.get('co_level'),
                kwargs.get('smoke_level'),
                kwargs.get('location', 'Default'),
                kwargs.get('notes', ''),
            ))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"[FirePredictor] Error guardando datos: {e}")
            return None
        finally:
            conn.close()

    def get_statistics(self, days: int = 7) -> List:
        conn = self.db.get_conn()
        if not conn:
            return []
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT
                    DATE(timestamp)                                              AS fecha,
                    COUNT(*)                                                     AS lecturas,
                    AVG(temperature)                                             AS temp_promedio,
                    MAX(temperature)                                             AS temp_maxima,
                    MIN(temperature)                                             AS temp_minima,
                    AVG(humidity)                                                AS humedad_promedio,
                    AVG(mq2_value)                                               AS mq2_promedio,
                    MAX(fire_risk_score)                                         AS riesgo_maximo,
                    SUM(CASE WHEN prediction = 'CRITICAL' THEN 1 ELSE 0 END)    AS alertas_criticas,
                    SUM(CASE WHEN prediction = 'HIGH'     THEN 1 ELSE 0 END)    AS alertas_altas
                FROM sensor_data
                WHERE timestamp >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY DATE(timestamp)
                ORDER BY fecha DESC
            """, (int(days),))
            return [
                {
                    'fecha':            str(row['fecha']),
                    'lecturas':         row['lecturas'],
                    'temp_promedio':    round(float(row['temp_promedio']    or 0), 2),
                    'temp_maxima':      round(float(row['temp_maxima']      or 0), 2),
                    'temp_minima':      round(float(row['temp_minima']      or 0), 2),
                    'humedad_promedio': round(float(row['humedad_promedio'] or 0), 2),
                    'mq2_promedio':     round(float(row['mq2_promedio']     or 0), 2),
                    'riesgo_maximo':    round(float(row['riesgo_maximo']    or 0), 2),
                    'alertas_criticas': int(row['alertas_criticas']         or 0),
                    'alertas_altas':    int(row['alertas_altas']            or 0),
                }
                for row in cursor.fetchall()
            ]
        except Exception as e:
            print(f"[FirePredictor] Error obteniendo estadísticas: {e}")
            return []
        finally:
            conn.close()