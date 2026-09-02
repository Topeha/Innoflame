from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd


BASE = Path("product_master_enrichment/final_product_grouping")
INPUT = BASE / "products_product_group_tree_no_inventory_warehouse_category_l4_min5_improved.csv"
OUTPUT_CSV = BASE / "products_product_group_tree_feedback_3level.csv"
OUTPUT_XLSX = BASE / "products_product_group_tree_feedback_3level.xlsx"
REPORT_CSV = BASE / "product_group_feedback_3level_mapping_report.csv"
LEVEL_SUMMARY_CSV = BASE / "product_group_feedback_3level_level_summary.csv"
SUMMARY_JSON = BASE / "product_group_feedback_3level_summary.json"

MIN_L3_SIZE = 5

L1_ORDER = [
    "Vaatteet",
    "Promootio- ja tapahtumatuotteet",
    "Koti ja keittiö",
    "Toimisto, painotuotteet ja pakkaukset",
    "Laukut ja matkatavarat",
    "Lahjakortit ja hyväntekeväisyys",
    "Työkalut ja turvallisuus",
    "Korut, kellot ja aurinkolasit",
    "Decalit ja merkkaustuotteet",
    "Elintarvikkeet",
    "Elektroniikka",
    "Vapaa-aika",
    "Hyvinvointi",
    "Muut / tarkistettavat",
]

TEXT_COLUMNS = ["product_name", "title_fi", "description_fi", "searchdata", "sku", "code", "brand_name"]


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


def old_path_text(row: pd.Series) -> str:
    return norm(" ".join(clean(row.get(f"product_group_l{i}_name", "")) for i in range(1, 5)))


def title_case_other(parent: str) -> str:
    parent = str(parent).strip()
    if norm(parent).startswith("muut "):
        return f"Tarkistettavat {parent[5:].strip().lower()}"
    return f"Muut {parent.lower()}"


def feedback_path(row: pd.Series) -> tuple[str, str, str, str]:
    text = text_for(row)
    path_text = old_path_text(row)
    old_l1 = clean(row.get("product_group_l1_name"))
    old_l2 = clean(row.get("product_group_l2_name"))
    old_l3 = clean(row.get("product_group_l3_name"))
    old_l4 = clean(row.get("product_group_l4_name"))

    # GoSystem marking/decal products: keep separate because they have their own operational handling.
    if has_any(text, "transfer logo", "siirtokuva", "kangasmerkki", "haalarimerkki", "overall patch", "tekstiilimerkki"):
        return ("Decalit ja merkkaustuotteet", "Decalit", "Siirtokuvat ja tekstiilimerkit", "feedback_decal_transfer")
    if has_any(text, "tarra", "etiketti", "sticker", "label", "tuotelappu", "hang tag"):
        return ("Decalit ja merkkaustuotteet", "Decalit", "Tarrat, etiketit ja tuotelaput", "feedback_decal_sticker")

    # Promotional give-away products.
    if has_any(text, "kaulanauha", "lanyard", "huomionauha"):
        return ("Promootio- ja tapahtumatuotteet", "Jakotuotteet", "Kaulanauhat", "feedback_promo_lanyard")
    if has_any(text, "tuubihuivi", "buff", "putkihuivi"):
        return ("Promootio- ja tapahtumatuotteet", "Jakotuotteet", "Putkihuivit", "feedback_promo_tube_scarf")
    if has_any(text, "avaimenpera", "avaimenperä", "keychain", "keyring", "polet"):
        return ("Promootio- ja tapahtumatuotteet", "Jakotuotteet", "Avaimenperät", "feedback_promo_keyring")
    if has_word(text, "kyna", "kynä", "pen", "pencil") or has_any(path_text, "kirjoitusvalineet kynat"):
        return ("Promootio- ja tapahtumatuotteet", "Jakotuotteet", "Kynät", "feedback_promo_pen")
    if has_any(text, "heijastinliivi", "reflective vest"):
        return ("Työkalut ja turvallisuus", "Suojaimet", "Heijastinliivit", "feedback_ppe_reflective_vest")
    if has_any(text, "heijastin", "reflector"):
        return ("Promootio- ja tapahtumatuotteet", "Jakotuotteet", "Heijastimet", "feedback_promo_reflector")
    if has_any(text, "pinssi", "rintanappi", "badge"):
        return ("Promootio- ja tapahtumatuotteet", "Jakotuotteet", "Pinssit ja rintanapit", "feedback_promo_badge")
    if has_any(text, "hiirimatto", "mousepad", "mouse mat"):
        return ("Promootio- ja tapahtumatuotteet", "Jakotuotteet", "Muut jakotuotteet", "feedback_promo_small_goods")

    # Event products.
    if has_any(text, "beachflag", "banderolli", "banner", "roll up", "messuseina", "messuseinake", "messu", "flag"):
        return ("Promootio- ja tapahtumatuotteet", "Tapahtumatuotteet", "Liput, banderollit ja messutuotteet", "feedback_event_display")
    if has_any(text, "ilmapallo", "balloon", "ranneke", "wristband", "narikkalappu"):
        return ("Promootio- ja tapahtumatuotteet", "Tapahtumatuotteet", "Muut tapahtumatuotteet", "feedback_event_goods")

    # Promo drink accessories and bags stay under the new promo structure only when the old path was promo.
    if old_l1 == "Promootio- ja käyttötavarat" and has_any(text, "lasinalunen", "baarimatto", "cocktailtikku", "juomatarvike", "drink"):
        return ("Promootio- ja tapahtumatuotteet", "Juomatarvikkeet", "Juomatarvikkeet", "feedback_promo_drink_accessory")
    if old_l1 == "Promootio- ja käyttötavarat" and has_any(text, "kassi", "bag", "tote"):
        return ("Promootio- ja tapahtumatuotteet", "Kassit", "Kassit", "feedback_promo_bag")

    # Clothing accessories move under Vaatteet > Asusteet.
    if has_any(text, "lippalakki", "baseball cap", "snapback", "trucker cap", "keps"):
        return ("Vaatteet", "Asusteet", "Lippalakit", "feedback_clothing_cap")
    if has_any(text, "pipo", "beanie", "tupsupipo", "neulepipo"):
        return ("Vaatteet", "Asusteet", "Pipot", "feedback_clothing_beanie")
    if has_any(text, "kasine", "käsine", "glove", "mittens", "rukkanen"):
        return ("Vaatteet", "Asusteet", "Käsineet", "feedback_clothing_gloves")
    if has_any(text, "sukka", "socks", "tennissukka"):
        return ("Vaatteet", "Asusteet", "Sukat", "feedback_clothing_socks")
    if has_any(text, "tyokenka", "turvakenka", "kenka", "saapas", "sievi", "shoe", "boot"):
        return ("Vaatteet", "Asusteet", "Jalkineet", "feedback_clothing_footwear")
    if has_any(text, "joustovyo", "vyö", "vyo", "belt"):
        return ("Vaatteet", "Asusteet", "Vyöt", "feedback_clothing_belt")
    if has_any(text, "hiusdonitsi", "scrunchie", "hiusasuste"):
        return ("Vaatteet", "Asusteet", "Muut asusteet", "feedback_clothing_hair")
    if has_any(text, "huivi", "scarf", "taskuliina", "solmio"):
        return ("Vaatteet", "Asusteet", "Huivit", "feedback_clothing_scarf")
    if old_l1 == "Asusteet" and has_any(path_text, "paahineet"):
        return ("Vaatteet", "Asusteet", "Muut asusteet", "feedback_clothing_accessory")

    # Jewellery, watches and eyewear become one top-level group.
    if has_any(text, "aurinkolasi", "sunglasses", "silmalasi", "eyewear"):
        return ("Korut, kellot ja aurinkolasit", "Silmälasit ja aurinkolasit", "Silmälasit ja aurinkolasit", "feedback_eyewear")
    if old_l1 in {"Korut ja kellot", "Korut, kellot ja aurinkolasit"} or has_any(path_text, "korut ja kellot", "aurinkolasit") or has_any(text, "kello", "watch", "koru", "kaulakoru", "korvakoru"):
        return ("Korut, kellot ja aurinkolasit", "Korut ja kellot", "Korut ja kellot", "feedback_jewellery_watch")

    # Safety is narrowed to PPE/suojaimet; reflectors are handled above as promotional products.
    if old_l1 == "Työkalut ja turvallisuus" and has_any(text, "suojain", "suojalas", "kasvomaski", "maski", "helmet", "kypärä", "kypara"):
        return ("Työkalut ja turvallisuus", "Suojaimet", "Suojaimet", "feedback_ppe")
    if old_l2 == "Turvallisuus":
        return ("Työkalut ja turvallisuus", "Suojaimet", "Muut suojaimet", "feedback_safety_to_ppe")

    # Gift/season hierarchy is narrowed to gift cards and charity only.
    if has_any(text, "hyvantekevaisyys", "charity", "lahjoitus"):
        return ("Lahjakortit ja hyväntekeväisyys", "Hyväntekeväisyys", "Hyväntekeväisyys", "feedback_charity")
    if has_any(text, "lahjakortti", "gift card", "vapaalippu", "leffalippu", "elokuvalippu", "lippupiste", "finnkino", "biorex", "kylpylaloma", "bookbeat"):
        return ("Lahjakortit ja hyväntekeväisyys", "Lahjakortit", "Lahjakortit ja pääsyliput", "feedback_giftcard")
    if old_l1 == "Lahjat ja sesonkituotteet":
        if has_any(text, "joulu", "christmas", "xmas", "piparkakku", "suklaa", "karkki", "makeinen", "hunaja"):
            return ("Elintarvikkeet", "Sesonkiherkut", "Sesonkiherkut", "feedback_season_food")
        if has_any(text, "kynttila", "maljakko", "vase", "sisustus", "sauna", "pyyhe", "huopa", "viltti"):
            return ("Koti ja keittiö", "Sisustus ja kodintekstiilit", "Sisustus- ja lahjatuotteet", "feedback_season_home")
        if has_any(text, "paketti", "setti", "bundle", "kit"):
            return ("Koti ja keittiö", "Lahjasetit", "Lahjasetit", "feedback_gift_set_home")
        return ("Muut / tarkistettavat", "Muut / tarkistettavat", "Muut / tarkistettavat", "feedback_gift_needs_review")

    # Rename the promo top level for remaining rows.
    if old_l1 == "Promootio- ja käyttötavarat":
        if has_any(path_text, "juomatarvikkeet", "juoma astiat"):
            return ("Promootio- ja tapahtumatuotteet", "Juomatarvikkeet", "Muut juomatarvikkeet", "feedback_promo_rename_drink_accessory")
        if has_any(path_text, "kassit"):
            return ("Promootio- ja tapahtumatuotteet", "Kassit", "Muut kassit", "feedback_promo_rename_bag")
        if has_any(path_text, "tapahtumatuotteet"):
            return ("Promootio- ja tapahtumatuotteet", "Tapahtumatuotteet", old_l3 if old_l3 and norm(old_l3) != norm(old_l2) else "Muut tapahtumatuotteet", "feedback_promo_rename_event")
        return ("Promootio- ja tapahtumatuotteet", "Muut promootiotuotteet", old_l3 if old_l3 and norm(old_l3) != norm(old_l2) else "Muut promootiotuotteet", "feedback_promo_rename_other")

    # Clean duplicate L2/L3 naming in known places.
    if old_l1 == "Koti ja keittiö" and old_l2 == "Kodintekstiilit" and norm(old_l3) == "kodintekstiilit":
        return ("Koti ja keittiö", "Kodintekstiilit", "Muut kodintekstiilit", "feedback_remove_duplicate_level_name")

    # Keep existing useful paths, but drop L4 and avoid L2/L3 duplicate labels.
    l1, l2, l3 = old_l1, old_l2, old_l3
    if old_l1 == "Asusteet":
        l1, l2, l3 = "Vaatteet", "Asusteet", old_l3 if old_l3 else "Muut asusteet"
    if norm(l2) == norm(l3) or not l3:
        l3 = title_case_other(l2) if l2 else "Muut / tarkistettavat"
    return (l1 or "Muut / tarkistettavat", l2 or "Muut / tarkistettavat", l3, "feedback_keep_3level")


def add_codes(df: pd.DataFrame) -> pd.DataFrame:
    l1_code_map = {name: f"{i:02d}" for i, name in enumerate(L1_ORDER, start=1)}
    extras = [name for name in sorted(df["product_group_l1_name"].dropna().unique(), key=norm) if name not in l1_code_map]
    for name in extras:
        l1_code_map[name] = f"{len(l1_code_map) + 1:02d}"
    df["product_group_l1_code"] = df["product_group_l1_name"].map(l1_code_map)

    for level in [2, 3]:
        parent_cols = [f"product_group_l{i}_code" for i in range(1, level)] + [f"product_group_l{i}_name" for i in range(1, level)]
        parent_cols = []
        for i in range(1, level):
            parent_cols.extend([f"product_group_l{i}_code", f"product_group_l{i}_name"])
        name_col = f"product_group_l{level}_name"
        code_col = f"product_group_l{level}_code"
        code_map: dict[tuple[str, ...], str] = {}
        rows = df[parent_cols + [name_col]].drop_duplicates().sort_values(parent_cols + [name_col], key=lambda s: s.map(norm))
        for parent_key, group in rows.groupby(parent_cols, sort=False, dropna=False):
            parent_code = parent_key[-2] if isinstance(parent_key, tuple) else str(parent_key)
            for idx, (_, row) in enumerate(group.iterrows(), start=1):
                key = tuple(row[parent_cols + [name_col]].astype(str))
                code_map[key] = f"{parent_code}.{idx:02d}"
        df[code_col] = df[parent_cols + [name_col]].astype(str).apply(lambda r: code_map[tuple(r)], axis=1)

    df["product_group_l4_code"] = ""
    df["product_group_l4_name"] = ""
    df["product_group_path_code"] = (
        df["product_group_l1_code"].astype(str)
        + " > "
        + df["product_group_l2_code"].astype(str)
        + " > "
        + df["product_group_l3_code"].astype(str)
    )
    df["product_group_path_name"] = (
        df["product_group_l1_name"].astype(str)
        + " > "
        + df["product_group_l2_name"].astype(str)
        + " > "
        + df["product_group_l3_name"].astype(str)
    )
    return df


def level_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for level in [1, 2, 3]:
        cols = []
        for i in range(1, level + 1):
            cols.extend([f"product_group_l{i}_code", f"product_group_l{i}_name"])
        grouped = df.groupby(cols, dropna=False).size().reset_index(name="product_count")
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
        for level in [1, 2, 3]
    }


def main() -> None:
    df = pd.read_csv(INPUT, dtype=str, keep_default_na=False, low_memory=False)
    original = df.copy()

    mapped = df.apply(feedback_path, axis=1, result_type="expand")
    mapped.columns = ["new_l1", "new_l2", "new_l3", "feedback_rule"]
    for level, col in [(1, "new_l1"), (2, "new_l2"), (3, "new_l3")]:
        df[f"product_group_l{level}_name"] = mapped[col]

    duplicate_l2_l3_mask = df["product_group_l2_name"].map(norm) == df["product_group_l3_name"].map(norm)
    for idx, row in df.loc[duplicate_l2_l3_mask].iterrows():
        df.at[idx, "product_group_l3_name"] = title_case_other(str(row["product_group_l2_name"]))
        mapped.at[idx, "feedback_rule"] = f"{mapped.at[idx, 'feedback_rule']}|feedback_remove_l2_l3_duplicate"

    double_other_mask = df["product_group_l3_name"].map(norm).str.startswith("muut muut ")
    for idx, row in df.loc[double_other_mask].iterrows():
        cleaned = re.sub(r"(?i)^muut\s+muut\s+", "", str(row["product_group_l3_name"])).strip()
        df.at[idx, "product_group_l3_name"] = f"Tarkistettavat {cleaned.lower()}" if cleaned else "Tarkistettavat tuotteet"
        mapped.at[idx, "feedback_rule"] = f"{mapped.at[idx, 'feedback_rule']}|feedback_remove_double_other"

    # Merge tiny L3 leaves to parent-level other groups, then to global review if still too small.
    for _ in range(4):
        counts = df.groupby(["product_group_l1_name", "product_group_l2_name", "product_group_l3_name"], dropna=False).size()
        small = {key for key, count in counts.items() if count < MIN_L3_SIZE}
        if not small:
            break
        changed = 0
        for idx, row in df.iterrows():
            key = (row["product_group_l1_name"], row["product_group_l2_name"], row["product_group_l3_name"])
            if key not in small:
                continue
            replacement = title_case_other(str(row["product_group_l2_name"]))
            if row["product_group_l3_name"] != replacement:
                df.at[idx, "product_group_l3_name"] = replacement
                mapped.at[idx, "feedback_rule"] = f"{mapped.at[idx, 'feedback_rule']}|feedback_l3_min5_parent_other"
                changed += 1
        if changed == 0:
            break

    counts = df.groupby(["product_group_l1_name", "product_group_l2_name", "product_group_l3_name"], dropna=False).size()
    small = {key for key, count in counts.items() if count < MIN_L3_SIZE}
    for idx, row in df.iterrows():
        key = (row["product_group_l1_name"], row["product_group_l2_name"], row["product_group_l3_name"])
        if key in small:
            df.loc[idx, ["product_group_l1_name", "product_group_l2_name", "product_group_l3_name"]] = [
                "Muut / tarkistettavat",
                "Muut / tarkistettavat",
                "Tarkistettavat tuotteet",
            ]
            mapped.at[idx, "feedback_rule"] = f"{mapped.at[idx, 'feedback_rule']}|feedback_l3_min5_global_review"

    old_source = df["product_group_source"].fillna("").astype(str)
    df["product_group_source"] = old_source + "|feedback_3level:" + mapped["feedback_rule"].astype(str)
    df = add_codes(df)

    report = pd.DataFrame(
        {
            "code": original.get("code", ""),
            "product_name": original.get("product_name", ""),
            "old_path": original.get("product_group_path_name", ""),
            "new_path": df["product_group_path_name"],
            "feedback_rule": mapped["feedback_rule"],
        }
    )
    report = report[report["old_path"] != report["new_path"]].copy()
    levels = level_summary(df)
    l3_counts = df.groupby(["product_group_l1_name", "product_group_l2_name", "product_group_l3_name"], dropna=False).size()
    duplicate_l2_l3 = int((df["product_group_l2_name"].map(norm) == df["product_group_l3_name"].map(norm)).sum())
    summary = {
        "input": str(INPUT.resolve()),
        "output_csv": str(OUTPUT_CSV.resolve()),
        "output_xlsx": str(OUTPUT_XLSX.resolve()),
        "rows_total": int(len(df)),
        "active_group_levels": 3,
        "l4_left_blank": True,
        "minimum_l3_group_size": MIN_L3_SIZE,
        "minimum_final_l3_size": int(l3_counts.min()),
        "group_counts_before": {
            f"L{level}": int(original[[f"product_group_l{level}_code", f"product_group_l{level}_name"]].drop_duplicates().shape[0])
            for level in [1, 2, 3, 4]
        },
        "group_counts_after": overview_counts(df),
        "rows_with_l2_l3_same_name_after": duplicate_l2_l3,
        "rows_changed": int(len(report)),
        "rule_counts": mapped["feedback_rule"].value_counts().to_dict(),
    }

    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    report.to_csv(REPORT_CSV, index=False, encoding="utf-8-sig")
    levels.to_csv(LEVEL_SUMMARY_CSV, index=False, encoding="utf-8-sig")
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    source_counts = df["product_group_source"].str.split("|").explode().value_counts().reset_index()
    source_counts.columns = ["source_marker", "product_count"]
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Products", index=False)
        levels.to_excel(writer, sheet_name="Yhteenveto", index=False)
        report.head(20000).to_excel(writer, sheet_name="Muutokset", index=False)
        source_counts.to_excel(writer, sheet_name="Source_counts", index=False)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
