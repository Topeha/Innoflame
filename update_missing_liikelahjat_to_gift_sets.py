from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parent
OUTPUTS = BASE / "outputs"
CSV_PATH = OUTPUTS / "Innoflame_merged_sales_csv_source_with_L1_L2_L3_delivery_handling.csv"

GROUP = {
    "product_group_l1_code": "3",
    "product_group_l1_name": "Koti ja keittiö",
    "product_group_l2_code": "03.04",
    "product_group_l2_name": "Lahjasetit",
    "product_group_l3_code": "03.04.01",
    "product_group_l3_name": "Muut lahjasetit",
}


def main() -> None:
    df = pd.read_csv(CSV_PATH, dtype=str, encoding="utf-8-sig", keep_default_na=False)
    missing = df["product_group_l3_code"].str.strip().eq("")
    category = df["category"].str.strip().str.casefold()
    target = missing & category.isin({"liikelahjat", "liikelahja"})

    backup_path = OUTPUTS / f"{CSV_PATH.stem}.backup_before_liikelahjat_gift_sets_{datetime.now():%Y%m%d_%H%M%S}.csv"
    shutil.copy2(CSV_PATH, backup_path)

    for column, value in GROUP.items():
        df.loc[target, column] = value
    df.loc[target, "product_group_match_method"] = "manual_missing_liikelahjat_to_gift_sets_rule"
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")

    updated_rows_path = OUTPUTS / "missing_liikelahjat_to_gift_sets_update_rows.csv"
    df.loc[
        target,
        [
            "id",
            "status",
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
    ].to_csv(updated_rows_path, index=False, encoding="utf-8-sig")

    missing_after = df["product_group_l3_code"].str.strip().eq("")
    summary = {
        "source_csv": str(CSV_PATH.resolve()),
        "backup_csv": str(backup_path.resolve()),
        "updated_rows_csv": str(updated_rows_path.resolve()),
        "rows_total": int(len(df)),
        "missing_before": int(missing.sum()),
        "rows_updated": int(target.sum()),
        "missing_after": int(missing_after.sum()),
        "target_category_values": ["Liikelahjat", "Liikelahja"],
        "target_group": GROUP,
    }
    summary_path = OUTPUTS / "missing_liikelahjat_to_gift_sets_update_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
