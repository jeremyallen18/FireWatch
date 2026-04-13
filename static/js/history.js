/* ═══════════════════════════════════════════════════════════════
   FIREWATCH — history.js
   Carga y filtrado del historial de detecciones, paginación,
   modal de evidencia fotográfica.
═══════════════════════════════════════════════════════════════ */

/* ── Configuración de paginación ───────────────────────────── */
const PAGE_SIZE = 20;         // registros por página
let currentPage  = 1;
let allRecords   = [];        // caché total de registros
let filteredRecs = [];        // registros después de filtrar

/* ── Carga inicial ──────────────────────────────────────────── */
window.addEventListener('DOMContentLoaded', () => {
  loadHistory();
  setDefaultDates();
});

/* Establece fechas por defecto: último mes hasta hoy */
function setDefaultDates() {
  const today = new Date();
  const lastMonth = new Date(today);
  lastMonth.setMonth(lastMonth.getMonth() - 1);

  document.getElementById('dateTo').value   = today.toISOString().slice(0,10);
  document.getElementById('dateFrom').value = lastMonth.toISOString().slice(0,10);
}

/* ── Obtener registros del API ──────────────────────────────── */
function loadHistory() {
  const gallery = document.getElementById('galleryGrid');
  if (gallery) {
    gallery.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-dim);">Cargando registros...</div>';
  }

  fetch('/api/detections')
    .then(r => r.json())
    .then(data => {
      allRecords = (data.detections || []).map(r => ({
        ...r,
        fecha: r.timestamp ? r.timestamp.slice(0, 10) : '—',
        hora: r.timestamp ? r.timestamp.slice(11, 19) : '—',
        tipo: r.status || 'Desconocido',
        confianza: parseFloat(r.confidence) || 0,
        email_enviado: Boolean(r.alert_sent),
        esp32_alertado: Boolean(r.esp32_triggered),
        imagen_path: r.image_path || ''
      }));
      filteredRecs = [...allRecords];
      updateStats(allRecords);
      renderPage(1);
    })
    .catch(() => {
      const gallery = document.getElementById('galleryGrid');
      if (gallery) {
        gallery.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--danger);">Error al cargar registros.</div>';
      }
      showToast('Error al conectar con el servidor', 'error');
    });
}

/* ── Aplicar filtros ────────────────────────────────────────── */
function applyFilters() {
  const from     = document.getElementById('dateFrom').value;
  const to       = document.getElementById('dateTo').value;
  const minConf  = parseFloat(document.getElementById('minConf').value) || 0;
  const status   = document.getElementById('filterStatus').value;

  filteredRecs = allRecords.filter(r => {
    const date = r.fecha?.slice(0,10) || '';
    if (from && date < from)    return false;
    if (to   && date > to)      return false;
    if (r.confianza < minConf)  return false;
    if (status && r.tipo !== status) return false;
    return true;
  });

  renderPage(1);
  showToast(`${filteredRecs.length} registros encontrados`, 'info');
}

/* ── Limpiar filtros ────────────────────────────────────────── */
function clearFilters() {
  document.getElementById('dateFrom').value    = '';
  document.getElementById('dateTo').value      = '';
  document.getElementById('minConf').value     = '';
  document.getElementById('filterStatus').value = '';
  filteredRecs = [...allRecords];
  renderPage(1);
}

/* ── Renderizar página de la galería ────────────────────────── */
function renderPage(page) {
  currentPage = page;
  const start  = (page - 1) * PAGE_SIZE;
  const slice  = filteredRecs.slice(start, start + PAGE_SIZE);

  const gallery = document.getElementById('galleryGrid');
  document.getElementById('recordCount').textContent =
    `${filteredRecs.length} registros`;

  if (!slice.length) {
    gallery.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-dim);">Sin registros para mostrar.</div>';
    document.getElementById('pagination').innerHTML = '';
    return;
  }

  // Construye cards de la galería
  gallery.innerHTML = slice.map(r => {
    const conf = Math.round((r.confianza || 0) * 100);
    const confCls = conf >= 70 ? 'high' : conf >= 40 ? 'mid' : 'low';

    // Ruta de imagen válida — normalizar para que siempre sea /screenshots/<archivo>
    let imgSrc = null;
    if (r.imagen_path) {
      const cleaned = r.imagen_path.replace(/^\/?(screenshots\/)*/, '');
      imgSrc = `/screenshots/${cleaned}`;
    }

    // HTML del thumbnail
    const thumbnailHtml = imgSrc
      ? `<img src="${imgSrc}" alt="Detección #${r.id}" style="object-fit: cover; width: 100%; height: 100%;" onerror="this.parentElement.innerHTML='<div class=\\"card-thumbnail-placeholder\\"><span>📷</span><span>Error</span></div>'">`
      : `<div class="card-thumbnail-placeholder"><span>📷</span><span>Sin imagen</span></div>`;

    return `
      <div class="detection-card">
        <div class="card-thumbnail">
          ${thumbnailHtml}
        </div>
        <div class="card-info">
          <div class="card-header-info">
            <span class="card-id">#${r.id}</span>
            <span class="card-confidence ${confCls}">${conf}%</span>
          </div>

          <div class="card-datetime">
            <span>${r.fecha?.slice(0,10) || '—'}</span>
            <span>${r.hora || '—'}</span>
          </div>

          <div class="card-status-indicators">
            <div class="status-badge email ${r.email_enviado ? 'active' : ''}">
              <span>✉️</span>
              <span>${r.email_enviado ? 'Enviado' : 'No'}</span>
            </div>
            <div class="status-badge esp32 ${r.esp32_alertado ? 'active' : ''}">
              <span>📡</span>
              <span>${r.esp32_alertado ? 'Sí' : 'No'}</span>
            </div>
          </div>

          <div class="card-actions">
            ${imgSrc ? `<button onclick="openModal('${imgSrc}', ${r.id})">Ver Imagen</button>` : '<button disabled>Sin Imagen</button>'}
            <button onclick="downloadImage('${imgSrc}', ${r.id})">Descargar</button>
          </div>
        </div>
      </div>`;
  }).join('');

  renderPagination();
}

/* ── Paginación ─────────────────────────────────────────────── */
function renderPagination() {
  const total = Math.ceil(filteredRecs.length / PAGE_SIZE);
  const pag   = document.getElementById('pagination');
  if (total <= 1) { pag.innerHTML = ''; return; }

  let html = '';
  for (let i = 1; i <= total; i++) {
    html += `<button class="page-btn ${i === currentPage ? 'active' : ''}"
               onclick="renderPage(${i})">${i}</button>`;
  }
  pag.innerHTML = html;
}

/* ── Estadísticas del historial ─────────────────────────────── */
function updateStats(records) {
  const today = new Date().toISOString().slice(0,10);
  const todayRecs = records.filter(r => r.fecha?.startsWith(today));
  const avgConf   = records.length
    ? Math.round(records.reduce((s, r) => s + (r.confianza || 0), 0) / records.length * 100)
    : 0;

  document.getElementById('hStatTotal').textContent  = records.length;
  document.getElementById('hStatToday').textContent  = todayRecs.length;
  document.getElementById('hStatAvg').textContent    = `${avgConf}%`;
  document.getElementById('hStatAlerts').textContent =
    records.filter(r => r.email_enviado).length;
}

/* ── Modal de evidencia fotográfica ─────────────────────────── */
function openModal(imgPath, id) {
  const modal = document.getElementById('imageModal');
  const rec   = allRecords.find(r => r.id === id);

  document.getElementById('modalImage').src = imgPath.startsWith('/')
    ? imgPath
    : `/${imgPath}`;
  document.getElementById('modalMeta').innerHTML = rec
    ? `ID: ${rec.id} &nbsp;·&nbsp; ${rec.fecha} ${rec.hora} &nbsp;·&nbsp; Confianza: ${Math.round(rec.confianza * 100)}%`
    : '';

  modal.classList.remove('hidden');
}

function closeModal() {
  document.getElementById('imageModal').classList.add('hidden');
  document.getElementById('modalImage').src = '';
}

/* Cierra el modal con Escape */
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
});

/* ── Descargar imagen ───────────────────────────────────────── */
function downloadImage(imgPath, id) {
  if (!imgPath) {
    showToast('No hay imagen disponible', 'warning');
    return;
  }

  const link = document.createElement('a');
  link.href = imgPath.startsWith('/') ? imgPath : `/${imgPath}`;
  link.download = `deteccion_${id}_${new Date().getTime()}.jpg`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  showToast('Descargando imagen...', 'success');
}