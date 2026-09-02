import json
import os
import re
import shutil
from datetime import datetime

import pandas as pd


BASE_DIR = r"C:\Users\TommiHavukainen\OneDrive - Unikie Oy\Customer\Innoflame"
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
CSV_PATH = os.path.join(
    OUTPUT_DIR, "Innoflame_merged_sales_csv_source_with_L1_L2_L3_delivery_handling.csv"
)


def norm(value):
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = text.replace("-", " ")
    text = re.sub(r"(?<=\d)\s*x\s*(?=\d)", "x", text)
    text = re.sub(r"(?<=\d)\s+cm\b", "cm", text)
    text = re.sub(r"\s+", " ", text)
    return text


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_csv = CSV_PATH.replace(
        ".csv", f".backup_before_luhta_aalto_towel_group_{timestamp}.csv"
    )
    audit_csv = os.path.join(OUTPUT_DIR, "luhta_aalto_towel_group_update_rows.csv")
    audit_json = os.path.join(OUTPUT_DIR, "luhta_aalto_towel_group_update_audit.json")

    shutil.copy2(CSV_PATH, backup_csv)
    df = pd.read_csv(CSV_PATH, low_memory=False)

    normalized_name = df["name"].map(norm)
    target_mask = normalized_name.str.contains("luhta aalto kylpypyyhe", na=False)
    target_mask &= normalized_name.str.contains("70x140cm", na=False)

    before_rows = df.loc[target_mask].copy()
    before_missing = (
        before_rows["product_group_l3_code"].isna()
        | (before_rows["product_group_l3_code"].astype(str).str.strip() == "")
        | before_rows["product_group_l3_name"].isna()
        | (before_rows["product_group_l3_name"].astype(str).str.strip() == "")
    )

    df.loc[target_mask, "product_group_l1_code"] = 3
    df.loc[target_mask, "product_group_l1_name"] = "Koti ja keittiö"
    df.loc[target_mask, "product_group_l2_code"] = "3.03"
    df.loc[target_mask, "product_group_l2_name"] = "Kodintekstiilit"
    df.loc[target_mask, "product_group_l3_code"] = "03.03.03"
    df.loc[target_mask, "product_group_l3_name"] = "Pyyhkeet ja laudeliinat"
    df.loc[target_mask, "product_group_match_method"] = "manual_luhta_aalto_towel_rule"

    updated_rows = df.loc[target_mask].copy()
    audit_cols = [
        "source_file",
        "id",
        "category",
        "productcode",
        "optioncode",
        "name",
        "sales",
        "amount",
        "order",
        "reference",
        "sold_at",
        "accountid",
        "product_group_l1_code",
        "product_group_l1_name",
        "product_group_l2_code",
        "product_group_l2_name",
        "product_group_l3_code",
        "product_group_l3_name",
        "product_group_match_method",
    ]
    updated_rows[audit_cols].to_csv(audit_csv, index=False, encoding="utf-8-sig")
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")

    missing_after_all = (
        df["product_group_l3_code"].isna()
        | (df["product_group_l3_code"].astype(str).str.strip() == "")
        | df["product_group_l3_name"].isna()
        | (df["product_group_l3_name"].astype(str).str.strip() == "")
    )
    summary = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "source_csv": CSV_PATH,
        "backup_csv": backup_csv,
        "target_name_rule": "Luhta Aalto kylpypyyhe + 70x140cm",
        "matched_rows": int(target_mask.sum()),
        "matched_rows_missing_group_before": int(before_missing.sum()),
        "matched_sales_eur": float(
            pd.to_numeric(before_rows["sales"], errors="coerce").fillna(0).sum()
        ),
        "assigned_group": {
            "product_group_l1_code": 3,
            "product_group_l1_name": "Koti ja keittiö",
            "product_group_l2_code": "3.03",
            "product_group_l2_name": "Kodintekstiilit",
            "product_group_l3_code": "03.03.03",
            "product_group_l3_name": "Pyyhkeet ja laudeliinat",
        },
        "rows_missing_l3_after_all": int(missing_after_all.sum()),
        "audit_rows_csv": audit_csv,
    }
    with open(audit_json, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
