/* ═══════════════════════════════════════════════════════════════
   FIREWATCH — statistics.js
   Dashboard de estadísticas y predicción de incendios
   - Compatible con respuestas directas o envueltas en JSON
   - Seguro ante elementos faltantes en el DOM
   - Actualiza reloj, riesgo, stats y gráficas sin romperse
═══════════════════════════════════════════════════════════════ */

let currentRiskData = null;

let charts = {
  temperature: null,
  humidity: null,
  mq2: null,
  risk: null
};

const RISK_COLORS = {
  CRITICAL: '#cc0000',
  HIGH: '#ff6b35',
  MEDIUM: '#ff9800',
  LOW: '#ffc107',
  MINIMAL: '#4caf50',
  UNKNOWN: '#999999'
};

const RISK_LABELS = {
  CRITICAL: 'CRÍTICO',
  HIGH: 'ALTO',
  MEDIUM: 'MEDIO',
  LOW: 'BAJO',
  MINIMAL: 'MÍNIMO',
  UNKNOWN: 'DESCONOCIDO'
};

/* ── Inicialización ─────────────────────────────────────────── */
window.addEventListener('DOMContentLoaded', () => {
  updateClock();
  loadRiskData();
  loadStatistics(7);

  // Reloj en vivo
  setInterval(updateClock, 1000);

  // Actualizar análisis de riesgo cada 5 segundos
  setInterval(loadRiskData, 5000);

  addNavHighlight();
});

/* ── Resalta la navegación activa ───────────────────────────── */
function addNavHighlight() {
  const currentPath = window.location.pathname;

  document.querySelectorAll('.nav-link').forEach(link => {
    if (link.getAttribute('href') === currentPath) {
      link.classList.add('active');
    } else {
      link.classList.remove('active');
    }
  });
}

/* ── Reloj superior ─────────────────────────────────────────── */
function updateClock() {
  const el = document.getElementById('currentTime');
  if (!el) return;

  const now = new Date();
  el.textContent = now.toLocaleTimeString('es-MX', {
    hour12: false
  });
}

/* ── Cargar análisis de riesgo ──────────────────────────────── */
function loadRiskData() {
  fetch('/api/fire-risk')
    .then(r => r.json())
    .then(data => {
      // Soporta respuesta directa o envuelta
      const prediction = normalizeRiskResponse(data);

      currentRiskData = prediction;
      updateRiskDisplay(prediction);
      updateLatestSensorData(prediction);
    })
    .catch(err => {
      console.error('Error cargando riesgo:', err);
      showToast('Error cargando datos de riesgo', 'error');
    });
}

/* ── Normaliza la respuesta de /api/fire-risk ───────────────── */
function normalizeRiskResponse(data) {
  if (!data) return null;

  // Caso 1: backend devuelve el objeto directamente
  if (data.prediction || data.current_values || data.components) {
    return data;
  }

  // Caso 2: backend devuelve { success, data }
  if (data.data && (data.data.prediction || data.data.current_values || data.data.components)) {
    return data.data;
  }

  return null;
}

/* ── Pintar el gauge, componentes y mensajes ───────────────── */
function updateRiskDisplay(prediction) {
  if (!prediction) return;

  const riskLevel = prediction.prediction || 'UNKNOWN';
  const riskScore = Number(prediction.risk_percentage ?? prediction.risk_score ?? 0);
  const riskColor = RISK_COLORS[riskLevel] || RISK_COLORS.UNKNOWN;

  const riskValueEl = document.getElementById('riskValue');
  const riskLabelEl = document.getElementById('riskLabel');
  const gaugeFill = document.getElementById('gaugeFill');
  const gaugeCenter = document.getElementById('riskGaugeCenter');

  if (riskValueEl) riskValueEl.textContent = `${riskScore.toFixed(1)}%`;
  if (riskLabelEl) riskLabelEl.textContent = RISK_LABELS[riskLevel] || riskLevel;

  // Actualiza el arco del gauge
  if (gaugeFill) {
    gaugeFill.style.stroke = riskColor;
    gaugeFill.style.strokeDasharray = `${(riskScore / 100) * 283}, 283`;
  }

  // Fondo del centro del gauge
  if (gaugeCenter) {
    gaugeCenter.style.background = `radial-gradient(circle, ${riskColor}18 0%, transparent 100%)`;
  }

  // Componentes del riesgo
  if (prediction.components) {
    updateComponentBar('compTemp', prediction.components.temperature_risk);
    updateComponentBar('compHumidity', prediction.components.humidity_risk);
    updateComponentBar('compMq2', prediction.components.mq2_risk);
    updateComponentBar('compTrend', prediction.components.trend_risk);
  }

  // Razones
  const reasonsList = document.getElementById('reasonsList');
  if (reasonsList && Array.isArray(prediction.reasons) && prediction.reasons.length > 0) {
    reasonsList.innerHTML = prediction.reasons.map(r => `<li>${escapeHtml(r)}</li>`).join('');
  } else if (reasonsList) {
    reasonsList.innerHTML = '<li>✅ No hay razones de riesgo relevantes</li>';
  }

  // Recomendaciones
  const recommendationsList = document.getElementById('recommendationsList');
  if (recommendationsList && Array.isArray(prediction.recommendations) && prediction.recommendations.length > 0) {
    recommendationsList.innerHTML = prediction.recommendations.map(r => `<li>${escapeHtml(r)}</li>`).join('');
  } else if (recommendationsList) {
    recommendationsList.innerHTML = '<li>✅ Todo en rango normal</li>';
  }
}

/* ── Barra de componente de riesgo ─────────────────────────── */
function updateComponentBar(elementId, value) {
  const elem = document.getElementById(elementId);
  const valueElem = document.getElementById(`${elementId}Val`);

  if (!elem || !valueElem) return;

  const percentage = Math.min(Math.max(Number(value) || 0, 0), 100);
  elem.style.width = `${percentage}%`;
  valueElem.textContent = `${percentage.toFixed(1)}%`;

  if (percentage >= 80) {
    elem.style.backgroundColor = RISK_COLORS.CRITICAL;
  } else if (percentage >= 60) {
    elem.style.backgroundColor = RISK_COLORS.HIGH;
  } else if (percentage >= 40) {
    elem.style.backgroundColor = RISK_COLORS.MEDIUM;
  } else if (percentage >= 20) {
    elem.style.backgroundColor = RISK_COLORS.LOW;
  } else {
    elem.style.backgroundColor = RISK_COLORS.MINIMAL;
  }
}

/* ── Muestra la lectura actual de sensores ─────────────────── */
function updateLatestSensorData(prediction) {
  if (!prediction || !prediction.current_values) return;

  const values = prediction.current_values;

  // Temperatura
  const tempDisplay = document.getElementById('tempDisplay');
  const tempStatus = document.getElementById('tempStatus');
  if (tempDisplay) {
    if (values.temperature !== null && values.temperature !== undefined) {
      tempDisplay.textContent = `${Number(values.temperature).toFixed(1)}°C`;
      const status = getTemperatureStatus(Number(values.temperature));
      if (tempStatus) {
        tempStatus.textContent = status.label;
        tempStatus.style.color = status.color;
      }
    } else {
      tempDisplay.textContent = '--°C';
      if (tempStatus) tempStatus.textContent = 'Sin datos';
    }
  }

  // Humedad
  const humidityDisplay = document.getElementById('humidityDisplay');
  const humidityStatus = document.getElementById('humidityStatus');
  if (humidityDisplay) {
    if (values.humidity !== null && values.humidity !== undefined) {
      humidityDisplay.textContent = `${Number(values.humidity).toFixed(1)}%`;
      const status = getHumidityStatus(Number(values.humidity));
      if (humidityStatus) {
        humidityStatus.textContent = status.label;
        humidityStatus.style.color = status.color;
      }
    } else {
      humidityDisplay.textContent = '--%';
      if (humidityStatus) humidityStatus.textContent = 'Sin datos';
    }
  }

  // MQ2
  const mq2Display = document.getElementById('mq2Display');
  const mq2Status = document.getElementById('mq2Status');
  if (mq2Display) {
    if (values.mq2_value !== null && values.mq2_value !== undefined) {
      mq2Display.textContent = `${Number(values.mq2_value)}`;
      const status = getMQ2Status(Number(values.mq2_value));
      if (mq2Status) {
        mq2Status.textContent = status.label;
        mq2Status.style.color = status.color;
      }
    } else {
      mq2Display.textContent = '--';
      if (mq2Status) mq2Status.textContent = 'Sin datos';
    }
  }
}

/* ── Estados visuales por sensor ───────────────────────────── */
function getTemperatureStatus(temp) {
  if (temp >= 40) return { label: '🔴 Crítica', color: '#cc0000' };
  if (temp >= 35) return { label: '🟡 Alta', color: '#ff6b35' };
  if (temp >= 30) return { label: '🟠 Elevada', color: '#ff9800' };
  if (temp >= 20) return { label: '🟢 Normal', color: '#4caf50' };
  return { label: '🔵 Baja', color: '#2196f3' };
}

function getHumidityStatus(humidity) {
  if (humidity <= 25) return { label: '🔴 Crítica', color: '#cc0000' };
  if (humidity <= 35) return { label: '🟡 Baja', color: '#ff6b35' };
  if (humidity <= 60) return { label: '🟢 Normal', color: '#4caf50' };
  if (humidity <= 75) return { label: '🟠 Alta', color: '#ff9800' };
  return { label: '🔵 Muy Alta', color: '#2196f3' };
}

function getMQ2Status(mq2) {
  if (mq2 >= 2500) return { label: '🔴 Crítico', color: '#cc0000' };
  if (mq2 >= 1500) return { label: '🟡 Alto', color: '#ff6b35' };
  if (mq2 >= 1000) return { label: '🟠 Elevado', color: '#ff9800' };
  if (mq2 >= 500) return { label: '🟡 Moderado', color: '#ffc107' };
  return { label: '🟢 Normal', color: '#4caf50' };
}

/* ── Carga estadísticas históricas ─────────────────────────── */
function loadStatistics(days) {
  const buttons = document.querySelectorAll('.btn-stat');
  buttons.forEach(btn => btn.classList.remove('active'));

  const activeBtn = document.getElementById(`statsDays${days}`);
  if (activeBtn) activeBtn.classList.add('active');

  fetch(`/api/sensor-stats?days=${days}`)
    .then(r => r.json())
    .then(data => {
      const stats = normalizeStatsResponse(data);
      updateStatsTable(stats);
      updateTimeSeriesCharts(stats);
    })
    .catch(err => {
      console.error('Error cargando estadísticas:', err);
      showToast('Error cargando estadísticas', 'error');
      updateStatsTable([]);
    });
}

/* ── Normaliza la respuesta de /api/sensor-stats ───────────── */
function normalizeStatsResponse(data) {
  if (!data) return [];

  // Caso 1: respuesta directa como lista
  if (Array.isArray(data)) return data;

  // Caso 2: respuesta envuelta en { success, data }
  if (Array.isArray(data.data)) return data.data;

  // Caso 3: backend devuelve otra propiedad
  if (Array.isArray(data.stats)) return data.stats;

  return [];
}

/* ── Renderiza la tabla histórica ───────────────────────────── */
function updateStatsTable(stats) {
  const tbody = document.getElementById('statsTableBody');
  if (!tbody) return;

  if (!stats || stats.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="loading-cell">Sin datos disponibles</td></tr>';
    return;
  }

  tbody.innerHTML = stats.map(day => {
    const alertStatus =
      (Number(day.alertas_criticas) > 0 || Number(day.alertas_altas) > 0)
        ? `🔴 ${Number(day.alertas_criticas) || 0} críticas, ${Number(day.alertas_altas) || 0} altas`
        : '✅ Normal';

    const riskValue = Number(day.riesgo_maximo) || 0;

    const riskStr = riskValue >= 80 ? '🔴 CRÍTICO'
      : riskValue >= 60 ? '🟠 ALTO'
      : riskValue >= 40 ? '🟡 MEDIO'
      : '🟢 BAJO';

    return `
      <tr>
        <td>${escapeHtml(String(day.fecha ?? '--'))}</td>
        <td class="mono">${Number(day.lecturas) || 0}</td>
        <td class="mono">${formatNumber(day.temp_promedio, 1)}°C</td>
        <td class="mono">${formatNumber(day.temp_maxima, 1)}/${formatNumber(day.temp_minima, 1)}°C</td>
        <td class="mono">${formatNumber(day.humedad_promedio, 1)}%</td>
        <td class="mono">${formatNumber(day.mq2_promedio, 0)}</td>
        <td>${riskStr}</td>
        <td>${alertStatus}</td>
      </tr>
    `;
  }).join('');
}

/* ── Actualiza las gráficas ────────────────────────────────── */
function updateTimeSeriesCharts(stats) {
  if (!stats || stats.length === 0) return;

  // Orden cronológico ascendente para gráficos
  const ordered = [...stats].reverse();

  const labels = ordered.map(d => String(d.fecha ?? ''));
  const tempProms = ordered.map(d => Number(d.temp_promedio) || 0);
  const tempMaxs = ordered.map(d => Number(d.temp_maxima) || 0);
  const tempMins = ordered.map(d => Number(d.temp_minima) || 0);
  const humidities = ordered.map(d => Number(d.humedad_promedio) || 0);
  const mq2s = ordered.map(d => Number(d.mq2_promedio) || 0);
  const risks = ordered.map(d => Number(d.riesgo_maximo) || 0);

  // Temperatura
  if (charts.temperature) charts.temperature.destroy();
  charts.temperature = new Chart(document.getElementById('tempChart'), {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Promedio',
          data: tempProms,
          borderColor: '#ff9800',
          backgroundColor: 'rgba(255,152,0,0.1)',
          tension: 0.4,
          fill: true,
        },
        {
          label: 'Máxima',
          data: tempMaxs,
          borderColor: '#cc0000',
          backgroundColor: 'transparent',
          borderDash: [5, 5],
          tension: 0.4,
        },
        {
          label: 'Mínima',
          data: tempMins,
          borderColor: '#2196f3',
          backgroundColor: 'transparent',
          borderDash: [5, 5],
          tension: 0.4,
        },
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          labels: { color: 'var(--text-secondary)' }
        }
      },
      scales: {
        y: {
          grid: { color: 'rgba(255,255,255,0.1)' },
          ticks: { color: 'var(--text-secondary)' },
        },
        x: {
          grid: { color: 'rgba(255,255,255,0.1)' },
          ticks: { color: 'var(--text-secondary)' },
        }
      }
    }
  });

  // Humedad
  if (charts.humidity) charts.humidity.destroy();
  charts.humidity = new Chart(document.getElementById('humidityChart'), {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Humedad (%)',
        data: humidities,
        borderColor: '#2196f3',
        backgroundColor: 'rgba(33,150,243,0.1)',
        tension: 0.4,
        fill: true,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          labels: { color: 'var(--text-secondary)' }
        }
      },
      scales: {
        y: {
          grid: { color: 'rgba(255,255,255,0.1)' },
          ticks: { color: 'var(--text-secondary)' },
          max: 100
        },
        x: {
          grid: { color: 'rgba(255,255,255,0.1)' },
          ticks: { color: 'var(--text-secondary)' },
        }
      }
    }
  });

  // MQ2
  if (charts.mq2) charts.mq2.destroy();
  charts.mq2 = new Chart(document.getElementById('mq2Chart'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'MQ2 (ppm)',
        data: mq2s,
        backgroundColor: 'rgba(255,107,53,0.3)',
        borderColor: '#ff6b35',
        borderWidth: 1,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          labels: { color: 'var(--text-secondary)' }
        }
      },
      scales: {
        y: {
          grid: { color: 'rgba(255,255,255,0.1)' },
          ticks: { color: 'var(--text-secondary)' },
        },
        x: {
          grid: { color: 'rgba(255,255,255,0.1)' },
          ticks: { color: 'var(--text-secondary)' },
        }
      }
    }
  });

  // Riesgo
  if (charts.risk) charts.risk.destroy();
  charts.risk = new Chart(document.getElementById('riskChart'), {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Riesgo de Incendio (%)',
        data: risks,
        borderColor: '#cc0000',
        backgroundColor: 'rgba(204,0,0,0.1)',
        tension: 0.4,
        fill: true,
        pointBackgroundColor: risks.map(r => {
          if (r >= 80) return '#cc0000';
          if (r >= 60) return '#ff6b35';
          if (r >= 40) return '#ff9800';
          if (r >= 20) return '#ffc107';
          return '#4caf50';
        }),
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          labels: { color: 'var(--text-secondary)' }
        }
      },
      scales: {
        y: {
          grid: { color: 'rgba(255,255,255,0.1)' },
          ticks: { color: 'var(--text-secondary)' },
          max: 100
        },
        x: {
          grid: { color: 'rgba(255,255,255,0.1)' },
          ticks: { color: 'var(--text-secondary)' },
        }
      }
    }
  });
}

/* ── Refresca todo manualmente ─────────────────────────────── */
function refreshData() {
  loadRiskData();

  const active = document.querySelector('.btn-stat.active');
  const days = active?.id?.replace('statsDays', '') || '7';

  loadStatistics(parseInt(days, 10));
  showToast('Datos actualizados', 'success');
}

/* ── Utilidades ────────────────────────────────────────────── */
function formatNumber(value, decimals = 1) {
  const n = Number(value);
  if (Number.isNaN(n)) return '--';
  return n.toFixed(decimals);
}

function escapeHtml(str) {
  return String(str)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => toast.remove(), 3000);
}