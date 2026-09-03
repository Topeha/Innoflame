"""Run the current-customer potential model with the 2026 source files.

This adapter keeps the calculation model unchanged while normalizing the new
product-level sales CSV and the new Finnish product master for it in memory.
Only this potentiaali folder is changed by this integration.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
POTENTIAL_DIR = Path(__file__).resolve().parent
SALES_PATH = ROOT / "GoSystems_sales_26_05_2026_summarized.csv"
PROFINDER_PATH = POTENTIAL_DIR / "haku_Prospektointimasterlista_2026-08-12.xlsx"
PRODUCT_MASTER_PATH = POTENTIAL_DIR / "INNOFLAME-TUOTELISTA-TUOTERYHMITTELY.xlsx"
ACCOUNTS_PATH = POTENTIAL_DIR / "Account_20.05.2026_combined_with_profinder.xlsx"
CRM_PATH = POTENTIAL_DIR / "CRM_potentials_03.06.2026_03.07.2026 (1).xlsx"
EXCLUSION_PATH = POTENTIAL_DIR / "Netvisor asiakastiedot 6-2026.xlsx"
MODEL_PATH = ROOT / "prospektointi" / "prospect_model.py"
V3_PATH = ROOT / "two_stage_potential_model" / "v3_recent_weighted_current_model" / "innoflame_all_accounts_model_v3.py"
RUNNER_PATH = ROOT / "prospektointi" / "run_current_customer_potential.py"

EXCLUDED_PRODUCT_TERMS = (
    "kustannus", "cost", "freight", "delivery", "transport", "shipping",
    "pakkauskustannus", "kuljetus", "kuljetuspakkaus", "kuljetuslaatikko",
    "kuljetusalusta", "lava", "rahti", "toimitusmaksu", "käsittelymaksu",
)


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
    if "productcode" in frame.columns and "sku" not in frame.columns:
        frame["sku"] = frame["productcode"]
    included = frame.loc[
        frame["status_clean"].str.casefold().eq("invoiced")
        & frame["account_id"].notna()
        & frame["created_at_dt"].notna()
    ].copy()
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
    sales_frame = sales_frame.loc[sales_frame["business_id"].notna() & sales_frame["product_code"].ne("")].copy()

    sold_product_stats = sales_frame.groupby(["product_code", "product_name", "product_group"], as_index=False).agg(
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
    group_stats = sales_frame.groupby(["business_id", "product_group"], as_index=False)["sales_eur"].sum()
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
    grouping, master_quality = prepare_product_grouping(PRODUCT_MASTER_PATH)
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
    product_quality = pd.concat([master_quality, product_quality, pd.DataFrame([
        {"metric": "source_sales_rows", "value": len(raw_sales)},
        {"metric": "included_invoiced_sales_rows", "value": len(sales)},
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
