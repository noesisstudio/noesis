# Plan de datos, servidores y copias de seguridad

> Documento de diseño. Responde a tres preguntas —**dónde se guarda cada dato, en
> qué servidores y cómo se copia**— y deja escrito el plan de ejecución que ha
> generado el resto de esta carpeta.
>
> - Creado: 2026-09-08 · Última revisión: 2026-09-08 · Próxima revisión: 2026-12-08
> - Responsable: founder (Xavier). Sin DPO designado a día de hoy.
> - Alcance: producto Noesis en producción. No cubre `marketing/`, que no trata
>   datos personales de clientes.

## 0. Punto de partida real

No se parte de cero. Verificado hoy en el repositorio:

| Ya existe | Dónde |
|---|---|
| Aislamiento por `business_id` en toda lectura/escritura | `src/noesis/db.py` |
| Copia diaria de base y documentos, verificada restaurándola | `src/noesis/web/backups.py`, `KEEP = 14` |
| Simulacro semanal independiente (domingos 04:30) | `noesis-restore-check`, `web/scheduler.py` |
| Copia externa S3-compatible opcional con cifrado solicitado | `NOESIS_BACKUP_S3_*` en `.env.example` |
| Bitácora de seguridad append-only encadenada por hash | migración 35, `security_events` |
| Centro CISO determinista en `/admin` | `src/noesis/security_center.py` |
| DPA, privacidad, cookies y aviso legal publicados | `web/templates/encargado-tratamiento.html` y siguientes |
| Borrado con conservación fiscal y bloqueo de datos | `db.py` (`purge_for_client`, baja con conservación) |

Lo que **no** existe y condiciona todo lo demás:

1. Las copias viven en la misma cuenta y el mismo proveedor que produce los datos.
   Una copia «OK» dentro de Railway no demuestra recuperación ante pérdida del
   proveedor, ni ante un atacante con la credencial de esa cuenta.
2. No hay cifrado en cliente: quien lea el bucket lee las facturas.
3. Nunca se ha restaurado en otra infraestructura, así que **RPO y RTO son
   estimaciones, no medidas**.
4. No hay registro de actividades del art. 30 ni evaluación de transferencias
   internacionales escritas, y ambos son exigibles hoy.

Esos cuatro puntos son los P0 de este plan.

## 1. Dónde almacenar cada dato

Regla general: cuanto más identificable es el dato, menos sitios lo tocan y menos
tiempo se queda. Nada de datos personales en logs, en artefactos de CI, en tickets
ni en conversaciones con IA.

| Dato | Sistema | Cifrado | Quién lee | Retención |
|---|---|---|---|---|
| Base operativa (negocios, clientes, trabajos, facturas, fichajes) | PostgreSQL gestionado, región UE | TLS en tránsito, cifrado de disco del proveedor | Proceso de la aplicación con credencial única; nadie por consola salvo incidente registrado | Vida de la cuenta + retención fiscal/laboral (§ Política de retención) |
| Documentos subidos y OCR | Volumen persistente montado en `/data/uploads` | Cifrado de volumen del proveedor | Aplicación; ruta nunca pública, servidos por endpoint con sesión | Igual que la base; borrado real al purgar cliente |
| Copias de seguridad | Bucket S3-compatible en un **segundo** proveedor europeo | **Cifrado en cliente antes de subir** (age/GPG) + SSE del proveedor | Nadie en caliente: credencial de solo escritura; lectura solo en restauración | 14 diarias + 8 semanales; ver § 3.5 |
| Secretos y credenciales | Gestor de variables del proveedor + copia sellada offline | Cifrado del gestor; copia offline cifrada | Founder y despliegue | Rotación registrada, sin caducidad fija |
| Certificado y clave AEAT (Veri*Factu) | Volumen privado, permisos 600, contraseña en gestor de secretos | PEM cifrado | Solo el proceso de remisión | Vigencia del certificado |
| Registros de aplicación (logs) | Salida estándar del proveedor, sin query string, cuerpo, token ni datos personales | Del proveedor | Founder | **30 días**; fijarlo explícitamente en el proveedor |
| Bitácora de seguridad `security_events` | Tabla append-only con triggers anti-UPDATE/DELETE | Igual que la base | Founder vía `/admin` | 24 meses; después, exportar y purgar |
| Colas de salida (WhatsApp, email, Veri*Factu) | Tablas de la base | Igual que la base | Aplicación | Purga del contenido a los 90 días; se conserva el resultado, no el mensaje |
| Analítica de uso | Contadores agregados en la propia base | — | Founder | Sin identificadores personales; no se añade analítica de terceros |
| Código y configuración | GitHub (repositorio privado) | Del proveedor | Founder y agentes | Historia completa; **jamás** `.env`, `noesis.db` ni `uploads/` |

### Lo que no se debe almacenar nunca

- Contraseñas en claro o reversibles (hoy PBKDF2, correcto), ni segundos factores
  en texto plano.
- Datos de tarjeta: los tiene Stripe, Noesis solo guarda identificadores de cliente
  y suscripción. No cambiar esto: entrar en PCI DSS no compensa.
- Categorías especiales del art. 9 RGPD. Riesgo real: un parte de trabajo o un
  documento subido puede contener una baja médica. Mitigación: aviso en el DPA de
  que el cliente no debe subir datos de salud, y no indexar el texto OCR más allá
  de lo necesario.
- Datos personales en el prompt enviado a una IA externa sin consentimiento del
  negocio; ya está condicionado por configuración, mantenerlo así.
- Copias de producción en el portátil del founder ni en la base local `noesis.db`.

### Minimización pendiente de decidir

- IBAN: hoy en claro en la base. Candidato número uno a cifrado de columna con
  clave separada del backup (sobre AES-GCM con clave en el gestor de secretos).
  P1, antes de escalar.
- Teléfonos de los clientes finales: necesarios para WhatsApp, no minimizables.
- Metadatos de sesión: guardar hash de IP, no la IP, si alguna vez se persiste.

## 2. Qué servidores

### Decisión: dos niveles, no uno

**Nivel piloto (hoy, hasta ~25 negocios reales):** se mantiene Railway con
PostgreSQL gestionado y volumen, **fijando la región en la UE** (Ámsterdam) y
**sacando las copias fuera** hacia un proveedor europeo distinto. Cambiar de
plataforma ahora añadiría riesgo operativo sin evidencia de que el proveedor sea
el problema; sacar las copias, en cambio, elimina el riesgo que sí está probado
(dependencia de un único proveedor y de una única credencial).

**Nivel producción (a partir de datos reales a escala, o del primer cliente que
exija jurisdicción UE por contrato):** migración a proveedor europeo, con matriz
en la UE y por tanto sin exposición al CLOUD Act estadounidense.

| | Nivel piloto | Nivel producción |
|---|---|---|
| Aplicación | Railway, región `europe-west4` | Scaleway (París) o Hetzner (Núremberg/Helsinki) |
| Base de datos | PostgreSQL gestionado de Railway | PostgreSQL gestionado del mismo proveedor europeo, con PITR |
| Archivos | Volumen `/data` | Volumen cifrado + Object Storage UE |
| Copias | **Fuera**: Object Storage de Scaleway (París) u OVHcloud (Gravelines) | Segundo proveedor europeo distinto del principal |
| Correo | Brevo (Francia, servidores UE) — ya elegido, correcto | Igual |
| IA | Local/privada primero; externa solo con consentimiento | Añadir opción europea (Mistral, Francia) como preferente frente a proveedores de EE. UU. |
| Coste orientativo | ~25-60 €/mes según consumo + ~2-5 €/mes de copias | ~60-120 €/mes; validar con el proveedor antes de decidir |

Los importes son órdenes de magnitud a fecha de hoy, no tarifas: confirmar en el
proveedor antes de comprometer nada.

### Criterio para elegir proveedor

En este orden, y el primero que falla descarta:

1. **Región de los datos en la UE**, contractualmente, incluidas las réplicas y
   las copias del propio proveedor.
2. **Jurisdicción de la matriz.** Un proveedor estadounidense con región europea
   sigue sujeto al CLOUD Act: exige cláusulas contractuales tipo, verificar el
   marco de adecuación aplicable y una evaluación de transferencia escrita.
   Un proveedor europeo elimina el problema en origen, no lo documenta.
3. **DPA firmable** con subencargados listados y aviso previo de cambios.
4. **Salida sin secuestro** (Data Act, cap. VI): exportación estándar, sin formatos
   propietarios, migración factible en menos de 30 días.
5. **PITR y retención configurables** en la base gestionada.
6. Que una sola persona pueda operarlo sin dedicarle la semana.

### Endurecimiento mínimo, independientemente del proveedor

- Superficie pública: solo 443. Base de datos y cualquier daemon auxiliar
  (ClamAV incluido) en red privada, sin IP pública.
- Separación estricta producción / pruebas / desarrollo: credenciales distintas,
  datos reales nunca fuera de producción, `NOESIS_RESET_DB` jamás activo.
- Acceso administrativo con Google OAuth obligatorio, sesión corta y verificación
  en dos pasos en la cuenta Google. Ya está en código; falta verificarlo en el
  proxy real.
- Parcheo: Dependabot y `pip-audit` ya en CI; revisar alertas antes de fusionar.
- Un monitor externo (fuera del proveedor) que vigile `/ready` y avise. Hoy no lo
  hay: si el proveedor cae, nadie se entera hasta que llama un cliente.

### Lo que NO se monta a este tamaño

Kubernetes, malla de servicios, SIEM comercial, HSM, multi-región activa-activa y
certificación ISO 27001. Cada uno añade superficie y mantenimiento que hoy nadie
puede sostener, y ninguno ataca los cuatro riesgos reales del § 0. Se reconsidera
cuando haya un segundo administrador, o cuando un cliente lo exija por contrato y
pague la diferencia.

## 3. Cómo hacer las copias de seguridad

### 3.1 Estrategia 3-2-1-1-0

- **3** copias: la base viva, la copia local del volumen y la copia externa.
- **2** soportes distintos: volumen de bloque y almacenamiento de objetos.
- **1** copia fuera del proveedor principal. *(Falta hoy: es el P0.)*
- **1** copia inmutable: bucket con versionado y bloqueo de objetos, credencial
  sin permiso de borrado. *(Falta hoy.)*
- **0** errores de verificación: cada copia se restaura y se compara antes de
  darla por buena. *(Ya implementado en `backups.py`.)*

### 3.2 Qué se copia

| Artefacto | Contenido | Cadencia |
|---|---|---|
| Base de datos | Volcado lógico completo, verificado restaurándolo en un esquema temporal | Diaria + PITR continuo cuando el proveedor lo ofrezca |
| Documentos | ZIP con manifiesto y hashes de `/data/uploads` | Diaria |
| Secretos | Copia sellada y cifrada, fuera de la infraestructura | Al rotar, con registro de fecha y responsable |
| Configuración e infraestructura | Git + variables documentadas (nombres, nunca valores) | Cada cambio |

No se copian: `.venv`, cachés, modelos descargables, `noesis.db` local ni
artefactos de CI.

### 3.3 Cifrado y control de acceso de las copias

El cambio de fondo respecto a hoy: **el servidor debe poder escribir copias y no
poder leerlas ni borrarlas.**

1. Cifrado en cliente antes de subir, con clave pública en el servidor y clave
   privada custodiada fuera (dos ubicaciones físicas, una offline). Si roban el
   servidor, se llevan cifrado inútil.
2. Credencial S3 limitada a `PutObject` sobre un prefijo. Sin `DeleteObject`.
3. Bloqueo de objetos en modo cumplimiento y versionado activo: el ransomware no
   puede sobrescribir lo ya subido.
4. La restauración usa una credencial distinta, guardada aparte y usada solo en
   simulacro o incidente, con registro en la bitácora.

### 3.4 RPO y RTO

| Escenario | RPO objetivo | RTO objetivo | Situación hoy |
|---|---|---|---|
| Borrado accidental de un registro | 0 (deshacer en aplicación) | minutos | Cubierto |
| Corrupción o migración fallida | ≤ 24 h; ≤ 15 min con PITR | ≤ 2 h | Estimado, no medido |
| Ransomware / cuenta comprometida | ≤ 24 h | ≤ 8 h | **No cubierto** hasta que exista copia inmutable fuera |
| Pérdida total del proveedor | ≤ 24 h | ≤ 8 h | **No cubierto**; nunca ensayado |

Objetivos declarados, no garantías. Dejan de ser estimaciones el día que el
simulacro externo del § 3.6 se ejecute y se cronometre.

### 3.5 Retención de las copias y derecho de supresión

Tensión real: el art. 17 del RGPD obliga a suprimir, y una copia de hace seis
meses contiene lo suprimido. Se resuelve así, y se deja escrito por si lo pregunta
la AEPD o un cliente:

- Retención de copias: **14 diarias + 8 semanales** (≈ 2 meses). No se guardan
  copias completas anuales.
- La supresión se ejecuta en los sistemas vivos de forma inmediata. En las copias,
  el dato queda **bloqueado** (art. 32 LOPDGDD): no se usa para nada salvo
  restaurar un desastre, y desaparece al vencer el ciclo.
- Si hubiera que restaurar una copia anterior a una supresión, la supresión se
  vuelve a aplicar inmediatamente después de restaurar. Paso obligatorio del
  runbook, no una buena intención.
- La conservación fiscal y laboral **no se cubre con copias de seguridad**, sino
  con exportaciones contables específicas y con la conservación en la propia base:
  facturas y libros según la LGT y el Código de Comercio, registros de jornada
  cuatro años. Las copias son para desastres; los archivos legales, para la ley.

### 3.6 Verificación en tres capas

1. **Por copia:** ya se restaura cada copia en un fichero o esquema temporal y se
   comparan esquema y recuentos. Automático.
2. **Semanal:** `noesis-restore-check` repite la restauración de forma
   independiente y valida el manifiesto documental. Automático, resultado en la
   bitácora y en el centro CISO.
3. **Trimestral, manual y fuera del proveedor:** descargar del bucket externo,
   descifrar con la clave custodiada, levantar un PostgreSQL en otra
   infraestructura, restaurar, arrancar la aplicación, comprobar el aislamiento
   entre dos negocios y **cronometrar**. Evidencia fechada y firmada en
   [`Registro-de-evidencias`](Registro-de-evidencias.md). Sin este paso, las dos
   capas anteriores prueban el código de restauración, no la supervivencia.

## 4. Marco normativo aplicado

| Norma | Cómo afecta a este plan |
|---|---|
| RGPD art. 32 | Cifrado, resiliencia y **capacidad de restaurar verificada periódicamente**: el § 3.6 es literalmente esta obligación |
| RGPD art. 28 y 30 | DPA con cada subencargado y registro de actividades: [`RAT`](RAT-Registro-actividades.md) y [`Subencargados`](Subencargados-y-transferencias.md) |
| RGPD arts. 33 y 34 | 72 horas para notificar a la AEPD: [`Procedimiento-brechas`](Procedimiento-brechas.md) |
| RGPD arts. 44-49 | Toda transferencia fuera del EEE necesita garantía y evaluación escrita |
| RGPD art. 35 | Cribado de EIPD documentado: tratamiento a gran escala no, pero sí datos de trabajadores |
| LOPDGDD art. 32 | Bloqueo de datos: justifica el tratamiento de la supresión en copias |
| LSSI art. 22.2 | Cookies: solo técnicas, sin analítica de terceros. Mantenerlo simplifica mucho |
| NIS2 (Dir. 2022/2555) | Por tamaño, Noesis previsiblemente **no** es entidad sujeta; sí puede recibir exigencias por contrato de clientes que lo sean. Verificar el estado de la transposición española antes de afirmarlo por escrito a un cliente |
| Reglamento de IA (2024/1689) | Uso de riesgo limitado: transparencia sobre que hay IA. Vigilar que ninguna función decida sobre trabajadores sin intervención humana, que es lo que la acercaría a alto riesgo |
| Data Act, cap. VI | Plan de salida del proveedor y portabilidad real |
| DORA y ENS | **No aplican**: ni entidad financiera ni contrato con sector público. Se revisa si eso cambia |
| CRA (2024/2847) | SaaS puro, previsiblemente fuera de ámbito; vigilar el calendario |
| LGT, Código de Comercio, ET art. 34.9 | Fijan las retenciones legales de facturas, libros y fichajes |

Interpretaciones de ingeniería, no dictamen jurídico. La revisión con abogado y la
firma de los DPA siguen siendo tarea externa pendiente.

## 5. Riesgos residuales

| Riesgo | Nivel tras las medidas | Quién lo acepta |
|---|---|---|
| Superusuario de la base de datos del proveedor puede leerlo todo | Medio | Founder; se reduce con cifrado de columna del IBAN y, más adelante, proveedor europeo |
| Sin monitor externo, una caída del proveedor se detecta tarde | Medio | Founder; P1 |
| Sin pentest independiente, el aislamiento está probado solo por su propia suite | Medio-alto | Founder; obligatorio antes de escalar |
| Clave privada de copias mal custodiada = copias irrecuperables | Alto si se descuida | Founder; dos ubicaciones y prueba de descifrado cada trimestre |
| IA externa con datos de un negocio que consintió sin entender | Medio | Founder; el consentimiento debe explicar destino y país |

## 6. Plan de ejecución

### Documentación creada hoy con este plan

```text
docs/cumplimiento/
├── README.md                          índice y cadencia de revisión
├── Plan-Datos-Servidores-Copias.md    este documento
├── RAT-Registro-actividades.md        art. 30, como responsable y como encargado
├── Politica-de-retencion.md           qué se guarda, cuánto y por qué
├── Subencargados-y-transferencias.md  art. 28 y arts. 44-49, con evaluación
├── Analisis-riesgos-y-EIPD.md         art. 32 y cribado del art. 35
├── Procedimiento-brechas.md           arts. 33 y 34, con reloj de 72 horas
├── Derechos-de-los-interesados.md     arts. 12-22, plazos y responsables
├── Continuidad-RPO-RTO.md             runbooks de recuperación
├── Registro-de-evidencias.md          bitácora de simulacros y rotaciones
└── plantillas/
    ├── Notificacion-brecha-AEPD.md
    ├── Respuesta-derechos.md
    ├── Registro-simulacro-restauracion.md
    └── Alta-subencargado.md
```

Más `scripts/check_cumplimiento.py`, que comprueba que la estructura existe y que
ningún documento lleva más de su plazo sin revisar.

### Acciones técnicas, por prioridad

**P0 — antes de meter datos reales de terceros**

1. Crear el bucket externo en proveedor europeo distinto y rellenar
   `NOESIS_BACKUP_S3_*` con una credencial de **solo escritura**.
2. Activar versionado y bloqueo de objetos en ese bucket.
3. Añadir cifrado en cliente antes de subir, con la clave privada custodiada fuera.
4. Ejecutar el primer simulacro de restauración externa completo y anotar RPO/RTO
   reales en [`Registro-de-evidencias`](Registro-de-evidencias.md).
5. Fijar la región UE en el proveedor actual y la retención de logs en 30 días.
6. Firmar los DPA pendientes con cada subencargado y completar la evaluación de
   transferencias.

**P1 — antes de escalar**

7. Monitor externo de `/ready` con aviso.
8. Cifrado de columna para el IBAN, con clave fuera del backup.
9. PITR activo en la base gestionada.
10. Pentest autenticado por un tercero, centrado en el aislamiento entre negocios.

**P2 — mejora**

11. Exportar la bitácora de seguridad a almacenamiento WORM.
12. Evaluar la migración completa a proveedor europeo con el coste real medido.

Los puntos 1-3, 5, 7 y 9 se ejecutan **en el proveedor**, no en el repositorio: el
código ya los soporta mediante variables de entorno. Este plan no puede tocarlos
por sí solo y no debe simular que lo ha hecho.
