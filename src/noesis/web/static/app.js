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
  const fields = (opts.fields || []).map(f => {
    const control = f.options
      ? `<select class="input" data-name="${f.name}">${f.options.map(o =>
          `<option value="${esc(o.value)}">${esc(o.label)}</option>`).join('')}</select>`
      : `<input class="input" data-name="${f.name}" type="${f.type || 'text'}"
          value="${esc(f.value ?? '')}" placeholder="${esc(f.placeholder || '')}">`;
    return `<label class="fld" style="margin-top:10px">${esc(f.label)}</label>${control}`;
  }).join('');
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
    ov.querySelectorAll('[data-name]').forEach(i => values[i.dataset.name] = i.value.trim());
    await opts.onSubmit(values);
    closeModal();
  };
  const onEsc = e => { if (e.key === 'Escape') { closeModal(); document.removeEventListener('keydown', onEsc); } };
  document.addEventListener('keydown', onEsc);
  const first = ov.querySelector('[data-name]');
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

/* Compartir un enlace privado (portal, presupuesto, acceso del equipo).
   Es el momento en que Noesis "sale" hacia el cliente final, así que enseña
   una previsualización de lo que va a recibir, no un campo de texto pelado.
   Modal accesible: atrapa Escape y devuelve el foco a quien lo abrió. */
const WA_ICON = '<svg viewBox="0 0 24 24" width="17" height="17" fill="currentColor" aria-hidden="true"><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5.1-1.3A10 10 0 1 0 12 2zm0 18.2a8.1 8.1 0 0 1-4.2-1.1l-.3-.2-3 .8.8-3-.2-.3A8.2 8.2 0 1 1 12 20.2zm4.6-6.1c-.3-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1-.2.3-.6.8-.8 1-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.3-.4 0-.5.1-.7l.4-.5c.1-.2.2-.3.3-.5v-.5c0-.1-.6-1.4-.8-1.9-.2-.5-.4-.4-.6-.4h-.5c-.2 0-.5 0-.7.3-.2.3-.9.9-.9 2.1s.9 2.4 1 2.6c.1.2 1.8 2.7 4.3 3.8.6.3 1.1.4 1.5.5.6.2 1.2.2 1.6.1.5-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.2-1.2-.1-.1-.3-.2-.5-.3z"/></svg>';
const LINK_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></svg>';

function shareLink(url, opts = {}) {
  closeModal();
  const opener = document.activeElement;
  let phone = String(opts.phone || '').replace(/\D/g, '');
  if (phone.length === 9) phone = '34' + phone;
  const text = opts.message
    ? (opts.message.includes(url) ? opts.message : opts.message + url)
    : url;
  const wa = phone
    ? `https://wa.me/${phone}?text=${encodeURIComponent(text)}`
    : `https://wa.me/?text=${encodeURIComponent(text)}`;
  let host = '', pathHint = '';
  try { const u = new URL(url); host = u.host; pathHint = u.pathname.slice(0, 14) + '…'; } catch {}
  const msgPreview = opts.message ? String(opts.message).replace(url, '').trim() : '';
  const ov = document.createElement('div');
  ov.className = 'modal-overlay';
  ov.innerHTML = `<div class="modal share-modal" role="dialog" aria-modal="true"
      aria-label="${esc(opts.title || 'Compartir enlace')}">
    <div class="modal-h"><h2>${esc(opts.title || 'Compartir enlace')}</h2>
      <button class="iconbtn modal-x" aria-label="Cerrar">✕</button></div>
    <div class="modal-b">
      <div class="share-preview" aria-hidden="true">
        <span class="share-ic">${LINK_ICON}</span>
        <div class="share-meta">
          <b>${esc(opts.title || 'Enlace privado')}</b>
          <span>${esc(host)}${esc(pathHint)}</span>
        </div>
        <span class="share-badge">privado</span>
      </div>
      ${msgPreview ? `<p class="share-msg">${esc(msgPreview)}</p>` : ''}
      <div class="share-copyrow">
        <input class="input" id="share-url" readonly value="${esc(url)}"
          aria-label="Enlace para compartir" onclick="this.select()">
        <button class="btn modal-copy" type="button">Copiar</button>
      </div>
      <a class="btn wa-share full" href="${esc(wa)}" target="_blank" rel="noopener">
        ${WA_ICON} Enviar por WhatsApp${phone ? '' : ' (elige el contacto)'}</a>
      <p class="share-note">${esc(opts.note ||
        'Cualquiera con este enlace puede abrirlo: envíaselo solo a la persona correcta.')}</p>
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
    setTimeout(() => { copyBtn.textContent = 'Copiar'; }, 1500);
  };
  document.addEventListener('keydown', onEsc);
  copyBtn.focus();
}

/* Menú global "+ Crear" (topbar): cerrar al hacer clic fuera o con Escape. */
document.addEventListener('click', e => {
  const qc = document.querySelector('.quick-create.open');
  if (qc && !qc.contains(e.target)) qc.classList.remove('open');
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    const qc = document.querySelector('.quick-create.open');
    if (qc) qc.classList.remove('open');
  }
});

/* Hoja inferior "Crear" (móvil): mismas altas que el menú "+ Crear" del topbar,
   pero con objetivos táctiles grandes y cierre por arrastre visual. */
function qcSheet() {
  closeModal();
  const item = (href, label, hint) => `<a class="sheet-item" href="/b/${BIZ}/${href}">
    <b>${label}</b><small>${hint}</small></a>`;
  const ov = document.createElement('div');
  ov.className = 'modal-overlay sheet-overlay';
  ov.innerHTML = `<div class="sheet" role="dialog" aria-modal="true" aria-label="Crear">
    <div class="sheet-grip" aria-hidden="true"></div>
    <div class="sheet-title">¿Qué quieres crear?</div>
    ${item('facturas?nuevo=1', 'Factura', 'cobra por tu trabajo')}
    ${item('presupuestos?nuevo=1', 'Presupuesto', 'para cerrar un encargo')}
    ${item('clientes?nuevo=1', 'Cliente', 'una ficha nueva')}
    ${item('costes?nuevo=1', 'Gasto', 'apunta un ticket')}
    ${item('equipo?nuevo=1', 'Persona del equipo', 'con su acceso de fichaje')}
    ${item('asistente', 'Trabajo (por chat)', 'díselo a Noesis con tus palabras')}
  </div>`;
  document.body.appendChild(ov);
  ov.addEventListener('click', e => { if (e.target === ov) closeModal(); });
}

/* Apertura directa del formulario de alta al llegar con ?nuevo=1 desde el menú
   "+ Crear". Cada página registra su modal en window.QUICK_NEW. */
window.addEventListener('DOMContentLoaded', () => {
  if (new URLSearchParams(location.search).get('nuevo') !== '1') return;
  if (typeof window.QUICK_NEW === 'function') setTimeout(window.QUICK_NEW, 120);
});

/* Buscador global (Ctrl+K): clientes, facturas, presupuestos y trabajos. */
function searchModal() {
  closeModal();
  const ov = document.createElement('div');
  ov.className = 'modal-overlay search-overlay';
  ov.innerHTML = `<div class="modal search-modal" role="dialog" aria-modal="true" aria-label="Buscar">
    <div class="search-box">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.5" y2="16.5"/></svg>
      <input class="input" id="gs-input" placeholder="Cliente, factura, presupuesto o trabajo…"
             autocomplete="off" spellcheck="false">
      <kbd>Esc</kbd>
    </div>
    <div class="search-results" id="gs-results">
      <div class="empty">Escribe al menos 2 letras. Ej.: «Marta», «2026-004», «caldera».</div>
    </div>
  </div>`;
  document.body.appendChild(ov);
  ov.addEventListener('click', e => { if (e.target === ov) closeModal(); });
  const onEsc = e => {
    if (e.key === 'Escape') { closeModal(); document.removeEventListener('keydown', onEsc); }
  };
  document.addEventListener('keydown', onEsc);
  const input = ov.querySelector('#gs-input');
  const results = ov.querySelector('#gs-results');
  let timer = null, seq = 0;
  const STATUS = { borrador: 'b-gray', enviada: 'b-amber', parcial: 'b-amber',
                   cobrada: 'b-green', aceptado: 'b-green', rechazado: 'b-red',
                   pendiente: 'b-amber', hecho: 'b-green' };
  const badge = s => s ? `<span class="badge ${STATUS[s] || 'b-gray'}">${esc(s)}</span>` : '';
  const group = (title, rows) => rows.length
    ? `<div class="gs-group">${esc(title)}</div>` + rows.join('') : '';
  const row = (href, main, side) => `<a class="gs-row" href="/b/${BIZ}/${href}">
    <span class="gs-main">${main}</span><span class="gs-side">${side}</span></a>`;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (q.length < 2) return;
    timer = setTimeout(async () => {
      const mine = ++seq;
      const r = await api('/search?q=' + encodeURIComponent(q));
      if (mine !== seq) return; // llegó tarde: ya hay otra búsqueda en curso
      const html =
        group('Clientes', r.clients.map(c => row('clientes',
          `<b>${esc(c.name)}</b>${c.zone ? `<small>${esc(c.zone)}</small>` : ''}`,
          esc(c.phone || '')))) +
        group('Facturas', r.invoices.map(i => row('facturas',
          `<b>${esc(i.number || 'borrador')}</b><small>${esc(i.client_name || '')} · ${esc(i.concept)}</small>`,
          `${eur(i.total)} ${badge(i.status)}`))) +
        group('Presupuestos', r.quotes.map(qu => row('presupuestos',
          `<b>${esc(qu.number || 'presupuesto')}</b><small>${esc(qu.client_name || '')} · ${esc(qu.concept)}</small>`,
          `${eur(qu.total)} ${badge(qu.status)}`))) +
        group('Trabajos', r.jobs.map(j => row('agenda',
          `<b>${esc(j.description)}</b><small>${esc(j.client_name || '')}${j.scheduled_for ? ' · ' + dateShort(j.scheduled_for) : ''}</small>`,
          badge(j.status))));
      results.innerHTML = html ||
        `<div class="empty">Nada con «${esc(q)}». Prueba con otro nombre o número.</div>`;
    }, 220);
  });
  input.focus();
}
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    if (typeof BIZ !== 'undefined' && BIZ) searchModal();
  }
});

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
