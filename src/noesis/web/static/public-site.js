/* Interacciones ligeras del sitio público: demo de producto y precios. */
(function () {
  'use strict';

  const number = value => new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);

  function initProductDemo() {
    document.querySelectorAll('[data-product-demo]').forEach(demo => {
      const tabs = Array.from(demo.querySelectorAll('[data-demo-tab]'));
      const panels = Array.from(demo.querySelectorAll('[data-demo-panel]'));
      if (!tabs.length || !panels.length) return;

      const subnavs = Array.from(demo.querySelectorAll('[data-demo-subnav]'));
      const select = selected => {
        const key = selected.dataset.demoTab;
        const parent = selected.dataset.demoParent || key;
        const crumb = demo.querySelector('[data-demo-crumb]');
        if (crumb) crumb.textContent = selected.dataset.demoLabel || selected.textContent.trim();
        tabs.forEach(tab => {
          // El apartado del menú lateral queda activo también cuando se navega
          // por sus subapartados; dentro del subnav solo se marca el exacto.
          const active = tab.dataset.demoTab === key
            || (!tab.dataset.demoParent && tab.dataset.demoTab === parent);
          tab.classList.toggle('active', active);
          tab.setAttribute('aria-selected', String(active));
          tab.tabIndex = active ? 0 : -1;
        });
        subnavs.forEach(subnav => {
          subnav.hidden = subnav.dataset.demoSubnav !== parent;
        });
        panels.forEach(panel => {
          const active = panel.dataset.demoPanel === key;
          panel.classList.toggle('active', active);
          panel.hidden = !active;
          // Los canvas no pueden medirse mientras el panel está oculto:
          // el gráfico se crea la primera vez que el panel se muestra.
          if (active) ensureDemoCharts(panel);
        });
      };

      tabs.forEach((tab, index) => {
        tab.addEventListener('click', () => select(tab));
        tab.addEventListener('keydown', event => {
          if (!['ArrowDown', 'ArrowRight', 'ArrowUp', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return;
          event.preventDefault();
          let next = index;
          if (event.key === 'Home') next = 0;
          else if (event.key === 'End') next = tabs.length - 1;
          else if (['ArrowDown', 'ArrowRight'].includes(event.key)) next = (index + 1) % tabs.length;
          else next = (index - 1 + tabs.length) % tabs.length;
          tabs[next].focus();
          select(tabs[next]);
        });
      });
      demo.querySelectorAll('[data-demo-open]').forEach(trigger => {
        trigger.addEventListener('click', () => {
          const target = tabs.find(tab => tab.dataset.demoTab === trigger.dataset.demoOpen);
          if (target) select(target);
        });
      });
      select(tabs.find(tab => tab.classList.contains('active')) || tabs[0]);
    });
  }

  const demoChartsReady = new Set();

  function demoChartConfig(id) {
    const barOptions = {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: { legend: { display: false }, tooltip: { enabled: true } },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#74817c', font: { size: 9 } }, border: { display: false } },
        y: { display: false, beginAtZero: true },
      },
    };
    const months = ['Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul'];
    const income = [3050, 3280, 3620, 4010, 4300, 4820];
    const costs = [1180, 1210, 1390, 1460, 1520, 1310];
    const bar = datasets => ({ type: 'bar', data: { labels: months, datasets }, options: barOptions });
    switch (id) {
      case 'demo-home-chart':
        return {
          type: 'bar',
          data: {
            labels: months.slice(1),
            datasets: [
              { label: 'Ingresos', data: income.slice(1), backgroundColor: '#2e8b74', borderRadius: 5, maxBarThickness: 18 },
              { label: 'Gastos', data: costs.slice(1), backgroundColor: '#d5a16a', borderRadius: 5, maxBarThickness: 18 },
            ],
          },
          options: barOptions,
        };
      case 'demo-analisis-chart':
        return bar([
          { label: 'Ingresos', data: income, backgroundColor: '#2e8b74', borderRadius: 5, maxBarThickness: 22 },
          { label: 'Gastos', data: costs, backgroundColor: '#d5a16a', borderRadius: 5, maxBarThickness: 22 },
          { label: 'Beneficio', data: income.map((v, i) => v - costs[i]), backgroundColor: '#14463b', borderRadius: 5, maxBarThickness: 22 },
        ]);
      case 'demo-ingresos-chart':
        return bar([
          { label: 'Facturado', data: income, backgroundColor: '#2e8b74', borderRadius: 5, maxBarThickness: 26 },
        ]);
      case 'demo-costes-chart':
        return {
          type: 'doughnut',
          data: {
            labels: ['Material', 'Combustible', 'Cuota autónomo', 'Seguros', 'Otros'],
            datasets: [{
              data: [610, 240, 294, 96, 70],
              backgroundColor: ['#2e8b74', '#d5a16a', '#14463b', '#8fb8a9', '#c9ddd5'],
              borderWidth: 0,
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: { legend: { position: 'right', labels: { color: '#53635c', font: { size: 10 }, boxWidth: 12 } } },
          },
        };
      default:
        return null;
    }
  }

  function ensureDemoCharts(root) {
    if (typeof window.Chart !== 'function') return;
    (root || document).querySelectorAll('canvas[id^="demo-"]').forEach(canvas => {
      if (demoChartsReady.has(canvas.id)) return;
      const config = demoChartConfig(canvas.id);
      if (!config) return;
      demoChartsReady.add(canvas.id);
      new window.Chart(canvas, config);
    });
  }

  function drawVisibleDemoCharts() {
    // Solo los gráficos visibles al cargar; el resto se crea al abrir su panel.
    document.querySelectorAll('.demo-panel:not([hidden]) canvas[id^="demo-"], canvas#demo-home-chart').forEach(canvas => {
      ensureDemoCharts(canvas.closest('.demo-panel') || document);
    });
  }

  // La librería de gráficos pesa más que el resto de la portada junta, así que
  // no se descarga hasta que el visitante llega de verdad a la demo.
  let chartLibraryRequested = false;
  function loadChartLibrary() {
    if (chartLibraryRequested) return;
    chartLibraryRequested = true;
    if (typeof window.Chart === 'function') {
      drawVisibleDemoCharts();
      return;
    }
    const script = document.createElement('script');
    script.src = document.body.dataset.chartSrc || '/static/vendor/chart.umd.min.js';
    script.defer = true;
    script.addEventListener('load', drawVisibleDemoCharts);
    document.head.appendChild(script);
  }

  function initDemoChart() {
    const demo = document.querySelector('[data-product-demo]');
    if (!demo) return;
    // Sin IntersectionObserver (navegadores antiguos) se carga sin más.
    if (!('IntersectionObserver' in window)) {
      loadChartLibrary();
      return;
    }
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) {
        observer.disconnect();
        loadChartLibrary();
      }
    }, { rootMargin: '200px' });
    observer.observe(demo);
    // Cambiar de pestaña dentro de la demo también necesita la librería.
    demo.addEventListener('click', loadChartLibrary, { once: true });
  }

  function setBillingPeriod(period) {
    const annual = period === 'annual';
    document.querySelectorAll('[data-billing-toggle]').forEach(button => {
      const active = button.dataset.billingToggle === period;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    });

    document.querySelectorAll('[data-plan-price]').forEach(card => {
      const monthly = Number(card.dataset.monthly || 0);
      const annualPrice = Number(card.dataset.annual || monthly * 10);
      const saving = Number(card.dataset.saving || monthly * 2);
      const value = card.querySelector('[data-price-value]');
      const suffix = card.querySelector('[data-price-suffix]');
      const note = card.querySelector('[data-annual-note]');
      if (value) value.textContent = number(annual ? annualPrice : monthly);
      if (suffix) suffix.textContent = annual ? ' + IVA/año' : ' + IVA/mes';
      if (note) {
        note.hidden = !annual;
        note.replaceChildren();
        if (annual) {
          const badge = document.createElement('b');
          badge.textContent = '−8,3% · 1 mes gratis';
          const detail = document.createElement('span');
          detail.textContent = `Ahorras ${number(saving)} € al año · equivale a ${number(annualPrice / 12)} €/mes`;
          note.append(badge, detail);
        }
      }
    });

    // Con el registro cerrado los planes llevan al formulario de solicitud; con
    // el registro abierto, al alta. En ambos casos se conserva el plan elegido.
    document.querySelectorAll('.plan-start-link[data-plan]').forEach(link => {
      const plan = encodeURIComponent(link.dataset.plan);
      link.href = link.getAttribute('href').startsWith('/solicitar-acceso')
        ? `/solicitar-acceso?plan=${plan}`
        : `/onboarding?intent=trial&plan=${plan}&billing=${period}`;
    });
    document.querySelectorAll('.plan-buy-link[data-plan]').forEach(link => {
      link.href = `/onboarding?intent=subscribe&plan=${encodeURIComponent(link.dataset.plan)}&billing=${period}`;
    });
    document.querySelectorAll('[data-billing-field]').forEach(field => {
      field.value = period;
    });
  }

  function initBillingToggle() {
    const toggles = Array.from(document.querySelectorAll('[data-billing-toggle]'));
    if (!toggles.length) return;
    toggles.forEach(button => {
      button.addEventListener('click', () => setBillingPeriod(button.dataset.billingToggle));
    });
    const parent = toggles[0].closest('[data-initial-billing]');
    setBillingPeriod(parent?.dataset.initialBilling === 'annual' ? 'annual' : 'monthly');
  }

  window.addEventListener('DOMContentLoaded', () => {
    initProductDemo();
    initDemoChart();
    initBillingToggle();
  });
}());
