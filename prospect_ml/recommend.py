from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from prospect_ml.config import AppConfig
from prospect_ml.features import compute_business_annual_sales, filter_eligible_training_sales, prepare_company_features


LOGGER = logging.getLogger(__name__)


@dataclass
class SimilarityArtifacts:
    preprocessor: ColumnTransformer
    neighbor_index: NearestNeighbors
    customer_business_ids: np.ndarray
    customer_products: dict[str, Counter]
    customer_annual_sales: dict[str, float]
    rules_by_antecedent: dict[str, list[dict[str, float | str]]]


def fit_recommender(companies: pd.DataFrame, sales: pd.DataFrame, config: AppConfig) -> SimilarityArtifacts:
    prepared_companies = prepare_company_features(companies, config)
    eligible_sales = filter_eligible_training_sales(sales, config)
    customer_product_history = build_customer_product_history(eligible_sales, config)
    customer_annual_sales = compute_business_annual_sales(eligible_sales, config).to_dict()
    customer_ids = np.array(sorted(customer_product_history.keys()))

    if customer_ids.size == 0:
        raise ValueError("Cannot fit recommender because sales history has no customer products.")

    preprocessor = build_similarity_preprocessor(config)
    feature_columns = config.features.company_feature_columns
    all_company_matrix = preprocessor.fit_transform(prepared_companies[feature_columns])
    customer_mask = prepared_companies[config.columns.business_id].astype(str).isin(customer_ids).to_numpy()
    customer_matrix = all_company_matrix[customer_mask]
    neighbor_index = NearestNeighbors(metric="cosine")
    neighbor_index.fit(customer_matrix)

    return SimilarityArtifacts(
        preprocessor=preprocessor,
        neighbor_index=neighbor_index,
        customer_business_ids=prepared_companies.loc[customer_mask, config.columns.business_id].astype(str).to_numpy(),
        customer_products=customer_product_history,
        customer_annual_sales={str(key): float(value) for key, value in customer_annual_sales.items()},
        rules_by_antecedent=build_cooccurrence_rules(eligible_sales, config),
    )


def recommend_products(
    prospects: pd.DataFrame,
    companies: pd.DataFrame,
    recommender: SimilarityArtifacts,
    config: AppConfig,
) -> pd.DataFrame:
    prepared_companies = prepare_company_features(companies, config)
    company_lookup = prepared_companies.assign(_business_id_key=lambda df: df[config.columns.business_id].astype(str)).set_index("_business_id_key")
    available_ids = set(company_lookup.index)
    feature_columns = config.features.company_feature_columns

    recommendation_rows = []
    for _, row in prospects.iterrows():
        business_id_value = row[config.columns.business_id]
        business_id_key = str(business_id_value)
        if business_id_key not in available_ids:
            recommendation_rows.append(_empty_recommendation_row(config.columns.business_id, business_id_value))
            continue

        company_row = company_lookup.loc[business_id_key]
        company_frame = pd.DataFrame([company_row])[feature_columns]
        product_candidates, neighbor_details, annual_potential_estimate = _neighbor_product_scores(company_frame, recommender, config)
        combined_scores = _apply_rule_boosts(product_candidates, recommender.rules_by_antecedent, config)
        recommendations = _top_recommendations(combined_scores, product_candidates, neighbor_details, config)
        recommendation_rows.append(
            {
                config.columns.business_id: business_id_value,
                "annual_potential_estimate_eur": round(float(annual_potential_estimate), 2),
                "potential_segment": classify_potential_segment(float(annual_potential_estimate), config),
                "recommended_products": json.dumps(recommendations, ensure_ascii=True),
                "recommended_product_labels": ", ".join(item["product"] for item in recommendations),
                "similar_customers": json.dumps(neighbor_details, ensure_ascii=True),
            }
        )

    return pd.DataFrame(recommendation_rows)


def build_customer_product_history(sales: pd.DataFrame, config: AppConfig) -> dict[str, Counter]:
    business_id_column = config.columns.business_id
    product_column = config.columns.product
    sales_value_column = config.columns.net_sales
    confidence_column = "product_group_match_confidence"
    grouped = defaultdict(Counter)
    base_columns = [business_id_column, product_column]
    if sales_value_column in sales.columns:
        base_columns.append(sales_value_column)
    if confidence_column in sales.columns:
        base_columns.append(confidence_column)

    for _, row in sales[base_columns].dropna(subset=[business_id_column, product_column]).iterrows():
        business_id = str(row[business_id_column])
        product = str(row[product_column])
        weight = float(row[sales_value_column]) if pd.notna(row.get(sales_value_column)) else 1.0
        confidence = float(row[confidence_column]) if confidence_column in row and pd.notna(row.get(confidence_column)) else 1.0
        confidence = max(0.1, min(confidence, 1.0))
        weight *= confidence
        grouped[business_id][product] += max(weight, 1.0)

    return dict(grouped)


def build_cooccurrence_rules(sales: pd.DataFrame, config: AppConfig) -> dict[str, list[dict[str, float | str]]]:
    business_id_column = config.columns.business_id
    product_column = config.columns.product
    baskets = (
        sales[[business_id_column, product_column]]
        .dropna()
        .assign(**{product_column: lambda df: df[product_column].astype(str)})
        .groupby(business_id_column)[product_column]
        .apply(lambda values: sorted(set(values)))
    )

    item_counts: Counter = Counter()
    pair_counts: Counter = Counter()
    basket_count = len(baskets)

    for basket in baskets:
        for item in basket:
            item_counts[item] += 1
        for antecedent in basket:
            for consequent in basket:
                if antecedent != consequent:
                    pair_counts[(antecedent, consequent)] += 1

    rules_by_antecedent: dict[str, list[dict[str, float | str]]] = defaultdict(list)
    for (antecedent, consequent), support_count in pair_counts.items():
        if support_count < config.recommendations.min_rule_support:
            continue
        confidence = support_count / item_counts[antecedent]
        consequent_support = item_counts[consequent] / basket_count if basket_count else 0.0
        lift = confidence / consequent_support if consequent_support else 0.0
        if confidence < config.recommendations.min_rule_confidence or lift < config.recommendations.min_rule_lift:
            continue
        rules_by_antecedent[antecedent].append(
            {
                "product": consequent,
                "support_count": float(support_count),
                "confidence": float(confidence),
                "lift": float(lift),
            }
        )

    return dict(rules_by_antecedent)


def build_similarity_preprocessor(config: AppConfig) -> ColumnTransformer:
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=True)),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, config.features.numeric_company),
            ("cat", categorical_pipeline, config.features.categorical_company + config.features.extra_company),
        ]
    )


def _neighbor_product_scores(
    company_frame: pd.DataFrame,
    recommender: SimilarityArtifacts,
    config: AppConfig,
) -> tuple[dict[str, float], list[dict[str, object]], float]:
    company_matrix = recommender.preprocessor.transform(company_frame)
    distances, indices = recommender.neighbor_index.kneighbors(company_matrix, n_neighbors=min(config.recommendations.top_k_neighbors, len(recommender.customer_business_ids)))
    product_scores: dict[str, float] = defaultdict(float)
    neighbor_details: list[dict[str, object]] = []
    weighted_potential = 0.0
    similarity_sum = 0.0

    for distance, customer_idx in zip(distances[0], indices[0], strict=True):
        similarity = max(0.0, 1.0 - float(distance))
        customer_id = str(recommender.customer_business_ids[customer_idx])
        customer_products = recommender.customer_products.get(customer_id, Counter())
        top_products = [product for product, _ in customer_products.most_common(5)]
        annual_sales = float(recommender.customer_annual_sales.get(customer_id, 0.0))
        neighbor_details.append(
            {
                "business_id": customer_id,
                "similarity": round(similarity, 6),
                "annual_sales_eur": round(annual_sales, 2),
                "products": top_products,
            }
        )
        weighted_potential += similarity * annual_sales
        similarity_sum += similarity

        for product, weight in customer_products.items():
            product_scores[product] += similarity * float(weight)

    if similarity_sum > 0:
        annual_potential_estimate = weighted_potential / similarity_sum
    elif recommender.customer_annual_sales:
        annual_potential_estimate = float(np.mean(list(recommender.customer_annual_sales.values())))
    else:
        annual_potential_estimate = 0.0

    return dict(product_scores), neighbor_details, annual_potential_estimate


def _apply_rule_boosts(
    neighbor_scores: dict[str, float],
    rules_by_antecedent: dict[str, list[dict[str, float | str]]],
    config: AppConfig,
) -> dict[str, float]:
    if not neighbor_scores:
        return {}

    normalized_neighbor = _normalize_scores(neighbor_scores)
    rule_scores: dict[str, float] = defaultdict(float)

    for product, product_score in normalized_neighbor.items():
        for rule in rules_by_antecedent.get(product, []):
            consequent = str(rule["product"])
            rule_scores[consequent] += product_score * float(rule["confidence"]) * float(rule["lift"])

    normalized_rule = _normalize_scores(rule_scores)
    combined_scores = defaultdict(float)
    for product, score in normalized_neighbor.items():
        combined_scores[product] += config.recommendations.neighbor_weight * score
    for product, score in normalized_rule.items():
        combined_scores[product] += config.recommendations.rule_weight * score
    return dict(combined_scores)


def _top_recommendations(
    combined_scores: dict[str, float],
    neighbor_scores: dict[str, float],
    neighbor_details: list[dict[str, object]],
    config: AppConfig,
) -> list[dict[str, object]]:
    recommendations: list[dict[str, object]] = []
    top_neighbors = neighbor_details[:3]
    for product, score in sorted(combined_scores.items(), key=lambda item: item[1], reverse=True)[: config.recommendations.max_recommendations]:
        supporting_neighbors = [item["business_id"] for item in top_neighbors if product in item["products"]]
        recommendations.append(
            {
                "product": product,
                "score": round(float(score), 6),
                "neighbor_signal": round(float(neighbor_scores.get(product, 0.0)), 6),
                "reason": f"Similar customers bought this product: {', '.join(supporting_neighbors) if supporting_neighbors else 'yes'}",
            }
        )
    return recommendations


def _normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    max_score = max(scores.values())
    if max_score <= 0:
        return {key: 0.0 for key in scores}
    return {key: value / max_score for key, value in scores.items()}


def _empty_recommendation_row(business_id_column: str, business_id_value: object) -> dict[str, str | object]:
    return {
        business_id_column: business_id_value,
        "annual_potential_estimate_eur": 0.0,
        "potential_segment": "Partner",
        "recommended_products": "[]",
        "recommended_product_labels": "",
        "similar_customers": "[]",
    }


def classify_potential_segment(annual_potential_eur: float, config: AppConfig) -> str:
    if annual_potential_eur < float(config.potential.min_annual_potential_eur):
        return config.potential.partner_label
    if annual_potential_eur >= float(config.potential.a_min_annual_potential_eur):
        return "A"
    if annual_potential_eur >= float(config.potential.b_min_annual_potential_eur):
        return "B"
    if annual_potential_eur >= float(config.potential.c_min_annual_potential_eur):
        return "C"
    return config.potential.below_c_label
