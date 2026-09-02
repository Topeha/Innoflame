from __future__ import annotations

import json
import logging
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.linear_model import LogisticRegression

from prospect_ml.train import TrainedModel


LOGGER = logging.getLogger(__name__)


def score_companies(model: TrainedModel, scoring_df: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
    feature_columns = model.feature_columns
    transformed = model.preprocessor.transform(scoring_df[feature_columns])
    probabilities = model.calibrated_model.predict_proba(_dense_if_needed(transformed, model))[:, 1]
    scored = scoring_df.copy()
    scored["score"] = probabilities
    explanations = build_explanations(model, transformed, scoring_df, top_n=top_n)
    scored["top_feature_contributions"] = [json.dumps(item, ensure_ascii=True) for item in explanations]
    scored["explanation"] = [format_explanation(item) for item in explanations]
    return scored


def build_explanations(
    model: TrainedModel,
    transformed_matrix,
    raw_frame: pd.DataFrame,
    top_n: int = 3,
) -> list[list[dict[str, object]]]:
    if not isinstance(model.explanation_model, LogisticRegression):
        return [[{"feature": "model_type", "direction": "info", "contribution": 0.0, "value": model.config.training.model_type}] for _ in range(len(raw_frame))]

    transformed_feature_names = model.transformed_feature_names
    coefficients = model.explanation_model.coef_[0]
    results: list[list[dict[str, object]]] = []

    for row_index in range(raw_frame.shape[0]):
        row = transformed_matrix[row_index]
        if sparse.issparse(row):
            contribution_vector = row.multiply(coefficients).toarray().ravel()
        else:
            contribution_vector = np.asarray(row).ravel() * coefficients

        grouped = defaultdict(float)
        for feature_name, contribution in zip(transformed_feature_names, contribution_vector, strict=True):
            source_feature = _source_feature_name(feature_name, model.categorical_columns)
            grouped[source_feature] += float(contribution)

        top_features = sorted(grouped.items(), key=lambda item: abs(item[1]), reverse=True)[:top_n]
        row_explanations: list[dict[str, object]] = []
        raw_row = raw_frame.iloc[row_index]
        for feature_name, contribution in top_features:
            row_explanations.append(
                {
                    "feature": feature_name,
                    "contribution": round(contribution, 6),
                    "direction": "positive" if contribution >= 0 else "negative",
                    "value": _safe_value(raw_row.get(feature_name)),
                }
            )
        results.append(row_explanations)

    return results


def format_explanation(explanation: list[dict[str, object]]) -> str:
    parts = []
    for item in explanation:
        feature = item["feature"]
        value = item["value"]
        contribution = float(item["contribution"])
        sign = "+" if contribution >= 0 else "-"
        parts.append(f"{feature}={value} ({sign}{abs(contribution):.3f})")
    return ", ".join(parts)


def _source_feature_name(transformed_name: str, categorical_columns: list[str]) -> str:
    if transformed_name.startswith("num__"):
        return transformed_name.removeprefix("num__")
    raw_name = transformed_name.removeprefix("cat__")
    for column in sorted(categorical_columns, key=len, reverse=True):
        prefix = f"{column}_"
        if raw_name == column or raw_name.startswith(prefix):
            return column
    return raw_name


def _safe_value(value: object) -> object:
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer, np.floating)):
        return float(value)
    return str(value)


def _dense_if_needed(matrix, model: TrainedModel):
    if model.config.training.model_type == "hist_gradient_boosting" and sparse.issparse(matrix):
        return matrix.toarray()
    return matrix
