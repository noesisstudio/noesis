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
- **No lo construimos**: se integra vía API de Holded/Quipu, ya homologados.
  Ver [[Arquitectura]] (adaptador de facturación) y [[Decisiones]].
- Datos fiscales necesarios del negocio: NIF, dirección, nombre/razón social.

## Pendiente
- Integración real Holded (hoy emisión simulada).
- Modelos estimados (303 IVA, 130 IRPF) como ayuda. Ver [[Roadmap]].
