-- ═══════════════════════════════════════════════════════════════
-- FireWatch — Esquema de Base de Datos MySQL
-- Ejecutar: mysql -u root -p < schema.sql
-- ═══════════════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS firewatch_2
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE firewatch_2;

-- ── Tabla: detecciones ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS detections (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    timestamp        DATETIME DEFAULT CURRENT_TIMESTAMP,
    confidence       FLOAT NOT NULL DEFAULT 0.0,
    image_path       VARCHAR(500),
    video_path       VARCHAR(500),
    status           VARCHAR(100) DEFAULT 'Fuego detectado',
    alert_sent       BOOLEAN DEFAULT FALSE,
    esp32_triggered  BOOLEAN DEFAULT FALSE,
    INDEX idx_timestamp (timestamp),
    INDEX idx_confidence (confidence)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Tabla: alertas ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    detection_id     INT NOT NULL,
    email_sent       BOOLEAN DEFAULT FALSE,
    esp32_sent       BOOLEAN DEFAULT FALSE,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    response_status  VARCHAR(100),
    FOREIGN KEY (detection_id) REFERENCES detections(id) ON DELETE CASCADE,
    INDEX idx_detection (detection_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Tabla: configuración ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS settings (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    setting_key   VARCHAR(100) NOT NULL UNIQUE,
    setting_value TEXT,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Tabla: usuarios ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          ENUM('admin', 'operator', 'viewer') DEFAULT 'operator',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login    DATETIME,
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Tabla: destinatarios de alertas ──────────────────────────────
CREATE TABLE IF NOT EXISTS recipients (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    email         VARCHAR(100) NOT NULL UNIQUE,
    name          VARCHAR(100),
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Tabla: datos de sensores ESP32 ───────────────────────────────
CREATE TABLE IF NOT EXISTS sensor_data (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    timestamp        DATETIME DEFAULT CURRENT_TIMESTAMP,
    temperature      FLOAT,
    humidity         FLOAT,
    mq2_value        INT,
    pressure         FLOAT,
    co_level         INT,
    smoke_level      INT,
    fire_risk_score  FLOAT DEFAULT 0.0,
    prediction       VARCHAR(50) DEFAULT 'LOW',
    location         VARCHAR(100),
    notes            TEXT,
    INDEX idx_timestamp (timestamp),
    INDEX idx_prediction (prediction),
    INDEX idx_risk_score (fire_risk_score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Datos iniciales de configuración ────────────────────────────
INSERT IGNORE INTO settings (setting_key, setting_value) VALUES
  ('smtp_server',         'smtp.gmail.com'),
  ('smtp_port',           '587'),
  ('email_sender',        ''),
  ('email_recipient',     ''),
  ('email_password',      ''),
  ('esp32_ip',            '192.168.1.100'),
  ('esp32_port',          '80'),
  ('esp32_mode',          'http'),
  ('esp32_serial',        'COM3'),
  ('detection_threshold', '0.5'),
  ('alert_cooldown',      '30'),
  ('camera_source',       '0'),
  ('model_path',          'models/best.pt'),
  ('db_host',             'localhost'),
  ('db_port',             '3306'),
  ('db_user',             'root'),
  ('db_password',         ''),
  ('db_name',             'firewatch_2');

-- ── Vista útil: resumen de detecciones ──────────────────────────
CREATE OR REPLACE VIEW detection_summary AS
SELECT
    DATE(timestamp)            AS fecha,
    COUNT(*)                   AS total_detecciones,
    AVG(confidence)            AS confianza_promedio,
    SUM(alert_sent)            AS emails_enviados,
    SUM(esp32_triggered)       AS esp32_activaciones
FROM detections
GROUP BY DATE(timestamp)
ORDER BY fecha DESC;
-- ── Vista útil: resumen de sensores ────────────────────────
CREATE OR REPLACE VIEW sensor_summary AS
SELECT
    DATE(timestamp)            AS fecha,
    COUNT(*)                   AS lecturas,
    AVG(temperature)           AS temp_promedio,
    MAX(temperature)           AS temp_maxima,
    MIN(temperature)           AS temp_minima,
    AVG(humidity)              AS humedad_promedio,
    AVG(mq2_value)             AS mq2_promedio,
    MAX(fire_risk_score)       AS riesgo_maximo,
    SUM(CASE WHEN prediction = 'CRITICAL' THEN 1 ELSE 0 END) as alertas_criticas,
    SUM(CASE WHEN prediction = 'HIGH' THEN 1 ELSE 0 END) as alertas_altas
FROM sensor_data
GROUP BY DATE(timestamp)
ORDER BY fecha DESC;
SELECT 'Esquema FireWatch creado correctamente.' AS mensaje;
