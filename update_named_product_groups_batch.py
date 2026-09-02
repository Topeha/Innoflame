import json
import os
import shutil
from datetime import datetime

import pandas as pd


BASE_DIR = r"C:\Users\TommiHavukainen\OneDrive - Unikie Oy\Customer\Innoflame"
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
CSV_PATH = os.path.join(
    OUTPUT_DIR, "Innoflame_merged_sales_csv_source_with_L1_L2_L3_delivery_handling.csv"
)

NAME_RULES = {
    "e-Lahjakortti Pancho Villa 50 €": {
        "product_group_l1_code": "6",
        "product_group_l1_name": "Lahjakortit ja pääsyliput",
        "product_group_l2_code": "06.02",
        "product_group_l2_name": "Lahjakortit ja pääsyliput",
        "product_group_l3_code": "06.02.01",
        "product_group_l3_name": "Lahjakortit ja pääsyliput",
    },
    "e-Lahjakortti Pancho Villa 50 �": {
        "product_group_l1_code": "6",
        "product_group_l1_name": "Lahjakortit ja pääsyliput",
        "product_group_l2_code": "06.02",
        "product_group_l2_name": "Lahjakortit ja pääsyliput",
        "product_group_l3_code": "06.02.01",
        "product_group_l3_name": "Lahjakortit ja pääsyliput",
    },
    "Nike Academy Woven -kurssitakki": {
        "product_group_l1_code": "1",
        "product_group_l1_name": "Vaatteet",
        "product_group_l2_code": "01.05",
        "product_group_l2_name": "Takit ja liivit",
        "product_group_l3_code": "01.05.03",
        "product_group_l3_name": "Takit",
    },
    "Polar Unite fitnesskello": {
        "product_group_l1_code": "8",
        "product_group_l1_name": "Korut, kellot ja aurinkolasit",
        "product_group_l2_code": "08.01",
        "product_group_l2_name": "Korut ja kellot",
        "product_group_l3_code": "08.01.01",
        "product_group_l3_name": "Muut korut ja kellot",
    },
}


def has_group(df):
    return (
        df["product_group_l3_code"].notna()
        & (df["product_group_l3_code"].astype(str).str.strip() != "")
        & df["product_group_l3_name"].notna()
        & (df["product_group_l3_name"].astype(str).str.strip() != "")
    )


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_csv = CSV_PATH.replace(
        ".csv", f".backup_before_named_product_groups_{timestamp}.csv"
    )
    audit_csv = os.path.join(OUTPUT_DIR, "named_product_groups_batch_update_rows.csv")
    audit_json = os.path.join(OUTPUT_DIR, "named_product_groups_batch_update_audit.json")

    shutil.copy2(CSV_PATH, backup_csv)
    df = pd.read_csv(CSV_PATH, low_memory=False)

    masks = []
    for name, group in NAME_RULES.items():
        mask = df["name"].eq(name)
        if not mask.any():
            continue
        masks.append(mask)
        for col, value in group.items():
            df.loc[mask, col] = value
        df.loc[mask, "product_group_match_method"] = "manual_named_product_rule"

    if masks:
        combined_mask = masks[0].copy()
        for mask in masks[1:]:
            combined_mask |= mask
    else:
        combined_mask = pd.Series(False, index=df.index)

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
    changed = df.loc[combined_mask].copy()
    changed[audit_cols].to_csv(audit_csv, index=False, encoding="utf-8-sig")
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")

    missing_l3 = ~has_group(df)
    changed["sales_num"] = pd.to_numeric(changed["sales"], errors="coerce").fillna(0)
    summary = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "source_csv": CSV_PATH,
        "backup_csv": backup_csv,
        "matched_rows": int(len(changed)),
        "rows_by_name": {k: int(v) for k, v in changed.groupby("name").size().to_dict().items()},
        "sales_by_name_eur": {
            k: round(float(v), 2)
            for k, v in changed.groupby("name")["sales_num"].sum().to_dict().items()
        },
        "rows_missing_l3_after_all": int(missing_l3.sum()),
        "audit_rows_csv": audit_csv,
    }
    with open(audit_json, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
