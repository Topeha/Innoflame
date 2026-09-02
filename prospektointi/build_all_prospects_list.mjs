import { Workbook, SpreadsheetFile } from "file:///C:/Users/TommiHavukainen/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";
import fs from "node:fs/promises";
import path from "node:path";

const baseDir = "C:/Users/TommiHavukainen/OneDrive - Unikie Oy/Customer/Innoflame";
const csvPath = path.join(baseDir, "prospect_segment_model_all_prospects.csv");
const outputPath = path.join(baseDir, "prospect_all.xlsx");

const csvText = await fs.readFile(csvPath, "utf8");
const workbook = await Workbook.fromCSV(csvText, { sheetName: "All Prospects" });

workbook.apply([
  { op: "sheet.set", target: "All Prospects", props: { name: "All Prospects" } },
  { op: "range.format.set", target: { sheet: "All Prospects", range: "A1:T1" }, props: { font: { bold: true }, fill: "#1F4E78", color: "#FFFFFF" } },
  { op: "range.format.set", target: { sheet: "All Prospects", range: "A2:A5000" }, props: { numberFormat: "0" } },
  { op: "range.format.set", target: { sheet: "All Prospects", range: "B2:B5000" }, props: { numberFormat: "@\"\"" } },
  { op: "range.format.set", target: { sheet: "All Prospects", range: "F2:F5000" }, props: { numberFormat: "0.000" } },
  { op: "range.format.set", target: { sheet: "All Prospects", range: "G2:I5000" }, props: { numberFormat: "#,##0.00" } },
  { op: "range.format.set", target: { sheet: "All Prospects", range: "J2:J5000" }, props: { numberFormat: "#,##0" } },
  { op: "range.format.set", target: { sheet: "All Prospects", range: "K2:K5000" }, props: { numberFormat: "#,##0.00" } },
  { op: "range.format.set", target: { sheet: "All Prospects", range: "L2:L5000" }, props: { numberFormat: "#,##0" } },
  { op: "range.format.set", target: { sheet: "All Prospects", range: "M2:M5000" }, props: { numberFormat: "@" } },
  { op: "range.format.set", target: { sheet: "All Prospects", range: "N2:N5000" }, props: { numberFormat: "@" } },
  { op: "range.format.set", target: { sheet: "All Prospects", range: "O2:O5000" }, props: { numberFormat: "@" } },
  { op: "range.format.set", target: { sheet: "All Prospects", range: "P2:P5000" }, props: { numberFormat: "#,##0.00" } },
  { op: "range.format.set", target: { sheet: "All Prospects", range: "Q2:Q5000" }, props: { numberFormat: "@" } },
  { op: "range.format.set", target: { sheet: "All Prospects", range: "R2:R5000" }, props: { numberFormat: "@" } },
  { op: "range.format.set", target: { sheet: "All Prospects", range: "S2:S5000" }, props: { numberFormat: "@" } },
  { op: "range.format.set", target: { sheet: "All Prospects", range: "T2:T5000" }, props: { numberFormat: "yyyy-mm-dd" } },
]);

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(outputPath);
