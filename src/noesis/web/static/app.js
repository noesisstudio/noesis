/* Helpers compartidos por todas las páginas de Noesis. */
const BIZ = window.NOESIS_BIZ;

const eur = n => (n ?? 0).toLocaleString('es-ES',
  { style: 'currency', currency: 'EUR' });
const num = n => (n ?? 0).toLocaleString('es-ES');

const api = (path) => fetch(`/api/${BIZ}${path}`).then(r => r.json());
const apiPost = (path, body) => fetch(`/api/${BIZ}${path}`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body || {})
}).then(r => r.json());
const apiDelete = (path) => fetch(`/api/${BIZ}${path}`, { method: 'DELETE' })
  .then(r => r.json());

/* Icono de papelera reutilizable para botones de borrar. */
const TRASH = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>';

const el = (id) => document.getElementById(id);

/* Paleta para gráficos (coherente con el sistema de diseño). */
const CHART = {
  brand: '#2e8b74', brandSoft: '#a9d2c5', forest: '#14463b',
  red: '#c0533f', green: '#1f8a6d', amber: '#b7831f',
  grid: '#ece8db',
  base(extra = {}) {
    return Object.assign({
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom',
        labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, font: { size: 12 } } } },
      scales: { x: { grid: { display: false } },
                y: { beginAtZero: true, grid: { color: this.grid }, border: { display: false } } }
    }, extra);
  }
};
