"""
Módulo de Notificaciones por Email
FireWatch - notifier.py
"""

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

from config.settings import Config


class EmailNotifier:
    """Envía alertas por email cuando se detecta fuego"""

    def __init__(self):
        """Inicializa el notificador cargando desde settings"""
        self.db_manager = None  # Se inyecta desde app.py

    def set_db_manager(self, db_manager):
        """Inyecta el DBManager para acceder a destinatarios"""
        self.db_manager = db_manager

    def _get_config(self):
        return {
            'server': Config.SMTP_SERVER,
            'port': Config.SMTP_PORT,
            'sender': Config.EMAIL_SENDER,
            'recipient': Config.EMAIL_RECIPIENT,
            'password': Config.EMAIL_PASSWORD,
        }

    def send_fire_alert(self, confidence: float, image_path: str = None, lat: float = None, lng: float = None) -> bool:
        """Envía alerta de fuego detectado a todos los destinatarios activos"""
        cfg = self._get_config()
        if not cfg['sender']:
            print("[Email] No hay email remitente configurado")
            return False

        # Obtener destinatarios activos de la BD
        recipients = []
        if self.db_manager:
            recipients = self.db_manager.get_active_recipients_emails()

        # Fallback a email configurado si no hay destinatarios en BD
        if not recipients and cfg['recipient']:
            recipients = [cfg['recipient']]

        if not recipients:
            print("[Email] No hay destinatarios configurados")
            return False

        # Preparar HTML con o sin imagen
        image_html = ""
        if image_path and os.path.exists(image_path):
            image_html = '<img src="cid:deteccion_img" style="max-width:100%;border-radius:8px;margin-top:16px;"/>'

        # Preparar sección de ubicación GPS
        location_html = ""
        if lat is not None and lng is not None:
            maps_url = f"https://www.google.com/maps?q={lat},{lng}"
            location_html = f"""
                    <tr style="background:#f9f9f9;">
                        <td style="padding:12px;border-bottom:1px solid #eee;font-weight:bold;">Ubicación:</td>
                        <td style="padding:12px;border-bottom:1px solid #eee;">
                            📍 {lat:.6f}, {lng:.6f}<br/>
                            <a href="{maps_url}" style="color:#1a73e8;text-decoration:none;font-size:13px;">
                                🗺️ Ver en Google Maps
                            </a>
                        </td>
                    </tr>"""

        subject = f"🔥 ALERTA: Fuego Detectado - FireWatch [{datetime.now().strftime('%H:%M:%S')}]"

        body = f"""
        <html><body style="font-family:Arial,sans-serif;color:#222;background:#f5f5f5;margin:0;padding:20px;">
        <div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;box-shadow:0 4px 6px rgba(0,0,0,0.1);">
            <div style="background:#ff4500;padding:20px;border-radius:12px 12px 0 0;color:white;text-align:center;">
                <h1 style="margin:0;font-size:28px;">🔥 ALERTA DE INCENDIO</h1>
            </div>

            <div style="padding:24px;">
                <p style="font-size:16px;color:#333;margin:0 0 20px 0;">
                    Se ha detectado <strong>FUEGO</strong> en el sistema FireWatch.
                </p>

                <table style="width:100%;border-collapse:collapse;margin:20px 0;">
                    <tr style="background:#f9f9f9;">
                        <td style="padding:12px;border-bottom:1px solid #eee;font-weight:bold;width:30%;">Fecha:</td>
                        <td style="padding:12px;border-bottom:1px solid #eee;">{datetime.now().strftime('%d/%m/%Y')}</td>
                    </tr>
                    <tr>
                        <td style="padding:12px;border-bottom:1px solid #eee;font-weight:bold;">Hora:</td>
                        <td style="padding:12px;border-bottom:1px solid #eee;">{datetime.now().strftime('%H:%M:%S')}</td>
                    </tr>
                    <tr style="background:#f9f9f9;">
                        <td style="padding:12px;border-bottom:1px solid #eee;font-weight:bold;">Confianza:</td>
                        <td style="padding:12px;border-bottom:1px solid #eee;"><strong style="color:#ff4500;">{confidence:.1%}</strong></td>
                    </tr>{location_html}
                    <tr>
                        <td style="padding:12px;font-weight:bold;">Estado:</td>
                        <td style="padding:12px;"><span style="background:#ff4500;color:white;padding:4px 12px;border-radius:4px;font-weight:bold;">ALERTA ACTIVA</span></td>
                    </tr>
                </table>

                {image_html}

                <div style="background:#fff3cd;border-left:4px solid #ff9800;padding:12px;margin-top:20px;border-radius:4px;">
                    <p style="margin:0;font-size:14px;color:#333;">
                        ⚠️ <strong>Acción Requerida:</strong> Verifica la zona y toma las medidas necesarias.
                    </p>
                </div>
            </div>

            <div style="background:#f5f5f5;padding:16px;border-radius:0 0 12px 12px;text-align:center;border-top:1px solid #eee;">
                <p style="margin:0;font-size:12px;color:#999;">
                    FireWatch — Sistema Automático de Detección de Incendios
                </p>
            </div>
        </div>
        </body></html>
        """
        
        # Enviar a cada destinatario
        success_count = 0
        for recipient in recipients:
            if self._send_alert_email(cfg['sender'], cfg['server'], cfg['port'], 
                                     cfg['password'], recipient, subject, body, image_path):
                success_count += 1
                print(f"[Email] Alerta enviada a {recipient}")
            else:
                print(f"[Email] Fallo al enviar a {recipient}")
        
        return success_count > 0

    def _send_alert_email(self, sender: str, server: str, port: int, password: str,
                         recipient: str, subject: str, body_html: str, image_path: str = None) -> bool:
        """Método auxiliar para enviar un email de alerta individual"""
        try:
            msg = MIMEMultipart('related')
            msg['From'] = sender
            msg['To'] = recipient
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body_html, 'html'))
            
            # Adjuntar imagen si existe
            if image_path and os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    img = MIMEImage(f.read())
                    img.add_header('Content-ID', '<deteccion_img>')
                    img.add_header('Content-Disposition', 'inline', filename='deteccion.jpg')
                    msg.attach(img)
            
            with smtplib.SMTP(server, port) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(sender, password)
                smtp.sendmail(sender, recipient, msg.as_string())
            
            return True
        except Exception as e:
            print(f"[Email] Error enviando a {recipient}: {e}")
            return False

    def send_test_email(self) -> dict:
        """Envía email de prueba"""
        cfg = self._get_config()
        if not cfg['sender']:
            return {'success': False, 'message': 'Configura el email primero'}
        
        try:
            msg = MIMEMultipart()
            msg['From'] = cfg['sender']
            msg['To'] = cfg['recipient']
            msg['Subject'] = "✅ Prueba de conexión - FireWatch"
            
            body = f"""
            <html><body style="font-family:Arial,sans-serif;color:#222;background:#f5f5f5;margin:0;padding:20px;">
            <div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;box-shadow:0 4px 6px rgba(0,0,0,0.1);">
                <div style="background:#4caf50;padding:20px;border-radius:12px 12px 0 0;color:white;text-align:center;">
                    <h1 style="margin:0;font-size:28px;">✅ Conexión Exitosa</h1>
                </div>
                
                <div style="padding:24px;">
                    <p style="font-size:16px;color:#333;margin:0 0 20px 0;">
                        El sistema FireWatch está <strong>listo para enviar alertas</strong>.
                    </p>
                    
                    <div style="background:#e8f5e9;border-left:4px solid #4caf50;padding:16px;border-radius:4px;margin-bottom:20px;">
                        <p style="margin:0;font-size:14px;color:#2e7d32;">
                            ✓ Configuración de correo validada<br/>
                            ✓ Conexión SMTP funcionando<br/>
                            ✓ Credenciales correctas
                        </p>
                    </div>
                    
                    <p style="font-size:14px;color:#666;margin:0;">
                        Este es un mensaje de prueba. Cuando se detecte fuego, recibirás una alerta inmediata con evidencia fotográfica.
                    </p>
                </div>
                
                <div style="background:#f5f5f5;padding:16px;border-radius:0 0 12px 12px;text-align:center;border-top:1px solid #eee;">
                    <p style="margin:0;font-size:12px;color:#999;">
                        FireWatch — Sistema Automático de Detección de Incendios
                    </p>
                </div>
            </div>
            </body></html>
            """
            msg.attach(MIMEText(body, 'html'))

            with smtplib.SMTP(cfg['server'], cfg['port']) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(cfg['sender'], cfg['password'])
                smtp.sendmail(cfg['sender'], cfg['recipient'], msg.as_string())

            return {'success': True, 'message': f'Email de prueba enviado a {cfg["recipient"]}'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def send_report_email(self, pdf_data: bytes, recipient: str, stats: dict = None) -> dict:
        """
        Envía un reporte PDF por correo
        
        Args:
            pdf_data: Contenido del PDF en bytes
            recipient: Email del destinatario
            stats: Diccionario con estadísticas del reporte (opcional)
            
        Returns:
            dict: {'success': bool, 'message': str}
        """
        cfg = self._get_config()
        if not cfg['sender']:
            return {'success': False, 'message': 'Configura el email primero'}
        
        if not recipient or not self._is_valid_email(recipient):
            return {'success': False, 'message': 'Correo destinatario inválido'}
        
        try:
            msg = MIMEMultipart()
            msg['From'] = cfg['sender']
            msg['To'] = recipient
            msg['Subject'] = f"📊 Reporte FireWatch - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            
            # Total y alertas desde estadísticas
            total = stats.get('total', 0) if stats else 0
            alertas = stats.get('alerts_sent', 0) if stats else 0
            
            body = f"""
            <html><body style="font-family:Arial,sans-serif;color:#222;background:#f5f5f5;margin:0;padding:20px;">
            <div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;box-shadow:0 4px 6px rgba(0,0,0,0.1);">
                <div style="background:#FF6B35;padding:20px;border-radius:12px 12px 0 0;color:white;text-align:center;">
                    <h1 style="margin:0;font-size:28px;">📊 REPORTE FireWatch</h1>
                </div>
                
                <div style="padding:24px;">
                    <p style="font-size:14px;color:#333;margin:0 0 20px 0;">
                        Se adjunta el reporte completo del sistema FireWatch generado el <strong>{datetime.now().strftime('%d/%m/%Y a las %H:%M:%S')}</strong>.
                    </p>
                    
                    <table style="width:100%;border-collapse:collapse;margin:20px 0;">
                        <tr style="background:#f9f9f9;">
                            <td style="padding:12px;border-bottom:1px solid #eee;font-weight:bold;width:40%;">Total de Detecciones:</td>
                            <td style="padding:12px;border-bottom:1px solid #eee;"><strong>{total}</strong></td>
                        </tr>
                        <tr>
                            <td style="padding:12px;border-bottom:1px solid #eee;font-weight:bold;">Alertas Enviadas:</td>
                            <td style="padding:12px;border-bottom:1px solid #eee;"><strong>{alertas}</strong></td>
                        </tr>
                        <tr style="background:#f9f9f9;">
                            <td style="padding:12px;font-weight:bold;">Generado por:</td>
                            <td style="padding:12px;">Sistema FireWatch</td>
                        </tr>
                    </table>
                    
                    <div style="background:#f0f9ff;border-left:4px solid #FF6B35;padding:12px;border-radius:4px;margin-top:20px;">
                        <p style="margin:0;font-size:13px;color:#333;">
                            📎 El reporte completo con gráficos, análisis temporal y evidencia fotográfica se adjunta en el archivo PDF.
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
            
            # Adjuntar PDF
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(pdf_data)
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment', filename='firewatch_reporte.pdf')
            msg.attach(part)
            
            # Enviar correo
            with smtplib.SMTP(cfg['server'], cfg['port']) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(cfg['sender'], cfg['password'])
                smtp.sendmail(cfg['sender'], recipient, msg.as_string())
            
            print(f"[Email] Reporte enviado a {recipient}")
            return {'success': True, 'message': f'Reporte enviado a {recipient}'}
            
        except Exception as e:
            print(f"[Email] Error enviando reporte: {e}")
            return {'success': False, 'message': str(e)}

    def _is_valid_email(self, email: str) -> bool:
        """Valida formato básico de email"""
        return '@' in email and '.' in email.split('@')[-1]
