# Plantilla — simulacro de restauración externa

> Trimestral. Es la única prueba que demuestra supervivencia ante pérdida del
> proveedor. Se rellena **durante** el simulacro, no después de memoria.

## Datos del simulacro

- Fecha y hora de inicio: [—]
- Responsable: [—]
- Copia utilizada: [nombre del artefacto y fecha de creación]
- Origen: [bucket externo, proveedor y región]
- Destino: [proveedor, región, tipo de máquina]

## Cronómetro

| Hito | Hora | Minutos acumulados |
|---|---|---|
| Inicio | | 0 |
| Copia descargada | | |
| Copia descifrada | | |
| Base restaurada | | |
| Migraciones aplicadas | | |
| Documentos extraídos y validados | | |
| Aplicación respondiendo en `/ready` | | |
| Aislamiento entre dos negocios comprobado | | |
| **Fin** | | **RTO real** |

- **RPO real** (antigüedad de la copia respecto al momento simulado del desastre): [—]

## Verificaciones

- [ ] Recuentos de tablas clave coinciden con lo esperado
- [ ] Numeración de facturas íntegra y sin huecos
- [ ] Documentos abren y sus hashes coinciden con el manifiesto
- [ ] Un negocio no ve datos de otro
- [ ] Colas de salida no reenvían mensajes antiguos al arrancar
- [ ] Supresiones posteriores a la copia reaplicadas

## Incidencias y mejoras

[Qué falló, qué tardó más de lo previsto, qué paso del runbook estaba mal escrito]

## Cierre

- Infraestructura de prueba destruida y datos borrados: [sí/no, fecha]
- Resultado anotado en `Registro-de-evidencias.md`: [sí/no]
