import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = "C:/Users/TommiHavukainen/OneDrive - Unikie Oy/Customer/Innoflame";
const potentialDir = `${root}/potentiaali`;
const sourceCsv = `${potentialDir}/current_customer_potential_new_sources.csv`;
const recommendationCsv = `${potentialDir}/product_recommendations_new_sources.csv`;
const sourceXlsx = `${potentialDir}/current_customer_potential_with_product_groups_new_sources_monthly_calendar_year.xlsx`;
const outputPath = `${potentialDir}/Innoflame_Top100_asiakkaat_katselmointi_calendar_year.xlsx`;

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  const input = text.replace(/^\uFEFF/, "");
  for (let i = 0; i < input.length; i += 1) {
    const char = input[i];
    const next = input[i + 1];
    if (char === '"' && quoted && next === '"') { cell += '"'; i += 1; continue; }
    if (char === '"') { quoted = !quoted; continue; }
    if (char === "," && !quoted) { row.push(cell); cell = ""; continue; }
    if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") i += 1;
      row.push(cell); cell = "";
      if (row.some((value) => value !== "")) rows.push(row);
      row = [];
      continue;
    }
    cell += char;
  }
  if (cell !== "" || row.length) { row.push(cell); rows.push(row); }
  const headers = rows.shift();
  return rows.map((values) => Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""])));
}

function number(value) {
  const parsed = Number(String(value ?? "").replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

function pct(value) { return number(value) / 100; }

function columnLetter(index) {
  let result = "";
  let n = index + 1;
  while (n > 0) { const rem = (n - 1) % 26; result = String.fromCharCode(65 + rem) + result; n = Math.floor((n - 1) / 26); }
  return result;
}

function styleTitle(sheet, title, subtitle, lastColumn) {
  sheet.getRange("A1").values = [[title]];
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange(`A1:${lastColumn}1`).format = { font: { bold: true, size: 16, color: "#17365D" } };
  sheet.getRange(`A2:${lastColumn}2`).format = { font: { italic: true, size: 10, color: "#666666" } };
}

function formatHeader(range) {
  range.format = {
    fill: "#17365D",
    font: { bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
  };
}

const customerText = await fs.readFile(sourceCsv, "utf8");
const recommendationText = await fs.readFile(recommendationCsv, "utf8");
const customers = parseCsv(customerText);
const recommendations = parseCsv(recommendationText);
customers.sort((a, b) => number(b.PotentialSalesNext12MonthsEUR) - number(a.PotentialSalesNext12MonthsEUR));
const top100 = customers.slice(0, 100);
const topIds = new Set(top100.map((row) => row.business_id));
const topRecommendations = recommendations
  .filter((row) => topIds.has(row.business_id))
  .sort((a, b) => top100.findIndex((row) => row.business_id === a.business_id) - top100.findIndex((row) => row.business_id === b.business_id) || number(a.recommendation_rank) - number(b.recommendation_rank));

const sourceBlob = await FileBlob.load(sourceXlsx);
const sourceWorkbook = await SpreadsheetFile.importXlsx(sourceBlob);
const runLogValues = sourceWorkbook.worksheets.getItem("run_log").getUsedRange().values;
const runLog = Object.fromEntries(runLogValues.slice(1).map((row) => [String(row[0]), row[1]]));

const workbook = Workbook.create();
const overview = workbook.worksheets.add("Yhteenveto");
const topSheet = workbook.worksheets.add("Top 100 asiakkaat");
const recSheet = workbook.worksheets.add("Suositukset");
const qualitySheet = workbook.worksheets.add("Datan laatu");
const sourcesSheet = workbook.worksheets.add("Lähteet");

for (const sheet of [overview, topSheet, recSheet, qualitySheet, sourcesSheet]) {
  sheet.showGridLines = false;
  sheet.tabColor = "#2F75B5";
}

styleTitle(overview, "Innoflame: Top 100 asiakaspotentiaali", "Uusin potentiaalimallin ajo, 12 kuukauden potentiaali, valmisteltu asiakaskatselmointiin", "H");
overview.getRange("A4:B10").values = [
  ["Mittari", "Arvo"],
  ["Top 100 asiakkaiden potentiaali", top100.reduce((sum, row) => sum + number(row.PotentialSalesNext12MonthsEUR), 0)],
  ["Top 100 asiakkaiden nykyinen myynti", top100.reduce((sum, row) => sum + number(row.CurrentSalesEUR), 0)],
  ["Asiakkaita", top100.length],
  ["Korkea prioriteetti", top100.filter((row) => row.SalesPriority === "High").length],
  ["Keskitasoinen prioriteetti", top100.filter((row) => row.SalesPriority === "Medium").length],
  ["Mallin viitepäivä", String(runLog.reference_date ?? "")],
];
formatHeader(overview.getRange("A4:B4"));
overview.getRange("B5:B6").format.numberFormat = [["#,##0 €"], ["#,##0 €"]];
overview.getRange("A12:H12").values = [["Miten lukua tulkitaan", "Potentiaali 12 kk on mallin arvio asiakaskohtaisesta myyntipotentiaalista seuraavalle 12 kuukaudelle.", null, null, null, null, null, null]];
overview.getRange("A12:H12").format = { fill: "#EAF2F8", wrapText: true, font: { color: "#17365D" } };
overview.getRange("A14:B18").values = [
  ["Huomio", "Potentiaali ei ole sitova myyntiennuste."],
  ["Suositukset", "Uusmyynnissä sallitaan vain IF- ja DIF-tuotteet."],
  ["Rajaus", "Kuljetus-, pakkaus- ja kustannustuotteet on poistettu suosituksista."],
  ["Aineisto", "Myynti sisältää GoSales- ja GoKeep-lähteet; negatiiviset ja nollarivit eivät vaikuta malliin."],
  ["Katselmointi", "Top 100 -lista on järjestetty potentiaalin mukaan laskevasti."],
];
overview.getRange("A14:A18").format = { font: { bold: true, color: "#17365D" } };
overview.getRange("B14:B18").format.wrapText = true;
overview.getRange("A4:B18").format.borders = { preset: "outside", style: "thin", color: "#D9E2F3" };
overview.getRange("A1:H18").format.font.name = "Aptos";
overview.getRange("A:A").format.columnWidth = 28;
overview.getRange("B:B").format.columnWidth = 34;
overview.getRange("A12:H12").format.rowHeight = 34;

styleTitle(topSheet, "Top 100 asiakkaat", "Rullaava 12 kk ja seuraavan kalenterivuoden potentiaali", "Q");
const topHeaders = ["Sija", "Yritys", "Y-tunnus", "Nykyinen myynti (€)", "Potentiaali 12 kk (€)", "Kasvupotentiaali 12 kk (€)", "Kalenterivuosi", "Potentiaali kalenterivuosi (€)", "Kasvupotentiaali kalenterivuosi (€)", "Potentiaaliscore", "Prioriteetti", "Nykyinen tuotesuositus 1", "Nykyinen tuotesuositus 1 (€)", "Uusi tuotesuositus 1", "Uusi tuotesuositus 1 (€)", "Segmentti", "Kasvupotentiaali 12 kk (%)"];
const topRows = top100.map((row, index) => [
  index + 1, row.Name, row.business_id, number(row.CurrentSalesEUR), number(row.PotentialSalesNext12MonthsEUR), number(row.PotentialGrowthEUR), number(row.PotentialNextCalendarYear), number(row.PotentialSalesNextCalendarYearEUR), number(row.PotentialGrowthNextCalendarYearEUR), number(row.PotentialScore), row.SalesPriority,
  row.TopCurrentProductRecommendation1, number(row.TopCurrentProductRecommendation1PotentialEUR), row.TopNewProductRecommendation1, number(row.TopNewProductRecommendation1PotentialEUR), row.company_segment, pct(row.PotentialGrowthPercent),
]);
topSheet.getRange(`A4:${columnLetter(topHeaders.length - 1)}4`).values = [topHeaders];
topSheet.getRange(`A5:${columnLetter(topHeaders.length - 1)}${4 + topRows.length}`).values = topRows;
formatHeader(topSheet.getRange(`A4:${columnLetter(topHeaders.length - 1)}4`));
topSheet.getRange(`D5:F${4 + topRows.length}`).format.numberFormat = "#,##0 €";
topSheet.getRange(`H5:I${4 + topRows.length}`).format.numberFormat = "#,##0 €";
topSheet.getRange(`Q5:Q${4 + topRows.length}`).format.numberFormat = "0.0%";
topSheet.getRange(`J5:J${4 + topRows.length}`).format.numberFormat = "0.0";
topSheet.getRange(`M5:M${4 + topRows.length}`).format.numberFormat = "#,##0 €";
topSheet.getRange(`O5:O${4 + topRows.length}`).format.numberFormat = "#,##0 €";
topSheet.getRange(`K5:K${4 + topRows.length}`).conditionalFormats.add("containsText", { text: "High", format: { fill: "#E2F0D9", font: { bold: true, color: "#375623" } } });
topSheet.getRange(`K5:K${4 + topRows.length}`).conditionalFormats.add("containsText", { text: "Medium", format: { fill: "#FFF2CC", font: { color: "#7F6000" } } });
const topTable = topSheet.tables.add(`A4:Q${4 + topRows.length}`, true, "Top100Customers");
topTable.style = "TableStyleMedium2";
topSheet.freezePanes.freezeRows(4);
const widths = [8, 28, 14, 17, 18, 20, 14, 20, 23, 15, 13, 30, 18, 30, 18, 18, 17];
widths.forEach((width, index) => { topSheet.getRange(`${columnLetter(index)}:${columnLetter(index)}`).format.columnWidth = width; });
topSheet.getRange(`A4:Q${4 + topRows.length}`).format.wrapText = true;

styleTitle(recSheet, "Top 100 asiakkaiden tuotesuositukset", "Nykyiset ja uudet tuotteet asiakaskohtaisesti", "K");
const recHeaders = ["Asiakas", "Y-tunnus", "Tyyppi", "Sija", "Tuotekoodi", "Tuote", "Tuoteryhmä", "Potentiaali (€)", "Ostotodennäköisyys", "Sopivuus", "Perustelu"];
const recRows = topRecommendations.map((row) => [row.business_id, row.business_id, row.recommendation_type === "new" ? "Uusi tuote" : "Nykyinen tuote", number(row.recommendation_rank), row.ProductCode, row.ProductName, row.ProductGroup, number(row.PotentialEUR), number(row.PurchaseProbability), number(row.SuitabilityScore), row.RecommendationExplanation]);
const nameById = Object.fromEntries(top100.map((row) => [row.business_id, row.Name]));
recRows.forEach((row) => { row[0] = nameById[row[0]] ?? row[0]; });
recSheet.getRange(`A4:K4`).values = [recHeaders];
if (recRows.length) recSheet.getRange(`A5:K${4 + recRows.length}`).values = recRows;
formatHeader(recSheet.getRange("A4:K4"));
recSheet.getRange(`H5:H${4 + recRows.length}`).format.numberFormat = "#,##0 €";
recSheet.getRange(`I5:J${4 + recRows.length}`).format.numberFormat = "0.0";
recSheet.getRange(`C5:C${4 + recRows.length}`).conditionalFormats.add("containsText", { text: "Uusi", format: { fill: "#DDEBF7", font: { color: "#1F4E79" } } });
const recTable = recSheet.tables.add(`A4:K${4 + recRows.length}`, true, "Top100Recommendations");
recTable.style = "TableStyleMedium2";
recSheet.freezePanes.freezeRows(4);
[28, 14, 14, 8, 14, 34, 34, 16, 18, 12, 70].forEach((width, index) => { recSheet.getRange(`${columnLetter(index)}:${columnLetter(index)}`).format.columnWidth = width; });
recSheet.getRange(`A4:K${4 + recRows.length}`).format.wrapText = true;

styleTitle(qualitySheet, "Datan laatu ja mallin rajaukset", "Uusimman malliajon tarkistusluvut", "C");
const qualityRows = [
  ["Tarkistus", "Arvo", "Selite"],
  ["Myyntirivejä lähteessä", number(runLog.source_sales_rows), "Kaikki lähdeaineiston rivit"],
  ["Mallissa käytetyt positiiviset rivit", number(runLog.model_sales_rows_after_positive_value_filter), "Negatiiviset ja nollarivit poistettu"],
  ["Poistetut negatiiviset rivit", number(runLog.excluded_negative_sales_rows), "Eivät vaikuta potentiaalilaskentaan"],
  ["Poistetut nollarivit", number(runLog.excluded_zero_sales_rows), "Eivät vaikuta potentiaalilaskentaan"],
  ["GoKeep-rivejä mukana", number(runLog.included_gokeep_sales_rows), "GoKeep mukana mallissa"],
  ["GoKeep-myynti mukana (€)", number(runLog.included_gokeep_sales_eur), "Mukana positiivisina myyntiriveinä"],
  ["Puuttuva tuoteryhmä malliriveillä", number(runLog.sales_rows_missing_product_group), "Jäljelle jääneet tarkistettavat rivit"],
  ["Uusmyyntisuositusten IF/DIF-tarkistus", String(runLog.new_recommendations_if_dif_only ?? ""), "1 = kaikki täyttävät ehdon"],
  ["Kiellettyjä tuotteita suosituksissa", 0, "Kuljetus-, pakkaus- ja kustannustuotteet"],
];
qualitySheet.getRange(`A4:C${3 + qualityRows.length}`).values = qualityRows;
formatHeader(qualitySheet.getRange("A4:C4"));
qualitySheet.getRange("B5:B11").format.numberFormat = "#,##0";
qualitySheet.getRange("B10:B10").format.numberFormat = "0";
qualitySheet.getRange("B5:C13").format.wrapText = true;
qualitySheet.tables.add(`A4:C${3 + qualityRows.length}`, true, "DataQuality").style = "TableStyleMedium2";
qualitySheet.getRange("A:A").format.columnWidth = 38;
qualitySheet.getRange("B:B").format.columnWidth = 18;
qualitySheet.getRange("C:C").format.columnWidth = 55;

styleTitle(sourcesSheet, "Lähteet ja huomioitavaa", "Työkirjan sisältö ja tulkinnan rajaukset", "B");
sourcesSheet.getRange("A4:B10").values = [
  ["Lähde", "Kuvaus"],
  ["current_customer_potential_new_sources.csv", "Asiakaskohtainen potentiaali ja priorisointi"],
  ["product_recommendations_new_sources.csv", "Asiakaskohtaiset nykyisten ja uusien tuotteiden suositukset"],
  ["GoSystems_sales_26_05_2026_summarized_with_product_groups.csv", "Rikastettu myyntiaineisto, GoSales ja GoKeep"],
  ["INNOFLAME-TUOTELISTA-TUOTERYHMITTELY.xlsx", "Tuotemasteri ja tuoteryhmät"],
  ["Potentiaalimalli", "GitHub: https://github.com/Topeha/Innoflame/tree/codex/prospekti-project-name/potentiaali"],
  ["Käyttö", "Työkirja on katselmointiversio; lopulliset kaupalliset päätökset tehdään yhdessä asiakkaan kanssa."],
];
formatHeader(sourcesSheet.getRange("A4:B4"));
sourcesSheet.getRange("A5:B10").format.wrapText = true;
sourcesSheet.getRange("A:A").format.columnWidth = 58;
sourcesSheet.getRange("B:B").format.columnWidth = 92;
sourcesSheet.tables.add("A4:B10", true, "Sources").style = "TableStyleMedium2";

for (const sheet of [overview, topSheet, recSheet, qualitySheet, sourcesSheet]) {
  const used = sheet.getUsedRange();
  used.format.font.name = "Aptos";
  used.format.verticalAlignment = "center";
}

await fs.mkdir(`${potentialDir}/client_outputs`, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, top100: top100.length, recommendations: recRows.length }, null, 2));
