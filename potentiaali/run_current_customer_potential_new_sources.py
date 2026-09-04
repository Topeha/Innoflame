"""Run the current-customer potential model with the 2026 source files.

This adapter keeps the calculation model unchanged while normalizing the new
product-level sales CSV and the new Finnish product master for it in memory.
Only this potentiaali folder is changed by this integration.
"""

from __future__ import annotations

import importlib.util
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
POTENTIAL_DIR = Path(__file__).resolve().parent
RAW_SALES_PATH = ROOT / "GoSystems_sales_26_05_2026_summarized.csv"
ENRICHED_SALES_PATH = ROOT / "GoSystems_sales_26_05_2026_summarized_with_product_groups.csv"
SALES_PATH = ENRICHED_SALES_PATH if ENRICHED_SALES_PATH.exists() else RAW_SALES_PATH
PROFINDER_PATH = POTENTIAL_DIR / "haku_Prospektointimasterlista_2026-08-12.xlsx"
PRODUCT_MASTER_PATH = POTENTIAL_DIR / "INNOFLAME-TUOTELISTA-TUOTERYHMITTELY.xlsx"
ACCOUNTS_PATH = POTENTIAL_DIR / "Account_20.05.2026_combined_with_profinder.xlsx"
CRM_PATH = POTENTIAL_DIR / "CRM_potentials_03.06.2026_03.07.2026 (1).xlsx"
EXCLUSION_PATH = POTENTIAL_DIR / "Netvisor asiakastiedot 6-2026.xlsx"
MODEL_PATH = ROOT / "prospektointi" / "prospect_model.py"
V3_PATH = ROOT / "two_stage_potential_model" / "v3_recent_weighted_current_model" / "innoflame_all_accounts_model_v3.py"
RUNNER_PATH = ROOT / "prospektointi" / "run_current_customer_potential.py"
GO_KEEP_COMPLETED_STATUSES = {"processed", "archived", "ready to archive"}

EXCLUDED_PRODUCT_TERMS = (
    "kustannus", "cost", "freight", "delivery", "transport", "shipping",
    "pakkauskustannus", "kuljetus", "kuljetuspakkaus", "kuljetuslaatikko",
    "kuljetusalusta", "lava", "rahti", "toimitusmaksu", "käsittelymaksu",
    "pakkaaminen", "express", "toimitus",
)
PACKAGING_TRANSPORT_GROUP = "Muut pakkaukset"
UNKNOWN_PRODUCT_GROUP = "Tuntematon tuoteryhmä"
PRODUCT_GROUP_ALIAS_PATH = POTENTIAL_DIR / "product_group_aliases.csv"
EXPLICIT_PRODUCT_GROUP_WORD_ALIASES = {
    "lahjakortti": "Lahjakortit ja pääsyliput",
    "huppari": "Hupparit ja Collaget",
}


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load model module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype("string").str.replace(",", ".", regex=False), errors="coerce")


def prepare_sales(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_csv(path, sep=None, engine="python")
    raw.columns = [str(column).lstrip("\ufeff").strip() for column in raw.columns]
    account_col = "account_id" if "account_id" in raw.columns else "accountid"
    date_col = "created_at" if "created_at" in raw.columns else "sold_at"
    value_col = "total_value" if "total_value" in raw.columns else "sales"
    required = {account_col, "status", date_col, value_col}
    missing = sorted(required - set(raw.columns))
    if missing:
        raise ValueError(f"Sales CSV is missing required columns: {missing}")

    frame = raw.copy()
    frame["account_id"] = pd.to_numeric(frame[account_col], errors="coerce")
    frame["total_value"] = number(frame[value_col]).fillna(0.0)
    frame["created_at_dt"] = pd.to_datetime(frame[date_col], errors="coerce", dayfirst=True, utc=True).dt.tz_convert(None)
    frame["created_year_month"] = frame["created_at_dt"].dt.to_period("M").astype("string")
    frame["status_clean"] = frame["status"].astype("string").str.strip()
    if "sku" not in frame.columns:
        sku_source = "ProductCodeEnriched" if "ProductCodeEnriched" in frame.columns else "productcode"
        if sku_source in frame.columns:
            frame["sku"] = frame[sku_source]
    if "ProductGroup" in frame.columns:
        source_group = frame["ProductGroup"].where(frame["ProductGroup"].ne(UNKNOWN_PRODUCT_GROUP))
        frame["product_group_from_source"] = source_group
    is_gosales = frame["source_file"].astype("string").str.casefold().str.contains("gosales", na=False) if "source_file" in frame.columns else pd.Series(True, index=frame.index)
    is_gokeep = frame["source_file"].astype("string").str.casefold().str.contains("gokeep", na=False) if "source_file" in frame.columns else pd.Series(False, index=frame.index)
    completed_sale = frame["status_clean"].str.casefold().eq("invoiced") & is_gosales
    completed_gokeep = frame["status_clean"].str.casefold().isin(GO_KEEP_COMPLETED_STATUSES) & is_gokeep
    included = frame.loc[
        (completed_sale | completed_gokeep)
        & frame["account_id"].notna()
        & frame["created_at_dt"].notna()
    ].copy()
    # Zero and negative sales must not affect potential, group shares, or recommendations.
    included["included_for_model"] = included["total_value"].gt(0)
    included = included.loc[included["included_for_model"]].copy()
    return included, frame


def prepare_product_grouping(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_excel(path, sheet_name="Tuotteet")
    required = {"Tuotekoodi", "Tuoteryhmä"}
    missing = sorted(required - set(raw.columns))
    if missing:
        raise ValueError(f"Product master is missing required columns: {missing}")

    group_col = "Koko ryhmäpolku" if "Koko ryhmäpolku" in raw.columns else "Tuoteryhmä"
    grouping = pd.DataFrame(
        {
            "sku": raw["Tuotekoodi"].fillna("").astype("string").str.strip(),
            "product_name": raw.get("Tuotteen nimi", pd.Series("", index=raw.index)).fillna("").astype("string").str.strip(),
            "product_description": raw.get("Description", raw.get("Kuvaus", pd.Series("", index=raw.index))).fillna("").astype("string").str.strip(),
            "product_group_l1_code": raw[group_col].fillna("").astype("string").str.strip(),
            "product_group_l1_name": raw[group_col].fillna("").astype("string").str.strip(),
        }
    )
    grouping = grouping.loc[grouping["sku"].ne("")].drop_duplicates("sku")
    quality = pd.DataFrame(
        [
            {"metric": "product_master_rows", "value": len(raw)},
            {"metric": "product_master_unique_product_codes", "value": grouping["sku"].nunique()},
            {"metric": "product_master_missing_product_groups", "value": int(grouping["product_group_l1_name"].eq("").sum())},
            {"metric": "product_master_group_column", "value": group_col},
        ]
    )
    return grouping, quality


def _normalise_product_name(value: object) -> str:
    """Create a conservative key for exact product-name matching."""
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _compact_product_name(value: object) -> str:
    return re.sub(r"[^a-z0-9åäö]+", "", _normalise_product_name(value))


def enrich_product_groups_by_product_code(
    sales: pd.DataFrame,
    product_grouping: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Use ProductCode as the primary and authoritative master lookup."""
    frame = sales.copy()
    if "sku" not in frame.columns:
        frame["sku"] = ""
    frame["sku"] = frame["sku"].fillna("").astype("string").str.strip()
    if "product_group_from_product_code" not in frame.columns:
        frame["product_group_from_product_code"] = pd.NA
    master = product_grouping.copy()
    master["product_code"] = master["sku"].map(_normalise_product_code)
    master["product_group"] = master["product_group_l1_name"].fillna("").astype("string").str.strip()
    master = master.loc[master["product_code"].ne("") & master["product_group"].ne("")].copy()
    code_counts = master.groupby("product_code")["product_group"].nunique()
    unique_codes = set(code_counts.loc[code_counts.eq(1)].index)
    lookup = master.loc[master["product_code"].isin(unique_codes)].drop_duplicates("product_code").set_index("product_code")

    frame["product_group_from_product_code"] = frame["sku"].map(lookup["product_group"])
    frame["product_code_match"] = "missing_code"
    frame.loc[frame["sku"].ne(""), "product_code_match"] = "unmatched_code"
    frame.loc[frame["sku"].isin(unique_codes), "product_code_match"] = "unique_master_code"
    frame.loc[frame["sku"].isin(code_counts.loc[code_counts.gt(1)].index), "product_code_match"] = "ambiguous_code"

    invoiced = frame.get("status_clean", pd.Series("", index=frame.index)).astype("string").str.casefold().eq("invoiced")
    quality = pd.DataFrame([
        {"metric": "product_code_master_unique_keys", "value": int(len(unique_codes))},
        {"metric": "sales_rows_matched_by_product_code", "value": int((frame["product_code_match"] == "unique_master_code").sum())},
        {"metric": "sales_rows_unmatched_product_code", "value": int((frame["product_code_match"] == "unmatched_code").sum())},
        {"metric": "sales_rows_ambiguous_product_code", "value": int((frame["product_code_match"] == "ambiguous_code").sum())},
        {"metric": "invoiced_rows_matched_by_product_code", "value": int(((frame["product_code_match"] == "unique_master_code") & invoiced).sum())},
    ])
    return frame, quality


def enrich_missing_product_codes_by_name(
    sales: pd.DataFrame,
    product_grouping: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fill missing sales SKUs when the product name maps uniquely to master.

    The match is intentionally exact after Unicode/whitespace normalization.
    Ambiguous names and names absent from the master remain untouched so that
    the model never assigns a potentially wrong product group.
    """
    frame = sales.copy()
    if "sku" not in frame.columns:
        frame["sku"] = ""
    frame["sku"] = frame["sku"].fillna("").astype("string").str.strip()
    if "product_group_from_product_code" not in frame.columns:
        frame["product_group_from_product_code"] = pd.NA
    needs_group = frame["product_group_from_product_code"].isna()
    name_col = next((column for column in ("name", "ProductName", "product_name") if column in frame.columns), None)
    if name_col is None:
        return frame, pd.DataFrame([{
            "metric": "product_name_enrichment_status",
            "value": "sales product-name column not found",
        }])

    master = product_grouping.copy()
    master["name_key"] = master["product_name"].map(_normalise_product_name)
    master["product_code"] = master["sku"].map(_normalise_product_code)
    master["product_group"] = master["product_group_l1_name"].fillna("").astype("string").str.strip()
    master = master.loc[master["name_key"].ne("") & master["product_code"].ne("") & master["product_group"].ne("")].copy()
    name_counts = master.groupby("name_key")["product_code"].nunique()
    unique_names = set(name_counts.loc[name_counts.eq(1)].index)
    master_lookup = master.loc[master["name_key"].isin(unique_names)].drop_duplicates("name_key").set_index("name_key")

    sales_name_key = frame[name_col].map(_normalise_product_name)
    missing_code = frame["sku"].eq("")
    matched_name = needs_group & sales_name_key.isin(unique_names)
    frame["product_name_match"] = "not_needed"
    frame.loc[needs_group, "product_name_match"] = "unmatched"
    frame.loc[needs_group & sales_name_key.isin(name_counts.loc[name_counts.gt(1)].index), "product_name_match"] = "ambiguous"
    frame.loc[matched_name, "product_name_match"] = "unique_master_name"
    frame.loc[matched_name, "sku"] = sales_name_key.loc[matched_name].map(master_lookup["product_code"])
    frame["product_group_from_name"] = sales_name_key.map(master_lookup["product_group"])

    # A punctuation/spacing-normalized name is the next safe fallback.
    master["compact_name_key"] = master["product_name"].map(_compact_product_name)
    compact_counts = master.groupby("compact_name_key")["product_code"].nunique()
    compact_names = set(compact_counts.loc[compact_counts.eq(1) & compact_counts.index.to_series().ne("")].index)
    compact_lookup = master.loc[master["compact_name_key"].isin(compact_names)].drop_duplicates("compact_name_key").set_index("compact_name_key")
    compact_keys = frame[name_col].map(_compact_product_name)
    compact_match = needs_group & frame["sku"].eq("") & compact_keys.isin(compact_names)
    frame.loc[compact_match, "sku"] = compact_keys.loc[compact_match].map(compact_lookup["product_code"])
    frame.loc[compact_match, "product_group_from_name"] = compact_keys.loc[compact_match].map(compact_lookup["product_group"])
    frame.loc[compact_match, "product_name_match"] = "normalized_master_name"

    frame["product_group_from_keyword"] = pd.NA
    product_name_text = frame[name_col].fillna("").astype("string").str.casefold()
    keyword_match = product_name_text.map(lambda value: any(term in value for term in EXCLUDED_PRODUCT_TERMS))
    keyword_match = keyword_match & needs_group & frame["product_group_from_name"].isna()
    frame.loc[keyword_match, "product_group_from_keyword"] = PACKAGING_TRANSPORT_GROUP
    frame.loc[keyword_match & frame["product_group_from_name"].isna(), "product_name_match"] = "transport_packaging_keyword"

    # Match a meaningful product-name word to a unique product-group word.
    frame["product_group_from_group_word"] = pd.NA
    leaf_group_map: dict[str, set[str]] = {}
    for group in master["product_group"].dropna().astype(str).drop_duplicates():
        leaf = _normalise_product_name(re.split(r"\s*>\s*|\s*/\s*|\s*\|\s*", group)[-1])
        if leaf:
            leaf_group_map.setdefault(leaf, set()).add(group)
    explicit_group_map = {
        alias: next(iter(leaf_group_map[_normalise_product_name(target)]))
        for alias, target in EXPLICIT_PRODUCT_GROUP_WORD_ALIASES.items()
        if _normalise_product_name(target) in leaf_group_map
    }
    explicit_group_match = pd.Series(False, index=frame.index)
    for alias, group in explicit_group_map.items():
        alias_match = needs_group & frame["product_group_from_name"].isna() & frame["product_group_from_keyword"].isna()
        alias_match = alias_match & sales_name_key.str.contains(rf"(?<![a-zåäö0-9]){re.escape(alias)}(?![a-zåäö0-9])", regex=True, na=False)
        frame.loc[alias_match, "product_group_from_group_word"] = group
        frame.loc[alias_match, "product_name_match"] = "explicit_product_group_alias"
        explicit_group_match = explicit_group_match | alias_match

    frame["product_group_from_group_pair"] = pd.NA
    pair_group_map: dict[tuple[str, str], set[str]] = {}
    for product_name, group in master[["product_name", "product_group"]].drop_duplicates().itertuples(index=False):
        words = re.findall(r"[a-zåäö0-9]{3,}", _normalise_product_name(product_name))
        for pair in zip(words, words[1:]):
            pair_group_map.setdefault(pair, set()).add(group)
    pair_group_match = pd.Series(False, index=frame.index)
    for row_index in frame.index[needs_group & frame["product_group_from_name"].isna() & frame["product_group_from_keyword"].isna() & ~explicit_group_match]:
        product_words = re.findall(r"[a-zåäö0-9]{3,}", sales_name_key.loc[row_index])
        candidate_groups = {group for pair in zip(product_words, product_words[1:]) for group in pair_group_map.get(pair, set())}
        if len(candidate_groups) == 1:
            frame.loc[row_index, "product_group_from_group_pair"] = next(iter(candidate_groups))
            frame.loc[row_index, "product_name_match"] = "product_group_pair"
            pair_group_match.loc[row_index] = True

    group_words: list[tuple[str, str]] = []
    ignored_group_words = {"ja", "sekä", "muut", "other", "tuotteet", "products"}
    for group in master["product_group"].dropna().astype(str).drop_duplicates():
        for word in re.findall(r"[a-zåäö0-9]{5,}", _normalise_product_name(group)):
            if word not in ignored_group_words:
                group_words.append((word, group))
    group_word_match = pd.Series(False, index=frame.index)
    for row_index in frame.index[needs_group & frame["product_group_from_name"].isna() & frame["product_group_from_keyword"].isna() & ~explicit_group_match & ~pair_group_match]:
        product_words = re.findall(r"[a-zåäö0-9]{5,}", sales_name_key.loc[row_index])
        candidate_groups: set[str] = set()
        for product_word in product_words:
            for group_word, group in group_words:
                if SequenceMatcher(None, product_word, group_word).ratio() >= 0.88:
                    candidate_groups.add(group)
        if len(candidate_groups) == 1:
            frame.loc[row_index, "product_group_from_group_word"] = next(iter(candidate_groups))
            frame.loc[row_index, "product_name_match"] = "product_group_word"
            group_word_match.loc[row_index] = True

    # Category and description can provide a group even when no product code exists.
    frame["product_group_from_description"] = pd.NA
    description_col = next((column for column in ("description", "Description", "product_description") if column in frame.columns), None)
    description_match = pd.Series(False, index=frame.index)
    if description_col and "product_description" in master.columns:
        master["description_key"] = master["product_description"].map(_normalise_product_name)
        description_counts = master.groupby("description_key")["product_code"].nunique()
        description_keys = set(description_counts.loc[description_counts.eq(1) & description_counts.index.to_series().ne("")].index)
        description_lookup = master.loc[master["description_key"].isin(description_keys)].drop_duplicates("description_key").set_index("description_key")
        sales_description_keys = frame[description_col].map(_normalise_product_name)
        description_match = frame["product_group_from_product_code"].isna() & frame["product_group_from_name"].isna() & sales_description_keys.isin(description_keys)
        frame.loc[description_match, "product_group_from_description"] = sales_description_keys.loc[description_match].map(description_lookup["product_group"])
        frame.loc[description_match, "sku"] = sales_description_keys.loc[description_match].map(description_lookup["product_code"])
        frame.loc[description_match, "product_name_match"] = "description_exact"

    frame["product_group_from_category"] = pd.NA
    category_col = next((column for column in ("category", "ProductGroup", "product_group") if column in frame.columns), None)
    if category_col:
        group_by_alias: dict[str, set[str]] = {}
        for group in master["product_group"].dropna().astype(str):
            for alias in re.split(r"\s*>\s*|\s*/\s*|\s*\|\s*", group):
                key = _normalise_product_name(alias)
                if key:
                    group_by_alias.setdefault(key, set()).add(group)
        category_map = {key: next(iter(groups)) for key, groups in group_by_alias.items() if len(groups) == 1}
        category_keys = frame[category_col].map(_normalise_product_name)
        category_match = frame["product_group_from_product_code"].isna() & frame["product_group_from_name"].isna() & category_keys.isin(category_map)
        frame.loc[category_match, "product_group_from_category"] = category_keys.loc[category_match].map(category_map)
        frame.loc[category_match, "product_name_match"] = "category_exact"

    # High-confidence fuzzy matches are accepted; lower-confidence matches stay review-only.
    token_index: dict[str, set[str]] = {}
    for name_key in master_lookup.index:
        for token in re.findall(r"[a-z0-9åäö]{4,}", name_key):
            token_index.setdefault(token, set()).add(name_key)
    fuzzy_candidates: dict[str, tuple[str, float]] = {}
    unresolved_keys = sales_name_key[needs_group & frame["sku"].eq("")].drop_duplicates()
    for sales_key in unresolved_keys:
        candidate_keys: set[str] = set()
        for token in re.findall(r"[a-z0-9åäö]{4,}", sales_key):
            candidate_keys.update(token_index.get(token, set()))
        scored = sorted(((key, SequenceMatcher(None, sales_key, key).ratio()) for key in candidate_keys), key=lambda item: item[1], reverse=True)
        if scored and scored[0][1] >= 0.93 and (len(scored) == 1 or scored[0][1] - scored[1][1] >= 0.03):
            fuzzy_candidates[sales_key] = scored[0]
    fuzzy_match = needs_group & frame["sku"].eq("") & sales_name_key.isin(fuzzy_candidates)
    if fuzzy_candidates:
        frame.loc[fuzzy_match, "sku"] = sales_name_key.loc[fuzzy_match].map(lambda key: master_lookup.loc[fuzzy_candidates[key][0], "product_code"])
        frame.loc[fuzzy_match, "product_group_from_name"] = sales_name_key.loc[fuzzy_match].map(lambda key: master_lookup.loc[fuzzy_candidates[key][0], "product_group"])
        frame.loc[fuzzy_match, "product_name_match"] = "fuzzy_high_confidence"

    audit = pd.DataFrame({
        "source_row": frame.index,
        "status": frame["status"].astype("string") if "status" in frame.columns else "",
        "product_name": frame[name_col].astype("string"),
        "product_name_key": sales_name_key,
        "product_code_after_enrichment": frame["sku"],
        "product_group_from_name": frame["product_group_from_name"],
        "match_status": frame["product_name_match"],
    })
    audit = audit.loc[needs_group].copy()
    invoiced = frame.get("status_clean", pd.Series("", index=frame.index)).astype("string").str.casefold().eq("invoiced")
    quality = pd.DataFrame([
        {"metric": "missing_product_code_before_name_enrichment", "value": int(missing_code.sum())},
        {"metric": "product_codes_filled_by_product_name", "value": int(matched_name.sum())},
        {"metric": "product_groups_filled_by_product_name", "value": int(matched_name.sum())},
        {"metric": "product_codes_filled_by_normalized_name", "value": int(compact_match.sum())},
        {"metric": "product_codes_filled_by_fuzzy_high_confidence_name", "value": int(fuzzy_match.sum())},
        {"metric": "product_codes_filled_by_description", "value": int(description_match.sum())},
        {"metric": "product_groups_filled_by_category", "value": int((frame["product_group_from_category"].notna()).sum())},
        {"metric": "product_groups_filled_by_group_word", "value": int(group_word_match.sum())},
        {"metric": "product_groups_filled_by_explicit_group_alias", "value": int(explicit_group_match.sum())},
        {"metric": "product_groups_filled_by_group_pair", "value": int(pair_group_match.sum())},
        {"metric": "product_groups_assigned_to_muut_pakkaukset_by_name", "value": int(keyword_match.sum())},
        {"metric": "missing_product_code_after_name_enrichment", "value": int(frame["sku"].eq("").sum())},
        {"metric": "invoiced_missing_product_code_before_name_enrichment", "value": int((missing_code & invoiced).sum())},
        {"metric": "invoiced_product_codes_filled_by_product_name", "value": int((matched_name & invoiced).sum())},
        {"metric": "invoiced_missing_product_code_after_name_enrichment", "value": int((frame["sku"].eq("") & invoiced).sum())},
        {"metric": "product_name_matches_ambiguous", "value": int((audit["match_status"] == "ambiguous").sum())},
        {"metric": "product_name_matches_unmatched", "value": int((audit["match_status"] == "unmatched").sum())},
        {"metric": "product_name_master_unique_keys", "value": int(len(unique_names))},
    ])
    return frame, quality


def enrich_product_groups_by_context(
    sales: pd.DataFrame,
    product_grouping: pd.DataFrame,
    *,
    use_fuzzy: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Use aliases, order context, customer history, and safe fuzzy matches."""
    frame = sales.copy()
    if "product_group_from_product_code" not in frame.columns:
        frame["product_group_from_product_code"] = pd.NA
    if "product_group_from_name" not in frame.columns:
        frame["product_group_from_name"] = pd.NA
    if "product_group_from_keyword" not in frame.columns:
        frame["product_group_from_keyword"] = pd.NA
    name_col = next((column for column in ("name", "ProductName", "product_name") if column in frame.columns), None)
    if name_col is None:
        return frame, pd.DataFrame(columns=["metric", "value"])
    name_key = frame[name_col].map(_normalise_product_name)
    frame["product_group_from_context"] = pd.NA
    frame["product_group_enrichment_source"] = "unmatched"
    resolved = frame["product_group_from_product_code"].combine_first(frame["product_group_from_name"])
    resolved = resolved.combine_first(frame["product_group_from_keyword"])
    if "product_group_from_source" in frame.columns:
        resolved = resolved.combine_first(frame["product_group_from_source"])

    # Optional local alias table: name, alias or product_name -> product_group.
    alias_map: dict[str, str] = {
        _normalise_product_name(alias): group
        for alias, group in EXPLICIT_PRODUCT_GROUP_WORD_ALIASES.items()
    }
    if PRODUCT_GROUP_ALIAS_PATH.exists():
        aliases = pd.read_csv(PRODUCT_GROUP_ALIAS_PATH)
        alias_col = next((column for column in ("alias", "name", "product_name") if column in aliases.columns), None)
        group_col = next((column for column in ("product_group", "ProductGroup") if column in aliases.columns), None)
        if alias_col and group_col:
            alias_map.update({
                _normalise_product_name(row[alias_col]): str(row[group_col]).strip()
                for _, row in aliases.dropna(subset=[alias_col, group_col]).iterrows()
                if _normalise_product_name(row[alias_col]) and str(row[group_col]).strip()
            })
    alias_match = resolved.isna() & name_key.isin(alias_map)
    frame.loc[alias_match, "product_group_from_context"] = name_key.loc[alias_match].map(alias_map)
    frame.loc[alias_match, "product_group_enrichment_source"] = "alias"
    resolved = resolved.combine_first(frame["product_group_from_context"])

    # Reuse a group seen elsewhere in the same order/reference only when unique.
    def unique_context_map(key_col: str) -> dict[str, str]:
        if key_col not in frame.columns:
            return {}
        key = frame[key_col].fillna("").astype("string").str.strip()
        valid = key.ne("") & resolved.notna()
        counts = pd.DataFrame({"key": key[valid], "group": resolved[valid]}).groupby("key")["group"].nunique()
        unique = set(counts.loc[counts.eq(1)].index)
        return pd.DataFrame({"key": key[valid], "group": resolved[valid]}).loc[lambda d: d["key"].isin(unique)].drop_duplicates("key").set_index("key")["group"].to_dict()

    for column, source in (("reference", "reference_context"), ("order", "order_context")):
        context_map = unique_context_map(column)
        if not context_map:
            continue
        key = frame[column].fillna("").astype("string").str.strip()
        match = resolved.isna() & key.isin(context_map)
        frame.loc[match, "product_group_from_context"] = key.loc[match].map(context_map)
        frame.loc[match, "product_group_enrichment_source"] = source
        resolved = resolved.combine_first(frame["product_group_from_context"])

    # Historical customer mapping: same account and product name, unique group.
    account_col = next((column for column in ("accountid", "account_id") if column in frame.columns), None)
    if account_col:
        account_key = frame[account_col].fillna("").astype("string").str.strip() + "|" + name_key
        valid = account_key.ne("|") & resolved.notna()
        history = pd.DataFrame({"key": account_key[valid], "group": resolved[valid]}).groupby("key")["group"].nunique()
        unique = set(history.loc[history.eq(1)].index)
        history_map = pd.DataFrame({"key": account_key[valid], "group": resolved[valid]}).loc[lambda d: d["key"].isin(unique)].drop_duplicates("key").set_index("key")["group"].to_dict()
        match = resolved.isna() & account_key.isin(history_map)
        frame.loc[match, "product_group_from_context"] = account_key.loc[match].map(history_map)
        frame.loc[match, "product_group_enrichment_source"] = "customer_history"
        resolved = resolved.combine_first(frame["product_group_from_context"])

    # Fuzzy suggestions are accepted only for a clear, high-confidence match.
    master = product_grouping.copy()
    master["name_key"] = master["product_name"].map(_normalise_product_name)
    master["group"] = master["product_group_l1_name"].fillna("").astype("string").str.strip()
    master = master.loc[master["name_key"].ne("") & master["group"].ne("")].drop_duplicates("name_key")
    token_index: dict[str, set[str]] = {}
    for key in master["name_key"]:
        for token in re.findall(r"[a-zåäö0-9]{4,}", key):
            token_index.setdefault(token, set()).add(key)
    fuzzy_map: dict[str, str] = {}
    if use_fuzzy:
        for key in name_key[resolved.isna()].drop_duplicates():
            candidates = {candidate for token in re.findall(r"[a-zåäö0-9]{4,}", key) for candidate in token_index.get(token, set())}
            scored = sorted(((candidate, SequenceMatcher(None, key, candidate).ratio()) for candidate in candidates), key=lambda item: item[1], reverse=True)
            if scored and scored[0][1] >= 0.93 and (len(scored) == 1 or scored[0][1] - scored[1][1] >= 0.03):
                fuzzy_map[key] = master.loc[master["name_key"].eq(scored[0][0]), "group"].iloc[0]
    match = resolved.isna() & name_key.isin(fuzzy_map)
    frame.loc[match, "product_group_from_context"] = name_key.loc[match].map(fuzzy_map)
    frame.loc[match, "product_group_enrichment_source"] = "fuzzy_high_confidence"
    resolved = resolved.combine_first(frame["product_group_from_context"])

    frame["product_group_unknown"] = resolved.isna()
    quality = pd.DataFrame([
        {"metric": "product_groups_filled_by_alias", "value": int(alias_match.sum())},
        {"metric": "product_groups_filled_by_reference_or_order", "value": int(frame["product_group_enrichment_source"].isin(["reference_context", "order_context"]).sum())},
        {"metric": "product_groups_filled_by_customer_history", "value": int((frame["product_group_enrichment_source"] == "customer_history").sum())},
        {"metric": "product_groups_filled_by_fuzzy_high_confidence", "value": int((frame["product_group_enrichment_source"] == "fuzzy_high_confidence").sum())},
        {"metric": "rows_assigned_unknown_product_group", "value": int(frame["product_group_unknown"].sum())},
    ])
    return frame, quality


def _product_text(frame: pd.DataFrame) -> pd.Series:
    columns = [column for column in ("sku", "product_name", "product_description", "lowest_product_group_name") if column in frame.columns]
    text = frame[columns].fillna("").astype("string").agg(" ".join, axis=1).str.casefold()
    return text


def _normalise_product_code(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().upper()


def build_product_recommendations(
    customer_potential: pd.DataFrame,
    sales: pd.DataFrame,
    accounts: pd.DataFrame,
    product_grouping: pd.DataFrame,
    *,
    max_recommendations_per_customer: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create product-level current/new recommendations with auditable rules."""
    master = product_grouping.copy()
    master["product_code"] = master["sku"].map(_normalise_product_code)
    master["product_name"] = master["product_name"].fillna("").astype("string").str.strip()
    master["product_group"] = master["lowest_product_group_name"].fillna("").astype("string").str.strip()
    master = master.loc[master["product_code"].ne("")].drop_duplicates("product_code")
    master["excluded_from_recommendations"] = _product_text(master).map(
        lambda value: any(term in value for term in EXCLUDED_PRODUCT_TERMS)
    )

    account_frame = accounts.copy()
    account_id_col = runner_resolve_column(account_frame, ["id", "account_id", "account id"])
    business_col = runner_resolve_column(account_frame, ["business id", "business_id", "y tunnus", "y-tunnus"])
    if account_id_col is None or business_col is None:
        raise ValueError("Accounts file must contain account ID and business ID columns.")
    account_keys = account_frame[[account_id_col, business_col]].copy()
    account_keys.columns = ["account_id", "business_id"]
    account_keys["account_id"] = pd.to_numeric(account_keys["account_id"], errors="coerce")
    account_keys["business_id"] = account_keys["business_id"].map(runner_normalize_business_id)
    account_keys = account_keys.dropna(subset=["account_id", "business_id"]).drop_duplicates("account_id")

    sales_frame = sales.copy()
    sales_frame["account_id"] = pd.to_numeric(sales_frame["account_id"], errors="coerce")
    sales_frame["product_code"] = sales_frame.get("sku", pd.Series("", index=sales_frame.index)).map(_normalise_product_code)
    sales_frame["sales_eur"] = pd.to_numeric(sales_frame["total_value"], errors="coerce").fillna(0.0)
    sales_frame = sales_frame.merge(account_keys, on="account_id", how="left")
    sales_frame = sales_frame.merge(master[["product_code", "product_name", "product_group"]], on="product_code", how="left")
    for column in ("product_group_from_product_code", "product_group_from_name", "product_group_from_description", "product_group_from_category", "product_group_from_keyword", "product_group_from_group_pair", "product_group_from_group_word"):
        if column not in sales_frame.columns:
            sales_frame[column] = pd.NA
    if "product_group_from_context" not in sales_frame.columns:
        sales_frame["product_group_from_context"] = pd.NA
    if "product_group_from_source" not in sales_frame.columns:
        sales_frame["product_group_from_source"] = pd.NA
    sales_frame["product_group"] = (
        sales_frame["product_group_from_product_code"]
        .combine_first(sales_frame["product_group_from_name"])
        .combine_first(sales_frame["product_group_from_description"])
        .combine_first(sales_frame["product_group_from_category"])
        .combine_first(sales_frame["product_group_from_keyword"])
        .combine_first(sales_frame["product_group_from_group_pair"])
        .combine_first(sales_frame["product_group_from_group_word"])
        .combine_first(sales_frame["product_group_from_context"])
        .combine_first(sales_frame["product_group_from_source"])
        .fillna(UNKNOWN_PRODUCT_GROUP)
        .combine_first(sales_frame["product_group"])
    )
    sales_frame = sales_frame.loc[sales_frame["business_id"].notna()].copy()

    sold_product_stats = sales_frame.loc[sales_frame["product_code"].ne("")].groupby(["product_code", "product_name", "product_group"], as_index=False).agg(
        total_product_sales_eur=("sales_eur", "sum"),
        product_customer_count=("business_id", "nunique"),
    )
    product_stats = master[["product_code", "product_name", "product_group"]].merge(
        sold_product_stats,
        on=["product_code", "product_name", "product_group"],
        how="left",
    )
    product_stats[["total_product_sales_eur", "product_customer_count"]] = product_stats[
        ["total_product_sales_eur", "product_customer_count"]
    ].fillna(0.0)
    group_stats = sales_frame.dropna(subset=["product_group"]).loc[sales_frame["product_group"].astype("string").str.strip().ne("")].groupby(["business_id", "product_group"], as_index=False)["sales_eur"].sum()
    customer_totals = group_stats.groupby("business_id")["sales_eur"].sum().to_dict()
    group_totals = group_stats.groupby("product_group")["sales_eur"].sum()
    group_stats["customer_group_share"] = group_stats.apply(
        lambda row: float(row["sales_eur"]) / float(customer_totals.get(row["business_id"], 0.0))
        if customer_totals.get(row["business_id"], 0.0) > 0 else 0.0,
        axis=1,
    )
    customer_group_share = {(row.business_id, row.product_group): row.customer_group_share for row in group_stats.itertuples()}
    peer_group_share = group_stats.groupby("product_group")["sales_eur"].sum()
    peer_total = float(peer_group_share.sum()) or 1.0
    peer_group_share = (peer_group_share / peer_total).to_dict()

    segment_col = "company_segment" if "company_segment" in customer_potential.columns else None
    customer_rows = customer_potential.dropna(subset=["business_id"]).drop_duplicates("business_id")
    segment_counts = customer_rows.groupby(segment_col)["business_id"].nunique().to_dict() if segment_col else {}
    owned = set(zip(sales_frame["business_id"], sales_frame["product_code"]))
    product_group_share = product_stats.assign(
        group_total=product_stats["product_group"].map(group_totals).fillna(0.0)
    )
    product_group_share["product_share"] = np.where(
        product_group_share["group_total"].gt(0),
        product_group_share["total_product_sales_eur"] / product_group_share["group_total"],
        1.0 / product_group_share.groupby("product_group")["product_code"].transform("count").clip(lower=1),
    )
    product_group_share = product_group_share.merge(master[["product_code", "excluded_from_recommendations"]], on="product_code", how="left")
    product_group_share["is_if"] = product_group_share["product_code"].str.startswith("IF")
    product_group_share["is_dif"] = product_group_share["product_code"].str.startswith("DIF")

    output_rows = []
    for row in customer_rows.itertuples(index=False):
        business_id = row.business_id
        expected = float(pd.to_numeric(getattr(row, "expected_potential_eur", 0.0), errors="coerce") or 0.0)
        segment = getattr(row, segment_col, "") if segment_col else ""
        customer_products = sales_frame.loc[sales_frame["business_id"].eq(business_id)]
        customer_product_sales = customer_products.groupby("product_code")["sales_eur"].sum().to_dict()
        customer_total = float(sum(max(value, 0.0) for value in customer_product_sales.values())) or 1.0
        customer_group_shares = {
            group: value / customer_total
            for group, value in customer_products.groupby("product_group")["sales_eur"].sum().items()
        }
        for recommendation_type in ("current", "new"):
            candidates = product_group_share.copy()
            candidates = candidates.loc[~candidates["excluded_from_recommendations"].fillna(False)]
            if recommendation_type == "current":
                candidates = candidates.loc[candidates["product_code"].isin(customer_product_sales)]
            else:
                candidates = candidates.loc[
                    candidates["product_code"].str.startswith(("IF", "DIF"))
                    & ~candidates["product_code"].map(lambda code: (business_id, code) in owned)
                ]
            if candidates.empty:
                continue
            candidates = candidates.copy()
            candidates["customer_group_share"] = candidates["product_group"].map(customer_group_shares).fillna(0.0)
            candidates["white_space_gap"] = (
                candidates["product_group"].map(peer_group_share).fillna(0.0) - candidates["customer_group_share"]
            ).clip(lower=0.0)
            candidates["purchase_probability"] = (
                0.85 if recommendation_type == "current" else 0.20
            ) + 0.10 * candidates["product_customer_count"].clip(upper=10).div(10)
            candidates["purchase_probability"] = candidates["purchase_probability"].clip(upper=0.95)
            candidates["potential_eur"] = (
                expected * candidates["white_space_gap"] * candidates["product_share"] * candidates["purchase_probability"]
            )
            candidates.loc[candidates["potential_eur"].le(0), "potential_eur"] = (
                expected * candidates["product_share"] * candidates["purchase_probability"] * 0.01
            )
            candidates["business_id"] = business_id
            candidates["recommendation_type"] = recommendation_type
            candidates["company_segment"] = segment
            candidates["suitability_score"] = (
                candidates["white_space_gap"] * 0.5
                + candidates["product_share"].clip(upper=1.0) * 0.3
                + candidates["purchase_probability"] * 0.2
            ).clip(upper=1.0)
            candidates = candidates.sort_values("potential_eur", ascending=False)
            if recommendation_type == "new":
                dif_candidates = candidates.loc[candidates["product_code"].str.startswith("DIF")].head(1)
                non_dif_candidates = candidates.loc[~candidates["product_code"].str.startswith("DIF")].head(max_recommendations_per_customer - len(dif_candidates))
                candidates = pd.concat([non_dif_candidates, dif_candidates], ignore_index=True).sort_values("potential_eur", ascending=False)
            candidates = candidates.head(max_recommendations_per_customer)
            for rank, candidate in enumerate(candidates.itertuples(index=False), 1):
                output_rows.append({
                    "business_id": business_id,
                    "company_segment": segment,
                    "recommendation_type": recommendation_type,
                    "recommendation_rank": rank,
                    "ProductCode": candidate.product_code,
                    "ProductName": candidate.product_name,
                    "ProductGroup": candidate.product_group,
                    "PotentialEUR": float(candidate.potential_eur),
                    "PurchaseProbability": float(candidate.purchase_probability),
                    "SuitabilityScore": float(candidate.suitability_score * 100),
                    "RecommendationExplanation": (
                        f"{recommendation_type}: tuoteryhmän vertailuosuus {peer_group_share.get(candidate.product_group, 0.0):.1%}, "
                        f"asiakkaan osuus {candidate.customer_group_share:.1%}; tuotteen osuus ryhmässä {candidate.product_share:.1%}."
                    ),
                })
    recommendations = pd.DataFrame(output_rows)
    if recommendations.empty:
        recommendations = pd.DataFrame(columns=["business_id", "company_segment", "recommendation_type", "recommendation_rank", "ProductCode", "ProductName", "ProductGroup", "PotentialEUR", "PurchaseProbability", "SuitabilityScore", "RecommendationExplanation"])
    quality = pd.DataFrame([
        {"metric": "product_recommendation_rows", "value": len(recommendations)},
        {"metric": "product_recommendation_excluded_master_products", "value": int(master["excluded_from_recommendations"].sum())},
        {"metric": "new_recommendations_if_dif_only", "value": int(recommendations.loc[recommendations["recommendation_type"].eq("new"), "ProductCode"].str.startswith(("IF", "DIF")).all()) if len(recommendations) else 1},
        {"metric": "sales_rows_without_product_code", "value": int(sales["sku"].isna().sum())},
        {"metric": "sales_value_without_product_code_eur", "value": float(sales.loc[sales["sku"].isna(), "total_value"].sum())},
    ])
    top = recommendations.groupby(["recommendation_type", "ProductCode", "ProductName", "ProductGroup"], as_index=False).agg(
        RecommendedPotentialEUR=("PotentialEUR", "sum"), CustomerCount=("business_id", "nunique")
    ).sort_values("RecommendedPotentialEUR", ascending=False)
    return recommendations, quality, top


def runner_resolve_column(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized = {str(column).strip().lower().replace("_", " "): column for column in frame.columns}
    return next((normalized.get(candidate.strip().lower().replace("_", " ")) for candidate in candidates if normalized.get(candidate.strip().lower().replace("_", " "))), None)


def runner_normalize_business_id(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text.upper().startswith("FI"):
        text = text[2:]
    digits = "".join(character for character in text if character.isdigit())
    if len(digits) == 7:
        digits = f"0{digits}"
    return f"{digits[:-1]}-{digits[-1]}" if len(digits) >= 8 else None


def enrich_customer_potential(customer_potential: pd.DataFrame) -> pd.DataFrame:
    frame = customer_potential.copy()
    current = pd.to_numeric(frame.get("recent_12m", 0.0), errors="coerce").fillna(0.0)
    next_12m = pd.to_numeric(frame.get("expected_potential_eur", 0.0), errors="coerce").fillna(0.0)
    frame["CurrentSalesEUR"] = current
    frame["PotentialSalesNext12MonthsEUR"] = next_12m
    frame["PotentialGrowthEUR"] = (next_12m - current).clip(lower=0.0)
    frame["PotentialGrowthPercent"] = np.where(current.gt(0), frame["PotentialGrowthEUR"] / current, 0.0)
    model_score = pd.to_numeric(frame.get("score", 0.0), errors="coerce").fillna(0.0)
    probability = pd.to_numeric(frame.get("probability_of_growth", 0.0), errors="coerce").fillna(0.0)
    frame["PotentialScore"] = ((model_score * 0.7 + probability * 0.3).clip(0.0, 1.0) * 100).round(1)
    frame["SalesPriority"] = pd.cut(frame["PotentialScore"], bins=[-1, 39.999, 69.999, 100], labels=["Low", "Medium", "High"]).astype("string")
    return frame


def add_product_recommendation_columns(customer_potential: pd.DataFrame, recommendations: pd.DataFrame) -> pd.DataFrame:
    frame = customer_potential.copy()
    for recommendation_type, prefix in (("current", "TopCurrentProductRecommendation"), ("new", "TopNewProductRecommendation")):
        subset = recommendations.loc[recommendations["recommendation_type"].eq(recommendation_type)]
        for rank in range(1, 4):
            row = subset.loc[subset["recommendation_rank"].eq(rank), ["business_id", "ProductCode", "PotentialEUR", "RecommendationExplanation"]].copy()
            row = row.rename(columns={"ProductCode": f"{prefix}{rank}", "PotentialEUR": f"{prefix}{rank}PotentialEUR", "RecommendationExplanation": f"{prefix}{rank}Explanation"})
            frame = frame.merge(row, on="business_id", how="left")
    return frame


def build_args() -> SimpleNamespace:
    output_xlsx = POTENTIAL_DIR / "current_customer_potential_with_product_groups_new_sources.xlsx"
    return SimpleNamespace(
        crm_potentials=str(CRM_PATH),
        product_grouping=str(PRODUCT_MASTER_PATH),
        accounts=str(ACCOUNTS_PATH),
        sales=str(SALES_PATH),
        companies=str(PROFINDER_PATH),
        exclude_business_ids_file=str(EXCLUSION_PATH),
        original_model=str(MODEL_PATH),
        v3_model=str(V3_PATH),
        output_xlsx=str(output_xlsx),
        current_customer_csv=str(POTENTIAL_DIR / "current_customer_potential_new_sources.csv"),
        recommendations_csv=str(POTENTIAL_DIR / "product_group_recommendations_new_sources.csv"),
        validation_csv=str(POTENTIAL_DIR / "validation_against_crm_new_sources.csv"),
        top_n_customers=1000,
        lookback_days=365 * 3,
        min_training_customer_annual_sales_eur=4000.0,
        recent_year_weight=0.60,
        middle_year_weight=0.30,
        oldest_year_weight=0.10,
        current_customer_recent_sales_weight=0.65,
        recent_sales_floor_multiplier=1.00,
        max_recommendations_per_customer=5,
        random_state=42,
    )


def main() -> None:
    runner = load_module(RUNNER_PATH, "innoflame_current_customer_runner")
    args = build_args()
    sales, raw_sales = prepare_sales(SALES_PATH)
    gosales_source = raw_sales["source_file"].astype("string").str.casefold().str.contains("gosales", na=False)
    gokeep_source = raw_sales["source_file"].astype("string").str.casefold().str.contains("gokeep", na=False)
    eligible_sales = (
        (raw_sales["status_clean"].str.casefold().eq("invoiced") & gosales_source)
        | (raw_sales["status_clean"].str.casefold().isin(GO_KEEP_COMPLETED_STATUSES) & gokeep_source)
    ) & raw_sales["account_id"].notna() & raw_sales["created_at_dt"].notna()
    grouping, master_quality = prepare_product_grouping(PRODUCT_MASTER_PATH)
    sales, product_code_quality = enrich_product_groups_by_product_code(sales, grouping)
    sales, product_name_quality = enrich_missing_product_codes_by_name(sales, grouping)
    sales, context_quality = enrich_product_groups_by_context(sales, grouping)
    product_name_audit = pd.DataFrame()
    if "product_name_match" in sales.columns:
        name_column = next((column for column in ("name", "ProductName", "product_name") if column in sales.columns), None)
        if name_column:
            product_name_audit = sales.loc[
                sales["product_name_match"].ne("not_needed"),
                ["source_file", "id", "status", name_column, "sku", "product_group_from_product_code", "product_group_from_name", "product_group_from_description", "product_group_from_category", "product_group_from_keyword", "product_group_from_group_pair", "product_name_match"],
            ].copy()
            product_name_audit = product_name_audit.rename(columns={name_column: "product_name", "sku": "ProductCode"})
            product_name_audit.to_csv(
                POTENTIAL_DIR / "product_name_group_enrichment_audit_new_sources.csv",
                index=False,
                encoding="utf-8-sig",
            )
    inputs = {
        "crm": pd.read_excel(CRM_PATH, sheet_name=0),
        "product_grouping": grouping,
        "accounts": runner.normalize_accounts_source(pd.read_excel(ACCOUNTS_PATH)),
        "sales": sales,
        "companies": pd.read_excel(PROFINDER_PATH),
    }

    product_grouping, group_columns = runner.create_lowest_product_group(inputs["product_grouping"])
    artifacts = runner.load_model_artifacts(args, inputs)
    crm_features, matched_features = runner.prepare_customer_features(inputs["crm"], inputs["accounts"], artifacts["all_scored"])
    customer_potential = runner.score_current_customers(crm_features, artifacts["all_scored"])
    customer_potential = runner.collapse_to_one_row_per_customer(customer_potential)
    customer_potential = enrich_customer_potential(customer_potential)
    recommendations, product_quality = runner.build_product_group_recommendations(
        customer_potential,
        inputs["sales"],
        inputs["accounts"],
        product_grouping,
        max_recommendations_per_customer=args.max_recommendations_per_customer,
    )
    product_recommendations, product_recommendation_quality, product_summary = build_product_recommendations(
        customer_potential,
        inputs["sales"],
        inputs["accounts"],
        product_grouping,
        max_recommendations_per_customer=args.max_recommendations_per_customer,
    )
    customer_potential = add_product_recommendation_columns(customer_potential, product_recommendations)
    validation = runner.validate_against_crm(customer_potential, artifacts["all_scored"])
    customer_potential = runner.remove_requested_crm_columns(customer_potential)
    validation = runner.remove_requested_crm_columns(validation)
    missing_features = {
        name: int(artifacts["modeling_df"][name].isna().sum())
        for name in artifacts["feature_columns"]
        if name in artifacts["modeling_df"].columns
    }
    product_quality = pd.concat([master_quality, product_code_quality, product_name_quality, context_quality, product_quality, pd.DataFrame([
        {"metric": "source_sales_rows", "value": len(raw_sales)},
        {"metric": "eligible_sales_rows_before_value_filter", "value": int(eligible_sales.sum())},
        {"metric": "excluded_negative_sales_rows", "value": int((eligible_sales & raw_sales["total_value"].lt(0)).sum())},
        {"metric": "excluded_zero_sales_rows", "value": int((eligible_sales & raw_sales["total_value"].eq(0)).sum())},
        {"metric": "model_sales_rows_after_positive_value_filter", "value": len(sales)},
        {"metric": "included_invoiced_sales_rows", "value": len(sales)},
        {"metric": "included_gokeep_sales_rows", "value": int(sales["source_file"].astype("string").str.casefold().str.contains("gokeep", na=False).sum())},
        {"metric": "included_gokeep_sales_eur", "value": float(sales.loc[sales["source_file"].astype("string").str.casefold().str.contains("gokeep", na=False), "total_value"].sum())},
        {"metric": "product_group_level_columns_detected", "value": json.dumps(group_columns, ensure_ascii=True)},
        {"metric": "crm_rows_matched_to_business_id", "value": int(crm_features["business_id"].notna().sum())},
        {"metric": "crm_rows_matched_to_model", "value": int(matched_features["_has_model_score"].sum())},
    ]), product_recommendation_quality], ignore_index=True)
    run_log = runner.build_run_log(inputs["crm"], customer_potential, validation, missing_features, product_quality, artifacts)
    data_quality = runner.build_data_quality(crm_features, customer_potential, product_quality)
    runner.write_outputs(customer_potential, recommendations, validation, run_log, data_quality, args)
    product_recommendations.to_csv(POTENTIAL_DIR / "product_recommendations_new_sources.csv", index=False, encoding="utf-8-sig")
    product_summary.to_csv(POTENTIAL_DIR / "top_recommended_products_new_sources.csv", index=False, encoding="utf-8-sig")
    new_summary = product_summary.loc[product_summary["recommendation_type"].eq("new")]
    new_summary.loc[new_summary["ProductCode"].str.startswith("IF")].head(10).to_csv(POTENTIAL_DIR / "top_10_if_products_new_sources.csv", index=False, encoding="utf-8-sig")
    new_summary.loc[new_summary["ProductCode"].str.startswith("DIF")].head(10).to_csv(POTENTIAL_DIR / "top_10_dif_products_new_sources.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(args.output_xlsx, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        product_recommendations.to_excel(writer, sheet_name="product_recommendations", index=False)
        product_summary.to_excel(writer, sheet_name="top_recommended_products", index=False)
        new_summary.loc[new_summary["ProductCode"].str.startswith("IF")].head(10).to_excel(writer, sheet_name="top_10_IF_products", index=False)
        new_summary.loc[new_summary["ProductCode"].str.startswith("DIF")].head(10).to_excel(writer, sheet_name="top_10_DIF_products", index=False)
    print(json.dumps({
        "output_xlsx": args.output_xlsx,
        "customer_rows": len(customer_potential),
        "recommendation_rows": len(recommendations),
        "source_sales_rows": len(raw_sales),
        "included_invoiced_sales_rows": len(sales),
    }, indent=2))


if __name__ == "__main__":
    main()
