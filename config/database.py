"""Gestión de conexión a MySQL para FireWatch"""

import mysql.connector
from mysql.connector import pooling
from config.settings import Config


def get_connection():
    """Retorna una conexión activa a MySQL"""
    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            autocommit=True
        )
        return conn
    except mysql.connector.Error as e:
        print(f"[DB] Error de conexión: {e}")
        return None


class DatabaseManager:
    """Interfaz base para operaciones de BD"""

    def test_connection(self):
        conn = get_connection()
        if conn:
            conn.close()
            return True
        return False
