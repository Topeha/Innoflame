from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


INNOFLAME_DIR = Path(r"C:\Users\TommiHavukainen\OneDrive - Unikie Oy\Customer\Innoflame")
ORIGINAL_MODEL_PATH = INNOFLAME_DIR / "prospektointi" / "prospect_model.py"
DEFAULT_OUTPUT = Path("outputs") / "innoflame_all_accounts_v3" / "prospect_segment_model_all_accounts_v3.csv"


def load_original_model() -> Any:
    spec = importlib.util.spec_from_file_location("innoflame_original_prospect_model", ORIGINAL_MODEL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load original model module from {ORIGINAL_MODEL_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Innoflame prospect potential model while also scoring all account-master customers.",
    )
    parser.add_argument(
        "--accounts",
        default=str(INNOFLAME_DIR / "Account_20.05.2026_combined_with_profinder.xlsx"),
    )
    parser.add_argument(
        "--sales",
        default=str(INNOFLAME_DIR / "GoSystems_sales_26_05_2026_summarized.csv"),
    )
    parser.add_argument(
        "--companies",
        default=str(INNOFLAME_DIR / "haku_Myyntiin_ai_2026-04-23 (1).xlsx"),
    )
    parser.add_argument(
        "--exclude-business-ids-file",
        default=str(INNOFLAME_DIR / "Netvisor asiakastiedot 6-2026.xlsx"),
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--xlsx-output", default="")
    parser.add_argument("--top-n-customers", type=int, default=1000)
    parser.add_argument("--lookback-days", type=int, default=365 * 3)
    parser.add_argument("--min-training-customer-annual-sales-eur", type=float, default=4000.0)
    parser.add_argument(
        "--recent-year-weight",
        type=float,
        default=0.60,
        help="Weight for sales from the most recent 12 months in v3 weighted annual sales.",
    )
    parser.add_argument(
        "--middle-year-weight",
        type=float,
        default=0.30,
        help="Weight for sales from months 13-24 in v3 weighted annual sales.",
    )
    parser.add_argument(
        "--oldest-year-weight",
        type=float,
        default=0.10,
        help="Weight for sales from months 25-36 in v3 weighted annual sales.",
    )
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def first_existing(frame: pd.DataFrame, columns: list[str]) -> str | None:
    for column in columns:
        if column in frame.columns:
            return column
    return None


def prepare_account_company_rows(accounts: pd.DataFrame, model: Any) -> pd.DataFrame:
    rows = accounts.copy()

    business_id_col = first_existing(rows, ["Y-tunnus", "Y-tunnus.1", "Business ID"])
    if business_id_col is None:
        raise ValueError("Account file has no usable business ID column.")

    rows["Y-tunnus"] = rows[business_id_col].where(rows[business_id_col].notna(), rows.get("Business ID"))
    rows["Y-tunnus"] = rows["Y-tunnus"].map(model.normalize_business_id)
    rows = rows.dropna(subset=["Y-tunnus"]).copy()

    company_name_col = first_existing(rows, ["Virallinen nimi", "Virallinen nimi.1", "Company Name", "Account Name"])
    marketing_name_col = first_existing(rows, ["Markkinointinimi", "Markkinointinimi.1", "Account Name"])
    if company_name_col:
        rows["Virallinen nimi"] = rows[company_name_col].where(rows[company_name_col].notna(), rows.get("Company Name"))
    if marketing_name_col:
        rows["Markkinointinimi"] = rows[marketing_name_col]
    if "Virallinen nimi" not in rows.columns:
        rows["Virallinen nimi"] = rows.get("Company Name", rows.get("Account Name", rows["Y-tunnus"]))

    # Ensure non-Profinder account rows still have enough fields for build_company_base.
    profinder_defaults = {
        "Emoyhtiön Y-tunnus": rows["Y-tunnus"],
        "Päätoimiala (Profinder)": np.nan,
        "Liikevaihto (tuhatta €)": np.nan,
        "Henkilöstö": np.nan,
        "Liikevaihdon muutos (prosenttia)": np.nan,
        "Liikevaihtoluokka": np.nan,
        "Henkilökuntaluokka": np.nan,
        "Käyntiosoitteen postitoimipaikka": rows.get("Address city", np.nan),
        "Kunta": rows.get("Address city", np.nan),
        "Maakunta": np.nan,
    }
    for column, value in profinder_defaults.items():
        if column not in rows.columns:
            rows[column] = value
        elif column == "Emoyhtiön Y-tunnus":
            rows[column] = rows[column].where(rows[column].notna(), rows["Y-tunnus"])

    preferred_columns = [
        "Y-tunnus",
        "Virallinen nimi",
        "Markkinointinimi",
        "Emoyhtiön Y-tunnus",
        "Päätoimiala (Profinder)",
        "Liikevaihto (tuhatta €)",
        "Henkilöstö",
        "Liikevaihdon muutos (prosenttia)",
        "Liikevaihtoluokka",
        "Henkilökuntaluokka",
        "Käyntiosoitteen postitoimipaikka",
        "Kunta",
        "Maakunta",
    ]
    return rows[preferred_columns].copy()


def build_scoring_universe(companies: pd.DataFrame, accounts: pd.DataFrame, model: Any) -> pd.DataFrame:
    account_company_rows = prepare_account_company_rows(accounts, model)
    universe = pd.concat([companies.copy(), account_company_rows], ignore_index=True, sort=False)

    business_id_col = model.resolve_existing_column(universe, ["y tunnus"])
    universe["_normalized_business_id"] = universe[business_id_col].map(model.normalize_business_id)
    universe["_has_model_features"] = universe[model.resolve_existing_column(universe, ["liikevaihto tuhatta"])].notna()
    universe["_source_priority"] = np.where(universe.index < len(companies), 0, 1)

    universe = universe.sort_values(
        ["_normalized_business_id", "_has_model_features", "_source_priority"],
        ascending=[True, False, True],
        kind="mergesort",
    )
    universe = universe.drop_duplicates(subset=["_normalized_business_id"], keep="first")
    return universe.drop(columns=["_normalized_business_id", "_has_model_features", "_source_priority"])


def compute_weighted_customer_targets(
    sales: pd.DataFrame,
    accounts: pd.DataFrame,
    lookback_days: int,
    min_training_customer_annual_sales_eur: float,
    *,
    recent_year_weight: float,
    middle_year_weight: float,
    oldest_year_weight: float,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    joined = sales.merge(
        accounts[["account_id", "business_id", "customer_status"]],
        on="account_id",
        how="left",
    )
    joined = joined.dropna(subset=["business_id"]).copy()
    joined["customer_status"] = joined["customer_status"].astype("string").str.strip().str.lower()
    joined = joined.loc[joined["customer_status"].isin(model_eligible_training_statuses())].copy()
    if joined.empty:
        raise ValueError("No eligible customer sales found for statuses Active / Gokeep+.")

    reference_date = joined["created_at"].max().normalize()
    window_start = reference_date - pd.Timedelta(days=lookback_days)
    lookback = joined.loc[joined["created_at"] > window_start].copy()
    lookback["days_from_reference"] = (reference_date - lookback["created_at"]).dt.days
    lookback["sales_year_bucket"] = pd.cut(
        lookback["days_from_reference"],
        bins=[-1, 365, 730, np.inf],
        labels=["recent_12m", "middle_12m", "oldest_12m"],
    ).astype("string")

    annual_sales = (
        lookback.pivot_table(
            index="business_id",
            columns="sales_year_bucket",
            values="total_value",
            aggfunc="sum",
            fill_value=0.0,
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    for column in ["recent_12m", "middle_12m", "oldest_12m"]:
        if column not in annual_sales.columns:
            annual_sales[column] = 0.0

    total_weight = recent_year_weight + middle_year_weight + oldest_year_weight
    if total_weight <= 0:
        raise ValueError("At least one v3 year weight must be positive.")
    recent = recent_year_weight / total_weight
    middle = middle_year_weight / total_weight
    oldest = oldest_year_weight / total_weight

    annual_sales["sales_3y_total_eur"] = annual_sales[["recent_12m", "middle_12m", "oldest_12m"]].sum(axis=1)
    annual_sales["avg_annual_sales_3y_eur_unweighted"] = annual_sales["sales_3y_total_eur"] / 3.0
    annual_sales["avg_annual_sales_3y_eur"] = (
        annual_sales["recent_12m"] * recent
        + annual_sales["middle_12m"] * middle
        + annual_sales["oldest_12m"] * oldest
    )
    annual_sales["recent_year_weight"] = recent
    annual_sales["middle_year_weight"] = middle
    annual_sales["oldest_year_weight"] = oldest
    annual_sales = annual_sales.loc[
        annual_sales["avg_annual_sales_3y_eur"] >= float(min_training_customer_annual_sales_eur)
    ].copy()
    annual_sales = annual_sales.sort_values("avg_annual_sales_3y_eur", ascending=False).reset_index(drop=True)
    return annual_sales, reference_date


def model_eligible_training_statuses() -> set[str]:
    return {"active", "gokeep+"}


def add_exclusion_flags(scoring: pd.DataFrame, account_frame: pd.DataFrame, excluded_business_ids: set[str], model: Any) -> pd.DataFrame:
    out = scoring.copy()
    current_customer_ids = set(account_frame["business_id"].dropna().astype(str))
    current_customer_parent_ids = set(account_frame["parent_business_id"].dropna().astype(str))
    current_customer_group_ids = current_customer_ids | current_customer_parent_ids

    out["is_account_customer"] = out["business_id"].astype(str).isin(current_customer_ids)
    out["excluded_current_customer"] = out["is_account_customer"]
    out["excluded_external_business_id"] = out["business_id"].astype(str).isin(excluded_business_ids)
    out["excluded_customer_parent_company"] = out["business_id"].astype(str).isin(current_customer_parent_ids)
    if "parent_business_id" in out.columns:
        out["excluded_customer_group"] = out["parent_business_id"].astype(str).isin(current_customer_group_ids)
    else:
        out["excluded_customer_group"] = False

    company_names = out["company_name"].map(model.normalize_name)
    marketing_names = out["marketing_name"].map(model.normalize_name) if "marketing_name" in out.columns else ""
    out["excluded_manual_name_term"] = False
    for term in model.MANUAL_EXCLUDED_NAME_TERMS:
        normalized_term = model.normalize_name(term)
        out["excluded_manual_name_term"] = (
            out["excluded_manual_name_term"]
            | company_names.str.contains(normalized_term, regex=False, na=False)
            | marketing_names.str.contains(normalized_term, regex=False, na=False)
        )
    return out


def add_growth_probability_and_expected_value(scoring: pd.DataFrame) -> pd.DataFrame:
    out = scoring.copy()
    score = pd.to_numeric(out.get("score"), errors="coerce").fillna(0.0).clip(0.0, 1.0)
    recent_sales = pd.to_numeric(out.get("recent_12m"), errors="coerce").fillna(0.0).clip(lower=0.0)
    previous_sales = pd.to_numeric(out.get("middle_12m"), errors="coerce").fillna(0.0).clip(lower=0.0)
    segment_lift = pd.to_numeric(out.get("segment_lift"), errors="coerce").fillna(1.0).clip(lower=0.5, upper=2.0)

    momentum_ratio = np.where(previous_sales.gt(0), recent_sales / previous_sales.replace(0, np.nan), np.nan)
    momentum_ratio = pd.Series(momentum_ratio, index=out.index).replace([np.inf, -np.inf], np.nan)
    momentum_signal = np.tanh(np.log(momentum_ratio.fillna(1.0).clip(lower=0.25, upper=4.0)))
    recent_sales_signal = np.where(recent_sales.gt(0), 0.10, -0.05)
    segment_signal = ((segment_lift - 1.0) * 0.08).clip(-0.04, 0.08)

    probability = 0.12 + (0.58 * score) + recent_sales_signal + (0.14 * momentum_signal) + segment_signal
    out["probability_of_growth"] = pd.Series(probability, index=out.index).clip(0.05, 0.90)
    out["sales_momentum_ratio"] = momentum_ratio
    out["conditional_potential_eur"] = pd.to_numeric(out.get("final_value_eur"), errors="coerce").fillna(0.0).clip(lower=0.0)
    out["expected_potential_eur"] = out["probability_of_growth"] * out["conditional_potential_eur"]
    return out


def score_all_accounts(
    trained_model: Any,
    modeling_df: pd.DataFrame,
    account_frame: pd.DataFrame,
    top_customers: pd.DataFrame,
    excluded_business_ids: set[str],
    reference_date: pd.Timestamp,
    model: Any,
    current_customer_recent_sales_weight: float = 0.0,
    recent_sales_floor_multiplier: float = 0.0,
) -> pd.DataFrame:
    numeric_features, categorical_features = model.feature_columns()
    feature_cols = numeric_features + categorical_features
    scoring = modeling_df.copy()
    scoring_features = model.sanitize_feature_frame(scoring[feature_cols], numeric_features, categorical_features)
    scoring["score"] = trained_model.predict_proba(scoring_features)[:, 1]
    scoring = add_exclusion_flags(scoring, account_frame, excluded_business_ids, model)

    top_customer_median = float(top_customers["avg_annual_sales_3y_eur"].median()) if not top_customers.empty else 0.0
    top_customer_segments = (
        modeling_df.loc[modeling_df["label"] == 1, ["company_segment", "avg_annual_sales_3y_eur"]]
        .dropna(subset=["company_segment", "avg_annual_sales_3y_eur"])
        .copy()
    )
    segment_medians = top_customer_segments.groupby("company_segment")["avg_annual_sales_3y_eur"].median()
    scoring["segment_median_value_eur"] = scoring["company_segment"].map(segment_medians).fillna(top_customer_median)
    scoring["model_value_eur"] = scoring["score"] * scoring["segment_median_value_eur"]
    scoring["baseline_value_eur"] = scoring.apply(
        lambda row: model.continuous_baseline_value(row.get("revenue_k_eur"), row.get("headcount"), row.get("segment_lift")),
        axis=1,
    )
    scoring["final_value_eur"] = (0.70 * scoring["model_value_eur"]) + (0.30 * scoring["baseline_value_eur"])
    scoring["pre_sales_adjusted_final_value_eur"] = scoring["final_value_eur"]
    scoring["recent_sales_value_eur"] = pd.to_numeric(scoring.get("recent_12m", 0.0), errors="coerce").fillna(0.0).clip(lower=0.0)
    sales_weight = min(max(float(current_customer_recent_sales_weight), 0.0), 1.0)
    floor_multiplier = max(float(recent_sales_floor_multiplier), 0.0)
    if sales_weight > 0 or floor_multiplier > 0:
        has_recent_sales = scoring["recent_sales_value_eur"].gt(0)
        blended_value = (
            (1.0 - sales_weight) * scoring["final_value_eur"]
            + sales_weight * scoring["recent_sales_value_eur"]
        )
        floor_value = scoring["recent_sales_value_eur"] * floor_multiplier
        adjusted_value = np.maximum.reduce([scoring["final_value_eur"], blended_value, floor_value])
        scoring["final_value_eur"] = np.where(has_recent_sales, adjusted_value, scoring["final_value_eur"])
    scoring["sales_history_adjustment_eur"] = scoring["final_value_eur"] - scoring["pre_sales_adjusted_final_value_eur"]
    scoring = add_growth_probability_and_expected_value(scoring)
    scoring["ennustettu potentiaali"] = np.ceil(scoring["final_value_eur"]).astype(int)
    scoring["rank"] = scoring["final_value_eur"].rank(method="first", ascending=False).astype(int)
    scoring = scoring.sort_values(["rank", "score"], ascending=[True, False]).reset_index(drop=True)
    scoring["priority"] = pd.cut(
        scoring["rank"],
        bins=[0, 100, 500, 1000, np.inf],
        labels=["A", "B", "C", "D"],
        include_lowest=True,
    ).astype("string")
    scoring["positive_signals"] = model.build_positive_signals(scoring)
    scoring["company"] = scoring["company_name"].fillna(scoring["marketing_name"]).fillna(scoring["business_id"])
    scoring["reference_date"] = reference_date.date().isoformat()

    return scoring[
        [
            "rank",
            "priority",
            "company",
            "business_id",
            "parent_business_id",
            "is_account_customer",
            "account_status",
            "account_count",
            "score",
            "segment_median_value_eur",
            "model_value_eur",
            "baseline_value_eur",
            "pre_sales_adjusted_final_value_eur",
            "recent_sales_value_eur",
            "sales_history_adjustment_eur",
            "final_value_eur",
            "probability_of_growth",
            "sales_momentum_ratio",
            "conditional_potential_eur",
            "expected_potential_eur",
            "ennustettu potentiaali",
            "avg_annual_sales_3y_eur",
            "avg_annual_sales_3y_eur_unweighted",
            "recent_12m",
            "middle_12m",
            "oldest_12m",
            "revenue_k_eur",
            "revenue_class",
            "headcount_class",
            "company_segment",
            "segment_lift",
            "industry",
            "growth_bucket",
            "positive_signals",
            "excluded_current_customer",
            "excluded_external_business_id",
            "excluded_customer_parent_company",
            "excluded_customer_group",
            "excluded_manual_name_term",
            "reference_date",
        ]
    ]


def main() -> None:
    args = parse_args()
    model = load_original_model()
    model.configure_logging()

    accounts, sales, companies = model.load_data(args.accounts, args.sales, args.companies)
    scoring_universe = build_scoring_universe(companies, accounts, model)

    def weighted_targets_adapter(
        sales: pd.DataFrame,
        accounts: pd.DataFrame,
        lookback_days: int,
        min_training_customer_annual_sales_eur: float,
    ) -> tuple[pd.DataFrame, pd.Timestamp]:
        return compute_weighted_customer_targets(
            sales=sales,
            accounts=accounts,
            lookback_days=lookback_days,
            min_training_customer_annual_sales_eur=min_training_customer_annual_sales_eur,
            recent_year_weight=args.recent_year_weight,
            middle_year_weight=args.middle_year_weight,
            oldest_year_weight=args.oldest_year_weight,
        )

    # Reuse the current prospect model flow, but replace the customer target with a v3 recency-weighted target.
    model.compute_customer_targets = weighted_targets_adapter
    modeling_df, top_customers, reference_date = model.build_modeling_frame(
        accounts=accounts,
        sales=sales,
        companies=scoring_universe,
        top_n_customers=args.top_n_customers,
        lookback_days=args.lookback_days,
        min_training_customer_annual_sales_eur=args.min_training_customer_annual_sales_eur,
    )

    numeric_features, categorical_features = model.feature_columns()
    trained_model, metrics = model.train_model(
        modeling_df=modeling_df,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        random_state=args.random_state,
    )

    account_frame = model.preprocess_accounts(accounts)
    excluded_business_ids = model.load_excluded_business_ids(args.exclude_business_ids_file)
    output = score_all_accounts(
        trained_model=trained_model,
        modeling_df=modeling_df,
        account_frame=account_frame,
        top_customers=top_customers,
        excluded_business_ids=excluded_business_ids,
        reference_date=reference_date,
        model=model,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False, encoding="utf-8-sig")

    xlsx_output = Path(args.xlsx_output) if args.xlsx_output else output_path.with_suffix(".xlsx")
    output.to_excel(xlsx_output, index=False)

    account_only = output.loc[output["is_account_customer"]].copy()
    account_only_path = output_path.with_name(output_path.stem + "_customers_only.csv")
    account_only_xlsx = output_path.with_name(output_path.stem + "_customers_only.xlsx")
    account_only.to_csv(account_only_path, index=False, encoding="utf-8-sig")
    account_only.to_excel(account_only_xlsx, index=False)

    metrics.update(
        {
            "rows": int(len(output)),
            "account_customer_rows": int(output["is_account_customer"].sum()),
            "non_account_rows": int((~output["is_account_customer"]).sum()),
            "top_customers": int(len(top_customers)),
            "scoring_universe_rows": int(len(scoring_universe)),
            "external_exclusion_business_ids": int(len(excluded_business_ids)),
            "total_potential_eur": int(output["ennustettu potentiaali"].sum()),
            "account_customer_potential_eur": int(output.loc[output["is_account_customer"], "ennustettu potentiaali"].sum()),
            "non_account_potential_eur": int(output.loc[~output["is_account_customer"], "ennustettu potentiaali"].sum()),
            "recent_year_weight": float(args.recent_year_weight),
            "middle_year_weight": float(args.middle_year_weight),
            "oldest_year_weight": float(args.oldest_year_weight),
            "target_method": "v3_recency_weighted_annual_sales",
            "target_formula": "0.60*recent_12m + 0.30*middle_12m + 0.10*oldest_12m by default, normalized if custom weights are used",
            "customers_only_output": str(account_only_path),
            "customers_only_xlsx": str(account_only_xlsx),
        }
    )
    output_path.with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "output": str(output_path),
                "xlsx": str(xlsx_output),
                "customers_only_output": str(account_only_path),
                "customers_only_xlsx": str(account_only_xlsx),
                "metrics": metrics,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
