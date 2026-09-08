# Análisis de riesgos y cribado de EIPD

> - Creado: 2026-09-08 · Última revisión: 2026-09-08 · Próxima revisión: 2027-03-08
> - Responsable: founder (Xavier).
> - Base: art. 32 (medidas apropiadas al riesgo) y art. 35 (evaluación de impacto).

## 1. Método

Riesgo = probabilidad × impacto **sobre las personas afectadas**, no sobre la
empresa. Un incidente que arruine la reputación de Noesis pero no dañe a nadie es
menos grave, a efectos del RGPD, que una fuga pequeña de datos de trabajadores.

Escala: bajo / medio / alto. Se registra el riesgo *residual*, es decir, el que
queda después de los controles ya implantados.

## 2. Riesgos evaluados

| # | Riesgo | Impacto en las personas | Controles actuales | Residual | Acción |
|---|---|---|---|---|---|
| 1 | Acceso cruzado entre negocios | Alto: un autónomo vería clientes y facturas de otro | `business_id` obligatorio, FK compuestas, suite de aislamiento | Medio | Pentest externo autenticado (P1) |
| 2 | Pérdida total del proveedor | Alto: negocio sin agenda, cobros ni facturas | Copias diarias verificadas | **Alto** hasta sacar la copia fuera | P0 §6 del Plan |
| 3 | Ransomware con credencial del servidor | Alto | Copias verificadas, pero borrables desde la misma cuenta | **Alto** | Copia inmutable y credencial de solo escritura (P0) |
| 4 | Fuga de la copia de seguridad | Alto: contiene todo | Cifrado del proveedor | Medio | Cifrado en cliente (P0) |
| 5 | Robo de sesión | Medio-alto | Cookie `__Host-`, rotación, caducidad, límite de intentos | Bajo | Verificar en el proxy real |
| 6 | Documento con datos de salud subido por el cliente | Alto: art. 9 | Instrucción en el DPA; sin indexación innecesaria | Medio | No técnicamente evitable; asumido y documentado |
| 7 | Envío de datos a IA externa sin consentimiento válido | Medio-alto | Consentimiento por negocio, enrutado local primero | Bajo-medio | Que el consentimiento indique proveedor y país |
| 8 | Fuga por logs | Medio | Log estructurado sin query string, cuerpo, token ni datos personales | Bajo | Fijar retención de 30 días en el proveedor |
| 9 | Archivo malicioso subido | Medio | Firma real, límites de tamaño/páginas/píxeles, ClamAV en streaming | Medio | Desplegar el daemon en fallo cerrado |
| 10 | Superusuario de la base del proveedor | Alto | Ninguno efectivo | Medio-alto | Cifrado de columna del IBAN; proveedor UE |
| 11 | Abuso de la cuenta de administración | Alto | Sesión corta, Google OAuth obligatorio, bitácora encadenada | Bajo-medio | Verificación en dos pasos comprobada en la cuenta Google |
| 12 | Caída no detectada | Medio | Healthcheck del proveedor | Medio | Monitor externo (P1) |
| 13 | Clave de cifrado de copias perdida | Alto: copias irrecuperables | Aún no existe la clave | — | Custodia doble y prueba de descifrado trimestral |

## 3. Cribado de evaluación de impacto (art. 35)

¿Hace falta una EIPD completa? Se contrastan los criterios del art. 35.3 y la
lista de la AEPD:

| Criterio | ¿Concurre? | Motivo |
|---|---|---|
| Evaluación sistemática y automatizada con efectos jurídicos | No | La IA propone; la persona confirma cobros, fiscalidad y acciones irreversibles |
| Tratamiento a gran escala de categorías especiales | No | No se tratan de forma deliberada; el riesgo 6 es incidental |
| Observación sistemática de zona de acceso público | No | — |
| Datos de trabajadores en relación de subordinación | **Sí** | Fichajes y registro de jornada |
| Uso de tecnologías innovadoras | Parcial | OCR y modelos de lenguaje sobre texto de negocio |
| Impedimento del ejercicio de un derecho o de un contrato | No | — |

**Conclusión.** No concurren dos o más criterios de alto riesgo a gran escala, así
que no procede una EIPD completa hoy. Sí procede este análisis documentado y una
vigilancia específica sobre los fichajes.

**Se rehace este cribado** si: se activa geolocalización continua en los fichajes,
se introduce cualquier automatismo que decida sobre un trabajador sin intervención
humana, se supera el centenar de negocios, o se incorpora perfilado o scoring de
clientes. El primero de esos supuestos acercaría además el producto al anexo III
del Reglamento (UE) 2024/1689 de IA, categoría de alto riesgo por gestión de
personal: es el límite de diseño que no conviene cruzar sin asesoría.

## 4. Riesgos aceptados por escrito

Los riesgos 2, 3 y 4 permanecen en alto hasta completar los P0 del plan. Mientras
sigan en alto, **no deben tratarse datos reales de clientes de terceros a escala**.
Es la línea que separa un piloto controlado de un problema notificable.
