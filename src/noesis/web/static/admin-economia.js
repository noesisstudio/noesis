/* Panel de economía: mueve las palancas y repinta.
 *
 * El cálculo NO está aquí. Cada cambio pide el modelo al servidor
 * (`/admin/economia/datos`), que es el mismo `economics.py` que genera el Word y
 * el Excel. Tener una copia del modelo en JavaScript daría una página más rápida
 * y dos modelos que se separarían al primer cambio.
 *
 * La página ya llega pintada desde el servidor: esto solo la actualiza.
 */
(function () {
  'use strict';

  const root = document.querySelector('[data-eco-root]');
  if (!root) return;
  const NS = 'http://www.w3.org/2000/svg';
  const levers = Array.from(document.querySelectorAll('[data-eco-lever]'));
  // No dejar que el rango o su paso redondeen lo guardado al abrir la página.
  levers.forEach(el => {
    const saved = Number(el.getAttribute('value'));
    el.min = Math.min(Number(el.min), saved);
    el.max = Math.max(Number(el.max), saved);
    el.step = 'any';
    el.value = String(saved);
  });
  const base = new Map(levers.map(el => [el.dataset.ecoLever, el.value]));
  const initial = new URLSearchParams(window.location.search);
  const overrides = new Map(levers.filter(el => initial.has(el.dataset.ecoLever))
    .map(el => [el.dataset.ecoLever, el.value]));
  const originalOverrides = new Map(overrides);
  let ultimo = 0;

  // ------------------------------------------------------------- formato ---
  const nf = (d) => new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: d, maximumFractionDigits: d,
  });
  const eur = (v, d = 0) => (v === null || v === undefined)
    ? '—' : nf(d).format(v) + ' €';
  const num = (v) => (v === null || v === undefined) ? '—' : nf(0).format(v);
  const dec = (v) => (v === null || v === undefined) ? '—' : nf(1).format(v);

  function etiqueta(clave, valor) {
    const v = parseFloat(valor);
    if (clave === 'retirada') return eur(v);
    if (clave === 'horas_mes') return nf(0).format(v) + ' h';
    if (clave === 'churn_maduro') return nf(1).format(v * 100) + ' %';
    if (clave === 'soporte_medio') return nf(1).format(v) + ' min';
    if (clave === 'objetivo') return nf(0).format(v) + '/mes';
    if (clave === 'pct_implantacion') return nf(0).format(v * 100) + ' %';
    return valor;
  }

  function query() {
    const p = new URLSearchParams();
    overrides.forEach((value, key) => p.set(key, value));
    return p;
  }

  // -------------------------------------------------------------- SVG ------
  function mk(tag, attrs) {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) {
      if (attrs[k] !== null && attrs[k] !== undefined) n.setAttribute(k, attrs[k]);
    }
    return n;
  }
  function texto(svg, x, y, value, opts) {
    const o = opts || {};
    const t = mk('text', {
      x, y, 'text-anchor': o.anchor || 'middle', fill: o.fill || 'var(--muted)',
      'font-size': o.size || 11, 'font-weight': o.weight || 400,
    });
    t.textContent = value;
    svg.appendChild(t);
    return t;
  }
  function tick(v) {
    const a = Math.abs(v);
    if (a >= 1000) return nf(1).format(v / 1000) + 'k';
    return nf(0).format(v);
  }
  function ejes(svg, geo, yMin, yMax, sufijo) {
    const { W, H, PL, PR, PT, PB } = geo;
    for (let i = 0; i <= 4; i++) {
      const v = yMin + (yMax - yMin) * i / 4;
      const y = PT + (H - PT - PB) * (1 - i / 4);
      svg.appendChild(mk('line', {
        x1: PL, x2: W - PR, y1: y, y2: y, stroke: 'var(--border)', 'stroke-width': 1,
      }));
      texto(svg, PL - 8, y + 4, tick(v) + (sufijo || ''), { anchor: 'end' });
    }
    for (let m = 6; m <= 36; m += 6) {
      const x = PL + (W - PL - PR) * (m - 1) / 35;
      texto(svg, x, H - PB + 17, 'mes ' + m);
    }
  }

  function pintarCaja(d) {
    const svg = document.querySelector('[data-eco-svg="caja"]');
    if (!svg) return;
    svg.replaceChildren();
    const geo = { W: 720, H: 250, PL: 56, PR: 14, PT: 24, PB: 28 };
    const filas = d.rampa.filas;
    const vals = filas.map(f => f.caja).concat([0, d.caja_inicial]);
    const lo = Math.min.apply(null, vals);
    const hi = Math.max.apply(null, vals);
    const pad = (hi - lo) * 0.12 || 1000;
    const yMin = Math.min(0, lo - pad);
    const yMax = hi + pad;
    const Y = v => geo.PT + (geo.H - geo.PT - geo.PB) * (1 - (v - yMin) / (yMax - yMin));
    const X = i => geo.PL + (geo.W - geo.PL - geo.PR) * i / 35;

    ejes(svg, geo, yMin, yMax, ' €');
    const y0 = Y(0);
    const linea = filas.map((f, i) => (i ? 'L' : 'M') + X(i) + ' ' + Y(f.caja)).join(' ');
    const area = linea + ' L' + X(35) + ' ' + y0 + ' L' + X(0) + ' ' + y0 + ' Z';

    const defs = mk('defs', {});
    [['eco-arriba', 0, Math.max(0, y0)],
     ['eco-abajo', y0, Math.max(0, geo.H - y0)]].forEach(([id, y, h]) => {
      const cp = mk('clipPath', { id });
      cp.appendChild(mk('rect', { x: 0, y, width: geo.W, height: h }));
      defs.appendChild(cp);
    });
    svg.appendChild(defs);
    svg.appendChild(mk('path', { d: area, fill: '#e2f1ea', 'clip-path': 'url(#eco-arriba)' }));
    svg.appendChild(mk('path', { d: area, fill: '#f7e8e3', 'clip-path': 'url(#eco-abajo)' }));
    svg.appendChild(mk('line', {
      x1: geo.PL, x2: geo.W - geo.PR, y1: y0, y2: y0,
      stroke: 'var(--border-strong)', 'stroke-width': 1.5,
    }));
    svg.appendChild(mk('path', {
      d: linea, fill: 'none', stroke: 'var(--brand-2)', 'stroke-width': 2,
      'stroke-linejoin': 'round', 'stroke-linecap': 'round',
    }));

    // Solo dos etiquetas directas: las dos cifras que deciden algo.
    let iMin = 0;
    filas.forEach((f, i) => { if (f.caja < filas[iMin].caja) iMin = i; });
    const xm = X(iMin);
    const ym = Y(filas[iMin].caja);
    svg.appendChild(mk('circle', {
      cx: xm, cy: ym, r: 4, fill: 'var(--red)', stroke: 'var(--surface)', 'stroke-width': 2,
    }));
    texto(svg, Math.min(geo.W - geo.PR - 55, Math.max(geo.PL + 45, xm)), ym + 19,
      'mínimo ' + eur(filas[iMin].caja), { fill: 'var(--red)', size: 12, weight: 600 });
    if (d.rampa.mes_positivo) {
      const xp = X(d.rampa.mes_positivo - 1);
      svg.appendChild(mk('line', {
        x1: xp, x2: xp, y1: geo.PT - 6, y2: geo.H - geo.PB,
        stroke: 'var(--brand)', 'stroke-width': 1, 'stroke-dasharray': '3 3',
      }));
      texto(svg, Math.min(geo.W - geo.PR - 4, xp + 6), geo.PT - 10,
        'mes ' + d.rampa.mes_positivo, { anchor: 'start', fill: 'var(--brand)', size: 12, weight: 600 });
    }
  }

  function pintarHoras(d) {
    const svg = document.querySelector('[data-eco-svg="horas"]');
    if (!svg) return;
    svg.replaceChildren();
    const geo = { W: 720, H: 200, PL: 56, PR: 14, PT: 18, PB: 28 };
    const filas = d.rampa.filas;
    const hi = Math.max(d.horas_mes, Math.max.apply(null, filas.map(f => f.horas)));
    const yMax = Math.ceil(hi * 1.15 / 10) * 10 || 10;
    const Y = v => geo.PT + (geo.H - geo.PT - geo.PB) * (1 - v / yMax);
    const X = i => geo.PL + (geo.W - geo.PL - geo.PR) * i / 35;

    ejes(svg, geo, 0, yMax, ' h');
    svg.appendChild(mk('rect', {
      x: geo.PL, y: Y(d.horas_mes), width: geo.W - geo.PL - geo.PR,
      height: Math.max(0, Y(d.horas_mes * 0.7) - Y(d.horas_mes)),
      fill: '#f5edd6', opacity: .6,
    }));
    svg.appendChild(mk('line', {
      x1: geo.PL, x2: geo.W - geo.PR, y1: Y(d.horas_mes), y2: Y(d.horas_mes),
      stroke: 'var(--faint)', 'stroke-width': 2, 'stroke-dasharray': '5 4',
    }));
    texto(svg, geo.W - geo.PR, Y(d.horas_mes) - 6, nf(0).format(d.horas_mes) + ' h disponibles',
      { anchor: 'end' });
    svg.appendChild(mk('path', {
      d: filas.map((f, i) => (i ? 'L' : 'M') + X(i) + ' ' + Y(f.horas)).join(' '),
      fill: 'none', stroke: 'var(--brand)', 'stroke-width': 2,
      'stroke-linejoin': 'round', 'stroke-linecap': 'round',
    }));
    if (d.rampa.mes_ahogo) {
      const xa = X(d.rampa.mes_ahogo - 1);
      const ya = Y(filas[d.rampa.mes_ahogo - 1].horas);
      svg.appendChild(mk('circle', {
        cx: xa, cy: ya, r: 4, fill: 'var(--amber)', stroke: 'var(--surface)', 'stroke-width': 2,
      }));
      texto(svg, Math.min(geo.W - geo.PR - 62, xa + 8), ya - 9,
        '70 % en el mes ' + d.rampa.mes_ahogo,
        { anchor: 'start', fill: 'var(--amber)', size: 12, weight: 600 });
    }
  }

  // ------------------------------------------------------------ render ----
  function pintar(d) {
    const eq = d.equilibrios.find(n => n.clave) || d.equilibrios[2];
    const cabe = d.cabe_en_horas;
    const r = d.rampa;

    const parte = document.querySelector('[data-eco-parte]');
    if (parte) {
      const minima = r.caja_minima || 0;
      const falta = minima < 0 ? Math.abs(minima) : 0;
      const cuando = r.mes_positivo
        ? 'Se llega en el <b>mes ' + r.mes_positivo + '</b>'
        : '<b class="red">No se llega dentro de 36 meses</b>';
      const caja = falta > 0
        ? ', y la caja baja hasta <b class="red">' + eur(minima) + '</b>: faltan '
          + eur(falta) + ' adicionales a la caja inicial. El plan no es financiable.'
        : ', y la caja mínima queda en <b>' + eur(minima)
          + '</b>. La caja inicial cubre esta proyección de 36 meses.';
      parte.innerHTML = (eq.cuentas === null
        ? '<b>No hay equilibrio con esta contribución por cuenta.</b> '
        : '<b>' + num(eq.cuentas) + ' cuentas</b> cubren la estructura, '
          + 'la cuota de autónomos y lo que quieres cobrar. ') + cuando + caja;
    }

    const steps = document.querySelector('[data-eco-steps]');
    if (steps) {
      steps.innerHTML = d.equilibrios.map((n, i) =>
        '<li class="eco-step' + (n.clave ? ' key' : '') + '">'
        + '<span class="eco-tier">' + (i + 1) + '</span>'
        + '<span class="eco-what">' + n.nivel + '<small>' + eur(n.coste)
        + ' al mes · contribución ' + eur(n.contribucion, 2) + ' · ' + n.nota
        + '</small></span>'
        + '<span class="eco-count">' + num(n.cuentas) + '<small>cuentas</small></span></li>'
      ).join('');
    }

    const nota = document.querySelector('[data-eco-horas]');
    if (nota) {
      nota.className = 'eco-note ' + (['no', 'sin_equilibrio'].includes(cabe.estado) ? 'bad'
        : cabe.estado === 'justo' ? 'warn' : 'ok');
      nota.innerHTML = cabe.estado === 'sin_equilibrio'
        ? '<b>No hay equilibrio con estos supuestos.</b> Cada cuenta tiene una contribución nula o negativa; disponer de más horas no lo resuelve.'
        : cabe.estado === 'no'
        ? '<b>No te dan las horas.</b> Atender esas ' + num(cabe.cuentas)
          + ' cuentas costaría ' + dec(cabe.horas) + ' h al mes y solo tienes '
          + nf(0).format(d.horas_mes) + ': llegarías al equilibrio sin una hora libre '
          + 'para haberlo vendido.'
        : '<b>' + (cabe.estado === 'justo' ? 'Cabe, pero justo.' : 'Cabe en tus horas.')
          + '</b> Atender esas ' + num(cabe.cuentas) + ' cuentas ocuparía '
          + dec(cabe.horas) + ' h al mes y quedarían ' + dec(cabe.libres)
          + ' para vender, unas ' + num(cabe.altas_posibles) + ' altas. El techo '
          + 'absoluto está en ' + num(d.capacidad.techo) + ' cuentas, cuando el '
          + 'soporte se come el mes entero.';
    }

    const badge = document.querySelector('[data-eco-badge]');
    if (badge) {
      const ok = r.financiable;
      badge.textContent = ok ? 'financiable con la caja actual' : 'no financiable';
      badge.className = 'badge ' + (ok ? 'b-green' : 'b-amber');
    }

    const capCaja = document.querySelector('[data-eco-cap="caja"]');
    if (capCaja) {
      capCaja.textContent = r.mes_positivo
        ? 'Primer mes en positivo: el ' + r.mes_positivo + '. Salida de caja de '
          + eur(r.salida_mensual) + ' al mes. Vida media ' + dec(d.vida_media)
          + ' meses, LTV ' + eur(d.ltv_caja) + ' y LTV/CAC '
          + dec(d.ltv_cac) + 'x.'
        : 'Con estos supuestos la caja no se recupera dentro de los 36 meses.';
    }
    const capHoras = document.querySelector('[data-eco-cap="horas"]');
    if (capHoras) {
      const frenados = r.filas.filter(f => f.frenado).length;
      capHoras.textContent = (r.mes_ahogo
        ? 'En el mes ' + r.mes_ahogo + ' el soporte ya ocupa el 70 % de tus horas. '
        : 'El soporte no llega al 70 % de tus horas en 36 meses. ')
        + (frenados ? frenados + ' de los 36 meses cierran menos altas de las que '
          + 'te propones, por falta de horas y no de mercado. ' : '')
        + 'Al mes 36 la cartera llega a ' + num(Math.round(r.cuentas_final)) + ' cuentas.';
    }

    pintarCaja(d);
    pintarHoras(d);
  }

  // ------------------------------------------------------------ fetch -----
  async function refrescar() {
    const p = query();
    // Las descargas tienen que reflejar lo que hay en pantalla.
    document.querySelectorAll('[data-eco-download]').forEach(a => {
      a.href = '/admin/economia/resumen.' + a.dataset.ecoDownload + '?' + p.toString();
    });
    const marca = ++ultimo;
    root.dataset.ecoBusy = '1';
    try {
      const res = await fetch('/admin/economia/datos?' + p.toString(),
        { headers: { 'Accept': 'application/json' }, credentials: 'same-origin' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const d = await res.json();
      if (marca !== ultimo) return;  // llegó tarde: hay una petición más nueva
      pintar(d);
    } catch (e) {
      if (marca !== ultimo) return;
      const nota = document.querySelector('[data-eco-horas]');
      if (nota) {
        nota.className = 'eco-note warn';
        nota.textContent = 'No se ha podido recalcular. Las cifras de arriba son las '
          + 'de la última lectura buena; recarga la página para volver a empezar.';
      }
    } finally {
      if (marca === ultimo) root.dataset.ecoBusy = '0';
    }
  }

  let debounce = null;
  function alMover(el) {
    overrides.set(el.dataset.ecoLever, el.value);
    const salida = document.querySelector('[data-eco-out="' + el.dataset.ecoLever + '"]');
    if (salida) salida.textContent = etiqueta(el.dataset.ecoLever, el.value);
    clearTimeout(debounce);
    debounce = setTimeout(refrescar, 160);
  }

  levers.forEach(el => {
    const salida = document.querySelector('[data-eco-out="' + el.dataset.ecoLever + '"]');
    if (salida) salida.textContent = etiqueta(el.dataset.ecoLever, el.value);
    el.addEventListener('input', () => alMover(el));
  });

  const reset = document.querySelector('[data-eco-reset]');
  if (reset) {
    reset.addEventListener('click', () => {
      overrides.clear();
      originalOverrides.forEach((value, key) => overrides.set(key, value));
      levers.forEach(el => {
        el.value = base.get(el.dataset.ecoLever);
        const salida = document.querySelector('[data-eco-out="' + el.dataset.ecoLever + '"]');
        if (salida) salida.textContent = etiqueta(el.dataset.ecoLever, el.value);
      });
      refrescar();
    });
  }

  // Primer pintado: la página llega con las tablas del servidor, pero los
  // gráficos y el parte los arma esto.
  refrescar();
}());
