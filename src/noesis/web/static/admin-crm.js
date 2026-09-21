/* CRM de captación: cambiar de lengua, copiar el guion y filtrar la lista.
 *
 * Todo lo que decide algo —el embudo, qué toca hoy, si hay que informar a
 * alguien— se calcula en el servidor (`sales.py`). Aquí solo está lo que no
 * puede estar en otro sitio: el portapapeles, el filtro y recordar con qué
 * nombre firmas.
 */
(function () {
  'use strict';

  const root = document.querySelector('[data-crm-root]');
  if (!root) return;
  const CLAVE_FIRMA = 'noesis.crm.firma';

  // ------------------------------------------------------------- firma ---
  const entrada = document.querySelector('[data-crm-yo-input]');

  function firma() {
    if (entrada && entrada.value.trim()) return entrada.value.trim();
    return root.dataset.crmYo || '';
  }

  try {
    const guardada = window.localStorage.getItem(CLAVE_FIRMA);
    if (guardada && entrada) entrada.value = guardada;
  } catch (e) { /* navegador sin almacenamiento: se usa el del servidor */ }

  if (entrada) {
    entrada.addEventListener('input', () => {
      try { window.localStorage.setItem(CLAVE_FIRMA, entrada.value.trim()); }
      catch (e) { /* da igual: el texto ya se ha repintado */ }
      pintarGuiones();
    });
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
    document.querySelectorAll('[data-crm-guion]').forEach(caja => {
      const texto = caja.querySelector('[data-crm-texto]');
      if (!texto) return;
      const lengua = caja.dataset.lengua || 'es';
      texto.textContent = rellenar(texto.dataset[lengua], caja);
      caja.querySelectorAll('[data-crm-lengua]').forEach(boton => {
        boton.setAttribute('aria-pressed',
          boton.dataset.crmLengua === lengua ? 'true' : 'false');
      });
    });
  }

  document.querySelectorAll('[data-crm-guion]').forEach(caja => {
    caja.querySelectorAll('[data-crm-lengua]').forEach(boton => {
      boton.addEventListener('click', () => {
        caja.dataset.lengua = boton.dataset.crmLengua;
        pintarGuiones();
      });
    });
    const copiar = caja.querySelector('[data-crm-copiar]');
    if (copiar) {
      copiar.addEventListener('click', async () => {
        const texto = caja.querySelector('[data-crm-texto]').textContent;
        const original = copiar.textContent;
        try {
          await navigator.clipboard.writeText(texto);
          copiar.textContent = 'Copiado';
        } catch (e) {
          // Sin permiso de portapapeles: se selecciona para copiar a mano.
          const rango = document.createRange();
          rango.selectNodeContents(caja.querySelector('[data-crm-texto]'));
          const seleccion = window.getSelection();
          seleccion.removeAllRanges();
          seleccion.addRange(rango);
          copiar.textContent = 'Selecciona y copia';
        }
        window.setTimeout(() => { copiar.textContent = original; }, 2000);
      });
    }
  });
  pintarGuiones();

  // ------------------------------------------------------------- filtro ---
  const filtro = document.querySelector('[data-crm-filtro]');
  if (filtro) {
    filtro.addEventListener('change', () => {
      const valor = filtro.value;
      document.querySelectorAll('[data-crm-fila]').forEach(fila => {
        fila.hidden = Boolean(valor) && fila.dataset.estado !== valor;
      });
    });
  }
})();
