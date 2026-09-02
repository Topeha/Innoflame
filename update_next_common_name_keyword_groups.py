import json
import os
import re
import shutil
from collections import Counter
from datetime import datetime

import pandas as pd


BASE_DIR = r"C:\Users\TommiHavukainen\OneDrive - Unikie Oy\Customer\Innoflame"
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
CSV_PATH = os.path.join(
    OUTPUT_DIR, "Innoflame_merged_sales_csv_source_with_L1_L2_L3_delivery_handling.csv"
)

GROUPS = {
    "gift_card": ("6", "Lahjakortit ja pääsyliput", "06.02", "Lahjakortit ja pääsyliput", "06.02.01", "Lahjakortit ja pääsyliput"),
    "tshirt": ("1", "Vaatteet", "01.04", "Paidat ja yläosat", "01.04.06", "T-paidat"),
    "polo": ("1", "Vaatteet", "01.04", "Paidat ja yläosat", "01.04.05", "Pikeepaidat"),
    "shirt": ("1", "Vaatteet", "01.04", "Paidat ja yläosat", "01.04.02", "Kauluspaidat"),
    "jacket": ("1", "Vaatteet", "01.05", "Takit ja liivit", "01.05.03", "Takit"),
    "cap": ("1", "Vaatteet", "01.01", "Asusteet", "01.01.04", "Lippalakit"),
    "hat": ("1", "Vaatteet", "01.01", "Asusteet", "01.01.05", "Muut asusteet"),
    "cooler_bag": ("5", "Laukut ja matkatavarat", "05.02", "Reput", "05.02.01", "Muut kylmälaukut"),
    "drink_cooler": ("2", "Promootio- ja tapahtumatuotteet", "02.02", "Juomatarvikkeet", "02.02.01", "Muut juomatarvikkeet"),
    "note_card": ("4", "Toimisto, painotuotteet ja pakkaukset", "04.04", "Painotuotteet", "04.04.03", "Kortit ja julkaisut"),
}


def has_group(df):
    return (
        df["product_group_l3_code"].notna()
        & (df["product_group_l3_code"].astype(str).str.strip() != "")
        & df["product_group_l3_name"].notna()
        & (df["product_group_l3_name"].astype(str).str.strip() != "")
    )


def normalize(value):
    if pd.isna(value):
        return ""
    text = str(value).lower()
    text = text.replace("-", " ")
    text = re.sub(r"(?<=\d)\s*x\s*(?=\d)", "x", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def contains_word(text, word):
    return re.search(r"(?<![a-zåäö])" + re.escape(word) + r"(?![a-zåäö])", text) is not None


def classify_name(name):
    text = normalize(name)

    if "lahjakortti" in text or "alennuskoodi" in text:
        return "lahjakortti/alennuskoodi", GROUPS["gift_card"]

    if "saatekortti" in text or contains_word(text, "note"):
        return "saatekortti/note", GROUPS["note_card"]

    if "kylmälaukku" in text or "kylmalaukku" in text:
        return "kylmälaukku", GROUPS["cooler_bag"]

    if "cooleri" in text:
        return "cooleri", GROUPS["drink_cooler"]

    if "jacket" in text:
        return "jacket", GROUPS["jacket"]

    if "lippis" in text:
        return "lippis", GROUPS["cap"]

    if "hattu" in text:
        return "hattu", GROUPS["hat"]

    if "t paita" in text or "t shirt" in text or "tee shirt" in text or "fanipaita" in text:
        return "t-paita/t-shirt/fanipaita", GROUPS["tshirt"]

    if "pikeepaita" in text or contains_word(text, "polo"):
        return "pikeepaita/polo", GROUPS["polo"]

    if "kauluspaita" in text or contains_word(text, "shirt"):
        return "kauluspaita/shirt", GROUPS["shirt"]

    if contains_word(text, "paita"):
        return "paita", GROUPS["tshirt"]

    return "", None


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_csv = CSV_PATH.replace(
        ".csv", f".backup_before_common_keyword_round_{timestamp}.csv"
    )
    audit_csv = os.path.join(OUTPUT_DIR, "common_keyword_round_update_rows.csv")
    audit_json = os.path.join(OUTPUT_DIR, "common_keyword_round_update_audit.json")

    shutil.copy2(CSV_PATH, backup_csv)
    df = pd.read_csv(CSV_PATH, low_memory=False)
    missing_before = ~has_group(df)

    audit_rows = []
    keyword_counts = Counter()
    group_counts = Counter()

    for idx in df.index[missing_before]:
        keyword, group = classify_name(df.at[idx, "name"])
        if group is None:
            continue
        for col, value in zip(
            [
                "product_group_l1_code",
                "product_group_l1_name",
                "product_group_l2_code",
                "product_group_l2_name",
                "product_group_l3_code",
                "product_group_l3_name",
            ],
            group,
        ):
            df.at[idx, col] = value
        df.at[idx, "product_group_match_method"] = "manual_common_keyword_rule"
        keyword_counts[keyword] += 1
        group_counts[group[5]] += 1
        audit_rows.append(
            {
                "csv_row_number": int(idx) + 2,
                "matched_keyword": keyword,
                "source_file": df.at[idx, "source_file"],
                "id": df.at[idx, "id"],
                "category": df.at[idx, "category"],
                "productcode": df.at[idx, "productcode"],
                "optioncode": df.at[idx, "optioncode"],
                "name": df.at[idx, "name"],
                "sales": df.at[idx, "sales"],
                "reference": df.at[idx, "reference"],
                "product_group_l1_code": group[0],
                "product_group_l1_name": group[1],
                "product_group_l2_code": group[2],
                "product_group_l2_name": group[3],
                "product_group_l3_code": group[4],
                "product_group_l3_name": group[5],
            }
        )

    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
    pd.DataFrame(audit_rows).to_csv(audit_csv, index=False, encoding="utf-8-sig")

    missing_after = ~has_group(df)
    audit_df = pd.DataFrame(audit_rows)
    updated_sales = 0.0
    if not audit_df.empty:
        updated_sales = float(pd.to_numeric(audit_df["sales"], errors="coerce").fillna(0).sum())

    summary = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "source_csv": CSV_PATH,
        "backup_csv": backup_csv,
        "updated_rows": len(audit_rows),
        "missing_group_rows_before": int(missing_before.sum()),
        "missing_group_rows_after": int(missing_after.sum()),
        "updated_sales_eur": updated_sales,
        "rows_by_keyword": dict(keyword_counts.most_common()),
        "rows_by_group": dict(group_counts.most_common()),
        "audit_rows_csv": audit_csv,
    }
    with open(audit_json, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
