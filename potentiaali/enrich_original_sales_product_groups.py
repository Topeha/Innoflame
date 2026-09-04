"""Write a product-group-enriched copy of the original sales CSV."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from run_current_customer_potential_new_sources import (
    PRODUCT_MASTER_PATH,
    EXCLUDED_PRODUCT_TERMS,
    UNKNOWN_PRODUCT_GROUP,
    _compact_product_name,
    _normalise_product_code,
    _normalise_product_name,
    enrich_product_groups_by_context,
    prepare_product_grouping,
)


BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_PATH = BASE_DIR / "GoSystems_sales_26_05_2026_summarized.csv"
OUTPUT_PATH = BASE_DIR / "GoSystems_sales_26_05_2026_summarized_with_product_groups.csv"
QUALITY_PATH = Path(__file__).resolve().parent / "original_sales_product_group_enrichment_quality.json"


def main() -> None:
    sales = pd.read_csv(INPUT_PATH, sep=None, engine="python")
    if "productcode" not in sales.columns or "name" not in sales.columns:
        raise ValueError("Original sales CSV must contain productcode and name columns.")

    work = sales.copy()
    grouping, _ = prepare_product_grouping(PRODUCT_MASTER_PATH)
    master = grouping[["sku", "product_name", "product_group_l1_name"]].copy()
    master["code"] = master["sku"].map(_normalise_product_code)
    master["name_key"] = master["product_name"].map(_normalise_product_name)
    master["compact_key"] = master["product_name"].map(_compact_product_name)
    master["group"] = master["product_group_l1_name"].fillna("").astype("string").str.strip()
    master = master.loc[master["code"].ne("") & master["group"].ne("")].drop_duplicates("code")

    def unique_map(key: str) -> dict[str, str]:
        counts = master.groupby(key)["group"].nunique()
        keys = set(counts.loc[counts.eq(1) & counts.index.to_series().ne("")].index)
        return master.loc[master[key].isin(keys)].drop_duplicates(key).set_index(key)["group"].to_dict()

    code_to_group = master.set_index("code")["group"].to_dict()
    name_to_group = unique_map("name_key")
    compact_to_group = unique_map("compact_key")
    group_word_to_groups: dict[str, set[str]] = {}
    pair_to_groups: dict[tuple[str, str], set[str]] = {}
    for row in master[["product_name", "group"]].drop_duplicates().itertuples(index=False):
        words = re.findall(r"[a-zåäö0-9]{3,}", _normalise_product_name(row.product_name))
        for pair in zip(words, words[1:]):
            pair_to_groups.setdefault(pair, set()).add(row.group)
    for group in master["group"].drop_duplicates():
        for word in re.findall(r"[a-zåäö0-9]{5,}", _normalise_product_name(group)):
            if word in {"muut", "other", "tuotteet", "products"}:
                continue
            aliases = {word}
            if word.endswith("t"):
                aliases.add(word[:-1])
            if word.endswith("it"):
                aliases.add(word[:-2] + "tti")
            for alias in aliases:
                group_word_to_groups.setdefault(alias, set()).add(group)

    work["sku"] = work["productcode"].fillna("").astype("string").str.strip()
    work["name_key"] = work["name"].map(_normalise_product_name)
    work["compact_key"] = work["name"].map(_compact_product_name)
    work["ProductGroup"] = work["sku"].map(code_to_group)
    work["ProductGroupSource"] = work["ProductGroup"].notna().map({True: "product_code", False: "unmatched"})
    missing = work["ProductGroup"].isna()
    work.loc[missing, "ProductGroup"] = work.loc[missing, "name_key"].map(name_to_group)
    work.loc[missing & work["ProductGroup"].notna(), "ProductGroupSource"] = "product_name"
    missing = work["ProductGroup"].isna()
    work.loc[missing, "ProductGroup"] = work.loc[missing, "compact_key"].map(compact_to_group)
    work.loc[missing & work["ProductGroup"].notna(), "ProductGroupSource"] = "normalized_name"
    name_text = work["name"].fillna("").astype("string").str.casefold()
    keyword = name_text.map(lambda value: any(term in value for term in EXCLUDED_PRODUCT_TERMS))
    missing = work["ProductGroup"].isna() & keyword
    work.loc[missing, "ProductGroup"] = "Muut pakkaukset"
    work.loc[missing, "ProductGroupSource"] = "transport_packaging_keyword"

    unique_names = work.loc[work["ProductGroup"].isna(), "name_key"].drop_duplicates()
    pair_groups = {}
    word_groups = {}
    explicit = {"lahjakortti": "Lahjakortit ja pääsyliput", "huppari": "Hupparit ja Collaget"}
    for key in unique_names:
        words = re.findall(r"[a-zåäö0-9]{3,}", key)
        candidates = {group for pair in zip(words, words[1:]) for group in pair_to_groups.get(pair, set())}
        if len(candidates) == 1:
            pair_groups[key] = next(iter(candidates))
            continue
        candidates = {group for word in words for group in group_word_to_groups.get(word, set())}
        if len(candidates) == 1:
            word_groups[key] = next(iter(candidates))
            continue
        for alias, group_name in explicit.items():
            if re.search(rf"(?<![a-zåäö0-9]){re.escape(alias)}(?![a-zåäö0-9])", key):
                word_groups[key] = next((group for group in master["group"] if group_name.casefold() in str(group).casefold()), group_name)
                break
    missing = work["ProductGroup"].isna()
    work.loc[missing, "ProductGroup"] = work.loc[missing, "name_key"].map(pair_groups)
    work.loc[missing & work["ProductGroup"].notna(), "ProductGroupSource"] = "product_group_pair"
    missing = work["ProductGroup"].isna()
    work.loc[missing, "ProductGroup"] = work.loc[missing, "name_key"].map(word_groups)
    work.loc[missing & work["ProductGroup"].notna(), "ProductGroupSource"] = "product_group_word"
    work["product_group_from_product_code"] = work["ProductGroup"].where(work["ProductGroupSource"].eq("product_code"))
    work["product_group_from_name"] = work["ProductGroup"].where(work["ProductGroupSource"].isin(["product_name", "normalized_name"]))
    work["product_group_from_keyword"] = work["ProductGroup"].where(work["ProductGroupSource"].eq("transport_packaging_keyword"))
    work["status_clean"] = work.get("status", pd.Series("", index=work.index)).astype("string").str.strip()
    work, context_quality = enrich_product_groups_by_context(work, grouping, use_fuzzy=False)
    context_missing = work["ProductGroup"].isna() & work["product_group_from_context"].notna()
    work.loc[context_missing, "ProductGroup"] = work.loc[context_missing, "product_group_from_context"]
    work.loc[context_missing, "ProductGroupSource"] = work.loc[context_missing, "product_group_enrichment_source"]
    work["ProductGroupIsUnknown"] = work["ProductGroup"].isna()
    work.loc[work["ProductGroupIsUnknown"], "ProductGroup"] = UNKNOWN_PRODUCT_GROUP
    work.loc[work["ProductGroupIsUnknown"], "ProductGroupSource"] = "unknown"
    work["ProductCodeEnriched"] = work["sku"].replace("", pd.NA)

    output_columns = list(sales.columns) + ["ProductCodeEnriched", "ProductGroup", "ProductGroupSource", "ProductGroupIsUnknown"]
    work[output_columns].to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    quality = {
        "input_rows": int(len(sales)),
        "output_rows": int(len(work)),
        "rows_with_product_group": int(work["ProductGroup"].notna().sum()),
        "rows_without_product_group": int(work["ProductGroup"].isna().sum()),
        "rows_assigned_unknown_product_group": int(work["ProductGroupIsUnknown"].sum()),
        "rows_with_product_group_percent": round(float(work["ProductGroup"].notna().mean() * 100), 2),
        "rows_by_source": work["ProductGroupSource"].value_counts(dropna=False).to_dict(),
        "output_path": str(OUTPUT_PATH),
        "context_quality": context_quality.set_index("metric")["value"].to_dict(),
    }
    QUALITY_PATH.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(quality, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
