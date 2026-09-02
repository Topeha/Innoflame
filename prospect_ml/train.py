from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from prospect_ml.config import AppConfig


LOGGER = logging.getLogger(__name__)


@dataclass
class TrainedModel:
    config: AppConfig
    preprocessor: ColumnTransformer
    explanation_model: LogisticRegression | HistGradientBoostingClassifier
    calibrated_model: CalibratedClassifierCV
    numeric_columns: list[str]
    categorical_columns: list[str]
    metrics: dict[str, float | int | str]

    @property
    def feature_columns(self) -> list[str]:
        return self.numeric_columns + self.categorical_columns

    @property
    def transformed_feature_names(self) -> list[str]:
        return self.preprocessor.get_feature_names_out().tolist()


def train_classifier(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    numeric_columns: list[str],
    categorical_columns: list[str],
    config: AppConfig,
) -> TrainedModel:
    preprocessor = build_preprocessor(
        numeric_columns=numeric_columns,
        categorical_columns=categorical_columns,
        sparse_output=config.training.model_type == "logistic_regression",
    )
    x_train = train_df[numeric_columns + categorical_columns]
    y_train = train_df["label"].astype(int)
    x_test = test_df[numeric_columns + categorical_columns]
    y_test = test_df["label"].astype(int)

    transformed_train = preprocessor.fit_transform(x_train)
    transformed_test = preprocessor.transform(x_test)

    if y_train.nunique() < 2:
        raise ValueError("Training data must contain both positive and negative labels.")

    explanation_model = build_base_estimator(config)
    explanation_model.fit(_maybe_dense(transformed_train, config.training.model_type), y_train)

    min_class_count = int(y_train.value_counts().min())
    if min_class_count >= 2:
        calibrated_model = CalibratedClassifierCV(
            estimator=clone(build_base_estimator(config)),
            method=config.training.calibration_method,
            cv=min(3, min_class_count),
        )
        calibrated_model.fit(_maybe_dense(transformed_train, config.training.model_type), y_train)
    else:
        LOGGER.warning("Falling back to prefit calibration because training split is very small.")
        calibrated_model = CalibratedClassifierCV(
            estimator=explanation_model,
            method=config.training.calibration_method,
            cv="prefit",
        )
        calibrated_model.fit(_maybe_dense(transformed_train, config.training.model_type), y_train)
    probabilities = calibrated_model.predict_proba(_maybe_dense(transformed_test, config.training.model_type))[:, 1]

    metrics = evaluate_predictions(y_test, probabilities, config.training.model_type)
    LOGGER.info("Finished model training", extra={"metrics": json.dumps(metrics, sort_keys=True)})

    return TrainedModel(
        config=config,
        preprocessor=preprocessor,
        explanation_model=explanation_model,
        calibrated_model=calibrated_model,
        numeric_columns=numeric_columns,
        categorical_columns=categorical_columns,
        metrics=metrics,
    )


def build_preprocessor(numeric_columns: list[str], categorical_columns: list[str], sparse_output: bool) -> ColumnTransformer:
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "encoder",
                OneHotEncoder(handle_unknown="ignore", sparse_output=sparse_output),
            ),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, numeric_columns),
            ("cat", categorical_pipeline, categorical_columns),
        ]
    )


def build_base_estimator(config: AppConfig) -> LogisticRegression | HistGradientBoostingClassifier:
    if config.training.model_type == "hist_gradient_boosting":
        return HistGradientBoostingClassifier(random_state=config.training.random_state)
    return LogisticRegression(
        max_iter=config.training.max_iter,
        random_state=config.training.random_state,
        class_weight="balanced",
    )


def evaluate_predictions(y_true: pd.Series, y_prob: np.ndarray, model_type: str) -> dict[str, float | int | str]:
    metrics: dict[str, float | int | str] = {
        "model_type": model_type,
        "rows": int(len(y_true)),
        "positive_rate": float(y_true.mean()),
        "brier_score": float(brier_score_loss(y_true, y_prob)),
        "log_loss": float(log_loss(y_true, y_prob, labels=[0, 1])),
        "average_precision": float(average_precision_score(y_true, y_prob)),
    }
    if y_true.nunique() > 1:
        metrics["roc_auc"] = float(roc_auc_score(y_true, y_prob))
    return metrics


def _maybe_dense(matrix: np.ndarray | sparse.spmatrix, model_type: str) -> np.ndarray | sparse.spmatrix:
    if model_type == "hist_gradient_boosting" and sparse.issparse(matrix):
        return matrix.toarray()
    return matrix
