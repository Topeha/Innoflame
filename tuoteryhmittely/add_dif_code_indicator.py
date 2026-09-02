from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "product_master_enrichment" / "final_product_grouping"
TARGET_FILES = [
    DATA_DIR / "products_product_group_tree_final.csv",
    DATA_DIR / "products_product_group_tree_final.xlsx",
    DATA_DIR / "products_product_group_tree_final_weight_value_updated_20260629_152451.xlsx",
    DATA_DIR / "products_product_group_tree_final_weight_value_updated_20260629_152451_web_enriched_20260629_154753.xlsx",
]
SUMMARY_JSON = DATA_DIR / "product_dif_code_indicator_summary.json"
NEW_COLUMN = "is_dif_code"


def backup_file(path: Path, stamp: str) -> Path:
    short_stem = path.stem[:80]
    backup = path.with_name(f"{short_stem}.backup_dif_{stamp}{path.suffix}")
    shutil.copy2(path, backup)
    return backup


def load_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path)
    raise ValueError(f"Unsupported file type: {path}")


def save_table(df: pd.DataFrame, path: Path, stamp: str) -> Path:
    if path.suffix.lower() == ".csv":
        df.to_csv(path, index=False, encoding="utf-8-sig")
        return path
    if path.suffix.lower() == ".xlsx":
        try:
            df.to_excel(path, index=False)
            return path
        except PermissionError:
            output = path.with_name(f"{path.stem[:80]}_dif_indicator_{stamp}{path.suffix}")
            df.to_excel(output, index=False)
            return output
    raise ValueError(f"Unsupported file type: {path}")


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = []
    for path in TARGET_FILES:
        if not path.exists():
            results.append({"file": str(path), "status": "missing"})
            continue
        df = load_table(path)
        if "code" not in df.columns:
            results.append({"file": str(path), "status": "missing_code_column", "rows": int(len(df))})
            continue
        backup = backup_file(path, stamp)
        df[NEW_COLUMN] = df["code"].fillna("").astype(str).str.startswith("DIF").astype(int)
        saved_path = save_table(df, path, stamp)
        results.append(
            {
                "file": str(path),
                "status": "updated",
                "saved_file": str(saved_path),
                "backup": str(backup),
                "rows": int(len(df)),
                "dif_rows": int(df[NEW_COLUMN].sum()),
            }
        )
    SUMMARY_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
