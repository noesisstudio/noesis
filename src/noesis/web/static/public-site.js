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

      const select = selected => {
        const key = selected.dataset.demoTab;
        tabs.forEach(tab => {
          const active = tab === selected;
          tab.classList.toggle('active', active);
          tab.setAttribute('aria-selected', String(active));
          tab.tabIndex = active ? 0 : -1;
        });
        panels.forEach(panel => {
          const active = panel.dataset.demoPanel === key;
          panel.classList.toggle('active', active);
          panel.hidden = !active;
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

  function initDemoChart() {
    const canvas = document.getElementById('demo-home-chart');
    if (!canvas || typeof window.Chart !== 'function') return;
    new window.Chart(canvas, {
      type: 'bar',
      data: {
        labels: ['Mar', 'Abr', 'May', 'Jun', 'Jul'],
        datasets: [
          { label: 'Ingresos', data: [3280, 3620, 4010, 4300, 4820], backgroundColor: '#2e8b74', borderRadius: 5, maxBarThickness: 18 },
          { label: 'Gastos', data: [1210, 1390, 1460, 1520, 1310], backgroundColor: '#d5a16a', borderRadius: 5, maxBarThickness: 18 },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: { legend: { display: false }, tooltip: { enabled: true } },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#74817c', font: { size: 9 } }, border: { display: false } },
          y: { display: false, beginAtZero: true },
        },
      },
    });
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

    document.querySelectorAll('.plan-start-link[data-plan]').forEach(link => {
      link.href = `/onboarding?plan=${encodeURIComponent(link.dataset.plan)}&billing=${period}`;
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
