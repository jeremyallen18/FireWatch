/* ═══════════════════════════════════════════════════════════════
   FIREWATCH — dashboard.js
   Lógica de monitoreo: WebSocket, estado de detección, log,
   controles de cámara y alertas.
═══════════════════════════════════════════════════════════════ */

/* ── Estado global del dashboard ───────────────────────────── */
const state = {
  monitoring: false,    // si el monitoreo está activo
  alertActive: false,   // si hay alerta de fuego en curso
  frameCount: 0,        // frames procesados en la sesión
  alertCount: 0,        // alertas enviadas hoy
  detectionCount: 0,    // detecciones confirmadas hoy
  totalConf: 0,         // suma de confianzas para calcular promedio
  uptimeStart: null,    // timestamp de inicio del monitoreo
  uptimeInterval: null, // referencia al setInterval del uptime
  cameraSource: 0       // índice/fuente de la cámara USB
};

/* ── Conexión Socket.IO ─────────────────────────────────────── */
const socket = io();  // conecta automáticamente al servidor Flask-SocketIO

socket.on('connect', () => {
  setConnectionStatus(true);
  addLog('Conexión WebSocket establecida', 'ok');
  // Sincronizar estado del sistema al reconectar
  syncSystemState();
});

socket.on('disconnect', () => {
  setConnectionStatus(false);
  addLog('Conexión WebSocket perdida', 'warn');
});

socket.on('system_status', (data) => {
  if (data && data.state && data.state.camera_source !== undefined) {
    state.cameraSource = parseInt(data.state.camera_source, 10) || 0;
    addLog(`Fuente de cámara configurada: ${state.cameraSource}`, 'info');
  }
});

socket.on('video_frame', (data) => {
  const img = document.getElementById('videoFeed');

  if (img) {
    img.src = "data:image/jpeg;base64," + data.frame;
  }

  // Opcional: actualizar UI
  if (data.fire_detected) {
    addLog(`🔥 Fuego detectado (${(data.confidence * 100).toFixed(1)}%)`, 'alert');
  }
});

/* Recibe cada frame procesado del detector */
socket.on('frame_result', (data) => {
  if (!state.monitoring) return;

  state.frameCount++;
  document.getElementById('frameCount').textContent = state.frameCount;

  // Actualiza HUD y barra de confianza
  const pct = Math.round((data.confidence || 0) * 100);
  document.getElementById('confidenceDisplay').textContent = `${pct}%`;
  document.getElementById('confBar').style.width = `${pct}%`;
  document.getElementById('confValue').textContent = `${pct}%`;

  if (data.fire_detected) {
    activateFireState(pct, data.label || 'Fuego');
  }
});

/* Recibe actualizaciones de estadísticas del día */
socket.on('stats_update', (data) => {
  // data.total ya contiene detecciones de HOY (se envía directamente desde el servidor)
  document.getElementById('statTotal').textContent  = data.total    || 0;
  document.getElementById('statAlerts').textContent = data.alerts   || 0;
  document.getElementById('statAvgConf').textContent = `${Math.round(data.avg_conf || 0)}%`;
});

/* ── Sincronizar estado del sistema ─────────────────────────── */
function syncSystemState() {
  fetch('/api/system_state')
    .then(r => r.json())
    .then(systemState => {
      // Actualizar estado local basado en el estado del servidor
      if (systemState.monitoring !== state.monitoring) {
        state.monitoring = systemState.monitoring;
        if (systemState.monitoring) {
          // Si el monitoreo está activo en el servidor, actualizar UI
          document.getElementById('btnStart').disabled = true;
          document.getElementById('btnStop').disabled = false;
          document.getElementById('videoOverlay').classList.add('hidden');
          document.getElementById('liveBadge').classList.add('active');
          const badge = document.getElementById('systemBadge');
          badge.classList.add('active');
          document.getElementById('systemLabel').textContent = 'Activo';
          // Iniciar uptime si no está
          if (!state.uptimeStart) {
            state.uptimeStart = Date.now();
            state.uptimeInterval = setInterval(updateUptime, 1000);
          }
          addLog('Estado sincronizado: monitoreo activo', 'ok');
        } else {
          // Si no está activo, resetear UI
          document.getElementById('btnStart').disabled = false;
          document.getElementById('btnStop').disabled = true;
          document.getElementById('videoFeed').src = '/static/images/no-signal.svg';
          document.getElementById('videoOverlay').classList.remove('hidden');
          document.getElementById('liveBadge').classList.remove('active');
          const badge = document.getElementById('systemBadge');
          badge.classList.remove('active');
          document.getElementById('systemLabel').textContent = 'Inactivo';
          clearInterval(state.uptimeInterval);
          addLog('Estado sincronizado: monitoreo inactivo', 'info');
        }
      }
      // Actualizar otros estados
      if (systemState.fire_detected && !state.alertActive) {
        activateFireState(Math.round(systemState.confidence * 100), 'Fuego');
      } else if (!systemState.fire_detected && state.alertActive) {
        resetAlert();
      }
      state.frameCount = systemState.frame_count || 0;
      document.getElementById('frameCount').textContent = state.frameCount;
      state.cameraSource = systemState.camera_source || 0;
    })
    .catch(err => {
      console.error('Error sincronizando estado:', err);
      addLog('Error al sincronizar estado del sistema', 'warn');
    });
}

/* ── Control de monitoreo ───────────────────────────────────── */
function startMonitoring() {
  if (state.monitoring) return;

  fetch('/api/start_monitoring', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source: state.cameraSource })
  })
  .then(r => r.json())
  .then(d => {
    if (!d.success) {
      addLog(`Error al iniciar monitoreo: ${d.message || 'Desconocido'}`, 'warn');
      showToast(`No se pudo iniciar monitoreo: ${d.message || 'Error'}`, 'error');
      return;
    }

    state.monitoring = true;
    state.uptimeStart = Date.now();

    // Habilita/deshabilita botones
    document.getElementById('btnStart').disabled = true;
    document.getElementById('btnStop').disabled  = false;

    // Activa feed de video
    document.getElementById('videoFeed').src = '/video_feed';
    document.getElementById('videoOverlay').classList.add('hidden');
    document.getElementById('liveBadge').classList.add('active');

    // Actualiza badge de sistema
    const badge = document.getElementById('systemBadge');
    badge.classList.add('active');
    document.getElementById('systemLabel').textContent = 'Activo';

    // Inicia contador de uptime
    state.uptimeInterval = setInterval(updateUptime, 1000);

    addLog('Monitoreo iniciado', 'ok');
    showToast('Monitoreo iniciado', 'success');
  })
  .catch(() => {
    addLog('No se pudo contactar el servidor para iniciar el monitoreo', 'warn');
    showToast('Error de red al iniciar monitoreo', 'error');
  });
}

function stopMonitoring() {
  if (!state.monitoring) return;

  fetch('/api/stop_monitoring', { method: 'POST' })
  .then(r => r.json())
  .then(d => {
    if (!d.success) {
      addLog(`Error al detener monitoreo: ${d.message || 'Desconocido'}`, 'warn');
      showToast(`No se pudo detener monitoreo: ${d.message || 'Error'}`, 'error');
      return;
    }

    state.monitoring = false;
    document.getElementById('btnStart').disabled = false;
    document.getElementById('btnStop').disabled  = true;

    // Restaura video al placeholder
    document.getElementById('videoFeed').src = '/static/images/no-signal.svg';
    document.getElementById('videoOverlay').classList.remove('hidden');
    document.getElementById('liveBadge').classList.remove('active');

    const badge = document.getElementById('systemBadge');
    badge.classList.remove('active');
    document.getElementById('systemLabel').textContent = 'Inactivo';

    clearInterval(state.uptimeInterval);

    addLog('Monitoreo detenido', 'warn');
    showToast('Monitoreo detenido', 'info');
  })
  .catch(() => {
    addLog('No se pudo contactar el servidor para detener el monitoreo', 'warn');
    showToast('Error de red al detener monitoreo', 'error');
  });
}

/* ── Activar estado de fuego detectado ─────────────────────── */
function activateFireState(confidence, label) {
  if (state.alertActive) return;  // evita spam si ya está activa
  state.alertActive = true;

  // Muestra banner y flash
  document.getElementById('alertBanner').classList.remove('hidden');
  document.getElementById('fireFlash').classList.add('active');

  // Actualiza círculo de estado
  const circle = document.getElementById('statusCircle');
  circle.classList.add('fire');
  document.getElementById('statusIconBig').textContent  = '🔥';
  document.getElementById('statusTextBig').textContent  = 'FUEGO';

  // Marca la última detección
  document.getElementById('lastDetection').textContent = timeNow();

  state.detectionCount++;
  document.getElementById('statTotal').textContent = state.detectionCount;

  addLog(`⚠ ${label} — confianza ${confidence}%`, 'fire');
  showToast(`¡Fuego detectado! Confianza: ${confidence}%`, 'error', 6000);
}

/* ── Reiniciar estado de alerta ─────────────────────────────── */
function resetAlert() {
  state.alertActive = false;

  document.getElementById('alertBanner').classList.add('hidden');
  document.getElementById('fireFlash').classList.remove('active');

  const circle = document.getElementById('statusCircle');
  circle.classList.remove('fire');
  document.getElementById('statusIconBig').textContent = '😴';
  document.getElementById('statusTextBig').textContent = 'Sin Fuego';

  socket.emit('reset_alert');
  addLog('Alerta reiniciada manualmente', 'info');
  showToast('Alerta reiniciada', 'info');
}

/* ── Cargar estadísticas del día ───────────────────────────── */
function loadStats() {
  fetch('/api/stats')
    .then(r => r.json())
    .then(data => {
      if (!data) return;
      // Actualizar estadísticas con los valores del servidor
      document.getElementById('statTotal').textContent = data.today || 0;  // Detecciones HOY
      document.getElementById('statAlerts').textContent = data.alerts_sent || 0;
      document.getElementById('statAvgConf').textContent = `${Math.round(data.avg_confidence || 0)}%`;
      addLog(`Estadísticas cargadas: ${data.today || 0} detecciones hoy`, 'info');
    })
    .catch(err => {
      console.error('Error cargando estadísticas:', err);
      addLog('Error al cargar estadísticas', 'warn');
    });
}

/* ── Probar conexión ESP32 ──────────────────────────────────── */
function testESP32() {
  addLog('Probando conexión con ESP32...', 'info');
  fetch('/api/test-esp32')
    .then(r => r.json())
    .then(d => {
      const ok = d.success;
      document.getElementById('esp32Status').textContent = ok ? 'Conectado' : 'Error';
      document.getElementById('esp32Status').className = `metric-value ${ok ? 'text-safe' : 'text-fire'}`;
      addLog(`ESP32: ${d.message || (ok ? 'OK' : 'Fallo')}`, ok ? 'ok' : 'fire');
      showToast(d.message || (ok ? 'ESP32 responde' : 'ESP32 sin respuesta'), ok ? 'success' : 'error');
    })
    .catch(() => showToast('Error al contactar ESP32', 'error'));
}

/* ── Añadir entrada al log de eventos ─────────────────────────
   Tipos: 'info' | 'ok' | 'warn' | 'fire'
─────────────────────────────────────────────────────────────── */
function addLog(msg, type = 'info') {
  const container = document.getElementById('logContainer');
  if (!container) return;

  const entry = document.createElement('div');
  entry.className = `log-entry log-${type} new`;
  entry.innerHTML = `<span class="log-time">${timeNow()}</span><span class="log-msg">${msg}</span>`;

  // Inserta al inicio para mostrar los más recientes primero
  container.insertBefore(entry, container.firstChild);

  // Limita el log a 100 entradas para no abusar de memoria
  if (container.children.length > 100) {
    container.removeChild(container.lastChild);
  }
}

/* ── Limpiar log ────────────────────────────────────────────── */
function clearLog() {
  const container = document.getElementById('logContainer');
  if (container) container.innerHTML = '';
  addLog('Log limpiado', 'info');
}

/* ── Uptime counter ─────────────────────────────────────────── */
function updateUptime() {
  if (!state.uptimeStart) return;
  const elapsed = Math.floor((Date.now() - state.uptimeStart) / 1000);
  const mm = String(Math.floor(elapsed / 60)).padStart(2, '0');
  const ss = String(elapsed % 60).padStart(2, '0');
  document.getElementById('statUptime').textContent = `${mm}:${ss}`;
}

/* ── Inicialización ─────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  // Sincronizar estado y cargar estadísticas al cargar la página
  syncSystemState();
  loadStats();
  // Actualizar ESP32 al iniciar
  testESP32();
  // Recargar estadísticas cada 10 segundos
  setInterval(loadStats, 10000);
});
