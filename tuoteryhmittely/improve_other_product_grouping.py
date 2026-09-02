from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd


BASE = Path("product_master_enrichment/final_product_grouping")
INPUT = BASE / "products_product_group_tree_no_inventory_warehouse_category_l4_min5.csv"
OUTPUT_CSV = BASE / "products_product_group_tree_no_inventory_warehouse_category_l4_min5_improved.csv"
OUTPUT_XLSX = BASE / "products_product_group_tree_no_inventory_warehouse_category_l4_min5_improved.xlsx"
REPORT_CSV = BASE / "product_group_other_improvement_report.csv"
LEVEL_SUMMARY_CSV = BASE / "product_group_other_improvement_level_summary.csv"
SUMMARY_JSON = BASE / "product_group_other_improvement_summary.json"

MIN_L4_SIZE = 5

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

TEXT_COLUMNS = [
    "product_name",
    "title_fi",
    "description_fi",
    "searchdata",
    "sku",
    "code",
    "brand_name",
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


def has_word(text: str, *words: str) -> bool:
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


def text_for(row: pd.Series) -> str:
    return norm(" ".join(clean(row.get(col, "")) for col in TEXT_COLUMNS))


def is_other_like(row: pd.Series) -> bool:
    values = [clean(row.get(f"product_group_l{level}_name", "")) for level in range(1, 5)]
    keys = [norm(value) for value in values]
    return any(
        key.startswith("muut ")
        or key in {"muut", "muu", "muut tarkistettavat", "tarkistettava", "tarkistettavat"}
        for key in keys
    )


def rule_path(text: str) -> tuple[str, str, str, str, str] | None:
    # Vaatteet and asusteet. These rules intentionally use only text fields, not warehouse categories.
    if has_any(text, "virkapukupaita", "kauluspaita", "dress shirt", "business shirt", "shirt l s", "shirt s s"):
        return ("Vaatteet", "Paidat ja yläosat", "Kauluspaidat", "Kauluspaidat", "improve_rule_dress_shirt")
    if has_any(text, "pikee", "polo", "poloshirt", "polo shirt"):
        return ("Vaatteet", "Paidat ja yläosat", "Pikeepaidat", "Pikeepaidat", "improve_rule_polo")
    if has_any(text, "t paita", "t shirt", "tee shirt", "tshirt", "teepaita"):
        return ("Vaatteet", "Paidat ja yläosat", "T-paidat", "T-paidat", "improve_rule_tshirt")
    if has_any(text, "huppari", "hoodie", "college", "sweatshirt"):
        return ("Vaatteet", "Paidat ja yläosat", "Hupparit ja colleget", "Hupparit ja colleget", "improve_rule_hoodie")
    if has_any(text, "neule", "sweater", "knitted sweater", "cardigan", "oakville", "v neck", "v kaula"):
        return ("Vaatteet", "Paidat ja yläosat", "Neuleet", "Neuleet", "improve_rule_knitwear")
    if has_any(text, "takki", "jacket", "softshell", "kuoritakki", "talvitakki", "sadetakki"):
        return ("Vaatteet", "Takit ja liivit", "Takit", "Takit", "improve_rule_jacket")
    if has_any(text, "liivi", "vest", "bodywarmer"):
        return ("Vaatteet", "Takit ja liivit", "Liivit", "Liivit", "improve_rule_vest")
    if has_any(text, "housu", "shortsit", "pants", "trousers", "soft housu", "lahkeellinen"):
        return ("Vaatteet", "Housut ja alaosat", "Housut ja shortsit", "Housut ja shortsit", "improve_rule_pants")
    if has_any(text, "uimapuku", "swimsuit", "sandaali", "sandaalit"):
        return ("Vaatteet", "Muut vaatteet", "Uima- ja vapaa-ajan vaatteet", "Uima- ja vapaa-ajan vaatteet", "improve_rule_swimwear")
    if has_any(text, "sukka", "socks", "tennissukka"):
        return ("Vaatteet", "Muut vaatteet", "Sukat", "Sukat", "improve_rule_socks")
    if has_any(text, "esiliina", "apron", "tunika", "tyoasu"):
        return ("Vaatteet", "Työvaatteet", "Esiliinat ja työasut", "Esiliinat ja työasut", "improve_rule_workwear")
    if has_any(text, "tyokenka", "turvakenka", "sievi", "saapas", "safety shoe"):
        return ("Työkalut ja turvallisuus", "Työkengät", "Työkengät", "Työkengät", "improve_rule_work_shoes")
    if has_any(text, "lippalakki", "baseball cap", "snapback", "cap xl", "trucker cap", "keps"):
        return ("Asusteet", "Päähineet", "Lippalakit", "Lippalakit", "improve_rule_cap")
    if has_any(text, "pipo", "beanie", "tupsupipo", "neulepipo"):
        return ("Asusteet", "Päähineet", "Pipot", "Pipot", "improve_rule_beanie")
    if has_any(text, "hitsaajanlatsa", "kalastushattu", "bucket hat", "hattu"):
        return ("Asusteet", "Päähineet", "Muut päähineet", "Muut päähineet", "improve_rule_hat")
    if has_any(text, "huivi", "scarf", "tuubihuivi", "buff", "taskuliina"):
        return ("Asusteet", "Huivit ja kaulatuotteet", "Huivit ja kaulatuotteet", "Huivit ja kaulatuotteet", "improve_rule_scarf")
    if has_any(text, "joustovyo", "vyö", "belt"):
        return ("Asusteet", "Vyöt", "Vyöt", "Vyöt", "improve_rule_belt")
    if has_any(text, "hiusdonitsi", "scrunchie", "hiusharja"):
        return ("Asusteet", "Muut asusteet", "Hiusasusteet", "Hiusasusteet", "improve_rule_hair_accessory")
    if has_any(text, "korvatulppa", "earplug"):
        return ("Hyvinvointi", "Hyvinvointi", "Korvatulpat", "Korvatulpat", "improve_rule_earplugs")
    if has_any(text, "aurinkorasva", "sunscreen", "aurinkovoide"):
        return ("Hyvinvointi", "Kosmetiikka", "Aurinkotuotteet", "Aurinkotuotteet", "improve_rule_sunscreen")

    # Common promotional utility items before office-print rules to avoid false matches from words like "opener".
    if has_any(text, "avaimenpera", "keychain", "keyring", "avaimenpera", "avaimenperä"):
        return ("Promootio- ja käyttötavarat", "Asusteet", "Avaimenperät ja poletit", "Avaimenperät ja poletit", "improve_rule_keyring")
    if has_any(text, "juomapullo", "termospullo", "termos", "bottle", "flaska", "camelbak", "flip straw"):
        return ("Koti ja keittiö", "Juoma-astiat", "Juomapullot ja termospullot", "Juomapullot ja termospullot", "improve_rule_bottle")
    if has_any(text, "esinepaikannin", "findmate", "airtag", "tracker", "ulkomokkula", "wifi", "mesh", "router", "led menutaulu") or has_word(text, "5g", "led"):
        return ("Elektroniikka", "Elektroniikka", "Muut elektroniikkatuotteet", "Muut elektroniikkatuotteet", "improve_rule_electronics")

    # Office, print and packaging.
    if has_any(text, "transfer logo", "siirtokuva", "kangasmerkki", "haalarimerkki", "overall patch"):
        return ("Toimisto, painotuotteet ja pakkaukset", "Painotuotteet ja merkit", "Siirtokuvat ja tekstiilimerkit", "Siirtokuvat ja tekstiilimerkit", "improve_rule_transfer_patch")
    if has_any(text, "pinssi", "rintanappi", "badge", "nimikyltti", "name badge"):
        return ("Toimisto, painotuotteet ja pakkaukset", "Painotuotteet ja merkit", "Pinssit ja rintanapit", "Pinssit ja rintanapit", "improve_rule_pin_badge")
    if has_any(text, "tarra", "etiketti", "sticker", "label"):
        return ("Toimisto, painotuotteet ja pakkaukset", "Painotuotteet ja merkit", "Tarrat ja etiketit", "Tarrat ja etiketit", "improve_rule_sticker")
    if has_any(text, "juliste", "poster"):
        return ("Toimisto, painotuotteet ja pakkaukset", "Painotuotteet ja merkit", "Julisteet", "Julisteet", "improve_rule_poster")
    if has_any(text, "brochure", "esite", "lehtinen", "publication", "handbook", "code of conduct"):
        return ("Toimisto, painotuotteet ja pakkaukset", "Painotuotteet ja merkit", "Esitteet ja julkaisut", "Esitteet ja julkaisut", "improve_rule_publication")
    if has_any(text, "folder", "kansio"):
        return ("Toimisto, painotuotteet ja pakkaukset", "Muistikirjat ja paperituotteet", "Kansiot", "Kansiot", "improve_rule_folder")
    if has_any(text, "envelope", "kirjekuori"):
        return ("Toimisto, painotuotteet ja pakkaukset", "Pakkaukset", "Kirjekuoret", "Kirjekuoret", "improve_rule_envelope")
    if has_any(text, "packing tape", "pakkausteippi", "teippi"):
        return ("Toimisto, painotuotteet ja pakkaukset", "Pakkaukset", "Pakkausteipit", "Pakkausteipit", "improve_rule_packaging_tape")
    if has_any(text, "tuotelappu", "hang tag", "narikkalappu"):
        return ("Toimisto, painotuotteet ja pakkaukset", "Painotuotteet ja merkit", "Tuotelaput ja tunnisteet", "Tuotelaput ja tunnisteet", "improve_rule_tag")
    if has_word(text, "kyna", "kynä", "pen", "pencil", "kuulakarkikyna", "mustekyna"):
        return ("Toimisto, painotuotteet ja pakkaukset", "Kirjoitusvälineet", "Kynät", "Kynät", "improve_rule_pen")
    if has_any(text, "muistikirja", "notebook", "vihko", "kierrevihko"):
        return ("Toimisto, painotuotteet ja pakkaukset", "Muistikirjat ja paperituotteet", "Muistikirjat", "Muistikirjat", "improve_rule_notebook")

    # Promootiotuotteet and small utility products.
    if has_any(text, "kaulanauha", "lanyard", "huomionauha"):
        return ("Promootio- ja käyttötavarat", "Asusteet", "Kaulanauhat", "Kaulanauhat", "improve_rule_lanyard")
    if has_any(text, "hiirimatto", "mousepad", "mouse mat"):
        return ("Promootio- ja käyttötavarat", "Promootiotuotteet", "Hiirimatot", "Hiirimatot", "improve_rule_mousepad")
    if has_any(text, "ilmapallo", "balloon"):
        return ("Promootio- ja käyttötavarat", "Tapahtumatuotteet", "Ilmapallot", "Ilmapallot", "improve_rule_balloon")
    if has_any(text, "beachflag", "lippu", "banderolli", "flag", "banner"):
        return ("Promootio- ja käyttötavarat", "Tapahtumatuotteet", "Liput ja banderollit", "Liput ja banderollit", "improve_rule_flag")
    if has_any(text, "ranneke", "wristband"):
        return ("Promootio- ja käyttötavarat", "Tapahtumatuotteet", "Rannekkeet", "Rannekkeet", "improve_rule_wristband")
    if has_any(text, "satulasuoja", "istuinsuoja", "autonpenkki", "vetokuulansuoja", "jaaraappa"):
        return ("Promootio- ja käyttötavarat", "Promootiotuotteet", "Auto- ja pyörätarvikkeet", "Auto- ja pyörätarvikkeet", "improve_rule_vehicle_accessory")
    if has_any(text, "lasinalunen", "baarimatto", "cocktailtikku", "menu taulu", "menutaulu"):
        return ("Promootio- ja käyttötavarat", "Promootiotuotteet", "Ravintola- ja baarituotteet", "Ravintola- ja baarituotteet", "improve_rule_bar_accessory")

    # Koti, keittiö, juoma-astiat and food.
    if has_any(text, "muki", "mug", "kuppi", "cup", "kertakayttokuppi"):
        return ("Koti ja keittiö", "Juoma-astiat", "Mukit", "Mukit", "improve_rule_mug")
    if has_any(text, "lasit", "lasi", "tuopit", "drink glass", "viinilasi"):
        return ("Koti ja keittiö", "Juoma-astiat", "Lasit", "Lasit", "improve_rule_glass")
    if has_any(text, "pyyhe", "laudeliina", "tiskiratti", "lounasliina"):
        return ("Koti ja keittiö", "Kodintekstiilit", "Pyyhkeet ja laudeliinat", "Pyyhkeet ja laudeliinat", "improve_rule_towel")
    if has_any(text, "viltti", "huopa", "blanket"):
        return ("Koti ja keittiö", "Kodintekstiilit", "Peitot ja viltit", "Peitot ja viltit", "improve_rule_blanket")
    if has_any(text, "ruokailuvaline", "aterimet", "veitsi", "leikkuulauta", "pannu", "kulho", "lautanen"):
        return ("Koti ja keittiö", "Keittiötuotteet", "Keittiövälineet", "Keittiövälineet", "improve_rule_kitchenware")
    if has_any(text, "kynttila", "candle", "maljakko", "vase", "saunatyyny"):
        return ("Koti ja keittiö", "Sisustus", "Sisustustuotteet", "Sisustustuotteet", "improve_rule_home_decor")
    if has_any(text, "hunaja", "sisu", "karamelli", "karkki", "suklaa", "makeinen", "purukumi", "candy", "chocolate"):
        return ("Elintarvikkeet", "Makeiset", "Makeiset", "Makeiset", "improve_rule_candy")
    if has_any(text, "kahvi", "tee ", "tea "):
        return ("Elintarvikkeet", "Juomat", "Kahvi ja tee", "Kahvi ja tee", "improve_rule_coffee_tea")

    # Bags, electronics, gift cards and leisure.
    if has_any(text, "reppu", "backpack", "rinkka"):
        return ("Laukut ja matkatavarat", "Reput", "Reput", "Reput", "improve_rule_backpack")
    if has_any(text, "matkalaukku", "samsonite", "spinner"):
        return ("Laukut ja matkatavarat", "Matkatavarat", "Matkalaukut", "Matkalaukut", "improve_rule_luggage")
    if has_any(text, "puhelinlaukku", "toilettilaukku", "laukku", "bag", "kassi", "tote"):
        return ("Laukut ja matkatavarat", "Laukut", "Kassit ja laukut", "Kassit ja laukut", "improve_rule_bag")
    if has_any(text, "lahjakortti", "gift card", "bonuspalkinto", "verkkokauppaan", "kylpylaloma"):
        return ("Lahjat ja sesonkituotteet", "Lahjakortit ja palvelut", "Lahjakortit ja palvelut", "Lahjakortit ja palvelut", "improve_rule_giftcard")
    if has_any(text, "tuotepaketti", "paketti", "setti", "kit", "bundle"):
        return ("Lahjat ja sesonkituotteet", "Tuotepaketit ja setit", "Tuotepaketit ja setit", "Tuotepaketit ja setit", "improve_rule_bundle")
    if has_any(text, "golf", "frisbee", "jumppakeppi", "pyorailylasit", "lenkkiasu"):
        return ("Vapaa-aika", "Urheilu", "Urheilutuotteet", "Urheilutuotteet", "improve_rule_sport")

    return None


def add_codes(df: pd.DataFrame) -> pd.DataFrame:
    l1_code_map = {name: f"{i:02d}" for i, name in enumerate(L1_ORDER, start=1)}
    extras = [name for name in sorted(df["product_group_l1_name"].dropna().unique(), key=norm) if name not in l1_code_map]
    for name in extras:
        l1_code_map[name] = f"{len(l1_code_map) + 1:02d}"
    df["product_group_l1_code"] = df["product_group_l1_name"].map(l1_code_map)

    parent_cols: list[str] = []
    for level in range(2, 5):
        parent_cols.extend([f"product_group_l{level - 1}_code", f"product_group_l{level - 1}_name"])
        name_col = f"product_group_l{level}_name"
        code_col = f"product_group_l{level}_code"
        code_map: dict[tuple[str, ...], str] = {}
        rows = df[parent_cols + [name_col]].drop_duplicates().sort_values(parent_cols + [name_col], key=lambda s: s.map(norm))
        for parent_key, group in rows.groupby(parent_cols, sort=False, dropna=False):
            parent_code = parent_key[-2] if isinstance(parent_key, tuple) else str(parent_key)
            for idx, (_, row) in enumerate(group.iterrows(), start=1):
                key = tuple(row[parent_cols + [name_col]].astype(str))
                suffix = f"{idx:03d}" if level == 4 else f"{idx:02d}"
                code_map[key] = f"{parent_code}.{suffix}"
        df[code_col] = df[parent_cols + [name_col]].astype(str).apply(lambda r: code_map[tuple(r)], axis=1)

    df["product_group_path_code"] = (
        df["product_group_l1_code"].astype(str)
        + " > "
        + df["product_group_l2_code"].astype(str)
        + " > "
        + df["product_group_l3_code"].astype(str)
        + " > "
        + df["product_group_l4_code"].astype(str)
    )
    df["product_group_path_name"] = (
        df["product_group_l1_name"].astype(str)
        + " > "
        + df["product_group_l2_name"].astype(str)
        + " > "
        + df["product_group_l3_name"].astype(str)
        + " > "
        + df["product_group_l4_name"].astype(str)
    )
    return df


def level_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for level in range(1, 5):
        group_cols = [f"product_group_l{i}_name" for i in range(1, level + 1)]
        code_cols = [f"product_group_l{i}_code" for i in range(1, level + 1)]
        grouped = df.groupby(code_cols + group_cols, dropna=False).size().reset_index(name="product_count")
        for _, row in grouped.iterrows():
            rows.append(
                {
                    "level": level,
                    "code": row[f"product_group_l{level}_code"],
                    "name": row[f"product_group_l{level}_name"],
                    "path": " > ".join(str(row[f"product_group_l{i}_name"]) for i in range(1, level + 1)),
                    "product_count": int(row["product_count"]),
                }
            )
    return pd.DataFrame(rows)


def overview_counts(df: pd.DataFrame) -> dict[str, int]:
    return {
        f"L{level}": int(df[[f"product_group_l{level}_code", f"product_group_l{level}_name"]].drop_duplicates().shape[0])
        for level in range(1, 5)
    }


def other_count(df: pd.DataFrame) -> int:
    mask = df.apply(is_other_like, axis=1)
    return int(mask.sum())


def main() -> None:
    df = pd.read_csv(INPUT, dtype=str, keep_default_na=False, low_memory=False)
    before = df.copy()

    candidates = df.apply(is_other_like, axis=1)
    changes: list[dict[str, object]] = []
    for idx, row in df.loc[candidates].iterrows():
        text = text_for(row)
        path = rule_path(text)
        if not path:
            continue
        l1, l2, l3, l4, source = path
        old_path = clean(row.get("product_group_path_name", ""))
        df.loc[idx, ["product_group_l1_name", "product_group_l2_name", "product_group_l3_name", "product_group_l4_name"]] = [l1, l2, l3, l4]
        old_source = clean(row.get("product_group_source", ""))
        df.at[idx, "product_group_source"] = f"{old_source}|{source}" if old_source else source
        changes.append(
            {
                "row_index": int(idx),
                "code": clean(row.get("code")),
                "product_name": clean(row.get("product_name")) or clean(row.get("title_fi")),
                "old_path": old_path,
                "new_path": " > ".join([l1, l2, l3, l4]),
                "rule": source,
            }
        )

    # Keep the agreed minimum: any L4 leaf under 5 products is merged into a larger bucket.
    # If the parent L3 has no large bucket, consolidate at L1 level; if even that is too small,
    # use the global review bucket so the final file has no one-off leaves.
    small_changes = 0
    for _ in range(5):
        l4_counts = df.groupby(["product_group_l1_name", "product_group_l2_name", "product_group_l3_name", "product_group_l4_name"], dropna=False).size()
        small_keys = {key for key, count in l4_counts.items() if count < MIN_L4_SIZE}
        if not small_keys:
            break
        changed_this_round = 0
        l1_counts = df.groupby("product_group_l1_name", dropna=False).size().to_dict()
        for idx, row in df.iterrows():
            key = (row["product_group_l1_name"], row["product_group_l2_name"], row["product_group_l3_name"], row["product_group_l4_name"])
            if key not in small_keys:
                continue
            l1 = str(row["product_group_l1_name"])
            if l1_counts.get(l1, 0) >= MIN_L4_SIZE and l1 != "Muut / tarkistettavat":
                l2 = f"Muut {l1.lower()}"
                l3 = l2
                l4 = l2
            else:
                l1 = "Muut / tarkistettavat"
                l2 = "Muut / tarkistettavat"
                l3 = "Muut / tarkistettavat"
                l4 = "Muut / tarkistettavat"
            old = (row["product_group_l1_name"], row["product_group_l2_name"], row["product_group_l3_name"], row["product_group_l4_name"])
            new = (l1, l2, l3, l4)
            if old != new:
                df.loc[idx, ["product_group_l1_name", "product_group_l2_name", "product_group_l3_name", "product_group_l4_name"]] = list(new)
                df.at[idx, "product_group_source"] = clean(row.get("product_group_source")) + "|l4_min5_after_other_improvement"
                small_changes += 1
                changed_this_round += 1
        if changed_this_round == 0:
            break

    remaining_counts = df.groupby(["product_group_l1_name", "product_group_l2_name", "product_group_l3_name", "product_group_l4_name"], dropna=False).size()
    remaining_small = {key for key, count in remaining_counts.items() if count < MIN_L4_SIZE}
    for idx, row in df.iterrows():
        key = (row["product_group_l1_name"], row["product_group_l2_name"], row["product_group_l3_name"], row["product_group_l4_name"])
        if key in remaining_small:
            df.loc[idx, ["product_group_l1_name", "product_group_l2_name", "product_group_l3_name", "product_group_l4_name"]] = [
                "Muut / tarkistettavat",
                "Muut / tarkistettavat",
                "Muut / tarkistettavat",
                "Muut / tarkistettavat",
            ]
            df.at[idx, "product_group_source"] = clean(row.get("product_group_source")) + "|l4_min5_global_review_bucket"
            small_changes += 1

    df = add_codes(df)
    report = pd.DataFrame(changes)
    levels = level_summary(df)

    source_counts = df["product_group_source"].str.split("|").explode().value_counts().reset_index()
    source_counts.columns = ["source_marker", "product_count"]

    l4_sizes = df.groupby(["product_group_l1_name", "product_group_l2_name", "product_group_l3_name", "product_group_l4_name"], dropna=False).size()
    summary = {
        "input": str(INPUT.resolve()),
        "output_csv": str(OUTPUT_CSV.resolve()),
        "output_xlsx": str(OUTPUT_XLSX.resolve()),
        "rows_total": int(len(df)),
        "candidate_other_like_rows_before": int(candidates.sum()),
        "other_like_rows_before": other_count(before),
        "other_like_rows_after": other_count(df),
        "rows_reclassified_from_other_like": int(len(report)),
        "small_l4_rows_merged_after_improvement": int(small_changes),
        "minimum_l4_group_size": MIN_L4_SIZE,
        "minimum_final_l4_size": int(l4_sizes.min()),
        "group_counts_before": overview_counts(before),
        "group_counts_after": overview_counts(df),
        "rule_counts": report["rule"].value_counts().to_dict() if not report.empty else {},
    }

    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    report.to_csv(REPORT_CSV, index=False, encoding="utf-8-sig")
    levels.to_csv(LEVEL_SUMMARY_CSV, index=False, encoding="utf-8-sig")
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Products", index=False)
        levels.to_excel(writer, sheet_name="Yhteenveto", index=False)
        report.to_excel(writer, sheet_name="Muut_siirrot", index=False)
        source_counts.to_excel(writer, sheet_name="Source_counts", index=False)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
