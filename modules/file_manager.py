"""
Gestor de Archivos y Carpetas
FireWatch - file_manager.py
Módulo para manejar creación de carpetas, guardado de imágenes y manejo seguro de archivos
"""

import os
from typing import Optional
import cv2


class FileManager:
    """Maneja operaciones de archivos de forma segura y centralizada"""

    def __init__(self, base_dir: str):
        """
        Inicializa el gestor de archivos
        
        Args:
            base_dir: Directorio base de la aplicación
        """
        self.base_dir = base_dir
        self.screenshots_dir = os.path.join(base_dir, 'screenshots')
        self.logs_dir = os.path.join(base_dir, 'logs')
        self.init_directories()

    def init_directories(self):
        """Crea todos los directorios necesarios"""
        directories = [
            self.screenshots_dir,
            self.logs_dir,
        ]
        
        for directory in directories:
            try:
                os.makedirs(directory, exist_ok=True)
                print(f"[FileManager] Directorio inicializado: {directory}")
            except Exception as e:
                print(f"[FileManager] Error al crear directorio {directory}: {e}")

    def save_screenshot(self, frame: 'cv2.Mat', filename: Optional[str] = None) -> Optional[str]:
        """
        Guarda un screenshot de forma segura
        
        Args:
            frame: Frame de OpenCV para guardar
            filename: Nombre del archivo (si es None, se genera automáticamente)
            
        Returns:
            str: Ruta relativa del archivo guardado o None si falla
        """
        try:
            from datetime import datetime
            
            if filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
                filename = f"fire_{timestamp}.jpg"
            
            full_path = os.path.join(self.screenshots_dir, filename)
            
            # Asegurar que el directorio existe
            os.makedirs(self.screenshots_dir, exist_ok=True)
            
            # Guardar imagen
            success = cv2.imwrite(full_path, frame)
            
            if success:
                print(f"[FileManager] Screenshot guardado: {full_path}")
                return filename
            else:
                print(f"[FileManager] Error: cv2.imwrite() falló para {full_path}")
                return None
                
        except Exception as e:
            print(f"[FileManager] Exception al guardar screenshot: {e}")
            return None

    def get_screenshot_full_path(self, relative_path: str) -> str:
        """
        Obtiene la ruta completa de un screenshot a partir de su ruta relativa
        
        Args:
            relative_path: Ruta relativa (ej: "screenshots/fire_123.jpg")
            
        Returns:
            str: Ruta completa del archivo
        """
        # Si ya incluye 'screenshots/', usar directamente; si no, agregar el directorio
        if relative_path.startswith('screenshots' + os.sep) or relative_path.startswith('screenshots/'):
            return os.path.join(self.base_dir, relative_path)
        return os.path.join(self.screenshots_dir, relative_path)

    def screenshot_exists(self, relative_path: str) -> bool:
        """
        Verifica si un screenshot existe
        
        Args:
            relative_path: Ruta relativa del screenshot
            
        Returns:
            bool: True si existe, False en caso contrario
        """
        full_path = self.get_screenshot_full_path(relative_path)
        return os.path.exists(full_path) and os.path.isfile(full_path)

    def list_screenshots(self) -> list:
        """
        Lista todos los screenshots
        
        Returns:
            list: Lista de nombres de archivos de screenshots
        """
        try:
            if not os.path.exists(self.screenshots_dir):
                return []
            
            files = [f for f in os.listdir(self.screenshots_dir) 
                    if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            return sorted(files, reverse=True)
            
        except Exception as e:
            print(f"[FileManager] Error al listar screenshots: {e}")
            return []

    def get_latest_screenshot(self) -> Optional[str]:
        """
        Obtiene el path del último screenshot
        
        Returns:
            str: Ruta relativa del último screenshot o None
        """
        try:
            files = self.list_screenshots()
            if files:
                return files[0]
            return None
        except Exception as e:
            print(f"[FileManager] Error al obtener último screenshot: {e}")
            return None

    def cleanup_old_screenshots(self, keep_count: int = 100):
        """
        Limpia screenshots antiguos manteniendo solo los más recientes
        
        Args:
            keep_count: Cantidad de screenshots a mantener
        """
        try:
            files = self.list_screenshots()
            
            if len(files) > keep_count:
                to_delete = files[keep_count:]
                for file in to_delete:
                    try:
                        full_path = os.path.join(self.screenshots_dir, file)
                        os.remove(full_path)
                        print(f"[FileManager] Screenshot eliminado: {file}")
                    except Exception as e:
                        print(f"[FileManager] Error al eliminar {file}: {e}")
        except Exception as e:
            print(f"[FileManager] Error en cleanup_old_screenshots: {e}")
