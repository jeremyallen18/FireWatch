/* ═══════════════════════════════════════════════════════════════
   FIREWATCH — main.js
   Utilidades compartidas: reloj, toasts, helpers globales
═══════════════════════════════════════════════════════════════ */

/* ── Reloj en tiempo real ───────────────────────────────────── */
function updateClock() {
  const el = document.getElementById('currentTime');
  if (!el) return;
  const now = new Date();
  // Formato HH:MM:SS con padding de ceros
  el.textContent = [
    now.getHours(), now.getMinutes(), now.getSeconds()
  ].map(n => String(n).padStart(2, '0')).join(':');
}

setInterval(updateClock, 1000);
updateClock();

/* ── Sistema de notificaciones Toast ────────────────────────── */
/**
 * Muestra una notificación flotante temporal.
 * @param {string} msg     - Mensaje a mostrar
 * @param {'info'|'success'|'error'} type - Tipo visual
 * @param {number} duration - Duración en ms (default 3500)
 */
function showToast(msg, type = 'info', duration = 3500) {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  // Ícono según tipo
  const icons = { info: '⚡', success: '✓', error: '⚠' };

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || '·'}</span><span>${msg}</span>`;
  container.appendChild(toast);

  // Auto-eliminar después del tiempo indicado
  setTimeout(() => {
    toast.style.transition = 'opacity .3s ease, transform .3s ease';
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    setTimeout(() => toast.remove(), 320);
  }, duration);
}

/* ── Actualiza el indicador de conexión en el sidebar ────────── */
/**
 * @param {boolean} connected - Estado de la conexión WebSocket
 */
function setConnectionStatus(connected) {
  const dot   = document.getElementById('connectionDot');
  const label = document.getElementById('connectionLabel');
  if (!dot || !label) return;

  if (connected) {
    dot.className   = 'status-dot connected';
    label.textContent = 'Sistema activo';
  } else {
    dot.className   = 'status-dot';
    label.textContent = 'Desconectado';
  }
}

/* ── Formato de timestamp legible ───────────────────────────── */
/**
 * Retorna hora actual en formato HH:MM:SS.
 */
function timeNow() {
  return new Date().toLocaleTimeString('es-MX', { hour12: false });
}

/* ── Exportar tabla como CSV ────────────────────────────────── */
/**
 * Convierte el tbody de la tabla de historial a archivo CSV descargable.
 */
function exportCSV() {
  const table = document.querySelector('.data-table');
  if (!table) return showToast('No hay tabla para exportar', 'error');

  const rows = [...table.querySelectorAll('tr')];
  const csv  = rows.map(row =>
    [...row.querySelectorAll('th, td')]
      .map(cell => `"${cell.innerText.replace(/"/g, '""')}"`)
      .join(',')
  ).join('\n');

  // Crear enlace de descarga virtual
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `firewatch_${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);

  showToast('CSV exportado correctamente', 'success');
}

/* ── Exportar reporte en PDF con formato profesional ──────── */
/**
 * Descarga un reporte PDF profesional con los datos de detecciones
 */
function exportPDF() {
  showToast('Generando reporte PDF...', 'info');
  
  fetch('/api/export/pdf')
    .then(response => {
      if (!response.ok) {
        throw new Error('Error al generar PDF');
      }
      return response.blob();
    })
    .then(blob => {
      // Crear enlace de descarga
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `firewatch_reporte_${new Date().toISOString().slice(0,10)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      
      showToast('Reporte PDF descargado correctamente', 'success');
    })
    .catch(error => {
      console.error('Error:', error);
      showToast('Error al descargar el reporte PDF', 'error');
    });
}

/* ── Enviar reporte por correo ──────────────────────────────── */
/**
 * Abre el modal para enviar el reporte por correo
 */
function openSendReportModal() {
  const modal = document.getElementById('sendReportModal');
  if (modal) {
    modal.classList.remove('hidden');
    document.getElementById('reportEmailInput').focus();
  }
}

/**
 * Cierra el modal de envío de reporte
 */
function closeSendReportModal() {
  const modal = document.getElementById('sendReportModal');
  if (modal) {
    modal.classList.add('hidden');
    document.getElementById('reportEmailInput').value = '';
  }
}

/**
 * Envía el reporte PDF por correo
 */
function sendReportEmail() {
  const recipient = document.getElementById('reportEmailInput').value.trim();
  
  if (!recipient) {
    showToast('Ingresa un correo válido', 'error');
    return;
  }
  
  // Validar formato básico de email
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(recipient)) {
    showToast('El correo no es válido', 'error');
    return;
  }
  
  const sendBtn = document.getElementById('sendReportBtn');
  const originalText = sendBtn.innerText;
  sendBtn.disabled = true;
  sendBtn.innerText = 'Enviando...';
  
  showToast('Generando y enviando reporte...', 'info');
  
  fetch('/api/send-report-email', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ recipient: recipient })
  })
    .then(response => response.json())
    .then(data => {
      sendBtn.disabled = false;
      sendBtn.innerText = originalText;
      
      if (data.success) {
        showToast(data.message, 'success');
        closeSendReportModal();
      } else {
        showToast(data.message || 'Error al enviar reporte', 'error');
      }
    })
    .catch(error => {
      console.error('Error:', error);
      sendBtn.disabled = false;
      sendBtn.innerText = originalText;
      showToast('Error al enviar reporte', 'error');
    });
}