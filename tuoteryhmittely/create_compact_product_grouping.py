from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd


BASE = Path("product_master_enrichment/final_product_grouping")
INPUT = BASE / "products_product_group_tree_final.csv"
OUTPUT_CSV = BASE / "products_product_group_tree_compact_workwear_under_clothing.csv"
OUTPUT_XLSX = BASE / "products_product_group_tree_compact_workwear_under_clothing.xlsx"
SUMMARY_JSON = BASE / "product_group_tree_compact_workwear_under_clothing_summary.json"
MAPPING_CSV = BASE / "product_group_tree_compact_mapping_report.csv"


L1_ORDER = [
    "Vaatteet",
    "Promootio- ja käyttötavarat",
    "Koti ja keittiö",
    "Toimisto, painotuotteet ja pakkaukset",
    "Laukut ja matkatavarat",
    "Lahjat ja sesonkituotteet",
    "Työkalut ja turvallisuus",
    "Asusteet",
    "Elintarvikkeet",
    "Elektroniikka",
    "Vapaa-aika",
    "Hyvinvointi",
    "Muut / tarkistettavat",
]


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


def first_match(text: str, rules: list[tuple[tuple[str, ...], str]], default: str) -> str:
    for needles, value in rules:
        if has_any(text, *needles):
            return value
    return default


def compact_l1(row: pd.Series) -> str:
    l1_code = clean(row.get("product_group_l1_code"))
    l1 = norm(row.get("product_group_l1_name"))

    if l1_code == "22" or l1 == "tyovaatteet":
        return "Vaatteet"
    if l1 in {"vaatteet", "tekstiilit"}:
        return "Vaatteet"
    if l1 in {"toimisto ja paperi", "toimisto painotuotteet ja kulutustuotteet", "pakkaukset"}:
        return "Toimisto, painotuotteet ja pakkaukset"
    if l1 in {"lahjat ja palvelut", "lahjat koti ja premium tuotteet", "sesonkituotteet", "vastuulliset tuotteet"}:
        return "Lahjat ja sesonkituotteet"
    if l1 == "korut ja kellot":
        return "Asusteet"
    if l1 in {"muut tarkistettavat", "muut maarittelemattomat"}:
        return "Muut / tarkistettavat"
    if clean(row.get("product_group_l1_name")) in L1_ORDER:
        return clean(row.get("product_group_l1_name"))
    return "Muut / tarkistettavat"


def compact_l2_l3(row: pd.Series, new_l1: str) -> tuple[str, str]:
    old_l1_code = clean(row.get("product_group_l1_code"))
    old_l2 = clean(row.get("product_group_l2_name"))
    old_l3 = clean(row.get("product_group_l3_name"))
    old_l4 = clean(row.get("product_group_l4_name"))
    text = norm(" ".join([old_l2, old_l3, old_l4, clean(row.get("product_name")), clean(row.get("title_fi"))]))

    if old_l1_code == "22":
        l3 = first_match(
            text,
            [
                (("tyopaita", "tunika", "pikee", "kauluspaita", "t paita", "paita"), "Työpaidat ja tunikat"),
                (("tyotakki", "takki", "liivi", "softshell", "fleece"), "Työtakit ja liivit"),
                (("tyohousu", "housu", "shortsit"), "Työhousut"),
                (("paahine", "pipo", "lippalakki", "asuste"), "Työvaateasusteet"),
                (("tyokenka", "saapas", "kenka"), "Työkengät"),
                (("suojain", "suojalas", "kuulosuojain"), "Suojaimet"),
                (("haalari",), "Haalarit"),
                (("esiliina", "tyoasu"), "Esiliinat ja työasut"),
            ],
            "Muut työvaatteet",
        )
        return "Työvaatteet", l3

    if new_l1 == "Vaatteet":
        l2 = first_match(
            text,
            [
                (("takki", "liivi", "fleece", "softshell", "ulkovaat"), "Takit ja liivit"),
                (("housu", "shortsit", "hame"), "Housut ja alaosat"),
                (("huppari", "college", "neule", "paita", "t paita", "pikee", "kaulus"), "Paidat ja yläosat"),
                (("kylpytakki", "tekstiili"), "Muut vaatteet ja tekstiilit"),
            ],
            "Muut vaatteet",
        )
        return l2, l2

    if new_l1 == "Toimisto, painotuotteet ja pakkaukset":
        l2 = first_match(
            text,
            [
                (("kyna", "kuulak", "mustekyna"), "Kirjoitusvälineet"),
                (("tarra", "etiket", "painotuote", "kortti", "julkaisu", "lehtinen", "esite", "kangasmerkki", "pinssi", "nimikyltti"), "Painotuotteet ja merkit"),
                (("pakkaus", "laatikko", "lahjalaatikko", "kirjekuori"), "Pakkaukset"),
                (("muistikirja", "vihko", "paperi"), "Muistikirjat ja paperituotteet"),
            ],
            "Muut toimisto- ja kulutustuotteet",
        )
        l3 = first_match(
            text,
            [
                (("kyna", "kuulak", "mustekyna"), "Kynät"),
                (("tarra", "etiket"), "Tarrat ja etiketit"),
                (("kangasmerkki", "pinssi", "nimikyltti"), "Merkit ja tunnisteet"),
                (("kortti", "julkaisu", "lehtinen", "esite"), "Kortit ja julkaisut"),
                (("laatikko", "pakkaus", "kirjekuori"), "Pakkaukset"),
                (("muistikirja", "vihko"), "Muistikirjat"),
            ],
            l2,
        )
        return l2, l3

    if new_l1 == "Lahjat ja sesonkituotteet":
        l2 = first_match(
            text,
            [
                (("lahjakort", "lippu", "palvelu", "aineeton"), "Lahjakortit ja palvelut"),
                (("paketti", "setti", "tervetulo", "lahjapak"), "Tuotepaketit ja setit"),
                (("joulu", "sesonki"), "Sesonkituotteet"),
                (("liikelah", "premium"), "Liikelahjat"),
            ],
            "Muut lahjatuotteet",
        )
        return l2, l2

    if new_l1 == "Promootio- ja käyttötavarat":
        l2 = first_match(
            text,
            [
                (("muki", "pullo", "termos", "juoma"), "Juoma-astiat"),
                (("avaimenpera", "kaulanauha", "pipo", "lippalakki", "asuste"), "Asusteet"),
                (("ilmapallo", "tapahtuma", "messu"), "Tapahtumatuotteet"),
                (("kassi", "ostoskassi"), "Kassit"),
                (("koti", "keittio"), "Koti ja keittiö"),
            ],
            "Promootiotuotteet",
        )
        return l2, first_match(text, [(("muki",), "Mukit"), (("pullo",), "Pullot"), (("kassi",), "Kassit")], l2)

    if new_l1 == "Koti ja keittiö":
        l2 = first_match(
            text,
            [
                (("muki", "pullo", "termos", "lasi", "juoma"), "Juoma-astiat"),
                (("pyyhe", "viltti", "peitto", "tekstiili"), "Kodintekstiilit"),
                (("keittio", "astia", "veitsi", "kulho", "pannu", "tarjoilu"), "Keittiötuotteet"),
                (("sisustus", "kynttila", "kukka"), "Sisustus"),
            ],
            "Muut koti- ja keittiötuotteet",
        )
        return l2, l2

    if new_l1 == "Laukut ja matkatavarat":
        l2 = first_match(
            text,
            [
                (("reppu",), "Reput"),
                (("matkalauk", "matkatav"), "Matkatavarat"),
                (("ostoskassi", "kassi"), "Kassit"),
                (("kylmalauk",), "Kylmälaukut"),
            ],
            "Laukut",
        )
        return l2, l2

    if new_l1 == "Työkalut ja turvallisuus":
        l2 = first_match(
            text,
            [
                (("heijastin", "ensiapu", "turvallisuus"), "Turvallisuus"),
                (("suojain", "suojalas"), "Suojaimet"),
                (("kenka", "saapas"), "Työkengät"),
                (("tyokalu", "mittanauha", "porakone", "makita", "leatherman"), "Työkalut"),
            ],
            "Muut työkalut ja turvallisuustuotteet",
        )
        return l2, l2

    if new_l1 == "Asusteet":
        l2 = first_match(
            text,
            [
                (("pipo", "lippalakki", "paahine"), "Päähineet"),
                (("huivi", "solmio", "tuubihuivi"), "Huivit ja kaulatuotteet"),
                (("avaimenpera",), "Avaimenperät"),
                (("koru", "kello"), "Korut ja kellot"),
                (("kasine",), "Käsineet"),
                (("kaulanauha",), "Kaulanauhat"),
            ],
            "Muut asusteet",
        )
        return l2, l2

    # Default: keep one compact mid-level and make L3 match it unless the old L3 is already useful.
    if new_l1 in {"Elintarvikkeet", "Elektroniikka", "Vapaa-aika", "Hyvinvointi"}:
        l2 = clean(row.get("product_group_l2_name")) or f"Muut {new_l1.lower()}"
        l3 = clean(row.get("product_group_l3_name")) or l2
        return l2, l3 if len(l3) <= 35 else l2

    return "Muut / tarkistettavat", "Muut / tarkistettavat"


def add_codes(df: pd.DataFrame) -> pd.DataFrame:
    l1_code_map = {name: f"{i:02d}" for i, name in enumerate(L1_ORDER, start=1)}
    df["product_group_l1_code"] = df["product_group_l1_name"].map(l1_code_map)

    for level, parent_cols in [
        (2, ["product_group_l1_code", "product_group_l1_name"]),
        (3, ["product_group_l1_code", "product_group_l1_name", "product_group_l2_code", "product_group_l2_name"]),
    ]:
        name_col = f"product_group_l{level}_name"
        code_col = f"product_group_l{level}_code"
        rows = (
            df[parent_cols + [name_col]]
            .drop_duplicates()
            .sort_values(parent_cols + [name_col], kind="stable")
        )
        code_map = {}
        for parent_key, group in rows.groupby(parent_cols, sort=False, dropna=False):
            # L2 codes extend the L1 code, L3 codes extend the L2 code.
            parent_code = parent_key[-2] if isinstance(parent_key, tuple) else parent_key
            for idx, (_, row) in enumerate(group.iterrows(), start=1):
                code_map[tuple(row[parent_cols + [name_col]].astype(str))] = f"{parent_code}.{idx:02d}"
        df[code_col] = df[parent_cols + [name_col]].astype(str).apply(lambda r: code_map[tuple(r)], axis=1)

    # In this compact version L4 is intentionally the same practical product-group level as L3.
    df["product_group_l4_name"] = df["product_group_l3_name"]
    df["product_group_l4_code"] = df["product_group_l3_code"] + ".001"
    df["product_group_path_code"] = (
        df["product_group_l1_code"] + " > " + df["product_group_l2_code"] + " > " + df["product_group_l3_code"] + " > " + df["product_group_l4_code"]
    )
    df["product_group_path_name"] = (
        df["product_group_l1_name"] + " > " + df["product_group_l2_name"] + " > " + df["product_group_l3_name"] + " > " + df["product_group_l4_name"]
    )
    return df


def level_count(df: pd.DataFrame, level: int) -> int:
    return int(df[[f"product_group_l{level}_code", f"product_group_l{level}_name"]].drop_duplicates().shape[0])


def main() -> None:
    df = pd.read_csv(INPUT, dtype=str, low_memory=False)
    original = df.copy()

    for level in range(1, 5):
        for field in ["code", "name"]:
            col = f"product_group_l{level}_{field}"
            df[f"original_{col}"] = df[col]

    new_l1 = df.apply(compact_l1, axis=1)
    pairs = [compact_l2_l3(row, l1) for (_, row), l1 in zip(df.iterrows(), new_l1)]
    df["product_group_l1_name"] = new_l1
    df["product_group_l2_name"] = [p[0] for p in pairs]
    df["product_group_l3_name"] = [p[1] for p in pairs]

    # Merge tiny L3 leaves into a parent-level "Muut ..." group to keep the tree maintainable.
    l3_counts = df.groupby(["product_group_l1_name", "product_group_l2_name", "product_group_l3_name"], dropna=False).size()
    tiny_keys = {key for key, count in l3_counts.items() if count < 10}
    for idx, row in df.iterrows():
        key = (row["product_group_l1_name"], row["product_group_l2_name"], row["product_group_l3_name"])
        if key in tiny_keys:
            df.at[idx, "product_group_l3_name"] = f"Muut {str(row['product_group_l2_name']).lower()}"

    df = add_codes(df)
    df["product_group_source"] = df["product_group_source"].fillna("") + "|compact_workwear_under_clothing"

    before = {f"L{level}": level_count(original, level) for level in range(1, 5)}
    after = {f"L{level}": level_count(df, level) for level in range(1, 5)}
    summary = {
        "input": str(INPUT),
        "output_csv": str(OUTPUT_CSV),
        "output_xlsx": str(OUTPUT_XLSX),
        "total_products": int(len(df)),
        "group_counts_before": before,
        "group_counts_after": after,
        "workwear_l1_rows_after": int((df["product_group_l1_name"] == "Työvaatteet").sum()),
        "workwear_under_clothing_rows_after": int(((df["product_group_l1_name"] == "Vaatteet") & (df["product_group_l2_name"] == "Työvaatteet")).sum()),
    }

    mapping = (
        df.groupby(
            [
                "original_product_group_l1_name",
                "original_product_group_l2_name",
                "original_product_group_l3_name",
                "original_product_group_l4_name",
                "product_group_l1_name",
                "product_group_l2_name",
                "product_group_l3_name",
                "product_group_l4_name",
            ],
            dropna=False,
        )
        .size()
        .reset_index(name="product_count")
        .sort_values("product_count", ascending=False)
    )

    product_output = df.drop(columns=[c for c in df.columns if c.startswith("original_product_group_")])

    product_output.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    mapping.to_csv(MAPPING_CSV, index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        product_output.to_excel(writer, sheet_name="Products", index=False)
        pd.DataFrame(
            [{"level": level, "before": before[level], "after": after[level], "change": after[level] - before[level]} for level in before]
        ).to_excel(writer, sheet_name="Summary", index=False)
        mapping.head(5000).to_excel(writer, sheet_name="Mapping", index=False)
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
