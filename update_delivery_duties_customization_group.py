from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parent
OUTPUTS = BASE / "outputs"
CSV_PATH = OUTPUTS / "Innoflame_merged_sales_csv_source_with_L1_L2_L3_delivery_handling.csv"

TARGET_NAMES = [
    "Leverans",
    "IMPORT EXPORT   DUTIES AND TAXES",
    "IMPORT EXPORT DUTIES AND TAXES",
    "Tuotteen mukauttaminen (peruskustannus)",
    "DUTIES & TAXES",
    "Duties and taxes",
]

TARGET_PATTERNS = [
    r"\bduties?\s*(?:&|and)?\s*tax(?:es|ies)?\b",
    r"\btax(?:es|ies)?\s*(?:&|and)\s*duties?\b",
    r"\bimport\s+export\s+duties?\b",
    r"\bduty\s+tax\s+paid\b",
    r"\bregulatory\s+charges\b",
    r"\bexport\s+(?:clearance|declaration)\b",
    r"\bfuel\s+surcharge\b",
    r"\bdemand\s+surcharge\b",
    r"\bbonded\s+storage\b",
    r"\bgogreen\s+plus\b",
    r"^import\s+export$",
    r"^export$",
]

GROUP = {
    "product_group_l1_code": "15",
    "product_group_l1_name": "Toimitus- ja käsittelykulu",
    "product_group_l2_code": "15.01",
    "product_group_l2_name": "Toimitus- ja käsittelykulu",
    "product_group_l3_code": "15.01.01",
    "product_group_l3_name": "Toimitus- ja käsittelykulu",
}


def normalize(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def main() -> None:
    df = pd.read_csv(CSV_PATH, dtype=str, encoding="utf-8-sig", keep_default_na=False)
    missing = df["product_group_l3_code"].str.strip().eq("")
    target_norms = {normalize(value) for value in TARGET_NAMES}
    name_norm = df["name"].map(normalize)

    exact_target = name_norm.isin(target_norms)
    pattern_target = pd.Series(False, index=df.index)
    for pattern in TARGET_PATTERNS:
        pattern_target = pattern_target | name_norm.str.contains(pattern, regex=True, na=False)
    update_mask = missing & (exact_target | pattern_target)

    backup_path = OUTPUTS / f"{CSV_PATH.stem}.backup_before_delivery_duties_customization_{datetime.now():%Y%m%d_%H%M%S}.csv"
    shutil.copy2(CSV_PATH, backup_path)

    for col, value in GROUP.items():
        df.loc[update_mask, col] = value
    df.loc[update_mask, "product_group_match_method"] = "manual_delivery_duties_customization_rule"
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")

    updated_rows_path = OUTPUTS / "delivery_duties_customization_update_rows.csv"
    df.loc[
        update_mask,
        [
            "id",
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

    audit_rows = []
    for target in TARGET_NAMES:
        target_mask = name_norm.eq(normalize(target))
        audit_rows.append(
            {
                "name": target,
                "rows_total": int(target_mask.sum()),
                "rows_missing_group_before": int((target_mask & missing).sum()),
                "rows_updated": int((target_mask & update_mask).sum()),
            }
        )
    for pattern in TARGET_PATTERNS:
        pattern_mask = name_norm.str.contains(pattern, regex=True, na=False)
        audit_rows.append(
            {
                "name": f"regex:{pattern}",
                "rows_total": int(pattern_mask.sum()),
                "rows_missing_group_before": int((pattern_mask & missing).sum()),
                "rows_updated": int((pattern_mask & update_mask).sum()),
            }
        )

    audit_path = OUTPUTS / "delivery_duties_customization_update_audit.csv"
    pd.DataFrame(audit_rows).to_csv(audit_path, index=False, encoding="utf-8-sig")

    missing_after = df["product_group_l3_code"].str.strip().eq("")
    summary = {
        "source_csv": str(CSV_PATH),
        "backup_csv": str(backup_path),
        "updated_rows_csv": str(updated_rows_path),
        "audit_csv": str(audit_path),
        "rows_total": int(len(df)),
        "rows_updated": int(update_mask.sum()),
        "missing_before": int(missing.sum()),
        "missing_after": int(missing_after.sum()),
        "target_names": TARGET_NAMES,
        "audit": audit_rows,
    }
    summary_path = OUTPUTS / "delivery_duties_customization_update_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
