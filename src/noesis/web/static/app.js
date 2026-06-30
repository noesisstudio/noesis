/* Helpers compartidos por todas las páginas de Noesis. */
const BIZ = window.NOESIS_BIZ;

const eur = n => (n ?? 0).toLocaleString('es-ES',
  { style: 'currency', currency: 'EUR' });
const num = n => (n ?? 0).toLocaleString('es-ES');
const pct = n => `${Math.round(n || 0)}%`;

const api = (path) => fetch(`/api/${BIZ}${path}`).then(async r => {
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || 'Error de API');
  return data;
});
const apiPost = (path, body) => fetch(`/api/${BIZ}${path}`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body || {})
}).then(async r => {
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || 'Error de API');
  return data;
});
const apiDelete = (path) => fetch(`/api/${BIZ}${path}`, { method: 'DELETE' })
  .then(async r => {
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || 'Error de API');
    return data;
  });

/* Icono de papelera reutilizable para botones de borrar. */
const TRASH = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>';

const el = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);
const dateShort = (value) => value ? new Date(value).toLocaleDateString('es-ES',
  { day: '2-digit', month: 'short' }) : '—';
const dateIso = (value) => value ? String(value).slice(0, 10) : '—';
const timeShort = (value) => value && String(value).includes('T')
  ? String(value).split('T')[1].slice(0, 5) : '';
const daysText = (days) => days == null ? 'sin fecha' : `${days} día${days === 1 ? '' : 's'}`;
const emptyState = (title, text, href, action) => `
  <div class="empty-state">
    <b>${esc(title)}</b>
    <span>${esc(text)}</span>
    ${href ? `<br><a class="btn sm" href="${href}">${esc(action || 'Ver')}</a>` : ''}
  </div>`;

/* Modal de formulario reutilizable (sustituye a los prompt() del navegador). */
function closeModal() {
  const m = document.querySelector('.modal-overlay');
  if (m) m.remove();
}
function formModal(opts) {
  closeModal();
  const ov = document.createElement('div');
  ov.className = 'modal-overlay';
  const fields = (opts.fields || []).map(f => `
    <label class="fld" style="margin-top:10px">${esc(f.label)}</label>
    <input class="input" data-name="${f.name}" type="${f.type || 'text'}"
      value="${esc(f.value ?? '')}" placeholder="${esc(f.placeholder || '')}">`).join('');
  ov.innerHTML = `<div class="modal" role="dialog" aria-modal="true">
    <div class="modal-h"><h2>${esc(opts.title)}</h2>
      <button class="iconbtn modal-x" aria-label="Cerrar">✕</button></div>
    <div class="modal-b">${fields}</div>
    <div class="modal-f"><button class="btn modal-cancel">Cancelar</button>
      <button class="btn primary modal-save">${esc(opts.submitLabel || 'Guardar')}</button></div>
  </div>`;
  document.body.appendChild(ov);
  ov.addEventListener('click', e => { if (e.target === ov) closeModal(); });
  ov.querySelector('.modal-x').onclick = closeModal;
  ov.querySelector('.modal-cancel').onclick = closeModal;
  ov.querySelector('.modal-save').onclick = async () => {
    const values = {};
    ov.querySelectorAll('input[data-name]').forEach(i => values[i.dataset.name] = i.value.trim());
    await opts.onSubmit(values);
    closeModal();
  };
  const onEsc = e => { if (e.key === 'Escape') { closeModal(); document.removeEventListener('keydown', onEsc); } };
  document.addEventListener('keydown', onEsc);
  const first = ov.querySelector('input');
  if (first) first.focus();
}

/* Mini-barras "Top X" (clientes, categorías, canales). items: {name, value, valText}. */
function barlist(items, cls) {
  if (!items || !items.length) return '<div class="empty">Sin datos todavía.</div>';
  const max = Math.max(1, ...items.map(i => i.value || 0));
  return items.map(i => `<div class="b-row">
    <span class="b-name">${esc(i.name)}</span>
    <span class="b-val">${esc(i.valText)}</span>
    <span class="b-track"><span class="b-fill ${cls || ''}" style="width:${Math.round((i.value || 0) / max * 100)}%"></span></span>
  </div>`).join('');
}

/* Compartir un enlace privado (portal del cliente): copiar o enviar por WhatsApp.
   Modal accesible: atrapa Escape, devuelve el foco a quien lo abrió. */
function shareLink(url, opts = {}) {
  closeModal();
  const opener = document.activeElement;
  const phone = String(opts.phone || '').replace(/\D/g, '');
  const text = (opts.message || '') + url;
  const wa = phone
    ? `https://wa.me/${phone}?text=${encodeURIComponent(text)}`
    : `https://wa.me/?text=${encodeURIComponent(text)}`;
  const ov = document.createElement('div');
  ov.className = 'modal-overlay';
  ov.innerHTML = `<div class="modal" role="dialog" aria-modal="true"
      aria-label="${esc(opts.title || 'Compartir enlace')}">
    <div class="modal-h"><h2>${esc(opts.title || 'Compartir enlace')}</h2>
      <button class="iconbtn modal-x" aria-label="Cerrar">✕</button></div>
    <div class="modal-b">
      <p class="muted" style="margin:0 0 10px">Enlace privado de tu cliente. Cualquiera
        con el enlace puede verlo, así que envíaselo solo a él.</p>
      <input class="input" id="share-url" readonly value="${esc(url)}"
        aria-label="Enlace del portal" onclick="this.select()">
    </div>
    <div class="modal-f">
      <button class="btn modal-copy" type="button">Copiar enlace</button>
      <a class="btn primary" href="${esc(wa)}" target="_blank" rel="noopener">Enviar por WhatsApp</a>
    </div>
  </div>`;
  document.body.appendChild(ov);
  const close = () => {
    ov.remove();
    document.removeEventListener('keydown', onEsc);
    if (opener && opener.focus) opener.focus();
  };
  const onEsc = e => { if (e.key === 'Escape') close(); };
  ov.addEventListener('click', e => { if (e.target === ov) close(); });
  ov.querySelector('.modal-x').onclick = close;
  const copyBtn = ov.querySelector('.modal-copy');
  copyBtn.onclick = async () => {
    try { await navigator.clipboard.writeText(url); }
    catch { const i = el('share-url'); i.select(); document.execCommand('copy'); }
    copyBtn.textContent = '¡Copiado!';
    setTimeout(() => { copyBtn.textContent = 'Copiar enlace'; }, 1500);
  };
  document.addEventListener('keydown', onEsc);
  copyBtn.focus();
}

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
