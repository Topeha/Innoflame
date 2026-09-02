import { Workbook, SpreadsheetFile } from "file:///C:/Users/TommiHavukainen/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";
import fs from "node:fs/promises";
import path from "node:path";

const outputDir = "C:/Users/TommiHavukainen/OneDrive - Unikie Oy/Customer/Innoflame";
const outputPath = path.join(outputDir, "Innoflame_monthly_sales_summary.xlsx");

const rows = [
  ["2023-05", 72, 115615.36],
  ["2023-06", 511, 530716.34],
  ["2023-07", 184, 279723.06],
  ["2023-08", 459, 452181.54],
  ["2023-09", 549, 685548.35],
  ["2023-10", 562, 626419.37],
  ["2023-11", 769, 1715247.65],
  ["2023-12", 835, 1239736.23],
  ["2024-01", 933, 971547.58],
  ["2024-02", 785, 1147642.71],
  ["2024-03", 1082, 1796860.69],
  ["2024-04", 1612, 1446459.94],
  ["2024-05", 1771, 1574501.37],
  ["2024-06", 1462, 1477990.75],
  ["2024-07", 666, 493459.86],
  ["2024-08", 1816, 942488.73],
  ["2024-09", 2065, 1377871.77],
  ["2024-10", 2171, 1995794.46],
  ["2024-11", 2093, 1956477.00],
  ["2024-12", 2291, 1526149.17],
  ["2025-01", 1942, 1411550.47],
  ["2025-02", 1728, 1702711.84],
  ["2025-03", 1835, 1494662.31],
  ["2025-04", 2192, 1918357.07],
  ["2025-05", 2137, 1616629.78],
  ["2025-06", 2423, 2007170.21],
  ["2025-07", 1037, 977825.09],
  ["2025-08", 1809, 1489760.14],
  ["2025-09", 2524, 1986819.38],
  ["2025-10", 3083, 2894048.57],
  ["2025-11", 2970, 2822578.77],
  ["2025-12", 2304, 1770694.96],
  ["2026-01", 1833, 1783685.46],
  ["2026-02", 1518, 1386534.24],
  ["2026-03", 1997, 1849011.09],
  ["2026-04", 1979, 1650421.97],
  ["2026-05", 1708, 1279301.84],
];

const workbook = Workbook.create();
workbook.apply([
  { op: "sheet.add", name: "Kuukausisummaa" },
  { op: "sheet.add", name: "Graafi" },
  { op: "range.values.set", target: { sheet: "Kuukausisummaa", range: "A1:C39" }, values: [
    ["Kuukausi", "Rivien määrä", "Kuukausisummaa"],
    ...rows,
    ["Yhteensä", { formula: "=SUM(B2:B38)" }, { formula: "=SUM(C2:C38)" }],
  ]},
  { op: "range.format.set", target: { sheet: "Kuukausisummaa", range: "A1:C1" }, props: { font: { bold: true }, fill: "#1F4E78", color: "#FFFFFF" } },
  { op: "range.format.set", target: { sheet: "Kuukausisummaa", range: "B2:B39" }, props: { numberFormat: "#,##0" } },
  { op: "range.format.set", target: { sheet: "Kuukausisummaa", range: "C2:C39" }, props: { numberFormat: "#,##0.00" } },
  { op: "range.format.set", target: { sheet: "Kuukausisummaa", range: "A39:C39" }, props: { font: { bold: true }, fill: "#D9EAF7" } },
  { op: "range.format.set", target: { sheet: "Kuukausisummaa", range: "A1:C39" }, props: { borders: { preset: "all", style: "solid", color: "#D0D7DE" } } },
  { op: "chart.add", sheet: "Graafi", props: {
    chartType: "line",
    anchor: { from: { row: 1, col: 1, rowOffsetPx: 4, colOffsetPx: 8 }, extent: { widthPx: 950, heightPx: 520 } },
    title: "Kuukausittainen myyntisummaa",
    categories: rows.map(r => r[0]),
    series: [{ name: "Kuukausisummaa", values: rows.map(r => r[2]) }],
    hasLegend: true,
    legend: { position: "bottom" },
    dataLabels: { showValue: false }
  }},
]);

const out = await SpreadsheetFile.exportXlsx(workbook);
await fs.mkdir(outputDir, { recursive: true });
await out.save(outputPath);
console.log(outputPath);
