# Límites operativos del Financial Core v1

Estos límites acotan el software del futuro piloto. No son SLO, plazos legales
ni aprobación de la política E. La situación real sigue bloqueada; G no iniciada.

| Límite | Valor | Aplicación |
|---|---:|---|
| Cohorte histórica | 64 items | Preflight BLOCKED por volumen superior; incluye identidad fiscal |
| Espera del gate compartido | 1 s | F/D79: try-lock PostgreSQL del mismo namespace; busy timeout SQLite |
| TX de handoff: warning | 2 s | Observación F en la TX, sin deshacer un commit |
| TX de handoff: revisión | 5 s | Bloqueo antes de commit y revisión manual |
| Readiness y preflight | 5 min | Revalidación every_use; caducidad bloquea enable/resume |
| Attestation | 5 min | Nueva UUID, jamás refresh de una fila |
| Corte protegido: warning | 5 min | Estado local observable, ninguna alerta remota |
| Corte protegido: intervención | 15 min | Estado de intervención; el fence no se libera por TTL |
| Integridad rota/duplicado económico | Bloqueo | Conservar pruebas y solicitar pausa; no corregir con otro EE |
| Resultado externo incierto | UNKNOWN | Sin retry automático ni aceptación/rechazo inventados |

`financial_providers.contracts.OperationalPolicy` es la constante cerrada única F.
Se congela en cada preflight. Los contratos A/D anteriores conservan sus TTL y
hashes; las matrices 77/78 prueban la compatibilidad. El watchdog actúa antes del
commit, nunca revierte un efecto fiscal o una entrega ya confirmados.

Los gates son transaccionales y por negocio en PostgreSQL. SQLite serializa
writes por archivo: no se promete concurrencia entre tenants equivalente a PG.
Ninguna TX/gate del negocio llega al transporte externo. `start` durable marca la
ventana de posible I/O; otro worker no presupone que el primero haya muerto.
`recover_unknown` es explícito y conservador: puede perder certeza, nunca repetir
un intento. Antes de usarlo, el operador debe detener/verificar el worker original.

La recuperación D79 exige pausa y snapshot exactos, export E actual, providers
vigentes, perfil original y un preflight nuevo. Una evaluación A caducada no se
promueve ni se edita: queda READINESS_STALE. F no añade un reset unilateral del
control plane; resolver esa situación operativa exige diseño/autorización antes
del piloto. Un binding de G antigua no se traslada automáticamente a G nueva.

Las mediciones de fixtures (vacío, 64 items, tres providers y 501 intentos) están en
[el cierre F](FASE-1.10F-cierre.md). El caso 64 puede quedar BLOCKED por evidencia
monetaria legacy insuficiente; medirlo no elimina ese bloqueo.
