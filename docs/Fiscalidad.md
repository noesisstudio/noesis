# Fiscalidad

Lo que hace que las facturas sean **legales y correctas**. Crítico: una factura mal
hecha le crea un problema con Hacienda al cliente.

## IVA
- General **21%**, reducido **10%**, superreducido **4%**, exento **0%**.
- Configurable por negocio (por defecto) y por factura. Implementado.

## IRPF (retención)
- Autónomos que facturan **a empresas** suelen aplicar retención: **15%**
  (o **7%** los tres primeros años de actividad).
- A particulares: normalmente **0%**.
- Fórmula implementada: **Total = base + IVA − IRPF retenido**.

## Verifactu / Ley Antifraude
- Obligatorio para autónomos desde **1-jul-2027** (plazo retrasado).
- **Fase 1 nativa** en `codex/verifactu-fase1`: registro de alta inalterable,
  huella SHA-256 encadenada, QR tributario, facturas rectificativas, eventos y
  exportación XML con la estructura de los XSD de la AEAT.
- La huella sigue el orden y formato del documento técnico AEAT 0.1.2; el QR sigue
  el documento técnico 0.5.0, mide 35 mm y usa corrección M.
- Algoritmo, tipo/versión de huella, versión de registro y URL de cotejo son
  configurables por entorno.
- **No hay remisión a la AEAT ni certificado digital en esta fase.** El modo está
  desactivado por defecto y no debe usarse fiscalmente en producción hasta completar
  la fase 2. Un sistema solo opera plenamente como «VERI*FACTU» cuando remite los
  registros según la normativa.
- Datos fiscales necesarios del negocio: NIF, dirección, nombre/razón social.
- También se debe configurar el NIF real del productor del software mediante
  `NOESIS_VERIFACTU_PRODUCER_NIF`; no existe un valor ficticio por defecto.

Fuentes técnicas:
- [Algoritmo de huella AEAT](https://www.agenciatributaria.es/static_files/AEAT_Desarrolladores/EEDD/IVA/VERI-FACTU/Veri-Factu_especificaciones_huella_hash_registros.pdf)
- [Especificaciones QR AEAT](https://www.agenciatributaria.es/static_files/AEAT_Desarrolladores/EEDD/IVA/VERI-FACTU/DetalleEspecificacTecnCodigoQRfactura.pdf)
- [Descripción de servicios y XML AEAT](https://sede.agenciatributaria.gob.es/static_files/AEAT_Desarrolladores/EEDD/IVA/VERI-FACTU/Veri-Factu_Descripcion_SWeb.pdf)

## Pendiente
- Fase 2: transmisión automática, certificado digital, respuestas y reintentos AEAT.
- Modelos estimados (303 IVA, 130 IRPF) como ayuda. Ver [[Roadmap]].
