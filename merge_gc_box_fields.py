from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
GC_PATH = ROOT / "product_master_enrichment" / "Product lists from suppliers" / "GC_tuotetiedot.xlsx"
BASE = ROOT / "product_master_enrichment" / "final_product_grouping"
INPUT_CSV = BASE / "products_product_group_tree_compact_supplier_enriched.csv"
OUTPUT_CSV = BASE / "products_product_group_tree_compact_supplier_enriched.csv"
OUTPUT_XLSX = BASE / "products_product_group_tree_compact_supplier_enriched_gc_box.xlsx"
REPORT_CSV = BASE / "gc_box_fields_update_report.csv"
SUMMARY_JSON = BASE / "gc_box_fields_update_summary.json"


BOX_COLUMN_MAP = {
    "Box - gross weight": "gc_box_gross_weight_kg",
    "Box - net weight": "gc_box_net_weight_kg",
    "Box - gross volume": "gc_box_gross_volume",
    "Box - net volume": "gc_box_net_volume",
    "Box - Height": "gc_box_height_cm",
    "Box - length": "gc_box_length_cm",
    "Box - width": "gc_box_width_cm",
}


def clean(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def norm_key(value: object) -> str:
    text = clean(value).upper()
    if text in {"", "NAN", "NONE"}:
        return ""
    return text


def norm_name(value: object) -> str:
    text = clean(value).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def to_float(value: object) -> float | None:
    text = clean(value).replace(",", ".")
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0))
    if number < 0:
        return None
    return number


def box_value(source_column: str, value: object) -> float | None:
    number = to_float(value)
    if number is None:
        return None
    if source_column in {"Box - Height", "Box - length", "Box - width"}:
        return round(number / 10, 6)  # GC box dimensions are in millimetres.
    return number


def set_if_missing(df: pd.DataFrame, idx: int, column: str, value: float | None) -> bool:
    if value is None:
        return False
    if column not in df.columns:
        df[column] = ""
    current = to_float(df.at[idx, column])
    if current is not None:
        return False
    df.at[idx, column] = value
    return True


def has_value(value: object) -> bool:
    return clean(value) != ""


def brand_matches(row: pd.Series, brand: str) -> bool:
    brand_key = norm_name(brand)
    if not brand_key:
        return False
    product_brand = norm_name(row.get("brand_name", ""))
    product_text = norm_name(" ".join([clean(row.get("product_name", "")), clean(row.get("title_fi", "")), clean(row.get("searchdata", ""))]))
    return product_brand == brand_key or brand_key in product_text


def box_tuple(row: pd.Series) -> tuple[float | None, ...]:
    return tuple(box_value(source_col, row.get(source_col)) for source_col in BOX_COLUMN_MAP)


def has_positive_box_data(row: pd.Series) -> bool:
    values = [box_value(source_col, row.get(source_col)) for source_col in BOX_COLUMN_MAP]
    return any(value is not None and value > 0 for value in values)


def stable_box_by_model(gc: pd.DataFrame) -> set[tuple[str, str]]:
    stable: set[tuple[str, str]] = set()
    for (brand, name), group in gc.groupby(["Brand", "Product name (fi)"], dropna=False):
        key = (norm_name(brand), norm_name(name))
        if not key[0] or not key[1]:
            continue
        tuples = {box_tuple(row) for _, row in group.iterrows()}
        if len(tuples) == 1:
            stable.add(key)
    return stable


def main() -> None:
    products = pd.read_csv(INPUT_CSV, dtype=str, low_memory=False, encoding="utf-8-sig")
    gc = pd.read_excel(GC_PATH, sheet_name="Export", dtype=str)
    stable_models = stable_box_by_model(gc)

    for source_col, target_col in BOX_COLUMN_MAP.items():
        products[target_col] = ""
    products["gc_box_data_source"] = ""

    products["_sku_norm"] = products["sku"].map(norm_key)
    products["_code_norm"] = products["code"].map(norm_key)
    products["_product_name_norm"] = products["product_name"].map(norm_name)
    products["_title_norm"] = products["title_fi"].map(norm_name)
    products["_match_text_norm"] = products[["product_name", "title_fi", "brand_name"]].fillna("").agg(" ".join, axis=1).map(norm_name)

    key_index: dict[str, set[int]] = {}
    for idx, row in products.iterrows():
        for key in [row["_sku_norm"], row["_code_norm"]]:
            if key:
                key_index.setdefault(key, set()).add(idx)

    name_index: dict[str, set[int]] = {}
    for idx, row in products.iterrows():
        for key in [row["_product_name_norm"], row["_title_norm"]]:
            if key:
                name_index.setdefault(key, set()).add(idx)

    report_rows = []
    unmatched_rows = 0
    matched_product_rows: set[int] = set()
    field_counts = {target: 0 for target in BOX_COLUMN_MAP.values()}
    method_counts: dict[str, int] = {}
    contains_match_cache: dict[tuple[str, str], set[int]] = {}

    for _, row in gc.iterrows():
        if not has_positive_box_data(row):
            unmatched_rows += 1
            continue

        keys = [norm_key(row.get(c)) for c in ["Sku", "Product number", "Ean"]]
        keys = [k for k in keys if k]
        matched: set[int] = set()
        method = ""

        for key in keys:
            matched.update(key_index.get(key, set()))
        if matched:
            method = "sku_code_or_ean_exact"

        if not matched:
            name = norm_name(row.get("Product name (fi)"))
            name_hits = set(name_index.get(name, set())) if name else set()
            if len(name_hits) == 1:
                matched = name_hits
                method = "product_name_unique_exact"

        if not matched:
            brand_key = norm_name(row.get("Brand"))
            name = norm_name(row.get("Product name (fi)"))
            if (brand_key, name) in stable_models and len(name) >= 4:
                cache_key = (brand_key, name)
                if cache_key not in contains_match_cache:
                    contains_hits = set(
                        products.index[
                            products["_match_text_norm"].str.contains(re.escape(name), regex=True, na=False)
                        ].tolist()
                    )
                    contains_match_cache[cache_key] = {
                        idx for idx in contains_hits if brand_matches(products.loc[idx], clean(row.get("Brand")))
                    }
                contains_hits = contains_match_cache[cache_key]
                if 0 < len(contains_hits) <= 5:
                    matched = contains_hits
                    method = "brand_and_product_name_contains_stable_box"

        if not matched:
            unmatched_rows += 1
            continue

        method_counts[method] = method_counts.get(method, 0) + len(matched)

        for idx in matched:
            changed = []
            before_after = {}
            for source_col, target_col in BOX_COLUMN_MAP.items():
                before = clean(products.at[idx, target_col])
                value = box_value(source_col, row.get(source_col))
                if set_if_missing(products, idx, target_col, value):
                    changed.append(target_col)
                    field_counts[target_col] += 1
                    before_after[f"before_{target_col}"] = before
                    before_after[f"after_{target_col}"] = products.at[idx, target_col]
            if changed:
                matched_product_rows.add(idx)
                if "gc_box_data_source" not in products.columns:
                    products["gc_box_data_source"] = ""
                products.at[idx, "gc_box_data_source"] = "GC_tuotetiedot.xlsx / Export"
                report_rows.append(
                    {
                        "row_index": idx + 2,
                        "product_id": products.at[idx, "product_id"] if "product_id" in products.columns else "",
                        "sku": products.at[idx, "sku"],
                        "product_name": products.at[idx, "product_name"],
                        "gc_sku": clean(row.get("Sku")),
                        "gc_product_number": clean(row.get("Product number")),
                        "gc_ean": clean(row.get("Ean")),
                        "gc_product_name": clean(row.get("Product name (fi)")),
                        "gc_brand": clean(row.get("Brand")),
                        "match_method": method,
                        "changed_fields": "; ".join(changed),
                        **before_after,
                    }
                )

    products = products.drop(columns=["_sku_norm", "_code_norm", "_product_name_norm", "_title_norm", "_match_text_norm"])
    products.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    pd.DataFrame(report_rows).to_csv(REPORT_CSV, index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        products.to_excel(writer, sheet_name="Products", index=False)
        pd.DataFrame(report_rows).to_excel(writer, sheet_name="GC box updates", index=False)

    summary = {
        "input_csv": str(INPUT_CSV),
        "gc_file": str(GC_PATH),
        "output_csv": str(OUTPUT_CSV),
        "output_xlsx": str(OUTPUT_XLSX),
        "report_csv": str(REPORT_CSV),
        "gc_rows": int(len(gc)),
        "updated_product_rows": int(len(matched_product_rows)),
        "unmatched_gc_rows": int(unmatched_rows),
        "field_update_counts": field_counts,
        "match_method_counts": method_counts,
        "box_columns_added": list(BOX_COLUMN_MAP.values()),
        "dimension_unit_note": "GC box Height/length/width converted from millimetres to centimetres.",
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
