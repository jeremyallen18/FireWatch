# 🔥 FireWatch — Sistema de Detección de Incendios

Sistema completo de monitoreo y alerta de incendios con detección YOLO, integración ESP32, notificaciones por email y base de datos MySQL.

---

## 📋 Requisitos

- Python 3.10+
- MySQL 8.0+ (opcional — funciona sin BD en modo demo)
- Webcam o cámara IP
- ESP32 con firmware cargado (opcional)
- Modelo YOLO entrenado `best.pt`

---

## ⚡ Instalación Rápida

```bash
# 1. Clonar / descomprimir el proyecto
cd firewatch_app

# 2. Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Edita .env con tus credenciales

# 5. Crear base de datos MySQL (opcional)
mysql -u root -p < docs/schema.sql

# 6. Colocar el modelo YOLO
cp ruta/a/best.pt models/best.pt

# 7. Iniciar la aplicación
python app.py
```

Abre en el navegador: **http://localhost:5000**

---

## 🗂️ Estructura del Proyecto

```
firewatch_app/
├── app.py                    ← Aplicación Flask principal
├── requirements.txt
├── .env.example              ← Plantilla de variables de entorno
│
├── config/
│   ├── settings.py           ← Configuración global
│   └── database.py           ← Conexión MySQL
│
├── modules/
│   ├── detector.py           ← Módulo YOLO
│   ├── notifier.py           ← Notificaciones email
│   ├── esp32_controller.py   ← Control ESP32
│   ├── history_manager.py    ← Historial de detecciones
│   └── database_manager.py   ← CRUD MySQL
│
├── templates/
│   ├── dashboard.html        ← Monitoreo en tiempo real
│   ├── history.html          ← Historial de detecciones
│   └── settings.html         ← Configuración
│
├── static/
│   ├── css/main.css
│   ├── js/
│   │   ├── main.js
│   │   ├── dashboard.js
│   │   ├── history.js
│   │   └── settings.js
│   └── images/
│
├── models/
│   └── best.pt               ← Tu modelo YOLO entrenado
│
├── screenshots/              ← Capturas de detecciones
├── logs/
└── docs/
    ├── schema.sql            ← Esquema MySQL
    └── esp32_firmware.ino    ← Firmware para ESP32
```

---

## 🖥️ Ventanas del Sistema

### 1. Monitoreo (`/`)
- Feed de cámara en tiempo real con anotaciones YOLO
- Estado del sistema: Sin fuego / Fuego detectado / Alerta activa
- Indicador de confianza
- Controles: Iniciar, Detener, Probar ESP32, Reiniciar Alerta
- Registro de eventos en tiempo real

### 2. Historial (`/historial`)
- Tabla paginada con todas las detecciones
- Filtros por fecha, confianza y estado
- Vista de evidencia (imagen capturada)
- Exportación a CSV

### 3. Configuración (`/configuracion`)
- Parámetros ESP32 (IP, puerto, modo de conexión)
- Configuración SMTP para alertas por email
- Conexión a base de datos MySQL
- Umbral de detección y cooldown de alertas
- Prueba de conexión para cada servicio

---

## 🔧 Configuración del ESP32

1. Abre `docs/esp32_firmware.ino` en Arduino IDE
2. Instala la placa **ESP32** en el gestor de placas
3. Cambia `SSID` y `PASSWORD` por los de tu red WiFi
4. Conecta:
   - LED → GPIO 2 (con resistencia 330Ω a GND)
   - Buzzer activo → GPIO 4 (con transistor NPN BC547)
5. Carga el firmware al ESP32
6. Anota la IP que aparece en el Monitor Serial
7. Ingresa esa IP en la sección Configuración del sistema

### Modos de comunicación ESP32:
| Modo    | Descripción                              |
|---------|------------------------------------------|
| `http`  | Requests HTTP directo (recomendado)      |
| `mqtt`  | Broker MQTT (Mosquitto, etc.)            |
| `serial`| USB Serial directo (solo local)          |

---

## 📧 Configurar Gmail para alertas

La configuración de correo se gestiona únicamente en el backend mediante variables de entorno. No es editable desde la interfaz web.

1. Activa la verificación en dos pasos en tu cuenta Google
2. Ve a **Seguridad → Contraseñas de aplicaciones**
3. Genera una contraseña para "Correo" / "Otro dispositivo"
4. Define estas variables de entorno en el backend:
   - `SMTP_SERVER`
   - `SMTP_PORT`
   - `EMAIL_SENDER`
   - `EMAIL_RECIPIENT`
   - `EMAIL_PASSWORD`

---

## 🧪 Modo Demo (sin modelo ni cámara)

Si no tienes `best.pt` o cámara disponible, el sistema activa automáticamente el **modo simulación**:
- Genera frames de prueba
- Simula detecciones de fuego periódicas
- Permite probar toda la interfaz y el flujo de alertas

---

## 🔌 API REST

| Endpoint                   | Método | Descripción                    |
|---------------------------|--------|--------------------------------|
| `/api/start_monitoring`   | POST   | Inicia el monitoreo de cámara  |
| `/api/stop_monitoring`    | POST   | Detiene el monitoreo           |
| `/api/reset_alert`        | POST   | Reinicia la alerta activa      |
| `/api/test_esp32`         | POST   | Prueba conexión con ESP32      |
| `/api/test_email`         | POST   | Envía email de prueba          |
| `/api/test_db`            | POST   | Prueba conexión MySQL          |
| `/api/detections`         | GET    | Lista detecciones (paginado)   |
| `/api/stats`              | GET    | Estadísticas generales         |
| `/api/export/csv`         | GET    | Exporta historial CSV          |
| `/api/settings`           | GET    | Obtiene configuración          |
| `/api/settings`           | POST   | Guarda configuración           |

### Eventos WebSocket
| Evento           | Dirección      | Datos                           |
|-----------------|----------------|---------------------------------|
| `video_frame`   | Servidor → Web | `{frame, fire_detected, conf}`  |
| `fire_alert`    | Servidor → Web | `{confidence, timestamp}`       |
| `alert_reset`   | Servidor → Web | `{}`                            |
| `system_status` | Servidor → Web | `{status, message}`             |

---

## 🚀 Producción

Para despliegue en producción se recomienda usar Gunicorn + Nginx:

```bash
pip install gunicorn
gunicorn --worker-class eventlet -w 1 -b 0.0.0.0:5000 app:app
```

---

## 📝 Licencia

Proyecto desarrollado para uso educativo e industrial en sistemas de seguridad contra incendios.
