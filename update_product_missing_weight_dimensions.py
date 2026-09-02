from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parent
SOURCE_XLSX = ROOT / "product_master_enrichment" / "Kopio_Innoflame_found_products_with_logic_fi_selitetty_2.xlsx"
TARGET_DIR = ROOT / "product_master_enrichment" / "final_product_grouping"
TARGET_CSV = TARGET_DIR / "products_product_group_tree_final.csv"
TARGET_XLSX = TARGET_DIR / "products_product_group_tree_final.xlsx"
REPORT_CSV = TARGET_DIR / "product_weight_dimension_update_report.csv"
REPORT_JSON = TARGET_DIR / "product_weight_dimension_update_summary.json"


SOURCE_COLUMNS = {
    "product_id": "tuote_id",
    "sku": "tuotekoodi",
    "weight_g": "rikastettu_paino_g (rikastettu paino g)",
    "packsize": "rikastettu_pakkauskoko (rikastettu packsize)",
    "dim1": "mitta_arvo_1 (1. mitta)",
    "dim2": "mitta_arvo_2 (2. mitta)",
    "dim3": "mitta_arvo_3 (3. mitta)",
    "dim_unit": "mitta_yksikkö (mm/cm/m)",
    "dim_raw": "mitta_raaka_arvo (alkuperäinen mittateksti)",
    "weight_raw": "paino_raaka_arvo (alkuperäinen painoteksti)",
}


def is_missing(value: Any, zero_is_missing: bool = False) -> bool:
    if pd.isna(value):
        return True
    text = str(value).strip().lower()
    if text in {"", "nan", "none", "null"}:
        return True
    if zero_is_missing:
        numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        return pd.notna(numeric) and float(numeric) == 0.0
    return False


def as_number(value: Any) -> float | None:
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip().replace(",", ".")
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return None
    return float(number)


def normalize_key(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def dimension_to_cm(value: Any, unit: Any) -> float | None:
    number = as_number(value)
    if number is None:
        return None
    unit_text = "" if pd.isna(unit) else str(unit).strip().lower()
    if unit_text == "mm":
        return number / 10.0
    if unit_text == "cm":
        return number
    if unit_text == "m":
        return number * 100.0
    return None


def clean_packsize(value: Any) -> Any:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    if text.endswith(".0"):
        return text[:-2]
    return text


def backup_file(path: Path, stamp: str) -> Path | None:
    if not path.exists():
        return None
    backup = path.with_name(f"{path.stem}.backup_before_weight_dimension_update_{stamp}{path.suffix}")
    shutil.copy2(path, backup)
    return backup


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_csv = backup_file(TARGET_CSV, stamp)
    backup_xlsx = backup_file(TARGET_XLSX, stamp)

    source = pd.read_excel(SOURCE_XLSX, sheet_name="Data")
    target = pd.read_csv(TARGET_CSV)

    missing_columns = [col for col in SOURCE_COLUMNS.values() if col not in source.columns]
    if missing_columns:
        raise KeyError(f"Source file is missing expected columns: {missing_columns}")

    source = source.copy()
    source["_product_id_key"] = source[SOURCE_COLUMNS["product_id"]].map(normalize_key)
    source = source[source["_product_id_key"] != ""].drop_duplicates("_product_id_key", keep="first")
    source_lookup = source.set_index("_product_id_key")

    target = target.copy()
    before_missing = {
        "weigh_zero_or_missing": int(target["weigh"].map(lambda v: is_missing(v, zero_is_missing=True)).sum()),
        "weight_g_missing": int(target["weight_g"].map(is_missing).sum()),
        "packsize_missing": int(target["packsize"].map(is_missing).sum()),
        "width_value_missing": int(target["width_value"].map(is_missing).sum()),
        "length_value_missing": int(target["length_value"].map(is_missing).sum()),
        "depth_value_missing": int(target["depth_value"].map(is_missing).sum()),
    }

    updates: list[dict[str, Any]] = []
    counters = {
        "matched_rows": 0,
        "weigh_updated": 0,
        "weight_g_updated": 0,
        "packsize_updated": 0,
        "length_value_updated": 0,
        "width_value_updated": 0,
        "depth_value_updated": 0,
    }

    for idx, row in target.iterrows():
        product_id_key = normalize_key(row.get("product_id"))
        if product_id_key not in source_lookup.index:
            continue

        counters["matched_rows"] += 1
        source_row = source_lookup.loc[product_id_key]
        row_updates: dict[str, Any] = {
            "product_id": row.get("product_id"),
            "sku": row.get("sku"),
            "updated_fields": [],
        }

        source_weight = as_number(source_row[SOURCE_COLUMNS["weight_g"]])
        if source_weight is not None:
            if is_missing(target.at[idx, "weigh"], zero_is_missing=True):
                target.at[idx, "weigh"] = source_weight
                counters["weigh_updated"] += 1
                row_updates["updated_fields"].append("weigh")
            if is_missing(target.at[idx, "weight_g"]):
                target.at[idx, "weight_g"] = source_weight
                target.at[idx, "weight_unit"] = "g"
                counters["weight_g_updated"] += 1
                row_updates["updated_fields"].append("weight_g")

        source_packsize = clean_packsize(source_row[SOURCE_COLUMNS["packsize"]])
        if source_packsize and is_missing(target.at[idx, "packsize"]):
            target.at[idx, "packsize"] = source_packsize
            counters["packsize_updated"] += 1
            row_updates["updated_fields"].append("packsize")

        unit = source_row[SOURCE_COLUMNS["dim_unit"]]
        dim1 = dimension_to_cm(source_row[SOURCE_COLUMNS["dim1"]], unit)
        dim2 = dimension_to_cm(source_row[SOURCE_COLUMNS["dim2"]], unit)
        dim3 = dimension_to_cm(source_row[SOURCE_COLUMNS["dim3"]], unit)

        if dim1 is not None and is_missing(target.at[idx, "length_value"]):
            target.at[idx, "length_value"] = dim1
            target.at[idx, "length_unit"] = "cm"
            counters["length_value_updated"] += 1
            row_updates["updated_fields"].append("length_value")
        if dim2 is not None and is_missing(target.at[idx, "width_value"]):
            target.at[idx, "width_value"] = dim2
            target.at[idx, "width_unit"] = "cm"
            counters["width_value_updated"] += 1
            row_updates["updated_fields"].append("width_value")
        if dim3 is not None and is_missing(target.at[idx, "depth_value"]):
            target.at[idx, "depth_value"] = dim3
            target.at[idx, "depth_unit"] = "cm"
            counters["depth_value_updated"] += 1
            row_updates["updated_fields"].append("depth_value")

        if row_updates["updated_fields"]:
            row_updates["updated_fields"] = ", ".join(row_updates["updated_fields"])
            row_updates["source_weight_g"] = source_weight
            row_updates["source_packsize"] = source_packsize
            row_updates["source_dimension_raw"] = source_row[SOURCE_COLUMNS["dim_raw"]]
            row_updates["source_weight_raw"] = source_row[SOURCE_COLUMNS["weight_raw"]]
            updates.append(row_updates)

    after_missing = {
        "weigh_zero_or_missing": int(target["weigh"].map(lambda v: is_missing(v, zero_is_missing=True)).sum()),
        "weight_g_missing": int(target["weight_g"].map(is_missing).sum()),
        "packsize_missing": int(target["packsize"].map(is_missing).sum()),
        "width_value_missing": int(target["width_value"].map(is_missing).sum()),
        "length_value_missing": int(target["length_value"].map(is_missing).sum()),
        "depth_value_missing": int(target["depth_value"].map(is_missing).sum()),
    }

    target.to_csv(TARGET_CSV, index=False, encoding="utf-8-sig")
    target.to_excel(TARGET_XLSX, index=False)
    pd.DataFrame(updates).to_csv(REPORT_CSV, index=False, encoding="utf-8-sig")

    summary = {
        "source_file": str(SOURCE_XLSX),
        "target_csv": str(TARGET_CSV),
        "target_xlsx": str(TARGET_XLSX),
        "backup_csv": str(backup_csv) if backup_csv else None,
        "backup_xlsx": str(backup_xlsx) if backup_xlsx else None,
        "source_rows": int(len(source)),
        "target_rows": int(len(target)),
        "updated_rows": int(len(updates)),
        "counters": counters,
        "missing_before": before_missing,
        "missing_after": after_missing,
        "report_csv": str(REPORT_CSV),
    }
    REPORT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
