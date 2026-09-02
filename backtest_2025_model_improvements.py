from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, roc_auc_score
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


BASE_DIR = Path(__file__).resolve().parent
ACCOUNTS_PATH = BASE_DIR / "GoSystems_accounts_25_06_2026_updated_business_ids_fi_normalized_without_innoflame.xlsx"
SALES_PATH = BASE_DIR / "GoSystems_sales_26_05_2026_summarized_without_innoflame.csv"
CURRENT_MODEL_PATH = BASE_DIR / "current_customer_potential_without_innoflame.csv"
RECOMMENDATIONS_PATH = BASE_DIR / "product_group_recommendations_without_innoflame.csv"
GROUPING_PATH = BASE_DIR / "product_master_enrichment" / "final_product_grouping" / "Innoflame_tuoteryhmittely.xlsx"
CRM_POTENTIALS_PATH = BASE_DIR / "CRM_potentials_03.06.2026_03.07.2026 (1).xlsx"
CRM_POTENTIALS_WORKCOPY_PATH = BASE_DIR / "Nykyiset asiakkaat" / "CRM_potentials_workcopy.xlsx"

OUTPUT_DIR = BASE_DIR / "model_improvement_backtest_2025"
OUTPUT_XLSX = BASE_DIR / "model_improvement_backtest_2025.xlsx"
FALLBACK_OUTPUT_XLSX = BASE_DIR / "model_improvement_backtest_2025_calibrated_product_groups.xlsx"
NEXT_YEAR_OUTPUT_XLSX = BASE_DIR / "model_improvement_next_year_recent_weighted.xlsx"


def normalize_business_id(value: Any) -> str | None:
    if pd.isna(value):
        return None
    if isinstance(value, (int, np.integer)):
        text = str(int(value))
    elif isinstance(value, (float, np.floating)) and float(value).is_integer():
        text = str(int(value))
    else:
        text = str(value).strip()
    if not text:
        return None
    if text.upper().startswith("FI"):
        text = text[2:]
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) == 7:
        digits = "0" + digits
    if len(digits) >= 8:
        return f"{digits[:-1]}-{digits[-1]}"
    return None


def clean_key(value: Any) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", "", str(value).strip().upper())


def normalize_customer_name(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b(oyj|oy|ab|ltd|limited|inc|gmbh|plc|konserni|group)\b", " ", text)
    text = re.sub(r"[^a-z0-9åäö]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def read_inputs() -> dict[str, pd.DataFrame]:
    accounts = pd.read_excel(ACCOUNTS_PATH)
    sales = pd.read_csv(SALES_PATH)
    current = pd.read_csv(CURRENT_MODEL_PATH)
    recommendations = pd.read_csv(RECOMMENDATIONS_PATH)
    grouping = pd.read_excel(GROUPING_PATH, sheet_name="Products")
    try:
        crm_potentials = pd.read_excel(CRM_POTENTIALS_PATH, sheet_name="Potentials")
    except PermissionError:
        crm_potentials = pd.read_excel(CRM_POTENTIALS_WORKCOPY_PATH, sheet_name="Potentials")

    accounts["business_id"] = accounts["business_id"].map(normalize_business_id)
    accounts["account_id"] = pd.to_numeric(accounts["id"], errors="coerce").astype("Int64")
    accounts["customer_name"] = accounts["name"].fillna(accounts.get("company_name"))

    sales["account_id"] = pd.to_numeric(sales["account_id"], errors="coerce").astype("Int64")
    sales["total_value"] = pd.to_numeric(sales["total_value"], errors="coerce").fillna(0.0)
    sales["created_month"] = pd.to_datetime(sales["created_year_month"].astype(str) + "-01", errors="coerce")
    sales["year"] = sales["created_month"].dt.year
    sales = sales.merge(
        accounts[["account_id", "business_id", "customer_name"]],
        on="account_id",
        how="left",
        validate="many_to_one",
    )

    current["business_id"] = current["business_id"].map(normalize_business_id)
    recommendations["business_id"] = recommendations["business_id"].map(normalize_business_id)
    return {
        "accounts": accounts,
        "sales": sales,
        "current": current,
        "recommendations": recommendations,
        "grouping": grouping,
        "crm_potentials": crm_potentials,
    }


def add_lowest_product_group(grouping: pd.DataFrame) -> pd.DataFrame:
    frame = grouping.copy()
    frame["lowest_product_group_code"] = pd.NA
    frame["lowest_product_group_name"] = pd.NA
    for level in range(4, 0, -1):
        code_col = f"product_group_l{level}_code"
        name_col = f"product_group_l{level}_name"
        if code_col not in frame.columns and name_col not in frame.columns:
            continue
        code = frame[code_col].astype("string").str.strip() if code_col in frame else pd.Series(pd.NA, index=frame.index)
        name = frame[name_col].astype("string").str.strip() if name_col in frame else pd.Series(pd.NA, index=frame.index)
        has_value = code.fillna("").ne("") | name.fillna("").ne("")
        target = frame["lowest_product_group_name"].isna() & has_value
        frame.loc[target, "lowest_product_group_code"] = code[target].where(code[target].fillna("").ne(""), name[target])
        frame.loc[target, "lowest_product_group_name"] = name[target].where(name[target].fillna("").ne(""), code[target])
    return frame


def map_sales_to_product_groups(sales: pd.DataFrame, grouping: pd.DataFrame) -> pd.DataFrame:
    groups = add_lowest_product_group(grouping)
    lookup_parts: list[pd.DataFrame] = []
    for key_col in ["sku", "code", "product_id"]:
        if key_col in groups.columns:
            part = groups[[key_col, "lowest_product_group_code", "lowest_product_group_name"]].copy()
            part["match_key"] = part[key_col].map(clean_key)
            part = part[part["match_key"].ne("")]
            lookup_parts.append(part[["match_key", "lowest_product_group_code", "lowest_product_group_name"]])

    lookup = pd.concat(lookup_parts, ignore_index=True).drop_duplicates("match_key") if lookup_parts else pd.DataFrame()
    frame = sales.copy()
    frame["match_key"] = frame["sku"].map(clean_key)
    if not lookup.empty:
        frame = frame.merge(lookup, on="match_key", how="left")
    else:
        frame["lowest_product_group_code"] = pd.NA
        frame["lowest_product_group_name"] = pd.NA

    fallback = frame["lowest_product_group_name"].isna() | frame["lowest_product_group_name"].astype("string").str.strip().eq("")
    category = frame["category"].fillna(frame["reference"]).fillna("Unmapped product group").astype(str).str.strip()
    category = category.mask(category.eq("") | category.eq("nan"), "Unmapped product group")
    frame.loc[fallback, "lowest_product_group_code"] = "sales_category:" + category[fallback]
    frame.loc[fallback, "lowest_product_group_name"] = category[fallback]
    frame["product_group_source"] = np.where(fallback, "sales_category_or_reference", "product_master_sku")
    return frame


def wide_sales_by_year(sales: pd.DataFrame) -> pd.DataFrame:
    valid = sales[sales["business_id"].notna()].copy()
    yearly = (
        valid.groupby(["business_id", "year"], dropna=False)["total_value"]
        .sum()
        .unstack(fill_value=0.0)
        .reset_index()
    )
    for year in [2023, 2024, 2025, 2026]:
        if year not in yearly.columns:
            yearly[year] = 0.0
    yearly = yearly.rename(columns={
        2023: "sales_2023_eur",
        2024: "sales_2024_eur",
        2025: "actual_sales_2025_eur",
        2026: "sales_2026_ytd_eur",
    })
    return yearly


def build_history_features(accounts: pd.DataFrame, sales: pd.DataFrame, grouped_sales: pd.DataFrame) -> pd.DataFrame:
    base = accounts[["business_id", "account_id", "customer_name", "country", "category"]].dropna(subset=["business_id"]).drop_duplicates("business_id")
    yearly = wide_sales_by_year(sales)
    frame = base.merge(yearly, on="business_id", how="left")
    for col in ["sales_2023_eur", "sales_2024_eur", "actual_sales_2025_eur", "sales_2026_ytd_eur"]:
        frame[col] = frame[col].fillna(0.0)

    prior = sales[(sales["year"].isin([2023, 2024])) & sales["business_id"].notna()].copy()
    monthly = prior.groupby(["business_id", "created_month"])["total_value"].sum().reset_index()
    active_months = monthly.groupby("business_id")["created_month"].nunique().rename("active_months_2023_2024")
    active_2024 = (
        monthly[monthly["created_month"].dt.year.eq(2024)]
        .groupby("business_id")["created_month"]
        .nunique()
        .rename("active_months_2024")
    )
    order_rows_2024 = (
        sales[(sales["year"].eq(2024)) & sales["business_id"].notna()]
        .groupby("business_id")["id"]
        .nunique()
        .rename("order_rows_2024")
    )
    last_purchase = prior.groupby("business_id")["created_month"].max().rename("last_purchase_before_2025")

    q = sales[(sales["year"].eq(2024)) & sales["business_id"].notna()].copy()
    q["quarter"] = q["created_month"].dt.quarter
    quarter = q.pivot_table(index="business_id", columns="quarter", values="total_value", aggfunc="sum", fill_value=0.0)
    for col in [1, 2, 3, 4]:
        if col not in quarter.columns:
            quarter[col] = 0.0
    quarter = quarter[[1, 2, 3, 4]].rename(columns={
        1: "sales_2024_q1_eur",
        2: "sales_2024_q2_eur",
        3: "sales_2024_q3_eur",
        4: "sales_2024_q4_eur",
    })

    group_count = (
        grouped_sales[(grouped_sales["year"].eq(2024)) & grouped_sales["business_id"].notna()]
        .groupby("business_id")["lowest_product_group_name"]
        .nunique()
        .rename("product_group_count_2024")
    )

    enrich = pd.concat([active_months, active_2024, order_rows_2024, last_purchase, quarter, group_count], axis=1).reset_index()
    frame = frame.merge(enrich, on="business_id", how="left")
    for col in [
        "active_months_2023_2024",
        "active_months_2024",
        "order_rows_2024",
        "sales_2024_q1_eur",
        "sales_2024_q2_eur",
        "sales_2024_q3_eur",
        "sales_2024_q4_eur",
        "product_group_count_2024",
    ]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0.0)

    frame["avg_monthly_sales_2024_eur"] = frame["sales_2024_eur"] / frame["active_months_2024"].replace(0, np.nan)
    frame["avg_monthly_sales_2024_eur"] = frame["avg_monthly_sales_2024_eur"].fillna(0.0)
    frame["sales_momentum_2024_vs_2023"] = frame["sales_2024_eur"] / frame["sales_2023_eur"].replace(0, np.nan)
    frame["sales_momentum_2024_vs_2023"] = frame["sales_momentum_2024_vs_2023"].replace([np.inf, -np.inf], np.nan)
    fallback_momentum = pd.Series(np.where(frame["sales_2024_eur"].gt(0), 2.0, 0.0), index=frame.index)
    frame["sales_momentum_2024_vs_2023"] = frame["sales_momentum_2024_vs_2023"].fillna(fallback_momentum)
    frame["h2_vs_h1_2024"] = (frame["sales_2024_q3_eur"] + frame["sales_2024_q4_eur"]) / (frame["sales_2024_q1_eur"] + frame["sales_2024_q2_eur"]).replace(0, np.nan)
    frame["h2_vs_h1_2024"] = frame["h2_vs_h1_2024"].replace([np.inf, -np.inf], np.nan)
    fallback_h2_h1 = pd.Series(np.where((frame["sales_2024_q3_eur"] + frame["sales_2024_q4_eur"]).gt(0), 2.0, 0.0), index=frame.index)
    frame["h2_vs_h1_2024"] = frame["h2_vs_h1_2024"].fillna(fallback_h2_h1)
    frame["days_since_last_purchase_at_2025_start"] = (
        pd.Timestamp("2025-01-01") - pd.to_datetime(frame["last_purchase_before_2025"])
    ).dt.days
    frame["days_since_last_purchase_at_2025_start"] = frame["days_since_last_purchase_at_2025_start"].fillna(9999).clip(lower=0)
    frame["grew_2025"] = (
        (frame["actual_sales_2025_eur"] > frame["sales_2024_eur"] * 1.10)
        & ((frame["actual_sales_2025_eur"] - frame["sales_2024_eur"]) > 1000)
    ).astype(int)
    frame["bought_2025"] = frame["actual_sales_2025_eur"].gt(0).astype(int)
    return frame


def add_recent_weighted_forward_features(frame: pd.DataFrame, sales: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    ytd_months = (
        sales.loc[sales["year"].eq(2026) & sales["created_month"].notna(), "created_month"]
        .dt.month
        .nunique()
    )
    ytd_months = int(ytd_months) if ytd_months else 5
    simple_annualization_factor = 12.0 / max(ytd_months, 1)
    comparable_2025 = sales[sales["year"].eq(2025)].copy()
    comparable_2025_ytd = comparable_2025[comparable_2025["created_month"].dt.month.le(ytd_months)]
    comparable_2025_total = comparable_2025["total_value"].sum()
    comparable_2025_ytd_total = comparable_2025_ytd["total_value"].sum()
    seasonal_annualization_factor = (
        comparable_2025_total / comparable_2025_ytd_total
        if comparable_2025_total > 0 and comparable_2025_ytd_total > 0
        else simple_annualization_factor
    )
    annualization_factor = seasonal_annualization_factor
    result["sales_2026_annualized_eur"] = result["sales_2026_ytd_eur"] * annualization_factor

    weights = {
        "sales_2023_eur": 0.10,
        "sales_2024_eur": 0.20,
        "actual_sales_2025_eur": 0.35,
        "sales_2026_annualized_eur": 0.35,
    }
    result["recent_weighted_sales_base_eur"] = sum(result[col] * weight for col, weight in weights.items())
    result["recent_two_year_avg_eur"] = (result["actual_sales_2025_eur"] + result["sales_2026_annualized_eur"]) / 2.0
    result["older_two_year_avg_eur"] = (result["sales_2023_eur"] + result["sales_2024_eur"]) / 2.0
    result["recent_vs_older_ratio"] = result["recent_two_year_avg_eur"] / result["older_two_year_avg_eur"].replace(0, np.nan)
    result["recent_vs_older_ratio"] = result["recent_vs_older_ratio"].replace([np.inf, -np.inf], np.nan)
    recent_ratio_fallback = pd.Series(np.where(result["recent_two_year_avg_eur"].gt(0), 1.25, 1.0), index=result.index)
    result["recent_vs_older_ratio"] = result["recent_vs_older_ratio"].fillna(recent_ratio_fallback)
    result["sales_2026_vs_2025_ratio"] = result["sales_2026_annualized_eur"] / result["actual_sales_2025_eur"].replace(0, np.nan)
    result["sales_2026_vs_2025_ratio"] = result["sales_2026_vs_2025_ratio"].replace([np.inf, -np.inf], np.nan)
    ytd_ratio_fallback = pd.Series(np.where(result["sales_2026_annualized_eur"].gt(0), 1.10, 1.0), index=result.index)
    result["sales_2026_vs_2025_ratio"] = result["sales_2026_vs_2025_ratio"].fillna(ytd_ratio_fallback)
    result["recent_weighted_years_formula"] = "2023*0.10 + 2024*0.20 + 2025*0.35 + annualized_2026_ytd*0.35"
    result["sales_2026_ytd_months"] = ytd_months
    result["sales_2026_annualization_factor"] = annualization_factor
    result["sales_2026_simple_annualization_factor"] = simple_annualization_factor
    result["sales_2026_annualization_method"] = "seasonal_factor_from_2025_same_months"
    result["sales_2025_same_months_eur"] = comparable_2025_ytd_total
    result["sales_2025_full_year_eur"] = comparable_2025_total
    return result


def merge_current_model(history: pd.DataFrame, current: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "business_id",
        "priority",
        "company",
        "score",
        "probability_of_growth",
        "conditional_potential_eur",
        "expected_potential_eur",
        "estimated_potential_eur",
        "model_estimated_potential_eur",
        "final_value_eur",
        "recent_sales_value_eur",
        "sales_momentum_ratio",
        "revenue_k_eur",
        "segment_lift",
        "company_segment",
        "industry",
        "positive_signals",
    ]
    available = [col for col in cols if col in current.columns]
    current_one = current[available].dropna(subset=["business_id"]).drop_duplicates("business_id")
    frame = history.merge(current_one, on="business_id", how="left")
    frame["current_model_expected_eur"] = pd.to_numeric(frame.get("expected_potential_eur"), errors="coerce").fillna(0.0)
    frame["current_model_conditional_eur"] = pd.to_numeric(frame.get("conditional_potential_eur"), errors="coerce").fillna(0.0)
    frame["current_probability_of_growth"] = pd.to_numeric(frame.get("probability_of_growth"), errors="coerce").fillna(0.0)
    return frame


def build_next_year_forecast(customer_backtest: pd.DataFrame, sales: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = add_recent_weighted_forward_features(customer_backtest, sales)
    probability = pd.to_numeric(frame["improved_probability_of_growth"], errors="coerce").fillna(0.0).clip(0.01, 0.99)
    score = pd.to_numeric(frame.get("score"), errors="coerce").fillna(0.0).clip(0.0, 1.0)
    recent_ratio = pd.to_numeric(frame["recent_vs_older_ratio"], errors="coerce").fillna(1.0).clip(0.60, 1.80)
    ytd_ratio = pd.to_numeric(frame["sales_2026_vs_2025_ratio"], errors="coerce").fillna(1.0).clip(0.60, 1.80)

    probability_uplift = 1.0 + ((probability - 0.50) * 0.18)
    score_uplift = 1.0 + ((score - 0.50) * 0.10)
    trend_uplift = 1.0 + ((recent_ratio - 1.0) * 0.18) + ((ytd_ratio - 1.0) * 0.12)
    frame["next_year_growth_multiplier"] = (probability_uplift * score_uplift * trend_uplift).clip(0.75, 1.35)
    frame["next_year_forecast_eur"] = frame["recent_weighted_sales_base_eur"] * frame["next_year_growth_multiplier"]

    active_history = frame[[
        "sales_2023_eur",
        "sales_2024_eur",
        "actual_sales_2025_eur",
        "sales_2026_ytd_eur",
    ]].sum(axis=1).gt(0)
    fallback = frame["next_year_forecast_eur"].le(0) & frame["improved_expected_sales_2025_eur"].gt(0)
    frame.loc[fallback, "next_year_forecast_eur"] = frame.loc[fallback, "improved_expected_sales_2025_eur"] * 0.35
    frame.loc[~active_history, "next_year_forecast_eur"] = frame.loc[~active_history, "improved_expected_sales_2025_eur"].fillna(0.0) * 0.25
    frame["next_year_forecast_eur"] = frame["next_year_forecast_eur"].clip(lower=0.0)
    frame["next_year_probability_weighted_eur"] = frame["next_year_forecast_eur"] * probability
    frame["next_year_vs_2025_actual_eur"] = frame["next_year_forecast_eur"] - frame["actual_sales_2025_eur"]
    frame["next_year_vs_2025_actual_pct"] = frame["next_year_vs_2025_actual_eur"] / frame["actual_sales_2025_eur"].replace(0, np.nan)
    frame["forecast_calendar_year"] = 2027
    frame["forecast_2027_eur"] = frame["next_year_forecast_eur"]
    frame["forecast_2027_probability_weighted_eur"] = frame["next_year_probability_weighted_eur"]
    frame["forecast_2027_vs_2025_actual_eur"] = frame["next_year_vs_2025_actual_eur"]
    frame["forecast_2027_vs_2025_actual_pct"] = frame["next_year_vs_2025_actual_pct"]
    frame["forecast_model_version"] = "recent_weighted_forward_2025_2026"
    frame["forecast_interpretation"] = np.select(
        [
            frame["next_year_vs_2025_actual_pct"].gt(0.10),
            frame["next_year_vs_2025_actual_pct"].lt(-0.10),
        ],
        ["growth_vs_2025", "lower_than_2025"],
        default="near_2025_level",
    )

    output_cols = [
        "business_id",
        "customer_name",
        "company",
        "priority",
        "company_segment",
        "sales_2023_eur",
        "sales_2024_eur",
        "actual_sales_2025_eur",
        "sales_2026_ytd_eur",
        "sales_2026_ytd_months",
        "sales_2026_annualization_method",
        "sales_2026_annualization_factor",
        "sales_2026_simple_annualization_factor",
        "sales_2026_annualized_eur",
        "sales_2025_same_months_eur",
        "sales_2025_full_year_eur",
        "recent_weighted_sales_base_eur",
        "recent_weighted_years_formula",
        "recent_vs_older_ratio",
        "sales_2026_vs_2025_ratio",
        "improved_probability_of_growth",
        "score",
        "forecast_calendar_year",
        "next_year_growth_multiplier",
        "next_year_forecast_eur",
        "forecast_2027_eur",
        "next_year_probability_weighted_eur",
        "forecast_2027_probability_weighted_eur",
        "next_year_vs_2025_actual_eur",
        "forecast_2027_vs_2025_actual_eur",
        "next_year_vs_2025_actual_pct",
        "forecast_2027_vs_2025_actual_pct",
        "forecast_interpretation",
        "positive_signals",
    ]
    output_cols = [col for col in output_cols if col in frame.columns]
    forecast = frame[output_cols].sort_values("next_year_forecast_eur", ascending=False)

    summary = pd.DataFrame([
        {"metric": "actual_sales_2025_eur", "value": frame["actual_sales_2025_eur"].sum(), "note": "2025 toteuma vertailutasoksi"},
        {"metric": "sales_2026_ytd_eur", "value": frame["sales_2026_ytd_eur"].sum(), "note": f"2026 YTD, {int(frame['sales_2026_ytd_months'].max())} kuukautta"},
        {"metric": "sales_2026_annualization_factor", "value": frame["sales_2026_annualization_factor"].max(), "note": "Annualisointikerroin 2025 saman jakson kausiprofiilista"},
        {"metric": "sales_2026_simple_annualization_factor", "value": frame["sales_2026_simple_annualization_factor"].max(), "note": "Vertailu: yksinkertainen 12 / kuukausien määrä"},
        {"metric": "sales_2026_annualized_eur", "value": frame["sales_2026_annualized_eur"].sum(), "note": "2026 YTD annualisoituna koko vuodeksi 2025 kausiprofiililla"},
        {"metric": "recent_weighted_sales_base_eur", "value": frame["recent_weighted_sales_base_eur"].sum(), "note": "2023 10 %, 2024 20 %, 2025 35 %, 2026 annualisoitu 35 %"},
        {"metric": "next_year_forecast_eur", "value": frame["next_year_forecast_eur"].sum(), "note": "Uusi seuraavan vuoden ennuste"},
        {"metric": "forecast_2027_eur", "value": frame["forecast_2027_eur"].sum(), "note": "Vuoden 2027 ennuste samalla laskennalla kuin next_year_forecast_eur"},
        {"metric": "next_year_vs_2025_actual_eur", "value": frame["next_year_forecast_eur"].sum() - frame["actual_sales_2025_eur"].sum(), "note": "Uuden ennusteen ero vuoden 2025 toteumaan"},
        {"metric": "forecast_2027_vs_2025_actual_eur", "value": frame["forecast_2027_eur"].sum() - frame["actual_sales_2025_eur"].sum(), "note": "Vuoden 2027 ennusteen ero vuoden 2025 toteumaan"},
        {"metric": "next_year_vs_2025_actual_pct", "value": (frame["next_year_forecast_eur"].sum() - frame["actual_sales_2025_eur"].sum()) / frame["actual_sales_2025_eur"].sum(), "note": "Prosentuaalinen ero 2025 toteumaan"},
        {"metric": "forecast_2027_vs_2025_actual_pct", "value": (frame["forecast_2027_eur"].sum() - frame["actual_sales_2025_eur"].sum()) / frame["actual_sales_2025_eur"].sum(), "note": "Vuoden 2027 ennusteen prosentuaalinen ero 2025 toteumaan"},
    ])
    return forecast, summary


def numeric_feature_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    feature_cols = [
        "sales_2023_eur",
        "sales_2024_eur",
        "sales_2026_ytd_eur",
        "active_months_2023_2024",
        "active_months_2024",
        "order_rows_2024",
        "sales_2024_q1_eur",
        "sales_2024_q2_eur",
        "sales_2024_q3_eur",
        "sales_2024_q4_eur",
        "avg_monthly_sales_2024_eur",
        "sales_momentum_2024_vs_2023",
        "h2_vs_h1_2024",
        "days_since_last_purchase_at_2025_start",
        "product_group_count_2024",
        "score",
        "current_probability_of_growth",
        "current_model_conditional_eur",
        "current_model_expected_eur",
        "revenue_k_eur",
        "segment_lift",
    ]
    available = [col for col in feature_cols if col in frame.columns]
    x = frame[available].copy()
    for col in available:
        x[col] = pd.to_numeric(x[col], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return x, available


def fit_backtest_models(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    scored = frame.copy()
    x, feature_cols = numeric_feature_frame(scored)
    y_growth = scored["grew_2025"].astype(int)
    y_sales = scored["actual_sales_2025_eur"].clip(lower=0)

    min_class = y_growth.value_counts().min() if y_growth.nunique() > 1 else 0
    n_splits = int(max(2, min(5, min_class))) if min_class >= 2 else 0

    if n_splits >= 2:
        clf = make_pipeline(
            StandardScaler(),
            RandomForestClassifier(
                n_estimators=250,
                min_samples_leaf=15,
                random_state=42,
                n_jobs=-1,
                class_weight="balanced_subsample",
            ),
        )
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
        prob = cross_val_predict(clf, x, y_growth, cv=cv, method="predict_proba")[:, 1]
        clf.fit(x, y_growth)
    else:
        prob = np.repeat(float(y_growth.mean()), len(scored))
        clf = None

    reg = RandomForestRegressor(
        n_estimators=250,
        min_samples_leaf=10,
        random_state=42,
        n_jobs=-1,
    )
    rcv = KFold(n_splits=min(5, max(2, len(scored) // 100)), shuffle=True, random_state=42)
    pred_sales = cross_val_predict(reg, x, y_sales, cv=rcv)
    improved_conditional = pred_sales.clip(min=0)
    reg.fit(x, y_sales)

    calibration = calibrate_probability(scored["current_probability_of_growth"], y_growth)
    scored["calibrated_current_probability"] = calibration["calibrated_values"]
    scored["improved_probability_of_growth"] = np.clip(prob, 0.01, 0.99)
    scored["improved_predicted_annual_sales_2025_eur"] = improved_conditional
    scored["improved_probability_weighted_sales_2025_eur"] = scored["improved_probability_of_growth"] * improved_conditional
    scored["improved_expected_sales_2025_eur"] = scored["improved_predicted_annual_sales_2025_eur"]
    scored["calibrated_current_expected_eur"] = scored["calibrated_current_probability"] * scored["current_model_conditional_eur"]
    scored["current_model_error_eur"] = scored["current_model_expected_eur"] - scored["actual_sales_2025_eur"]
    scored["calibrated_current_error_eur"] = scored["calibrated_current_expected_eur"] - scored["actual_sales_2025_eur"]
    scored["improved_model_error_eur"] = scored["improved_expected_sales_2025_eur"] - scored["actual_sales_2025_eur"]

    importance = pd.DataFrame(columns=["feature", "importance_mean", "importance_std"])
    if clf is not None and len(feature_cols) > 0:
        try:
            result = permutation_importance(clf, x, y_growth, n_repeats=5, random_state=42, n_jobs=-1)
            importance = pd.DataFrame({
                "feature": feature_cols,
                "importance_mean": result.importances_mean,
                "importance_std": result.importances_std,
            }).sort_values("importance_mean", ascending=False)
        except Exception:
            importance = pd.DataFrame({"feature": feature_cols, "importance_mean": np.nan, "importance_std": np.nan})
    return scored, importance


def calibrate_probability(raw_probability: pd.Series, y: pd.Series) -> dict[str, Any]:
    raw = pd.to_numeric(raw_probability, errors="coerce").fillna(raw_probability.mean() if raw_probability.notna().any() else 0.0)
    raw = raw.clip(0.0, 1.0)
    if y.nunique() > 1 and raw.nunique() > 2:
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.01, y_max=0.99)
        calibrated = iso.fit_transform(raw, y)
    else:
        calibrated = np.repeat(float(y.mean()), len(y))
    return {"calibrated_values": calibrated}


def probability_calibration_table(frame: pd.DataFrame) -> pd.DataFrame:
    table_frame = frame.copy()
    try:
        table_frame["probability_bin"] = pd.qcut(table_frame["current_probability_of_growth"], 10, duplicates="drop")
    except ValueError:
        table_frame["probability_bin"] = pd.cut(table_frame["current_probability_of_growth"], 5)
    table = table_frame.groupby("probability_bin", observed=False).agg(
        customers=("business_id", "count"),
        avg_raw_probability=("current_probability_of_growth", "mean"),
        avg_calibrated_probability=("calibrated_current_probability", "mean"),
        observed_growth_rate_2025=("grew_2025", "mean"),
        actual_sales_2025_eur=("actual_sales_2025_eur", "sum"),
        current_expected_eur=("current_model_expected_eur", "sum"),
        calibrated_current_expected_eur=("calibrated_current_expected_eur", "sum"),
        improved_expected_eur=("improved_expected_sales_2025_eur", "sum"),
    ).reset_index()
    table["probability_bin"] = table["probability_bin"].astype(str)
    return table


def prediction_metrics(frame: pd.DataFrame, pred_col: str, label: str) -> dict[str, Any]:
    actual = frame["actual_sales_2025_eur"].astype(float)
    pred = frame[pred_col].astype(float).fillna(0.0)
    rmse = math.sqrt(mean_squared_error(actual, pred))
    mape_frame = frame[actual.gt(100)].copy()
    mape = np.nan
    if len(mape_frame):
        mape = (np.abs(mape_frame[pred_col] - mape_frame["actual_sales_2025_eur"]) / mape_frame["actual_sales_2025_eur"]).mean()
    corr = np.nan if pred.nunique() <= 1 or actual.nunique() <= 1 else pred.corr(actual)
    return {
        "model": label,
        "customers": len(frame),
        "actual_sales_2025_eur": actual.sum(),
        "predicted_eur": pred.sum(),
        "bias_eur": pred.sum() - actual.sum(),
        "mae_eur": mean_absolute_error(actual, pred),
        "rmse_eur": rmse,
        "median_abs_error_eur": np.median(np.abs(pred - actual)),
        "mape_actual_over_100eur": mape,
        "correlation": corr,
    }


def build_error_analysis(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    abs_error = result["improved_model_error_eur"].abs()
    threshold = np.maximum(5000.0, result["actual_sales_2025_eur"].abs() * 0.50)
    result["error_bucket"] = np.select(
        [
            abs_error <= np.maximum(1000.0, result["actual_sales_2025_eur"].abs() * 0.20),
            result["improved_model_error_eur"] > threshold,
            result["improved_model_error_eur"] < -threshold,
            result["actual_sales_2025_eur"].eq(0) & result["improved_expected_sales_2025_eur"].gt(5000),
        ],
        ["good_fit", "model_over_high", "model_under_high", "no_actual_sales_high_prediction"],
        default="medium_error",
    )
    result["absolute_error_eur"] = abs_error
    cols = [
        "business_id",
        "customer_name",
        "company",
        "priority",
        "company_segment",
        "actual_sales_2025_eur",
        "sales_2024_eur",
        "current_model_expected_eur",
        "calibrated_current_expected_eur",
        "improved_expected_sales_2025_eur",
        "improved_probability_weighted_sales_2025_eur",
        "current_model_error_eur",
        "improved_model_error_eur",
        "absolute_error_eur",
        "current_probability_of_growth",
        "calibrated_current_probability",
        "improved_probability_of_growth",
        "error_bucket",
        "positive_signals",
    ]
    available = [col for col in cols if col in result.columns]
    return result[available].sort_values("absolute_error_eur", ascending=False)


def build_sales_feedback_template(error_analysis: pd.DataFrame) -> pd.DataFrame:
    template = error_analysis.head(500).copy()
    template["sales_feedback_type"] = ""
    template["sales_corrected_potential_eur"] = ""
    template["exclude_from_training"] = ""
    template["reason_code"] = ""
    template["missing_product_groups"] = ""
    template["sales_notes"] = ""
    return template


def build_product_group_model(grouped_sales: pd.DataFrame, customer_frame: pd.DataFrame, recommendations: pd.DataFrame) -> pd.DataFrame:
    valid = grouped_sales[grouped_sales["business_id"].notna()].copy()
    valid = valid[valid["year"].isin([2024, 2025])]
    top_groups = (
        valid.groupby(["lowest_product_group_code", "lowest_product_group_name"], dropna=False)["total_value"]
        .sum()
        .sort_values(ascending=False)
        .head(60)
        .reset_index()
    )
    customers = customer_frame[["business_id", "customer_name", "company_segment", "sales_2024_eur", "actual_sales_2025_eur"]].drop_duplicates("business_id")
    grid = customers.assign(_key=1).merge(top_groups.assign(_key=1), on="_key", how="outer").drop(columns="_key")
    sales_pg = (
        valid.groupby(["business_id", "lowest_product_group_code", "lowest_product_group_name", "year"])["total_value"]
        .sum()
        .unstack(fill_value=0.0)
        .reset_index()
    )
    for year in [2024, 2025]:
        if year not in sales_pg.columns:
            sales_pg[year] = 0.0
    sales_pg = sales_pg.rename(columns={2024: "customer_group_sales_2024_eur", 2025: "actual_group_sales_2025_eur"})
    grid = grid.merge(sales_pg, on=["business_id", "lowest_product_group_code", "lowest_product_group_name"], how="left")
    grid["customer_group_sales_2024_eur"] = grid["customer_group_sales_2024_eur"].fillna(0.0)
    grid["actual_group_sales_2025_eur"] = grid["actual_group_sales_2025_eur"].fillna(0.0)
    grid["customer_group_share_2024"] = grid["customer_group_sales_2024_eur"] / grid["sales_2024_eur"].replace(0, np.nan)
    grid["customer_group_share_2024"] = grid["customer_group_share_2024"].fillna(0.0)

    group_totals = (
        grid.groupby(["company_segment", "lowest_product_group_code", "lowest_product_group_name"])
        .agg(segment_group_sales_2024_eur=("customer_group_sales_2024_eur", "sum"), segment_total_sales_2024_eur=("sales_2024_eur", "sum"))
        .reset_index()
    )
    group_totals["similar_customer_group_share_2024"] = group_totals["segment_group_sales_2024_eur"] / group_totals["segment_total_sales_2024_eur"].replace(0, np.nan)
    group_totals["similar_customer_group_share_2024"] = group_totals["similar_customer_group_share_2024"].fillna(0.0)
    grid = grid.merge(group_totals, on=["company_segment", "lowest_product_group_code", "lowest_product_group_name"], how="left")
    grid["white_space_gap_2024"] = (grid["similar_customer_group_share_2024"] - grid["customer_group_share_2024"]).clip(lower=0.0)
    grid["product_group_model_expected_2025_eur"] = grid["sales_2024_eur"] * grid["white_space_gap_2024"]

    rec = recommendations.rename(columns={
        "product_group_code": "lowest_product_group_code",
        "product_group_name": "lowest_product_group_name",
    })
    rec_cols = [
        "business_id",
        "lowest_product_group_code",
        "lowest_product_group_name",
        "recommended_group_expected_potential_eur",
        "recommended_group_potential_eur",
        "recommendation_rank",
    ]
    rec_cols = [col for col in rec_cols if col in rec.columns]
    grid = grid.merge(rec[rec_cols], on=["business_id", "lowest_product_group_code", "lowest_product_group_name"], how="left")
    grid["recommended_group_expected_potential_eur"] = pd.to_numeric(grid.get("recommended_group_expected_potential_eur"), errors="coerce").fillna(0.0)
    grid["product_group_error_eur"] = grid["product_group_model_expected_2025_eur"] - grid["actual_group_sales_2025_eur"]
    grid, _ = apply_product_group_calibration(grid)
    return grid.sort_values(["business_id", "product_group_calibrated_expected_2025_eur"], ascending=[True, False])


def apply_product_group_calibration(pg: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = pg.copy()
    global_actual = frame["actual_group_sales_2025_eur"].sum()
    global_expected = frame["product_group_model_expected_2025_eur"].sum()
    global_factor = global_actual / global_expected if global_expected > 0 else 1.0

    calibration = frame.groupby(["lowest_product_group_code", "lowest_product_group_name"]).agg(
        customers=("business_id", "count"),
        buyers_2025=("actual_group_sales_2025_eur", lambda s: int((s > 0).sum())),
        actual_group_sales_2025_eur=("actual_group_sales_2025_eur", "sum"),
        product_group_model_expected_2025_eur=("product_group_model_expected_2025_eur", "sum"),
        current_recommendation_expected_eur=("recommended_group_expected_potential_eur", "sum"),
    ).reset_index()
    calibration["raw_calibration_factor"] = calibration["actual_group_sales_2025_eur"] / calibration["product_group_model_expected_2025_eur"].replace(0, np.nan)
    calibration["raw_calibration_factor"] = calibration["raw_calibration_factor"].replace([np.inf, -np.inf], np.nan)
    calibration["buyer_credibility"] = (calibration["buyers_2025"] / 50.0).clip(lower=0.0, upper=1.0)
    calibration["sales_credibility"] = (calibration["actual_group_sales_2025_eur"] / 250000.0).clip(lower=0.0, upper=1.0)
    calibration["calibration_credibility"] = calibration[["buyer_credibility", "sales_credibility"]].max(axis=1)
    calibration["product_group_calibration_factor"] = (
        calibration["raw_calibration_factor"].fillna(global_factor) * calibration["calibration_credibility"]
        + global_factor * (1.0 - calibration["calibration_credibility"])
    ).clip(lower=0.25, upper=6.0)
    calibration["calibration_method"] = np.select(
        [
            calibration["calibration_credibility"].ge(0.80),
            calibration["calibration_credibility"].ge(0.40),
        ],
        ["group_specific_high_confidence", "group_specific_smoothed"],
        default="global_ratio_heavily_smoothed",
    )
    calibration["global_calibration_factor"] = global_factor

    factor_cols = [
        "lowest_product_group_code",
        "lowest_product_group_name",
        "product_group_calibration_factor",
        "raw_calibration_factor",
        "calibration_credibility",
        "calibration_method",
        "global_calibration_factor",
    ]
    frame = frame.merge(calibration[factor_cols], on=["lowest_product_group_code", "lowest_product_group_name"], how="left")
    frame["product_group_calibration_factor"] = frame["product_group_calibration_factor"].fillna(global_factor).clip(lower=0.25, upper=6.0)
    frame["product_group_calibrated_expected_2025_eur"] = frame["product_group_model_expected_2025_eur"] * frame["product_group_calibration_factor"]
    frame["product_group_calibrated_error_eur"] = frame["product_group_calibrated_expected_2025_eur"] - frame["actual_group_sales_2025_eur"]
    frame["recommended_group_calibrated_expected_potential_eur"] = frame["recommended_group_expected_potential_eur"] * frame["product_group_calibration_factor"]
    return frame, calibration


def summarize_product_group_model(pg: pd.DataFrame) -> pd.DataFrame:
    summary = pg.groupby(["lowest_product_group_code", "lowest_product_group_name"]).agg(
        customers=("business_id", "count"),
        buyers_2025=("actual_group_sales_2025_eur", lambda s: int((s > 0).sum())),
        actual_group_sales_2025_eur=("actual_group_sales_2025_eur", "sum"),
        product_group_model_expected_2025_eur=("product_group_model_expected_2025_eur", "sum"),
        product_group_calibrated_expected_2025_eur=("product_group_calibrated_expected_2025_eur", "sum"),
        current_recommendation_expected_eur=("recommended_group_expected_potential_eur", "sum"),
        calibrated_recommendation_expected_eur=("recommended_group_calibrated_expected_potential_eur", "sum"),
        product_group_calibration_factor=("product_group_calibration_factor", "first"),
        raw_calibration_factor=("raw_calibration_factor", "first"),
        calibration_credibility=("calibration_credibility", "first"),
        calibration_method=("calibration_method", "first"),
        mae_eur=("product_group_error_eur", lambda s: float(np.abs(s).mean())),
        calibrated_mae_eur=("product_group_calibrated_error_eur", lambda s: float(np.abs(s).mean())),
    ).reset_index()
    summary["buyer_rate_2025"] = summary["buyers_2025"] / summary["customers"].replace(0, np.nan)
    summary["bias_eur"] = summary["product_group_model_expected_2025_eur"] - summary["actual_group_sales_2025_eur"]
    summary["calibrated_bias_eur"] = summary["product_group_calibrated_expected_2025_eur"] - summary["actual_group_sales_2025_eur"]
    summary["absolute_bias_eur"] = summary["bias_eur"].abs()
    summary["calibrated_absolute_bias_eur"] = summary["calibrated_bias_eur"].abs()
    summary["bias_improvement_pct"] = 1.0 - (summary["calibrated_absolute_bias_eur"] / summary["absolute_bias_eur"].replace(0, np.nan))
    summary["mae_improvement_pct"] = 1.0 - (summary["calibrated_mae_eur"] / summary["mae_eur"].replace(0, np.nan))
    return summary.sort_values("actual_group_sales_2025_eur", ascending=False)


def calibrate_current_recommendations(recommendations: pd.DataFrame, pg_calibration: pd.DataFrame) -> pd.DataFrame:
    frame = recommendations.rename(columns={
        "product_group_code": "lowest_product_group_code",
        "product_group_name": "lowest_product_group_name",
    }).copy()
    factor_cols = [
        "lowest_product_group_code",
        "lowest_product_group_name",
        "product_group_calibration_factor",
        "raw_calibration_factor",
        "calibration_credibility",
        "calibration_method",
        "actual_group_sales_2025_eur",
        "product_group_model_expected_2025_eur",
        "product_group_calibrated_expected_2025_eur",
    ]
    frame = frame.merge(pg_calibration[factor_cols], on=["lowest_product_group_code", "lowest_product_group_name"], how="left")
    global_factor = (
        pg_calibration["actual_group_sales_2025_eur"].sum()
        / pg_calibration["product_group_model_expected_2025_eur"].sum()
        if pg_calibration["product_group_model_expected_2025_eur"].sum() > 0
        else 1.0
    )
    frame["product_group_calibration_factor"] = frame["product_group_calibration_factor"].fillna(global_factor).clip(lower=0.25, upper=6.0)
    frame["calibration_method"] = frame["calibration_method"].fillna("global_factor_for_unseen_group")
    frame["recommended_group_expected_potential_eur_raw"] = pd.to_numeric(frame["recommended_group_expected_potential_eur"], errors="coerce").fillna(0.0)
    frame["recommended_group_calibrated_expected_potential_eur"] = (
        frame["recommended_group_expected_potential_eur_raw"] * frame["product_group_calibration_factor"]
    )
    frame["product_group_code"] = frame["lowest_product_group_code"]
    frame["product_group_name"] = frame["lowest_product_group_name"]
    frame = frame.sort_values(
        ["business_id", "recommended_group_calibrated_expected_potential_eur"],
        ascending=[True, False],
    )
    frame["calibrated_recommendation_rank"] = frame.groupby("business_id").cumcount() + 1
    return frame


def build_sales_potential_case(
    next_year_forecast: pd.DataFrame,
    recommendations_calibrated: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    recs = recommendations_calibrated.copy()
    recs["recommended_group_calibrated_expected_potential_eur"] = pd.to_numeric(
        recs["recommended_group_calibrated_expected_potential_eur"], errors="coerce"
    ).fillna(0.0).clip(lower=0.0)
    recs["calibrated_recommendation_rank"] = pd.to_numeric(
        recs.get("calibrated_recommendation_rank"), errors="coerce"
    ).fillna(9999)

    top_recs = recs[recs["calibrated_recommendation_rank"].le(10)].copy()
    growth_pool = (
        top_recs.groupby("business_id", dropna=False)
        .agg(
            product_group_growth_pool_eur=("recommended_group_calibrated_expected_potential_eur", "sum"),
            recommended_product_group_count=("lowest_product_group_name", "nunique"),
        )
        .reset_index()
    )

    top_names = (
        top_recs[top_recs["calibrated_recommendation_rank"].le(3)]
        .sort_values(["business_id", "calibrated_recommendation_rank"])
        .groupby("business_id")["lowest_product_group_name"]
        .apply(lambda values: ", ".join(str(value) for value in values.dropna().head(3)))
        .rename("top_recommended_product_groups")
        .reset_index()
    )
    growth_pool = growth_pool.merge(top_names, on="business_id", how="left")

    frame = next_year_forecast.copy().merge(growth_pool, on="business_id", how="left")
    frame["product_group_growth_pool_eur"] = frame["product_group_growth_pool_eur"].fillna(0.0)
    frame["recommended_product_group_count"] = frame["recommended_product_group_count"].fillna(0).astype(int)
    frame["top_recommended_product_groups"] = frame["top_recommended_product_groups"].fillna("")

    probability = pd.to_numeric(frame["improved_probability_of_growth"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    base_forecast = pd.to_numeric(frame["next_year_forecast_eur"], errors="coerce").fillna(0.0).clip(lower=0.0)
    actual_2025 = pd.to_numeric(frame["actual_sales_2025_eur"], errors="coerce").fillna(0.0).clip(lower=0.0)
    reference_level = pd.concat([base_forecast, actual_2025], axis=1).max(axis=1)

    priority = frame.get("priority", pd.Series("", index=frame.index)).astype(str).str.upper().str.strip()
    priority_multiplier = priority.map({"A": 1.00, "B": 0.85, "C": 0.65, "D": 0.45}).fillna(0.55)
    cap_pct = priority.map({"A": 0.60, "B": 0.45, "C": 0.30, "D": 0.20}).fillna(0.25)
    cap_floor = priority.map({"A": 15000.0, "B": 10000.0, "C": 6000.0, "D": 3000.0}).fillna(5000.0)

    probability_factor = (0.70 + probability).clip(0.75, 1.35)
    raw_growth = frame["product_group_growth_pool_eur"] * priority_multiplier * probability_factor
    growth_cap = np.maximum(reference_level * cap_pct, cap_floor)

    frame["base_forecast_eur"] = base_forecast
    frame["forecast_calendar_year"] = 2027
    frame["base_forecast_2027_eur"] = frame["base_forecast_eur"]
    frame["sales_potential_reference_eur"] = reference_level
    frame["growth_potential_eur"] = np.minimum(raw_growth, growth_cap).clip(lower=0.0)
    frame["growth_potential_2027_eur"] = frame["growth_potential_eur"]
    frame["realistic_potential_eur"] = frame["sales_potential_reference_eur"] + frame["growth_potential_eur"]
    frame["upside_potential_eur"] = frame["sales_potential_reference_eur"] + np.minimum(
        frame["product_group_growth_pool_eur"], growth_cap * 1.50
    ).clip(lower=0.0)
    frame["realistic_potential_2027_eur"] = frame["realistic_potential_eur"]
    frame["upside_potential_2027_eur"] = frame["upside_potential_eur"]
    frame["growth_opportunity_pct"] = frame["growth_potential_eur"] / frame["sales_potential_reference_eur"].replace(0, np.nan)
    frame["realistic_potential_vs_2025_eur"] = frame["realistic_potential_eur"] - actual_2025
    frame["realistic_potential_vs_2025_pct"] = frame["realistic_potential_vs_2025_eur"] / actual_2025.replace(0, np.nan)
    frame["potential_case_version"] = "forecast_plus_calibrated_product_group_white_space"

    frame["recommended_growth_action"] = np.select(
        [
            frame["sales_2026_ytd_eur"].le(0) & actual_2025.gt(0),
            frame["growth_potential_eur"].gt(25000),
            frame["growth_potential_eur"].gt(5000),
        ],
        [
            "Reactivate customer and test top product groups",
            "Expand into top recommended product groups",
            "Target selected white-space product groups",
        ],
        default="Maintain base sales and monitor opportunity",
    )

    output_cols = [
        "business_id",
        "customer_name",
        "company",
        "priority",
        "company_segment",
        "actual_sales_2025_eur",
        "sales_2026_ytd_eur",
        "sales_2026_annualized_eur",
        "forecast_calendar_year",
        "base_forecast_eur",
        "base_forecast_2027_eur",
        "sales_potential_reference_eur",
        "product_group_growth_pool_eur",
        "growth_potential_eur",
        "growth_potential_2027_eur",
        "realistic_potential_eur",
        "realistic_potential_2027_eur",
        "upside_potential_eur",
        "upside_potential_2027_eur",
        "growth_opportunity_pct",
        "realistic_potential_vs_2025_eur",
        "realistic_potential_vs_2025_pct",
        "improved_probability_of_growth",
        "score",
        "recommended_product_group_count",
        "top_recommended_product_groups",
        "recommended_growth_action",
        "potential_case_version",
        "positive_signals",
    ]
    output_cols = [col for col in output_cols if col in frame.columns]
    potential = frame[output_cols].sort_values("realistic_potential_eur", ascending=False)

    actual_sum = actual_2025.sum()
    summary = pd.DataFrame([
        {"metric": "actual_sales_2025_eur", "value": actual_sum, "note": "2025 toteuma vertailutasoksi"},
        {"metric": "base_forecast_eur", "value": frame["base_forecast_eur"].sum(), "note": "Konservatiivinen run-rate ennuste"},
        {"metric": "base_forecast_2027_eur", "value": frame["base_forecast_2027_eur"].sum(), "note": "Vuoden 2027 konservatiivinen run-rate ennuste samalla laskennalla"},
        {"metric": "product_group_growth_pool_eur", "value": frame["product_group_growth_pool_eur"].sum(), "note": "Kalibroitujen tuoteryhmäsuositusten bruttokasvumahdollisuus"},
        {"metric": "growth_potential_eur", "value": frame["growth_potential_eur"].sum(), "note": "Todennäköisyys-, prioriteetti- ja katto-oikaistu kasvupotentiaali"},
        {"metric": "growth_potential_2027_eur", "value": frame["growth_potential_2027_eur"].sum(), "note": "Vuodelle 2027 nimetty kasvupotentiaali samalla laskennalla"},
        {"metric": "realistic_potential_eur", "value": frame["realistic_potential_eur"].sum(), "note": "Myynnillinen potentiaalicase: vertailutaso + kasvupotentiaali"},
        {"metric": "realistic_potential_2027_eur", "value": frame["realistic_potential_2027_eur"].sum(), "note": "Vuoden 2027 myynnillinen potentiaalicase samalla laskennalla"},
        {"metric": "upside_potential_eur", "value": frame["upside_potential_eur"].sum(), "note": "Korkeampi upside-skenaario tuoteryhmäavauksille"},
        {"metric": "upside_potential_2027_eur", "value": frame["upside_potential_2027_eur"].sum(), "note": "Vuoden 2027 upside-skenaario samalla laskennalla"},
        {"metric": "realistic_potential_vs_2025_eur", "value": frame["realistic_potential_eur"].sum() - actual_sum, "note": "Potentiaalicasen ero vuoden 2025 toteumaan"},
        {"metric": "realistic_potential_vs_2025_pct", "value": (frame["realistic_potential_eur"].sum() - actual_sum) / actual_sum if actual_sum else np.nan, "note": "Potentiaalicasen prosentuaalinen kasvu vuoden 2025 toteumaan"},
        {"metric": "customers_with_positive_growth_potential", "value": int(frame["growth_potential_eur"].gt(0).sum()), "note": "Asiakkaat, joille malli loytaa positiivista tuoteryhmakasvua"},
    ])
    return potential, summary


def build_crm_potential_validation(
    sales_potential_case: pd.DataFrame,
    crm_potentials: pd.DataFrame,
    accounts: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    crm = crm_potentials.copy()
    crm["_crm_row_id"] = np.arange(1, len(crm) + 1)
    crm["crm_normalized_name"] = crm.get("Name", pd.Series("", index=crm.index)).map(normalize_customer_name)
    crm["crm_sales_eur"] = pd.to_numeric(crm.get("Sales"), errors="coerce").fillna(0.0)
    crm["crm_probability"] = pd.to_numeric(crm.get("Probability"), errors="coerce").fillna(0.0)
    crm.loc[crm["crm_probability"].gt(1.0), "crm_probability"] = crm.loc[crm["crm_probability"].gt(1.0), "crm_probability"] / 100.0
    crm["crm_probability"] = crm["crm_probability"].clip(lower=0.0, upper=1.0)
    crm["crm_expected_sales_eur"] = crm["crm_sales_eur"] * crm["crm_probability"]
    crm["crm_status_text"] = crm.get("Status", pd.Series("", index=crm.index)).fillna("").astype(str).str.strip()
    crm["crm_type_text"] = crm.get("Type", pd.Series("", index=crm.index)).fillna("").astype(str).str.strip()

    crm_agg = (
        crm[crm["crm_normalized_name"].ne("")]
        .groupby("crm_normalized_name", dropna=False)
        .agg(
            crm_name=("Name", "first"),
            crm_source_row_count=("_crm_row_id", "size"),
            crm_source_row_ids=("_crm_row_id", lambda s: ", ".join(str(int(v)) for v in s)),
            crm_statuses=("crm_status_text", lambda s: ", ".join(sorted(set(v for v in s if v)))),
            crm_types=("crm_type_text", lambda s: ", ".join(sorted(set(v for v in s if v)))),
            crm_sales_eur=("crm_sales_eur", "sum"),
            crm_expected_sales_eur=("crm_expected_sales_eur", "sum"),
            crm_max_probability=("crm_probability", "max"),
        )
        .reset_index()
    )

    account_lookup = accounts[["business_id", "account_id", "customer_name"]].dropna(subset=["business_id"]).copy()
    account_lookup["crm_normalized_name"] = account_lookup["customer_name"].map(normalize_customer_name)
    account_lookup = account_lookup[account_lookup["crm_normalized_name"].ne("")]
    name_counts = account_lookup.groupby("crm_normalized_name")["business_id"].nunique().rename("account_name_business_id_count")
    account_lookup = (
        account_lookup.sort_values(["crm_normalized_name", "business_id"])
        .drop_duplicates("crm_normalized_name")
        .merge(name_counts, on="crm_normalized_name", how="left")
    )
    crm_agg = crm_agg.merge(
        account_lookup[["crm_normalized_name", "business_id", "account_id", "customer_name", "account_name_business_id_count"]],
        on="crm_normalized_name",
        how="left",
    )
    crm_agg["crm_match_quality"] = np.select(
        [
            crm_agg["business_id"].notna() & crm_agg["account_name_business_id_count"].eq(1),
            crm_agg["business_id"].notna() & crm_agg["account_name_business_id_count"].gt(1),
        ],
        ["name_match_unique", "name_match_ambiguous"],
        default="no_account_match",
    )

    crm_matched = crm_agg[crm_agg["business_id"].notna()].copy()
    crm_matched["business_id"] = crm_matched["business_id"].map(normalize_business_id)
    crm_by_business = (
        crm_matched.groupby("business_id", dropna=False)
        .agg(
            crm_name=("crm_name", "first"),
            crm_source_row_count=("crm_source_row_count", "sum"),
            crm_source_row_ids=("crm_source_row_ids", lambda s: "; ".join(str(v) for v in s if str(v))),
            crm_statuses=("crm_statuses", lambda s: ", ".join(sorted(set(part.strip() for value in s for part in str(value).split(",") if part.strip())))),
            crm_types=("crm_types", lambda s: ", ".join(sorted(set(part.strip() for value in s for part in str(value).split(",") if part.strip())))),
            crm_sales_eur=("crm_sales_eur", "sum"),
            crm_expected_sales_eur=("crm_expected_sales_eur", "sum"),
            crm_max_probability=("crm_max_probability", "max"),
            crm_match_quality=("crm_match_quality", lambda s: "name_match_ambiguous" if (s == "name_match_ambiguous").any() else "name_match_unique"),
        )
        .reset_index()
    )

    frame = sales_potential_case.copy().merge(crm_by_business, on="business_id", how="left")
    frame["crm_found"] = frame["crm_source_row_count"].notna()
    for col in ["crm_sales_eur", "crm_expected_sales_eur", "crm_max_probability"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["crm_source_row_count"] = frame["crm_source_row_count"].fillna(0).astype(int)
    frame["crm_match_quality"] = frame["crm_match_quality"].fillna("missing_in_crm")
    frame["crm_statuses"] = frame["crm_statuses"].fillna("")
    frame["crm_types"] = frame["crm_types"].fillna("")
    frame["crm_name"] = frame["crm_name"].fillna("")

    original = pd.to_numeric(frame["realistic_potential_2027_eur"], errors="coerce").fillna(0.0)
    crm_expected = pd.to_numeric(frame["crm_expected_sales_eur"], errors="coerce")
    frame["crm_validated_realistic_potential_2027_eur"] = np.where(
        frame["crm_found"] & crm_expected.gt(original),
        crm_expected,
        original,
    )
    frame["crm_value_action"] = np.select(
        [
            ~frame["crm_found"],
            frame["crm_found"] & crm_expected.gt(original),
            frame["crm_found"] & crm_expected.le(original),
        ],
        [
            "kept_original_no_crm_match",
            "raised_to_crm_expected_sales",
            "kept_original_model_not_below_crm",
        ],
        default="kept_original",
    )
    frame["crm_potential_diff_eur"] = original - crm_expected
    frame["crm_potential_diff_pct"] = frame["crm_potential_diff_eur"] / crm_expected.replace(0, np.nan)
    frame["crm_validation_status"] = np.select(
        [
            ~frame["crm_found"],
            frame["crm_found"] & crm_expected.gt(original * 1.20),
            frame["crm_found"] & original.gt(crm_expected * 1.20),
            frame["crm_found"],
        ],
        [
            "missing_in_crm_kept_original",
            "model_may_be_too_low",
            "model_above_crm_pipeline",
            "aligned_with_crm",
        ],
        default="not_checked",
    )

    output_cols = [
        "business_id",
        "customer_name",
        "company",
        "priority",
        "forecast_calendar_year",
        "base_forecast_2027_eur",
        "growth_potential_2027_eur",
        "realistic_potential_2027_eur",
        "upside_potential_2027_eur",
        "crm_found",
        "crm_match_quality",
        "crm_name",
        "crm_source_row_count",
        "crm_statuses",
        "crm_types",
        "crm_sales_eur",
        "crm_max_probability",
        "crm_expected_sales_eur",
        "crm_validated_realistic_potential_2027_eur",
        "crm_value_action",
        "crm_potential_diff_eur",
        "crm_potential_diff_pct",
        "crm_validation_status",
        "top_recommended_product_groups",
        "recommended_growth_action",
        "positive_signals",
    ]
    validation = frame[[col for col in output_cols if col in frame.columns]].sort_values(
        ["crm_found", "crm_expected_sales_eur", "realistic_potential_2027_eur"],
        ascending=[False, False, False],
    )

    unmatched_crm = crm_agg[crm_agg["business_id"].isna()].copy()
    unmatched_summary = pd.DataFrame([
        {"metric": "crm_rows_input", "value": len(crm), "note": "CRM-potentials alkuperaiset rivit"},
        {"metric": "crm_unique_names", "value": len(crm_agg), "note": "CRM-rivit aggregoituna normalisoidulle nimelle"},
        {"metric": "crm_names_matched_to_account", "value": int(crm_agg["business_id"].notna().sum()), "note": "CRM-nimet, joille loytyi account-aineistosta asiakas"},
        {"metric": "crm_names_not_matched_to_account", "value": len(unmatched_crm), "note": "CRM-nimet, joille ei loytynyt account-osumaa"},
        {"metric": "model_customers_with_crm_match", "value": int(validation["crm_found"].sum()), "note": "Malliasiakkaat, joille loytyi CRM-osuma"},
        {"metric": "model_customers_without_crm_match_kept_original", "value": int((~validation["crm_found"]).sum()), "note": "Malliasiakkaat ilman CRM-osumaa; alkuperainen arvo sailyi"},
        {"metric": "model_may_be_too_low_count", "value": int(validation["crm_validation_status"].eq("model_may_be_too_low").sum()), "note": "CRM expected sales yli 20 % mallin realistisen potentiaalin"},
        {"metric": "raised_to_crm_expected_sales_count", "value": int(validation["crm_value_action"].eq("raised_to_crm_expected_sales").sum()), "note": "Rivit, joissa validointiarvo nostettiin CRM-odotusarvoon"},
    ])
    return validation, unmatched_crm, unmatched_summary


def build_summary(customer_backtest: pd.DataFrame, pg_summary: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        prediction_metrics(customer_backtest, "current_model_expected_eur", "current_model_expected"),
        prediction_metrics(customer_backtest, "calibrated_current_expected_eur", "calibrated_current_model"),
        prediction_metrics(customer_backtest, "improved_expected_sales_2025_eur", "history_feature_model"),
    ]
    summary = pd.DataFrame(metrics)
    try:
        summary.loc[summary["model"].eq("current_model_expected"), "growth_auc"] = roc_auc_score(
            customer_backtest["grew_2025"], customer_backtest["current_probability_of_growth"]
        )
        summary.loc[summary["model"].eq("calibrated_current_model"), "growth_auc"] = roc_auc_score(
            customer_backtest["grew_2025"], customer_backtest["calibrated_current_probability"]
        )
        summary.loc[summary["model"].eq("history_feature_model"), "growth_auc"] = roc_auc_score(
            customer_backtest["grew_2025"], customer_backtest["improved_probability_of_growth"]
        )
    except Exception:
        summary["growth_auc"] = np.nan

    extra = pd.DataFrame([
        {"model": "input_customers", "customers": len(customer_backtest), "actual_sales_2025_eur": customer_backtest["actual_sales_2025_eur"].sum()},
        {
            "model": "product_group_rows_raw",
            "customers": len(pg_summary),
            "actual_sales_2025_eur": pg_summary["actual_group_sales_2025_eur"].sum(),
            "predicted_eur": pg_summary["product_group_model_expected_2025_eur"].sum(),
            "bias_eur": pg_summary["product_group_model_expected_2025_eur"].sum() - pg_summary["actual_group_sales_2025_eur"].sum(),
        },
        {
            "model": "product_group_rows_calibrated",
            "customers": len(pg_summary),
            "actual_sales_2025_eur": pg_summary["actual_group_sales_2025_eur"].sum(),
            "predicted_eur": pg_summary["product_group_calibrated_expected_2025_eur"].sum(),
            "bias_eur": pg_summary["product_group_calibrated_expected_2025_eur"].sum() - pg_summary["actual_group_sales_2025_eur"].sum(),
        },
    ])
    return pd.concat([summary, extra], ignore_index=True)


def append_next_year_summary(summary: pd.DataFrame, next_year_summary: pd.DataFrame) -> pd.DataFrame:
    values = next_year_summary.set_index("metric")["value"]
    actual_2025 = values.get("actual_sales_2025_eur", np.nan)
    forecast = values.get("next_year_forecast_eur", np.nan)
    diff = values.get("next_year_vs_2025_actual_eur", np.nan)
    pct = values.get("next_year_vs_2025_actual_pct", np.nan)
    row = {
        "model": "next_year_recent_weighted_forecast",
        "customers": np.nan,
        "actual_sales_2025_eur": actual_2025,
        "predicted_eur": forecast,
        "bias_eur": diff,
        "mae_eur": np.nan,
        "rmse_eur": np.nan,
        "median_abs_error_eur": np.nan,
        "mape_actual_over_100eur": pct,
        "correlation": np.nan,
        "growth_auc": np.nan,
    }
    return pd.concat([summary, pd.DataFrame([row])], ignore_index=True)


def append_sales_potential_summary(summary: pd.DataFrame, sales_potential_summary: pd.DataFrame) -> pd.DataFrame:
    values = sales_potential_summary.set_index("metric")["value"]
    actual_2025 = values.get("actual_sales_2025_eur", np.nan)
    realistic = values.get("realistic_potential_eur", np.nan)
    diff = values.get("realistic_potential_vs_2025_eur", np.nan)
    pct = values.get("realistic_potential_vs_2025_pct", np.nan)
    row = {
        "model": "sales_potential_case",
        "customers": values.get("customers_with_positive_growth_potential", np.nan),
        "actual_sales_2025_eur": actual_2025,
        "predicted_eur": realistic,
        "bias_eur": diff,
        "mae_eur": np.nan,
        "rmse_eur": np.nan,
        "median_abs_error_eur": np.nan,
        "mape_actual_over_100eur": pct,
        "correlation": np.nan,
        "growth_auc": np.nan,
    }
    return pd.concat([summary, pd.DataFrame([row])], ignore_index=True)


def write_outputs(outputs: dict[str, pd.DataFrame]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    csv_map = {
        "customer_backtest_2025": "backtest_customer_2025.csv",
        "next_year_forecast": "next_year_forecast_recent_weighted.csv",
        "next_year_summary": "next_year_summary_recent_weighted.csv",
        "sales_potential_case": "sales_potential_case.csv",
        "sales_potential_summary": "sales_potential_summary.csv",
        "crm_potential_validation": "crm_potential_validation.csv",
        "crm_unmatched_names": "crm_unmatched_names.csv",
        "crm_validation_summary": "crm_validation_summary.csv",
        "history_features": "history_features_2025.csv",
        "probability_calibration": "probability_calibration_2025.csv",
        "product_group_model": "backtest_product_group_2025.csv",
        "product_group_summary": "product_group_summary_2025.csv",
        "product_group_calibration": "product_group_calibration_2025.csv",
        "recommendations_calibrated": "product_group_recommendations_calibrated.csv",
        "error_analysis": "error_analysis_2025.csv",
        "sales_feedback_template": "sales_feedback_template.csv",
        "feature_importance": "feature_importance_2025.csv",
        "summary": "summary_2025.csv",
    }
    for key, name in csv_map.items():
        outputs[key].to_csv(OUTPUT_DIR / name, index=False, encoding="utf-8-sig")

    try:
        writer_context = pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl")
        output_xlsx = OUTPUT_XLSX
    except PermissionError:
        writer_context = pd.ExcelWriter(FALLBACK_OUTPUT_XLSX, engine="openpyxl")
        output_xlsx = FALLBACK_OUTPUT_XLSX

    with writer_context as writer:
        for sheet, frame in outputs.items():
            excel_frame = frame.copy()
            if len(excel_frame) > 200000:
                excel_frame = excel_frame.head(200000)
            excel_frame.to_excel(writer, sheet_name=sheet[:31], index=False)
        wb = writer.book
        for ws in wb.worksheets:
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for col_cells in ws.columns:
                max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in col_cells[:200])
                ws.column_dimensions[col_cells[0].column_letter].width = min(max(max_len + 2, 10), 42)
    outputs["_written_files"] = pd.DataFrame([{"output_xlsx": str(output_xlsx), "csv_dir": str(OUTPUT_DIR)}])


def main() -> None:
    inputs = read_inputs()
    grouped_sales = map_sales_to_product_groups(inputs["sales"], inputs["grouping"])
    history = build_history_features(inputs["accounts"], inputs["sales"], grouped_sales)
    customer_base = merge_current_model(history, inputs["current"])
    customer_backtest, importance = fit_backtest_models(customer_base)
    next_year_forecast, next_year_summary = build_next_year_forecast(customer_backtest, inputs["sales"])
    calibration = probability_calibration_table(customer_backtest)
    error_analysis = build_error_analysis(customer_backtest)
    feedback = build_sales_feedback_template(error_analysis)
    pg_model = build_product_group_model(grouped_sales, customer_backtest, inputs["recommendations"])
    pg_summary = summarize_product_group_model(pg_model)
    pg_calibration = pg_summary[[
        "lowest_product_group_code",
        "lowest_product_group_name",
        "customers",
        "buyers_2025",
        "buyer_rate_2025",
        "actual_group_sales_2025_eur",
        "product_group_model_expected_2025_eur",
        "product_group_calibrated_expected_2025_eur",
        "raw_calibration_factor",
        "product_group_calibration_factor",
        "calibration_credibility",
        "calibration_method",
        "bias_eur",
        "calibrated_bias_eur",
        "mae_eur",
        "calibrated_mae_eur",
        "absolute_bias_eur",
        "calibrated_absolute_bias_eur",
        "bias_improvement_pct",
        "mae_improvement_pct",
    ]].copy()
    recommendations_calibrated = calibrate_current_recommendations(inputs["recommendations"], pg_calibration)
    sales_potential_case, sales_potential_summary = build_sales_potential_case(next_year_forecast, recommendations_calibrated)
    crm_potential_validation, crm_unmatched_names, crm_validation_summary = build_crm_potential_validation(
        sales_potential_case,
        inputs["crm_potentials"],
        inputs["accounts"],
    )
    summary = append_next_year_summary(build_summary(customer_backtest, pg_summary), next_year_summary)
    summary = append_sales_potential_summary(summary, sales_potential_summary)

    notes = pd.DataFrame([
        {"topic": "Seuraavan vuoden ennuste", "description": "Varsinainen forward-ennuste ei ole sidottu vuoden 2025 toteumaan. Se kayttaa painotettua historiapohjaa, jossa 2025 ja annualisoitu 2026 YTD muodostavat 70 prosenttia historiapainosta."},
        {"topic": "Vuoden 2027 ennuste", "description": "Laskentaa ei muutettu. Forecast_2027_eur, base_forecast_2027_eur, realistic_potential_2027_eur ja upside_potential_2027_eur ovat nykyisen seuraavan vuoden laskennan 2027-nimetyt output-sarakkeet."},
        {"topic": "Myynnillinen potentiaalicase", "description": "Sales_potential_case erottaa konservatiivisen run-rate ennusteen ja aktiivisella myyntityolla tavoiteltavan kasvun. Kasvupotentiaali perustuu kalibroituihin tuoteryhmasuosituksiin, asiakkaan prioriteettiin ja kasvutodennakoisyyteen."},
        {"topic": "CRM-potentials validointi", "description": "CRM-potentials-aineiston Status, Sales ja Probability aggregoidaan asiakasnimella. Jos CRM-osumaa ei loydy, crm_validated_realistic_potential_2027_eur sailyttaa mallin alkuperaisen realistic_potential_2027_eur-arvon."},
        {"topic": "Recent weighted -painotus", "description": "Seuraavan vuoden ennusteen historiapainot ovat 2023 10 %, 2024 20 %, 2025 35 % ja annualisoitu 2026 YTD 35 %. 2026 YTD annualisoidaan 2025 saman kuukausijakson kausiprofiilin perusteella, ei pelkalla 12/kuukaudet-kertoimella."},
        {"topic": "Backtest 2025 toteumaan", "description": "Vertaa nykyisen mallin odotusarvoa ja parannettua ostohistoriafeatureihin perustuvaa mallia vuoden 2025 toteutuneeseen GoSystems-myyntiin."},
        {"topic": "Ostohistoriafeaturet", "description": "Mukana 2023 ja 2024 myynti, 2024 kvartaalit, aktiiviset ostokuukaudet, tilausrivien määrä, ostoryhmien määrä, momentum ja recency."},
        {"topic": "Todennakoisyyden kalibrointi", "description": "Nykyisen mallin probability_of_growth kalibroidaan isotonic-regressiolla 2025 kasvutoteumaan; erillinen history_feature_model arvioi kasvun todennakoisyytta ostohistorian perusteella."},
        {"topic": "Tuoteryhmakohtainen malli", "description": "Historialliset myyntirivit mapataan alimman saatavilla olevan tuoteryhmatason mukaan SKU:lla; puuttuvat SKU-osumat pidetaan myynnin kategoriatasolla, ei tuotetasolla."},
        {"topic": "Tuoteryhmakalibrointi", "description": "Tuoteryhmakohtainen white space -ennuste korjataan 2025 backtestista lasketulla kalibrointikertoimella. Suurilla tuoteryhmilla kaytetaan ryhman omaa kerrointa, pienilla ryhmilla sekoitetaan mukaan globaali toteuma/ennuste-suhde."},
        {"topic": "Virheanalyysi", "description": "Asiakkaat luokitellaan hyvaksi osumaksi, yliarvioksi, aliarvioksi tai keskisuureksi virheeksi. Suurimmat virheet viedaan myynnin palautepohjaan."},
    ])

    outputs = {
        "summary": summary,
        "next_year_forecast": next_year_forecast,
        "next_year_summary": next_year_summary,
        "sales_potential_case": sales_potential_case,
        "sales_potential_summary": sales_potential_summary,
        "crm_potential_validation": crm_potential_validation,
        "crm_unmatched_names": crm_unmatched_names,
        "crm_validation_summary": crm_validation_summary,
        "customer_backtest_2025": customer_backtest,
        "history_features": history,
        "probability_calibration": calibration,
        "product_group_model": pg_model,
        "product_group_summary": pg_summary,
        "product_group_calibration": pg_calibration,
        "recommendations_calibrated": recommendations_calibrated,
        "error_analysis": error_analysis,
        "sales_feedback_template": feedback,
        "feature_importance": importance,
        "model_notes": notes,
    }
    write_outputs(outputs)
    written_xlsx = outputs.get("_written_files", pd.DataFrame([{"output_xlsx": str(OUTPUT_XLSX)}]))["output_xlsx"].iloc[0]
    print(f"Wrote {written_xlsx}")
    print(f"Wrote CSV outputs to {OUTPUT_DIR}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
