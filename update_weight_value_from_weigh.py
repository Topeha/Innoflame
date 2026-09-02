from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parent
TARGET_DIR = ROOT / "product_master_enrichment" / "final_product_grouping"
TARGET_CSV = TARGET_DIR / "products_product_group_tree_final.csv"
TARGET_XLSX = TARGET_DIR / "products_product_group_tree_final.xlsx"
REPORT_CSV = TARGET_DIR / "product_weight_value_from_weigh_report.csv"
SUMMARY_JSON = TARGET_DIR / "product_weight_value_from_weigh_summary.json"


def backup_file(path: Path, stamp: str) -> Path | None:
    if not path.exists():
        return None
    backup = path.with_name(f"{path.stem}.backup_before_weight_value_from_weigh_{stamp}{path.suffix}")
    shutil.copy2(path, backup)
    return backup


def as_number(value: Any) -> float | None:
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip().replace(",", ".")
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return None
    return float(number)


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_csv = backup_file(TARGET_CSV, stamp)
    backup_xlsx = backup_file(TARGET_XLSX, stamp)

    df = pd.read_csv(TARGET_CSV)
    for column in ["weigh", "weight_value", "weight_unit"]:
        if column not in df.columns:
            raise KeyError(f"Target data is missing required column: {column}")

    weigh_numeric = df["weigh"].map(as_number)
    update_mask = weigh_numeric.notna() & (weigh_numeric != 0)

    before_weight_value_missing = int(df["weight_value"].isna().sum())
    before_weight_value_nonmissing = int(df["weight_value"].notna().sum())

    report = df.loc[update_mask, ["product_id", "sku", "weigh", "weight_value", "weight_unit", "product_name"]].copy()
    report = report.rename(
        columns={
            "weight_value": "old_weight_value",
            "weight_unit": "old_weight_unit",
        }
    )
    report["new_weight_value"] = weigh_numeric.loc[update_mask].values
    report["new_weight_unit"] = "g"

    df.loc[update_mask, "weight_value"] = weigh_numeric.loc[update_mask].values
    df.loc[update_mask, "weight_unit"] = "g"

    after_weight_value_missing = int(df["weight_value"].isna().sum())
    after_weight_value_nonmissing = int(df["weight_value"].notna().sum())

    df.to_csv(TARGET_CSV, index=False, encoding="utf-8-sig")
    df.to_excel(TARGET_XLSX, index=False)
    report.to_csv(REPORT_CSV, index=False, encoding="utf-8-sig")

    summary = {
        "target_csv": str(TARGET_CSV),
        "target_xlsx": str(TARGET_XLSX),
        "backup_csv": str(backup_csv) if backup_csv else None,
        "backup_xlsx": str(backup_xlsx) if backup_xlsx else None,
        "target_rows": int(len(df)),
        "rows_with_nonzero_weigh": int(update_mask.sum()),
        "rows_not_updated_because_weigh_zero_or_missing": int((~update_mask).sum()),
        "weight_value_missing_before": before_weight_value_missing,
        "weight_value_nonmissing_before": before_weight_value_nonmissing,
        "weight_value_missing_after": after_weight_value_missing,
        "weight_value_nonmissing_after": after_weight_value_nonmissing,
        "report_csv": str(REPORT_CSV),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
