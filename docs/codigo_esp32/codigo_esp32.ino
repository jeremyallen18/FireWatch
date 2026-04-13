/*
 * FireWatch ESP32 — Firmware v3.2 (Serial Debug Edition)
 * RGB 4 Pines - Ánodo Común
 */

#include <WiFi.h>
#include <WebServer.h>
#include <DHT.h>

// ── CONFIGURACIÓN WIFI ────────────────────────────────────────────
const char* SSID     = "FIBRA OPTICA NARVIZ";
const char* PASSWORD = "DANA8112VAYA$";

// ── PINES ─────────────────────────────────────────────────────────
const int PIN_LED_R = 14;
const int PIN_LED_G = 12;
const int PIN_LED_B = 13;
const int PIN_BUZZER = 4;
const int PIN_DHT22  = 17;
const int PIN_MQ2    = 35;

// ── BUZZER PWM ────────────────────────────────────────────────────
const int BUZZER_CHANNEL    = 0;
const int BUZZER_RESOLUTION = 8;

// ── UMBRALES ──────────────────────────────────────────────────────
const int   MQ2_THRESHOLD  = 1000;
const float TEMP_THRESHOLD = 30.0;

// ── ALERTAS ───────────────────────────────────────────────────────
typedef enum {
  ALERT_NONE = 0,
  ALERT_TEMP,
  ALERT_GAS,
  ALERT_HTTP
} AlertType;

// ── ESTADO ────────────────────────────────────────────────────────
AlertType alertType  = ALERT_NONE;
bool      alertActive = false;
bool      httpAlertPending = false;

unsigned long alertStart = 0;
unsigned long lastDHTRead = 0;

float temp = 0.0, humidity = 0.0;
int   mq2_value = 0;

const unsigned long DHT_READ_INTERVAL = 2000;

DHT dht(PIN_DHT22, DHT22);
WebServer server(80);

// ═══════════════════════════════════════════════════════════════════
// RGB (ÁNODO COMÚN → LOW = ENCENDIDO)
// ═══════════════════════════════════════════════════════════════════

void setColor(bool r, bool g, bool b) {
  digitalWrite(PIN_LED_R, r ? LOW : HIGH);
  digitalWrite(PIN_LED_G, g ? LOW : HIGH);
  digitalWrite(PIN_LED_B, b ? LOW : HIGH);
}

void updateRGBStatus() {
  if (alertActive) {
    setColor(true, false, false);
  } 
  else if (mq2_value > (MQ2_THRESHOLD * 0.6) || temp > (TEMP_THRESHOLD * 0.8)) {
    setColor(false, false, true);
  } 
  else {
    setColor(false, true, false);
  }
}

// ═══════════════════════════════════════════════════════════════════
// SERIAL DEBUG
// ═══════════════════════════════════════════════════════════════════

void printSensorData() {
  Serial.println("----- FIREWATCH STATUS -----");

  Serial.print("Temperatura: ");
  Serial.print(temp);
  Serial.println(" °C");

  Serial.print("Humedad: ");
  Serial.print(humidity);
  Serial.println(" %");

  Serial.print("MQ2 (Gas): ");
  Serial.println(mq2_value);

  Serial.print("Estado Alerta: ");
  switch (alertType) {
    case ALERT_NONE: Serial.println("NINGUNA"); break;
    case ALERT_TEMP: Serial.println("TEMPERATURA"); break;
    case ALERT_GAS:  Serial.println("GAS"); break;
    case ALERT_HTTP: Serial.println("REMOTA (HTTP)"); break;
  }

  Serial.print("Sistema activo: ");
  Serial.println(alertActive ? "SI" : "NO");

  Serial.print("Nivel de riesgo: ");
  if (mq2_value > MQ2_THRESHOLD || temp > TEMP_THRESHOLD) {
    Serial.println("ALTO");
  } else if (mq2_value > (MQ2_THRESHOLD * 0.6) || temp > (TEMP_THRESHOLD * 0.8)) {
    Serial.println("MEDIO");
  } else {
    Serial.println("BAJO");
  }

  Serial.println("-----------------------------\n");
}

// ═══════════════════════════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════════════════════════

void setup() {
  Serial.begin(115200);

  pinMode(PIN_LED_R, OUTPUT);
  pinMode(PIN_LED_G, OUTPUT);
  pinMode(PIN_LED_B, OUTPUT);
  pinMode(PIN_MQ2, INPUT);

  setColor(false, false, false);

  ledcSetup(BUZZER_CHANNEL, 1000, BUZZER_RESOLUTION);
  ledcAttachPin(PIN_BUZZER, BUZZER_CHANNEL);

  dht.begin();

  WiFi.begin(SSID, PASSWORD);
  Serial.print("Conectando a WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi conectado");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());

  server.on("/", []() {
    server.send(200, "text/plain", "ESP32 FireWatch activo");
  });

  server.on("/ping", HTTP_GET, []() {
    server.send(200, "text/plain", "PONG");
  });

  server.on("/activate", HTTP_POST, []() {
    activateAlert(ALERT_HTTP);
    httpAlertPending = true;
    server.send(200, "application/json", "{\"status\":\"activated\"}");
  });

  server.on("/reset", HTTP_POST, []() {
    httpAlertPending = false;
    deactivateAlert();
    server.send(200, "application/json", "{\"status\":\"reset\"}");
  });

  server.on("/sensors", HTTP_GET, []() {
    String json = "{";
    json += "\"temperature\":" + String(temp) + ",";
    json += "\"humidity\":" + String(humidity) + ",";
    json += "\"mq2_value\":" + String(mq2_value) + ",";
    json += "\"mq2_threshold\":" + String(MQ2_THRESHOLD) + ",";
    json += "\"mq2_alarm\":" + String(mq2_value > MQ2_THRESHOLD ? "true" : "false");
    json += "}";

    server.send(200, "application/json", json);
  });

  server.begin();
}

// ═══════════════════════════════════════════════════════════════════
// LOOP
// ═══════════════════════════════════════════════════════════════════

void loop() {
  server.handleClient();

  unsigned long now = millis();

  if (now - lastDHTRead > DHT_READ_INTERVAL) {
    lastDHTRead = now;

    readSensors();
    checkSensorAlerts();
    checkAutoReset();
    updateRGBStatus();

    // 🔥 PRINT SERIAL AQUÍ
    printSensorData();
  }

  if (alertActive) {
    runBuzzerPattern();
  }
}

// ═══════════════════════════════════════════════════════════════════
// SENSORES
// ═══════════════════════════════════════════════════════════════════

void readSensors() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();

  if (!isnan(t)) temp = t;
  if (!isnan(h)) humidity = h;

  mq2_value = analogRead(PIN_MQ2);
}

// ═══════════════════════════════════════════════════════════════════
// ALERTAS
// ═══════════════════════════════════════════════════════════════════

void checkSensorAlerts() {
  if (httpAlertPending) return;

  if (mq2_value > MQ2_THRESHOLD) {
    activateAlert(ALERT_GAS);
  } 
  else if (temp > TEMP_THRESHOLD && !alertActive) {
    activateAlert(ALERT_TEMP);
  }
}

void checkAutoReset() {
  if (!alertActive || alertType == ALERT_HTTP) return;

  if (mq2_value <= MQ2_THRESHOLD && temp <= TEMP_THRESHOLD) {
    deactivateAlert();
  }
}

void activateAlert(AlertType type) {
  alertActive = true;
  alertType = type;
  alertStart = millis();
}

void deactivateAlert() {
  alertActive = false;
  alertType = ALERT_NONE;
  setColor(false, false, false);
  buzzerOff();
}

// ═══════════════════════════════════════════════════════════════════
// BUZZER
// ═══════════════════════════════════════════════════════════════════

void runBuzzerPattern() {
  unsigned long elapsed = millis() - alertStart;

  if (alertType == ALERT_TEMP) {
    bool on = ((elapsed % 1000) < 500);

    setColor(on, false, false);

    if (on) buzzerTone(1000, 50);
    else buzzerOff();
  } 
  else {
    bool on = ((elapsed % 160) < 100);

    setColor(on, false, false);

    if (on) buzzerTone(2500, 50);
    else buzzerOff();
  }
}

void buzzerTone(int freqHz, int dutyPercent) {
  ledcSetup(BUZZER_CHANNEL, freqHz, BUZZER_RESOLUTION);
  int duty = (255 * dutyPercent) / 100;
  ledcWrite(BUZZER_CHANNEL, duty);
}

void buzzerOff() {
  ledcWrite(BUZZER_CHANNEL, 0);
}