from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


INNOFLAME_DIR = Path(r"C:\Users\TommiHavukainen\OneDrive - Unikie Oy\Customer\Innoflame")
ORIGINAL_MODEL_PATH = INNOFLAME_DIR / "prospect_model.py"
DEFAULT_OUTPUT = Path("outputs") / "innoflame_all_accounts" / "prospect_segment_model_all_accounts.csv"


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


def score_all_accounts(
    trained_model: Any,
    modeling_df: pd.DataFrame,
    account_frame: pd.DataFrame,
    top_customers: pd.DataFrame,
    excluded_business_ids: set[str],
    reference_date: pd.Timestamp,
    model: Any,
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
    scoring["ennustettu potentiaali"] = scoring["final_value_eur"].round().astype(int)
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
            "ennustettu potentiaali",
            "avg_annual_sales_3y_eur",
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
