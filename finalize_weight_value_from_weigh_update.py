from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
TARGET_DIR = ROOT / "product_master_enrichment" / "final_product_grouping"
TARGET_CSV = TARGET_DIR / "products_product_group_tree_final.csv"
TARGET_XLSX = TARGET_DIR / "products_product_group_tree_final.xlsx"
REPORT_CSV = TARGET_DIR / "product_weight_value_from_weigh_report.csv"
SUMMARY_JSON = TARGET_DIR / "product_weight_value_from_weigh_summary.json"


def latest_backup_csv() -> Path:
    backups = sorted(
        TARGET_DIR.glob("products_product_group_tree_final.backup_before_weight_value_from_weigh_*.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not backups:
        raise FileNotFoundError("No weight_value_from_weigh backup CSV found")
    return backups[0]


def main() -> None:
    current = pd.read_csv(TARGET_CSV)
    before_path = latest_backup_csv()
    before = pd.read_csv(before_path)

    key_cols = ["product_id", "sku"]
    before_small = before[key_cols + ["weigh", "weight_value", "weight_unit", "product_name"]].rename(
        columns={
            "weigh": "old_weigh",
            "weight_value": "old_weight_value",
            "weight_unit": "old_weight_unit",
            "product_name": "old_product_name",
        }
    )
    current_small = current[key_cols + ["weigh", "weight_value", "weight_unit", "product_name"]].rename(
        columns={
            "weight_value": "new_weight_value",
            "weight_unit": "new_weight_unit",
        }
    )
    report = current_small.merge(before_small, on=key_cols, how="left")
    updated = (
        report["weigh"].fillna(0).astype(float).ne(0)
        & report["new_weight_value"].fillna(-1).astype(float).eq(report["weigh"].astype(float))
        & report["new_weight_unit"].fillna("").eq("g")
    )
    report = report.loc[
        updated,
        [
            "product_id",
            "sku",
            "weigh",
            "old_weight_value",
            "old_weight_unit",
            "new_weight_value",
            "new_weight_unit",
            "product_name",
        ],
    ]
    report.to_csv(REPORT_CSV, index=False, encoding="utf-8-sig")

    xlsx_path = TARGET_XLSX
    xlsx_write_status = "updated_original"
    try:
        current.to_excel(TARGET_XLSX, index=False)
    except PermissionError:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        xlsx_path = TARGET_DIR / f"products_product_group_tree_final_weight_value_updated_{stamp}.xlsx"
        current.to_excel(xlsx_path, index=False)
        xlsx_write_status = "original_locked_saved_as_new_file"

    weigh_numeric = pd.to_numeric(current["weigh"], errors="coerce").fillna(0)
    summary = {
        "target_csv": str(TARGET_CSV),
        "target_xlsx": str(xlsx_path),
        "xlsx_write_status": xlsx_write_status,
        "backup_csv_used_for_report": str(before_path),
        "target_rows": int(len(current)),
        "rows_with_nonzero_weigh": int(weigh_numeric.ne(0).sum()),
        "rows_not_updated_because_weigh_zero_or_missing": int(weigh_numeric.eq(0).sum()),
        "updated_report_rows": int(len(report)),
        "weight_value_missing_after": int(current["weight_value"].isna().sum()),
        "weight_value_nonmissing_after": int(current["weight_value"].notna().sum()),
        "report_csv": str(REPORT_CSV),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
