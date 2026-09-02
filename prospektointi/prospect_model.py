from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


LOGGER = logging.getLogger(__name__)

ELIGIBLE_TRAINING_STATUSES = {"active", "gokeep+"}
DEFAULT_TOP_N = 1000
DEFAULT_LOOKBACK_DAYS = 365 * 3
MANUAL_EXCLUDED_NAME_TERMS = {"outokumpu"}


def parse_args() -> argparse.Namespace:
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Prospect potential model for top-customer lookalikes.")
    parser.add_argument(
        "--accounts",
        default=str(base_dir / "Account_20.05.2026_combined_with_profinder.xlsx"),
        help="Path to account master Excel file.",
    )
    parser.add_argument(
        "--sales",
        default=str(base_dir / "GoSystems_sales_26_05_2026_summarized.csv"),
        help="Path to sales CSV file.",
    )
    parser.add_argument(
        "--companies",
        default=str(base_dir / "haku_Myyntiin_ai_2026-04-23 (1).xlsx"),
        help="Path to companies / Profinder Excel file.",
    )
    parser.add_argument(
        "--exclude-business-ids-file",
        default=str(base_dir / "Netvisor asiakastiedot 6-2026.xlsx"),
        help="Optional Excel/CSV file whose Y-tunnus values are excluded from prospects.",
    )
    parser.add_argument(
        "--output",
        default=str(base_dir / "prospect_top1000_segment_model.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--top-n-customers",
        type=int,
        default=DEFAULT_TOP_N,
        help="How many best customers define the positive class.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help="How many days of sales history are used for 3-year annual average.",
    )
    parser.add_argument(
        "--min-training-customer-annual-sales-eur",
        type=float,
        default=4000.0,
        help="Minimum annualized sales for customers included in training universe.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for train/test split.",
    )
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


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
    digits = "".join(character for character in text if character.isdigit())
    if len(digits) == 7:
        digits = f"0{digits}"
    if len(digits) >= 8:
        return f"{digits[:-1]}-{digits[-1]}"
    if re.fullmatch(r"\d{7,8}-\d", text):
        return text
    return None


def normalize_column_name(value: str) -> str:
    text = str(value).lower()
    replacements = {
        "ä": "a",
        "ö": "o",
        "å": "a",
        "Ã¤": "a",
        "Ã¶": "o",
        "Ã¥": "a",
        "ÃƒÂ¤": "a",
        "ÃƒÂ¶": "o",
        "ÃƒÂ¥": "a",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def resolve_existing_column(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized_columns = {normalize_column_name(column): column for column in frame.columns}
    for candidate in candidates:
        normalized_candidate = normalize_column_name(candidate)
        if normalized_candidate in normalized_columns:
            return normalized_columns[normalized_candidate]
    return None


def parse_month(value: Any) -> pd.Timestamp | pd.NaT:
    if pd.isna(value):
        return pd.NaT
    return pd.to_datetime(f"{value}-01", errors="coerce")


def normalize_name(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).lower().strip()
    text = re.sub(r"[^a-z0-9åäö]+", " ", text)
    return " ".join(text.split())


def load_data(accounts_path: str, sales_path: str, companies_path: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    LOGGER.info("Loading input files")
    accounts = pd.read_excel(accounts_path)
    sales = pd.read_csv(sales_path)
    companies = pd.read_excel(companies_path)
    LOGGER.info(
        "Loaded raw datasets",
        extra={
            "accounts_rows": len(accounts),
            "sales_rows": len(sales),
            "companies_rows": len(companies),
        },
    )
    return accounts, sales, companies


def load_excluded_business_ids(path: str | None) -> set[str]:
    if not path:
        return set()
    file_path = Path(path)
    if not file_path.exists():
        LOGGER.warning("External exclusion file does not exist: %s", file_path)
        return set()

    if file_path.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        frame = pd.read_excel(file_path, dtype=str)
    else:
        frame = pd.read_csv(file_path, dtype=str)

    business_id_col = resolve_existing_column(frame, ["y tunnus", "business id", "business_id"])
    if not business_id_col:
        raise ValueError(f"No business ID column found in external exclusion file: {file_path}")

    return set(frame[business_id_col].map(normalize_business_id).dropna().astype(str))


def preprocess_accounts(accounts: pd.DataFrame) -> pd.DataFrame:
    frame = accounts.copy()
    frame["business_id"] = frame["Business ID"].map(normalize_business_id)
    parent_business_id_col = resolve_existing_column(frame, ["emoyhtion y tunnus"])
    if parent_business_id_col:
        frame["parent_business_id"] = frame[parent_business_id_col].map(normalize_business_id)
    else:
        frame["parent_business_id"] = None
    frame["account_id"] = pd.to_numeric(frame["ID"], errors="coerce")
    frame["customer_status"] = frame["customer_status"].astype("string").str.strip()
    frame["company_account_name"] = frame["Company Name"].astype("string")
    frame = frame.dropna(subset=["business_id", "account_id"]).copy()
    return frame


def preprocess_sales(sales: pd.DataFrame) -> pd.DataFrame:
    frame = sales.copy()
    frame["account_id"] = pd.to_numeric(frame["account_id"], errors="coerce")
    frame["total_value"] = pd.to_numeric(frame["total_value"], errors="coerce").fillna(0.0)
    frame["created_at"] = frame["created_year_month"].map(parse_month)
    frame = frame.dropna(subset=["account_id", "created_at"]).copy()
    return frame


def build_company_base(companies: pd.DataFrame, accounts: pd.DataFrame) -> pd.DataFrame:
    frame = companies.copy()
    business_id_col = resolve_existing_column(frame, ["y tunnus"])
    frame["business_id"] = frame[business_id_col].map(normalize_business_id)
    frame = frame.dropna(subset=["business_id"]).drop_duplicates(subset=["business_id"]).copy()

    selected_columns = {
        "company_name": resolve_existing_column(frame, ["virallinen nimi"]),
        "marketing_name": resolve_existing_column(frame, ["markkinointinimi"]),
        "parent_business_id": resolve_existing_column(frame, ["emoyhtion y tunnus"]),
        "industry": resolve_existing_column(frame, ["paatoimiala profinder"]),
        "revenue_k_eur": resolve_existing_column(frame, ["liikevaihto tuhatta"]),
        "headcount": resolve_existing_column(frame, ["henkilosto"]),
        "growth_pct": resolve_existing_column(frame, ["liikevaihdon muutos prosenttia"]),
        "revenue_class": resolve_existing_column(frame, ["liikevaihtoluokka"]),
        "headcount_class": resolve_existing_column(frame, ["henkilokuntaluokka"]),
        "location": resolve_existing_column(frame, ["kayntiosoitteen postitoimipaikka"]),
        "municipality": resolve_existing_column(frame, ["kunta"]),
        "region": resolve_existing_column(frame, ["maakunta"]),
    }
    chosen_columns = ["business_id"] + [column for column in selected_columns.values() if column]
    base = frame[chosen_columns].copy()
    base = base.rename(columns={value: key for key, value in selected_columns.items() if value})
    if "parent_business_id" in base.columns:
        base["parent_business_id"] = base["parent_business_id"].map(normalize_business_id)
        base["parent_business_id"] = base["parent_business_id"].fillna(base["business_id"])
    else:
        base["parent_business_id"] = base["business_id"]

    account_summary = (
        accounts.groupby("business_id")
        .agg(
            account_company_name=("company_account_name", "first"),
            account_status=("customer_status", lambda values: ", ".join(sorted(set(values.dropna().astype(str))))),
            account_count=("account_id", "nunique"),
        )
        .reset_index()
    )
    base = base.merge(account_summary, on="business_id", how="left")
    base["company_name"] = base["company_name"].fillna(base["account_company_name"])
    base["revenue_k_eur"] = pd.to_numeric(base["revenue_k_eur"], errors="coerce")
    base["headcount"] = pd.to_numeric(base["headcount"], errors="coerce")
    base["growth_pct"] = pd.to_numeric(base["growth_pct"], errors="coerce")
    base["growth_pct"] = base["growth_pct"].clip(lower=-100, upper=200)
    return base


def compute_customer_targets(
    sales: pd.DataFrame,
    accounts: pd.DataFrame,
    lookback_days: int,
    min_training_customer_annual_sales_eur: float,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    joined = sales.merge(
        accounts[["account_id", "business_id", "customer_status"]],
        on="account_id",
        how="left",
    )
    joined = joined.dropna(subset=["business_id"]).copy()
    joined["customer_status"] = joined["customer_status"].astype("string").str.strip().str.lower()
    joined = joined.loc[joined["customer_status"].isin(ELIGIBLE_TRAINING_STATUSES)].copy()
    if joined.empty:
        raise ValueError("No eligible customer sales found for statuses Active / Gokeep+.")

    reference_date = joined["created_at"].max().normalize()
    window_start = reference_date - pd.Timedelta(days=lookback_days)
    lookback = joined.loc[joined["created_at"] > window_start].copy()

    customer_sales = (
        lookback.groupby("business_id")["total_value"]
        .sum()
        .reset_index(name="sales_3y_total_eur")
    )
    customer_sales["avg_annual_sales_3y_eur"] = customer_sales["sales_3y_total_eur"] / 3.0
    customer_sales = customer_sales.loc[
        customer_sales["avg_annual_sales_3y_eur"] >= float(min_training_customer_annual_sales_eur)
    ].copy()
    customer_sales = customer_sales.sort_values("avg_annual_sales_3y_eur", ascending=False).reset_index(drop=True)
    return customer_sales, reference_date


def revenue_bucket(revenue_k_eur: float | None) -> str:
    if pd.isna(revenue_k_eur):
        return "unknown"
    revenue_eur = float(revenue_k_eur) * 1000.0
    if revenue_eur < 1_000_000:
        return "0-1M"
    if revenue_eur < 5_000_000:
        return "1-5M"
    if revenue_eur < 20_000_000:
        return "5-20M"
    if revenue_eur < 100_000_000:
        return "20-100M"
    return "100M+"


def headcount_bucket(headcount: float | None) -> str:
    if pd.isna(headcount):
        return "unknown"
    count = float(headcount)
    if count < 10:
        return "1-10"
    if count < 50:
        return "10-50"
    if count < 250:
        return "50-250"
    if count < 1000:
        return "250-1000"
    return "1000+"


def revenue_bucket_from_class(revenue_class: Any) -> str | None:
    if pd.isna(revenue_class):
        return None
    text = str(revenue_class).strip().lower()
    if not text:
        return None
    if "20+" in text:
        return "20-100M"
    if "10-20" in text or "10 - 20" in text:
        return "5-20M"
    if "2-10" in text or "2 - 10" in text or "1-2" in text or "1 - 2" in text:
        return "1-5M"
    if "0.4-1" in text or "0,4-1" in text or "0.4 - 1" in text:
        return "0-1M"
    return None


def headcount_bucket_from_class(headcount_class: Any) -> str | None:
    if pd.isna(headcount_class):
        return None
    text = str(headcount_class).strip().lower()
    if not text:
        return None
    if "500-999" in text or "500 - 999" in text or "250-499" in text or "250 - 499" in text:
        return "250-1000"
    if "100-249" in text or "100 - 249" in text or "50-99" in text or "50 - 99" in text:
        return "50-250"
    if "20-49" in text or "20 - 49" in text or "10-19" in text or "10 - 19" in text:
        return "10-50"
    if "1-9" in text or "1 - 9" in text:
        return "1-10"
    if ">999" in text or "1000" in text:
        return "1000+"
    return None


def add_segment_features(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()
    enriched["revenue_bucket"] = enriched["revenue_k_eur"].map(revenue_bucket)
    revenue_bucket_from_label = enriched["revenue_class"].map(revenue_bucket_from_class)
    enriched["revenue_bucket"] = enriched["revenue_bucket"].where(enriched["revenue_bucket"] != "unknown", revenue_bucket_from_label)
    enriched["revenue_bucket"] = enriched["revenue_bucket"].fillna("unknown")
    headcount_bucket_from_label = enriched["headcount_class"].map(headcount_bucket_from_class)
    headcount_bucket_from_numeric = enriched["headcount"].map(headcount_bucket)
    enriched["headcount_bucket"] = headcount_bucket_from_label.fillna(headcount_bucket_from_numeric).fillna("unknown")
    enriched["company_segment"] = enriched["revenue_bucket"].astype(str) + "_" + enriched["headcount_bucket"].astype(str)
    enriched["revenue_per_employee"] = np.where(
        enriched["headcount"].fillna(0) > 0,
        enriched["revenue_k_eur"] * 1000.0 / enriched["headcount"],
        np.nan,
    )
    enriched["growth_bucket"] = pd.cut(
        enriched["growth_pct"],
        bins=[-np.inf, -5, 5, 20, np.inf],
        labels=["decline", "stable", "growth", "high_growth"],
    ).astype("string")
    return enriched


def compute_segment_lift(modeling_df: pd.DataFrame, positive_business_ids: set[str]) -> pd.DataFrame:
    customers = modeling_df.loc[modeling_df["current_customer"] == 1].copy()
    overall_share = customers["company_segment"].value_counts(normalize=True)
    top_customers = customers.loc[customers["business_id"].astype(str).isin(positive_business_ids)].copy()
    top_share = top_customers["company_segment"].value_counts(normalize=True)

    lift_rows = []
    for segment, overall_value in overall_share.items():
        top_value = float(top_share.get(segment, 0.0))
        lift = top_value / float(overall_value) if overall_value else 0.0
        lift_rows.append({"company_segment": segment, "segment_lift": lift})
    lift_df = pd.DataFrame(lift_rows)
    return modeling_df.merge(lift_df, on="company_segment", how="left")


def build_modeling_frame(
    accounts: pd.DataFrame,
    sales: pd.DataFrame,
    companies: pd.DataFrame,
    top_n_customers: int,
    lookback_days: int,
    min_training_customer_annual_sales_eur: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    account_frame = preprocess_accounts(accounts)
    sales_frame = preprocess_sales(sales)
    company_frame = build_company_base(companies, account_frame)
    company_frame = add_segment_features(company_frame)
    company_frame["current_customer"] = company_frame["business_id"].isin(set(account_frame["business_id"].astype(str))).astype(int)

    customer_targets, reference_date = compute_customer_targets(
        sales=sales_frame,
        accounts=account_frame,
        lookback_days=lookback_days,
        min_training_customer_annual_sales_eur=min_training_customer_annual_sales_eur,
    )
    top_customers = customer_targets.head(top_n_customers).copy()
    positive_business_ids = set(top_customers["business_id"].astype(str))

    modeling_df = company_frame.merge(customer_targets, on="business_id", how="left")
    modeling_df["label"] = modeling_df["business_id"].astype(str).isin(positive_business_ids).astype(int)
    modeling_df = compute_segment_lift(modeling_df, positive_business_ids)
    modeling_df["segment_lift"] = modeling_df["segment_lift"].fillna(0.0)
    return modeling_df, top_customers, reference_date


def feature_columns() -> tuple[list[str], list[str]]:
    numeric_features = [
        "revenue_k_eur",
        "headcount",
        "growth_pct",
        "revenue_per_employee",
        "segment_lift",
    ]
    categorical_features = [
        "industry",
        "revenue_bucket",
        "headcount_bucket",
        "company_segment",
        "growth_bucket",
        "municipality",
        "region",
    ]
    return numeric_features, categorical_features


def sanitize_feature_frame(
    frame: pd.DataFrame,
    numeric_features: list[str],
    categorical_features: list[str],
) -> pd.DataFrame:
    clean = frame.copy()
    for column in numeric_features:
        if column in clean.columns:
            clean[column] = pd.to_numeric(clean[column], errors="coerce")
    for column in categorical_features:
        if column in clean.columns:
            clean[column] = clean[column].astype("object")
            clean.loc[clean[column].isna(), column] = np.nan
    return clean


def train_model(
    modeling_df: pd.DataFrame,
    numeric_features: list[str],
    categorical_features: list[str],
    random_state: int,
) -> tuple[Pipeline, dict[str, float]]:
    trainable = modeling_df.loc[modeling_df["current_customer"] == 1].copy()
    feature_cols = numeric_features + categorical_features
    X = sanitize_feature_frame(trainable[feature_cols], numeric_features, categorical_features)
    y = trainable["label"]
    if y.nunique() < 2:
        raise ValueError("Training set does not contain both positive and negative classes.")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=random_state,
        stratify=y,
    )

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
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, numeric_features),
            ("cat", categorical_pipeline, categorical_features),
        ]
    )
    model = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )
    model.fit(X_train, y_train)

    probabilities = model.predict_proba(X_test)[:, 1]
    metrics = {
        "roc_auc": float(roc_auc_score(y_test, probabilities)),
        "average_precision": float(average_precision_score(y_test, probabilities)),
        "train_rows": float(len(X_train)),
        "test_rows": float(len(X_test)),
        "positive_rate": float(y.mean()),
    }
    LOGGER.info("Model metrics %s", metrics)
    return model, metrics


def continuous_baseline_value(revenue_k_eur: Any, headcount: Any, segment_lift_value: Any) -> float:
    revenue_eur = max(float(revenue_k_eur) * 1000.0, 0.0) if pd.notna(revenue_k_eur) else 0.0
    employee_count = max(float(headcount), 1.0) if pd.notna(headcount) else 25.0
    lift = float(segment_lift_value) if pd.notna(segment_lift_value) else 1.0

    revenue_component = max(np.log1p(revenue_eur) - np.log1p(1_000_000.0), 0.0) * 22_000.0
    headcount_component = np.log1p(employee_count) * 6_500.0
    lift_component = min(max(lift, 0.7), 1.8)

    return float((revenue_component + headcount_component) * lift_component)


def build_positive_signals(prospects: pd.DataFrame, top_n: int = 4) -> list[str]:
    reasons: list[str] = []
    for _, row in prospects.iterrows():
        parts: list[str] = []
        lift = float(row.get("segment_lift", 0.0) or 0.0)
        if lift >= 1.20:
            parts.append(f"vahva segmenttiosuma (lift {lift:.2f})")

        revenue_bucket_value = row.get("revenue_bucket")
        if isinstance(revenue_bucket_value, str) and revenue_bucket_value != "unknown":
            parts.append(f"liikevaihtoluokka {revenue_bucket_value}")

        headcount_bucket_value = row.get("headcount_bucket")
        if isinstance(headcount_bucket_value, str) and headcount_bucket_value != "unknown":
            parts.append(f"henkilöstöluokka {headcount_bucket_value}")

        growth_bucket_value = row.get("growth_bucket")
        if pd.notna(growth_bucket_value) and str(growth_bucket_value) in {"growth", "high_growth"}:
            parts.append(f"kasvuluokka {growth_bucket_value}")

        industry_value = row.get("industry")
        if pd.notna(industry_value):
            parts.append(f"toimiala {industry_value}")

        reasons.append(", ".join(parts[:top_n]) if parts else "profiili muistuttaa parhaita asiakkaita")
    return reasons


def score_prospects(
    model: Pipeline,
    modeling_df: pd.DataFrame,
    accounts: pd.DataFrame,
    top_customers: pd.DataFrame,
    excluded_business_ids: set[str] | None = None,
) -> pd.DataFrame:
    numeric_features, categorical_features = feature_columns()
    feature_cols = numeric_features + categorical_features
    scoring = modeling_df.copy()
    scoring_features = sanitize_feature_frame(scoring[feature_cols], numeric_features, categorical_features)
    scoring["score"] = model.predict_proba(scoring_features)[:, 1]

    current_customer_ids = set(accounts["business_id"].dropna().astype(str))
    current_customer_parent_ids = set(accounts["parent_business_id"].dropna().astype(str))
    current_customer_group_ids = current_customer_ids | current_customer_parent_ids
    external_exclusion_ids = excluded_business_ids or set()
    scoring["excluded_current_customer"] = scoring["business_id"].astype(str).isin(current_customer_ids)
    scoring["excluded_external_business_id"] = scoring["business_id"].astype(str).isin(external_exclusion_ids)
    scoring["excluded_customer_parent_company"] = scoring["business_id"].astype(str).isin(current_customer_parent_ids)
    company_names = scoring["company_name"].map(normalize_name)
    marketing_names = scoring["marketing_name"].map(normalize_name) if "marketing_name" in scoring.columns else ""
    scoring["excluded_manual_name_term"] = False
    for term in MANUAL_EXCLUDED_NAME_TERMS:
        normalized_term = normalize_name(term)
        scoring["excluded_manual_name_term"] = (
            scoring["excluded_manual_name_term"]
            | company_names.str.contains(normalized_term, regex=False, na=False)
            | marketing_names.str.contains(normalized_term, regex=False, na=False)
        )
    if "parent_business_id" in scoring.columns:
        scoring["excluded_customer_group"] = scoring["parent_business_id"].astype(str).isin(current_customer_group_ids)
    else:
        scoring["excluded_customer_group"] = False
    prospects = scoring.loc[
        (~scoring["excluded_current_customer"])
        & (~scoring["excluded_external_business_id"])
        & (~scoring["excluded_customer_parent_company"])
        & (~scoring["excluded_customer_group"])
        & (~scoring["excluded_manual_name_term"])
        & scoring["business_id"].notna()
        & scoring["company_name"].notna()
    ].copy()
    prospects.attrs["exclusion_counts"] = {
        "excluded_current_customer_business_id": int(scoring["excluded_current_customer"].sum()),
        "excluded_external_business_id": int(scoring["excluded_external_business_id"].sum()),
        "external_exclusion_business_ids": int(len(external_exclusion_ids)),
        "excluded_current_customer_parent_business_id": int(
            (
                (scoring["excluded_customer_group"] | scoring["excluded_customer_parent_company"])
                & ~scoring["excluded_current_customer"]
            ).sum()
        ),
        "excluded_customer_parent_company_business_id": int(scoring["excluded_customer_parent_company"].sum()),
        "excluded_manual_name_term": int(scoring["excluded_manual_name_term"].sum()),
        "current_customer_parent_business_ids": int(len(current_customer_parent_ids)),
    }
    prospects = prospects.sort_values("score", ascending=False).reset_index(drop=True)

    top_customer_median = float(top_customers["avg_annual_sales_3y_eur"].median()) if not top_customers.empty else 0.0
    top_customer_segments = (
        modeling_df.loc[modeling_df["label"] == 1, ["company_segment", "avg_annual_sales_3y_eur"]]
        .dropna(subset=["company_segment", "avg_annual_sales_3y_eur"])
        .copy()
    )
    segment_medians = top_customer_segments.groupby("company_segment")["avg_annual_sales_3y_eur"].median()
    prospects["segment_median_value_eur"] = prospects["company_segment"].map(segment_medians).fillna(top_customer_median)
    prospects["model_value_eur"] = prospects["score"] * prospects["segment_median_value_eur"]
    prospects["baseline_value_eur"] = prospects.apply(
        lambda row: continuous_baseline_value(row.get("revenue_k_eur"), row.get("headcount"), row.get("segment_lift")),
        axis=1,
    )
    prospects["final_value_eur"] = (0.70 * prospects["model_value_eur"]) + (0.30 * prospects["baseline_value_eur"])
    prospects["ennustettu potentiaali"] = prospects["final_value_eur"].round().astype(int)
    prospects["rank"] = prospects["final_value_eur"].rank(method="first", ascending=False).astype(int)
    prospects = prospects.sort_values(["rank", "score"], ascending=[True, False]).reset_index(drop=True)
    prospects["priority"] = pd.cut(
        prospects["rank"],
        bins=[0, 100, 500, 1000, np.inf],
        labels=["A", "B", "C", "D"],
        include_lowest=True,
    ).astype("string")
    prospects["positive_signals"] = build_positive_signals(prospects)
    prospects["company"] = prospects["company_name"].fillna(prospects["marketing_name"]).fillna(prospects["business_id"])

    return prospects[
        [
            "rank",
            "priority",
            "company",
            "business_id",
            "parent_business_id",
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
        ]
    ]


def main() -> None:
    args = parse_args()
    configure_logging()

    accounts, sales, companies = load_data(args.accounts, args.sales, args.companies)
    modeling_df, top_customers, reference_date = build_modeling_frame(
        accounts=accounts,
        sales=sales,
        companies=companies,
        top_n_customers=args.top_n_customers,
        lookback_days=args.lookback_days,
        min_training_customer_annual_sales_eur=args.min_training_customer_annual_sales_eur,
    )
    numeric_features, categorical_features = feature_columns()
    model, metrics = train_model(
        modeling_df=modeling_df,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        random_state=args.random_state,
    )
    account_frame = preprocess_accounts(accounts)
    excluded_business_ids = load_excluded_business_ids(args.exclude_business_ids_file)
    output = score_prospects(
        model=model,
        modeling_df=modeling_df,
        accounts=account_frame,
        top_customers=top_customers,
        excluded_business_ids=excluded_business_ids,
    )
    metrics.update(output.attrs.get("exclusion_counts", {}))
    output["reference_date"] = reference_date.date().isoformat()

    output_path = Path(args.output)
    output.to_csv(output_path, index=False, encoding="utf-8-sig")
    metrics_path = output_path.with_suffix(".metrics.json")
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    LOGGER.info("Saved output to %s", output_path)
    LOGGER.info("Saved metrics to %s", metrics_path)


if __name__ == "__main__":
    main()
