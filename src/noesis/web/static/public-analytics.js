/* Google Analytics de la web pública, solo con permiso explícito.
 * Sin decisión o tras rechazar no hay ninguna petición a Google. La decisión se
 * guarda en este navegador un máximo de 12 meses y se puede cambiar desde el pie
 * («Preferencias de cookies») o desde la política de cookies.
 */
(function () {
  'use strict';
  const tag = document.querySelector('script[data-ga-id]');
  const banner = document.querySelector('[data-cookie-banner]');
  const id = tag ? tag.dataset.gaId : '';
  if (!banner || !/^G-[A-Z0-9]{4,20}$/.test(id)) return;
  const KEY = 'bynoesis-analytics-consent';
  const MAX_AGE = 365 * 24 * 3600 * 1000;
  let loaded = false;

  function stored() {
    try {
      const saved = JSON.parse(localStorage.getItem(KEY) || 'null');
      if (saved && ['granted', 'denied'].includes(saved.v) && Date.now() - saved.t < MAX_AGE) return saved.v;
    } catch (e) { /* Sin almacenamiento: se vuelve a preguntar. */ }
    return '';
  }
  function remember(value) {
    try { localStorage.setItem(KEY, JSON.stringify({ v: value, t: Date.now() })); } catch (e) { /* noop */ }
  }
  function load() {
    if (loaded) return;
    loaded = true;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    // Solo analítica: nada de publicidad, señales de Google ni personalización.
    window.gtag('consent', 'default', { analytics_storage: 'granted', ad_storage: 'denied',
      ad_user_data: 'denied', ad_personalization: 'denied' });
    window.gtag('js', new Date());
    window.gtag('config', id, { allow_google_signals: false, allow_ad_personalization_signals: false });
    const script = document.createElement('script');
    script.async = true;
    script.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(id);
    document.head.append(script);
  }
  function clearCookies() {
    const parts = location.hostname.split('.');
    const domains = [''];
    for (let i = 0; i < parts.length - 1; i++) domains.push('; domain=.' + parts.slice(i).join('.'));
    document.cookie.split(';').forEach(item => {
      const name = item.split('=')[0].trim();
      if (!/^(_ga|_gid|_gat)/.test(name)) return;
      domains.forEach(domain => { document.cookie = name + '=; Max-Age=0; path=/' + domain; });
    });
  }
  function decide(value) {
    remember(value);
    banner.hidden = true;
    if (value === 'granted') { load(); return; }
    clearCookies();
    // Recargar es la única forma segura de parar un gtag ya en marcha.
    if (loaded) location.reload();
  }
  function ask() {
    banner.hidden = false;
    banner.querySelector('[data-cookie-accept]').focus({ preventScroll: true });
  }

  banner.querySelector('[data-cookie-accept]').addEventListener('click', () => decide('granted'));
  banner.querySelector('[data-cookie-reject]').addEventListener('click', () => decide('denied'));
  document.querySelectorAll('[data-cookie-settings]').forEach(button => {
    button.hidden = false;
    button.addEventListener('click', ask);
  });
  // Las mismas interacciones que ya contamos en el servidor, sin datos personales.
  function forward(name) {
    if (loaded && typeof name === 'string' && /^[a-z_]{1,40}$/.test(name)) window.gtag('event', name);
  }
  document.addEventListener('noesis:public-event', e => forward(e.detail?.name));
  document.addEventListener('click', e => {
    const link = e.target.closest('[data-public-event]');
    if (link) forward(link.dataset.publicEvent);
  });

  const choice = stored();
  if (choice === 'granted') load();
  else if (!choice) banner.hidden = false;
}());
