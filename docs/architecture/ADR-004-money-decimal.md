# ADR-004 · Dinero exacto y compatibilidad legacy

- Estado: aceptado e implementado en los fundamentos de Fase 0.

## Contexto

Los cálculos actuales combinan Decimal con resultados float; `_normalise_value`
convierte los NUMERIC de PostgreSQL a float y las tablas operativas usan
DOUBLE PRECISION/REAL. Ninguna conversión posterior recupera precisión ya perdida.
Fase 0 no modifica importes históricos ni cambia el comportamiento de facturación.

## Contrato público

`core/money.py` expone:

- `Currency.EUR`: solo EUR operativo. El campo moneda existe desde el inicio;
  otras monedas se rechazan hasta añadir reglas/pruebas explícitas.
- `parse_money(Decimal | str | int) -> Decimal`: no redondea. Texto con dígitos
  ASCII, signo opcional y punto decimal; sin espacios, coma, miles, exponentes,
  símbolos ni interpretación de idioma. El parseo conversacional queda fuera.
- `quantize_currency(value, currency) -> Decimal`: HALF_UP a dos decimales EUR.
- `Money(Decimal, currency)` / `Money.parse(...)`: objeto inmutable de importe
  final. Construirlo es un límite explícito de redondeo.
- `Money.to_decimal_string()`: cadena fija para transporte JSON o almacenamiento
  TEXT; nunca `float`. Suma/resta solo entre Money de la misma moneda.

Rango absoluto máximo de entrada: `9999999999999999.9999`, compatible con
NUMERIC(20,4). Se admiten hasta 18 decimales intermedios de entrada y texto de
hasta 64 caracteres. Se comprueba otra vez el límite después del redondeo: un
acarreo fuera de rango falla. NaN, infinitos, bool y floats se rechazan. El cero
final se normaliza a positivo. Contexto decimal local de precisión 50 y HALF_UP,
independiente de precisión, traps o redondeo del llamador.

Importes finales: dos decimales. Precios unitarios/tipos/cantidades NO deben
envolverse prematuramente en Money: usan Decimal y cada dominio documentará su
escala, límites y punto de redondeo. NUMERIC(20,4) es el mínimo de almacenamiento
monetario propuesto, no permiso para truncar intermediarios silenciosamente.
No se añaden aquí fórmulas fiscales, reparto de cuotas ni conversiones de divisas.

## Persistencia

`FinancialSession` presta una vista exacta de la conexión actual. PostgreSQL
conserva Decimal de NUMERIC, fechas nativas y JSONB. Los parámetros float y los
resultados float se rechazan, también dentro de contenedores JSON leídos. Por
eso los importes en JSON se transportan como cadenas decimales.

SQLite representa importes nuevos como TEXT canónico; el driver recibe Decimal
como cadena solo en `execute_exact`. No hay adaptador global. La afinidad NUMERIC
de SQLite puede devolver floats: se rechaza y existe una prueba para demostrarlo.
No ejecutar SUM/aritmética SQL sobre dinero TEXT en SQLite: leer y operar con
Decimal. En PostgreSQL se podrán usar agregaciones NUMERIC exactas.

Las consultas legacy conservan su normalización. La vista exacta no convierte
DOUBLE PRECISION histórico en dinero exacto: lo rechaza. Una futura migración o
puente desde legacy deberá tener conversión explícita, escala, reconciliación y
tratamiento de discrepancias; no presentar Decimal(str(float)) como exactitud de
origen. No modificar las huellas/registros fiscales históricos al normalizar.

## Alternativas descartadas y pruebas

Se descartan float canónico, adaptación global del driver, cambiar todos los
lectores legacy y usar NUMERIC SQLite como si garantizase precisión decimal.
Centavos enteros son posibles, pero TEXT conserva escalas sin conversiones ocultas.

Pruebas: empates positivos/negativos, límites y acarreo, inválidos, contexto hostil,
inmutabilidad, ida/vuelta de céntimos y persistencia exacta SQLite/PostgreSQL. El
caso `9999999999999999.99` demuestra que la lectura nueva permanece exacta aunque
la lectura legacy del mismo NUMERIC siga devolviendo float.
