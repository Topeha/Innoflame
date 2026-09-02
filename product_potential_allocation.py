from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from prospect_model import (
    add_segment_features,
    build_company_base,
    normalize_business_id,
    preprocess_accounts,
    preprocess_sales,
)


LOGGER = logging.getLogger(__name__)
OUTPUT_COLUMNS = ["business_id", "product_id", "product_potential", "product_rank"]


def allocate_product_potential(
    df_accounts: pd.DataFrame,
    df_product_sales: pd.DataFrame,
    *,
    max_weight: float | None = None,
    tolerance: float = 0.01,
) -> pd.DataFrame:
    accounts = _prepare_accounts(df_accounts)
    product_sales = _prepare_product_sales(df_product_sales)
    segment_weights, global_weights = calculate_product_weights(product_sales, max_weight=max_weight)
    allocated = _expand_accounts_to_products(accounts, segment_weights, global_weights)

    allocated["product_potential_raw"] = allocated["account_potential"] * allocated["weight"]
    raw_sum = allocated.groupby("business_id")["product_potential_raw"].transform("sum")
    allocated["product_potential"] = np.where(
        raw_sum.gt(0),
        allocated["product_potential_raw"] / raw_sum * allocated["account_potential"],
        0.0,
    )
    allocated = allocated.sort_values(
        ["business_id", "product_potential", "product_id"],
        ascending=[True, False, True],
        kind="mergesort",
    )
    allocated["product_rank"] = allocated.groupby("business_id").cumcount() + 1
    allocated["product_rank"] = allocated["product_rank"].astype(int)

    validate_product_potential_totals(allocated, tolerance=tolerance)
    return allocated[OUTPUT_COLUMNS].reset_index(drop=True)


def calculate_product_weights(
    df_product_sales: pd.DataFrame,
    *,
    max_weight: float | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    product_sales = _prepare_product_sales(df_product_sales)
    _validate_max_weight(max_weight)

    segment_base = (
        product_sales.dropna(subset=["segment_key"])
        .groupby(["segment_key", "product_id"], as_index=False)["sales"]
        .sum()
    )
    segment_weights = _build_group_weights(segment_base, ["segment_key"], max_weight=max_weight)

    global_base = product_sales.groupby("product_id", as_index=False)["sales"].sum()
    global_weights = _build_group_weights(global_base, [], max_weight=max_weight)
    return segment_weights, global_weights


def validate_product_potential_totals(df_allocated: pd.DataFrame, *, tolerance: float = 0.01) -> pd.DataFrame:
    _require_columns(df_allocated, {"business_id", "account_potential", "product_potential"}, "df_allocated")
    check = df_allocated.groupby("business_id", as_index=False).agg(
        total_product_potential=("product_potential", "sum"),
        account_potential=("account_potential", "first"),
    )
    check["diff"] = check["total_product_potential"] - check["account_potential"]
    failures = check.loc[check["diff"].abs() >= tolerance]
    if not failures.empty:
        sample = failures.head(5).to_dict(orient="records")
        raise ValueError(f"Product potential validation failed: abs(diff) must be < {tolerance}. Sample failures: {sample}")
    return check


def select_top_products(df_output: pd.DataFrame, *, top_n: int = 3) -> pd.DataFrame:
    _require_columns(df_output, {"business_id", "product_rank"}, "df_output")
    return df_output.loc[df_output["product_rank"] <= top_n].copy().reset_index(drop=True)


def build_product_sales_by_segment(
    accounts: pd.DataFrame,
    sales: pd.DataFrame,
    companies: pd.DataFrame,
    *,
    product_column: str = "sku",
    product_name_column: str = "name",
    sales_column: str = "total_value",
) -> pd.DataFrame:
    account_frame = preprocess_accounts(accounts)
    sales_frame = preprocess_sales(sales)
    company_frame = add_segment_features(build_company_base(companies, account_frame))

    account_segments = account_frame[["account_id", "business_id"]].merge(
        company_frame[["business_id", "company_segment"]],
        on="business_id",
        how="left",
    )
    product_sales = sales_frame.merge(account_segments, on="account_id", how="left")
    product_sales["product_id"] = _coalesce_product_id(product_sales, product_column, product_name_column)
    product_sales["segment"] = product_sales["company_segment"].fillna("unknown")
    product_sales["sales"] = pd.to_numeric(product_sales[sales_column], errors="coerce").fillna(0.0)
    product_sales = product_sales.dropna(subset=["product_id"])
    return product_sales[["product_id", "segment", "sales"]]


def _coalesce_product_id(frame: pd.DataFrame, product_column: str, product_name_column: str) -> pd.Series:
    if product_column not in frame.columns and product_name_column not in frame.columns:
        raise ValueError(f"Sales data must include {product_column!r} or {product_name_column!r}.")
    primary = frame[product_column].astype("string") if product_column in frame.columns else pd.Series(pd.NA, index=frame.index, dtype="string")
    fallback = frame[product_name_column].astype("string") if product_name_column in frame.columns else pd.Series(pd.NA, index=frame.index, dtype="string")
    product_id = primary.where(primary.str.strip().fillna("").ne(""), fallback)
    return product_id.map(_clean_id)


def _expand_accounts_to_products(accounts: pd.DataFrame, segment_weights: pd.DataFrame, global_weights: pd.DataFrame) -> pd.DataFrame:
    segment_keys = set(segment_weights["segment_key"].dropna().unique())
    segment_accounts = accounts.loc[accounts["segment_key"].isin(segment_keys)].copy()
    fallback_accounts = accounts.loc[~accounts["segment_key"].isin(segment_keys)].copy()

    frames: list[pd.DataFrame] = []
    if not segment_accounts.empty:
        frames.append(segment_accounts.merge(segment_weights, on="segment_key", how="inner"))
    if not fallback_accounts.empty:
        frames.append(
            fallback_accounts.assign(_join_key=1)
            .merge(global_weights.assign(_join_key=1), on="_join_key", how="inner")
            .drop(columns=["_join_key"])
        )
    if not frames:
        raise ValueError("No account-product rows could be created from the provided inputs.")
    return pd.concat(frames, ignore_index=True)


def _build_group_weights(base: pd.DataFrame, group_columns: list[str], *, max_weight: float | None) -> pd.DataFrame:
    if base.empty:
        raise ValueError("Product sales must contain at least one usable product row.")
    if not group_columns:
        result = base[["product_id"]].copy()
        result["weight"] = _weights_for_sales(base["sales"], max_weight=max_weight)
        return result

    frames = []
    for _, group in base.groupby(group_columns, dropna=False, sort=False):
        group = group.copy()
        group["weight"] = _weights_for_sales(group["sales"], max_weight=max_weight)
        frames.append(group)
    return pd.concat(frames, ignore_index=True)


def _weights_for_sales(sales: pd.Series, *, max_weight: float | None) -> np.ndarray:
    values = pd.to_numeric(sales, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    weights = values / values.sum() if values.sum() > 0 else np.full(len(values), 1.0 / len(values), dtype=float)
    return _apply_max_weight(weights, max_weight)


def _apply_max_weight(weights: np.ndarray, max_weight: float | None) -> np.ndarray:
    weights = np.nan_to_num(np.asarray(weights, dtype=float), nan=0.0, neginf=0.0, posinf=0.0)
    weights = np.clip(weights, 0.0, None)
    weights = weights / weights.sum() if weights.sum() > 0 else np.full(len(weights), 1.0 / len(weights), dtype=float)
    if max_weight is None:
        return weights
    if len(weights) * max_weight < 1.0 - 1e-12:
        raise ValueError(f"max_weight={max_weight} is too low for {len(weights)} products.")

    capped = np.zeros(len(weights), dtype=float)
    remaining = np.ones(len(weights), dtype=bool)
    remaining_mass = 1.0
    base_weights = weights.copy()
    while remaining.any():
        remaining_base = base_weights[remaining]
        candidate = remaining_base / remaining_base.sum() * remaining_mass if remaining_base.sum() > 0 else np.full(remaining.sum(), remaining_mass / remaining.sum())
        over_cap = candidate > max_weight + 1e-12
        remaining_indices = np.where(remaining)[0]
        if not over_cap.any():
            capped[remaining_indices] = candidate
            break
        capped_indices = remaining_indices[over_cap]
        capped[capped_indices] = max_weight
        remaining[capped_indices] = False
        remaining_mass = 1.0 - capped[~remaining].sum()
    return capped / capped.sum()


def _prepare_accounts(df_accounts: pd.DataFrame) -> pd.DataFrame:
    if "account_potential" not in df_accounts.columns:
        raise ValueError("df_accounts must include account_potential.")
    if "segment" not in df_accounts.columns:
        raise ValueError("df_accounts must include segment.")
    accounts = df_accounts.copy()
    accounts["business_id"] = accounts["business_id"].map(normalize_business_id).fillna(accounts["business_id"].map(_clean_id))
    accounts["account_potential"] = pd.to_numeric(accounts["account_potential"], errors="coerce").fillna(0.0)
    accounts["segment_key"] = accounts["segment"].map(_clean_id)
    if accounts["business_id"].isna().any():
        raise ValueError("df_accounts contains missing business_id values.")
    if accounts["account_potential"].lt(0).any():
        raise ValueError("df_accounts.account_potential must be non-negative.")
    return accounts


def _prepare_product_sales(df_product_sales: pd.DataFrame) -> pd.DataFrame:
    for column in ["product_id", "segment", "sales"]:
        if column not in df_product_sales.columns:
            raise ValueError(f"df_product_sales is missing required column: {column}")
    product_sales = df_product_sales.copy()
    product_sales["product_id"] = product_sales["product_id"].map(_clean_id)
    product_sales["segment_key"] = product_sales["segment"].map(_clean_id)
    product_sales["sales"] = pd.to_numeric(product_sales["sales"], errors="coerce").fillna(0.0).clip(lower=0.0)
    product_sales = product_sales.dropna(subset=["product_id"])
    if product_sales.empty:
        raise ValueError("df_product_sales must contain at least one product_id.")
    if product_sales["sales"].lt(0).any():
        raise ValueError("df_product_sales.sales must be non-negative.")
    return product_sales


def _prepare_model_output(path: Path) -> pd.DataFrame:
    output = pd.read_csv(path)
    accounts = output.rename(
        columns={
            "ennustettu potentiaali": "account_potential",
            "company_segment": "segment",
        }
    )
    return accounts[["business_id", "account_potential", "segment", "score"]].copy()


def _require_columns(dataframe: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required.difference(dataframe.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")


def _clean_id(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _validate_max_weight(max_weight: float | None) -> None:
    if max_weight is not None and (max_weight <= 0 or max_weight > 1):
        raise ValueError("max_weight must be in the interval (0, 1].")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Allocate Innoflame prospect potential to product-level priorities.")
    parser.add_argument("--prospect-output", default="prospect_segment_model_all_prospects.csv")
    parser.add_argument("--accounts", default="Account_20.05.2026_combined_with_profinder.xlsx")
    parser.add_argument("--sales", default="GoSystems_sales_26_05_2026_summarized.csv")
    parser.add_argument("--companies", default="haku_Myyntiin_ai_2026-04-23 (1).xlsx")
    parser.add_argument("--output", default="prospect_product_potential.csv")
    parser.add_argument("--top-output", default="prospect_product_potential_top3.csv")
    parser.add_argument("--top-n", type=int, default=3)
    parser.add_argument("--max-weight", type=float, default=0.3)
    parser.add_argument("--tolerance", type=float, default=0.01)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = parse_args()

    accounts = pd.read_excel(args.accounts)
    sales = pd.read_csv(args.sales)
    companies = pd.read_excel(args.companies)
    model_accounts = _prepare_model_output(Path(args.prospect_output))
    product_sales = build_product_sales_by_segment(accounts, sales, companies)

    output = allocate_product_potential(
        model_accounts,
        product_sales,
        max_weight=args.max_weight,
        tolerance=args.tolerance,
    )
    output.to_csv(args.output, index=False, encoding="utf-8-sig")
    select_top_products(output, top_n=args.top_n).to_csv(args.top_output, index=False, encoding="utf-8-sig")

    check_source = output.merge(model_accounts[["business_id", "account_potential"]], on="business_id", how="left")
    check = validate_product_potential_totals(check_source, tolerance=args.tolerance)
    metrics = {
        "accounts": int(check["business_id"].nunique()),
        "product_rows": int(len(output)),
        "max_abs_diff": float(check["diff"].abs().max()),
        "top_n": int(args.top_n),
        "max_weight": args.max_weight,
    }
    Path(args.output).with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    LOGGER.info("Saved product potential output to %s", args.output)
    LOGGER.info("Validation max abs diff %.8f", metrics["max_abs_diff"])


if __name__ == "__main__":
    main()
