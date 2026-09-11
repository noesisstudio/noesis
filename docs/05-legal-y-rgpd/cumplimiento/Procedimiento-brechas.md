# Procedimiento ante violaciones de seguridad

> - Creado: 2026-09-08 · Última revisión: 2026-09-08 · Próxima revisión: 2027-03-08
> - Responsable: founder (Xavier). Sustituto: [nombrar antes del piloto].
> - Base: arts. 33 y 34 RGPD. El reloj de 72 horas empieza cuando se **tiene
>   conocimiento** de la brecha, no cuando se termina de investigar.

## 0. Antes de que pase nada

Que esté escrito y a mano: quién decide, a qué hora se le localiza, y desde qué
dispositivo se puede entrar al proveedor si el portátil habitual no está
disponible. Un procedimiento que solo funciona en horario de oficina no funciona.

## 1. Reloj

| Momento | Plazo | Qué hay que tener |
|---|---|---|
| T+0 | Conocimiento de la brecha | Anotar hora exacta y quién la detecta |
| T+1 h | Contención | Credencial o integración afectada desactivada |
| T+4 h | Alcance preliminar | Qué negocios, qué categorías, cuántas personas |
| T+24 h | Decisión de notificar | Con criterio de riesgo del § 3 |
| **T+72 h** | **Notificación a la AEPD** si hay riesgo | [`plantillas/Notificacion-brecha-AEPD`](plantillas/Notificacion-brecha-AEPD.md) |
| Sin demora indebida | Comunicación a los interesados | Si el riesgo es **alto** (art. 34) |

Si Noesis actúa como **encargado**, la obligación es distinta y más rápida:
avisar **sin dilación indebida al negocio responsable** en cuanto se conozca. Es
el negocio quien notifica a la AEPD, no Noesis. Este matiz cambia a quién se
llama primero, así que conviene tenerlo claro de antemano.

## 2. Pasos

1. **Contener** sin destruir evidencia: desactivar la credencial o la integración,
   revocar sesiones, cerrar el acceso. No borrar logs, no reinstalar, no
   «limpiar» el servidor.
2. **Preservar**: exportar la bitácora `security_events` del periodo, los logs del
   proveedor, los `request_id` implicados y el historial de cambios de
   configuración. Guardarlo fuera del sistema afectado.
3. **Determinar el alcance** por `business_id`, categoría de dato, periodo
   temporal y terceros implicados. Números concretos, no impresiones.
4. **Rotar** las credenciales afectadas y las adyacentes. Tras rotar
   `NOESIS_SECRET` caen todas las sesiones: avisar antes.
5. **Recuperar** desde un estado conocido. Si se restaura una copia, comprobar que
   se reaplican las supresiones posteriores a esa copia.
6. **Decidir y notificar** según el § 3, con asesoría jurídica si el alcance
   incluye datos de terceros.
7. **Cerrar**: causa raíz, control correctivo, prueba de no regresión y entrada en
   [`Registro-de-evidencias`](Registro-de-evidencias.md) y en
   `docs/Registro-cambios.md`.

## 3. Cuándo se notifica

**A la AEPD (art. 33):** siempre que haya riesgo para los derechos y libertades,
salvo que sea improbable. En la práctica, ante la duda se notifica: una
notificación de más no sanciona; una de menos, sí.

**A los interesados (art. 34):** cuando el riesgo sea alto. Indicadores de riesgo
alto aquí: datos bancarios (IBAN) expuestos, documentos completos accesibles,
datos de trabajadores, o volumen relevante de datos de clientes finales.

**No procede notificar** si los datos estaban cifrados con una clave que no se ha
visto comprometida (art. 34.3.a). Este es exactamente el motivo por el que el
cifrado en cliente de las copias es un P0 y no una mejora estética.

## 4. Registro obligatorio

Toda brecha se documenta **aunque no se notifique**. El art. 33.5 exige el
registro interno con hechos, efectos y medidas correctivas, y la AEPD puede
pedirlo. Se anota en [`Registro-de-evidencias`](Registro-de-evidencias.md), sin
incluir en él los datos personales afectados.

## 5. Contactos

| Rol | Quién | Vía |
|---|---|---|
| Decisión y coordinación | Founder | [teléfono directo] |
| Suplente | [pendiente de nombrar] | — |
| Asesoría jurídica / RGPD | [pendiente de contratar] | — |
| Autoridad de control | AEPD | Sede electrónica, formulario de brechas |
| Proveedores críticos | Railway, Stripe, Meta, Brevo | Soporte de cada panel |

Los tres «pendiente» son tarea real, no formalismo: a las 3 de la mañana no se
busca abogado, se llama al que ya está en esta tabla.
