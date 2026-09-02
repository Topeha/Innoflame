from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


BASE = Path("product_master_enrichment")
FINAL = BASE / "final_product_grouping"
ZIP_PATH = BASE / "Product lists from suppliers.zip"
INPUT = FINAL / "products_product_group_tree_compact_workwear_under_clothing.csv"
FALLBACK_INPUT = FINAL / "products_product_group_tree_final.csv"
OUTPUT_CSV = FINAL / "products_product_group_tree_compact_supplier_enriched.csv"
OUTPUT_XLSX = FINAL / "products_product_group_tree_compact_supplier_enriched.xlsx"
REPORT_CSV = FINAL / "supplier_weight_dimension_update_report.csv"
SUMMARY_JSON = FINAL / "supplier_weight_dimension_update_summary.json"
UNMATCHED_CSV = FINAL / "supplier_weight_dimension_unmatched_candidates.csv"


@dataclass
class SupplierRecord:
    source_file: str
    source_sheet: str
    match_keys: list[str]
    product_name: str = ""
    brand: str = ""
    gross_weight_kg: float | None = None
    net_weight_kg: float | None = None
    width_cm: float | None = None
    length_cm: float | None = None
    depth_cm: float | None = None
    pc_gross_weight_kg: float | None = None
    rbx_pcs: float | None = None
    rbx_gross_weight_kg: float | None = None
    rbx_height_cm: float | None = None
    rbx_length_cm: float | None = None
    rbx_width_cm: float | None = None
    notes: str = ""


def clean(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def to_float(value: object) -> float | None:
    text = clean(value)
    if not text:
        return None
    text = text.replace("\xa0", " ").replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def parse_weight_kg(value: object, default_unit: str = "kg") -> float | None:
    number = to_float(value)
    if number is None or number <= 0:
        return None
    text = clean(value).lower()
    if "g" in text and "kg" not in text:
        return number / 1000
    if default_unit == "g":
        return number / 1000
    return number


def parse_dim_cm(value: object, default_unit: str = "cm") -> float | None:
    number = to_float(value)
    if number is None or number <= 0:
        return None
    text = clean(value).lower()
    if "mm" in text:
        return number / 10
    if default_unit == "mm":
        return number / 10
    if "m" in text and "mm" not in text and "cm" not in text:
        return number * 100
    return number


def norm_key(value: object) -> str:
    text = clean(value).upper()
    if not text or text in {"NAN", "NONE"}:
        return ""
    return text


def norm_name(value: object) -> str:
    text = clean(value).lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def code_tokens(values: Iterable[object]) -> list[str]:
    keys: list[str] = []
    for value in values:
        key = norm_key(value)
        if key and key not in keys:
            keys.append(key)
    return keys


def read_headered_excel(zf: zipfile.ZipFile, name: str, sheet_name: str = 0) -> pd.DataFrame:
    raw = zf.read(name)
    df = pd.read_excel(io.BytesIO(raw), sheet_name=sheet_name, dtype=str)
    unnamed = [c for c in df.columns if str(c).startswith("Unnamed:")]
    if len(unnamed) >= len(df.columns) * 0.7 and not df.empty:
        headers = [clean(v) or f"col_{i}" for i, v in enumerate(df.iloc[0].tolist())]
        df = df.iloc[1:].copy()
        df.columns = headers
    return df


def supplier_records() -> list[SupplierRecord]:
    records: list[SupplierRecord] = []
    with zipfile.ZipFile(ZIP_PATH) as zf:
        fiskars = pd.read_excel(io.BytesIO(zf.read("Fiskars Finland tuotetiedot valikoimalle H1 2026.xlsx")), dtype=str)
        for _, row in fiskars.iterrows():
            records.append(
                SupplierRecord(
                    source_file="Fiskars Finland tuotetiedot valikoimalle H1 2026.xlsx",
                    source_sheet="Taul1",
                    match_keys=code_tokens([row.get("Code"), row.get("Vendor product code")]),
                    product_name=clean(row.get("Product name")),
                    brand="Fiskars",
                    gross_weight_kg=parse_weight_kg(row.get("Gross weight")),
                    net_weight_kg=parse_weight_kg(row.get("Net weight")),
                    width_cm=parse_dim_cm(row.get("Width of sales unit (product in packaging or set box)")),
                    length_cm=parse_dim_cm(row.get("Height of sales unit (product in packaging or set box)")),
                    depth_cm=parse_dim_cm(row.get("Depth of sales unit (product in packaging or set box)")),
                    pc_gross_weight_kg=parse_weight_kg(row.get("Gross weight")),
                    notes="Fiskars sales unit dimensions",
                )
            )

        vita = read_headered_excel(zf, "Fiskars Vita Innoflame logistiikkatiedot.xlsx")
        for _, row in vita.iterrows():
            records.append(
                SupplierRecord(
                    source_file="Fiskars Vita Innoflame logistiikkatiedot.xlsx",
                    source_sheet="Sheet1",
                    match_keys=code_tokens([row.get("SAP Material Number"), row.get("EAN Code"), row.get("UPC6 Code")]),
                    product_name=clean(row.get("Product Name")),
                    brand="Fiskars Vita",
                    gross_weight_kg=parse_weight_kg(row.get("Gross weight")),
                    net_weight_kg=parse_weight_kg(row.get("Net weight")),
                    width_cm=parse_dim_cm(row.get("Width")),
                    length_cm=parse_dim_cm(row.get("Length")),
                    depth_cm=parse_dim_cm(row.get("Height")),
                    pc_gross_weight_kg=parse_weight_kg(row.get("Gross weight")),
                    rbx_pcs=to_float(row.get("PCS.")),
                    rbx_gross_weight_kg=parse_weight_kg(row.get("Gross weight rbx")),
                    rbx_height_cm=parse_dim_cm(row.get("Height rbx")),
                    rbx_length_cm=parse_dim_cm(row.get("Length rbx")),
                    rbx_width_cm=parse_dim_cm(row.get("Width rbx")),
                    notes="Fiskars Vita PC logistics dimensions",
                )
            )

        innoflame_fiskars = read_headered_excel(zf, "Innoflame_Fiskars tietoja 07052026.xlsx")
        for _, row in innoflame_fiskars.iterrows():
            records.append(
                SupplierRecord(
                    source_file="Innoflame_Fiskars tietoja 07052026.xlsx",
                    source_sheet="Sheet1",
                    match_keys=code_tokens([row.get("Material code"), row.get("EAN code")]),
                    product_name=clean(row.get("Material description FI")),
                    brand="Fiskars",
                    gross_weight_kg=parse_weight_kg(row.get("Gross weight")),
                    net_weight_kg=parse_weight_kg(row.get("Net Weight")),
                    width_cm=parse_dim_cm(row.get("Width")),
                    length_cm=parse_dim_cm(row.get("Length")),
                    depth_cm=parse_dim_cm(row.get("Height")),
                    pc_gross_weight_kg=parse_weight_kg(row.get("Gross weight")),
                    rbx_pcs=to_float(row.get("RBX QTY")),
                    rbx_gross_weight_kg=parse_weight_kg(row.get("RBX gross weight")),
                    rbx_height_cm=parse_dim_cm(row.get("RBX height")),
                    rbx_length_cm=parse_dim_cm(row.get("RBX length")),
                    rbx_width_cm=parse_dim_cm(row.get("RBX width")),
                    notes="Fiskars Innoflame product logistics dimensions",
                )
            )

        gc = pd.read_excel(io.BytesIO(zf.read("GC_tuotetiedot.xlsx")), sheet_name="Export", dtype=str)
        for _, row in gc.iterrows():
            records.append(
                SupplierRecord(
                    source_file="GC_tuotetiedot.xlsx",
                    source_sheet="Export",
                    match_keys=code_tokens([row.get("Sku"), row.get("Product number"), row.get("Ean")]),
                    product_name=clean(row.get("Product name (fi)")),
                    brand=clean(row.get("Brand")),
                    gross_weight_kg=parse_weight_kg(row.get("Gross weight")),
                    net_weight_kg=parse_weight_kg(row.get("Net weight")),
                    width_cm=parse_dim_cm(row.get("Width")),
                    length_cm=parse_dim_cm(row.get("Length")),
                    depth_cm=parse_dim_cm(row.get("Height")),
                    notes="GC product dimensions only; carton box dimensions intentionally not used",
                )
            )

        trexet_xl = pd.ExcelFile(io.BytesIO(zf.read("Trexet_SS26.xlsx")))
        for sheet in trexet_xl.sheet_names:
            trexet = pd.read_excel(trexet_xl, sheet_name=sheet, dtype=str)
            for _, row in trexet.iterrows():
                records.append(
                    SupplierRecord(
                        source_file="Trexet_SS26.xlsx",
                        source_sheet=sheet,
                        match_keys=code_tokens([row.get("Sku"), row.get("Product number"), row.get("Variation number"), row.get("Ean")]),
                        product_name=clean(row.get("Product name (fi)")),
                        brand=clean(row.get("Brand")),
                        gross_weight_kg=parse_weight_kg(row.get("Gross weight")),
                        net_weight_kg=parse_weight_kg(row.get("Net weight")),
                        notes="Trexet/New Wave weights; no package dimensions in source",
                    )
                )

        stanley = pd.read_csv(io.BytesIO(zf.read("products_Stanley_Stella.csv")), dtype=str, encoding="utf-8-sig", sep=None, engine="python")
        for _, row in stanley.iterrows():
            records.append(
                SupplierRecord(
                    source_file="products_Stanley_Stella.csv",
                    source_sheet="csv",
                    match_keys=code_tokens([row.get("B2BSKUREF"), row.get("StyleCode")]),
                    product_name=clean(row.get("StyleName")),
                    brand="Stanley/Stella",
                    gross_weight_kg=parse_weight_kg(row.get("WeightPerUnit")),
                    net_weight_kg=parse_weight_kg(row.get("WeightPerUnit")),
                    notes="Stanley/Stella unit weight only; garment measurements intentionally not used as package dimensions",
                )
            )
    return [
        r
        for r in records
        if r.match_keys
        and any(
            [
                r.gross_weight_kg,
                r.net_weight_kg,
                r.width_cm,
                r.length_cm,
                r.depth_cm,
                r.pc_gross_weight_kg,
                r.rbx_pcs,
                r.rbx_gross_weight_kg,
                r.rbx_height_cm,
                r.rbx_length_cm,
                r.rbx_width_cm,
            ]
        )
    ]


def nonzero_number(series_value: object) -> bool:
    number = to_float(series_value)
    return bool(number and number > 0)


def set_if_missing(df: pd.DataFrame, idx: int, column: str, value: object) -> bool:
    if value is None:
        return False
    if column not in df.columns:
        df[column] = ""
    current = df.at[idx, column]
    if clean(current) and nonzero_number(current):
        return False
    df.at[idx, column] = value
    return True


def existing_positive_number(df: pd.DataFrame, idx: int, column: str) -> float | None:
    if column not in df.columns:
        return None
    number = to_float(df.at[idx, column])
    if number is None or number <= 0:
        return None
    return number


def close_enough(a: float, b: float) -> bool:
    return abs(a - b) <= max(2.0, abs(a) * 0.02)


def main() -> None:
    input_path = INPUT if INPUT.exists() else FALLBACK_INPUT
    df = pd.read_csv(input_path, dtype=str, low_memory=False, encoding="utf-8-sig")
    for col in ["sku", "code", "product_name", "title_fi", "searchdata", "description_fi", "brand_name", "inventory_supplier"]:
        if col not in df.columns:
            df[col] = ""
    df["_sku_norm"] = df["sku"].map(norm_key)
    df["_code_norm"] = df["code"].map(norm_key)
    df["_product_name_norm"] = df["product_name"].map(norm_name)
    df["_title_norm"] = df["title_fi"].map(norm_name)
    search_cols = ["sku", "code", "product_name", "title_fi", "searchdata", "description_fi", "brand_name", "inventory_supplier"]
    df["_search_text"] = " " + df[search_cols].fillna("").agg(" ".join, axis=1).str.upper() + " "
    df["_search_text_norm"] = df[search_cols].fillna("").agg(" ".join, axis=1).map(norm_name)

    sku_index: dict[str, list[int]] = {}
    for idx, row in df.iterrows():
        for key in [row["_sku_norm"], row["_code_norm"]]:
            if key:
                sku_index.setdefault(key, []).append(idx)

    name_index: dict[str, set[int]] = {}
    for idx, row in df.iterrows():
        for name_key in [row["_product_name_norm"], row["_title_norm"]]:
            if name_key:
                name_index.setdefault(name_key, set()).add(idx)

    # Fast exact-token index for supplier product numbers, EANs and SKU-like codes that
    # appear inside long product descriptions/search data.
    text_key_index: dict[str, set[int]] = {}
    token_pattern = re.compile(r"(?<![A-Z0-9])([A-Z0-9][A-Z0-9._/-]{4,})(?![A-Z0-9])")
    for idx, text in df["_search_text"].items():
        for token in token_pattern.findall(text):
            text_key_index.setdefault(token.strip("._/-"), set()).add(idx)

    records = supplier_records()
    reports = []
    unmatched = []
    updated_rows: set[int] = set()
    update_counts = {
        "weight_value": 0,
        "weight_g": 0,
        "width_value": 0,
        "length_value": 0,
        "depth_value": 0,
        "supplier_pc_gross_weight_kg": 0,
        "supplier_rbx_pcs": 0,
        "supplier_rbx_gross_weight_kg": 0,
        "supplier_rbx_height_cm": 0,
        "supplier_rbx_length_cm": 0,
        "supplier_rbx_width_cm": 0,
    }

    for record in records:
        matched: set[int] = set()
        match_method = ""
        for key in record.match_keys:
            if key in sku_index:
                matched.update(sku_index[key])
                match_method = "sku_or_code_exact"

        # Exact code-in-text fallback is allowed only when it identifies a small, unambiguous set.
        if not matched:
            for key in record.match_keys:
                if len(key) < 5:
                    continue
                hits = list(text_key_index.get(key.strip("._/-"), set()))
                if 0 < len(hits) <= 5:
                    matched.update(hits)
                    match_method = "supplier_key_in_product_text"

        has_logistics = any(
            [
                record.pc_gross_weight_kg,
                record.rbx_pcs,
                record.rbx_gross_weight_kg,
                record.rbx_height_cm,
                record.rbx_length_cm,
                record.rbx_width_cm,
            ]
        )
        if not matched and has_logistics and "Fiskars" in record.source_file:
            product_name_key = norm_name(record.product_name)
            name_hits = set(name_index.get(product_name_key, set()))
            if not name_hits and len(product_name_key) >= 8:
                name_hits = set(df.index[df["_search_text_norm"].str.contains(re.escape(product_name_key), regex=True, na=False)].tolist())
            if len(name_hits) == 1:
                matched.update(name_hits)
                match_method = "product_name_exact_or_unique_contains"

        if not matched:
            unmatched.append(
                {
                    "source_file": record.source_file,
                    "source_sheet": record.source_sheet,
                    "match_keys": "; ".join(record.match_keys[:8]),
                    "product_name": record.product_name,
                    "brand": record.brand,
                    "gross_weight_kg": record.gross_weight_kg,
                    "width_cm": record.width_cm,
                    "length_cm": record.length_cm,
                    "depth_cm": record.depth_cm,
                    "pc_gross_weight_kg": record.pc_gross_weight_kg,
                    "rbx_pcs": record.rbx_pcs,
                    "rbx_gross_weight_kg": record.rbx_gross_weight_kg,
                    "rbx_height_cm": record.rbx_height_cm,
                    "rbx_length_cm": record.rbx_length_cm,
                    "rbx_width_cm": record.rbx_width_cm,
                }
            )
            continue

        for idx in matched:
            tracked_cols = [
                "weight_value",
                "weight_g",
                "width_value",
                "length_value",
                "depth_value",
                "supplier_pc_gross_weight_kg",
                "supplier_rbx_pcs",
                "supplier_rbx_gross_weight_kg",
                "supplier_rbx_height_cm",
                "supplier_rbx_length_cm",
                "supplier_rbx_width_cm",
            ]
            before = {col: clean(df.at[idx, col]) if col in df.columns else "" for col in tracked_cols}
            changed = []
            weight_kg = record.gross_weight_kg or record.net_weight_kg
            supplier_weight_g = round(weight_kg * 1000, 3) if weight_kg else None
            existing_weight_value = existing_positive_number(df, idx, "weight_value")
            weight_conflict = bool(
                supplier_weight_g is not None
                and existing_weight_value is not None
                and not close_enough(existing_weight_value, supplier_weight_g)
            )
            if set_if_missing(df, idx, "weight_value", supplier_weight_g):
                df.at[idx, "weight_unit"] = "g"
                changed.append("weight_value")
                update_counts["weight_value"] += 1
            # Avoid creating inconsistent weight_value vs weight_g pairs. If weight_value
            # already exists and differs from supplier gross/net weight, leave weight_g untouched.
            can_update_weight_g = not weight_conflict
            if can_update_weight_g and set_if_missing(df, idx, "weight_g", supplier_weight_g):
                changed.append("weight_g")
                update_counts["weight_g"] += 1
            if set_if_missing(df, idx, "width_value", record.width_cm):
                df.at[idx, "width_unit"] = "cm"
                changed.append("width_value")
                update_counts["width_value"] += 1
            if set_if_missing(df, idx, "length_value", record.length_cm):
                df.at[idx, "length_unit"] = "cm"
                changed.append("length_value")
                update_counts["length_value"] += 1
            if set_if_missing(df, idx, "depth_value", record.depth_cm):
                df.at[idx, "depth_unit"] = "cm"
                changed.append("depth_value")
                update_counts["depth_value"] += 1
            logistics_updates = {
                "supplier_pc_gross_weight_kg": record.pc_gross_weight_kg,
                "supplier_rbx_pcs": record.rbx_pcs,
                "supplier_rbx_gross_weight_kg": record.rbx_gross_weight_kg,
                "supplier_rbx_height_cm": record.rbx_height_cm,
                "supplier_rbx_length_cm": record.rbx_length_cm,
                "supplier_rbx_width_cm": record.rbx_width_cm,
            }
            for column, value in logistics_updates.items():
                if set_if_missing(df, idx, column, value):
                    changed.append(column)
                    update_counts[column] += 1

            if changed:
                updated_rows.add(idx)
                source_note = f"{record.source_file} / {record.source_sheet}"
                if "supplier_data_source" not in df.columns:
                    df["supplier_data_source"] = ""
                existing_source = clean(df.at[idx, "supplier_data_source"])
                df.at[idx, "supplier_data_source"] = source_note if not existing_source else existing_source + " | " + source_note
                reports.append(
                    {
                        "row_index": idx + 2,
                        "product_id": df.at[idx, "product_id"] if "product_id" in df.columns else "",
                        "sku": df.at[idx, "sku"],
                        "product_name": df.at[idx, "product_name"],
                        "matched_supplier_product": record.product_name,
                        "supplier_brand": record.brand,
                        "source_file": record.source_file,
                        "source_sheet": record.source_sheet,
                        "match_method": match_method,
                        "match_keys": "; ".join(record.match_keys[:8]),
                        "changed_fields": "; ".join(changed),
                        "before_weight_value": before.get("weight_value", ""),
                        "after_weight_value": df.at[idx, "weight_value"] if "weight_value" in df.columns else "",
                        "before_weight_g": before.get("weight_g", ""),
                        "after_weight_g": df.at[idx, "weight_g"] if "weight_g" in df.columns else "",
                        "before_width_value": before.get("width_value", ""),
                        "after_width_value": df.at[idx, "width_value"] if "width_value" in df.columns else "",
                        "before_length_value": before.get("length_value", ""),
                        "after_length_value": df.at[idx, "length_value"] if "length_value" in df.columns else "",
                        "before_depth_value": before.get("depth_value", ""),
                        "after_depth_value": df.at[idx, "depth_value"] if "depth_value" in df.columns else "",
                        "before_supplier_pc_gross_weight_kg": before.get("supplier_pc_gross_weight_kg", ""),
                        "after_supplier_pc_gross_weight_kg": df.at[idx, "supplier_pc_gross_weight_kg"] if "supplier_pc_gross_weight_kg" in df.columns else "",
                        "before_supplier_rbx_pcs": before.get("supplier_rbx_pcs", ""),
                        "after_supplier_rbx_pcs": df.at[idx, "supplier_rbx_pcs"] if "supplier_rbx_pcs" in df.columns else "",
                        "before_supplier_rbx_gross_weight_kg": before.get("supplier_rbx_gross_weight_kg", ""),
                        "after_supplier_rbx_gross_weight_kg": df.at[idx, "supplier_rbx_gross_weight_kg"] if "supplier_rbx_gross_weight_kg" in df.columns else "",
                        "before_supplier_rbx_height_cm": before.get("supplier_rbx_height_cm", ""),
                        "after_supplier_rbx_height_cm": df.at[idx, "supplier_rbx_height_cm"] if "supplier_rbx_height_cm" in df.columns else "",
                        "before_supplier_rbx_length_cm": before.get("supplier_rbx_length_cm", ""),
                        "after_supplier_rbx_length_cm": df.at[idx, "supplier_rbx_length_cm"] if "supplier_rbx_length_cm" in df.columns else "",
                        "before_supplier_rbx_width_cm": before.get("supplier_rbx_width_cm", ""),
                        "after_supplier_rbx_width_cm": df.at[idx, "supplier_rbx_width_cm"] if "supplier_rbx_width_cm" in df.columns else "",
                        "notes": record.notes + (" | supplier_weight_differs_from_existing_weight_value" if weight_conflict else ""),
                    }
                )

    df = df.drop(
        columns=[
            "_sku_norm",
            "_code_norm",
            "_product_name_norm",
            "_title_norm",
            "_search_text",
            "_search_text_norm",
            *[c for c in df.columns if c.startswith("original_product_group_")],
        ]
    )
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    pd.DataFrame(reports).to_csv(REPORT_CSV, index=False, encoding="utf-8-sig")
    pd.DataFrame(unmatched).head(20000).to_csv(UNMATCHED_CSV, index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Products", index=False)
        pd.DataFrame(reports).to_excel(writer, sheet_name="Updated rows", index=False)
        pd.DataFrame(unmatched).head(5000).to_excel(writer, sheet_name="Unmatched sample", index=False)

    summary = {
        "input_file": str(input_path),
        "supplier_zip": str(ZIP_PATH),
        "output_csv": str(OUTPUT_CSV),
        "output_xlsx": str(OUTPUT_XLSX),
        "report_csv": str(REPORT_CSV),
        "unmatched_candidates_csv": str(UNMATCHED_CSV),
        "supplier_records_with_weight_or_dimensions": len(records),
        "updated_product_rows": len(updated_rows),
        "field_update_counts": update_counts,
        "report_rows": len(reports),
        "unmatched_supplier_records": len(unmatched),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
