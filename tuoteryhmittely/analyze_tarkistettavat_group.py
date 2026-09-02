from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import pandas as pd


BASE = Path("product_master_enrichment/final_product_grouping")
INPUT = BASE / "products_product_group_tree_feedback_3level.csv"
OUT_DIR = Path("outputs/product_grouping_summary")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_XLSX = OUT_DIR / "tarkistettavat_ryhma_analyysi.xlsx"
OUTPUT_CSV = OUT_DIR / "tarkistettavat_ryhma_tuotteet.csv"
SUGGESTIONS_CSV = OUT_DIR / "tarkistettavat_ryhma_luokitteluehdotukset.csv"
SUMMARY_JSON = OUT_DIR / "tarkistettavat_ryhma_analyysi.json"

TEXT_COLUMNS = ["product_name", "title_fi", "description_fi", "searchdata", "sku", "code", "brand_name", "inventory_supplier"]

STOP_WORDS = {
    "and",
    "att",
    "black",
    "blue",
    "code",
    "den",
    "det",
    "for",
    "from",
    "har",
    "if",
    "ja",
    "joka",
    "jossa",
    "koko",
    "kpl",
    "logo",
    "logolla",
    "med",
    "mm",
    "och",
    "pcs",
    "product",
    "rif",
    "the",
    "this",
    "to",
    "tuote",
    "tuotteen",
    "tuotteet",
    "white",
    "with",
}


def clean(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def norm(value: object) -> str:
    text = clean(value).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def has_any(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


def has_word(text: str, *words: str) -> bool:
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


def text_for(row: pd.Series) -> str:
    return norm(" ".join(clean(row.get(col, "")) for col in TEXT_COLUMNS))


def tarkistettava_mask(df: pd.DataFrame) -> pd.Series:
    cols = ["product_group_l1_name", "product_group_l2_name", "product_group_l3_name", "product_group_path_name"]
    return df[cols].apply(lambda s: s.str.contains("Tarkistettavat|Muut / tarkistettavat", case=False, na=False)).any(axis=1)


def suggestion_for(row: pd.Series) -> tuple[str, str, str, str, str]:
    text = text_for(row)

    if has_any(text, "kuuloke", "korvakuuloke", "tws", "earbud", "headphone"):
        return ("Elektroniikka", "Audio", "Kuulokkeet", "high", "Kuulokkeen avainsana")
    if has_any(text, "smart tv", "qled", "google smart tv", "viihdeboksi", "router", "wifi", "kaiutin", "speaker"):
        return ("Elektroniikka", "Elektroniikka", "Viihde-elektroniikka", "high", "Elektroniikan avainsana")
    if has_any(text, "imuri", "varsi imuri", "varsiimuri", "airfryer", "vedenkeitin", "leivanpaahdin"):
        return ("Koti ja keittiö", "Kodinkoneet", "Pienkodinkoneet", "high", "Kodinkoneen avainsana")
    if has_any(text, "deskbike", "jumppakeppi", "treen", "fitness", "jooga", "yoga"):
        return ("Vapaa-aika", "Urheilu", "Liikunta- ja kuntoilutuotteet", "medium", "Liikuntatuotteen avainsana")
    if has_any(text, "pehmolelu", "leluauto", "toy", "wader", "mikado", "katuliitu", "peli", "game"):
        return ("Vapaa-aika", "Pelit ja lelut", "Lelut ja pelit", "high", "Lelu-/pelituotteen avainsana")
    if has_any(text, "sateenvarjo", "umbrella"):
        return ("Vapaa-aika", "Ulkoilu", "Sateenvarjot", "high", "Sateenvarjon avainsana")
    if has_any(text, "teelusikka", "lusikka", "haarukka", "aterin", "ruokailuvaline", "lounasrasia"):
        return ("Koti ja keittiö", "Keittiötuotteet", "Keittiövälineet", "high", "Keittiövälineen avainsana")
    if has_any(text, "talvipusero", "pusero", "fleecetakki", "takki", "shirt", "paita", "hoodie", "huppari"):
        return ("Vaatteet", "Paidat ja yläosat", "Paidat ja yläosat", "medium", "Vaatteen avainsana")
    if has_any(text, "muki", "kuppi", "cup"):
        return ("Koti ja keittiö", "Juoma-astiat", "Mukit", "high", "Juoma-astian avainsana")
    if has_any(text, "pullo", "bottle", "termos"):
        return ("Koti ja keittiö", "Juoma-astiat", "Juomapullot ja termospullot", "high", "Juoma-astian avainsana")
    if has_any(text, "lounasliina", "laudeliina", "pyyhe", "tiskiratti", "harso"):
        return ("Koti ja keittiö", "Kodintekstiilit", "Pyyhkeet ja laudeliinat", "medium", "Kodintekstiilin avainsana")
    if has_any(text, "aurinkorasva", "aurinkovoide", "sunscreen"):
        return ("Hyvinvointi", "Kosmetiikka", "Aurinkotuotteet", "high", "Kosmetiikka-avainsana")
    if has_any(text, "pakkaus", "laatikko", "kirjekuori", "envelope") or has_word(text, "box"):
        return ("Toimisto, painotuotteet ja pakkaukset", "Pakkaukset", "Pakkaukset", "medium", "Pakkaustuotteen avainsana")
    if has_any(text, "juliste", "poster", "esite", "brochure", "folder"):
        return ("Toimisto, painotuotteet ja pakkaukset", "Painotuotteet ja merkit", "Esitteet, julkaisut ja julisteet", "medium", "Painotuotteen avainsana")
    if has_any(text, "fanilippu", "seinalippu", "seinälippu"):
        return ("Promootio- ja tapahtumatuotteet", "Tapahtumatuotteet", "Liput, banderollit ja messutuotteet", "high", "Tapahtumalipun avainsana")
    if has_any(text, "lahjakortti", "gift card", "paasylippu", "pääsylippu", "ticket"):
        return ("Lahjakortit ja hyväntekeväisyys", "Lahjakortit", "Lahjakortit ja pääsyliput", "high", "Lahjakortti-/lippuavainsana")
    if has_any(text, "makeinen", "suklaa", "karkki", "candy", "chocolate", "purukumi", "toffee", "vesi", "juoma"):
        return ("Elintarvikkeet", "Makeiset ja juomat", "Makeiset ja juomat", "medium", "Elintarvikeavainsana")
    if has_any(text, "tervetuloa set", "tervetulosetti", "tervetuloa paketti"):
        return ("Koti ja keittiö", "Lahjasetit", "Lahjasetit", "medium", "Tervetulopaketin avainsana")
    if has_any(text, "kaulanauha", "avaimenpera", "heijastin", "pinssi", "rintanappi", "lanyard", "keyring"):
        return ("Promootio- ja tapahtumatuotteet", "Jakotuotteet", "Muut jakotuotteet", "medium", "Jakotuoteavainsana")

    return ("", "", "", "manual", "Ei riittävää tekstiosumaa")


def top_words(series: pd.Series, n: int = 120) -> pd.DataFrame:
    counter: Counter[str] = Counter()
    for text in series.fillna(""):
        normalized = norm(text)
        for word in re.findall(r"[a-z0-9]{3,}", normalized):
            if word in STOP_WORDS or word.isdigit():
                continue
            counter[word] += 1
    return pd.DataFrame(counter.most_common(n), columns=["word", "count"])


def main() -> None:
    df = pd.read_csv(INPUT, dtype=str, keep_default_na=False, low_memory=False)
    mask = tarkistettava_mask(df)
    tark = df.loc[mask].copy()

    suggestions = tark.apply(suggestion_for, axis=1, result_type="expand")
    suggestions.columns = ["suggested_l1", "suggested_l2", "suggested_l3", "confidence", "reason"]
    tark = pd.concat([tark.reset_index(drop=False).rename(columns={"index": "row_index"}), suggestions.reset_index(drop=True)], axis=1)
    tark["suggested_path"] = tark[["suggested_l1", "suggested_l2", "suggested_l3"]].agg(lambda row: " > ".join([v for v in row if clean(v)]), axis=1)
    tark["text_length"] = tark[["product_name", "title_fi", "description_fi", "searchdata"]].fillna("").agg(" ".join, axis=1).str.len()

    by_group = (
        tark.groupby(["product_group_l1_name", "product_group_l2_name", "product_group_l3_name"], dropna=False)
        .size()
        .reset_index(name="product_count")
        .sort_values("product_count", ascending=False)
    )
    by_source = (
        tark["product_group_source"].str.split("|").explode().value_counts().reset_index()
    )
    by_source.columns = ["source_marker", "product_count"]
    by_supplier = (
        tark.groupby("inventory_supplier", dropna=False).size().reset_index(name="product_count").sort_values("product_count", ascending=False)
    )
    by_brand = (
        tark.groupby("brand_name", dropna=False).size().reset_index(name="product_count").sort_values("product_count", ascending=False)
    )
    by_suggestion = (
        tark.groupby(["confidence", "suggested_l1", "suggested_l2", "suggested_l3", "reason"], dropna=False)
        .size()
        .reset_index(name="product_count")
        .sort_values(["confidence", "product_count"], ascending=[True, False])
    )
    text_blob = tark[TEXT_COLUMNS].fillna("").agg(" ".join, axis=1)
    words = top_words(text_blob)

    suggestion_rows = tark[
        [
            "code",
            "product_name",
            "title_fi",
            "description_fi",
            "product_group_path_name",
            "product_group_source",
            "suggested_path",
            "confidence",
            "reason",
        ]
    ].copy()
    suggestion_rows.to_csv(SUGGESTIONS_CSV, index=False, encoding="utf-8-sig")
    tark.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    summary = {
        "input": str(INPUT.resolve()),
        "rows_total": int(len(df)),
        "tarkistettavat_rows": int(len(tark)),
        "tarkistettavat_pct": round(len(tark) / len(df) * 100, 1),
        "groups": by_group.to_dict(orient="records"),
        "suggestion_counts": by_suggestion.to_dict(orient="records"),
        "high_or_medium_suggestion_rows": int(tark["confidence"].isin(["high", "medium"]).sum()),
        "manual_review_rows": int((tark["confidence"] == "manual").sum()),
        "top_words": words.head(40).to_dict(orient="records"),
        "output_xlsx": str(OUTPUT_XLSX.resolve()),
        "products_csv": str(OUTPUT_CSV.resolve()),
        "suggestions_csv": str(SUGGESTIONS_CSV.resolve()),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {"metric": "Tuotteita aineistossa", "value": len(df)},
                {"metric": "Tarkistettavia tuotteita", "value": len(tark)},
                {"metric": "Osuus tuotteista", "value": f"{round(len(tark) / len(df) * 100, 1)} %"},
                {"metric": "High/medium ehdotuksia", "value": int(tark["confidence"].isin(["high", "medium"]).sum())},
                {"metric": "Manuaalisia tarkistuksia", "value": int((tark["confidence"] == "manual").sum())},
            ]
        ).to_excel(writer, sheet_name="Yhteenveto", index=False)
        by_group.to_excel(writer, sheet_name="Ryhmittain", index=False)
        by_suggestion.to_excel(writer, sheet_name="Ehdotukset", index=False)
        words.to_excel(writer, sheet_name="Yleisimmat_sanat", index=False)
        by_source.head(100).to_excel(writer, sheet_name="Lahdemerkit", index=False)
        by_supplier.head(100).to_excel(writer, sheet_name="Toimittajat", index=False)
        by_brand.head(100).to_excel(writer, sheet_name="Brandit", index=False)
        suggestion_rows.to_excel(writer, sheet_name="Tuotteet", index=False)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
