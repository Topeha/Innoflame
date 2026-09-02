import fs from "node:fs/promises";
import path from "node:path";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const ROOT = process.cwd();
const DATA_PATH = path.join(ROOT, "outputs", "product_grouping_summary", "product_grouping_deck_data.json");
const FINAL = process.env.PRODUCT_GROUPING_DECK_OUT ?? path.join(ROOT, "outputs", "Innoflame_tuoteryhmittely_kooste.pptx");
const TMP = path.join(ROOT, "outputs", "product_grouping_summary", "pptx_qa");

const data = JSON.parse(await fs.readFile(DATA_PATH, "utf8"));
await fs.mkdir(TMP, { recursive: true });

const W = 1280;
const H = 720;
const C = {
  ink: "#101010",
  muted: "#555555",
  panel: "#EFEFEF",
  rule: "#B8BCC4",
  accent: "#FF6B35",
  dark: "#1F2937",
  pale: "#F7F7F7",
};

const presentation = Presentation.create({ slideSize: { width: W, height: H } });

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

function addText(slide, text, x, y, w, h, style = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: { left: x, top: y, width: w, height: h },
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    fontSize: style.fontSize ?? 20,
    color: style.color ?? C.ink,
    bold: style.bold ?? false,
    alignment: style.alignment ?? "left",
    fontFace: "Helvetica Neue",
  };
  return shape;
}

function addTitle(slide, title, kicker = "TUOTERYHMITTELY") {
  addText(slide, kicker, 52, 38, 320, 28, { fontSize: 16, bold: true, color: C.muted });
  addText(slide, title, 52, 72, 1000, 54, { fontSize: 38, bold: true, color: C.ink });
  slide.shapes.add({
    geometry: "rect",
    position: { left: 52, top: 138, width: 1176, height: 1 },
    fill: C.rule,
    line: { style: "solid", fill: C.rule, width: 0 },
  });
}

function addMetric(slide, label, value, x, y, w = 180) {
  slide.shapes.add({
    geometry: "rect",
    position: { left: x, top: y, width: w, height: 112 },
    fill: C.pale,
    line: { style: "solid", fill: C.rule, width: 1 },
  });
  addText(slide, value, x + 16, y + 18, w - 32, 42, { fontSize: 32, bold: true });
  addText(slide, label, x + 16, y + 66, w - 32, 36, { fontSize: 15, color: C.muted });
}

function addBulletList(slide, items, x, y, w, lineHeight = 36, fontSize = 20) {
  items.forEach((item, i) => {
    addText(slide, "•", x, y + i * lineHeight, 22, 26, { fontSize, bold: true, color: C.accent });
    addText(slide, item, x + 28, y + i * lineHeight, w - 28, lineHeight, { fontSize, color: C.ink });
  });
}

function fmt(n) {
  return new Intl.NumberFormat("fi-FI").format(n);
}

function percent(v) {
  return `${String(v).replace(".", ",")} %`;
}

function addSimpleTable(slide, rows, x, y, w, h, colWidths, fontSize = 15) {
  const rowH = h / rows.length;
  rows.forEach((row, r) => {
    slide.shapes.add({
      geometry: "rect",
      position: { left: x, top: y + r * rowH, width: w, height: rowH },
      fill: r === 0 ? C.panel : r % 2 === 0 ? "#FAFAFA" : "#FFFFFF",
      line: { style: "solid", fill: C.rule, width: 0.6 },
    });
    let left = x;
    row.forEach((cell, c) => {
      const cw = colWidths[c] ?? w / row.length;
      const align = c >= row.length - 2 ? "right" : "left";
      const cellText = String(cell);
      const cellFontSize = c === 0 && cellText.length > 8 ? Math.min(fontSize, 10) : fontSize;
      addText(slide, cellText, left + 8, y + r * rowH + 6, cw - 14, Math.max(18, rowH - 8), {
        fontSize: cellFontSize,
        bold: r === 0,
        color: C.ink,
        alignment: align,
      });
      left += cw;
    });
  });
}

function addBarChart(slide, title, items, x, y, w, h) {
  addText(slide, title, x, y - 34, w, 28, { fontSize: 20, bold: true });
  const max = Math.max(...items.map((i) => i.product_count));
  items.slice(0, 8).forEach((item, idx) => {
    const rowY = y + idx * 42;
    addText(slide, item.name, x, rowY, 230, 28, { fontSize: 15, color: C.ink });
    slide.shapes.add({
      geometry: "rect",
      position: { left: x + 240, top: rowY + 6, width: 230, height: 14 },
      fill: "#E5E7EB",
      line: { style: "solid", fill: "none", width: 0 },
    });
    slide.shapes.add({
      geometry: "rect",
      position: { left: x + 240, top: rowY + 6, width: Math.max(8, 230 * item.product_count / max), height: 14 },
      fill: C.ink,
      line: { style: "solid", fill: "none", width: 0 },
    });
    addText(slide, fmt(item.product_count), x + 485, rowY - 2, 90, 28, { fontSize: 15, bold: true, alignment: "right" });
  });
}

function slideCover() {
  const slide = presentation.slides.add();
  slide.background.fill = "#FFFFFF";
  addText(slide, "Innoflame", 52, 42, 260, 30, { fontSize: 18, bold: true, color: C.muted });
  addText(slide, "Tuoteryhmittelyn kooste", 52, 180, 880, 76, { fontSize: 58, bold: true });
  addText(slide, "Palautteen mukainen 3-tasoinen tuoteryhmäpuu ilman inventory warehouse -ohjausta", 56, 274, 980, 70, { fontSize: 24, color: C.muted });
  addMetric(slide, "tuotetta aineistossa", fmt(data.issues.total_products), 56, 430, 210);
  addMetric(slide, "päätasoa", fmt(data.summaries.l1.group_count), 288, 430, 170);
  addMetric(slide, "L3-ryhmää", fmt(data.summaries.l3.group_count), 480, 430, 170);
  addMetric(slide, "aktiivista tasoa", "3", 672, 430, 210);
  addMetric(slide, "DIF-koodia", fmt(data.issues.dif_rows), 904, 430, 170);
  addText(slide, "Lähde: product_master_enrichment/final_product_grouping/Innoflame_tuoteryhmittely.csv", 56, 650, 1120, 24, { fontSize: 14, color: C.muted });
}

function slideExecutive() {
  const slide = presentation.slides.add();
  addTitle(slide, "Uusi ryhmäpuu on kolmitasoinen ja selkeämpi");
  const levels = [
    ["L1 päätasot", data.summaries.l1.group_count],
    ["L2 alatasot", data.summaries.l2.group_count],
    ["L3 tuoteryhmät", data.summaries.l3.group_count],
    ["Aktiivisia tasoja", data.issues.active_group_levels ?? 3],
  ];
  levels.forEach((m, i) => addMetric(slide, m[0], fmt(m[1]), 72 + i * 250, 178, 218));
  addBulletList(
    slide,
    [
      `Kaikilla ${fmt(data.issues.total_products)} tuotteella on L1-L3-tuoteryhmä täytetty.`,
      "Luokittelu ei käytä inventory_warehouse_category-kenttää ohjaavana tietona.",
      `Ryhmämäärä on nyt ${fmt(data.summaries.l1.group_count)} päätasoa ja ${fmt(data.summaries.l3.group_count)} aktiivista L3-tuoteryhmää.`,
      "L4-taso on jätetty tyhjäksi, jotta se ei toista L3-otsikoita.",
      "Asusteet on siirretty Vaatteet-päätason alle, ja promootio-/decal-/lahjakorttirakenne on erotettu.",
      `Suurimmat jatkotarkistukset kohdistuvat Muut-ryhmiin ja manuaalisiin tarkistuksiin.`,
    ],
    82,
    350,
    1080,
    48,
    21,
  );
}

function slideDataEnrichment() {
  const slide = presentation.slides.add();
  addTitle(slide, "Luokittelu perustuu tuotteen sisältöön");
  const cards = [
    ["Tuotteita", fmt(data.issues.total_products), "kaikilla L1-L3 täytetty"],
    ["L3-ryhmiä", fmt(data.summaries.l3.group_count), "aktiivinen alin taso"],
    ["Alle minimin", fmt(data.summaries.l3.groups_under_5_products ?? 0), "L3-ryhmää"],
    ["Muut L3", fmt(data.issues.l3_other_products), `${percent(data.issues.l3_other_products_pct)} tuotteista`],
  ];
  cards.forEach((card, i) => {
    const x = 72 + i * 280;
    const y = 176;
    slide.shapes.add({
      geometry: "rect",
      position: { left: x, top: y, width: 238, height: 132 },
      fill: C.pale,
      line: { style: "solid", fill: C.rule, width: 1 },
    });
    addText(slide, card[1], x + 18, y + 20, 190, 42, { fontSize: 32, bold: true, color: i === 2 ? C.accent : C.ink });
    addText(slide, card[0], x + 18, y + 66, 202, 30, { fontSize: 16, bold: true });
    addText(slide, card[2], x + 18, y + 98, 202, 22, { fontSize: 14, color: C.muted });
  });

  const rows = [
    ["Luokittelun rajaus", "Tulos", "Huomio"],
    ["Inventory warehouse", "Ei käytössä", "Kenttää ei käytetty ohjaavana tietona"],
    ["Aktiiviset tasot", "3", "L4 on jätetty tyhjäksi"],
    ["Alle 5 tuotteen L3", fmt(data.summaries.l3.groups_under_5_products ?? 0), "Minimikoko toteutuu"],
    ["Muut-ryhmät", fmt(data.issues.l3_other_products), `${percent(data.issues.l3_other_products_pct)} tuotteista`],
    ["Brand mapping", fmt(data.issues.brand_rows), "brand_name ja brand_website mukana tukitietona"],
  ];
  addSimpleTable(slide, rows, 92, 350, 1080, 260, [350, 150, 520], 15);
  addText(slide, "Tulkinta: luokittelu on rakennettu niin, että varastokategoria ei ohjaa uutta tuoteryhmäpuuta. Jatkossa tarkistus kannattaa keskittää erityisesti Muut-ryhmiin.", 92, 626, 1040, 36, { fontSize: 18, color: C.muted });
}

function slideLevelOverview() {
  const slide = presentation.slides.add();
  addTitle(slide, "Ryhmämäärä pieneni selvästi aiemmasta versiosta");
  const items = [
    { name: "L1", product_count: data.summaries.l1.group_count },
    { name: "L2", product_count: data.summaries.l2.group_count },
    { name: "L3", product_count: data.summaries.l3.group_count },
  ];
  addBarChart(slide, "Ryhmien lukumäärä per taso", items, 92, 200, 550, 360);
  const rows = [
    ["Taso", "Ryhmiä", "Suurin ryhmä", "Tuotteita"],
    ["L1", fmt(data.summaries.l1.group_count), data.summaries.l1.largest_group, fmt(data.summaries.l1.largest_group_products)],
    ["L2", fmt(data.summaries.l2.group_count), data.summaries.l2.largest_group, fmt(data.summaries.l2.largest_group_products)],
    ["L3", fmt(data.summaries.l3.group_count), data.summaries.l3.largest_group, fmt(data.summaries.l3.largest_group_products)],
  ];
  addSimpleTable(slide, rows, 690, 210, 500, 230, [70, 90, 230, 110], 15);
  addText(slide, "Tulkinta", 690, 476, 300, 28, { fontSize: 22, bold: true });
  addText(slide, "Työvaatteet eivät ole enää oma päätaso, vaan ne ovat Vaatteet-kategorian alla. Tämä vähentää päällekkäisiä vaatehierarkioita ja tekee pääkategoriatasosta selkeämmän.", 690, 512, 500, 96, { fontSize: 18, color: C.muted });
}

function slideTopLevel(level, title, tableCount = 10) {
  const slide = presentation.slides.add();
  addTitle(slide, title);
  const top = data.top_groups[`l${level}`].slice(0, tableCount);
  addBarChart(slide, `Suurimmat L${level}-ryhmät`, top.slice(0, 8), 76, 198, 520, 376);
  const rows = [["Koodi", "Ryhmä", "Tuotteita", "%"]];
  top.forEach((g) => rows.push([g.code, g.name, fmt(g.product_count), percent(g.pct)]));
  addSimpleTable(slide, rows, 650, 178, 560, 430, [90, 300, 95, 75], 13);
  const s = data.summaries[`l${level}`];
  addText(slide, `${fmt(s.group_count)} ryhmää tasolla L${level}. Suurin ryhmä kattaa ${percent(s.largest_group_pct)} tuotteista.`, 78, 610, 1080, 38, { fontSize: 19, color: C.muted });
}

function slideSources() {
  const slide = presentation.slides.add();
  addTitle(slide, "Mistä luokittelu syntyi");
  const rows = [["Luokittelun lähde", "Tuotteita", "%"]];
  data.top_sources.slice(0, 9).forEach((s) => rows.push([s.source, fmt(s.product_count), percent(s.pct)]));
  addSimpleTable(slide, rows, 72, 178, 715, 420, [460, 130, 90], 12);
  addText(slide, "Luotettavuusnäkökulma", 835, 178, 330, 34, { fontSize: 24, bold: true });
  addBulletList(
    slide,
    [
      `Tekstisääntöihin perustuvia rivejä: ${fmt(data.issues.title_rule_rows)} (${percent(data.issues.title_rule_pct)}).`,
      "Inventory warehouse -kategoriaa ei käytetty ohjaavana luokittelutietona.",
      `Aiemman tuotepuun fallback-rivejä: ${fmt(data.issues.fallback_classified_rows)} (${percent(data.issues.fallback_classified_pct)}).`,
      "Jatkossa kannattaa tallentaa luokittelun lähde ja luottamustaso pysyvästi tuotemasteriin.",
    ],
    835,
    235,
    350,
    68,
    18,
  );
}

function slideIssues() {
  const slide = presentation.slides.add();
  addTitle(slide, "Luokittelun keskeiset tarkistuskohdat");
  const issueCards = [
    ["Muut-ryhmät L3", `${percent(data.issues.l3_other_products_pct)}`, `${fmt(data.issues.l3_other_products)} tuotetta`],
    ["Fallback-luokitus", `${percent(data.issues.fallback_classified_pct)}`, `${fmt(data.issues.fallback_classified_rows)} tuotetta`],
    ["L3 alle 5", fmt(data.summaries.l3.groups_under_5_products ?? 0), "ryhmää"],
    ["L3 alle 10", fmt(data.summaries.l3.groups_under_10_products ?? 0), "ryhmää"],
  ];
  issueCards.forEach((card, i) => {
    const x = 72 + (i % 2) * 570;
    const y = 178 + Math.floor(i / 2) * 170;
    slide.shapes.add({ geometry: "rect", position: { left: x, top: y, width: 510, height: 128 }, fill: C.pale, line: { style: "solid", fill: C.rule, width: 1 } });
    addText(slide, card[0], x + 22, y + 18, 360, 30, { fontSize: 22, bold: true });
    addText(slide, card[1], x + 22, y + 50, 190, 42, { fontSize: 34, bold: true, color: C.accent });
    addText(slide, card[2], x + 210, y + 62, 260, 28, { fontSize: 18, color: C.muted });
  });
  const rows = [
    ["Tarkistus", "Tulos", "Huomio"],
    ["Inventory warehouse", "0 ohjausta", "Ei käytössä luokittelun päätöksenteossa"],
    ["L3-minimi", "0 alle 5 ryhmää", "Minimikoko toteutuu"],
    ["Muut L3 tuotteet", fmt(data.issues.l3_other_products), `${percent(data.issues.l3_other_products_pct)} tuotteista`],
    ["Fallback-luokitus", fmt(data.issues.fallback_classified_rows), `${percent(data.issues.fallback_classified_pct)} tuotteista`],
  ];
  addSimpleTable(slide, rows, 72, 510, 1068, 154, [460, 190, 360], 12);
}

function slideOtherGroups() {
  const slide = presentation.slides.add();
  addTitle(slide, "Muut- ja tarkistettavat ryhmät");
  const rows = [["L1", "L2", "L3", "Tuotteita"]];
  data.biggest_other_l3_groups.slice(0, 9).forEach((g) => rows.push([
    g.product_group_l1_name,
    g.product_group_l2_name,
    g.product_group_l3_name,
    fmt(g.product_count),
  ]));
  addSimpleTable(slide, rows, 72, 170, 1080, 430, [230, 230, 460, 120], 12);
  addText(slide, `L3-tasolla “Muut”-tyyppisissä ryhmissä on ${fmt(data.issues.l3_other_products)} tuotetta (${percent(data.issues.l3_other_products_pct)}). Näiden purkaminen parantaa raportoinnin käyttökelpoisuutta ja tuotekohtaisten suositusten tarkkuutta.`, 72, 620, 1080, 46, { fontSize: 18, color: C.muted });
}

function slideRecommendations() {
  const slide = presentation.slides.add();
  addTitle(slide, "Suositellut jatkotoimet");
  addBulletList(
    slide,
    [
      "Tallenna tuotemasteriin aina tuoteryhmän L1-L3-koodi, nimi, lähde ja luottamustaso.",
      "Pidä L3 käytännön alimpana tuoteryhmätasona ja käytä L4:ää vain erillisellä tarpeella.",
      "Käsittele ensin suuret “Muut”-ryhmät ja tarkistettavaksi jääneet tuotteet.",
      "Automatisoi uusien tuotteiden luokittelu: tuotteen nimi ja kuvaus ensin, ei inventory warehouse -kategoriaa ohjaavana tietona.",
      "Seuraa kuukausittain: uudet tuotteet ilman ryhmää, fallback-osuus, alle minimikoon L3-ryhmät ja Muut-ryhmien osuus.",
    ],
    92,
    190,
    1050,
    72,
    24,
  );
  addText(slide, "Täydet ryhmäkohtaiset lukumäärät löytyvät output-kansiosta: product_group_level_1_summary.csv ... product_group_level_3_summary.csv", 92, 630, 1050, 30, { fontSize: 16, color: C.muted });
}

slideCover();
slideExecutive();
slideDataEnrichment();
slideLevelOverview();
slideTopLevel(1, "L1: Vaatteet on nyt suurin päätaso", 12);
slideTopLevel(2, "L2: suurimmat alaryhmät", 12);
slideTopLevel(3, "L3: suurimmat ryhmät", 12);
slideSources();
slideIssues();
slideOtherGroups();
slideRecommendations();

for (const [index, slide] of presentation.slides.items.entries()) {
  const stem = `slide-${String(index + 1).padStart(2, "0")}`;
  await writeBlob(path.join(TMP, `${stem}.png`), await presentation.export({ slide, format: "png", scale: 1 }));
  const layout = await slide.export({ format: "layout" });
  await fs.writeFile(path.join(TMP, `${stem}.layout.json`), await layout.text(), "utf8");
}

await writeBlob(path.join(TMP, "deck-montage.webp"), await presentation.export({ format: "webp", montage: true, scale: 1 }));
const inspect = await presentation.inspect({ kind: "slide,textbox,shape,chart,table,layout", maxChars: 20000 });
await fs.writeFile(path.join(TMP, "inspect.ndjson"), inspect.ndjson, "utf8");

const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(FINAL);
console.log(FINAL);
