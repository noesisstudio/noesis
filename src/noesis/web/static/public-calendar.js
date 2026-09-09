/* Cal.com solo se conecta después de consentimiento explícito en Contacto.
 * Protocolo: calcom/cal.com packages/embeds/embed-core, consultado 09-09-2026.
 * La integración no importa el SDK externo ni transmite datos de la reserva.
 */
(function () {
  'use strict';
  const root = document.querySelector('[data-calendar]');
  if (!root) return;
  const consent = root.querySelector('[data-cal-consent]');
  const mount = root.querySelector('[data-cal-mount]');
  const status = root.querySelector('[data-cal-status]');
  const revoke = root.querySelector('[data-cal-revoke]');
  let iframe = null, timeout = null;
  function event(name) {
    document.dispatchEvent(new CustomEvent('noesis:public-event', { detail: { name } }));
  }
  root.querySelector('[data-cal-allow]').addEventListener('click', () => {
    if (iframe) return;
    const url = new URL(root.dataset.calUrl);
    if (url.origin !== 'https://cal.com') return;
    url.pathname += '/embed';
    url.searchParams.set('embed', 'noesis');
    url.searchParams.set('layout', 'month_view');
    url.searchParams.set('theme', 'light');
    iframe = document.createElement('iframe');
    iframe.title = 'Reserva una demo con el equipo de Noesis';
    iframe.name = 'cal-embed=noesis';
    iframe.referrerPolicy = 'no-referrer';
    iframe.src = url.href;
    iframe.style.height = '680px';
    mount.append(iframe);
    consent.hidden = true; revoke.hidden = false;
    status.textContent = 'Conectando con la agenda…';
    event('cal_demo_started');
    timeout = setTimeout(() => {
      status.textContent = 'Si la agenda no aparece, puedes abrirla en otra pestaña.';
      const fallback = document.createElement('a');
      fallback.href = root.dataset.calUrl; fallback.target = '_blank';
      fallback.rel = 'noopener noreferrer'; fallback.textContent = ' Abrir Cal.com';
      status.append(fallback);
    }, 15000);
  });
  window.addEventListener('message', e => {
    if (!iframe || e.origin !== 'https://cal.com' || e.source !== iframe.contentWindow) return;
    const detail = e.data;
    if (!detail || typeof detail !== 'object' || detail.originator !== 'CAL') return;
    const parts = typeof detail.fullType === 'string' ? detail.fullType.split(':') : [];
    if (parts.length !== 3 || parts[0] !== 'CAL' || parts[1] !== 'noesis') return;
    if (parts[2] === '__iframeReady') {
      iframe.contentWindow.postMessage({ originator: 'CAL', method: 'parentKnowsIframeReady' }, 'https://cal.com');
      iframe.contentWindow.postMessage({ originator: 'CAL', method: 'ui', arg: {
        hideEventTypeDetails: true, showTimezoneWhenEventDetailsHidden: true
      } }, 'https://cal.com');
    }
    if (parts[2] === '__dimensionChanged') {
      const height = Number(detail.data?.iframeHeight);
      if (Number.isFinite(height) && height > 0) iframe.style.height = Math.min(2400, Math.max(630, height)) + 'px';
    }
    if (['linkReady', 'bookerReady'].includes(parts[2])) {
      clearTimeout(timeout); status.textContent = 'Disponibilidad de Cal.com. Elige día y hora.';
    }
    if (parts[2] === 'bookingSuccessfulV2') {
      // No conservar uid, correo, título, asistentes ni fechas del evento.
      event('cal_demo_booked');
      status.textContent = 'Reserva enviada a Cal.com. Revisa en tu correo su estado y los detalles.';
    }
  });
  revoke.addEventListener('click', () => {
    clearTimeout(timeout); mount.replaceChildren(); iframe = null;
    consent.hidden = false; revoke.hidden = true;
    status.textContent = 'Calendario cerrado. No volverá a conectarse hasta que lo permitas. Puedes borrar las cookies anteriores de Cal.com desde tu navegador.';
    root.querySelector('[data-cal-allow]').focus();
  });
}());
