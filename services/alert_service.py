"""
FireWatch - Servicio de alertas
Construccion de correos de alerta de sensores y utilidades relacionadas.
"""

import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config.settings import Config


def risk_color(risk_level: str) -> str:
    """Retorna color hexadecimal basado en nivel de riesgo."""
    colors = {
        'CRITICAL': '#cc0000',
        'HIGH': '#ff6b35',
        'MEDIUM': '#ff9800',
        'LOW': '#ffc107',
        'MINIMAL': '#4caf50',
    }
    return colors.get(risk_level, '#999999')


def build_sensor_alert_email(alert_type, temperature, humidity, mq2_value, prediction):
    """Construye el asunto y cuerpo HTML para una alerta de sensor."""
    if alert_type == 'MQ2_HIGH':
        subject_prefix = "🚨 ALERTA DE GAS/HUMO DETECTADO"
        alert_desc = f"Nivel de gases/humo alto: {mq2_value} ppm"
    elif alert_type == 'TEMP_HIGH':
        subject_prefix = "🌡️ ALERTA TEMPERATURA ALTA"
        alert_desc = f"Temperatura peligrosa: {temperature}°C"
    else:
        subject_prefix = "⚠️ ALERTA DEL SENSOR"
        alert_desc = alert_type

    now = datetime.now()
    subject = f"{subject_prefix} - FireWatch [{now.strftime('%H:%M:%S')}]"

    body = f"""
    <html><body style="font-family:Arial,sans-serif;color:#222;background:#f5f5f5;margin:0;padding:20px;">
    <div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;box-shadow:0 4px 6px rgba(0,0,0,0.1);">
        <div style="background:#ff6b35;padding:20px;border-radius:12px 12px 0 0;color:white;text-align:center;">
            <h1 style="margin:0;font-size:24px;">⚠️ ALERTA DEL SISTEMA ESP32</h1>
        </div>

        <div style="padding:24px;">
            <p style="font-size:16px;color:#333;margin:0 0 20px 0;">
                <strong>{alert_desc}</strong>
            </p>

            <table style="width:100%;border-collapse:collapse;margin:20px 0;">
                <tr style="background:#f9f9f9;">
                    <td style="padding:12px;border-bottom:1px solid #eee;font-weight:bold;width:35%;">Fecha/Hora:</td>
                    <td style="padding:12px;border-bottom:1px solid #eee;">{now.strftime('%d/%m/%Y %H:%M:%S')}</td>
                </tr>
                <tr>
                    <td style="padding:12px;border-bottom:1px solid #eee;font-weight:bold;">Tipo de Alerta:</td>
                    <td style="padding:12px;border-bottom:1px solid #eee;">{alert_type}</td>
                </tr>
                <tr style="background:#f9f9f9;">
                    <td style="padding:12px;border-bottom:1px solid #eee;font-weight:bold;">Temperatura:</td>
                    <td style="padding:12px;border-bottom:1px solid #eee;">{temperature:.1f}°C</td>
                </tr>
                <tr>
                    <td style="padding:12px;border-bottom:1px solid #eee;font-weight:bold;">Humedad:</td>
                    <td style="padding:12px;border-bottom:1px solid #eee;">{humidity:.1f}%</td>
                </tr>
                <tr style="background:#f9f9f9;">
                    <td style="padding:12px;border-bottom:1px solid #eee;font-weight:bold;">Nivel MQ2 (Gas):</td>
                    <td style="padding:12px;border-bottom:1px solid #eee;"><span style="background:#ff6b35;color:white;padding:4px 12px;border-radius:4px;font-weight:bold;">{mq2_value}</span></td>
                </tr>
                <tr>
                    <td style="padding:12px;font-weight:bold;">Riesgo Predicho:</td>
                    <td style="padding:12px;"><span style="background:{risk_color(prediction['prediction'])};color:white;padding:4px 12px;border-radius:4px;font-weight:bold;">{prediction['prediction']} ({prediction['risk_percentage']:.1f}%)</span></td>
                </tr>
            </table>

            <div style="background:#fff3cd;border-left:4px solid #ff9800;padding:12px;margin-top:20px;border-radius:4px;">
                <p style="margin:0;font-size:14px;color:#333;">
                    ⚠️ <strong>Accion Inmediata:</strong> Verifica la zona y toma medidas de seguridad.
                </p>
            </div>
        </div>

        <div style="background:#f5f5f5;padding:16px;border-radius:0 0 12px 12px;text-align:center;border-top:1px solid #eee;">
            <p style="margin:0;font-size:12px;color:#999;">
                FireWatch — Sistema Automatico de Monitoreo de Incendios y Gases
            </p>
        </div>
    </div>
    </body></html>
    """

    return subject, body


def send_sensor_alert_email(subject, body_html):
    """Envia un correo de alerta de sensor usando la configuracion SMTP."""
    try:
        msg = MIMEMultipart()
        msg['From'] = Config.EMAIL_SENDER
        msg['To'] = Config.EMAIL_RECIPIENT
        msg['Subject'] = subject
        msg.attach(MIMEText(body_html, 'html'))

        with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(Config.EMAIL_SENDER, Config.EMAIL_PASSWORD)
            smtp.sendmail(Config.EMAIL_SENDER, Config.EMAIL_RECIPIENT, msg.as_string())
            print(f"[Sensor Alert] Correo enviado")
    except Exception as e:
        print(f"[Sensor Alert] Error enviando correo: {e}")
