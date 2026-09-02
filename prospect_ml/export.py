from __future__ import annotations

import json
import logging
from io import BytesIO
from pathlib import Path

import pandas as pd
from google.cloud import bigquery
from pyarrow import fs

from prospect_ml.config import AppConfig


LOGGER = logging.getLogger(__name__)


def export_results(results: pd.DataFrame, config: AppConfig, bq_client: bigquery.Client | None = None) -> None:
    output_mode = config.output.mode.lower()
    export_frame = _stringify_complex_columns(results.copy())

    if output_mode in {"csv", "both"}:
        if not config.output.csv_uri:
            raise ValueError("CSV export mode requires output.csv_uri")
        write_csv(export_frame, config.output.csv_uri)

    if output_mode in {"bigquery", "both"}:
        if not config.output.bigquery_table:
            raise ValueError("BigQuery export mode requires output.bigquery_table")
        if bq_client is None:
            raise ValueError("BigQuery export requires a BigQuery client.")
        write_bigquery(export_frame, config.output.bigquery_table, config.output.write_disposition, bq_client)


def write_csv(results: pd.DataFrame, uri: str) -> None:
    LOGGER.info("Writing CSV output", extra={"uri": uri})
    if uri.startswith("gs://"):
        filesystem, path = fs.FileSystem.from_uri(uri)
        with filesystem.open_output_stream(path) as stream:
            stream.write(results.to_csv(index=False).encode("utf-8"))
        return

    path = Path(uri)
    path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(path, index=False)


def write_bigquery(results: pd.DataFrame, table: str, write_disposition: str, bq_client: bigquery.Client) -> None:
    LOGGER.info("Writing BigQuery output", extra={"table": table, "write_disposition": write_disposition})
    job_config = bigquery.LoadJobConfig(write_disposition=write_disposition)
    load_job = bq_client.load_table_from_dataframe(results, destination=table, job_config=job_config)
    load_job.result()


def write_metrics(metrics: dict[str, object], output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metrics, indent=2, ensure_ascii=True), encoding="utf-8")


def _stringify_complex_columns(frame: pd.DataFrame) -> pd.DataFrame:
    for column in frame.columns:
        if frame[column].map(lambda value: isinstance(value, (dict, list))).any():
            frame[column] = frame[column].map(lambda value: json.dumps(value, ensure_ascii=True))
    return frame
