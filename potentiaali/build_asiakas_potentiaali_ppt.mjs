import fs from "node:fs/promises";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const OUT = "C:/Users/TommiHavukainen/OneDrive - Unikie Oy/Customer/Innoflame/Innoflame_asiakas_potentiaali_mallipaivitys.pptx";
const PREVIEW_DIR = "C:/Users/TommiHavukainen/AppData/Local/Temp/codex-presentations/manual-asiakas-potentiaali/ppt-esitys/tmp/preview";
const MONTAGE = "C:/Users/TommiHavukainen/AppData/Local/Temp/codex-presentations/manual-asiakas-potentiaali/ppt-esitys/tmp/preview/montage.webp";

const C = {
  canvas: "#FFFFFF",
  ink: "#000000",
  muted: "#555555",
  panel: "#EDEDED",
  rule: "#B8BCC4",
  accent: "#FF6B35",
  softAccent: "#FFE4D8",
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

function addMetric(slide, label, value, note, x, y, w = 260) {
  addText(slide, label.toUpperCase(), { left: x, top: y, width: w, height: 28 }, { fontSize: 15, bold: true, color: C.muted });
  addText(slide, value, { left: x, top: y + 34, width: w, height: 70 }, { fontSize: 48, bold: true });
  addText(slide, note, { left: x, top: y + 106, width: w, height: 60 }, { fontSize: 18, color: C.muted });
}

function addFooter(slide, n) {
  addRule(slide, 42, 660, 1196);
  addText(slide, "Innoflame nykyasiakaspotentiaali", { left: 42, top: 674, width: 420, height: 24 }, { fontSize: 13, color: C.muted });
  addText(slide, String(n), { left: 1210, top: 674, width: 28, height: 24 }, { fontSize: 13, color: C.muted, alignment: "right" });
}

function addTitle(slide, title, subtitle, n) {
  addText(slide, title, { left: 42, top: 44, width: 1120, height: 92 }, { fontSize: 39, bold: true });
  if (subtitle) addText(slide, subtitle, { left: 42, top: 134, width: 1020, height: 58 }, { fontSize: 20, color: C.muted });
  addFooter(slide, n);
}

const ppt = Presentation.create({ slideSize: { width: 1280, height: 720 } });

// 1. Cover
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addText(slide, "Innoflame", { left: 42, top: 42, width: 240, height: 40 }, { fontSize: 22, bold: true });
  addText(slide, "Nykyasiakkaiden potentiaali", { left: 42, top: 190, width: 760, height: 150 }, { fontSize: 64, bold: true });
  addText(slide, "Päivitys, jossa malli huomioi vahvemmin viimeisen 12 kuukauden toteutunutta myyntiä.", { left: 42, top: 368, width: 720, height: 92 }, { fontSize: 26, color: C.muted });
  addPanel(slide, { left: 880, top: 120, width: 280, height: 380 }, C.panel);
  addText(slide, "117,7 M€", { left: 908, top: 192, width: 230, height: 72 }, { fontSize: 52, bold: true });
  addText(slide, "päivitetty mallipotentiaali", { left: 908, top: 274, width: 220, height: 60 }, { fontSize: 22, color: C.muted });
  addText(slide, "+6,7 M€", { left: 908, top: 390, width: 220, height: 58 }, { fontSize: 42, bold: true, color: C.accent });
  addText(slide, "muutos aiempaan ajoon", { left: 908, top: 450, width: 220, height: 44 }, { fontSize: 18, color: C.muted });
  addFooter(slide, 1);
}

// 2. Why it changed
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Mallin piti pysyä kiinni toteutuneessa asiakaskäyttäytymisessä", "Aiempi arvo perustui vahvasti prospektimallin segmentti- ja baseline-logiikkaan. Nykyasiakkailla toteutunut myynti on suora signaali ostokyvystä.", 2);
  addPanel(slide, { left: 42, top: 222, width: 350, height: 300 }, C.panel);
  addText(slide, "Ennen", { left: 72, top: 250, width: 270, height: 42 }, { fontSize: 30, bold: true });
  addText(slide, "Segmentin mediaani, score ja baseline määrittivät euromääräisen potentiaalin. Toteutunut viime vuoden myynti näkyi lähinnä koulutusjoukon targetissa.", { left: 72, top: 310, width: 285, height: 150 }, { fontSize: 21, color: C.muted });
  addPanel(slide, { left: 465, top: 222, width: 350, height: 300 }, C.softAccent);
  addText(slide, "Nyt", { left: 495, top: 250, width: 270, height: 42 }, { fontSize: 30, bold: true });
  addText(slide, "Viimeisen 12 kk myynti toimii nykyasiakkailla alarajana. Se nostaa alimitoitetut arviot, mutta ei laske korkeampia malliarvioita.", { left: 495, top: 310, width: 285, height: 150 }, { fontSize: 21, color: C.ink });
  addPanel(slide, { left: 888, top: 222, width: 350, height: 300 }, C.panel);
  addText(slide, "Miksi se auttaa", { left: 918, top: 250, width: 270, height: 42 }, { fontSize: 30, bold: true });
  addText(slide, "Myynti saa listan, jossa olemassa oleva asiakkuus ei näytä keinotekoisesti pieneltä suhteessa toteutuneeseen ostotasoon.", { left: 918, top: 310, width: 285, height: 150 }, { fontSize: 21, color: C.muted });
}

// 3. Impact metrics
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Päivitys nosti kokonaispotentiaalia hallitusti", "Muutos kohdistui vain asiakkaisiin, joilla toteutunut viimeisen 12 kk myynti paljasti alimitoitetun arvion.", 3);
  addMetric(slide, "Kokonaispotentiaali", "117,7 M€", "aiemmin 111,0 M€", 58, 230, 260);
  addMetric(slide, "Nousu", "+6,7 M€", "+6,0 % aiempaan ajoon", 365, 230, 260);
  addMetric(slide, "Oikaistut asiakkaat", "100", "343 asiakkaalla löytyi viimeisen 12 kk myynti", 672, 230, 300);
  addMetric(slide, "Alle toteutuneen myynnin", "0", "yksikään malliosuma ei jää alle 12 kk myynnin", 1018, 230, 220);
  slide.charts.add("bar", {
    position: { left: 80, top: 484, width: 560, height: 130 },
    categories: ["Aiempi", "Päivitetty"],
    series: [{ name: "Potentiaali M€", values: [111.0, 117.7], fill: C.accent }],
    hasLegend: false,
    dataLabels: { showValue: true, position: "outEnd" },
    yAxis: { majorGridlines: { style: "solid", fill: C.rule, width: 1 } },
  });
  addText(slide, "Oikaisu on tarkoituksella yksisuuntainen: se korjaa liian matalia arvioita, mutta ei heikennä mallin jo korkeaksi tunnistamia mahdollisuuksia.", { left: 720, top: 500, width: 430, height: 88 }, { fontSize: 22, color: C.muted });
}

// 4. Validation
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Validointi näyttää, missä malli ja CRM eroavat", "Vertailu säilyttää myös puuttuvat CRM- ja malliosumat, jotta aineiston kattavuus näkyy päätöksenteossa.", 4);
  slide.charts.add("bar", {
    position: { left: 70, top: 220, width: 640, height: 350 },
    categories: ["Malli korkeampi", "Puuttuu CRM:stä", "Puuttuu Y-tunnus", "CRM korkeampi", "Lähellä"],
    series: [{ name: "Rivit", values: [4579, 1532, 468, 130, 26], fill: C.ink }],
    hasLegend: false,
    dataLabels: { showValue: true, position: "outEnd" },
    yAxis: { majorGridlines: { style: "solid", fill: C.rule, width: 1 } },
  });
  addPanel(slide, { left: 780, top: 228, width: 386, height: 268 }, C.panel);
  addText(slide, "Tulkinta", { left: 815, top: 258, width: 300, height: 42 }, { fontSize: 30, bold: true });
  addText(slide, "Suurin ero on mallin CRM:ää korkeampi potentiaali. Tämä on odotettava seuraus, kun nykyasiakkaan toteutunut myynti otetaan alarajaksi.", { left: 815, top: 320, width: 300, height: 120 }, { fontSize: 22, color: C.muted });
}

// 5. Product group recommendations
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Tuoteryhmäsuositukset kohdistavat potentiaalin myynnin seuraaviin keskusteluihin", "Suositukset tehdään tuoteryhmätasolla, eivät SKU-tasolla.", 5);
  slide.charts.add("bar", {
    position: { left: 58, top: 216, width: 700, height: 380 },
    categories: ["Hupparit ja colleget", "Tarrat ja etiketit", "Lippalakit", "Pipot", "Vyöt", "T-paidat"],
    series: [{ name: "Suosituspotentiaali M€", values: [8.38, 7.77, 7.14, 5.34, 5.32, 4.52], fill: C.accent }],
    hasLegend: false,
    dataLabels: { showValue: true, position: "outEnd" },
    yAxis: { majorGridlines: { style: "solid", fill: C.rule, width: 1 } },
  });
  addMetric(slide, "Suositusrivejä", "23 675", "tuoteryhmäkohtaiset ehdotukset", 840, 248, 300);
  addMetric(slide, "Asiakkaita", "4 735", "sai vähintään malliosuman", 840, 430, 300);
}

// 6. Use in sales
{
  const slide = ppt.slides.add();
  slide.background.fill = C.canvas;
  addTitle(slide, "Päivitettyä tulosta kannattaa käyttää priorisointiin ja keskustelun avaamiseen", "Paras käyttö on yhdistää asiakaskohtainen potentiaali, validointistatus ja tuoteryhmäkohtainen white space.", 6);
  const steps = [
    ["1", "Aloita A- ja B-prioriteeteista", "Korkein potentiaali ja suurin nostotarve löytyvät ensimmäisenä näistä ryhmistä."],
    ["2", "Tarkista CRM-poikkeamat", "Model_higher-rivit kertovat missä CRM:n potentiaali voi olla alikirjattu."],
    ["3", "Vie keskustelu tuoteryhmään", "Käytä suositusta seuraavan myyntiteeman valintaan, ei yksittäisen tuotteen tyrkyttämiseen."],
  ];
  let x = 74;
  for (const [num, heading, body] of steps) {
    addPanel(slide, { left: x, top: 238, width: 330, height: 270 }, num === "2" ? C.softAccent : C.panel);
    addText(slide, num, { left: x + 26, top: 264, width: 60, height: 54 }, { fontSize: 44, bold: true, color: num === "2" ? C.accent : C.ink });
    addText(slide, heading, { left: x + 26, top: 338, width: 265, height: 64 }, { fontSize: 27, bold: true });
    addText(slide, body, { left: x + 26, top: 422, width: 265, height: 74 }, { fontSize: 20, color: C.muted });
    x += 400;
  }
  addText(slide, "Lopputulos on käytännön myyntilista, ei pelkkä datamalli.", { left: 74, top: 560, width: 850, height: 42 }, { fontSize: 28, bold: true });
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
