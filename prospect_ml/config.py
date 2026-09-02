from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


ENV_PREFIX = "PROSPECT__"


@dataclass
class RuntimeConfig:
    gcp_project: str | None = None
    gcp_location: str | None = None
    log_level: str = "INFO"
    artifact_dir: str = "artifacts"


@dataclass
class SourceConfig:
    type: str = "bigquery"
    table: str | None = None
    query: str | None = None
    path: str | None = None


@dataclass
class SourcesConfig:
    companies: SourceConfig = field(default_factory=SourceConfig)
    sales: SourceConfig = field(default_factory=SourceConfig)
    accounts: SourceConfig = field(default_factory=SourceConfig)
    accounts_direct_delivery: SourceConfig = field(default_factory=SourceConfig)
    accounts_gokeep_plus: SourceConfig = field(default_factory=SourceConfig)


@dataclass
class ColumnConfig:
    business_id: str = "business_id"
    customer_id: str = "customer_id"
    customer_status: str = "customer_status"
    account_business_id: str = "Business ID"
    account_status: str = "status"
    order_date: str = "order_date"
    product: str = "product"
    net_sales: str = "net_sales"
    net_sales_fallbacks: list[str] = field(default_factory=lambda: ["sales"])
    margin: str = "margin"
    sales_status: str = "status"
    product_group_l3_code: str = "product_group_l3_code"
    product_group_match_method: str = "product_group_match_method"
    productcode: str = "productcode"
    name: str = "name"
    category: str = "category"
    reference: str = "reference"


@dataclass
class FeatureConfig:
    numeric_company: list[str] = field(default_factory=lambda: ["revenue", "headcount", "growth"])
    categorical_company: list[str] = field(default_factory=lambda: ["industry", "location"])
    extra_company: list[str] = field(default_factory=list)

    @property
    def company_feature_columns(self) -> list[str]:
        ordered = self.numeric_company + self.categorical_company + self.extra_company
        return list(dict.fromkeys(ordered))


@dataclass
class TrainingConfig:
    as_of_date: str | None = None
    lookback_days: int = 365
    snapshot_frequency: str = "M"
    test_fraction: float = 0.2
    model_type: str = "logistic_regression"
    calibration_method: str = "sigmoid"
    random_state: int = 42
    max_iter: int = 1000
    eligible_customer_statuses: list[str] = field(default_factory=lambda: ["Active", "Gokeep+"])
    min_training_customer_annual_sales_eur: float = 4000.0
    default_account_status: str = "Active"
    direct_delivery_status: str = "direct_delivery"
    gokeep_plus_status: str = "Gokeep+"
    invoice_statuses: list[str] = field(default_factory=lambda: ["Invoiced"])
    excluded_product_group_l3_codes: list[str] = field(default_factory=lambda: ["15.01.01"])


@dataclass
class PotentialConfig:
    min_annual_potential_eur: float = 4000.0
    c_min_annual_potential_eur: float = 10000.0
    b_min_annual_potential_eur: float = 50000.0
    a_min_annual_potential_eur: float = 100000.0
    below_c_label: str = "Below C"
    partner_label: str = "Partner"


@dataclass
class RecommendationConfig:
    top_k_neighbors: int = 10
    max_recommendations: int = 5
    min_rule_support: int = 2
    min_rule_confidence: float = 0.05
    min_rule_lift: float = 1.0
    neighbor_weight: float = 0.7
    rule_weight: float = 0.3


@dataclass
class OutputConfig:
    mode: str = "csv"
    bigquery_table: str | None = None
    csv_uri: str | None = None
    write_disposition: str = "WRITE_TRUNCATE"


@dataclass
class AppConfig:
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    sources: SourcesConfig = field(default_factory=SourcesConfig)
    columns: ColumnConfig = field(default_factory=ColumnConfig)
    features: FeatureConfig = field(default_factory=FeatureConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    potential: PotentialConfig = field(default_factory=PotentialConfig)
    recommendations: RecommendationConfig = field(default_factory=RecommendationConfig)
    output: OutputConfig = field(default_factory=OutputConfig)


def load_config(path: str | os.PathLike[str]) -> AppConfig:
    config_path = Path(path)
    raw = {}
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    merged = _deep_merge(raw, _env_overrides())
    return AppConfig(
        runtime=RuntimeConfig(**merged.get("runtime", {})),
        sources=SourcesConfig(
            companies=SourceConfig(**merged.get("sources", {}).get("companies", {})),
            sales=SourceConfig(**merged.get("sources", {}).get("sales", {})),
            accounts=SourceConfig(**merged.get("sources", {}).get("accounts", {})),
            accounts_direct_delivery=SourceConfig(**merged.get("sources", {}).get("accounts_direct_delivery", {})),
            accounts_gokeep_plus=SourceConfig(**merged.get("sources", {}).get("accounts_gokeep_plus", {})),
        ),
        columns=ColumnConfig(**merged.get("columns", {})),
        features=FeatureConfig(**merged.get("features", {})),
        training=TrainingConfig(**merged.get("training", {})),
        potential=PotentialConfig(**merged.get("potential", {})),
        recommendations=RecommendationConfig(**merged.get("recommendations", {})),
        output=OutputConfig(**merged.get("output", {})),
    )


def _env_overrides() -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for key, value in os.environ.items():
        if not key.startswith(ENV_PREFIX):
            continue
        path = key[len(ENV_PREFIX) :].lower().split("__")
        _set_nested(overrides, path, yaml.safe_load(value))
    return overrides


def _set_nested(target: dict[str, Any], keys: list[str], value: Any) -> None:
    cursor = target
    for key in keys[:-1]:
        cursor = cursor.setdefault(key, {})
    cursor[keys[-1]] = value


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
