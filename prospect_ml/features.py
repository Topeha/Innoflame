from __future__ import annotations

import logging

import pandas as pd

from prospect_ml.config import AppConfig


LOGGER = logging.getLogger(__name__)


def prepare_company_features(companies: pd.DataFrame, config: AppConfig) -> pd.DataFrame:
    columns = config.columns
    feature_columns = config.features.company_feature_columns
    selected_columns = [columns.business_id] + feature_columns
    prepared = companies.loc[:, [column for column in selected_columns if column in companies.columns]].copy()
    prepared = prepared.drop_duplicates(subset=[columns.business_id]).reset_index(drop=True)

    for numeric_column in config.features.numeric_company:
        if numeric_column in prepared.columns:
            prepared[numeric_column] = pd.to_numeric(prepared[numeric_column], errors="coerce")

    for categorical_column in config.features.categorical_company:
        if categorical_column in prepared.columns:
            prepared[categorical_column] = prepared[categorical_column].astype("string")

    for extra_column in config.features.extra_company:
        if extra_column in prepared.columns and prepared[extra_column].dtype == "object":
            prepared[extra_column] = prepared[extra_column].astype("string")

    return prepared


def prepare_sales_history(sales: pd.DataFrame, config: AppConfig) -> pd.DataFrame:
    columns = config.columns
    prepared = sales.copy()
    prepared[columns.order_date] = pd.to_datetime(prepared[columns.order_date], errors="coerce")
    prepared = prepared.loc[prepared[columns.order_date].notna()].copy()

    prepared = apply_prospect_sales_quality_rules(prepared, config)
    prepared = resolve_sales_value_column(prepared, config)
    prepared = resolve_product_fallback_key(prepared, config)
    prepared = add_product_group_match_confidence(prepared, config)

    for numeric_column in [columns.net_sales, columns.margin]:
        if numeric_column in prepared.columns:
            prepared[numeric_column] = pd.to_numeric(prepared[numeric_column], errors="coerce")

    if columns.product in prepared.columns:
        prepared[columns.product] = prepared[columns.product].astype("string")

    if columns.customer_status in prepared.columns:
        prepared[columns.customer_status] = prepared[columns.customer_status].astype("string").str.strip()

    return prepared


def apply_prospect_sales_quality_rules(sales: pd.DataFrame, config: AppConfig) -> pd.DataFrame:
    """Apply the agreed prospect-model source filters when matching columns exist."""
    columns = config.columns
    prepared = sales.copy()

    if columns.sales_status in prepared.columns and config.training.invoice_statuses:
        invoice_statuses = {str(status).strip().casefold() for status in config.training.invoice_statuses}
        prepared = prepared.loc[
            prepared[columns.sales_status].astype("string").str.strip().str.casefold().isin(invoice_statuses)
        ].copy()

    if columns.product_group_l3_code in prepared.columns and config.training.excluded_product_group_l3_codes:
        excluded = {str(code).strip() for code in config.training.excluded_product_group_l3_codes}
        prepared = prepared.loc[
            ~prepared[columns.product_group_l3_code].astype("string").str.strip().isin(excluded)
        ].copy()

    return prepared


def resolve_sales_value_column(sales: pd.DataFrame, config: AppConfig) -> pd.DataFrame:
    columns = config.columns
    prepared = sales.copy()

    candidate_columns = [columns.net_sales] + list(columns.net_sales_fallbacks)
    existing_candidates = [column for column in candidate_columns if column in prepared.columns]
    if not existing_candidates:
        return prepared

    source_column = existing_candidates[0]
    prepared[columns.net_sales] = pd.to_numeric(
        prepared[source_column].astype("string").str.replace(",", ".", regex=False),
        errors="coerce",
    )
    prepared["sales_value_source_column"] = source_column
    return prepared


def resolve_product_fallback_key(sales: pd.DataFrame, config: AppConfig) -> pd.DataFrame:
    columns = config.columns
    prepared = sales.copy()

    product_key = pd.Series(pd.NA, index=prepared.index, dtype="string")
    product_source = pd.Series(pd.NA, index=prepared.index, dtype="string")

    fallback_steps = [
        ("productcode", columns.productcode),
        ("name_category", columns.name),
        ("reference_category", columns.reference),
    ]

    for source_name, source_column in fallback_steps:
        if source_column not in prepared.columns:
            continue
        values = prepared[source_column].astype("string").str.strip()
        has_value = values.notna() & values.ne("")
        needs_value = product_key.isna() | product_key.str.strip().fillna("").eq("")
        mask = needs_value & has_value

        if source_name in {"name_category", "reference_category"} and columns.category in prepared.columns:
            category = prepared[columns.category].astype("string").str.strip().fillna("")
            product_key.loc[mask] = source_name + ":" + values.loc[mask] + "|category:" + category.loc[mask]
        else:
            product_key.loc[mask] = source_name + ":" + values.loc[mask]
        product_source.loc[mask] = source_name

    if product_key.notna().any():
        prepared[columns.product] = product_key
        prepared["product_fallback_source"] = product_source

    return prepared


def add_product_group_match_confidence(sales: pd.DataFrame, config: AppConfig) -> pd.DataFrame:
    columns = config.columns
    prepared = sales.copy()
    method_column = columns.product_group_match_method
    if method_column not in prepared.columns:
        return prepared

    method = prepared[method_column].astype("string").str.strip()
    confidence = pd.Series(0.6, index=prepared.index, dtype="float")
    confidence.loc[method.eq("sku")] = 1.0
    confidence.loc[method.str.contains("productcode", case=False, na=False)] = 0.95
    confidence.loc[method.str.contains("name_category|same_name|name_unique", case=False, regex=True, na=False)] = 0.85
    confidence.loc[method.str.contains("reference", case=False, na=False)] = 0.8
    confidence.loc[method.str.contains("source_zip", case=False, na=False)] = 0.8
    confidence.loc[method.str.contains("manual_", case=False, na=False)] = 0.75
    confidence.loc[method.str.contains("category_guided", case=False, na=False)] = 0.7
    confidence.loc[method.eq("") | method.isna()] = 0.0
    prepared["product_group_match_confidence"] = confidence
    return prepared


def enrich_sales_with_account_status(
    sales: pd.DataFrame,
    accounts: pd.DataFrame | None,
    config: AppConfig,
) -> pd.DataFrame:
    if accounts is None:
        return sales

    sales_frame = sales.copy()
    account_business_id_column = config.columns.account_business_id
    if account_business_id_column not in accounts.columns:
        raise ValueError(
            f"Accounts source is missing required join column: {account_business_id_column}"
        )

    account_status_column = config.columns.account_status
    account_frame = accounts.copy()
    account_frame[account_business_id_column] = account_frame[account_business_id_column].astype(str).str.strip()

    if account_status_column not in account_frame.columns:
        account_frame[account_status_column] = config.training.default_account_status

    account_frame[account_status_column] = account_frame[account_status_column].astype("string").str.strip()
    account_frame = account_frame[[account_business_id_column, account_status_column]].drop_duplicates(subset=[account_business_id_column])

    sales_frame[config.columns.business_id] = sales_frame[config.columns.business_id].astype(str).str.strip()
    sales_frame = sales_frame.drop(columns=[config.columns.customer_status], errors="ignore")
    merged = sales_frame.merge(
        account_frame,
        left_on=config.columns.business_id,
        right_on=account_business_id_column,
        how="left",
    )
    merged[config.columns.customer_status] = merged[account_status_column]
    merged = merged.drop(columns=[column for column in [account_business_id_column, account_status_column] if column in merged.columns and column != config.columns.customer_status])
    return merged


def enrich_sales_with_fixed_account_status(
    sales: pd.DataFrame,
    accounts: pd.DataFrame | None,
    fixed_status: str,
    config: AppConfig,
) -> pd.DataFrame:
    if accounts is None:
        return sales

    account_business_id_column = config.columns.account_business_id
    if account_business_id_column not in accounts.columns:
        raise ValueError(
            f"Accounts source is missing required join column: {account_business_id_column}"
        )

    sales_frame = sales.copy()
    sales_frame[config.columns.business_id] = sales_frame[config.columns.business_id].astype(str).str.strip()

    account_ids = (
        accounts[account_business_id_column]
        .dropna()
        .astype(str)
        .str.strip()
        .drop_duplicates()
    )
    mask = sales_frame[config.columns.business_id].isin(set(account_ids.tolist()))
    if config.columns.customer_status not in sales_frame.columns:
        sales_frame[config.columns.customer_status] = pd.NA
    sales_frame.loc[mask, config.columns.customer_status] = fixed_status
    return sales_frame


def build_training_dataset(
    companies: pd.DataFrame,
    sales: pd.DataFrame,
    config: AppConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    columns = config.columns
    prepared_companies = prepare_company_features(companies, config)
    eligible_sales = filter_eligible_training_sales(sales, config)
    snapshot_dates = generate_snapshot_dates(eligible_sales, config)
    LOGGER.info("Creating training snapshots", extra={"snapshot_count": len(snapshot_dates)})

    snapshot_frames: list[pd.DataFrame] = []
    for snapshot_date in snapshot_dates:
        positives = _positive_business_ids_for_snapshot(eligible_sales, columns.business_id, columns.order_date, snapshot_date, config.training.lookback_days)
        snapshot_frame = prepared_companies.copy()
        snapshot_frame["snapshot_date"] = snapshot_date
        snapshot_frame["snapshot_month"] = snapshot_date.month
        snapshot_frame["snapshot_quarter"] = snapshot_date.quarter
        snapshot_frame["label"] = snapshot_frame[columns.business_id].isin(positives).astype(int)
        snapshot_frames.append(snapshot_frame)

    dataset = pd.concat(snapshot_frames, ignore_index=True)
    train_df, test_df = split_time_aware(dataset, config.training.test_fraction)
    return prepared_companies, train_df, test_df


def build_scoring_dataset(companies: pd.DataFrame, config: AppConfig) -> pd.DataFrame:
    scoring_date = resolve_as_of_date(config)
    prepared = prepare_company_features(companies, config)
    prepared["snapshot_date"] = scoring_date
    prepared["snapshot_month"] = scoring_date.month
    prepared["snapshot_quarter"] = scoring_date.quarter
    return prepared


def current_customers(sales: pd.DataFrame, config: AppConfig) -> set[str]:
    sales = prepare_sales_history(sales, config)
    business_ids = sales[config.columns.business_id].dropna().astype(str).unique().tolist()
    return set(business_ids)


def build_sales_quality_metrics(sales: pd.DataFrame, config: AppConfig) -> dict[str, object]:
    columns = config.columns
    frame = sales.copy()
    metrics: dict[str, object] = {
        "source_sales_rows": int(len(frame)),
    }

    candidate_columns = [columns.net_sales] + list(columns.net_sales_fallbacks)
    sales_source_column = next((column for column in candidate_columns if column in frame.columns), None)
    if sales_source_column:
        sales_values = pd.to_numeric(
            frame[sales_source_column].astype("string").str.replace(",", ".", regex=False),
            errors="coerce",
        ).fillna(0.0)
        metrics["sales_value_source_column"] = sales_source_column
        metrics["source_sales_eur"] = round(float(sales_values.sum()), 2)
    else:
        sales_values = pd.Series(0.0, index=frame.index)
        metrics["sales_value_source_column"] = None
        metrics["source_sales_eur"] = 0.0

    if columns.sales_status in frame.columns:
        invoice_statuses = {str(status).strip().casefold() for status in config.training.invoice_statuses}
        invoiced = frame[columns.sales_status].astype("string").str.strip().str.casefold().isin(invoice_statuses)
        metrics["invoiced_sales_rows"] = int(invoiced.sum())
        metrics["invoiced_sales_eur"] = round(float(sales_values.loc[invoiced].sum()), 2)
    else:
        invoiced = pd.Series(True, index=frame.index)
        metrics["invoiced_sales_rows"] = int(len(frame))
        metrics["invoiced_sales_eur"] = round(float(sales_values.sum()), 2)

    if columns.product_group_l3_code in frame.columns:
        product_group = frame[columns.product_group_l3_code].astype("string").str.strip()
        missing_group = product_group.isna() | product_group.eq("")
        excluded_codes = {str(code).strip() for code in config.training.excluded_product_group_l3_codes}
        excluded_group = product_group.isin(excluded_codes)
        metrics["missing_product_group_rows"] = int(missing_group.sum())
        metrics["missing_product_group_sales_eur"] = round(float(sales_values.loc[missing_group].sum()), 2)
        metrics["invoiced_missing_product_group_rows"] = int((invoiced & missing_group).sum())
        metrics["invoiced_missing_product_group_sales_eur"] = round(float(sales_values.loc[invoiced & missing_group].sum()), 2)
        metrics["excluded_product_group_rows"] = int((invoiced & excluded_group).sum())
        metrics["excluded_product_group_sales_eur"] = round(float(sales_values.loc[invoiced & excluded_group].sum()), 2)
    else:
        metrics["missing_product_group_rows"] = 0
        metrics["missing_product_group_sales_eur"] = 0.0
        metrics["invoiced_missing_product_group_rows"] = 0
        metrics["invoiced_missing_product_group_sales_eur"] = 0.0
        metrics["excluded_product_group_rows"] = 0
        metrics["excluded_product_group_sales_eur"] = 0.0

    prepared = prepare_sales_history(frame, config)
    metrics["model_sales_rows_after_filters"] = int(len(prepared))
    metrics["model_sales_eur_after_filters"] = round(
        float(pd.to_numeric(prepared.get(columns.net_sales, pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum()),
        2,
    )
    if "product_fallback_source" in prepared.columns:
        metrics["product_fallback_source_counts"] = {
            str(key): int(value)
            for key, value in prepared["product_fallback_source"].fillna("(missing)").value_counts(dropna=False).to_dict().items()
        }
    else:
        metrics["product_fallback_source_counts"] = {}

    if "product_group_match_confidence" in prepared.columns:
        metrics["product_group_match_confidence_avg"] = round(float(prepared["product_group_match_confidence"].mean()), 4)
        metrics["product_group_match_confidence_by_method"] = {
            str(key): round(float(value), 4)
            for key, value in prepared.groupby(columns.product_group_match_method)["product_group_match_confidence"].mean().to_dict().items()
        }

    if metrics["source_sales_rows"]:
        metrics["model_row_coverage_pct"] = round(100 * metrics["model_sales_rows_after_filters"] / metrics["source_sales_rows"], 2)
    if metrics["source_sales_eur"]:
        metrics["model_sales_coverage_pct"] = round(100 * metrics["model_sales_eur_after_filters"] / metrics["source_sales_eur"], 2)

    return metrics


def filter_eligible_training_sales(sales: pd.DataFrame, config: AppConfig) -> pd.DataFrame:
    sales = prepare_sales_history(sales, config)
    status_column = config.columns.customer_status
    if status_column not in sales.columns:
        raise ValueError(
            f"Sales history is missing required training status column: {status_column}. "
            "Add the customer status join and map the column in config."
        )

    eligible_statuses = {str(status).strip().lower() for status in config.training.eligible_customer_statuses}
    filtered = sales.loc[
        sales[status_column].astype("string").str.strip().str.lower().isin(eligible_statuses)
    ].copy()
    if filtered.empty:
        raise ValueError(
            "No sales rows matched the eligible training statuses. "
            f"Configured statuses: {config.training.eligible_customer_statuses}"
        )

    business_annual_sales = compute_business_annual_sales(filtered, config)
    min_annual_sales = float(config.training.min_training_customer_annual_sales_eur)
    eligible_business_ids = set(
        business_annual_sales.loc[business_annual_sales >= min_annual_sales].index.astype(str).tolist()
    )
    filtered = filtered.loc[filtered[config.columns.business_id].astype(str).isin(eligible_business_ids)].copy()
    if filtered.empty:
        raise ValueError(
            "No sales rows remained after applying the minimum annual sales threshold for training. "
            f"Configured minimum annual sales: {config.training.min_training_customer_annual_sales_eur}"
        )
    return filtered


def compute_business_annual_sales(sales: pd.DataFrame, config: AppConfig) -> pd.Series:
    net_sales_column = config.columns.net_sales
    if net_sales_column not in sales.columns:
        raise ValueError(
            f"Sales history is missing required net sales column: {net_sales_column}. "
            "Annual customer potential cannot be calculated without net sales."
        )

    reference_date = (
        pd.Timestamp(config.training.as_of_date).normalize()
        if config.training.as_of_date
        else sales[config.columns.order_date].max().normalize()
    )
    window_start = reference_date - pd.Timedelta(days=config.training.lookback_days)
    lookback_sales = sales.loc[
        (sales[config.columns.order_date] > window_start) & (sales[config.columns.order_date] <= reference_date)
    ].copy()

    if lookback_sales.empty:
        raise ValueError("No sales rows fall within the configured annual potential lookback window.")

    aggregated = (
        lookback_sales.groupby(config.columns.business_id)[net_sales_column]
        .sum(min_count=1)
        .fillna(0.0)
        .astype(float)
    )
    aggregated.index = aggregated.index.astype(str)
    return aggregated


def resolve_feature_columns(config: AppConfig) -> tuple[list[str], list[str]]:
    numeric_columns = [column for column in config.features.numeric_company if column]
    categorical_columns = [column for column in config.features.categorical_company + config.features.extra_company if column]
    numeric_columns.extend(["snapshot_month", "snapshot_quarter"])
    return numeric_columns, categorical_columns


def resolve_as_of_date(config: AppConfig) -> pd.Timestamp:
    if config.training.as_of_date:
        return pd.Timestamp(config.training.as_of_date)
    return pd.Timestamp.utcnow().normalize()


def generate_snapshot_dates(sales: pd.DataFrame, config: AppConfig) -> list[pd.Timestamp]:
    order_date_column = config.columns.order_date
    max_date = sales[order_date_column].max()
    min_date = sales[order_date_column].min()
    if pd.isna(min_date) or pd.isna(max_date):
        raise ValueError("Sales history does not contain valid order dates.")

    start_date = (min_date + pd.Timedelta(days=config.training.lookback_days)).normalize()
    end_date = (max_date if config.training.as_of_date is None else pd.Timestamp(config.training.as_of_date)).normalize()
    snapshot_dates = pd.date_range(start=start_date, end=end_date, freq=config.training.snapshot_frequency)
    if len(snapshot_dates) < 2:
        midpoint = end_date - pd.Timedelta(days=max(config.training.lookback_days // 2, 30))
        snapshot_dates = pd.to_datetime([midpoint.normalize(), end_date.normalize()])
    return [pd.Timestamp(value) for value in snapshot_dates]


def split_time_aware(dataset: pd.DataFrame, test_fraction: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    snapshot_dates = sorted(dataset["snapshot_date"].drop_duplicates().tolist())
    test_count = max(1, int(len(snapshot_dates) * test_fraction))
    train_dates = snapshot_dates[:-test_count]
    test_dates = snapshot_dates[-test_count:]
    if not train_dates:
        raise ValueError("Not enough snapshot dates for a time-aware split.")

    train_df = dataset.loc[dataset["snapshot_date"].isin(train_dates)].reset_index(drop=True)
    test_df = dataset.loc[dataset["snapshot_date"].isin(test_dates)].reset_index(drop=True)
    return train_df, test_df


def _positive_business_ids_for_snapshot(
    sales: pd.DataFrame,
    business_id_column: str,
    order_date_column: str,
    snapshot_date: pd.Timestamp,
    lookback_days: int,
) -> set[str]:
    window_start = snapshot_date - pd.Timedelta(days=lookback_days)
    in_window = sales.loc[
        (sales[order_date_column] > window_start) & (sales[order_date_column] <= snapshot_date),
        business_id_column,
    ]
    return set(in_window.dropna().astype(str))
