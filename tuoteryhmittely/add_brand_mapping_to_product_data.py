from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parent
BRAND_MAPPING_XLSX = ROOT / "product_master_enrichment" / "Brand mapping.xlsx"
TARGET_DIR = ROOT / "product_master_enrichment" / "final_product_grouping"
TARGET_CSV = TARGET_DIR / "products_product_group_tree_final.csv"
TARGET_XLSX = TARGET_DIR / "products_product_group_tree_final.xlsx"
REPORT_CSV = TARGET_DIR / "product_brand_mapping_report.csv"
SUMMARY_JSON = TARGET_DIR / "product_brand_mapping_summary.json"


def normalize_id(value: Any) -> str:
    if pd.isna(value):
        return ""
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.notna(number):
        return str(int(number))
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def backup_file(path: Path, stamp: str) -> Path | None:
    if not path.exists():
        return None
    backup = path.with_name(f"{path.stem}.backup_before_brand_mapping_{stamp}{path.suffix}")
    shutil.copy2(path, backup)
    return backup


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_csv = backup_file(TARGET_CSV, stamp)
    backup_xlsx = backup_file(TARGET_XLSX, stamp)

    target = pd.read_csv(TARGET_CSV)
    brands = pd.read_excel(BRAND_MAPPING_XLSX)

    required = {"Brand ID", "Brand name", "Website"}
    missing = required.difference(brands.columns)
    if missing:
        raise KeyError(f"Brand mapping is missing columns: {sorted(missing)}")
    if "brandiid" not in target.columns:
        raise KeyError("Target data is missing brandiid column")

    brands = brands.copy()
    brands["_brand_id_key"] = brands["Brand ID"].map(normalize_id)
    brands = brands[brands["_brand_id_key"] != ""].drop_duplicates("_brand_id_key", keep="first")

    brand_lookup = brands.set_index("_brand_id_key")[["Brand name", "Website"]]
    target = target.copy()
    target["_brand_id_key"] = target["brandiid"].map(normalize_id)

    if "brand_name" in target.columns:
        target = target.drop(columns=["brand_name"])
    if "brand_website" in target.columns:
        target = target.drop(columns=["brand_website"])

    target = target.merge(brand_lookup, how="left", left_on="_brand_id_key", right_index=True)
    target = target.rename(columns={"Brand name": "brand_name", "Website": "brand_website"})

    target.loc[target["_brand_id_key"].isin({"", "0"}), ["brand_name", "brand_website"]] = ""

    report_mask = target["brand_name"].notna() & (target["brand_name"].astype(str).str.strip() != "")
    report_cols = ["product_id", "sku", "brandiid", "brand_name", "brand_website", "product_name"]
    report = target.loc[report_mask, [col for col in report_cols if col in target.columns]].copy()

    unmapped_nonzero = sorted(
        key
        for key in target.loc[~target["_brand_id_key"].isin({"", "0"}), "_brand_id_key"].unique()
        if key not in set(brand_lookup.index)
    )

    target = target.drop(columns=["_brand_id_key"])
    target.to_csv(TARGET_CSV, index=False, encoding="utf-8-sig")
    target.to_excel(TARGET_XLSX, index=False)
    report.to_csv(REPORT_CSV, index=False, encoding="utf-8-sig")

    summary = {
        "brand_mapping_file": str(BRAND_MAPPING_XLSX),
        "target_csv": str(TARGET_CSV),
        "target_xlsx": str(TARGET_XLSX),
        "backup_csv": str(backup_csv) if backup_csv else None,
        "backup_xlsx": str(backup_xlsx) if backup_xlsx else None,
        "brand_mapping_rows": int(len(brands)),
        "target_rows": int(len(target)),
        "products_with_nonzero_brandid": int((target["brandiid"].map(normalize_id) != "0").sum()),
        "products_with_brand_name": int(report_mask.sum()),
        "unique_brand_names_in_products": int(target["brand_name"].dropna().replace("", pd.NA).dropna().nunique()),
        "unmapped_nonzero_brand_ids": unmapped_nonzero,
        "report_csv": str(REPORT_CSV),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
