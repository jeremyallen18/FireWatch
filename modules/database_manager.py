"""
Módulo de Gestión de Base de Datos MySQL
FireWatch - database_manager.py
"""

import mysql.connector
from datetime import datetime
import re


class DBManager:
    """CRUD para MySQL - detecciones, alertas, configuración, usuarios"""

    def __init__(self):
        self._config = None
        self._last_error = None
    
    @staticmethod
    def validate_email(email: str) -> tuple:
        """Valida formato de email - retorna (is_valid, error_msg)"""
        if not email or not isinstance(email, str):
            return False, 'Email no puede estar vacío'
        
        email = email.strip()
        if len(email) > 255:
            return False, 'Email no puede exceder 255 caracteres'
        
        # Validación adicional: no permitir puntos consecutivos
        if '..' in email:
            return False, 'Email no puede contener puntos consecutivos'
        
        # Regex mejorado para emails - RFC 5322 simplificado
        email_pattern = r'^[a-zA-Z0-9][a-zA-Z0-9._%+-]*[a-zA-Z0-9]@[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]\.[a-zA-Z]{2,}$|^[a-zA-Z0-9]+@[a-zA-Z0-9]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return False, 'Formato de email inválido. Ejemplo: usuario@dominio.com'
        
        return True, None
    
    @staticmethod
    def validate_name(name: str) -> tuple:
        """Valida nombre de destinatario"""
        if name and len(str(name).strip()) > 100:
            return False, 'Nombre no puede exceder 100 caracteres'
        return True, None

    def _load_config(self):
        """Carga config desde archivo de entorno o settings"""
        from config.settings import Config
        return {
            'host': Config.DB_HOST,
            'port': Config.DB_PORT,
            'user': Config.DB_USER,
            'password': Config.DB_PASSWORD,
            'database': Config.DB_NAME,
        }

    def get_conn(self):
        """Retorna una conexión a MySQL o None si falla"""
        try:
            cfg = self._load_config()
            conn = mysql.connector.connect(**cfg, autocommit=True)
            self._last_error = None
            return conn
        except Exception as e:
            self._last_error = str(e)
            print(f"[DB] Sin conexión: {self._last_error}")
            return None

    def init_db(self):
        """Crea las tablas si no existen"""
        conn = self.get_conn()
        if not conn:
            print("[DB] No se pudo inicializar la BD — modo sin BD activo")
            return
        
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detections (
                id INT AUTO_INCREMENT PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                confidence FLOAT,
                image_path VARCHAR(500),
                video_path VARCHAR(500),
                status VARCHAR(100),
                alert_sent BOOLEAN DEFAULT FALSE,
                esp32_triggered BOOLEAN DEFAULT FALSE
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                detection_id INT,
                email_sent BOOLEAN DEFAULT FALSE,
                esp32_sent BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                response_status VARCHAR(100),
                FOREIGN KEY (detection_id) REFERENCES detections(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                setting_key VARCHAR(100) UNIQUE,
                setting_value TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE,
                password_hash VARCHAR(255),
                role VARCHAR(50) DEFAULT 'operator',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipients (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(100) NOT NULL UNIQUE,
                name VARCHAR(100),
                is_active BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_email (email),
                INDEX idx_active (is_active)
            )
        """)
        
        conn.commit()
        conn.close()
        print("[DB] Tablas inicializadas correctamente")

    def get_setting(self, key: str, default: str = '') -> str:
        """Obtiene un valor de configuración"""
        conn = self.get_conn()
        if not conn:
            return default
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT setting_value FROM firewatch_2.settings WHERE setting_key = %s", (key,))
            row = cursor.fetchone()
            return row[0] if row else default
        except mysql.connector.Error as e:
            print(f"[DB] Error en get_setting: {e}")
            return default
        finally:
            conn.close()

    def save_setting(self, key: str, value: str):
        """Guarda o actualiza una configuración"""
        conn = self.get_conn()
        if not conn:
            return
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO firewatch_2.settings (setting_key, setting_value) VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
            """, (key, str(value)))
            conn.commit()
        finally:
            conn.close()

    def get_all_settings(self) -> dict:
        """Retorna todas las configuraciones como diccionario"""
        conn = self.get_conn()
        if not conn:
            return self._default_settings()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT setting_key, setting_value FROM firewatch_2.settings")
            result = dict(cursor.fetchall())
            # Rellenar defaults si faltan
            defaults = self._default_settings()
            defaults.update(result)
            return defaults
        except mysql.connector.Error as e:
            print(f"[DB] Error en get_all_settings: {e}")
            return self._default_settings()
        finally:
            conn.close()

    def test_connection(self) -> dict:
        conn = self.get_conn()
        if conn:
            conn.close()
            return {'success': True, 'message': 'Conexión exitosa a MySQL'}
        return {
            'success': False,
            'message': 'No se pudo conectar a MySQL',
            'error': self._last_error or 'Error desconocido'
        }

    def _default_settings(self) -> dict:
        return {
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': '587',
            'email_sender': '',
            'email_recipient': '',
            'email_password': '',
            'esp32_ip': '192.168.1.100',
            'esp32_port': '80',
            'esp32_mode': 'http',
            'esp32_serial': 'COM3',
            'detection_threshold': '0.5',
            'alert_cooldown': '30',
            'camera_source': '0',
            'model_path': 'models/best.pt',
            'db_host': 'localhost',
            'db_port': '3306',
            'db_user': '',
            'db_password': '',
            'db_name': 'firewatch_2',
        }

    # ────── CRUD PARA DESTINATARIOS DE ALERTAS ──────── 
    def add_recipient(self, email: str, name: str = '') -> dict:
        """Agrega un nuevo destinatario de alertas"""
        # Validar email
        is_valid, error_msg = self.validate_email(email)
        if not is_valid:
            return {'success': False, 'message': error_msg}
        
        email = email.strip()
        
        # Validar nombre
        is_valid, error_msg = self.validate_name(name)
        if not is_valid:
            return {'success': False, 'message': error_msg}
        
        name = (name or email.split('@')[0]).strip()
        
        conn = self.get_conn()
        if not conn:
            return {'success': False, 'message': 'No hay conexión a BD'}
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO firewatch_2.recipients (email, name, is_active) 
                VALUES (%s, %s, TRUE)
            """, (email, name))
            conn.commit()
            return {'success': True, 'message': f'Destinatario {email} agregado'}
        except mysql.connector.Error as e:
            if 'Duplicate' in str(e):
                return {'success': False, 'message': f'El email {email} ya existe'}
            return {'success': False, 'message': str(e)}
        finally:
            conn.close()

    def get_recipients(self, active_only: bool = True) -> list:
        """Obtiene lista de destinatarios"""
        conn = self.get_conn()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor(dictionary=True)
            if active_only:
                cursor.execute("""
                    SELECT id, email, name, is_active, created_at 
                    FROM firewatch_2.recipients 
                    WHERE is_active = TRUE 
                    ORDER BY created_at DESC
                """)
            else:
                cursor.execute("""
                    SELECT id, email, name, is_active, created_at 
                    FROM firewatch_2.recipients 
                    ORDER BY created_at DESC
                """)
            return cursor.fetchall() or []
        except mysql.connector.Error as e:
            print(f"[DB] Error en get_recipients: {e}")
            return []
        finally:
            conn.close()

    def get_recipient(self, recipient_id: int) -> dict:
        """Obtiene un destinatario por ID"""
        conn = self.get_conn()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT id, email, name, is_active, created_at 
                FROM firewatch_2.recipients 
                WHERE id = %s
            """, (recipient_id,))
            return cursor.fetchone()
        except mysql.connector.Error as e:
            print(f"[DB] Error en get_recipient: {e}")
            return None
        finally:
            conn.close()

    def update_recipient(self, recipient_id: int, email: str = None, name: str = None) -> dict:
        """Actualiza datos de un destinatario"""
        conn = self.get_conn()
        if not conn:
            return {'success': False, 'message': 'No hay conexión a BD'}
        
        try:
            cursor = conn.cursor()
            updates = []
            params = []
            
            if email is not None:
                # Validar email
                is_valid, error_msg = self.validate_email(email)
                if not is_valid:
                    return {'success': False, 'message': error_msg}
                updates.append("email = %s")
                params.append(email.strip())
            
            if name is not None:
                # Validar nombre
                is_valid, error_msg = self.validate_name(name)
                if not is_valid:
                    return {'success': False, 'message': error_msg}
                updates.append("name = %s")
                params.append(name.strip())
            
            if not updates:
                return {'success': False, 'message': 'No hay datos para actualizar'}
            
            params.append(recipient_id)
            query = f"UPDATE firewatch_2.recipients SET {', '.join(updates)} WHERE id = %s"
            cursor.execute(query, params)
            conn.commit()
            return {'success': True, 'message': 'Destinatario actualizado'}
        except mysql.connector.Error as e:
            if 'Duplicate' in str(e):
                return {'success': False, 'message': 'El email ya está registrado'}
            return {'success': False, 'message': str(e)}
        finally:
            conn.close()

    def delete_recipient(self, recipient_id: int) -> dict:
        """Elimina un destinatario"""
        conn = self.get_conn()
        if not conn:
            return {'success': False, 'message': 'No hay conexión a BD'}
        
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM firewatch_2.recipients WHERE id = %s", (recipient_id,))
            conn.commit()
            return {'success': True, 'message': 'Destinatario eliminado'}
        except mysql.connector.Error as e:
            print(f"[DB] Error en delete_recipient: {e}")
            return {'success': False, 'message': 'Error al eliminar destinatario'}
        finally:
            conn.close()

    def toggle_recipient_active(self, recipient_id: int, is_active: bool) -> dict:
        """Activa o desactiva un destinatario"""
        conn = self.get_conn()
        if not conn:
            return {'success': False, 'message': 'No hay conexión a BD'}
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE firewatch_2.recipients 
                SET is_active = %s 
                WHERE id = %s
            """, (is_active, recipient_id))
            conn.commit()
            estado = 'activado' if is_active else 'desactivado'
            return {'success': True, 'message': f'Destinatario {estado}'}
        except mysql.connector.Error as e:
            print(f"[DB] Error en toggle_recipient_active: {e}")
            return {'success': False, 'message': 'Error al actualizar estado'}
        finally:
            conn.close()

    def get_active_recipients_emails(self) -> list:
        """Retorna lista de emails activos para enviar alertas"""
        recipients = self.get_recipients(active_only=True)
        return [r['email'] for r in recipients] if recipients else []
