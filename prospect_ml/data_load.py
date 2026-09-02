from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

from prospect_ml.config import AppConfig, SourceConfig


LOGGER = logging.getLogger(__name__)


def create_bigquery_client(config: AppConfig) -> bigquery.Client:
    return bigquery.Client(project=config.runtime.gcp_project, location=config.runtime.gcp_location)


def load_company_data(config: AppConfig, bq_client: bigquery.Client | None = None) -> pd.DataFrame:
    return _load_source(config.sources.companies, bq_client)


def load_sales_data(config: AppConfig, bq_client: bigquery.Client | None = None) -> pd.DataFrame:
    sales = _load_source(config.sources.sales, bq_client)
    sales[config.columns.order_date] = pd.to_datetime(sales[config.columns.order_date], errors="coerce")
    return sales


def load_account_data(config: AppConfig, bq_client: bigquery.Client | None = None) -> pd.DataFrame | None:
    source = config.sources.accounts
    if not any([source.table, source.query, source.path]):
        return None
    return _load_source(source, bq_client)


def load_direct_delivery_account_data(config: AppConfig, bq_client: bigquery.Client | None = None) -> pd.DataFrame | None:
    source = config.sources.accounts_direct_delivery
    if not any([source.table, source.query, source.path]):
        return None
    return _load_source(source, bq_client)


def load_gokeep_plus_account_data(config: AppConfig, bq_client: bigquery.Client | None = None) -> pd.DataFrame | None:
    source = config.sources.accounts_gokeep_plus
    if not any([source.table, source.query, source.path]):
        return None
    return _load_source(source, bq_client)


def _load_source(source: SourceConfig, bq_client: bigquery.Client | None = None) -> pd.DataFrame:
    source_type = source.type.lower()
    LOGGER.info("Loading source", extra={"source_type": source_type, "table": source.table, "path": source.path})

    if source_type == "bigquery":
        if bq_client is None:
            raise ValueError("BigQuery client is required for BigQuery sources.")
        query = source.query or _table_query(source.table)
        return bq_client.query(query).result().to_dataframe(create_bqstorage_client=False)
    if source_type == "csv":
        _require_path(source.path)
        return pd.read_csv(source.path)
    if source_type in {"excel", "xlsx", "xls"}:
        _require_path(source.path)
        return pd.read_excel(source.path)
    if source_type == "parquet":
        _require_path(source.path)
        return pd.read_parquet(source.path)
    if source_type == "json":
        _require_path(source.path)
        return pd.read_json(source.path)
    raise ValueError(f"Unsupported source type: {source.type}")


def ensure_columns(frame: pd.DataFrame, required_columns: list[str], frame_name: str) -> None:
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{frame_name} is missing required columns: {missing}")


def ensure_output_directory(path_like: str) -> None:
    path = Path(path_like)
    if path.parent and not str(path).startswith("gs://"):
        path.parent.mkdir(parents=True, exist_ok=True)


def _require_path(path: str | None) -> None:
    if not path:
        raise ValueError("File-based source requires a path.")


def _table_query(table: str | None) -> str:
    if not table:
        raise ValueError("BigQuery source requires either query or table.")
    return f"SELECT * FROM `{table}`"
