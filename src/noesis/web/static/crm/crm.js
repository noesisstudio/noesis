/* CRM de captación: apartados, guiones, portapapeles, tablero y gráficos.
 *
 * Todo lo que decide algo —el embudo, qué toca hoy, los números de los
 * gráficos— se calcula en el servidor (`sales.py` y `crm/panel.py`). Aquí solo
 * está lo que no puede estar en otro sitio: enseñar un apartado cada vez, el
 * portapapeles, arrastrar una tarjeta, lo que sale al pasar por una barra y
 * recordar con qué nombre firmas.
 *
 * Sin este archivo la página se lee y se usa igual: los apartados van uno
 * debajo de otro, cada gráfico trae su tabla y el estado se cambia en la ficha.
 *
 * Casi todo escucha en el documento y no en cada botón: así una ficha que se
 * pinte después de cargar funciona sin volver a enganchar nada.
 *
 * `window.crmDemo` solo existe en la demo con datos inventados (`crm/demo.py`):
 * allí no hay servidor, y lo que aquí se guardaría se enseña y nada más.
 */
(function () {
  'use strict';

  const root = document.querySelector('[data-crm-root]');
  if (!root) return;
  const CLAVE_FIRMA = 'noesis.crm.firma';

  // --------------------------------------------------------- apartados ---
  // Cada apartado es una sección con su ancla. Lo que manda es la dirección:
  // `#tanda` abre «Hoy y tanda» y baja hasta la tanda, y el servidor ya
  // redirige con esas mismas anclas después de guardar algo.
  const barra = document.querySelector('[data-crm-pestanas]');
  const apartados = Array.from(document.querySelectorAll('[data-crm-pestana]'));

  function abrir(nombre) {
    apartados.forEach(apartado => {
      apartado.hidden = apartado.dataset.crmPestana !== nombre;
    });
    barra.querySelectorAll('[data-crm-ir]').forEach(enlace => {
      if (enlace.dataset.crmIr === nombre) {
        enlace.setAttribute('aria-current', 'page');
        enlace.hidden = false;
      } else {
        enlace.removeAttribute('aria-current');
      }
    });
  }

  function segunDireccion(desplazar) {
    let destino = null;
    try {
      const ancla = decodeURIComponent(window.location.hash.slice(1));
      destino = ancla ? document.getElementById(ancla) : null;
    } catch (e) { /* ancla mal escrita: se abre el resumen */ }
    const apartado = destino && destino.closest('[data-crm-pestana]');
    abrir(apartado ? apartado.dataset.crmPestana : 'resumen');
    if (desplazar && destino && destino !== apartado) {
      destino.scrollIntoView({ block: 'start' });
    } else if (desplazar && apartado) {
      barra.scrollIntoView({ block: 'start' });
    }
  }

  if (barra && apartados.length) {
    root.classList.add('con-pestanas');
    window.addEventListener('hashchange', () => segunDireccion(true));
    segunDireccion(Boolean(window.location.hash));
  }

  // ------------------------------------------------------------- firma ---
  function entradaFirma() {
    return document.querySelector('[data-crm-yo-input]');
  }

  function firma() {
    const entrada = entradaFirma();
    if (entrada && entrada.value.trim()) return entrada.value.trim();
    return root.dataset.crmYo || '';
  }

  // ------------------------------------------------------------ guiones ---
  function rellenar(plantilla, caja) {
    return (plantilla || '')
      .replaceAll('{nombre}', caja.dataset.nombre || '')
      .replaceAll('{yo}', firma())
      .replaceAll('{quien}', caja.dataset.quien || '…')
      .replaceAll('{oficio}', caja.dataset.oficio || 'tu oficio')
      .replaceAll('{zona}', caja.dataset.zona || 'la zona')
      .replaceAll('{novedad}', '…');
  }

  function pintarGuiones() {
    const entrada = entradaFirma();
    if (entrada && !entrada.dataset.crmLista) {
      entrada.dataset.crmLista = 'si';
      try {
        const guardada = window.localStorage.getItem(CLAVE_FIRMA);
        if (guardada) entrada.value = guardada;
      } catch (e) { /* navegador sin almacenamiento: se usa el del servidor */ }
    }
    document.querySelectorAll('[data-crm-guion]').forEach(caja => {
      const texto = caja.querySelector('[data-crm-texto]');
      if (!texto) return;
      const lengua = caja.dataset.lengua || 'es';
      texto.textContent = rellenar(texto.dataset[lengua], caja);
      const asunto = caja.querySelector('[data-crm-asunto]');
      if (asunto) asunto.textContent = asunto.dataset[lengua] || '';
      caja.querySelectorAll('[data-crm-lengua]').forEach(boton => {
        boton.setAttribute('aria-pressed',
          boton.dataset.crmLengua === lengua ? 'true' : 'false');
      });
    });
  }

  document.addEventListener('input', evento => {
    if (!evento.target.matches('[data-crm-yo-input]')) return;
    try { window.localStorage.setItem(CLAVE_FIRMA, evento.target.value.trim()); }
    catch (e) { /* da igual: el texto ya se ha repintado */ }
    pintarGuiones();
  });

  // ----------------------------------------------------------- copiar ---
  async function copiar(origen, boton) {
    const original = boton.textContent;
    try {
      await navigator.clipboard.writeText(origen.textContent.trim());
      boton.textContent = 'Copiado';
    } catch (e) {
      // Sin permiso de portapapeles: se selecciona para copiar a mano.
      const rango = document.createRange();
      rango.selectNodeContents(origen);
      const seleccion = window.getSelection();
      seleccion.removeAllRanges();
      seleccion.addRange(rango);
      boton.textContent = 'Selecciona y copia';
    }
    window.setTimeout(() => { boton.textContent = original; }, 2000);
  }

  document.addEventListener('click', evento => {
    const lengua = evento.target.closest('[data-crm-lengua]');
    if (lengua) {
      lengua.closest('[data-crm-guion]').dataset.lengua = lengua.dataset.crmLengua;
      pintarGuiones();
      return;
    }
    const guion = evento.target.closest('[data-crm-copiar]');
    if (guion) {
      copiar(guion.closest('[data-crm-guion]').querySelector('[data-crm-texto]'), guion);
      return;
    }
    // Un correo o un asunto: lo que se pega en el programa de correo.
    const dato = evento.target.closest('[data-crm-copiar-texto]');
    if (dato) {
      const caja = dato.closest('.crm-copiable, .crm-formula');
      const origen = caja && caja.querySelector('[data-crm-copia]');
      if (origen) copiar(origen, dato);
    }
  });

  // ------------------------------------------------------------ tanda ---
  document.addEventListener('change', evento => {
    if (evento.target.matches('[data-crm-marcar-todos]')) {
      evento.target.closest('form').querySelectorAll('input[name="ids"]')
        .forEach(casilla => { casilla.checked = evento.target.checked; });
    } else if (evento.target.matches('[data-crm-enviar-al-cambiar]')
               && !window.crmDemo) {
      evento.target.form.submit();
    }
  });

  // ---------------------------------------------------------- tablero ---
  // Arrastrar una tarjeta a otra columna cambia su estado en el servidor y
  // recarga: así el embudo, las cifras y la lista dicen lo mismo que el tablero.
  const tablero = document.querySelector('[data-crm-tablero]');
  const aviso = document.querySelector('[data-crm-tablero-aviso]');

  function avisar(mensaje) {
    if (!aviso) return;
    aviso.textContent = mensaje;
    aviso.hidden = !mensaje;
  }

  async function moverEnServidor(tarjeta, columna) {
    const datos = new FormData();
    datos.append('estado', columna.dataset.crmColumna);
    const respuesta = await fetch(
      '/admin/crm/' + encodeURIComponent(tarjeta.dataset.crmTarjeta) + '/mover',
      { method: 'POST', body: datos, credentials: 'same-origin' });
    const cuerpo = await respuesta.json().catch(() => ({}));
    if (!respuesta.ok) {
      throw new Error(cuerpo.error || 'No se ha podido mover. Prueba desde la ficha.');
    }
    window.location.reload();
  }

  if (tablero) {
    let arrastrada = null;
    tablero.addEventListener('dragstart', evento => {
      const tarjeta = evento.target.closest('[data-crm-tarjeta]');
      if (!tarjeta) return;
      arrastrada = tarjeta;
      tarjeta.classList.add('arrastrando');
      evento.dataTransfer.effectAllowed = 'move';
      evento.dataTransfer.setData('text/plain', tarjeta.dataset.crmTarjeta);
    });
    tablero.addEventListener('dragend', () => {
      if (arrastrada) arrastrada.classList.remove('arrastrando');
      tablero.querySelectorAll('.encima').forEach(c => c.classList.remove('encima'));
    });
    tablero.querySelectorAll('[data-crm-columna]').forEach(columna => {
      columna.addEventListener('dragover', evento => {
        if (!arrastrada) return;
        evento.preventDefault();
        columna.classList.add('encima');
      });
      columna.addEventListener('dragleave', evento => {
        if (!columna.contains(evento.relatedTarget)) columna.classList.remove('encima');
      });
      columna.addEventListener('drop', async evento => {
        evento.preventDefault();
        columna.classList.remove('encima');
        const tarjeta = arrastrada;
        arrastrada = null;
        if (!tarjeta || tarjeta.dataset.crmEstado === columna.dataset.crmColumna) return;
        avisar('');
        try {
          if (window.crmDemo) window.crmDemo.mover(tarjeta, columna);
          else await moverEnServidor(tarjeta, columna);
        } catch (e) {
          avisar(e instanceof TypeError
            ? 'No se ha podido mover: no hay conexión. Prueba otra vez.'
            : e.message);
        }
      });
    });
  }

  // --------------------------------------------- lo que dice cada marca ---
  // Una sola caja para todos los gráficos. Sale con el ratón y con el teclado,
  // y solo repite lo que ya está en la tabla de debajo. Se rellena con
  // `textContent`: los nombres vienen de una hoja que escriben terceros.
  const marcas = document.querySelectorAll('[data-crm-tip]');
  if (marcas.length) {
    const caja = document.createElement('div');
    caja.className = 'crm-tip';
    caja.setAttribute('role', 'tooltip');
    caja.hidden = true;
    const valor = document.createElement('b');
    const titulo = document.createElement('span');
    caja.append(valor, titulo);
    document.body.appendChild(caja);

    function colocar(x, y) {
      const margen = 12;
      const ancho = caja.offsetWidth;
      const alto = caja.offsetHeight;
      let izquierda = x + margen;
      let arriba = y - alto - margen;
      if (izquierda + ancho > window.innerWidth - 8) izquierda = x - ancho - margen;
      if (arriba < 8) arriba = y + margen;
      caja.style.left = Math.max(8, izquierda) + 'px';
      caja.style.top = arriba + 'px';
    }

    function mostrar(marca, x, y) {
      valor.textContent = marca.dataset.crmTipValor || '';
      titulo.textContent = marca.dataset.crmTip || '';
      caja.hidden = false;
      colocar(x, y);
    }

    marcas.forEach(marca => {
      marca.setAttribute('aria-label',
        (marca.dataset.crmTip || '') + ': ' + (marca.dataset.crmTipValor || ''));
      marca.addEventListener('pointermove', e => mostrar(marca, e.clientX, e.clientY));
      marca.addEventListener('pointerleave', () => { caja.hidden = true; });
      marca.addEventListener('focus', () => {
        const r = marca.getBoundingClientRect();
        mostrar(marca, r.left + r.width / 2, r.top);
      });
      marca.addEventListener('blur', () => { caja.hidden = true; });
    });
  }

  pintarGuiones();
  // Para lo que se pinta después de cargar (la ficha de la demo).
  window.crmRepintar = pintarGuiones;
  window.crmAbrir = nombre => { if (barra) abrir(nombre); };
})();
