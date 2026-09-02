from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd


BASE = Path("product_master_enrichment/final_product_grouping")
SOURCE_CSV = BASE / "products_product_group_tree_feedback_3level.csv"
SOURCE_XLSX = BASE / "products_product_group_tree_feedback_3level.xlsx"
SUGGESTIONS_CSV = Path("outputs/product_grouping_summary/tarkistettavat_ryhma_luokitteluehdotukset.csv")
REPORT_CSV = BASE / "high_confidence_suggestion_application_report.csv"
SUMMARY_JSON = BASE / "high_confidence_suggestion_application_summary.json"


def split_path(path: str) -> tuple[str, str, str]:
    parts = [part.strip() for part in str(path).split(">")]
    if len(parts) != 3 or any(not part for part in parts):
        raise ValueError(f"Invalid 3-level path: {path!r}")
    return parts[0], parts[1], parts[2]


def build_existing_path_map(df: pd.DataFrame) -> dict[str, dict[str, str]]:
    cols = [
        "product_group_l1_code",
        "product_group_l1_name",
        "product_group_l2_code",
        "product_group_l2_name",
        "product_group_l3_code",
        "product_group_l3_name",
        "product_group_path_name",
        "product_group_path_code",
    ]
    groups = df[cols].drop_duplicates(subset=["product_group_path_name"])
    return {str(row["product_group_path_name"]): row.to_dict() for _, row in groups.iterrows()}


def next_l2_code(df: pd.DataFrame, l1_code: str) -> str:
    existing = (
        df.loc[df["product_group_l1_code"].eq(l1_code), "product_group_l2_code"]
        .dropna()
        .astype(str)
        .unique()
    )
    suffixes = [int(code.split(".")[-1]) for code in existing if code.startswith(f"{l1_code}.")]
    return f"{l1_code}.{max(suffixes, default=0) + 1:02d}"


def next_l3_code(df: pd.DataFrame, l2_code: str) -> str:
    existing = (
        df.loc[df["product_group_l2_code"].eq(l2_code), "product_group_l3_code"]
        .dropna()
        .astype(str)
        .unique()
    )
    suffixes = [int(code.split(".")[-1]) for code in existing if code.startswith(f"{l2_code}.")]
    return f"{l2_code}.{max(suffixes, default=0) + 1:02d}"


def build_group_record(df: pd.DataFrame, path: str) -> dict[str, str]:
    l1_name, l2_name, l3_name = split_path(path)
    l1_lookup = df[["product_group_l1_name", "product_group_l1_code"]].drop_duplicates()
    l1_matches = l1_lookup[l1_lookup["product_group_l1_name"].eq(l1_name)]
    if l1_matches.empty:
        raise ValueError(f"Unknown L1 group in suggested path: {path}")
    l1_code = str(l1_matches.iloc[0]["product_group_l1_code"])

    l2_lookup = df[
        [
            "product_group_l1_code",
            "product_group_l2_name",
            "product_group_l2_code",
        ]
    ].drop_duplicates()
    l2_matches = l2_lookup[
        l2_lookup["product_group_l1_code"].eq(l1_code)
        & l2_lookup["product_group_l2_name"].eq(l2_name)
    ]
    if l2_matches.empty:
        l2_code = next_l2_code(df, l1_code)
    else:
        l2_code = str(l2_matches.iloc[0]["product_group_l2_code"])

    l3_code = next_l3_code(df, l2_code)
    return {
        "product_group_l1_code": l1_code,
        "product_group_l1_name": l1_name,
        "product_group_l2_code": l2_code,
        "product_group_l2_name": l2_name,
        "product_group_l3_code": l3_code,
        "product_group_l3_name": l3_name,
        "product_group_path_code": f"{l1_code} > {l2_code} > {l3_code}",
        "product_group_path_name": path,
    }


def level_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for level in [1, 2, 3]:
        cols: list[str] = []
        for i in range(1, level + 1):
            cols.extend([f"product_group_l{i}_code", f"product_group_l{i}_name"])
        grouped = df.groupby(cols, dropna=False).size().reset_index(name="product_count")
        for _, row in grouped.iterrows():
            rows.append(
                {
                    "level": level,
                    "code": row[f"product_group_l{level}_code"],
                    "name": row[f"product_group_l{level}_name"],
                    "path": " > ".join(str(row[f"product_group_l{i}_name"]) for i in range(1, level + 1)),
                    "product_count": int(row["product_count"]),
                }
            )
    return pd.DataFrame(rows).sort_values(["level", "code", "path"])


def autosize(writer: pd.ExcelWriter) -> None:
    for worksheet in writer.book.worksheets:
        worksheet.freeze_panes = "A2"
        for column_cells in worksheet.columns:
            values = [str(cell.value) for cell in column_cells[:200] if cell.value is not None]
            width = min(max([len(value) for value in values] + [12]) + 2, 55)
            worksheet.column_dimensions[column_cells[0].column_letter].width = width


def main() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_csv = SOURCE_CSV.with_name(f"{SOURCE_CSV.stem}.backup_before_high_{timestamp}{SOURCE_CSV.suffix}")
    backup_xlsx = SOURCE_XLSX.with_name(f"{SOURCE_XLSX.stem}.backup_before_high_{timestamp}{SOURCE_XLSX.suffix}")

    products = pd.read_csv(SOURCE_CSV, dtype=str, keep_default_na=False, low_memory=False)
    suggestions = pd.read_csv(SUGGESTIONS_CSV, dtype=str, keep_default_na=False, low_memory=False)
    high = suggestions[suggestions["confidence"].eq("high") & suggestions["suggested_path"].ne("")].copy()
    high = high.drop_duplicates(subset=["code"], keep="first")

    path_map = build_existing_path_map(products)
    for suggested_path in sorted(set(high["suggested_path"])):
        if suggested_path not in path_map:
            path_map[suggested_path] = build_group_record(products, suggested_path)
            extra = pd.DataFrame([path_map[suggested_path]])
            products_for_codes = products.copy()
            for col, value in path_map[suggested_path].items():
                products_for_codes.loc[len(products_for_codes), col] = value

    code_to_suggestion = {row["code"]: row for _, row in high.iterrows()}
    changed_rows = []

    for idx, row in products.iterrows():
        code = row.get("code", "")
        if code not in code_to_suggestion:
            continue

        suggestion = code_to_suggestion[code]
        target = path_map[suggestion["suggested_path"]]
        old_path = row.get("product_group_path_name", "")
        new_path = target["product_group_path_name"]

        for col in [
            "product_group_l1_code",
            "product_group_l1_name",
            "product_group_l2_code",
            "product_group_l2_name",
            "product_group_l3_code",
            "product_group_l3_name",
            "product_group_path_code",
            "product_group_path_name",
        ]:
            products.at[idx, col] = target[col]
        products.at[idx, "product_group_l4_code"] = ""
        products.at[idx, "product_group_l4_name"] = ""
        products.at[idx, "product_group_source"] = (
            str(row.get("product_group_source", ""))
            + "|high_suggestion_applied:"
            + str(suggestion.get("reason", ""))
        )

        changed_rows.append(
            {
                "code": code,
                "product_name": row.get("product_name", ""),
                "old_path": old_path,
                "new_path": new_path,
                "confidence": suggestion["confidence"],
                "reason": suggestion.get("reason", ""),
            }
        )

    shutil.copy2(SOURCE_CSV, backup_csv)
    if SOURCE_XLSX.exists():
        shutil.copy2(SOURCE_XLSX, backup_xlsx)

    levels = level_summary(products)
    report = pd.DataFrame(changed_rows)
    source_counts = products["product_group_source"].str.split("|").explode().value_counts().reset_index()
    source_counts.columns = ["source_marker", "product_count"]

    products.to_csv(SOURCE_CSV, index=False, encoding="utf-8-sig")
    report.to_csv(REPORT_CSV, index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(SOURCE_XLSX, engine="openpyxl") as writer:
        products.to_excel(writer, sheet_name="Products", index=False)
        levels.to_excel(writer, sheet_name="Yhteenveto", index=False)
        report.to_excel(writer, sheet_name="Muutokset", index=False)
        source_counts.to_excel(writer, sheet_name="Source_counts", index=False)
        autosize(writer)

    summary = {
        "source_csv": str(SOURCE_CSV.resolve()),
        "source_xlsx": str(SOURCE_XLSX.resolve()),
        "suggestions_csv": str(SUGGESTIONS_CSV.resolve()),
        "backup_csv": str(backup_csv.resolve()),
        "backup_xlsx": str(backup_xlsx.resolve()) if SOURCE_XLSX.exists() else "",
        "high_suggestions_applied": len(changed_rows),
        "unique_target_paths": int(report["new_path"].nunique()) if not report.empty else 0,
        "target_counts": report["new_path"].value_counts().to_dict() if not report.empty else {},
        "group_counts_after": {
            f"L{level}": int(products[[f"product_group_l{level}_code", f"product_group_l{level}_name"]].drop_duplicates().shape[0])
            for level in [1, 2, 3]
        },
        "remaining_14_01_01_rows": int(products["product_group_l3_code"].eq("14.01.01").sum()),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
