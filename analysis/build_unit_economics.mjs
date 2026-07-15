import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = path.resolve("outputs/2026-07-15-internal-brain-unit-economics");
const outputFile = path.join(outputDir, "Noesis_unit_economics.xlsx");
const previewDir = path.join(outputDir, "previews");

const wb = Workbook.create();
await wb.comments.setSelf({ displayName: "Noesis" });

const summary = wb.worksheets.add("Summary");
const assumptions = wb.worksheets.add("Assumptions");
const unit = wb.worksheets.add("Unit_Economics");
const scale = wb.worksheets.add("Scale");
const ai = wb.worksheets.add("AI_Options");
const sources = wb.worksheets.add("Sources");
const checks = wb.worksheets.add("Checks");

const C = {
  forest: "#14463B",
  teal: "#2E8B74",
  cream: "#F4F1E8",
  sand: "#E7E0D1",
  ink: "#18302B",
  muted: "#60706B",
  white: "#FFFFFF",
  input: "#0000FF",
  link: "#008000",
  good: "#DDEFE7",
  warn: "#FFF1CC",
  bad: "#F8D7DA",
};

function title(sheet, range, text) {
  sheet.getRange(range).merge();
  const cell = sheet.getRange(range.split(":")[0]);
  cell.values = [[text]];
  cell.format = {
    fill: C.forest,
    font: { bold: true, color: C.white, size: 18 },
    verticalAlignment: "center",
  };
  sheet.getRange(range).format.rowHeight = 34;
}

function section(sheet, range, text) {
  sheet.getRange(range).merge();
  const cell = sheet.getRange(range.split(":")[0]);
  cell.values = [[text]];
  cell.format = {
    fill: C.teal,
    font: { bold: true, color: C.white, size: 11 },
    verticalAlignment: "center",
  };
}

function headers(range) {
  range.format = {
    fill: C.sand,
    font: { bold: true, color: C.ink },
    borders: { preset: "doubleBottom", style: "thin", color: C.forest },
    verticalAlignment: "center",
    wrapText: true,
  };
}

function common(sheet, widthRange = "A:Z") {
  sheet.showGridLines = false;
  sheet.getRange(widthRange).format.font = { name: "Aptos", size: 10, color: C.ink };
}

// Assumptions
common(assumptions, "A:F");
title(assumptions, "A1:F1", "Noesis · Supuestos editables del modelo");
assumptions.getRange("A2:F2").merge();
assumptions.getRange("A2").values = [["Celdas azules = inputs. Importes sin IVA salvo que se indique. Fecha de referencia: 15/07/2026."]];
assumptions.getRange("A2").format = { font: { color: C.muted, italic: true }, wrapText: true };
section(assumptions, "A4:F4", "Supuestos por plan");
assumptions.getRange("A5:F5").values = [["Driver", "Autónomo", "Negocio", "Sin Límites", "Unidad", "Fuente / criterio"]];
headers(assumptions.getRange("A5:F5"));
const planInputs = [
  ["Precio actual", 29, 39, 79, "€/mes + IVA", "Catálogo actual"],
  ["Precio recomendado", 29, 49, 99, "€/mes + IVA", "Recomendación de unit economics"],
  ["Mix de clientes", 0.55, 0.35, 0.10, "%", "Supuesto de escala"],
  ["Créditos avanzados incluidos", 75, 300, 1500, "acciones/mes", "Catálogo actual"],
  ["Uso esperado del límite", 0.35, 0.40, 0.25, "%", "Supuesto conservador"],
  ["Resolución por cerebro interno", 0.60, 0.60, 0.60, "%", "Objetivo tras piloto"],
  ["WhatsApp utility enviados", 30, 80, 200, "mensajes/mes", "Supuesto operativo"],
  ["WhatsApp service recibidos", 100, 300, 1000, "mensajes/mes", "Gratis hoy; sensibilidad futura"],
  ["Audio transcrito", 15, 60, 200, "min/mes", "Supuesto operativo"],
  ["Documentos procesados", 15, 50, 200, "docs/mes", "Supuesto operativo"],
  ["Documentos que escalan fuera", 0.20, 0.20, 0.20, "%", "OCR local primero"],
  ["Almacenamiento", 0.25, 1, 3, "GB/cuenta", "Supuesto operativo"],
  ["Voz telefónica incluida", 0, 0, 100, "min/mes", "Promesa Premium actual"],
  ["Soporte humano", 12, 20, 45, "min/cuenta/mes", "Supuesto de servicio"],
  ["Onboarding inicial", 30, 60, 120, "min/cuenta", "Amortizado en 12 meses"],
];
assumptions.getRange(`A6:F${5 + planInputs.length}`).values = planInputs;
assumptions.getRange("B6:D20").format.font = { color: C.input };
assumptions.getRange("B8:D8").format.numberFormat = "0.0%";
assumptions.getRange("B10:D11").format.numberFormat = "0.0%";
assumptions.getRange("B16:D16").format.numberFormat = "0.0%";
assumptions.getRange("B6:D7").format.numberFormat = "€#,##0.00";
section(assumptions, "A23:F23", "Supuestos globales");
assumptions.getRange("A24:F24").values = [["Driver", "Valor", "Unidad", "Fecha", "Fuente", "Nota"]];
headers(assumptions.getRange("A24:F24"));
const globalInputs = [
  ["EUR por USD", 1 / 1.1405, "EUR/USD", "14/07/2026", "ECB", "1 EUR = 1,1405 USD"],
  ["Stripe Payments", 0.015, "% ingreso", "15/07/2026", "Stripe", "Tarjeta EEE estándar"],
  ["Stripe Billing", 0.007, "% ingreso", "15/07/2026", "Stripe", "Pago por uso"],
  ["Stripe fijo", 0.25, "€/transacción", "15/07/2026", "Stripe", "Una renovación mensual"],
  ["WhatsApp utility España", 0.0166, "€/mensaje", "15/07/2026", "Meta / rate card", "Mensaje entregado"],
  ["WhatsApp service futuro", 0.0166, "€/mensaje", "15/07/2026", "Sensibilidad", "Actualmente 0 €"],
  ["Haiku 4.5 por interacción", 0.014, "USD/interacción", "15/07/2026", "Anthropic", "8k input + 1,2k output"],
  ["Qwen3 32B por interacción", 0.003028, "USD/interacción", "15/07/2026", "Groq", "Mismo supuesto de tokens"],
  ["Peso Qwen en fallback", 0.80, "%", "15/07/2026", "Arquitectura híbrida", "Resto Haiku"],
  ["Whisper Turbo", 0.04, "USD/hora", "15/07/2026", "Groq", "Solo transcripción"],
  ["Extracción externa documento", 0.012, "€/documento", "15/07/2026", "Supuesto", "Validar con corpus real"],
  ["Object storage", 0.015, "USD/GB-mes", "15/07/2026", "Railway", "Sin egress"],
  ["Voz agente", 0.11, "USD/min", "15/07/2026", "Retell", "Ejemplo de calculadora"],
  ["Número telefónico voz", 2, "USD/mes", "15/07/2026", "Retell", "Solo plan Premium"],
  ["Coste hora soporte", 25, "€/hora", "15/07/2026", "Supuesto", "Coste empresa cargado"],
  ["Plataforma fija", 65, "€/mes", "15/07/2026", "Supuesto", "App, email y backups mínimos"],
  ["Opex fijo para break-even", 3500, "€/mes", "15/07/2026", "Supuesto", "Founder, legal, herramientas, reserva"],
  ["CAC inicial", 150, "€/cliente", "15/07/2026", "Supuesto", "Validar durante piloto"],
  ["IVA España", 0.21, "%", "15/07/2026", "AEAT", "Precio recomendado se comunica + IVA"],
  ["Cuentas para repartir fijo", 100, "cuentas", "15/07/2026", "Escenario base", "Solo unit economics por plan"],
];
assumptions.getRange(`A25:F${24 + globalInputs.length}`).values = globalInputs;
assumptions.getRange("B25:B44").format.font = { color: C.input };
assumptions.getRange("B26:B27").format.numberFormat = "0.00%";
assumptions.getRange("B33").format.numberFormat = "0%";
assumptions.getRange("B43").format.numberFormat = "0%";
assumptions.getRange("A5:F44").format.borders = { preset: "inside", style: "thin", color: "#DDD8CC" };
assumptions.getRange("A:A").format.columnWidth = 33;
assumptions.getRange("B:D").format.columnWidth = 16;
assumptions.getRange("E:E").format.columnWidth = 18;
assumptions.getRange("F:F").format.columnWidth = 39;
assumptions.getRange("F6:F44").format.wrapText = true;
assumptions.freezePanes.freezeRows(5);

// Unit economics
common(unit, "A:H");
title(unit, "A1:H1", "Unit economics por plan");
unit.getRange("A2:H2").merge();
unit.getRange("A2").values = [["Escenario base híbrido: cerebro interno 60%, Qwen para el 80% del fallback y Haiku para el 20% restante."]];
unit.getRange("A2").format = { font: { color: C.muted, italic: true }, wrapText: true };
unit.getRange("A4:H4").values = [["Métrica", "Autónomo actual", "Negocio actual", "Premium actual", "Autónomo recom.", "Negocio recom.", "Premium recom.", "Unidad"]];
headers(unit.getRange("A4:H4"));
const metricLabels = [
  "Precio neto", "Stripe", "WhatsApp utility", "IA avanzada", "Transcripción", "Extracción externa", "Almacenamiento", "Voz Premium", "COGS software", "Margen bruto software", "Soporte humano", "Onboarding amortizado", "Fijo asignado", "Contribución", "Margen de contribución", "Ingreso si el precio incluyera IVA", "Contribución si incluyera IVA", "IA: 100% de créditos con Haiku", "Margen bruto en peor caso IA"
];
unit.getRange("A5:A23").values = metricLabels.map(x => [x]);
unit.getRange("H5:H23").values = [["€/mes"],["€/mes"],["€/mes"],["€/mes"],["€/mes"],["€/mes"],["€/mes"],["€/mes"],["€/mes"],["%"],["€/mes"],["€/mes"],["€/mes"],["€/mes"],["%"],["€/mes"],["€/mes"],["€/mes"],["%"]];
const cols = ["B", "C", "D", "E", "F", "G"];
for (let j = 0; j < cols.length; j++) {
  const col = cols[j];
  const planIndex = j % 3;
  const aCol = ["B", "C", "D"][planIndex];
  const priceRow = j < 3 ? 6 : 7;
  unit.getRange(`${col}5`).formulas = [[`='Assumptions'!${aCol}$${priceRow}`]];
  unit.getRange(`${col}6`).formulas = [[`=${col}5*('Assumptions'!$B$26+'Assumptions'!$B$27)+'Assumptions'!$B$28`]];
  unit.getRange(`${col}7`).formulas = [[`='Assumptions'!${aCol}$12*'Assumptions'!$B$29`]];
  unit.getRange(`${col}8`).formulas = [[`='Assumptions'!${aCol}$9*'Assumptions'!${aCol}$10*(1-'Assumptions'!${aCol}$11)*('Assumptions'!$B$33*'Assumptions'!$B$32+(1-'Assumptions'!$B$33)*'Assumptions'!$B$31)*'Assumptions'!$B$25`]];
  unit.getRange(`${col}9`).formulas = [[`='Assumptions'!${aCol}$14/60*'Assumptions'!$B$34*'Assumptions'!$B$25`]];
  unit.getRange(`${col}10`).formulas = [[`='Assumptions'!${aCol}$15*'Assumptions'!${aCol}$16*'Assumptions'!$B$35`]];
  unit.getRange(`${col}11`).formulas = [[`='Assumptions'!${aCol}$17*'Assumptions'!$B$36*'Assumptions'!$B$25`]];
  unit.getRange(`${col}12`).formulas = [[`=IF('Assumptions'!${aCol}$18>0,'Assumptions'!${aCol}$18*'Assumptions'!$B$37*'Assumptions'!$B$25+'Assumptions'!$B$38*'Assumptions'!$B$25,0)`]];
  unit.getRange(`${col}13`).formulas = [[`=SUM(${col}6:${col}12)`]];
  unit.getRange(`${col}14`).formulas = [[`=(${col}5-${col}13)/${col}5`]];
  unit.getRange(`${col}15`).formulas = [[`='Assumptions'!${aCol}$19/60*'Assumptions'!$B$39`]];
  unit.getRange(`${col}16`).formulas = [[`='Assumptions'!${aCol}$20/60*'Assumptions'!$B$39/12`]];
  unit.getRange(`${col}17`).formulas = [[`='Assumptions'!$B$40/'Assumptions'!$B$44`]];
  unit.getRange(`${col}18`).formulas = [[`=${col}5-${col}13-${col}15-${col}16-${col}17`]];
  unit.getRange(`${col}19`).formulas = [[`=${col}18/${col}5`]];
  unit.getRange(`${col}20`).formulas = [[`=${col}5/(1+'Assumptions'!$B$43)`]];
  unit.getRange(`${col}21`).formulas = [[`=${col}20-${col}13-${col}15-${col}16-${col}17`]];
  unit.getRange(`${col}22`).formulas = [[`='Assumptions'!${aCol}$9*'Assumptions'!$B$31*'Assumptions'!$B$25`]];
  unit.getRange(`${col}23`).formulas = [[`=(${col}5-(${col}13-${col}8+${col}22))/${col}5`]];
}
unit.getRange("B5:G23").format.numberFormat = "€#,##0.00;[Red](€#,##0.00);-";
unit.getRange("B14:G14").format.numberFormat = "0.0%";
unit.getRange("B19:G19").format.numberFormat = "0.0%";
unit.getRange("B23:G23").format.numberFormat = "0.0%";
unit.getRange("A13:H14").format.fill = C.good;
unit.getRange("A18:H19").format.fill = C.cream;
unit.getRange("A20:H21").format.fill = C.warn;
unit.getRange("A23:H23").format.borders = { preset: "doubleBottom", style: "thin", color: C.forest };
unit.getRange("A:A").format.columnWidth = 32;
unit.getRange("B:G").format.columnWidth = 17;
unit.getRange("H:H").format.columnWidth = 13;
unit.freezePanes.freezeRows(4);

// Scale
common(scale, "A:K");
title(scale, "A1:K1", "Escala, contribución y punto de equilibrio");
scale.getRange("A3:K3").values = [["Cuentas", "Ingresos actuales", "Ingresos recomendados", "COGS software actual", "COGS software recom.", "Contribución actual", "Contribución recom.", "Margen actual", "Margen recom.", "Resultado actual", "Resultado recom."]];
headers(scale.getRange("A3:K3"));
scale.getRange("A4:A7").values = [[10],[50],[100],[500]];
for (let row = 4; row <= 7; row++) {
  scale.getRange(`B${row}`).formulas = [[`=$A${row}*SUMPRODUCT('Assumptions'!$B$8:$D$8,'Assumptions'!$B$6:$D$6)`]];
  scale.getRange(`C${row}`).formulas = [[`=$A${row}*SUMPRODUCT('Assumptions'!$B$8:$D$8,'Assumptions'!$B$7:$D$7)`]];
  scale.getRange(`D${row}`).formulas = [[`=$A${row}*SUMPRODUCT('Assumptions'!$B$8:$D$8,'Unit_Economics'!$B$13:$D$13)`]];
  scale.getRange(`E${row}`).formulas = [[`=$A${row}*SUMPRODUCT('Assumptions'!$B$8:$D$8,'Unit_Economics'!$E$13:$G$13)`]];
  scale.getRange(`F${row}`).formulas = [[`=$A${row}*SUMPRODUCT('Assumptions'!$B$8:$D$8,'Unit_Economics'!$B$18:$D$18)`]];
  scale.getRange(`G${row}`).formulas = [[`=$A${row}*SUMPRODUCT('Assumptions'!$B$8:$D$8,'Unit_Economics'!$E$18:$G$18)`]];
  scale.getRange(`H${row}`).formulas = [[`=F${row}/B${row}`]];
  scale.getRange(`I${row}`).formulas = [[`=G${row}/C${row}`]];
  scale.getRange(`J${row}`).formulas = [[`=F${row}-'Assumptions'!$B$41`]];
  scale.getRange(`K${row}`).formulas = [[`=G${row}-'Assumptions'!$B$41`]];
}
scale.getRange("B4:G7").format.numberFormat = "€#,##0;[Red](€#,##0);-";
scale.getRange("J4:K7").format.numberFormat = "€#,##0;[Red](€#,##0);-";
scale.getRange("H4:I7").format.numberFormat = "0.0%";
section(scale, "A10:K10", "Break-even operativo (mix 55% / 35% / 10%)");
scale.getRange("A11:C11").values = [["Escenario", "Contribución por cuenta", "Cuentas para cubrir opex"]];
headers(scale.getRange("A11:C11"));
scale.getRange("A12:A13").values = [["Precios actuales"],["Precios recomendados"]];
scale.getRange("B12").formulas = [["=SUMPRODUCT('Assumptions'!$B$8:$D$8,'Unit_Economics'!$B$18:$D$18)"]];
scale.getRange("B13").formulas = [["=SUMPRODUCT('Assumptions'!$B$8:$D$8,'Unit_Economics'!$E$18:$G$18)"]];
scale.getRange("C12").formulas = [["=ROUNDUP('Assumptions'!$B$41/B12,0)"]];
scale.getRange("C13").formulas = [["=ROUNDUP('Assumptions'!$B$41/B13,0)"]];
scale.getRange("B12:B13").format.numberFormat = "€#,##0.00";
scale.getRange("A:A").format.columnWidth = 15;
scale.getRange("B:K").format.columnWidth = 17;
scale.getRange("A3:K13").format.wrapText = true;
scale.getRange("A16:C20").values = [
  ["Cuentas", "Resultado actual", "Resultado recomendado"],
  [10, null, null],
  [50, null, null],
  [100, null, null],
  [500, null, null],
];
for (let row = 17; row <= 20; row++) {
  const sourceRow = row - 13;
  scale.getRange(`B${row}`).formulas = [[`=J${sourceRow}`]];
  scale.getRange(`C${row}`).formulas = [[`=K${sourceRow}`]];
}
headers(scale.getRange("A16:C16"));
scale.getRange("B17:C20").format.numberFormat = "€#,##0;[Red](€#,##0);-";
const scaleChart = scale.charts.add("column", scale.getRange("A16:C20"));
scaleChart.titleText = "Resultado mensual tras opex (€)";
scaleChart.hasLegend = true;
scaleChart.setPosition("E10", "K25");
scale.freezePanes.freezeRows(3);

// AI options
common(ai, "A:H");
title(ai, "A1:H1", "Opciones de inteligencia: coste y uso correcto");
ai.getRange("A3:H3").values = [["Opción", "Coste/interacción", "75/mes", "300/mes", "1.500/mes", "Fijo mensual", "Uso recomendado", "Riesgo principal"]];
headers(ai.getRange("A3:H3"));
ai.getRange("A4:A8").values = [["Cerebro determinista Noesis"],["Cloudflare Qwen3 30B A3B"],["Groq Qwen3 32B"],["Anthropic Haiku 4.5"],["GPU 16 GB siempre encendida"]];
ai.getRange("B4:B8").formulas = [["=0"],["=0.00081*'Assumptions'!$B$25"],["='Assumptions'!$B$32*'Assumptions'!$B$25"],["='Assumptions'!$B$31*'Assumptions'!$B$25"],["=0"]];
for (let row = 4; row <= 8; row++) {
  ai.getRange(`C${row}`).formulas = [[`=B${row}*75`]];
  ai.getRange(`D${row}`).formulas = [[`=B${row}*300`]];
  ai.getRange(`E${row}`).formulas = [[`=B${row}*1500`]];
}
ai.getRange("F4:F8").values = [[0],[0],[0],[0],[423.40 * (1 / 1.1405)]];
ai.getRange("G4:H8").values = [
  ["Hechos, cálculos, clasificación, borradores repetibles", "Cobertura limitada; exige reglas y tests"],
  ["Fallback barato de texto", "Cuotas/cambio de precio y datos fuera"],
  ["Fallback barato con herramientas", "Proveedor externo y límites"],
  ["Respaldo de calidad", "Más caro; sigue siendo API externa"],
  ["Privacidad o volumen muy alto", "Coste fijo, operación y capacidad ociosa"],
];
ai.getRange("B4:F8").format.numberFormat = "€#,##0.000";
section(ai, "A11:H11", "Puntos de cruce de coste puro");
ai.getRange("A12:C12").values = [["Comparación", "Interacciones/mes", "Lectura"]];
headers(ai.getRange("A12:C12"));
ai.getRange("A13:A14").values = [["GPU vs Haiku"],["GPU vs Groq Qwen"]];
ai.getRange("B13").formulas = [["=F8/B7"]];
ai.getRange("B14").formulas = [["=F8/B6"]];
ai.getRange("C13:C14").values = [["Por debajo, pagar por uso es más barato"],["Por debajo, pagar por uso es más barato"]];
ai.getRange("B13:B14").format.numberFormat = "#,##0";
ai.getRange("A:A").format.columnWidth = 31;
ai.getRange("B:F").format.columnWidth = 16;
ai.getRange("G:H").format.columnWidth = 36;
ai.getRange("G4:H14").format.wrapText = true;

// Sources
common(sources, "A:G");
title(sources, "A1:G1", "Fuentes y trazabilidad");
sources.getRange("A3:G3").values = [["ID", "Input", "Valor", "Unidad", "Fuente", "URL", "Accedido"]];
headers(sources.getRange("A3:G3"));
const sourceRows = [
  ["S01", "Stripe Payments + Billing", "1,5% + 0,25 € + 0,7%", "por cobro", "Stripe España", "https://stripe.com/es/pricing", "15/07/2026"],
  ["S02", "Haiku 4.5", "$1 input / $5 output por MTok", "tokens", "Anthropic", "https://www.anthropic.com/claude/haiku", "15/07/2026"],
  ["S03", "Railway", "$10 RAM; $20 CPU; $0,05 egress", "mes/uso", "Railway", "https://docs.railway.com/pricing", "15/07/2026"],
  ["S04", "Resend Pro", "$20 / 50.000 emails", "mes", "Resend", "https://resend.com/docs/knowledge-base/what-is-resend-pricing", "15/07/2026"],
  ["S05", "WhatsApp pricing model", "Por mensaje entregado y categoría", "mensaje", "WhatsApp Business", "https://whatsappbusiness.com/products/platform-pricing/", "15/07/2026"],
  ["S06", "WhatsApp España utility", "0,0166 €", "mensaje", "Rate card España", "https://whautomate.com/whatsapp-business-api-pricing-spain", "15/07/2026"],
  ["S07", "EUR/USD", "1 EUR = 1,1405 USD", "14/07/2026", "ECB", "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html", "15/07/2026"],
  ["S08", "Retell voz", "$0,07-$0,31/min; ejemplo $0,11", "minuto", "Retell", "https://www.retellai.com/pricing", "15/07/2026"],
  ["S09", "Whisper Turbo", "$0,04/hora", "audio", "Groq", "https://console.groq.com/docs/speech-to-text", "15/07/2026"],
  ["S10", "Runpod serverless", "Desde $0,58/h 16 GB", "GPU-hora", "Runpod", "https://www.runpod.io/product/serverless", "15/07/2026"],
  ["S11", "Qwen3 8B", "Apache 2.0; 100+ idiomas; tools", "modelo", "Qwen", "https://github.com/QwenLM/Qwen3", "15/07/2026"],
];
sources.getRange(`A4:G${3 + sourceRows.length}`).values = sourceRows;
sources.getRange("F4:F14").format.font = { color: C.link, underline: true };
sources.getRange("A:A").format.columnWidth = 10;
sources.getRange("B:B").format.columnWidth = 30;
sources.getRange("C:E").format.columnWidth = 24;
sources.getRange("F:F").format.columnWidth = 68;
sources.getRange("G:G").format.columnWidth = 15;
sources.getRange("B4:F14").format.wrapText = true;

// Checks
common(checks, "A:F");
title(checks, "A1:F1", "Controles del modelo");
checks.getRange("A3:F3").values = [["Check", "Actual", "Esperado", "Diferencia", "Tolerancia", "Estado"]];
headers(checks.getRange("A3:F3"));
checks.getRange("A4:A9").values = [["Mix de planes suma 100%"],["COGS = componentes (Autónomo actual)"],["Contribución = ingreso - costes"],["Precio recomendado no baja"],["Break-even recomendado menor"],["Todos los márgenes brutos positivos"]];
checks.getRange("B4").formulas = [["=SUM('Assumptions'!$B$8:$D$8)"]];
checks.getRange("C4").values = [[1]];
checks.getRange("B5").formulas = [["='Unit_Economics'!B13"]];
checks.getRange("C5").formulas = [["=SUM('Unit_Economics'!B6:B12)"]];
checks.getRange("B6").formulas = [["='Unit_Economics'!B18"]];
checks.getRange("C6").formulas = [["='Unit_Economics'!B5-SUM('Unit_Economics'!B13,'Unit_Economics'!B15:B17)"]];
checks.getRange("B7").formulas = [["=MIN('Assumptions'!B7:D7-'Assumptions'!B6:D6)"]];
checks.getRange("C7").values = [[0]];
checks.getRange("B8").formulas = [["='Scale'!C13"]];
checks.getRange("C8").formulas = [["='Scale'!C12"]];
checks.getRange("B9").formulas = [["=MIN('Unit_Economics'!B14:G14)"]];
checks.getRange("C9").values = [[0]];
checks.getRange("D4:D7").formulas = [["=B4-C4"],["=B5-C5"],["=B6-C6"],["=B7-C7"]];
checks.getRange("D8").formulas = [["=B8-C8"]];
checks.getRange("D9").formulas = [["=B9-C9"]];
checks.getRange("E4:E9").values = [[0.000001],[0.000001],[0.000001],[0],[0],[0]];
checks.getRange("F4").formulas = [["=IF(ABS(D4)<=E4,\"PASS\",\"FAIL\")"]];
checks.getRange("F5").formulas = [["=IF(ABS(D5)<=E5,\"PASS\",\"FAIL\")"]];
checks.getRange("F6").formulas = [["=IF(ABS(D6)<=E6,\"PASS\",\"FAIL\")"]];
checks.getRange("F7").formulas = [["=IF(D7>=-E7,\"PASS\",\"FAIL\")"]];
checks.getRange("F8").formulas = [["=IF(D8<=E8,\"PASS\",\"FAIL\")"]];
checks.getRange("F9").formulas = [["=IF(D9>E9,\"PASS\",\"FAIL\")"]];
checks.getRange("A12:B12").values = [["MODEL STATUS", ""]];
checks.getRange("B12").formulas = [["=IF(COUNTIF(F4:F9,\"FAIL\")=0,\"PASS\",\"FAIL\")"]];
checks.getRange("A12:B12").format = { fill: C.forest, font: { bold: true, color: C.white } };
checks.getRange("F4:F9").conditionalFormats.add("containsText", { text: "PASS", format: { fill: C.good, font: { color: C.forest, bold: true } } });
checks.getRange("F4:F9").conditionalFormats.add("containsText", { text: "FAIL", format: { fill: C.bad, font: { color: "#9C1C26", bold: true } } });
checks.getRange("A:A").format.columnWidth = 39;
checks.getRange("B:F").format.columnWidth = 17;
checks.getRange("B4:E9").format.numberFormat = "0.0000";

// Summary (built after calculations)
common(summary, "A:H");
title(summary, "A1:H1", "Noesis · Decisión de IA y precios");
summary.getRange("A2:H2").merge();
summary.getRange("A2").values = [["Modelo híbrido recomendado: cerebro propio para lo repetible, Qwen local/compatible para lenguaje libre y Haiku como respaldo de fiabilidad."]];
summary.getRange("A2").format = { font: { color: C.muted, italic: true }, wrapText: true };
section(summary, "A4:H4", "Decisión ejecutiva");
summary.getRange("A5:H8").merge();
summary.getRange("A5").values = [["Sí conviene construir servicio interno, pero no entrenar un modelo fundacional. La capa propia ya puede redactar recordatorios de cobro, seguimientos de presupuesto, citas, correos de gestoría y mensajes personalizados usando datos reales; cualquier envío requiere confirmación del titular. Para el piloto, mantener 29 € + IVA, subir Negocio a 49 € + IVA y Premium a 99 € + IVA si conserva 100 minutos de voz."]];
summary.getRange("A5").format = { fill: C.cream, font: { bold: true, size: 12, color: C.ink }, wrapText: true, verticalAlignment: "center" };
section(summary, "A10:H10", "Indicadores clave");
summary.getRange("A11:B11").merge(); summary.getRange("C11:D11").merge(); summary.getRange("E11:F11").merge(); summary.getRange("G11:H11").merge();
summary.getRange("A11").values = [["Contribución / cuenta actual"]];
summary.getRange("C11").values = [["Contribución / cuenta recom."]];
summary.getRange("E11").values = [["Break-even actual"]];
summary.getRange("G11").values = [["Break-even recomendado"]];
summary.getRange("A12:B13").merge(); summary.getRange("C12:D13").merge(); summary.getRange("E12:F13").merge(); summary.getRange("G12:H13").merge();
summary.getRange("A12").formulas = [["='Scale'!B12"]];
summary.getRange("C12").formulas = [["='Scale'!B13"]];
summary.getRange("E12").formulas = [["='Scale'!C12"]];
summary.getRange("G12").formulas = [["='Scale'!C13"]];
summary.getRange("A12:D12").format.numberFormat = "€#,##0.00";
summary.getRange("E12:H12").format.numberFormat = "#,##0 \"cuentas\"";
summary.getRange("A11:H13").format = { fill: C.white, borders: { preset: "outside", style: "thin", color: C.sand }, horizontalAlignment: "center", verticalAlignment: "center", font: { color: C.ink, bold: true } };
summary.getRange("A12:H13").format.font = { size: 18, bold: true, color: C.forest };
section(summary, "A16:H16", "Precio, coste y margen de contribución");
summary.getRange("A17:D17").values = [["Plan", "Precio actual", "Precio recomendado", "Margen recomendado"]];
headers(summary.getRange("A17:D17"));
summary.getRange("A18:A20").values = [["Autónomo"],["Negocio"],["Sin Límites"]];
summary.getRange("B18:B20").formulas = [["='Unit_Economics'!B5"],["='Unit_Economics'!C5"],["='Unit_Economics'!D5"]];
summary.getRange("C18:C20").formulas = [["='Unit_Economics'!E5"],["='Unit_Economics'!F5"],["='Unit_Economics'!G5"]];
summary.getRange("D18:D20").formulas = [["='Unit_Economics'!E19"],["='Unit_Economics'!F19"],["='Unit_Economics'!G19"]];
summary.getRange("B18:C20").format.numberFormat = "€#,##0.00";
summary.getRange("D18:D20").format.numberFormat = "0.0%";
summary.getRange("A23:E24").merge();
summary.getRange("A23").values = [["Regla de control: Noesis puede preparar, pero el autónomo autoriza transferencias, cobros, emisiones definitivas y envíos sensibles."]];
summary.getRange("A23").format = { fill: C.warn, font: { bold: true, color: C.ink }, wrapText: true, rowHeight: 38 };
summary.getRange("F31:G34").values = [["Plan", "Margen"],["Autónomo", null],["Negocio", null],["Sin Límites", null]];
summary.getRange("G32:G34").formulas = [["=D18*100"],["=D19*100"],["=D20*100"]];
headers(summary.getRange("F31:G31"));
summary.getRange("G32:G34").format.numberFormat = "0.0\"%\"";
const marginChart = summary.charts.add("column", summary.getRange("F31:G34"));
marginChart.titleText = "Margen de contribución recomendado (%)";
marginChart.hasLegend = false;
marginChart.setPosition("F17", "H29");
summary.getRange("A:H").format.columnWidth = 16;
summary.getRange("A:A").format.columnWidth = 22;
summary.getRange("A5:H8").format.rowHeight = 28;
summary.freezePanes.freezeRows(4);

// Add audit comments to key input cells.
await wb.comments.addThread({ cell: assumptions.getRange("B25") }, "Fuente: ECB, referencia 14/07/2026. 1 EUR = 1,1405 USD.");
await wb.comments.addThread({ cell: assumptions.getRange("B26") }, "Fuente: Stripe España. Tarjeta estándar emitida en el EEE.");
await wb.comments.addThread({ cell: assumptions.getRange("B29") }, "WhatsApp cobra por mensaje entregado; tarifa utility España usada como referencia y sujeta a cambios de Meta.");
await wb.comments.addThread({ cell: assumptions.getRange("B31") }, "Anthropic Haiku 4.5: $1/MTok input y $5/MTok output. Interacción modelo: 8k input + 1,2k output.");

await fs.mkdir(previewDir, { recursive: true });

const summaryInspect = await wb.inspect({ kind: "table", range: "Summary!A1:H23", include: "values,formulas", tableMaxRows: 25, tableMaxCols: 10, maxChars: 9000 });
console.log(summaryInspect.ndjson);
const errorInspect = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "final formula error scan", maxChars: 5000 });
console.log(errorInspect.ndjson);
const checkInspect = await wb.inspect({ kind: "table", range: "Checks!A1:F12", include: "values,formulas", tableMaxRows: 15, tableMaxCols: 8, maxChars: 7000 });
console.log(checkInspect.ndjson);

for (const sheetName of ["Summary", "Assumptions", "Unit_Economics", "Scale", "AI_Options", "Sources", "Checks"]) {
  const preview = await wb.render({ sheetName, autoCrop: "all", scale: 1.3, format: "png" });
  const bytes = new Uint8Array(await preview.arrayBuffer());
  await fs.writeFile(path.join(previewDir, `${sheetName}.png`), bytes);
}

await fs.mkdir(outputDir, { recursive: true });
const exported = await SpreadsheetFile.exportXlsx(wb);
await exported.save(outputFile);
console.log(JSON.stringify({ outputFile, previewDir }));
