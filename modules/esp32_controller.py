"""
Módulo de Control ESP32
FireWatch - esp32_controller.py
"""

import requests
import serial
import time
from modules.database_manager import DBManager


class ESP32Controller:
    """Controla el ESP32 para activar buzzer y LED"""

    def __init__(self):
        self.db = DBManager()
        self.serial_conn = None

    def _get_config(self):
        return {
            'ip': self.db.get_setting('esp32_ip', '192.168.0.18'),
            'port': self.db.get_setting('esp32_port', '80'),
            'mode': self.db.get_setting('esp32_mode', 'http'),
            'serial_port': self.db.get_setting('esp32_serial', 'COM3'),
        }

    def activate(self) -> bool:
        """Activa buzzer y LED en el ESP32"""
        cfg = self._get_config()
        try:
            if cfg['mode'] == 'http':
                return self._http_command(cfg, 'activate')
            elif cfg['mode'] == 'serial':
                return self._serial_command('FIRE_ALERT\n')
            elif cfg['mode'] == 'mqtt':
                return self._mqtt_command('activate')
        except Exception as e:
            print(f"[ESP32] Error al activar: {e}")
            return False
        return False

    def deactivate(self) -> bool:
        """Desactiva el ESP32"""
        cfg = self._get_config()
        try:
            if cfg['mode'] == 'http':
                return self._http_command(cfg, 'reset')
            elif cfg['mode'] == 'serial':
                return self._serial_command('RESET\n')
        except Exception as e:
            print(f"[ESP32] Error al desactivar: {e}")
            return False
        return False

    def test_connection(self) -> dict:
        """Prueba la conexión con el ESP32"""
        cfg = self._get_config()
        try:
            if cfg['mode'] == 'http':
                url = f"http://{cfg['ip']}:{cfg['port']}/ping"
                resp = requests.get(url, timeout=3)
                if resp.status_code == 200:
                    return {'success': True, 'message': f"ESP32 conectado en {cfg['ip']}"}
                return {'success': False, 'message': f"Error HTTP {resp.status_code}"}
            
            elif cfg['mode'] == 'serial':
                s = serial.Serial(cfg['serial_port'], 115200, timeout=2)
                s.write(b'PING\n')
                time.sleep(0.5)
                response = s.read_all().decode().strip()
                s.close()
                if response == 'PONG':
                    return {'success': True, 'message': f"ESP32 en {cfg['serial_port']}"}
                return {'success': False, 'message': 'No hay respuesta del ESP32'}
            
        except requests.exceptions.ConnectionError:
            return {'success': False, 'message': f"No se puede conectar a {cfg['ip']}"}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def _http_command(self, cfg: dict, action: str) -> bool:
        url = f"http://{cfg['ip']}:{cfg['port']}/{action}"
        resp = requests.post(url, timeout=3)
        return resp.status_code == 200

    def _serial_command(self, command: str) -> bool:
        cfg = self._get_config()
        try:
            if not self.serial_conn or not self.serial_conn.is_open:
                self.serial_conn = serial.Serial(cfg['serial_port'], 115200, timeout=2)
            self.serial_conn.write(command.encode())
            return True
        except Exception as e:
            print(f"[Serial] Error: {e}")
            return False

    def get_sensor_data(self) -> dict:
        """Obtiene datos de sensores del ESP32"""
        cfg = self._get_config()
        try:
            if cfg['mode'] == 'http':
                url = f"http://{cfg['ip']}:{cfg['port']}/sensors"
                resp = requests.get(url, timeout=3)
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        'success': True,
                        'temperature': data.get('temperature', 0),
                        'humidity': data.get('humidity', 0),
                        'mq2_value': data.get('mq2_value', 0),
                        'mq2_threshold': data.get('mq2_threshold', 2500),
                        'mq2_alarm': data.get('mq2_alarm', False)
                    }
                return {'success': False, 'message': f"Error HTTP {resp.status_code}"}
            
            elif cfg['mode'] == 'serial':
                # Implementar si es necesario
                return {'success': False, 'message': 'Modo serial no implementado para sensores'}
            
        except requests.exceptions.ConnectionError:
            return {'success': False, 'message': f"No se puede conectar a {cfg['ip']}"}
        except Exception as e:
            return {'success': False, 'message': str(e)}
