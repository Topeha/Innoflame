from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path


BASE = Path("product_master_enrichment/final_product_grouping")
OUT = Path("outputs/product_grouping_summary")

CURRENT_CSV = BASE / "products_product_group_tree_feedback_3level.csv"
CURRENT_XLSX = BASE / "products_product_group_tree_feedback_3level.xlsx"
FINAL_CSV = BASE / "Innoflame_tuoteryhmittely.csv"
FINAL_XLSX = BASE / "Innoflame_tuoteryhmittely.xlsx"
MANIFEST = BASE / "Innoflame_tuoteryhmittely_manifest.json"


DELETE_PATTERNS = [
    "products_product_group_tree_compact_supplier_enriched*",
    "products_product_group_tree_compact_workwear_under_clothing*",
    "products_product_group_tree_no_inventory_warehouse_category*",
    "products_product_group_tree_feedback_3level.backup_before_high_*",
    "product_group_l4_*",
    "product_group_no_inventory_warehouse_category_*",
    "product_group_other_improvement_*",
    "product_group_tree_compact_*",
    "inventory_workwear_top_level_move_report.csv",
    "*.inspect.ndjson",
]

KEEP = {
    CURRENT_CSV.name,
    CURRENT_XLSX.name,
    FINAL_CSV.name,
    FINAL_XLSX.name,
    MANIFEST.name,
    "product_group_feedback_3level_level_summary.csv",
    "product_group_feedback_3level_mapping_report.csv",
    "product_group_feedback_3level_summary.json",
    "high_confidence_suggestion_application_report.csv",
    "high_confidence_suggestion_application_summary.json",
}


def file_info(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size_bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def main() -> None:
    if not CURRENT_CSV.exists() or not CURRENT_XLSX.exists():
        raise FileNotFoundError("Current feedback_3level CSV/XLSX was not found.")

    shutil.copy2(CURRENT_CSV, FINAL_CSV)
    shutil.copy2(CURRENT_XLSX, FINAL_XLSX)

    deletion_candidates: dict[Path, str] = {}
    for pattern in DELETE_PATTERNS:
        for path in BASE.glob(pattern):
            if path.is_file() and path.name not in KEEP:
                deletion_candidates[path] = pattern

    deleted = []
    for path in sorted(deletion_candidates):
        deleted.append(
            {
                "path": str(path.resolve()),
                "size_bytes": path.stat().st_size,
                "matched_pattern": deletion_candidates[path],
            }
        )
        path.unlink()

    manifest = {
        "finalized_at": datetime.now().isoformat(timespec="seconds"),
        "final_files": [file_info(FINAL_CSV), file_info(FINAL_XLSX)],
        "working_files_kept": [file_info(CURRENT_CSV), file_info(CURRENT_XLSX)],
        "reports_kept": [
            file_info(BASE / name)
            for name in sorted(KEEP)
            if (BASE / name).exists() and name not in {CURRENT_CSV.name, CURRENT_XLSX.name, FINAL_CSV.name, FINAL_XLSX.name, MANIFEST.name}
        ],
        "summary_outputs_kept": [
            file_info(path)
            for path in sorted(OUT.glob("*"))
            if path.is_file()
        ],
        "deleted_previous_versions": deleted,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"final_files": manifest["final_files"], "deleted_count": len(deleted)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
