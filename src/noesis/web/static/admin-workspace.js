/* Navegación progresiva: sin JS todos los apartados y formularios siguen disponibles. */
(() => {
  const root = document.querySelector('[data-admin-workspace]');
  if (!root) return;
  const panels = [...root.querySelectorAll('[data-admin-panel]')];
  const links = [...document.querySelectorAll('[data-admin-nav]')];
  const title = document.getElementById('admin-view-title');
  const hint = document.getElementById('admin-view-hint');
  const heading = document.getElementById('admin-content');
  const navigation = document.querySelector('.admin-nav-disclosure');
  const mobile = window.matchMedia('(max-width:720px)');
  const fitNavigation = () => { if (navigation) navigation.open = !mobile.matches; };
  fitNavigation();
  mobile.addEventListener('change', fitNavigation);
  root.querySelector('[data-admin-refresh]')?.addEventListener('click', event => {
    event.preventDefault();
    window.location.reload();
  });
  const search = root.querySelector('[data-admin-account-search]');
  const accountRows = [...root.querySelectorAll('[data-admin-account-row]')];
  const searchStatus = root.querySelector('[data-admin-search-status]');
  const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es');
  search?.addEventListener('input', () => {
    const query = normalize(search.value.trim());
    let count = 0;
    accountRows.forEach(row => {
      const identity = row.querySelector('.gestion-id').textContent;
      row.hidden = !normalize(identity).includes(query);
      if (!row.hidden) count += 1;
    });
    searchStatus.hidden = !query;
    searchStatus.textContent = `${count} cuentas encontradas de ${accountRows.length}.`;
  });
  const activate = (moveFocus = false) => {
    let hash;
    try { hash = decodeURIComponent(location.hash.slice(1)); } catch { hash = ''; }
    if (hash === 'admin-content') {
      heading.focus({preventScroll:true});
      heading.scrollIntoView({block:'start'});
      return;
    }
    const target = hash ? document.getElementById(hash) : null;
    const targetPanel = target?.closest('[data-admin-panel]');
    const requested = hash.startsWith('vista-') ? hash.slice(6) : targetPanel?.dataset.adminPanel;
    const key = links.some(link => link.dataset.adminNav === requested) ? requested : (root.dataset.adminDefault || 'resumen');
    const refresh = root.querySelector('[data-admin-refresh]');
    if (refresh) refresh.href = `${location.pathname}${location.search}#vista-${key}`;
    panels.forEach(panel => { panel.hidden = panel.dataset.adminPanel !== key; });
    links.forEach(link => {
      const active = link.dataset.adminNav === key;
      if (active) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
      if (active) {
        title.textContent = link.querySelector('span').textContent;
        hint.textContent = link.querySelector('small').textContent;
        const current = document.querySelector('[data-admin-nav-current]');
        if (current) current.textContent = title.textContent;
      }
    });
    if (target && targetPanel && !hash.startsWith('vista-')) {
      for (let parent = target.parentElement; parent; parent = parent.parentElement) {
        if (parent.tagName === 'DETAILS') parent.open = true;
      }
    }
    if (moveFocus) {
      if (navigation && mobile.matches) navigation.open = false;
      heading.focus({preventScroll:true});
      if (target && targetPanel && !hash.startsWith('vista-')) {
        target.scrollIntoView({block:'start'});
      }
      else window.scrollTo({top:0, behavior:'auto'});
    }
    window.dispatchEvent(new Event('resize'));
  };
  activate();
  window.addEventListener('hashchange', () => activate(true));
  window.addEventListener('load', () => {
    if (location.hash.startsWith('#vista-')) window.scrollTo({top:0, behavior:'auto'});
  });
  root.querySelectorAll('details').forEach(item => item.addEventListener('toggle', () => {
    if (item.open) window.dispatchEvent(new Event('resize'));
  }));
})();
