import io
import json
import os
import re
import shutil
import zipfile
from datetime import datetime

import numpy as np
import pandas as pd


BASE_DIR = r"C:\Users\TommiHavukainen\OneDrive - Unikie Oy\Customer\Innoflame"
SALES_CSV = os.path.join(
    BASE_DIR,
    "outputs",
    "Innoflame_merged_sales_csv_source_with_L1_L2_L3_delivery_handling.csv",
)
SOURCE_ZIP = os.path.join(
    BASE_DIR,
    "tuoteryhmittely",
    "Innoflame_tuoteryhmittely_lahdedata.zip",
)
SOURCE_MEMBER = (
    "Innoflame_tuoteryhmittely_lahdedata/"
    "03_tuoteryhmittely_ja_auditointi/Innoflame_tuoteryhmittely.csv"
)
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

GROUP_COLS = [
    "product_group_l1_code",
    "product_group_l1_name",
    "product_group_l2_code",
    "product_group_l2_name",
    "product_group_l3_code",
    "product_group_l3_name",
]


def clean_code(value):
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none"}:
        return ""
    return text.upper()


def norm_text(value):
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def has_group(df):
    return (
        df["product_group_l3_code"].notna()
        & df["product_group_l3_name"].notna()
        & (df["product_group_l3_code"].astype(str).str.strip() != "")
        & (df["product_group_l3_name"].astype(str).str.strip() != "")
    )


def unique_group_map(df, key_cols):
    keep = df[df["_has_group"]].copy()
    keep = keep[keep[key_cols].replace("", np.nan).notna().all(axis=1)]
    if keep.empty:
        return {}

    uniqueness = (
        keep.groupby(key_cols)
        .agg(
            l1=("product_group_l1_code", "nunique"),
            l2=("product_group_l2_code", "nunique"),
            l3=("product_group_l3_code", "nunique"),
            l3_name=("product_group_l3_name", "nunique"),
        )
        .reset_index()
    )
    ok_keys = uniqueness[
        (uniqueness["l1"] == 1)
        & (uniqueness["l2"] == 1)
        & (uniqueness["l3"] == 1)
        & (uniqueness["l3_name"] == 1)
    ][key_cols]

    mapped = keep.merge(ok_keys, on=key_cols, how="inner")
    mapped = mapped.drop_duplicates(subset=key_cols, keep="first")
    return mapped.set_index(key_cols)[GROUP_COLS].to_dict("index")


def apply_map(df, remaining, method, key_func, mapping, audit_rows):
    keys = key_func(df)
    matched = remaining & keys.map(lambda key: key in mapping)
    if not matched.any():
        return remaining, 0

    for idx in df.index[matched]:
        group_values = mapping[keys.at[idx]]
        for col in GROUP_COLS:
            df.at[idx, col] = group_values[col]
        df.at[idx, "product_group_match_method"] = method
        audit_rows.append(
            {
                "row_index_zero_based": int(idx),
                "csv_row_number": int(idx) + 2,
                "method": method,
                "productcode": df.at[idx, "productcode"],
                "optioncode": df.at[idx, "optioncode"],
                "name": df.at[idx, "name"],
                "category": df.at[idx, "category"],
                "reference": df.at[idx, "reference"],
                "sales": df.at[idx, "sales"],
                **{col: df.at[idx, col] for col in GROUP_COLS},
            }
        )
    return remaining & ~matched, int(matched.sum())


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_csv = SALES_CSV.replace(
        ".csv", f".backup_before_missing_group_fill_{timestamp}.csv"
    )
    shutil.copy2(SALES_CSV, backup_csv)

    sales = pd.read_csv(SALES_CSV, low_memory=False)
    missing_before_mask = ~has_group(sales)
    missing_before = int(missing_before_mask.sum())

    source_cols = [
        "code",
        "sku",
        "product_name",
        "title_fi",
        "inventory_category",
        *GROUP_COLS,
    ]
    with zipfile.ZipFile(SOURCE_ZIP) as zf:
        grouping = pd.read_csv(
            io.BytesIO(zf.read(SOURCE_MEMBER)),
            usecols=lambda col: col in source_cols,
            low_memory=False,
        )

    for col in source_cols:
        if col not in grouping.columns:
            grouping[col] = np.nan

    grouping["_has_group"] = has_group(grouping)
    grouping["_code"] = grouping["code"].map(clean_code)
    grouping["_sku"] = grouping["sku"].map(clean_code)
    grouping["_cat"] = grouping["inventory_category"].map(norm_text)
    grouping["_name"] = grouping["product_name"].map(norm_text)
    grouping_title = grouping.copy()
    grouping_title["_name"] = grouping_title["title_fi"].map(norm_text)
    grouping_names = pd.concat([grouping, grouping_title], ignore_index=True)

    source_maps = {
        "source_zip_productcode_code": unique_group_map(grouping, ["_code"]),
        "source_zip_productcode_sku": unique_group_map(grouping, ["_sku"]),
        "source_zip_optioncode_code": unique_group_map(grouping, ["_code"]),
        "source_zip_optioncode_sku": unique_group_map(grouping, ["_sku"]),
        "source_zip_name_category_unique": unique_group_map(grouping_names, ["_name", "_cat"]),
        "source_zip_name_unique": unique_group_map(grouping_names, ["_name"]),
    }

    sales["_productcode_norm"] = sales["productcode"].map(clean_code)
    sales["_optioncode_norm"] = sales["optioncode"].map(clean_code)
    sales["_name_norm"] = sales["name"].map(norm_text)
    sales["_category_norm"] = sales["category"].map(norm_text)
    sales["_reference_norm"] = sales["reference"].map(norm_text)

    audit_rows = []
    remaining = missing_before_mask.copy()
    counts = {}

    source_steps = [
        ("source_zip_productcode_code", lambda df: df["_productcode_norm"], source_maps["source_zip_productcode_code"]),
        ("source_zip_productcode_sku", lambda df: df["_productcode_norm"], source_maps["source_zip_productcode_sku"]),
        ("source_zip_optioncode_code", lambda df: df["_optioncode_norm"], source_maps["source_zip_optioncode_code"]),
        ("source_zip_optioncode_sku", lambda df: df["_optioncode_norm"], source_maps["source_zip_optioncode_sku"]),
        (
            "source_zip_name_category_unique",
            lambda df: pd.Series(list(zip(df["_name_norm"], df["_category_norm"])), index=df.index),
            source_maps["source_zip_name_category_unique"],
        ),
        ("source_zip_name_unique", lambda df: df["_name_norm"], source_maps["source_zip_name_unique"]),
    ]

    for method, key_func, mapping in source_steps:
        remaining, count = apply_map(sales, remaining, method, key_func, mapping, audit_rows)
        counts[method] = count

    sales["_has_group_after_source"] = has_group(sales)
    sales_grouped = sales[sales["_has_group_after_source"]].copy()
    sales_maps = {
        "same_sales_productcode_unique": unique_group_map(sales_grouped.assign(_has_group=True), ["_productcode_norm"]),
        "same_sales_optioncode_unique": unique_group_map(sales_grouped.assign(_has_group=True), ["_optioncode_norm"]),
        "same_sales_name_category_reference_unique": unique_group_map(
            sales_grouped.assign(_has_group=True),
            ["_name_norm", "_category_norm", "_reference_norm"],
        ),
        "same_sales_name_category_unique": unique_group_map(
            sales_grouped.assign(_has_group=True), ["_name_norm", "_category_norm"]
        ),
        "same_sales_name_unique": unique_group_map(sales_grouped.assign(_has_group=True), ["_name_norm"]),
    }

    sales_steps = [
        ("same_sales_productcode_unique", lambda df: df["_productcode_norm"], sales_maps["same_sales_productcode_unique"]),
        ("same_sales_optioncode_unique", lambda df: df["_optioncode_norm"], sales_maps["same_sales_optioncode_unique"]),
        (
            "same_sales_name_category_reference_unique",
            lambda df: pd.Series(
                list(zip(df["_name_norm"], df["_category_norm"], df["_reference_norm"])),
                index=df.index,
            ),
            sales_maps["same_sales_name_category_reference_unique"],
        ),
        (
            "same_sales_name_category_unique",
            lambda df: pd.Series(list(zip(df["_name_norm"], df["_category_norm"])), index=df.index),
            sales_maps["same_sales_name_category_unique"],
        ),
        ("same_sales_name_unique", lambda df: df["_name_norm"], sales_maps["same_sales_name_unique"]),
    ]

    for method, key_func, mapping in sales_steps:
        remaining, count = apply_map(sales, remaining, method, key_func, mapping, audit_rows)
        counts[method] = count

    helper_cols = [
        "_productcode_norm",
        "_optioncode_norm",
        "_name_norm",
        "_category_norm",
        "_reference_norm",
        "_has_group_after_source",
    ]
    sales = sales.drop(columns=[col for col in helper_cols if col in sales.columns])
    missing_after = int((~has_group(sales)).sum())
    updated_rows = len(audit_rows)

    sales.to_csv(SALES_CSV, index=False, encoding="utf-8-sig")

    audit_csv = os.path.join(OUTPUT_DIR, "missing_product_group_fill_audit_rows.csv")
    audit_json = os.path.join(OUTPUT_DIR, "missing_product_group_fill_audit.json")
    pd.DataFrame(audit_rows).to_csv(audit_csv, index=False, encoding="utf-8-sig")

    summary = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "source_sales_csv": SALES_CSV,
        "backup_csv": backup_csv,
        "source_grouping_zip": SOURCE_ZIP,
        "source_grouping_member": SOURCE_MEMBER,
        "rows_total": int(len(sales)),
        "missing_group_rows_before": missing_before,
        "updated_rows": updated_rows,
        "missing_group_rows_after": missing_after,
        "counts_by_method": counts,
        "updated_sales_eur": float(
            pd.to_numeric(pd.DataFrame(audit_rows).get("sales", pd.Series(dtype=float)), errors="coerce")
            .fillna(0)
            .sum()
        ),
        "audit_rows_csv": audit_csv,
    }
    with open(audit_json, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
