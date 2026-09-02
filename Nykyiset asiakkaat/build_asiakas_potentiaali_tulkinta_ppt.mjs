import fs from "node:fs/promises";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const OUT = "C:/Users/TommiHavukainen/OneDrive - Unikie Oy/Customer/Innoflame/Nykyiset asiakkaat/Innoflame_asiakas_potentiaali_tulkinta_ja_malli_uusin_malli_valilehdet_crm_validointi.pptx";
const PREVIEW_DIR = "C:/Users/TommiHavukainen/AppData/Local/Temp/codex-presentations/manual-asiakas-potentiaali/tulkinta-ppt/preview";
const MONTAGE = `${PREVIEW_DIR}/montage.webp`;

const C = {
  canvas: "#FFFFFF",
  ink: "#0B0B0B",
  muted: "#555555",
  panel: "#EDEDED",
  rule: "#B8BCC4",
  accent: "#FF6B35",
  softAccent: "#FFE4D8",
  green: "#6AA84F",
  softGreen: "#D9EAD3",
};

const data = {
  customerRows: 6266,
  matchedCustomers: 4734,
  recommendationRows: 23670,
  validationRows: 6732,
  modelPotentialM: 40.8,
  expectedPotentialM: 20.2,
  recExpectedM: 23.0,
  probabilityMedian: 16.2,
  probabilityMax: 90.0,
  missingBusinessId: 466,
  priority: [
    ["A", 74, 13.1, 136.6],
    ["B", 249, 24.5, 95.3],
    ["C", 232, 17.6, 75.3],
    ["D", 4179, 61.5, 6.2],
  ],
  validation: [
    ["Model above CRM", 4263],
    ["Missing CRM kept", 1542],
    ["Model may be low", 342],
    ["Aligned", 119],
  ],
  crmValidation: {
    crmRows: 32716,
    crmNames: 5534,
    crmMatches: 4724,
    missingKept: 1542,
    modelMayBeLow: 342,
    raisedToCrm: 401,
  },
  productGroups: [
    ["Hupparit ja colleget", 4.0],
    ["Tarrat ja etiketit", 3.8],
    ["Vyöt", 2.9],
    ["Lippalakit", 2.9],
    ["Pipot", 2.6],
    ["Tarkistettavat", 1.8],
    ["T-paidat", 1.7],
  ],
  backtest: {
    actual2025M: 20.48,
    historyExpectedM: 20.24,
    historyBiasM: -0.25,
    historyCorrelation: 0.80,
    historyAuc: 0.72,
    historyMae: 2489,
  },
  salesPotential: {
    baseForecastM: 20.24,
    productGroupGrowthPoolM: 80.42,
    growthPotentialM: 15.03,
    realisticPotentialM: 40.78,
    upsidePotentialM: 48.23,
    growthVs2025M: 20.30,
    growthVs2025Pct: 99.1,
    customersWithGrowth: 4734,
  },
  errorBuckets: [
    ["Good fit", 4349],
    ["Medium error", 1461],
    ["Model over high", 242],
    ["Model under high", 214],
  ],
  featureImportance: [
    ["2026 YTD sales", 9.7],
    ["Current probability", 3.2],
    ["Segment lift", 2.8],
    ["Score", 1.0],
    ["Revenue", 0.7],
    ["Avg monthly 2024", 0.7],
    ["Sales 2024", 0.7],
    ["Momentum 2024 vs 2023", 0.6],
  ],
  backtestProductGroups: [
    ["Sales promotion", 7.78, 7.78],
    ["Kevyt työvaatetus", 3.05, 3.05],
    ["Liikelahjat", 2.85, 2.85],
    ["HR-lahjat", 1.04, 1.04],
    ["Hupparit ja colleget", 0.37, 0.37],
    ["Raskas työvaatetus", 0.36, 0.36],
  ],
  productGroupCalibration: {
    actualM: 19.27,
    rawM: 7.50,
    calibratedM: 20.10,
    rawBiasM: -11.77,
    calibratedBiasM: 0.83,
  },
  topProbabilityCustomers: [
    ["BMH Technology Oy", "1713440-0", 98.6, 13462],
    ["CABB Oy", "1031310-7", 98.1, 22014],
    ["Restel Ravintolat Oy", "0658353-4", 98.1, 24157],
    ["Agco Power Oy", "0986815-6", 97.9, 31769],
    ["Ammattiopisto Luovi Oy", "3240571-5", 97.8, 20057],
    ["Suur-Seudun Osuuskauppa SSO", "1834868-9", 97.7, 60607],
    ["Maakunnan Auto", "2212880-6", 97.6, 22679],
    ["NG Nordic Finland Oy", "0350017-4", 97.5, 47935],
    ["KONTIOTUOTE OY", "0243055-7", 97.5, 13473],
    ["Lindab oy", "0920791-3", 97.5, 13703],
  ],
  topRenewalPotentialCustomers: [
    ["Hartwall", "0213454-7", 1594521, 63.0],
    ["Ponsse Oyj", "0934209-0", 1065073, 96.7],
    ["Telia Finland Oyj", "1475607-9", 908050, 96.7],
    ["Koiviston Auto konserni", "3254069-3", 841050, 65.6],
    ["Makita", "1651936-8", 706177, 74.0],
    ["K-ryhma", "0109862-8", 572209, 57.8],
    ["LIWLIG Finland Oy", "2068393-7", 508401, 75.7],
    ["Fortum", "1463611-4", 490041, 73.6],
    ["DNA Oyj", "0592509-6", 452584, 71.9],
    ["TREDU/Tampereen seudun ammattiopisto", "0211675-2", 433347, 58.8],
  ],
  sheetGuidePart1: [
    ["summary", "Yhteenveto mallin osuvuudesta.", "Katso ensin: toteuma, ennuste, bias, korrelaatio ja AUC."],
    ["next_year_forecast", "Konservatiivinen run-rate ennuste.", "Kayta perusennusteena nykyisella ostotasolla."],
    ["next_year_summary", "Run-rate ennusteen yhteenveto.", "Tarkista 2026 YTD annualisointi ja ero vuoden 2025 toteumaan."],
    ["sales_potential_case", "Myynnillinen potentiaalicase.", "Priorisoi asiakkaat realistisen kasvumahdollisuuden mukaan."],
    ["sales_potential_summary", "Potentiaalicasen yhteenveto.", "Vertaa run-rate ennustetta ja myynnillista potentiaalia."],
    ["customer_backtest_2025", "Asiakaskohtainen backtest.", "Etsi asiakkaat, joissa malli osuu tai poikkeaa toteumasta."],
  ],
  sheetGuidePart2: [
    ["history_features", "Asiakkaan ostohistoriafeaturet.", "Tarkista mihin asiakkaan vuosiarvio perustuu."],
    ["probability_calibration", "Todennakoisyyden kalibrointi.", "Arvioi onko probability_of_growth realistinen toteumaan verrattuna."],
    ["product_group_model", "Asiakas x tuoteryhma -tason backtest.", "Nayttaa ryhmakohtaisen white space -arvion ja toteuman."],
    ["product_group_summary", "Tuoteryhmien yhteenveto.", "Vertaa tuoteryhmien toteumaa, raakaa ennustetta ja kalibroitua ennustetta."],
    ["product_group_calibration", "Tuoteryhmakohtaiset kertoimet.", "Kayta kun haluat nahda miksi Sales promotion tai tyovaatetus skaalautuu."],
    ["recommendations_calibrated", "Kalibroitu myyntisuosituslista.", "Kayta myynnin tuoteryhmapriorisointiin asiakkaan tasolla."],
  ],
  sheetGuidePart3: [
    ["crm_potential_validation", "CRM Status/Sales/Probability -validointi.", "Tarkista onko malli liian pieni tai linjassa CRM-pipelinen kanssa."],
    ["crm_validation_summary", "CRM-validoinnin yhteenveto.", "Nayttaa osumat, puuttuvat CRM-osumat ja nostetut arvot."],
    ["crm_unmatched_names", "CRM-nimet ilman account-osumaa.", "Kayta nimikohdistuksen laadun parantamiseen."],
    ["error_analysis", "Suurimmat yli- ja aliarviot.", "Valitse tarkistettavat asiakkaat ja opi missa malli erehtyy."],
    ["sales_feedback_template", "Myynnin palautepohja.", "Tayta korjattu potentiaali, syy ja kommentti seuraavaa mallia varten."],
    ["feature_importance", "Mallin tarkeimmat signaalit.", "Selittaa mitka ostohistoria- ja score-signaalit vaikuttavat eniten."],
    ["model_notes", "Mallin dokumentaatio.", "Tarkista mallin tarkoitus, rajaukset ja laskennan paaperiaatteet."],
  ],
};

async function writeBlob(path, blob) {
  await fs.writeFile(path, new Uint8Array(await blob.arrayBuffer()));
}

function addText(slide, text, position, style = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    fontFace: "Helvetica Neue",
    fontSize: style.fontSize ?? 22,
    color: style.color ?? C.ink,
    bold: style.bold ?? false,
    alignment: style.alignment ?? "left",
  };
  return shape;
}

function addPanel(slide, position, fill = C.panel) {
  return slide.shapes.add({
    geometry: "rect",
    position,
    fill,
    line: { style: "solid", fill: "none", width: 0 },
  });
}

function addRule(slide, left, top, width) {
  slide.shapes.add({
    geometry: "rect",
    position: { left, top, width, height: 1 },
    fill: C.rule,
    line: { style: "solid", fill: "none", width: 0 },
  });
}

function addFooter(slide, n) {
  addRule(slide, 42, 660, 1196);
  addText(slide, "Source: model_improvement_next_year_recent_weighted.xlsx, Innoflame removed", { left: 42, top: 674, width: 760, height: 24 }, { fontSize: 13, color: C.muted });
  addText(slide, String(n), { left: 1186, top: 674, width: 52, height: 24 }, { fontSize: 13, color: C.muted, alignment: "right" });
}

function addTitle(slide, title, subtitle, n) {
  addText(slide, title, { left: 42, top: 42, width: 1120, height: 88 }, { fontSize: 38, bold: true });
  if (subtitle) addText(slide, subtitle, { left: 42, top: 132, width: 1020, height: 58 }, { fontSize: 20, color: C.muted });
  addFooter(slide, n);
}

function addMetric(slide, label, value, note, x, y, w = 260) {
  addText(slide, label.toUpperCase(), { left: x, top: y, width: w, height: 28 }, { fontSize: 14, bold: true, color: C.muted });
  addText(slide, value, { left: x, top: y + 32, width: w, height: 68 }, { fontSize: 45, bold: true });
  addText(slide, note, { left: x, top: y + 100, width: w, height: 56 }, { fontSize: 18, color: C.muted });
}

function addStep(slide, number, title, body, x, y, fill = C.panel) {
  addPanel(slide, { left: x, top: y, width: 330, height: 270 }, fill);
  addText(slide, number, { left: x + 26, top: y + 28, width: 60, height: 52 }, { fontSize: 42, bold: true, color: fill === C.softAccent ? C.accent : C.ink });
  addText(slide, title, { left: x + 26, top: y + 96, width: 270, height: 70 }, { fontSize: 25, bold: true });
  addText(slide, body, { left: x + 26, top: y + 176, width: 270, height: 70 }, { fontSize: 18, color: C.muted });
}

function addCustomerTable(slide, rows, columns, x, y, width, rowHeight = 38) {
  const colWidths = columns.map((col) => col.width);
  addPanel(slide, { left: x, top: y, width, height: 40 }, C.ink);
  let left = x + 14;
  for (const col of columns) {
    addText(slide, col.label, { left, top: y + 10, width: col.width - 10, height: 22 }, { fontSize: 14, bold: true, color: "#FFFFFF" });
    left += col.width;
  }
  rows.forEach((row, index) => {
    const top = y + 42 + index * rowHeight;
    addPanel(slide, { left: x, top, width, height: rowHeight - 2 }, index % 2 === 0 ? C.panel : "#FFFFFF");
    let cellLeft = x + 14;
    columns.forEach((col, colIndex) => {
      addText(slide, String(row[colIndex]), { left: cellLeft, top: top + 8, width: col.width - 10, height: 22 }, { fontSize: 15, bold: colIndex === 0, color: colIndex === 0 ? C.ink : C.muted });
      cellLeft += col.width;
    });
  });
}

function addSheetGuideTable(slide, rows, x, y) {
  const columns = [
    { label: "Valilehti", width: 270 },
    { label: "Miksi se on mukana", width: 360 },
    { label: "Mihin sita kaytetaan", width: 410 },
  ];
  addPanel(slide, { left: x, top: y, width: 1040, height: 40 }, C.ink);
  let left = x + 14;
  for (const col of columns) {
    addText(slide, col.label, { left, top: y + 10, width: col.width - 10, height: 22 }, { fontSize: 14, bold: true, color: "#FFFFFF" });
    left += col.width;
  }
  rows.forEach((row, index) => {
    const top = y + 42 + index * 60;
    addPanel(slide, { left: x, top, width: 1040, height: 58 }, index % 2 === 0 ? C.panel : "#FFFFFF");
    let cellLeft = x + 14;
    row.forEach((value, colIndex) => {
      const width = columns[colIndex].width - 12;
      addText(slide, String(value), { left: cellLeft, top: top + 8, width, height: 42 }, { fontSize: colIndex === 0 ? 15 : 14, bold: colIndex === 0, color: colIndex === 0 ? C.ink : C.muted });
      cellLeft += columns[colIndex].width;
    });
  });
}

const ppt = Presentation.create({ slideSize: { width: 1280, height: 720 } });

// 1. Cover
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addText(slide, "Innoflame", { left: 42, top: 42, width: 240, height: 40 }, { fontSize: 22, bold: true });
  addText(slide, "Asiakaspotentiaalitaulukon tulkinta ja mallin rakenne", { left: 42, top: 176, width: 760, height: 180 }, { fontSize: 58, bold: true });
  addText(slide, "Miten taulukkoa luetaan, mitä sarakkeet tarkoittavat ja miten malli muodostaa vuositason potentiaalin nykyasiakkaille.", { left: 42, top: 400, width: 720, height: 90 }, { fontSize: 24, color: C.muted });
  addPanel(slide, { left: 878, top: 130, width: 300, height: 374 }, C.panel);
  addText(slide, "6 266", { left: 914, top: 196, width: 230, height: 70 }, { fontSize: 54, bold: true });
  addText(slide, "asiakasrivia", { left: 914, top: 272, width: 230, height: 34 }, { fontSize: 21, color: C.muted });
  addText(slide, "40,8 MEUR", { left: 914, top: 370, width: 230, height: 58 }, { fontSize: 42, bold: true, color: C.accent });
  addText(slide, "realistinen 2027 potentiaalicase", { left: 914, top: 432, width: 230, height: 52 }, { fontSize: 18, color: C.muted });
  addFooter(slide, 1);
}

// 2. Workbook map
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Taulukko on jaettu käyttötarkoituksen mukaan viiteen näkymään", "Aloita asiakaskohtaisesta potentiaalista, siirry tuoteryhmäsuosituksiin ja käytä validointia CRM-vertailuun.", 2);
  addStep(slide, "1", "customer_potential", "Asiakaskohtainen pisteytys, euroarvo, todennäköisyys ja prioriteetti.", 58, 230);
  addStep(slide, "2", "product groups", "Sheet product_group_recommendations kertoo, mitä tuoteryhmiä asiakkaalle kannattaa myydä.", 475, 230, C.softAccent);
  addStep(slide, "3", "validation_against_crm", "Malli vs CRM-potentiaali sekä poikkeamien status.", 892, 230);
  addText(slide, "run_log kertoo ajon asetukset ja data_quality näyttää rivit, joilla puuttuu tunniste tai malliosuma.", { left: 82, top: 545, width: 1040, height: 42 }, { fontSize: 24, bold: true });
}

// 3. How to read customer potential
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Jokaisella välilehdellä on oma rooli tuloksen tulkinnassa", "Päätaulukko kertoo kenelle myydään, tuoteryhmät kertovat mitä myydään ja validointi kertoo mitä kannattaa tarkistaa.", 3);
  const sheetRows = [
    ["customer_potential", "Asiakaskohtainen päätaulukko: pisteytys, prioriteetti, euromääräinen potentiaali, odotusarvo ja perustelusignaalit."],
    ["product groups", "Sheet product_group_recommendations: missä tuoteryhmissä asiakkaalla on white space -mahdollisuus."],
    ["validation_against_crm", "Mallin ja CRM-potentiaalin vertailu: erot euroina, prosentteina ja validointistatuksena."],
    ["run_log", "Ajon loki: rivimäärät, malliosumat, puuttuvat Y-tunnukset, metriikat ja käytetyt painotukset."],
    ["data_quality", "Datan laadun tarkistuslista: puuttuvat tunnisteet, puuttuvat malliosumat ja muut tarkistettavat rivit."],
  ];
  let y = 210;
  for (const [sheet, purpose] of sheetRows) {
    addPanel(slide, { left: 70, top: y, width: 1060, height: 68 }, sheet === "customer_potential" ? C.softAccent : C.panel);
    addText(slide, sheet, { left: 98, top: y + 17, width: 315, height: 34 }, { fontSize: 23, bold: true });
    addText(slide, purpose, { left: 440, top: y + 15, width: 650, height: 42 }, { fontSize: 19, color: C.muted });
    y += 78;
  }
}

// 4. How to read customer potential
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Päätaulukko kannattaa lukea vasemmalta oikealle myyntiprioriteettina", "Yksittäinen rivi ei ole lupaus myynnistä, vaan perusteltu arvio asiakkaan potentiaalista ja parhaasta seuraavasta myyntitoimesta.", 4);
  const rows = [
    ["Identity", "business_id, Name, company", "Varmista, että asiakas on oikea ja Y-tunnus täsmää."],
    ["Priority", "rank, priority, score", "Käytä A/B/C/D-jakoa työlistan järjestämiseen."],
    ["Potential", "final_value_eur, expected_potential_eur", "Erottele ehdollinen potentiaali ja todennäköisyyspainotettu odotusarvo."],
    ["Evidence", "positive_signals, recent_12m", "Katso miksi malli nosti asiakkaan ja miten viime vuoden myynti tuki arviota."],
  ];
  let y = 218;
  for (const [label, cols, meaning] of rows) {
    addPanel(slide, { left: 70, top: y, width: 1060, height: 70 }, label === "Potential" ? C.softAccent : C.panel);
    addText(slide, label, { left: 94, top: y + 18, width: 170, height: 34 }, { fontSize: 24, bold: true });
    addText(slide, cols, { left: 292, top: y + 19, width: 340, height: 32 }, { fontSize: 20, color: C.ink });
    addText(slide, meaning, { left: 670, top: y + 16, width: 420, height: 40 }, { fontSize: 19, color: C.muted });
    y += 86;
  }
}

// 5. Model construction
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Malli rakentuu yritysdatasta, myyntihistoriasta ja segmenttivertailusta", "Logiikka on sama prospektimallin runko, mutta nykyasiakkaat pidetään mukana ja heidän toteutunut myynti huomioidaan vahvemmin.", 5);
  addStep(slide, "1", "Featuret", "Liikevaihto, henkilöstö, toimiala, segmentti, kasvu ja tilitiedot muodostavat mallin syötteen.", 58, 230);
  addStep(slide, "2", "Vertailujoukko", "Asiakkaita verrataan samankaltaisiin ja korkean potentiaalin ostajiin segmenttitasolla.", 475, 230);
  addStep(slide, "3", "Scoring", "Malli laskee score-arvon 0-1 ja muuntaa sen euromääräiseksi potentiaaliksi.", 892, 230, C.softAccent);
  addText(slide, "Innoflame poistettiin lopullisesta ajosta sekä asiakas- että myyntihistorialähteistä, jotta sisäinen ostohistoria ei vääristä vertailua.", { left: 70, top: 555, width: 1040, height: 40 }, { fontSize: 22, bold: true });
}

// 6. Potential formula
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Uusin malli erottaa vuoden 2027 ennusteen ja myynnillisen potentiaalin", "Laskentaa ei muutettu: nykyinen seuraavan vuoden ennuste on nimetty vuoden 2027 ennusteeksi ja sen rinnalla naytetaan kasvupotentiaalicase.", 6);
  addPanel(slide, { left: 58, top: 220, width: 520, height: 300 }, C.panel);
  addText(slide, "base_forecast_2027_eur", { left: 88, top: 252, width: 450, height: 38 }, { fontSize: 30, bold: true });
  addText(slide, "Konservatiivinen run-rate ennuste perustuu asiakkaan ostohistoriaan, 2025 toteumaan ja 2026 YTD annualisointiin.", { left: 88, top: 316, width: 440, height: 110 }, { fontSize: 22, color: C.muted });
  addText(slide, "Kayta tata ennustamiseen nykyisella ostotasolla.", { left: 88, top: 454, width: 440, height: 44 }, { fontSize: 20, bold: true });
  addPanel(slide, { left: 686, top: 220, width: 520, height: 300 }, C.softGreen);
  addText(slide, "realistic_potential_2027_eur", { left: 716, top: 252, width: 450, height: 38 }, { fontSize: 30, bold: true });
  addText(slide, "Myynnillinen potentiaalicase lisaa run-rate tasoon kalibroiduista tuoteryhmista tunnistetun kasvumahdollisuuden.", { left: 716, top: 316, width: 440, height: 112 }, { fontSize: 22, color: C.muted });
  addText(slide, "Kayta tata myynnin kasvutyolistan priorisointiin.", { left: 716, top: 454, width: 440, height: 44 }, { fontSize: 20, bold: true, color: C.green });
  addText(slide, "VUODEN 2027 RUN-RATE", { left: 88, top: 540, width: 300, height: 24 }, { fontSize: 14, bold: true, color: C.muted });
  addText(slide, "20,24 MEUR", { left: 88, top: 570, width: 280, height: 58 }, { fontSize: 42, bold: true });
  addText(slide, "2025 toteuma 20,48 MEUR", { left: 88, top: 626, width: 280, height: 24 }, { fontSize: 17, color: C.muted });
  addText(slide, "REALISTINEN 2027 POTENTIAALI", { left: 716, top: 540, width: 330, height: 24 }, { fontSize: 14, bold: true, color: C.muted });
  addText(slide, "40,78 MEUR", { left: 716, top: 570, width: 330, height: 58 }, { fontSize: 42, bold: true });
  addText(slide, "+99,1 % vuoden 2025 toteumaan", { left: 716, top: 626, width: 360, height: 24 }, { fontSize: 17, color: C.muted });
}

// 7. What changed in the model
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Muutos edelliseen malliin: vuoden 2027 ennuste ja kasvupotentiaali erotettiin", "Laskenta pysyi ennallaan. Uusi lisays tekee nakyviin, etta seuraavan vuoden run-rate tulkitaan vuoden 2027 ennusteeksi.", 7);
  addMetric(slide, "2025 toteuma", "20,48 MEUR", "GoSystems-myynti ilman Innoflamea", 80, 238, 250);
  addMetric(slide, "2027 run-rate", `${data.salesPotential.baseForecastM.toFixed(2)} MEUR`, "nykyisen ostotason arvio", 350, 238, 260);
  addMetric(slide, "Kasvupotentiaali", `${data.salesPotential.growthPotentialM.toFixed(2)} MEUR`, "todennakoisyys- ja prioriteettioikaistu", 650, 238, 290);
  addMetric(slide, "Realistinen 2027 potentiaali", `${data.salesPotential.realisticPotentialM.toFixed(2)} MEUR`, "run-rate + kasvumahdollisuus", 970, 238, 260);
  addPanel(slide, { left: 78, top: 520, width: 1040, height: 78 }, C.softAccent);
  addText(slide, "Tulkinta: base_forecast_eur sopii ennustamiseen. realistic_potential_eur sopii myynnin kasvutyolistan priorisointiin. upside_potential_eur on korkeampi skenaario, ei perusennuste.", { left: 108, top: 542, width: 980, height: 38 }, { fontSize: 22, bold: true });
}

// 7. Product group recommendations
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Tuoteryhmäsuositus näyttää asiakkaan white space -mahdollisuuden", "Suositus ei ole SKU-lista. Se kertoo, missä tuoteryhmissä samankaltaiset asiakkaat ostavat enemmän kuin kyseinen asiakas.", 8);
  slide.charts.add("bar", {
    position: { left: 72, top: 220, width: 690, height: 380 },
    categories: data.productGroups.map((row) => row[0]),
    series: [{ name: "Expected potential M€", values: data.productGroups.map((row) => row[1]), fill: C.accent }],
    hasLegend: false,
    dataLabels: { showValue: true, position: "outEnd" },
    yAxis: { majorGridlines: { style: "solid", fill: C.rule, width: 1 } },
  });
  addMetric(slide, "Recommendation rows", "23 670", "tuoteryhmätason suositusta", 842, 250, 280);
  addMetric(slide, "Expected group potential", "23,0 M€", "todennäköisyyspainotettu", 842, 430, 310);
}

// 8. Validation view
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "CRM-validointi tarkistaa onko 2027-potentiaali realistinen", "CRM:n Status, Sales ja Probability aggregoidaan asiakastasolle. Jos CRM-osumaa ei loydy, mallin alkuperainen potentiaali sailyy ennallaan.", 9);
  slide.charts.add("bar", {
    position: { left: 76, top: 214, width: 650, height: 370 },
    categories: data.validation.map((row) => row[0]),
    series: [{ name: "Rows", values: data.validation.map((row) => row[1]), fill: C.ink }],
    hasLegend: false,
    dataLabels: { showValue: true, position: "outEnd" },
    yAxis: { majorGridlines: { style: "solid", fill: C.rule, width: 1 } },
  });
  addPanel(slide, { left: 800, top: 245, width: 360, height: 250 }, C.panel);
  addText(slide, "Miten CRM vaikuttaa", { left: 830, top: 276, width: 300, height: 36 }, { fontSize: 28, bold: true });
  addText(slide, "crm_expected_sales_eur = Sales * Probability. Jos CRM-odotusarvo on mallia korkeampi, validointiarvo nostetaan. Jos CRM-osumaa ei ole, alkuperainen realistic_potential_2027_eur sailyy.", { left: 830, top: 336, width: 300, height: 132 }, { fontSize: 19, color: C.muted });
  addText(slide, "CRM-OSUMAT", { left: 805, top: 535, width: 170, height: 24 }, { fontSize: 14, bold: true, color: C.muted });
  addText(slide, "4 724", { left: 805, top: 565, width: 170, height: 52 }, { fontSize: 40, bold: true });
  addText(slide, "SAILYI ENNALLAAN", { left: 995, top: 535, width: 190, height: 24 }, { fontSize: 14, bold: true, color: C.muted });
  addText(slide, "1 542", { left: 995, top: 565, width: 190, height: 52 }, { fontSize: 40, bold: true });
}

// 9. Operating rules
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Käytä taulukkoa myynnin priorisointiin, ei automaattisena lupauksena liikevaihdosta", "Malli antaa järjestyksen, perustelun ja seuraavan tuoteryhmäteeman. Myynti vahvistaa tulkinnan asiakastiedolla.", 10);
  const rules = [
    ["Start with A and B", "Korkein prioriteetti yhdistää potentiaalin, score-signaalin ja vertailuryhmän."],
    ["Use expected value for forecasting", "Odotusarvo on parempi ennustamiseen kuin ehdollinen potentiaali."],
    ["Use conditional value for upside", "Ehdollinen potentiaali kertoo mahdollisen vuosikoon, jos kasvu toteutuu."],
    ["Check data quality", "Puuttuva Y-tunnus tai missing_in_crm vaatii manuaalisen tarkistuksen ennen päätöstä."],
  ];
  let y = 220;
  for (const [title, body] of rules) {
    addPanel(slide, { left: 76, top: y, width: 1030, height: 72 }, title === "Use expected value for forecasting" ? C.softAccent : C.panel);
    addText(slide, title, { left: 108, top: y + 18, width: 330, height: 34 }, { fontSize: 24, bold: true });
    addText(slide, body, { left: 470, top: y + 18, width: 570, height: 36 }, { fontSize: 20, color: C.muted });
    y += 88;
  }
}

// 10. Backtest result
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Backtest osoittaa, etta uusin malli osuu lahelle 2025 toteumaa", "Vertailu vanhoihin malliversioihin on poistettu. Tama dia nayttaa vain toteuman ja uusimman ostohistoriaan ankkuroidun mallin.", 11);
  slide.charts.add("bar", {
    position: { left: 70, top: 220, width: 690, height: 350 },
    categories: ["Toteuma 2025", "Uusin malli"],
    series: [{ name: "M EUR", values: [data.backtest.actual2025M, data.backtest.historyExpectedM], fill: C.accent }],
    hasLegend: false,
    dataLabels: { showValue: true, position: "outEnd" },
    yAxis: { majorGridlines: { style: "solid", fill: C.rule, width: 1 } },
  });
  addMetric(slide, "Toteuma 2025", "20,48 MEUR", "GoSystems-myynti ilman Innoflamea", 842, 222, 310);
  addMetric(slide, "Uusi arvio", "20,24 MEUR", "ostohistoriafeature-malli", 842, 390, 310);
  addText(slide, "Johtopaatos: vuosipotentiaalin euroarvo kannattaa ankkuroida asiakkaan omaan ostohistoriaan ja kayttaa scorea priorisoinnin tukena.", { left: 82, top: 596, width: 1040, height: 42 }, { fontSize: 21, bold: true });
}

// 11. Probability calibration and history features
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Todennakoisyys pidetaan erillaan euroarvosta", "Probability_of_growth kertoo kasvun toteutumisen todennakoisyyden. Euroarvio muodostetaan ostohistorian ja mallisignaalien perusteella.", 12);
  addMetric(slide, "Growth AUC", "0,72", "kasvun toteutumisen erottelukyky", 82, 250, 280);
  addMetric(slide, "Correlation", "0,80", "vuosimyyntiarvio vs 2025 toteuma", 382, 250, 300);
  addMetric(slide, "MAE", "2 489 EUR", "asiakaskohtainen keskivirhe", 82, 430, 280);
  addMetric(slide, "Bias", "-0,25 MEUR", "kokonaisennusteen ero toteumaan", 382, 430, 300);
  addPanel(slide, { left: 752, top: 224, width: 400, height: 330 }, C.panel);
  addText(slide, "Tarkeimmat signaalit", { left: 782, top: 252, width: 330, height: 38 }, { fontSize: 28, bold: true });
  let y = 310;
  for (const [feature, value] of data.featureImportance.slice(0, 6)) {
    addText(slide, feature, { left: 782, top: y, width: 245, height: 26 }, { fontSize: 18, color: C.ink });
    addText(slide, `${value.toFixed(1)} %`, { left: 1040, top: y, width: 80, height: 26 }, { fontSize: 18, bold: true, alignment: "right" });
    y += 38;
  }
  addText(slide, "Kaytannossa myyntihistoria antaa mallille muistia: kuka osti, kuinka usein, mihin suuntaan ostaminen liikkui ja kuinka tuore suhde on.", { left: 82, top: 590, width: 1040, height: 48 }, { fontSize: 21, bold: true });
}

// 12. Product group backtest
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Tuoteryhmaennuste on nyt kalibroitu tuoteryhmakohtaisilla kertoimilla", "Backtestista lasketut kertoimet korjaavat isot kategoriat omalla toteuma/ennuste-suhteellaan ja pienet kategoriat varovaisemmin globaalilla kertoimella.", 13);
  slide.charts.add("bar", {
    position: { left: 70, top: 218, width: 720, height: 380 },
    categories: data.backtestProductGroups.map((row) => row[0]),
    series: [
      { name: "Actual 2025 M EUR", values: data.backtestProductGroups.map((row) => row[1]), fill: C.ink },
      { name: "Calibrated M EUR", values: data.backtestProductGroups.map((row) => row[2]), fill: C.accent },
    ],
    hasLegend: true,
    dataLabels: { showValue: false },
    yAxis: { majorGridlines: { style: "solid", fill: C.rule, width: 1 } },
  });
  addPanel(slide, { left: 842, top: 250, width: 330, height: 270 }, C.softAccent);
  addText(slide, "Kalibroinnin vaikutus", { left: 872, top: 282, width: 270, height: 34 }, { fontSize: 27, bold: true });
  addText(slide, `Raaka tuoteryhmamalli oli ${data.productGroupCalibration.rawM.toFixed(2)} MEUR ja toteuma ${data.productGroupCalibration.actualM.toFixed(2)} MEUR. Kalibroitu arvio on ${data.productGroupCalibration.calibratedM.toFixed(2)} MEUR.`, { left: 872, top: 342, width: 270, height: 128 }, { fontSize: 20, color: C.muted });
}

// 13. Error analysis and feedback loop
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Virheanalyysi tekee mallin parantamisesta myynnille konkreettista", "Suurimmat yli- ja aliarviot on viety palautepohjaan, jossa myynti voi korjata potentiaalia, merkitä poikkeussyyn ja lisätä puuttuvan tuoteryhmätiedon.", 14);
  slide.charts.add("bar", {
    position: { left: 70, top: 220, width: 620, height: 360 },
    categories: data.errorBuckets.map((row) => row[0]),
    series: [{ name: "Customers", values: data.errorBuckets.map((row) => row[1]), fill: C.accent }],
    hasLegend: false,
    dataLabels: { showValue: true, position: "outEnd" },
    yAxis: { majorGridlines: { style: "solid", fill: C.rule, width: 1 } },
  });
  addPanel(slide, { left: 760, top: 226, width: 390, height: 330 }, C.panel);
  addText(slide, "Seuraava palautesilmukka", { left: 790, top: 258, width: 330, height: 34 }, { fontSize: 27, bold: true });
  const loop = [
    "Myynti tarkistaa 500 suurinta virhettä",
    "Korjattu potentiaali ja poikkeussyy talteen",
    "Virhetyypit lisätään mallin opetusdataan",
    "Uusi ajo validoidaan seuraavaa toteumaa vasten",
  ];
  let y = 318;
  for (const item of loop) {
    addText(slide, item, { left: 790, top: y, width: 320, height: 34 }, { fontSize: 20, color: C.muted });
    y += 48;
  }
  addText(slide, "Tavoite ei ole saada jokaista asiakasta oikein kerralla, vaan lyhentää oppimissykliä myynnin palautteen ja toteuman avulla.", { left: 82, top: 594, width: 1040, height: 44 }, { fontSize: 21, bold: true });
}

// 14. Top probability customers
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Top 10 asiakkaat ostotodennakoisyyden mukaan", "Lista jarjestyy improved_probability_of_growth-arvon mukaan. Korkea todennakoisyys syntyy, kun ostohistoria, aktiivisuus, segmenttisopivuus ja alkuperaisen mallin score tukevat samaa kasvusignaalia.", 15);
  addCustomerTable(
    slide,
    data.topProbabilityCustomers.map((row, index) => [
      `${index + 1}. ${row[0]}`,
      row[1],
      `${row[2].toFixed(1)} %`,
      `${Math.round(row[3]).toLocaleString("fi-FI")} EUR`,
    ]),
    [
      { label: "Asiakas", width: 510 },
      { label: "Business ID", width: 170 },
      { label: "Todennakoisyys", width: 170 },
      { label: "Vuosiarvio", width: 170 },
    ],
    70,
    210,
    1040,
    38
  );
}

// 15. Top renewal potential customers
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Top 10 asiakkaat realistisen potentiaalin mukaan", "Realistinen potentiaali tarkoittaa run-rate ennustetta lisattuna kalibroidulla tuoteryhmakohtaisella kasvumahdollisuudella.", 16);
  addCustomerTable(
    slide,
    data.topRenewalPotentialCustomers.map((row, index) => [
      `${index + 1}. ${row[0]}`,
      row[1],
      `${Math.round(row[2]).toLocaleString("fi-FI")} EUR`,
      `${row[3].toFixed(1)} %`,
    ]),
    [
      { label: "Asiakas", width: 510 },
      { label: "Business ID", width: 170 },
      { label: "Realistinen potentiaali", width: 190 },
      { label: "Todennakoisyys", width: 150 },
    ],
    70,
    210,
    1040,
    38
  );
}

// 16. Workbook sheet guide part 1
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Excelin valilehdet kertovat eri osan mallin tuloksesta", "Ensimmainen osa valilehdista auttaa lukemaan paatuloksen, run-rate ennusteen ja myynnillisen potentiaalicasen.", 17);
  addSheetGuideTable(slide, data.sheetGuidePart1, 70, 206);
}

// 17. Workbook sheet guide part 2
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Tuoteryhma- ja kalibrointivalilehdet selittavat mista kasvu tulee", "Naita valilehtia kaytetaan, kun halutaan tarkistaa white space -laskenta, todennakoisyys tai tuoteryhmakohtaiset kertoimet.", 18);
  addSheetGuideTable(slide, data.sheetGuidePart2, 70, 206);
}

// 19. Workbook sheet guide part 3
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Virheanalyysi ja myynnin palaute sulkevat oppimissilmukan", "Naita valilehtia kaytetaan, kun malli halutaan tarkentaa seuraavassa ajossa myynnin palautteen ja toteuman avulla.", 19);
  addSheetGuideTable(slide, data.sheetGuidePart3, 70, 206);
}

await fs.mkdir(PREVIEW_DIR, { recursive: true });
for (const [index, slide] of ppt.slides.items.entries()) {
  const stem = `slide-${String(index + 1).padStart(2, "0")}`;
  await writeBlob(`${PREVIEW_DIR}/${stem}.png`, await ppt.export({ slide, format: "png", scale: 1 }));
  await fs.writeFile(`${PREVIEW_DIR}/${stem}.layout.json`, await (await slide.export({ format: "layout" })).text());
}
await writeBlob(MONTAGE, await ppt.export({ format: "webp", montage: true, scale: 1 }));
const file = await PresentationFile.exportPptx(ppt);
await file.save(OUT);
console.log(JSON.stringify({ pptx: OUT, montage: MONTAGE, slides: ppt.slides.items.length }, null, 2));
