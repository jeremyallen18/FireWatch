/* ═══════════════════════════════════════════════════════════════
   FIREWATCH — settings.js
   Carga de configuración desde el servidor, guardado de
   secciones individuales y pruebas de conexión.
═══════════════════════════════════════════════════════════════ */

/* ── Carga de configuración al iniciar ─────────────────────── */
window.addEventListener('DOMContentLoaded', () => {
  loadSettings();
});

/* Obtiene todos los ajustes guardados y rellena los inputs */
function loadSettings() {
  fetch('/api/config')
    .then(r => r.json())
    .then(cfg => {
      // ESP32
      setValue('esp32_ip',     cfg.esp32_ip);
      setValue('esp32_port',   cfg.esp32_port);
      setValue('esp32_mode',   cfg.esp32_mode);
      setValue('esp32_serial', cfg.esp32_serial);

      // Base de datos
      setValue('db_host', cfg.db_host);
      setValue('db_port', cfg.db_port);
      setValue('db_user', cfg.db_user);
      setValue('db_name', cfg.db_name);

      // Detección
      setValue('detection_threshold', cfg.detection_threshold || 0.5);
      setValue('alert_cooldown',      cfg.alert_cooldown || 30);
      setValue('camera_source',       cfg.camera_source ?? 0);
      setValue('model_path',          cfg.model_path || 'models/best.pt');

      // Sincroniza el label del slider
      const slider = document.getElementById('detection_threshold');
      if (slider) {
        document.getElementById('thresholdDisplay').textContent =
          parseFloat(slider.value).toFixed(2);
      }
    })
    .catch(() => showToast('No se pudo cargar la configuración', 'error'));
  
  // Cargar estado del filtro de pantallas
  loadScreenFilterStatus();
}

/* Cargar estado del filtro de pantallas */
function loadScreenFilterStatus() {
  fetch('/api/screen-filter')
    .then(r => r.json())
    .then(data => {
      const enabledCheckbox = document.getElementById('screen_filter_enabled');
      const penaltySlider = document.getElementById('screen_filter_penalty');
      
      if (enabledCheckbox) {
        enabledCheckbox.checked = data.enabled || false;
      }
      if (penaltySlider) {
        penaltySlider.value = (data.penalty || 0.7).toFixed(2);
        document.getElementById('penaltyDisplay').textContent = 
          parseFloat(penaltySlider.value).toFixed(2);
      }
    })
    .catch(() => console.log('No se pudo cargar estado del filtro de pantallas'));
}

/* Helper — asigna valor a un input por ID (si existe) */
function setValue(id, val) {
  const el = document.getElementById(id);
  if (el && val !== undefined && val !== null) el.value = val;
}

/* Helper — obtiene valor de un input por ID */
function getValue(id) {
  const el = document.getElementById(id);
  return el ? el.value : null;
}

/* ─── FUNCIONES DE VALIDACIÓN ───────────────────────────────────────── */

function validateThreshold(value) {
  const num = parseFloat(value);
  if (isNaN(num)) return 'Threshold debe ser un número';
  if (num < 0 || num > 1) return 'Threshold debe estar entre 0.0 y 1.0';
  return null;
}

function validateCooldown(value) {
  const num = parseInt(value, 10);
  if (isNaN(num)) return 'Cooldown debe ser un número entero';
  if (num < 1 || num > 3600) return 'Cooldown debe estar entre 1 y 3600 segundos';
  return null;
}

function validateCameraSource(value) {
  const num = parseInt(value, 10);
  if (isNaN(num)) return 'Cámara debe ser un número';
  if (num < 0 || num > 10) return 'Cámara debe ser entre 0 y 10';
  return null;
}

function validatePort(value, fieldName) {
  const num = parseInt(value, 10);
  if (isNaN(num)) return `${fieldName} debe ser un número`;
  if (num < 1 || num > 65535) return `${fieldName} debe estar entre 1 y 65535`;
  return null;
}

function validateIPAddress(value) {
  if (!value || value.trim().length === 0) return 'IP no puede estar vacía';
  if (value.length > 255) return 'IP no puede exceder 255 caracteres';
  return null;
}

function validateDatabaseField(value, fieldName) {
  if (value && value.length > 255) return `${fieldName} no puede exceder 255 caracteres`;
  return null;
}

/* ── Guardar sección ESP32 ──────────────────────────────────── */
function saveESP32() {
  // Validar IP
  const ipError = validateIPAddress(getValue('esp32_ip'));
  if (ipError) {
    showToast(ipError, 'error');
    return;
  }
  
  // Validar puerto
  const portError = validatePort(getValue('esp32_port'), 'ESP32 port');
  if (portError) {
    showToast(portError, 'error');
    return;
  }
  
  postSettings('/api/config/esp32', {
    esp32_ip:     getValue('esp32_ip'),
    esp32_port:   getValue('esp32_port'),
    esp32_mode:   getValue('esp32_mode'),
    esp32_serial: getValue('esp32_serial')
  }, 'Configuración ESP32 guardada');
}

/* ── Guardar sección Base de Datos ──────────────────────────── */
function saveDB() {
  // Validar host
  const hostError = validateIPAddress(getValue('db_host'));
  if (hostError) {
    showToast(hostError, 'error');
    return;
  }
  
  // Validar puerto
  const portError = validatePort(getValue('db_port'), 'DB port');
  if (portError) {
    showToast(portError, 'error');
    return;
  }
  
  // Validar otros campos
  const userError = validateDatabaseField(getValue('db_user'), 'DB user');
  if (userError) {
    showToast(userError, 'error');
    return;
  }
  
  const nameError = validateDatabaseField(getValue('db_name'), 'DB name');
  if (nameError) {
    showToast(nameError, 'error');
    return;
  }
  
  postSettings('/api/config/db', {
    db_host:     getValue('db_host'),
    db_port:     getValue('db_port'),
    db_user:     getValue('db_user'),
    db_password: getValue('db_password'),
    db_name:     getValue('db_name')
  }, 'Configuración de BD guardada');
}

/* ── Guardar parámetros de detección ────────────────────────── */
function saveDetectionSettings() {
  // Validar threshold
  const thresholdError = validateThreshold(getValue('detection_threshold'));
  if (thresholdError) {
    showToast(thresholdError, 'error');
    return;
  }
  
  // Validar cooldown
  const cooldownError = validateCooldown(getValue('alert_cooldown'));
  if (cooldownError) {
    showToast(cooldownError, 'error');
    return;
  }
  
  // Validar cámara
  const cameraError = validateCameraSource(getValue('camera_source'));
  if (cameraError) {
    showToast(cameraError, 'error');
    return;
  }
  
  // Validar path del modelo (no vacío, máx 500 caracteres)
  const modelPath = getValue('model_path');
  if (!modelPath || modelPath.trim().length === 0) {
    showToast('Model path no puede estar vacío', 'error');
    return;
  }
  if (modelPath.length > 500) {
    showToast('Model path no puede exceder 500 caracteres', 'error');
    return;
  }
  
  postSettings('/api/config/detection', {
    detection_threshold: parseFloat(getValue('detection_threshold')),
    alert_cooldown:      parseInt(getValue('alert_cooldown'), 10),
    camera_source:       parseInt(getValue('camera_source'), 10),
    model_path:          modelPath
  }, 'Parámetros de detección guardados');
}

/* ── Guardar todo de una vez ────────────────────────────────── */
function saveAll() {
  saveESP32();
  saveDB();
  saveDetectionSettings();
}

/* ── POST genérico para guardar configuración ───────────────── */
function postSettings(url, payload, successMsg) {
  fetch(url, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload)
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) showToast(successMsg, 'success');
    else showToast(d.error || 'Error al guardar', 'error');
  })
  .catch(() => showToast('Error de red al guardar', 'error'));
}

/* ── Probar conexión ESP32 ──────────────────────────────────── */
function testESP32() {
  showToast('Probando ESP32...', 'info');
  fetch('/api/test-esp32')
    .then(r => r.json())
    .then(d => showToast(d.message || (d.success ? 'ESP32 OK' : 'Fallo'), d.success ? 'success' : 'error'))
    .catch(() => showToast('No se pudo contactar el ESP32', 'error'));
}

/* ── Probar envío de email ──────────────────────────────────── */
function testEmail() {
  showToast('Enviando email de prueba...', 'info');
  fetch('/api/test-email')
    .then(r => r.json())
    .then(d => showToast(d.message || (d.success ? 'Email enviado' : 'Error'), d.success ? 'success' : 'error'))
    .catch(() => showToast('Error al probar email', 'error'));
}

/* ── Probar conexión a la BD ────────────────────────────────── */
function testDB() {
  showToast('Probando base de datos...', 'info');
  fetch('/api/test-db')
    .then(r => r.json())
    .then(d => showToast(d.message || (d.success ? 'BD conectada' : 'Error'), d.success ? 'success' : 'error'))
    .catch(() => showToast('Error al probar la BD', 'error'));
}

/* ═══════════════════════════════════════════════════════════════
   GESTIÓN DE DESTINATARIOS DE ALERTAS
═══════════════════════════════════════════════════════════════ */

/* Carga y muestra la lista de destinatarios */
function loadRecipients() {
  fetch('/api/recipients')
    .then(r => r.json())
    .then(data => {
      const list = document.getElementById('recipientsList');
      if (!list) return;
      
      if (!data.recipients || data.recipients.length === 0) {
        list.innerHTML = '<tr style="text-align:center;color:var(--text-dim);"><td colspan="4" style="padding:20px;">No hay destinatarios agregados</td></tr>';
        return;
      }
      
      list.innerHTML = data.recipients.map(recipient => `
        <tr style="border-bottom:1px solid #eee;">
          <td style="padding:10px;">${escapeHtml(recipient.email)}</td>
          <td style="padding:10px;">${escapeHtml(recipient.name || '—')}</td>
          <td style="padding:10px;text-align:center;">
            <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:${recipient.is_active ? '#4CAF50' : '#ccc'};"></span>
          </td>
          <td style="padding:10px;text-align:center;display:flex;gap:6px;justify-content:center;">
            <button class="btn btn-secondary" style="padding:4px 8px;font-size:0.85rem;" onclick="toggleRecipient(${recipient.id}, ${!recipient.is_active})" title="${recipient.is_active ? 'Desactivar' : 'Activar'}">
              ${recipient.is_active ? '✓ Activo' : '✗ Inactivo'}
            </button>
            <button class="btn btn-secondary" style="padding:4px 8px;font-size:0.85rem;" onclick="editRecipient(${recipient.id})">
              Editar
            </button>
            <button class="btn btn-danger" style="padding:4px 8px;font-size:0.85rem;background:#ff5252;" onclick="deleteRecipient(${recipient.id})">
              Eliminar
            </button>
          </td>
        </tr>
      `).join('');
    })
    .catch(() => showToast('Error al cargar destinatarios', 'error'));
}

/* Agrega un nuevo destinatario */
function addRecipient() {
  const email = document.getElementById('new_recipient_email').value.trim();
  const name = document.getElementById('new_recipient_name').value.trim();
  
  if (!email) {
    showToast('Ingresa un correo', 'error');
    return;
  }
  
  // Validación regex mejorada de email
  const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
  if (!emailRegex.test(email)) {
    showToast('Formato de correo inválido. Ejemplo: usuario@dominio.com', 'error');
    return;
  }
  
  // Validar longitud máxima de email
  if (email.length > 255) {
    showToast('El correo no puede exceder 255 caracteres', 'error');
    return;
  }
  
  // Validar nombre (opcional pero con límite)
  if (name.length > 100) {
    showToast('El nombre no puede exceder 100 caracteres', 'error');
    return;
  }
  
  fetch('/api/recipients', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, name })
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast(data.message || 'Destinatario agregado', 'success');
        document.getElementById('new_recipient_email').value = '';
        document.getElementById('new_recipient_name').value = '';
        loadRecipients();
      } else {
        showToast(data.message || 'Error al agregar', 'error');
      }
    })
    .catch(() => showToast('Error de red', 'error'));
}

/* Edita un destinatario */
function editRecipient(recipientId) {
  const newEmail = prompt('Nuevo correo (dejar vacío para no cambiar):');
  if (newEmail === null) return; // Cancelado
  
  const newName = prompt('Nuevo nombre (opcional):');
  if (newName === null) return;
  
  const payload = {};
  const trimmedEmail = newEmail.trim();
  const trimmedName = newName.trim();
  
  // Validar email si se proporciona
  if (trimmedEmail) {
    const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    if (!emailRegex.test(trimmedEmail)) {
      showToast('Formato de correo inválido. Ejemplo: usuario@dominio.com', 'error');
      return;
    }
    if (trimmedEmail.length > 255) {
      showToast('El correo no puede exceder 255 caracteres', 'error');
      return;
    }
    payload.email = trimmedEmail;
  }
  
  // Validar nombre si se proporciona
  if (trimmedName) {
    if (trimmedName.length > 100) {
      showToast('El nombre no puede exceder 100 caracteres', 'error');
      return;
    }
    payload.name = trimmedName;
  }
  
  if (Object.keys(payload).length === 0) {
    showToast('No hay cambios', 'info');
    return;
  }
  
  fetch(`/api/recipients/${recipientId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast(data.message || 'Destinatario actualizado', 'success');
        loadRecipients();
      } else {
        showToast(data.message || 'Error al actualizar', 'error');
      }
    })
    .catch(() => showToast('Error de red', 'error'));
}

/* Activa o desactiva un destinatario */
function toggleRecipient(recipientId, isActive) {
  fetch(`/api/recipients/${recipientId}/toggle`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_active: isActive })
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast(data.message || (isActive ? 'Activado' : 'Desactivado'), 'success');
        loadRecipients();
      } else {
        showToast(data.message || 'Error', 'error');
      }
    })
    .catch(() => showToast('Error de red', 'error'));
}

/* Elimina un destinatario */
function deleteRecipient(recipientId) {
  if (!confirm('¿Eliminar este destinatario?')) return;
  
  fetch(`/api/recipients/${recipientId}`, {
    method: 'DELETE'
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast(data.message || 'Destinatario eliminado', 'success');
        loadRecipients();
      } else {
        showToast(data.message || 'Error al eliminar', 'error');
      }
    })
    .catch(() => showToast('Error de red', 'error'));
}

/* Helper para escapar HTML */
function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return (text || '').replace(/[&<>"']/g, m => map[m]);
}

/* Carga destinatarios cuando el DOM está listo */
document.addEventListener('DOMContentLoaded', loadRecipients);

/* ═══════════════════════════════════════════════════════════════
   FILTRO DE PANTALLAS
═══════════════════════════════════════════════════════════════ */

/* Guardaguarda configuración del filtro de pantallas */
function saveScreenFilter() {
  const enabled = document.getElementById('screen_filter_enabled').checked;
  const penalty = parseFloat(document.getElementById('screen_filter_penalty').value);
  
  // Validar penalty
  if (isNaN(penalty) || penalty < 0 || penalty > 1) {
    showToast('Penalty debe ser un número entre 0.0 y 1.0', 'error');
    return;
  }
  
  fetch('/api/screen-filter', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      enabled: enabled,
      penalty: penalty
    })
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast(data.message || 'Filtro de pantallas guardado', 'success');
      } else {
        showToast(data.message || 'Error al guardar', 'error');
      }
    })
    .catch(() => showToast('Error de red', 'error'));
}

/* Prueba el filtro de pantallas */
function testScreenFilter() {
  showToast('Probando filtro de pantallas...', 'info');
  fetch('/api/screen-filter')
    .then(r => r.json())
    .then(data => {
      const status = data.enabled ? 'Activado' : 'Desactivado';
      const penalty = (data.penalty * 100).toFixed(0);
      showToast(
        `Filtro: ${status}\nPenalización: ${penalty}%`,
        'success'
      );
    })
    .catch(() => showToast('Error al probar filtro', 'error'));
}