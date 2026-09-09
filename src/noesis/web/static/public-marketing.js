/* Demostración sin proveedores, sonido ni datos reales. */
(function () {
  'use strict';
  const allowed = new Set(['hero_whatsapp_cta', 'hero_demo_started', 'hero_demo_completed',
    'autonomos_cta', 'gestorias_cta', 'cal_demo_started', 'cal_demo_booked',
    'pricing_click', 'contact_whatsapp', 'final_cta']);
  const sent = new Set();
  const pages = new Set(['/', '/autonomos', '/gestorias', '/contacto', '/precios']);
  function track(name) {
    if (!pages.has(location.pathname) || !allowed.has(name) || sent.has(name)) return;
    sent.add(name);
    // Solo evento y ruta fija; sin query, cookies, identificador ni contenido.
    fetch('/public/event', { method: 'POST', credentials: 'omit', keepalive: true,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event: name, page: location.pathname })
    }).catch(() => {});
  }
  document.addEventListener('noesis:public-event', e => track(e.detail?.name));
  document.addEventListener('click', e => {
    const link = e.target.closest('[data-public-event]');
    if (link) track(link.dataset.publicEvent);
    else if (e.target.closest('a[href="/precios"]')) track('pricing_click');
  });
  // El menú se cierra al elegir destino, con Escape o al pulsar fuera.
  const menu = document.querySelector('.public-menu');
  if (menu) {
    menu.addEventListener('click', e => { if (e.target.closest('a')) menu.open = false; });
    document.addEventListener('click', e => { if (!menu.contains(e.target)) menu.open = false; });
    menu.addEventListener('keydown', e => {
      if (e.key === 'Escape') { menu.open = false; menu.querySelector('summary').focus(); }
    });
  }
  document.querySelectorAll('[data-conversation-demo]').forEach(demo => {
    const cases = [...demo.querySelectorAll('[data-chat-case]')];
    const selectors = [...demo.querySelectorAll('[data-chat-select]')];
    const pause = demo.querySelector('[data-chat-pause]');
    const motion = matchMedia('(prefers-reduced-motion: reduce)');
    let selected = 0, elapsed = 0, previous = 0, raf = 0, rendered = '';
    let paused = motion.matches, visible = true, completed = false;
    const duration = 7800;
    function render(full = false) {
      const frameKey = [selected, full, paused, visible, document.hidden,
        elapsed >= 800, elapsed >= 1700, elapsed >= 2200].join(':');
      if (frameKey === rendered) return;
      rendered = frameKey;
      cases.forEach((item, index) => {
        item.hidden = index !== selected;
        item.querySelectorAll('[data-chat-step]').forEach(step => {
          const n = Number(step.dataset.chatStep);
          const show = full ? n !== 2 : (n === 0 || n === 1 && elapsed >= 800 ||
            n === 2 && elapsed >= 1700 && elapsed < 2200 || n === 3 && elapsed >= 2200);
          step.classList.toggle('is-visible', show);
        });
      });
      selectors.forEach((button, i) => button.setAttribute('aria-pressed', String(i === selected)));
      pause.textContent = paused ? 'Reproducir' : 'Pausar';
      demo.classList.toggle('is-playing', !paused && visible && !document.hidden && elapsed < 2200);
    }
    function tick(now) {
      if (paused || !visible || document.hidden) { raf = 0; previous = 0; return; }
      if (previous) elapsed += Math.min(now - previous, 100);
      previous = now;
      if (elapsed >= duration) {
        if (selected === cases.length - 1 && !completed) {
          completed = true; track('hero_demo_completed');
        }
        selected = (selected + 1) % cases.length; elapsed = 0;
      }
      render();
      raf = requestAnimationFrame(tick);
    }
    function play() {
      if (paused || !visible || document.hidden || raf) return;
      track('hero_demo_started');
      previous = 0; raf = requestAnimationFrame(tick);
    }
    demo.classList.add('is-animated');
    pause.hidden = false;
    render(paused); play();
    pause.addEventListener('click', () => {
      paused = !paused; if (!paused && elapsed === 0) elapsed = 2200;
      render(paused); play();
    });
    selectors.forEach((button, i) => button.addEventListener('click', () => {
      selected = i; paused = true; elapsed = 2200; render(true);
    }));
    document.querySelectorAll('[data-demo-start]').forEach(link => link.addEventListener('click', () => {
      selected = 0; elapsed = 0; paused = motion.matches; render(paused); play();
      pause.focus({ preventScroll: true });
    }));
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver(entries => {
        visible = entries[0].isIntersecting; render(paused); play();
      }, { threshold: .1 });
      observer.observe(demo);
    }
    document.addEventListener('visibilitychange', () => { render(paused); play(); });
    motion.addEventListener('change', () => { paused = motion.matches; render(paused); play(); });
    const dialog = demo.querySelector('dialog');
    demo.querySelector('[data-invoice-open]').addEventListener('click', () => {
      paused = true; render(true); dialog.showModal();
    });
  });
}());
