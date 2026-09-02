from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parent
OUTPUTS = BASE / "outputs"
CSV_PATH = OUTPUTS / "Innoflame_merged_sales_csv_source_with_L1_L2_L3_delivery_handling.csv"

GROUPS = {
    "01.01.02": ("1", "Vaatteet", "01.01", "Asusteet", "01.01.02", "Jalkineet"),
    "01.01.03": ("1", "Vaatteet", "01.01", "Asusteet", "01.01.03", "Käsineet"),
    "01.01.07": ("1", "Vaatteet", "01.01", "Asusteet", "01.01.07", "Sukat"),
    "01.04.01": ("1", "Vaatteet", "01.04", "Paidat ja yläosat", "01.04.01", "Hupparit ja colleget"),
    "01.04.05": ("1", "Vaatteet", "01.04", "Paidat ja yläosat", "01.04.05", "Pikeepaidat"),
    "01.05.01": ("1", "Vaatteet", "01.05", "Takit ja liivit", "01.05.01", "Liivit"),
    "01.05.03": ("1", "Vaatteet", "01.05", "Takit ja liivit", "01.05.03", "Takit"),
    "01.02.01": ("1", "Vaatteet", "01.02", "Housut ja alaosat", "01.02.01", "Housut ja shortsit"),
    "02.01.04": ("2", "Promootio- ja tapahtumatuotteet", "02.01", "Jakotuotteet", "02.01.04", "Kynät"),
    "02.02.01": ("2", "Promootio- ja tapahtumatuotteet", "02.02", "Juomatarvikkeet", "02.02.01", "Muut juomatarvikkeet"),
    "02.04.02": ("2", "Promootio- ja tapahtumatuotteet", "02.04", "Muut promootiotuotteet", "02.04.02", "Tarkistettavat promootiotuotteet"),
    "02.05.01": ("2", "Promootio- ja tapahtumatuotteet", "02.05", "Tapahtumatuotteet", "02.05.01", "Liput, banderollit ja messutuotteet"),
    "03.01.03": ("3", "Koti ja keittiö", "03.01", "Juoma-astiat", "03.01.03", "Mukit"),
    "03.01.05": ("3", "Koti ja keittiö", "03.01", "Juoma-astiat", "03.01.05", "Pullot"),
    "03.02.03": ("3", "Koti ja keittiö", "03.02", "Keittiötuotteet", "03.02.03", "Muut keittiötuotteet"),
    "03.03.03": ("3", "Koti ja keittiö", "03.03", "Kodintekstiilit", "03.03.03", "Pyyhkeet ja laudeliinat"),
    "04.01.02": ("4", "Toimisto, painotuotteet ja pakkaukset", "04.01", "Toimistotuotteet", "04.01.02", "Muistikirjat"),
    "04.04.02": ("4", "Toimisto, painotuotteet ja pakkaukset", "04.04", "Painotuotteet ja merkit", "04.04.02", "Julisteet"),
    "05.01.01": ("5", "Laukut ja matkatavarat", "05.01", "Kassit", "05.01.01", "Muut kassit"),
    "05.03.02": ("5", "Laukut ja matkatavarat", "05.03", "Laukut", "05.03.02", "Muut laukut"),
    "05.05.01": ("5", "Laukut ja matkatavarat", "05.05", "Reput", "05.05.01", "Muut reput"),
    "08.02.01": ("8", "Korut, kellot ja aurinkolasit", "08.02", "Silmälasit ja aurinkolasit", "08.02.01", "Muut silmälasit ja aurinkolasit"),
    "10.03.01": ("10", "Makeiset ja elintarvikkeet", "10.03", "Makeiset", "10.03.01", "Muut makeiset"),
}

ALL_CATEGORIES = {"Sales promotion", "Liikelahjat", "HR-lahjat", "Kevyt työvaatetus", "Raskas työvaatetus", "Suojaimet", ""}
PROMO_CATEGORIES = {"Sales promotion"}
GIFT_CATEGORIES = {"Sales promotion", "Liikelahjat", "HR-lahjat", ""}
CLOTHING_CATEGORIES = {"Sales promotion", "Liikelahjat", "HR-lahjat", "Kevyt työvaatetus", "Raskas työvaatetus", ""}
WORKWEAR_CATEGORIES = {"Kevyt työvaatetus", "Raskas työvaatetus", "Suojaimet"}


RULES = [
    ("sales_promo_bar_mat_drink_accessory", PROMO_CATEGORIES, r"\b(baarimatto|lasinalunen|sinkkiämpäri)\b", "02.02.01"),
    ("sales_promo_table_tent", PROMO_CATEGORIES, r"\b(pöytäkolmio|poytakolmio|table\s*tent)\b", "02.04.02"),
    ("sales_promo_flag_banner", PROMO_CATEGORIES, r"\b(lippusiima|banderolli|banneri|viiri)\b", "02.05.01"),
    ("sales_promo_pos_material", PROMO_CATEGORIES, r"\b(pos)\b", "02.04.02"),
    ("poster_print", ALL_CATEGORIES, r"\b(juliste|poster)\b", "04.04.02"),
    ("towel_textile", ALL_CATEGORIES, r"\b(käsipyyhe|kasipyyhe|kylpypyyhe|pyyhe|laudeliina)\b", "03.03.03"),
    ("sunglasses", ALL_CATEGORIES, r"\b(aurinkolasit|sunglasses)\b", "08.02.01"),
    ("pen", GIFT_CATEGORIES, r"\b(kuulakärkikynä|kuulakarkikyna|kynä|kyna|pen)\b", "02.01.04"),
    ("notebook", GIFT_CATEGORIES, r"\b(muistikirja|vihko|notebook)\b", "04.01.02"),
    ("mug", GIFT_CATEGORIES, r"\b(muki|mukit|mug)\b", "03.01.03"),
    ("bottle", GIFT_CATEGORIES, r"\b(juomapullo|urheilupullo|vesipullo|termos|termospullo|pullo|bottle)\b", "03.01.05"),
    ("backpack", GIFT_CATEGORIES, r"\b(reppu|backpack)\b", "05.05.01"),
    ("bag", GIFT_CATEGORIES, r"\b(gym\s*bag|ostoskassi|kassi|bag)\b", "05.01.01"),
    ("shoulder_bag", GIFT_CATEGORIES, r"\b(olkalaukku|shoulder\s*bag)\b", "05.03.02"),
    ("cast_iron_pot", GIFT_CATEGORIES, r"\b(valurautapata|pata|paistinpannu)\b", "03.02.03"),
    ("candy", GIFT_CATEGORIES, r"\b(makeinen|makeiset|suklaa|karkki|candy|chocolate)\b", "10.03.01"),
    ("hoodie", CLOTHING_CATEGORIES, r"\b(vetoketjuhuppari|huppari|hoodie|hoody|college)\b", "01.04.01"),
    ("polo", CLOTHING_CATEGORIES, r"\b(pikee|pikeepaita|polo)\b", "01.04.05"),
    ("jacket", CLOTHING_CATEGORIES, r"\b(softshell|fleece|kurssitakki|takki|jacket)\b", "01.05.03"),
    ("trousers", WORKWEAR_CATEGORIES, r"\b(housut|shortsit|pants|trousers|shorts)\b", "01.02.01"),
    ("vest", WORKWEAR_CATEGORIES, r"\b(liivi|vest)\b", "01.05.01"),
    ("socks", CLOTHING_CATEGORIES, r"\b(villasukat|sukat|sock|socks)\b", "01.01.07"),
    ("gloves", WORKWEAR_CATEGORIES | {"Liikelahjat"}, r"\b(käsine|käsineet|kasine|kasineet|glove|gloves)\b", "01.01.03"),
    ("footwear", WORKWEAR_CATEGORIES, r"\b(jalkine|jalkineet|kenkä|kengät|shoe|shoes)\b", "01.01.02"),
]


def normalize_category(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(CSV_PATH)

    df = pd.read_csv(CSV_PATH, dtype=str, encoding="utf-8-sig", keep_default_na=False)
    missing_before = df["product_group_l3_code"].str.strip().eq("")

    backup_path = OUTPUTS / f"{CSV_PATH.stem}.backup_before_category_guided_{datetime.now():%Y%m%d_%H%M%S}.csv"
    shutil.copy2(CSV_PATH, backup_path)

    category = df["category"].map(normalize_category)
    name = df["name"].fillna("").astype(str).str.lower()
    unmatched = missing_before.copy()

    audit_rows = []
    updated_indices: list[int] = []

    for rule_name, allowed_categories, pattern, group_code in RULES:
        group = GROUPS[group_code]
        mask = unmatched & category.isin(allowed_categories) & name.str.contains(pattern, regex=True, na=False)
        indices = df.index[mask].tolist()
        if not indices:
            continue

        (
            df.loc[mask, "product_group_l1_code"],
            df.loc[mask, "product_group_l1_name"],
            df.loc[mask, "product_group_l2_code"],
            df.loc[mask, "product_group_l2_name"],
            df.loc[mask, "product_group_l3_code"],
            df.loc[mask, "product_group_l3_name"],
        ) = group
        df.loc[mask, "product_group_match_method"] = f"category_guided_name_rule:{rule_name}"

        audit_rows.append(
            {
                "rule": rule_name,
                "pattern": pattern,
                "allowed_categories": ", ".join(sorted(c or "(blank)" for c in allowed_categories)),
                "product_group_l3_code": group[4],
                "product_group_l3_name": group[5],
                "rows_updated": len(indices),
            }
        )
        updated_indices.extend(indices)
        unmatched = unmatched & ~mask

    missing_after = df["product_group_l3_code"].str.strip().eq("")
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")

    audit = pd.DataFrame(audit_rows).sort_values("rows_updated", ascending=False)
    audit_path = OUTPUTS / "category_guided_name_update_audit.csv"
    audit.to_csv(audit_path, index=False, encoding="utf-8-sig")

    rows_path = OUTPUTS / "category_guided_name_update_rows.csv"
    df.loc[
        updated_indices,
        [
            "id",
            "category",
            "productcode",
            "name",
            "product_group_l1_code",
            "product_group_l1_name",
            "product_group_l2_code",
            "product_group_l2_name",
            "product_group_l3_code",
            "product_group_l3_name",
            "product_group_match_method",
            "sales",
            "amount",
            "accountid",
        ],
    ].to_csv(rows_path, index=False, encoding="utf-8-sig")

    summary = {
        "source_csv": str(CSV_PATH),
        "backup_csv": str(backup_path),
        "audit_csv": str(audit_path),
        "updated_rows_csv": str(rows_path),
        "rows_total": int(len(df)),
        "missing_before": int(missing_before.sum()),
        "rows_updated": int(len(updated_indices)),
        "missing_after": int(missing_after.sum()),
        "rules_with_hits": int(len(audit_rows)),
        "updated_by_l3": (
            df.loc[updated_indices]
            .groupby(["product_group_l3_code", "product_group_l3_name"])
            .size()
            .sort_values(ascending=False)
            .reset_index(name="rows")
            .to_dict(orient="records")
        ),
        "updated_by_category": (
            df.loc[updated_indices]
            .groupby("category", dropna=False)
            .size()
            .sort_values(ascending=False)
            .reset_index(name="rows")
            .to_dict(orient="records")
        ),
    }
    summary_path = OUTPUTS / "category_guided_name_update_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
