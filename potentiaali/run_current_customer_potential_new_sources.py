"""Run the current-customer potential model with the 2026 source files.

This adapter keeps the calculation model unchanged while normalizing the new
product-level sales CSV and the new Finnish product master for it in memory.
Only this potentiaali folder is changed by this integration.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
POTENTIAL_DIR = Path(__file__).resolve().parent
SALES_PATH = ROOT / "GoSystems_sales_26_05_2026_combined.csv"
PROFINDER_PATH = ROOT / "haku_Prospektointimasterlista_2026-08-12.xlsx"
PRODUCT_MASTER_PATH = Path(r"C:\Users\TommiHavukainen\Downloads\INNOFLAME-TUOTELISTA-TUOTERYHMITTELY.xlsx")
ACCOUNTS_PATH = ROOT / "Account_20.05.2026_combined_with_profinder.xlsx"
CRM_PATH = POTENTIAL_DIR / "CRM_potentials_03.06.2026_03.07.2026 (1).xlsx"
EXCLUSION_PATH = ROOT / "Netvisor asiakastiedot 6-2026.xlsx"
MODEL_PATH = ROOT / "prospektointi" / "prospect_model.py"
V3_PATH = ROOT / "two_stage_potential_model" / "v3_recent_weighted_current_model" / "innoflame_all_accounts_model_v3.py"
RUNNER_PATH = ROOT / "prospektointi" / "run_current_customer_potential.py"


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
    raw = pd.read_csv(path, low_memory=False)
    required = {"account_id", "status", "price", "amount", "created_at"}
    missing = sorted(required - set(raw.columns))
    if missing:
        raise ValueError(f"Sales CSV is missing required columns: {missing}")

    frame = raw.copy()
    frame["account_id"] = pd.to_numeric(frame["account_id"], errors="coerce")
    frame["price_num"] = number(frame["price"]).fillna(0.0)
    frame["amount_num"] = number(frame["amount"]).fillna(0.0)
    frame["total_value"] = frame["price_num"] * frame["amount_num"]
    frame["created_at_dt"] = pd.to_datetime(frame["created_at"], errors="coerce", utc=True).dt.tz_convert(None)
    frame["created_year_month"] = frame["created_at_dt"].dt.to_period("M").astype("string")
    frame["status_clean"] = frame["status"].astype("string").str.strip()
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
    recommendations, product_quality = runner.build_product_group_recommendations(
        customer_potential,
        inputs["sales"],
        inputs["accounts"],
        product_grouping,
        max_recommendations_per_customer=args.max_recommendations_per_customer,
    )
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
    ])], ignore_index=True)
    run_log = runner.build_run_log(inputs["crm"], customer_potential, validation, missing_features, product_quality, artifacts)
    data_quality = runner.build_data_quality(crm_features, customer_potential, product_quality)
    runner.write_outputs(customer_potential, recommendations, validation, run_log, data_quality, args)
    print(json.dumps({
        "output_xlsx": args.output_xlsx,
        "customer_rows": len(customer_potential),
        "recommendation_rows": len(recommendations),
        "source_sales_rows": len(raw_sales),
        "included_invoiced_sales_rows": len(sales),
    }, indent=2))


if __name__ == "__main__":
    main()
