from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parent
OUTPUTS = BASE / "outputs"
CSV_PATH = OUTPUTS / "Innoflame_merged_sales_csv_source_with_L1_L2_L3_delivery_handling.csv"

GROUP_COLUMNS = [
    "product_group_l1_code",
    "product_group_l1_name",
    "product_group_l2_code",
    "product_group_l2_name",
    "product_group_l3_code",
    "product_group_l3_name",
]

KEY_COLUMNS = ["productcode", "optioncode", "reference", "name"]


def normalize_text(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def build_unique_mapping(df: pd.DataFrame, key_column: str) -> dict[tuple[str, str], dict[str, str]]:
    source = df[
        df["product_group_l3_code"].str.strip().ne("")
        & df[key_column].str.strip().ne("")
    ].copy()
    source["_key_norm"] = source[key_column].map(normalize_text)
    source["_category_norm"] = source["category"].map(normalize_text)

    unique_rows = []
    for (key_norm, category_norm), group in source.groupby(["_key_norm", "_category_norm"], dropna=False):
        groups = group[GROUP_COLUMNS].drop_duplicates()
        if len(groups) == 1:
            values = groups.iloc[0].to_dict()
            unique_rows.append((key_norm, category_norm, values))

    return {(key_norm, category_norm): values for key_norm, category_norm, values in unique_rows}


def build_unique_mapping_frame(df: pd.DataFrame, key_column: str) -> pd.DataFrame:
    source = df[
        df["product_group_l3_code"].str.strip().ne("")
        & df[key_column].str.strip().ne("")
    ].copy()
    source["_key_norm"] = source[key_column].map(normalize_text)
    source["_category_norm"] = source["category"].map(normalize_text)

    counts = (
        source.groupby(["_key_norm", "_category_norm"], dropna=False)[GROUP_COLUMNS]
        .nunique(dropna=False)
        .reset_index()
    )
    unique_keys = counts[counts[GROUP_COLUMNS].eq(1).all(axis=1)][["_key_norm", "_category_norm"]]
    mapping = source[["_key_norm", "_category_norm", *GROUP_COLUMNS]].drop_duplicates()
    mapping = mapping.merge(unique_keys, on=["_key_norm", "_category_norm"], how="inner")
    return mapping.drop_duplicates(["_key_norm", "_category_norm"])


def main() -> None:
    df = pd.read_csv(CSV_PATH, dtype=str, encoding="utf-8-sig", keep_default_na=False)
    missing_before = df["product_group_l3_code"].str.strip().eq("")

    backup_path = OUTPUTS / f"{CSV_PATH.stem}.backup_before_same_key_category_{datetime.now():%Y%m%d_%H%M%S}.csv"
    shutil.copy2(CSV_PATH, backup_path)

    audit_rows = []
    updated_indices: list[int] = []

    for key_column in KEY_COLUMNS:
        remaining_missing = df["product_group_l3_code"].str.strip().eq("")
        mapping = build_unique_mapping_frame(df, key_column)
        candidates = df.loc[
            remaining_missing & df[key_column].str.strip().ne(""),
            [key_column, "category"],
        ].copy()
        candidates["_row_index"] = candidates.index
        candidates["_key_norm"] = candidates[key_column].map(normalize_text)
        candidates["_category_norm"] = candidates["category"].map(normalize_text)
        hits = candidates.merge(mapping, on=["_key_norm", "_category_norm"], how="inner")

        if hits.empty:
            audit_rows.append(
                {
                    "key_column": key_column,
                    "unique_mapping_keys": len(mapping),
                    "rows_updated": 0,
                }
            )
            continue

        hit_indices = hits["_row_index"].astype(int).to_numpy()
        for column in GROUP_COLUMNS:
            df.loc[hit_indices, column] = hits[column].to_numpy()
        df.loc[hit_indices, "product_group_match_method"] = f"same_{key_column}_category_unique_refresh"

        updated_indices.extend(hit_indices.tolist())
        audit_rows.append(
            {
                "key_column": key_column,
                "unique_mapping_keys": len(mapping),
                "rows_updated": int(len(hit_indices)),
            }
        )

    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")

    updated_unique_indices = sorted(set(updated_indices))
    updated_rows_path = OUTPUTS / "same_key_category_update_rows.csv"
    df.loc[
        updated_unique_indices,
        [
            "id",
            "status",
            "category",
            "productcode",
            "optioncode",
            "reference",
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

    audit_path = OUTPUTS / "same_key_category_update_audit.csv"
    pd.DataFrame(audit_rows).to_csv(audit_path, index=False, encoding="utf-8-sig")

    missing_after = df["product_group_l3_code"].str.strip().eq("")
    summary = {
        "source_csv": str(CSV_PATH.resolve()),
        "backup_csv": str(backup_path.resolve()),
        "updated_rows_csv": str(updated_rows_path.resolve()),
        "audit_csv": str(audit_path.resolve()),
        "rows_total": int(len(df)),
        "missing_before": int(missing_before.sum()),
        "rows_updated": int(len(updated_unique_indices)),
        "missing_after": int(missing_after.sum()),
        "audit": audit_rows,
        "updated_by_method": (
            df.loc[updated_unique_indices]
            .groupby("product_group_match_method")
            .size()
            .sort_values(ascending=False)
            .reset_index(name="rows")
            .to_dict(orient="records")
        ),
        "updated_by_l3": (
            df.loc[updated_unique_indices]
            .groupby(["product_group_l3_code", "product_group_l3_name"])
            .size()
            .sort_values(ascending=False)
            .reset_index(name="rows")
            .head(30)
            .to_dict(orient="records")
        ),
    }
    summary_path = OUTPUTS / "same_key_category_update_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
