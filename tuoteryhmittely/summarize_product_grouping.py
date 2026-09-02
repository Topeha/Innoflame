from __future__ import annotations

import json
from pathlib import Path
from glob import glob

import pandas as pd


BASE = Path("product_master_enrichment/final_product_grouping")
OUT = Path("outputs/product_grouping_summary")
OUT.mkdir(parents=True, exist_ok=True)

PRODUCTS = BASE / "Innoflame_tuoteryhmittely.csv"


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def level_summary(df: pd.DataFrame, level: int) -> pd.DataFrame:
    cols = []
    for i in range(1, level + 1):
        cols.extend([f"product_group_l{i}_code", f"product_group_l{i}_name"])
    result = (
        df.groupby(cols, dropna=False)
        .agg(
            product_count=("product_id", "nunique"),
            sku_count=("sku", "nunique"),
            source_count=("product_group_source", "nunique"),
        )
        .reset_index()
        .sort_values(["product_count"] + [f"product_group_l{level}_name"], ascending=[False, True])
    )
    return result


def pct(part: int, whole: int) -> float:
    return round(part / whole * 100, 1) if whole else 0.0


def non_empty_count(df: pd.DataFrame, column: str) -> int:
    if column not in df.columns:
        return 0
    return int(df[column].fillna("").astype(str).str.strip().ne("").sum())


def numeric_nonzero_count(df: pd.DataFrame, column: str) -> int:
    if column not in df.columns:
        return 0
    values = pd.to_numeric(df[column], errors="coerce").fillna(0)
    return int(values.ne(0).sum())


def numeric_positive_count(df: pd.DataFrame, column: str) -> int:
    if column not in df.columns:
        return 0
    values = pd.to_numeric(df[column], errors="coerce").fillna(0)
    return int(values.gt(0).sum())


def numeric_missing_or_zero_count(df: pd.DataFrame, column: str) -> int:
    if column not in df.columns:
        return int(len(df))
    values = pd.to_numeric(df[column], errors="coerce").fillna(0)
    return int(values.eq(0).sum())


def latest_json(pattern: str) -> dict:
    matches = sorted(glob(pattern), key=lambda path: Path(path).stat().st_mtime, reverse=True)
    if not matches:
        return {}
    try:
        return json.loads(Path(matches[0]).read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> None:
    df = read_csv(PRODUCTS)
    total = int(df["product_id"].nunique())

    summaries = {}
    top_groups = {}
    active_levels = 3
    for level in range(1, active_levels + 1):
        s = level_summary(df, level)
        s.to_csv(OUT / f"product_group_level_{level}_summary.csv", index=False, encoding="utf-8-sig")
        name_col = f"product_group_l{level}_name"
        code_col = f"product_group_l{level}_code"
        summaries[f"l{level}"] = {
            "group_count": int(len(s)),
            "largest_group": str(s.iloc[0][name_col]),
            "largest_group_code": str(s.iloc[0][code_col]),
            "largest_group_products": int(s.iloc[0]["product_count"]),
            "largest_group_pct": pct(int(s.iloc[0]["product_count"]), total),
            "median_group_size": float(round(s["product_count"].median(), 1)),
            "groups_under_5_products": int((s["product_count"] < 5).sum()),
            "groups_under_10_products": int((s["product_count"] < 10).sum()),
        }
        top_groups[f"l{level}"] = [
            {
                "code": str(row[code_col]),
                "name": str(row[name_col]),
                "product_count": int(row["product_count"]),
                "pct": pct(int(row["product_count"]), total),
            }
            for _, row in s.head(12).iterrows()
        ]

    source_counts = df["product_group_source"].value_counts().reset_index()
    source_counts.columns = ["product_group_source", "product_count"]
    source_counts.to_csv(OUT / "product_group_source_counts.csv", index=False, encoding="utf-8-sig")

    l3 = level_summary(df, 3)
    other_l3 = l3[l3["product_group_l3_name"].astype(str).str.lower().str.contains("muut|tarkistettavat|ei tunnistettu", regex=True)]
    l3_900 = l3[l3["product_group_l3_code"].astype(str).str.endswith(".900")]

    issue_rows = []
    reports = {
        "Puuttuva paino korjattavissa duplikaatin perusteella": "duplicate_products_missing_weight_by_name.csv",
        "Paino täytetty duplikaattituotteelta": "duplicate_products_weight_update_report.csv",
        "Tuplatuotteiden tuoteryhmäpolku yhdistetty": "duplicate_product_group_merge_report.csv",
        "Pienet L4-ryhmät yhdistetty Muut-ryhmään": "product_group_l4_consolidation_report.csv",
        "Varastokategorian perusteella uudelleenmapattu": "inventory_warehouse_review_mapping_report.csv",
        "Työvaatteet siirretty omaan päätasoon": "inventory_workwear_top_level_move_report.csv",
    }
    for label, filename in reports.items():
        path = BASE / filename
        if path.exists():
            count = int(len(read_csv(path)))
            issue_rows.append({"issue": label, "affected_rows": count, "pct_of_products": pct(count, total), "source_file": filename})

    missing_weight_summary_path = BASE / "duplicate_products_missing_weight_summary.csv"
    if missing_weight_summary_path.exists():
        missing_weight_summary = read_csv(missing_weight_summary_path)
        missing_weight_total = int(missing_weight_summary["missing_rows"].sum()) if "missing_rows" in missing_weight_summary.columns else 0
    else:
        missing_weight_total = 0

    missing_weight_value_rows = numeric_missing_or_zero_count(df, "weight_value")
    brand_rows = non_empty_count(df, "brand_name")
    dif_rows = int(pd.to_numeric(df["is_dif_code"], errors="coerce").fillna(0).sum()) if "is_dif_code" in df.columns else 0
    web_dimension_rows = non_empty_count(df, "web_extracted_dimensions")
    web_weight_rows = non_empty_count(df, "web_extracted_weight")
    rbx_rows = int(
        df[
            [
                col
                for col in [
                    "supplier_rbx_gross_weight_kg",
                    "supplier_rbx_height_cm",
                    "supplier_rbx_length_cm",
                    "supplier_rbx_width_cm",
                    "supplier_rbx_net_volume",
                ]
                if col in df.columns
            ]
        ]
        .fillna("")
        .astype(str)
        .apply(lambda row: any(cell.strip() not in {"", "0", "0.0"} for cell in row), axis=1)
        .sum()
    )
    pc_gross_weight_rows = numeric_positive_count(df, "supplier_pc_gross_weight_kg")

    issues = {
        "total_products": total,
        "unique_skus": int(df["sku"].nunique()),
        "duplicate_sku_rows": int(total - df["sku"].nunique()),
        "missing_weight_rows": missing_weight_value_rows,
        "missing_weight_rows_pct": pct(missing_weight_value_rows, total),
        "missing_weight_g_rows": int(df["weight_g"].isna().sum()),
        "missing_weight_g_rows_pct": pct(int(df["weight_g"].isna().sum()), total),
        "missing_weight_duplicate_fix_candidates": missing_weight_total,
        "missing_weight_duplicate_fix_pct": pct(missing_weight_total, total),
        "missing_dimension_rows": int(df[["width_value", "length_value", "depth_value"]].isna().all(axis=1).sum()),
        "missing_dimension_rows_pct": pct(int(df[["width_value", "length_value", "depth_value"]].isna().all(axis=1).sum()), total),
        "brand_rows": brand_rows,
        "brand_rows_pct": pct(brand_rows, total),
        "unique_brand_names": int(df["brand_name"].dropna().replace("", pd.NA).dropna().nunique()) if "brand_name" in df.columns else 0,
        "dif_rows": dif_rows,
        "dif_rows_pct": pct(dif_rows, total),
        "web_dimension_rows": web_dimension_rows,
        "web_dimension_rows_pct": pct(web_dimension_rows, total),
        "web_weight_rows": web_weight_rows,
        "web_weight_rows_pct": pct(web_weight_rows, total),
        "supplier_pc_gross_weight_rows": pc_gross_weight_rows,
        "supplier_pc_gross_weight_rows_pct": pct(pc_gross_weight_rows, total),
        "supplier_rbx_rows": rbx_rows,
        "supplier_rbx_rows_pct": pct(rbx_rows, total),
        "fallback_classified_rows": int(df["product_group_source"].astype(str).str.contains("previous_tree_fallback").sum()),
        "fallback_classified_pct": pct(int(df["product_group_source"].astype(str).str.contains("previous_tree_fallback").sum()), total),
        "title_rule_rows": int(df["product_group_source"].astype(str).str.contains("title_description_rule").sum()),
        "title_rule_pct": pct(int(df["product_group_source"].astype(str).str.contains("title_description_rule").sum()), total),
        "inventory_mapped_rows": int(df["product_group_source"].astype(str).str.contains("inventory_category_mapped").sum()),
        "inventory_mapped_pct": pct(int(df["product_group_source"].astype(str).str.contains("inventory_category_mapped").sum()), total),
        "active_group_levels": active_levels,
        "l3_other_groups": int(len(other_l3)),
        "l3_other_products": int(other_l3["product_count"].sum()),
        "l3_other_products_pct": pct(int(other_l3["product_count"].sum()), total),
        "l3_900_groups": int(len(l3_900)),
        "l3_900_products": int(l3_900["product_count"].sum()),
        "l3_900_products_pct": pct(int(l3_900["product_count"].sum()), total),
        "issue_rows": issue_rows,
    }

    update_summaries = {
        "weight_dimension": latest_json(str(BASE / "product_weight_dimension_update_summary.json")),
        "brand_mapping": latest_json(str(BASE / "product_brand_mapping_summary.json")),
        "weight_value_from_weigh": latest_json(str(BASE / "product_weight_value_from_weigh_summary.json")),
        "dif_indicator": latest_json(str(BASE / "product_dif_code_indicator_summary.json")),
        "supplier_weight_dimension": latest_json(str(BASE / "supplier_weight_dimension_update_summary.json")),
        "rbx_merge": latest_json(str(BASE / "gc_box_to_supplier_rbx_merge_summary.json")),
        "unit_conversion": latest_json(str(BASE / "dimension_unit_conversion_to_cm_summary.json")),
    }

    biggest_other = (
        other_l3.sort_values("product_count", ascending=False)
        .head(10)[["product_group_l1_name", "product_group_l2_name", "product_group_l3_name", "product_count"]]
    )
    biggest_other.to_csv(OUT / "largest_other_l3_groups.csv", index=False, encoding="utf-8-sig")

    payload = {
        "summaries": summaries,
        "top_groups": top_groups,
        "issues": issues,
        "top_sources": [
            {"source": str(row["product_group_source"]), "product_count": int(row["product_count"]), "pct": pct(int(row["product_count"]), total)}
            for _, row in source_counts.head(12).iterrows()
        ],
        "biggest_other_l3_groups": biggest_other.to_dict(orient="records"),
        "update_summaries": update_summaries,
    }
    (OUT / "product_grouping_deck_data.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
