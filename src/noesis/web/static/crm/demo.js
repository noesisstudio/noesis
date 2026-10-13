/* Demo del CRM con datos inventados. Solo se usa en las páginas que genera
 * `noesis/crm/demo.py`: la app real nunca carga este archivo.
 *
 * En la demo no hay servidor. Lo que en la app se guardaría, aquí se enseña en
 * pantalla y se dice que no se ha guardado; lo que en la app pide otra página
 * al servidor (una ficha, un filtro), aquí se resuelve con lo que ya está
 * cargado. Va antes que `crm.js`, que mira si existe `window.crmDemo`.
 */
(function () {
  'use strict';

  const root = document.querySelector('[data-crm-root]');
  if (!root) return;

  // ------------------------------------------------------------- avisos ---
  const tostada = document.createElement('div');
  tostada.className = 'crm-demo-aviso';
  tostada.setAttribute('role', 'status');
  tostada.setAttribute('aria-live', 'polite');
  tostada.hidden = true;
  document.body.appendChild(tostada);
  let reloj = null;

  function decir(mensaje) {
    tostada.textContent = mensaje;
    tostada.hidden = false;
    window.clearTimeout(reloj);
    reloj = window.setTimeout(() => { tostada.hidden = true; }, 4200);
  }

  function ir(ancla) {
    if (window.location.hash === '#' + ancla) {
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    } else {
      window.location.hash = ancla;
    }
  }

  // ------------------------------------------------------------ tablero ---
  function contar(columna, cambio) {
    const cifra = columna.querySelector('header .crm-num');
    if (!cifra) return;
    const ahora = Number(cifra.textContent.replace(/\D/g, '')) + cambio;
    cifra.textContent = ahora.toLocaleString('es-ES');
    const vacia = columna.querySelector('.crm-columna-vacia');
    if (vacia) vacia.hidden = ahora > 0;
  }

  window.crmDemo = {
    mover(tarjeta, columna) {
      const origen = tarjeta.closest('[data-crm-columna]');
      columna.querySelector('ul').prepend(tarjeta);
      tarjeta.dataset.crmEstado = columna.dataset.crmColumna;
      contar(origen, -1);
      contar(columna, 1);
      decir('Movida a «' + columna.querySelector('header b').textContent
        + '». En la app queda apuntado en su historial; en la demo no se guarda.');
    },
  };

  // ------------------------------------------------------------- fichas ---
  // Las fichas de quien sale en pantalla van en un archivo aparte, para no
  // cargar mil con cada página.
  let fichas = null;

  async function abrirFicha(id) {
    if (!fichas) {
      try {
        fichas = await (await fetch(root.dataset.crmDemoFichas)).json();
      } catch (e) {
        fichas = {};
      }
    }
    const hueco = document.querySelector('[data-crm-hueco-ficha]');
    if (!fichas[id] || !hueco) {
      decir('En la demo solo se abren las fichas de quien sale en esta página.');
      return;
    }
    // HTML generado por la propia app a partir de datos inventados.
    hueco.innerHTML = fichas[id];
    hueco.querySelectorAll('form[onsubmit]').forEach(f => f.removeAttribute('onsubmit'));
    if (window.crmRepintar) window.crmRepintar();
    ir('ficha');
  }

  // ------------------------------------------------------------ la lista ---
  function plano(texto) {
    return (texto || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  }

  function filtrarLista(formulario) {
    const busca = plano(formulario.q ? formulario.q.value.trim() : '');
    const estado = formulario.estado ? formulario.estado.value : '';
    const provincia = formulario.provincia ? plano(formulario.provincia.value) : '';
    let visibles = 0;
    document.querySelectorAll('[data-crm-fila]').forEach(fila => {
      const texto = plano(fila.textContent);
      const pasa = (!busca || texto.includes(busca))
        && (!estado || fila.dataset.estado === estado)
        && (!provincia || texto.includes(provincia));
      fila.hidden = !pasa;
      if (pasa) visibles += 1;
    });
    decir(visibles + ' coinciden entre los 50 de esta página. En la app se busca '
      + 'en toda la lista.');
  }

  // ------------------------------------------------------------ enlaces ---
  document.addEventListener('click', evento => {
    const enlace = evento.target.closest('a[href]');
    if (!enlace) return;
    const destino = enlace.getAttribute('href');
    if (enlace.matches('[data-crm-cerrar-ficha]')) {
      evento.preventDefault();
      ir('lista');
      return;
    }
    const ficha = /[?&]contacto=(\d+)/.exec(destino);
    if (ficha) {
      evento.preventDefault();
      abrirFicha(ficha[1]);
      return;
    }
    if (!destino.startsWith('/admin')) return;
    evento.preventDefault();
    const estado = /[?&]estado=([a-z]+)/.exec(destino);
    const formulario = document.querySelector('.crm-filtros');
    if (estado && formulario && formulario.estado) {
      formulario.estado.value = estado[1];
      filtrarLista(formulario);
      ir('lista');
    } else if (destino.includes('pagina=')) {
      decir('En la demo solo está la primera página de la lista.');
    } else if (destino.includes('#lista') && formulario) {
      formulario.reset();
      filtrarLista(formulario);
    } else {
      decir('Ese enlace lleva a otra parte del panel interno, que no está en la demo.');
    }
  });

  // --------------------------------------------------------- formularios ---
  const MENSAJES = [
    ['/toque', 'Anotado. En la app queda en el historial y, si cambia de estado, '
      + 'se mueve en el tablero.'],
    ['/hoja/conectar', 'En la app, aquí se lee tu hoja de Google y entran sus '
      + 'filas. La demo ya trae una lista inventada.'],
    ['/leer', 'En la app se vuelve a leer la hoja ahora mismo.'],
    ['/desconectar', 'En la app se deja de leer la hoja; los contactos se quedan.'],
    ['/hoja/enlace', 'En la app se crea la dirección y la fórmula para pegar en '
      + 'tu hoja.'],
    ['/importar', 'En la app entran en la lista los nombres pegados, sin duplicar.'],
    ['/nuevo', 'En la app se crea la ficha y se abre.'],
    ['/baja', 'En la app queda como «no contactar» y la hoja no lo readmite.'],
    ['/eliminar', 'En la app se borra con su historial y no vuelve desde la hoja.'],
    ['/logout', 'Estás en la demo: no hay sesión que cerrar.'],
  ];

  document.addEventListener('submit', evento => {
    const formulario = evento.target;
    const accion = formulario.getAttribute('action') || '';
    evento.preventDefault();
    if (formulario.matches('.crm-filtros')) {
      filtrarLista(formulario);
      return;
    }
    if (formulario.matches('.crm-zona')) {
      decir('La demo trae preparada la tanda de una sola zona.');
      return;
    }
    if (accion.endsWith('/admin/crm/tanda')) {
      const marcadas = formulario.querySelectorAll('input[name="ids"]:checked');
      if (!marcadas.length) {
        decir('Marca primero a quién le has escrito.');
        return;
      }
      marcadas.forEach(casilla => casilla.closest('tr').remove());
      decir(marcadas.length + ' apuntados como escritos. En la app pasan a '
        + '«Contactado» y vuelven a la semana; en la demo no se guarda.');
      return;
    }
    const mensaje = MENSAJES.find(par => accion.includes(par[0]));
    decir((mensaje ? mensaje[1] : 'En la app esto se guarda.')
      + ' En la demo no cambia nada.');
  }, true);

  document.addEventListener('change', evento => {
    if (evento.target.matches('[data-crm-enviar-al-cambiar]')) {
      decir('La demo trae preparada la tanda de una sola zona.');
    }
  });

  // Los `confirm()` de la app no se enseñan dentro de la demo.
  document.querySelectorAll('form[onsubmit]').forEach(f => f.removeAttribute('onsubmit'));
})();
