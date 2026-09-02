from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    mean_absolute_error,
    median_absolute_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from innoflame_all_accounts_model import build_scoring_universe


INNOFLAME_DIR = Path(r"C:\Users\TommiHavukainen\OneDrive - Unikie Oy\Customer\Innoflame")
ORIGINAL_MODEL_PATH = INNOFLAME_DIR / "prospect_model.py"
DEFAULT_OUTPUT = Path("outputs") / "innoflame_two_stage" / "innoflame_two_stage_potential.csv"


def load_original_model() -> Any:
    spec = importlib.util.spec_from_file_location("innoflame_original_prospect_model", ORIGINAL_MODEL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load original model module from {ORIGINAL_MODEL_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Two-stage Innoflame model: purchase probability + buyer potential.")
    parser.add_argument("--accounts", default=str(INNOFLAME_DIR / "Account_20.05.2026_combined_with_profinder.xlsx"))
    parser.add_argument("--sales", default=str(INNOFLAME_DIR / "GoSystems_sales_26_05_2026_summarized.csv"))
    parser.add_argument("--companies", default=str(INNOFLAME_DIR / "haku_Myyntiin_ai_2026-04-23 (1).xlsx"))
    parser.add_argument("--lookback-days", type=int, default=365 * 3)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--xlsx-output", default="")
    return parser.parse_args()


def build_sales_targets(
    accounts: pd.DataFrame,
    sales: pd.DataFrame,
    model: Any,
    *,
    lookback_days: int,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    account_frame = model.preprocess_accounts(accounts)
    sales_frame = model.preprocess_sales(sales)
    joined = sales_frame.merge(
        account_frame[["account_id", "business_id", "customer_status"]],
        on="account_id",
        how="left",
    )
    joined = joined.dropna(subset=["business_id"]).copy()
    reference_date = joined["created_at"].max().normalize()
    window_start = reference_date - pd.Timedelta(days=lookback_days)
    lookback = joined.loc[joined["created_at"] > window_start].copy()

    customer_sales = (
        lookback.groupby("business_id", as_index=False)["total_value"]
        .sum()
        .rename(columns={"total_value": "sales_3y_total_eur"})
    )
    customer_sales["avg_annual_sales_3y_eur"] = customer_sales["sales_3y_total_eur"] / 3.0
    customer_sales = customer_sales.loc[customer_sales["avg_annual_sales_3y_eur"] > 0].copy()
    return customer_sales, reference_date


def add_sales_labels(modeling_df: pd.DataFrame, sales_targets: pd.DataFrame) -> pd.DataFrame:
    labeled = modeling_df.merge(sales_targets, on="business_id", how="left", suffixes=("", "_sales_target"))
    if "avg_annual_sales_3y_eur_sales_target" in labeled.columns:
        labeled["actual_avg_annual_sales_3y_eur"] = labeled["avg_annual_sales_3y_eur_sales_target"]
    elif "avg_annual_sales_3y_eur" in sales_targets.columns and "avg_annual_sales_3y_eur" in labeled.columns:
        labeled["actual_avg_annual_sales_3y_eur"] = labeled["avg_annual_sales_3y_eur"]
    else:
        labeled["actual_avg_annual_sales_3y_eur"] = np.nan
    labeled["has_sales_history"] = labeled["actual_avg_annual_sales_3y_eur"].fillna(0).gt(0).astype(int)
    return labeled


def make_preprocessor(numeric_features: list[str], categorical_features: list[str]) -> ColumnTransformer:
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value="unknown")),
            ("encoder", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, numeric_features),
            ("cat", categorical_pipeline, categorical_features),
        ]
    )


def train_purchase_model(
    trainable: pd.DataFrame,
    numeric_features: list[str],
    categorical_features: list[str],
    model: Any,
    *,
    random_state: int,
) -> tuple[Pipeline, dict[str, float]]:
    feature_cols = numeric_features + categorical_features
    X = model.sanitize_feature_frame(trainable[feature_cols], numeric_features, categorical_features)
    y = trainable["has_sales_history"]
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=random_state,
        stratify=y,
    )
    pipeline = Pipeline(
        steps=[
            ("preprocessor", make_preprocessor(numeric_features, categorical_features)),
            ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )
    pipeline.fit(X_train, y_train)
    probabilities = pipeline.predict_proba(X_test)[:, 1]
    metrics = {
        "purchase_train_rows": float(len(X_train)),
        "purchase_test_rows": float(len(X_test)),
        "purchase_positive_rate": float(y.mean()),
        "purchase_roc_auc": float(roc_auc_score(y_test, probabilities)),
        "purchase_average_precision": float(average_precision_score(y_test, probabilities)),
    }
    return pipeline, metrics


def train_buyer_potential_model(
    trainable: pd.DataFrame,
    numeric_features: list[str],
    categorical_features: list[str],
    model: Any,
    *,
    random_state: int,
) -> tuple[Pipeline, dict[str, float]]:
    buyers = trainable.loc[trainable["has_sales_history"] == 1].copy()
    feature_cols = numeric_features + categorical_features
    X = model.sanitize_feature_frame(buyers[feature_cols], numeric_features, categorical_features)
    y_log = np.log1p(buyers["actual_avg_annual_sales_3y_eur"].astype(float))
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y_log,
        test_size=0.2,
        random_state=random_state,
    )
    pipeline = Pipeline(
        steps=[
            ("preprocessor", make_preprocessor(numeric_features, categorical_features)),
            (
                "regressor",
                RandomForestRegressor(
                    n_estimators=300,
                    min_samples_leaf=5,
                    random_state=random_state,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    pipeline.fit(X_train, y_train)
    pred_log = pipeline.predict(X_test)
    y_actual = np.expm1(y_test)
    pred_actual = np.expm1(pred_log)
    metrics = {
        "buyer_potential_train_rows": float(len(X_train)),
        "buyer_potential_test_rows": float(len(X_test)),
        "buyer_potential_mae_eur": float(mean_absolute_error(y_actual, pred_actual)),
        "buyer_potential_median_ae_eur": float(median_absolute_error(y_actual, pred_actual)),
        "buyer_potential_r2_log": float(r2_score(y_test, pred_log)),
        "buyer_potential_target_median_eur": float(buyers["actual_avg_annual_sales_3y_eur"].median()),
        "buyer_potential_target_mean_eur": float(buyers["actual_avg_annual_sales_3y_eur"].mean()),
        "buyer_potential_target_max_eur": float(buyers["actual_avg_annual_sales_3y_eur"].max()),
    }
    return pipeline, metrics


def rank_priority(rank: pd.Series) -> pd.Series:
    return pd.cut(
        rank,
        bins=[0, 100, 500, 1000, np.inf],
        labels=["A", "B", "C", "D"],
        include_lowest=True,
    ).astype("string")


def main() -> None:
    args = parse_args()
    model = load_original_model()
    model.configure_logging()

    accounts, sales, companies = model.load_data(args.accounts, args.sales, args.companies)
    scoring_universe = build_scoring_universe(companies, accounts, model)

    # Build the same feature frame as the old model, but do not collapse target customers into top-vs-rest potential.
    modeling_df, _, reference_date = model.build_modeling_frame(
        accounts=accounts,
        sales=sales,
        companies=scoring_universe,
        top_n_customers=1000,
        lookback_days=args.lookback_days,
        min_training_customer_annual_sales_eur=0.0,
    )
    sales_targets, sales_reference_date = build_sales_targets(
        accounts=accounts,
        sales=sales,
        model=model,
        lookback_days=args.lookback_days,
    )
    reference_date = max(reference_date, sales_reference_date)
    modeling_df = add_sales_labels(modeling_df, sales_targets)

    numeric_features, categorical_features = model.feature_columns()
    trainable = modeling_df.loc[modeling_df["current_customer"] == 1].copy()
    purchase_model, purchase_metrics = train_purchase_model(
        trainable,
        numeric_features,
        categorical_features,
        model,
        random_state=args.random_state,
    )
    buyer_potential_model, potential_metrics = train_buyer_potential_model(
        trainable,
        numeric_features,
        categorical_features,
        model,
        random_state=args.random_state,
    )

    feature_cols = numeric_features + categorical_features
    scoring_features = model.sanitize_feature_frame(modeling_df[feature_cols], numeric_features, categorical_features)
    output = modeling_df.copy()
    output["purchase_probability"] = purchase_model.predict_proba(scoring_features)[:, 1]
    output["predicted_buyer_potential_eur"] = np.expm1(buyer_potential_model.predict(scoring_features))
    output["expected_potential_eur"] = output["purchase_probability"] * output["predicted_buyer_potential_eur"]
    output["ennustettu potentiaali"] = output["expected_potential_eur"].round().clip(lower=0).astype(int)
    output["rank"] = output["expected_potential_eur"].rank(method="first", ascending=False).astype(int)
    output = output.sort_values(["rank", "purchase_probability"], ascending=[True, False]).reset_index(drop=True)
    output["priority"] = rank_priority(output["rank"])
    output["company"] = output["company_name"].fillna(output["marketing_name"]).fillna(output["business_id"])
    output["reference_date"] = reference_date.date().isoformat()

    output_columns = [
        "rank",
        "priority",
        "company",
        "business_id",
        "parent_business_id",
        "current_customer",
        "has_sales_history",
        "actual_avg_annual_sales_3y_eur",
        "purchase_probability",
        "predicted_buyer_potential_eur",
        "expected_potential_eur",
        "ennustettu potentiaali",
        "revenue_k_eur",
        "revenue_class",
        "headcount_class",
        "company_segment",
        "segment_lift",
        "industry",
        "growth_bucket",
        "account_status",
        "account_count",
        "reference_date",
    ]
    output = output[output_columns]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False, encoding="utf-8-sig")
    xlsx_path = Path(args.xlsx_output) if args.xlsx_output else output_path.with_suffix(".xlsx")
    output.to_excel(xlsx_path, index=False)

    customer_only = output.loc[output["current_customer"] == 1].copy()
    customer_csv = output_path.with_name(output_path.stem + "_customers_only.csv")
    customer_xlsx = output_path.with_name(output_path.stem + "_customers_only.xlsx")
    customer_only.to_csv(customer_csv, index=False, encoding="utf-8-sig")
    customer_only.to_excel(customer_xlsx, index=False)

    metrics = {
        **purchase_metrics,
        **potential_metrics,
        "rows": int(len(output)),
        "customer_rows": int((output["current_customer"] == 1).sum()),
        "customers_with_sales_history": int((trainable["has_sales_history"] == 1).sum()),
        "customers_without_sales_history": int((trainable["has_sales_history"] == 0).sum()),
        "total_expected_potential_eur": int(output["ennustettu potentiaali"].sum()),
        "customer_expected_potential_eur": int(customer_only["ennustettu potentiaali"].sum()),
        "reference_date": reference_date.date().isoformat(),
        "output": str(output_path),
        "xlsx": str(xlsx_path),
        "customers_only_output": str(customer_csv),
        "customers_only_xlsx": str(customer_xlsx),
    }
    output_path.with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
