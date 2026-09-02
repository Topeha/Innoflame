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
TARGET_NAMES = {"Express processing", "Pick & pack"}
GROUP = {
    "product_group_l1_code": "15",
    "product_group_l1_name": "Toimitus- ja käsittelykulu",
    "product_group_l2_code": "15.01",
    "product_group_l2_name": "Toimitus- ja käsittelykulu",
    "product_group_l3_code": "15.01.01",
    "product_group_l3_name": "Toimitus- ja käsittelykulu",
}


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_csv = CSV_PATH.replace(
        ".csv", f".backup_before_express_pick_pack_group_{timestamp}.csv"
    )
    audit_csv = os.path.join(OUTPUT_DIR, "express_pick_pack_group_update_rows.csv")
    audit_json = os.path.join(OUTPUT_DIR, "express_pick_pack_group_update_audit.json")

    shutil.copy2(CSV_PATH, backup_csv)
    df = pd.read_csv(CSV_PATH, low_memory=False)
    mask = df["name"].isin(TARGET_NAMES)
    before = df.loc[mask].copy()

    for col, value in GROUP.items():
        df.loc[mask, col] = value
    df.loc[mask, "product_group_match_method"] = "manual_express_pick_pack_rule"

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
    df.loc[mask, audit_cols].to_csv(audit_csv, index=False, encoding="utf-8-sig")
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")

    missing_l3 = (
        df["product_group_l3_code"].isna()
        | (df["product_group_l3_code"].astype(str).str.strip() == "")
        | df["product_group_l3_name"].isna()
        | (df["product_group_l3_name"].astype(str).str.strip() == "")
    )
    summary = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "source_csv": CSV_PATH,
        "backup_csv": backup_csv,
        "matched_rows": int(mask.sum()),
        "rows_by_name": {k: int(v) for k, v in before.groupby("name").size().to_dict().items()},
        "matched_sales_eur": float(pd.to_numeric(before["sales"], errors="coerce").fillna(0).sum()),
        "assigned_group": GROUP,
        "rows_missing_l3_after_all": int(missing_l3.sum()),
        "audit_rows_csv": audit_csv,
    }
    with open(audit_json, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
