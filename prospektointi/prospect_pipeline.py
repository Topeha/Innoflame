from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from prospect_ml.config import AppConfig, load_config
from prospect_ml.data_load import create_bigquery_client, ensure_columns, load_account_data, load_company_data, load_direct_delivery_account_data, load_gokeep_plus_account_data, load_sales_data
from prospect_ml.export import export_results, write_metrics
from prospect_ml.features import build_sales_quality_metrics, build_scoring_dataset, build_training_dataset, current_customers, enrich_sales_with_account_status, enrich_sales_with_fixed_account_status, resolve_feature_columns
from prospect_ml.recommend import fit_recommender, recommend_products
from prospect_ml.score import score_companies
from prospect_ml.train import train_classifier


LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lead scoring and next-best-offer pipeline for prospecting.")
    parser.add_argument("--config", default="config.example.yaml", help="Path to YAML configuration file.")
    return parser.parse_args()


def configure_logging(config: AppConfig) -> None:
    logging.basicConfig(
        level=getattr(logging, config.runtime.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    configure_logging(config)

    bq_client = create_bigquery_client(config) if _needs_bigquery(config) else None
    companies = load_company_data(config, bq_client)
    sales = load_sales_data(config, bq_client)
    accounts = load_account_data(config, bq_client)
    accounts_direct_delivery = load_direct_delivery_account_data(config, bq_client)
    accounts_gokeep_plus = load_gokeep_plus_account_data(config, bq_client)
    sales = enrich_sales_with_account_status(sales, accounts, config)
    sales = enrich_sales_with_fixed_account_status(sales, accounts_direct_delivery, config.training.direct_delivery_status, config)
    sales = enrich_sales_with_fixed_account_status(sales, accounts_gokeep_plus, config.training.gokeep_plus_status, config)
    sales_quality_metrics = build_sales_quality_metrics(sales, config)

    ensure_columns(
        companies,
        [config.columns.business_id] + config.features.company_feature_columns,
        "companies",
    )
    ensure_columns(
        sales,
        [config.columns.business_id, config.columns.order_date, config.columns.customer_status],
        "sales",
    )

    _, train_df, test_df = build_training_dataset(companies, sales, config)
    numeric_columns, categorical_columns = resolve_feature_columns(config)
    model = train_classifier(train_df, test_df, numeric_columns, categorical_columns, config)

    scoring_df = build_scoring_dataset(companies, config)
    scored = score_companies(model, scoring_df)
    customer_ids = current_customers(sales, config)
    prospect_mask = ~scored[config.columns.business_id].astype(str).isin(customer_ids)
    prospects = scored.loc[prospect_mask].copy()

    recommender = fit_recommender(companies, sales, config)
    recommendations = recommend_products(prospects, companies, recommender, config)

    output = prospects.merge(recommendations, on=config.columns.business_id, how="left")
    output["expected_annual_value_eur"] = output["score"] * output["annual_potential_estimate_eur"]
    output = output.loc[
        output["annual_potential_estimate_eur"].fillna(0.0) >= float(config.potential.min_annual_potential_eur)
    ].copy()
    output["scored_at"] = pd.Timestamp.utcnow().isoformat()
    output = output.sort_values(["expected_annual_value_eur", "score"], ascending=[False, False]).reset_index(drop=True)

    export_results(output, config, bq_client)

    artifact_dir = Path(config.runtime.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = artifact_dir / "training_metrics.json"
    write_metrics({**model.metrics, "sales_quality": sales_quality_metrics}, str(metrics_path))
    LOGGER.info("Pipeline completed", extra={"prospects": len(output), "metrics_path": str(metrics_path)})


def _needs_bigquery(config: AppConfig) -> bool:
    source_types = [
        config.sources.companies.type.lower(),
        config.sources.sales.type.lower(),
        config.sources.accounts.type.lower(),
        config.sources.accounts_direct_delivery.type.lower(),
        config.sources.accounts_gokeep_plus.type.lower(),
    ]
    return "bigquery" in source_types or config.output.mode.lower() in {"bigquery", "both"}


if __name__ == "__main__":
    main()
