from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


BASE = Path(__file__).resolve().parent
SALES_CSV = BASE / "outputs" / "Innoflame_merged_sales_csv_source_with_L1_L2_L3_delivery_handling.csv"
ACCOUNTS_XLSX = BASE / "Account_20.05.2026_combined_with_profinder.xlsx"
PROSPECT_MODEL_CSV = (
    BASE
    / "outputs"
    / "innoflame_all_accounts_v3_corrected_sales"
    / "prospect_segment_model_all_accounts_v3_corrected_sales.csv"
)
OUTPUT_DIR = BASE / "outputs" / "product_group_submodel_v1"
RECOMMENDATIONS_CSV = OUTPUT_DIR / "prospect_product_group_recommendations.csv"
SUMMARY_JSON = OUTPUT_DIR / "product_group_submodel_summary.json"
GROUP_PROFILE_CSV = OUTPUT_DIR / "product_group_training_profile.csv"


MATCH_CONFIDENCE_DEFAULT = 0.6
EXCLUDED_PRODUCT_GROUP_L3_CODES = {"15.01.01", "04.05.02"}


def normalize_business_id(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    if text.upper().startswith("FI"):
        text = text[2:]
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) == 7:
        digits = f"0{digits}"
    if len(digits) >= 8:
        return f"{digits[:-1]}-{digits[-1]}"
    if re.fullmatch(r"\d{7,8}-\d", text):
        return text
    return text


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def group_match_confidence(method_value: Any) -> float:
    method = normalize_text(method_value).casefold()
    if not method:
        return 0.0
    if method == "sku":
        return 1.0
    if "productcode" in method:
        return 0.95
    if any(token in method for token in ["name_category", "same_name", "name_unique"]):
        return 0.85
    if "reference" in method:
        return 0.8
    if "source_zip" in method:
        return 0.8
    if method.startswith("manual_"):
        return 0.75
    if "category_guided" in method:
        return 0.7
    return MATCH_CONFIDENCE_DEFAULT


def load_training_sales() -> tuple[pd.DataFrame, dict[str, Any]]:
    sales = pd.read_csv(SALES_CSV, dtype=str, encoding="utf-8-sig", keep_default_na=False)
    accounts = pd.read_excel(ACCOUNTS_XLSX, dtype=str)

    account_keys = accounts[["ID", "Business ID", "customer_status"]].copy()
    account_keys["accountid"] = account_keys["ID"].map(normalize_text)
    account_keys["business_id"] = account_keys["Business ID"].map(normalize_business_id)
    account_keys["customer_status"] = account_keys["customer_status"].map(normalize_text)
    account_keys = account_keys.drop_duplicates(subset=["accountid"])
    account_keys = account_keys[["accountid", "business_id", "customer_status"]]

    sales["accountid"] = sales["accountid"].map(normalize_text)
    sales["sales_eur"] = pd.to_numeric(
        sales["sales"].astype(str).str.replace(",", ".", regex=False),
        errors="coerce",
    ).fillna(0.0)
    sales["sold_at_date"] = pd.to_datetime(sales["sold_at"], errors="coerce")
    sales["status_clean"] = sales["status"].map(normalize_text)
    sales["product_group_l3_code"] = sales["product_group_l3_code"].map(normalize_text)
    sales["product_group_l3_name"] = sales["product_group_l3_name"].map(normalize_text)
    sales["product_group_l2_code"] = sales["product_group_l2_code"].map(normalize_text)
    sales["product_group_l2_name"] = sales["product_group_l2_name"].map(normalize_text)
    sales["product_group_l1_code"] = sales["product_group_l1_code"].map(normalize_text)
    sales["product_group_l1_name"] = sales["product_group_l1_name"].map(normalize_text)
    sales["product_group_match_confidence"] = sales["product_group_match_method"].map(group_match_confidence)

    joined = sales.merge(account_keys, on="accountid", how="left")
    has_l3 = joined["product_group_l3_code"].ne("")
    model_mask = (
        joined["status_clean"].eq("Invoiced")
        & joined["sold_at_date"].notna()
        & joined["accountid"].ne("")
        & has_l3
        & ~joined["product_group_l3_code"].isin(EXCLUDED_PRODUCT_GROUP_L3_CODES)
    )
    eligible_status = joined["customer_status"].str.casefold().isin(["active", "gokeep+"])
    training = joined.loc[model_mask & eligible_status & joined["business_id"].ne("")].copy()
    training["weighted_sales_eur"] = training["sales_eur"] * training["product_group_match_confidence"].clip(0.0, 1.0)

    audit = {
        "source_rows": int(len(sales)),
        "invoiced_rows": int(joined["status_clean"].eq("Invoiced").sum()),
        "rows_with_l3_product_group": int((model_mask).sum()),
        "training_rows_active_gokeep_with_business_id": int(len(training)),
        "training_sales_eur": round(float(training["sales_eur"].sum()), 2),
        "training_weighted_sales_eur": round(float(training["weighted_sales_eur"].sum()), 2),
        "training_business_ids": int(training["business_id"].nunique()),
        "training_l3_groups": int(training["product_group_l3_code"].nunique()),
    }
    return training, audit


def group_profiles(training: pd.DataFrame) -> pd.DataFrame:
    key_cols = [
        "product_group_l1_code",
        "product_group_l1_name",
        "product_group_l2_code",
        "product_group_l2_name",
        "product_group_l3_code",
        "product_group_l3_name",
    ]
    detailed = (
        training.groupby(key_cols, dropna=False)
        .agg(
            training_rows=("sales_eur", "size"),
            customer_count=("business_id", "nunique"),
            sales_eur=("sales_eur", "sum"),
            weighted_sales_eur=("weighted_sales_eur", "sum"),
            avg_match_confidence=("product_group_match_confidence", "mean"),
        )
        .reset_index()
    )
    canonical_idx = detailed.groupby("product_group_l3_code")["weighted_sales_eur"].idxmax()
    canonical = detailed.loc[canonical_idx, key_cols].copy()
    numeric = (
        detailed.groupby("product_group_l3_code", dropna=False)
        .agg(
            training_rows=("training_rows", "sum"),
            customer_count=("customer_count", "max"),
            sales_eur=("sales_eur", "sum"),
            weighted_sales_eur=("weighted_sales_eur", "sum"),
            avg_match_confidence=("avg_match_confidence", "mean"),
        )
        .reset_index()
    )
    profile = canonical.merge(numeric, on="product_group_l3_code", how="left")
    total_weighted_sales = float(profile["weighted_sales_eur"].sum())
    profile["global_group_share"] = np.where(
        total_weighted_sales > 0,
        profile["weighted_sales_eur"] / total_weighted_sales,
        0.0,
    )
    return profile.sort_values("weighted_sales_eur", ascending=False).reset_index(drop=True)


def segment_profiles(training: pd.DataFrame, scored: pd.DataFrame) -> pd.DataFrame:
    feature_cols = [
        "business_id",
        "company_segment",
        "industry",
        "revenue_class",
        "headcount_class",
    ]
    customer_features = scored[[col for col in feature_cols if col in scored.columns]].drop_duplicates("business_id")
    enriched = training.merge(customer_features, on="business_id", how="left")
    profile_cols = [
        "product_group_l3_code",
        "company_segment",
        "industry",
        "revenue_class",
        "headcount_class",
    ]
    rows = []
    for level_name, cols, weight in [
        ("company_segment", ["company_segment"], 0.48),
        ("industry", ["industry"], 0.28),
        ("revenue_headcount", ["revenue_class", "headcount_class"], 0.16),
        ("global", [], 0.08),
    ]:
        group_cols = cols + [
            "product_group_l3_code",
            "product_group_l3_name",
            "product_group_l2_code",
            "product_group_l2_name",
            "product_group_l1_code",
            "product_group_l1_name",
        ]
        frame = (
            enriched.groupby(group_cols, dropna=False)
            .agg(
                weighted_sales_eur=("weighted_sales_eur", "sum"),
                sales_eur=("sales_eur", "sum"),
                customer_count=("business_id", "nunique"),
                avg_match_confidence=("product_group_match_confidence", "mean"),
            )
            .reset_index()
        )
        if cols:
            totals = frame.groupby(cols, dropna=False)["weighted_sales_eur"].transform("sum")
            frame["profile_share"] = np.where(totals.gt(0), frame["weighted_sales_eur"] / totals, 0.0)
        else:
            total = float(frame["weighted_sales_eur"].sum())
            frame["profile_share"] = frame["weighted_sales_eur"] / total if total else 0.0
        frame["profile_level"] = level_name
        frame["profile_weight"] = weight
        rows.append(frame)
    return pd.concat(rows, ignore_index=True, sort=False)


def build_recommendations(scored: pd.DataFrame, profiles: pd.DataFrame, group_profile: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    group_lookup_cols = [
        "product_group_l3_code",
        "product_group_l3_name",
        "product_group_l2_code",
        "product_group_l2_name",
        "product_group_l1_code",
        "product_group_l1_name",
        "global_group_share",
        "customer_count",
        "sales_eur",
        "avg_match_confidence",
    ]
    group_lookup = group_profile[group_lookup_cols].copy()

    company_cols = [
        "business_id",
        "company",
        "rank",
        "priority",
        "is_account_customer",
        "company_segment",
        "industry",
        "revenue_class",
        "headcount_class",
        "ennustettu potentiaali",
        "score",
    ]
    companies = scored[[col for col in company_cols if col in scored.columns]].copy()
    companies["_company_row_id"] = np.arange(len(companies), dtype=int)

    candidate_parts = []
    merge_specs = [
        ("company_segment", ["company_segment"]),
        ("industry", ["industry"]),
        ("revenue_headcount", ["revenue_class", "headcount_class"]),
    ]
    for level_name, cols in merge_specs:
        part_profile = profiles.loc[profiles["profile_level"].eq(level_name)].copy()
        if part_profile.empty or any(col not in companies.columns for col in cols):
            continue
        part = companies.merge(part_profile, on=cols, how="inner")
        candidate_parts.append(part)

    global_profile = profiles.loc[profiles["profile_level"].eq("global")].copy()
    if not global_profile.empty:
        global_part = companies.assign(_join_key=1).merge(global_profile.assign(_join_key=1), on="_join_key").drop(columns=["_join_key"])
        candidate_parts.append(global_part)

    if not candidate_parts:
        return pd.DataFrame()
    candidates = pd.concat(candidate_parts, ignore_index=True, sort=False)
    candidates["weighted_profile_share"] = (
        pd.to_numeric(candidates["profile_share"], errors="coerce").fillna(0.0)
        * pd.to_numeric(candidates["profile_weight"], errors="coerce").fillna(0.0)
    )
    candidates = (
        candidates.groupby(["_company_row_id", "product_group_l3_code"], dropna=False)
        .agg(
            recommendation_score=("weighted_profile_share", "sum"),
            evidence_levels=("profile_level", lambda values: ", ".join(sorted(set(map(str, values))))),
        )
        .reset_index()
        .merge(companies, on="_company_row_id", how="left")
        .merge(group_lookup, on="product_group_l3_code", how="left")
    )
    candidates["recommendation_score"] = pd.to_numeric(candidates["recommendation_score"], errors="coerce").fillna(0.0)
    candidates = candidates.loc[candidates["recommendation_score"].gt(0)].copy()
    if candidates.empty:
        return pd.DataFrame()

    candidates = candidates.sort_values(
        ["_company_row_id", "recommendation_score", "sales_eur", "customer_count"],
        ascending=[True, False, False, False],
        kind="mergesort",
    )
    result = candidates.groupby("_company_row_id", group_keys=False).head(top_n).copy()
    result["recommendation_rank"] = result.groupby("_company_row_id").cumcount() + 1
    top_score_sum = result.groupby("_company_row_id")["recommendation_score"].transform("sum")
    result["top_allocation_share"] = np.where(top_score_sum.gt(0), result["recommendation_score"] / top_score_sum, 0.0)
    result["recommended_group_potential_eur"] = (
        result["top_allocation_share"]
        * pd.to_numeric(result["ennustettu potentiaali"], errors="coerce").fillna(0.0)
    ).round(0)
    result["confidence"] = (
        pd.to_numeric(result["avg_match_confidence"], errors="coerce").fillna(MATCH_CONFIDENCE_DEFAULT)
        * np.minimum(1.0, np.log1p(pd.to_numeric(result["customer_count"], errors="coerce").fillna(0.0)) / np.log1p(50))
    ).clip(0.0, 1.0)
    result["recommendation_reason"] = result.apply(
        lambda row: (
            f"Osuus perustuu profiileihin: {row['evidence_levels']}; "
            f"tuoteryhmää ostanut {int(row['customer_count'])} opetusasiakasta."
        ),
        axis=1,
    )
    output_columns = [
        "business_id",
        "company",
        "rank",
        "priority",
        "is_account_customer",
        "company_segment",
        "industry",
        "revenue_class",
        "headcount_class",
        "ennustettu potentiaali",
        "score",
        "recommendation_rank",
        "product_group_l1_code",
        "product_group_l1_name",
        "product_group_l2_code",
        "product_group_l2_name",
        "product_group_l3_code",
        "product_group_l3_name",
        "recommendation_score",
        "top_allocation_share",
        "recommended_group_potential_eur",
        "confidence",
        "customer_count",
        "sales_eur",
        "evidence_levels",
        "recommendation_reason",
    ]
    return result[output_columns].sort_values(["rank", "recommendation_rank"], kind="mergesort")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    training, audit = load_training_sales()
    scored = pd.read_csv(PROSPECT_MODEL_CSV, dtype={"business_id": str}, encoding="utf-8-sig")
    scored["business_id"] = scored["business_id"].map(normalize_business_id)

    group_profile = group_profiles(training)
    profiles = segment_profiles(training, scored)
    recommendations = build_recommendations(scored, profiles, group_profile, top_n=5)

    group_profile.to_csv(GROUP_PROFILE_CSV, index=False, encoding="utf-8-sig")
    recommendations.to_csv(RECOMMENDATIONS_CSV, index=False, encoding="utf-8-sig")

    summary = {
        "model_name": "product_group_submodel_v1",
        "level": "L3",
        "source_sales_csv": str(SALES_CSV.resolve()),
        "source_prospect_model_csv": str(PROSPECT_MODEL_CSV.resolve()),
        "recommendations_csv": str(RECOMMENDATIONS_CSV.resolve()),
        "group_profile_csv": str(GROUP_PROFILE_CSV.resolve()),
        "training_audit": audit,
        "scored_companies": int(len(scored)),
        "recommendation_rows": int(len(recommendations)),
        "companies_with_recommendations": int(recommendations["business_id"].nunique()) if not recommendations.empty else 0,
        "avg_recommendations_per_company": round(float(len(recommendations) / len(scored)), 2) if len(scored) else 0.0,
        "total_recommended_group_potential_eur": round(float(recommendations["recommended_group_potential_eur"].sum()), 2)
        if not recommendations.empty
        else 0.0,
        "top_recommended_groups_by_rows": recommendations["product_group_l3_name"].value_counts().head(10).to_dict()
        if not recommendations.empty
        else {},
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
