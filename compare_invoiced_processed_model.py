from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parent
CURRENT_DIR = BASE / "outputs" / "innoflame_all_accounts_v3_corrected_sales"
ALT_DIR = BASE / "outputs" / "innoflame_all_accounts_v3_invoiced_processed"
CURRENT_CSV = CURRENT_DIR / "prospect_segment_model_all_accounts_v3_corrected_sales.csv"
ALT_CSV = ALT_DIR / "prospect_segment_model_all_accounts_v3_invoiced_processed.csv"
CURRENT_METRICS = CURRENT_DIR / "prospect_segment_model_all_accounts_v3_corrected_sales.metrics.json"
ALT_METRICS = ALT_DIR / "prospect_segment_model_all_accounts_v3_invoiced_processed.metrics.json"
DATA_AUDIT = BASE / "outputs" / "processed_inclusion_impact_data_summary.json"
OUTPUT_JSON = ALT_DIR / "invoiced_processed_vs_invoiced_only_summary.json"
OUTPUT_CSV = ALT_DIR / "invoiced_processed_vs_invoiced_only_comparison.csv"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def top_overlap(left: pd.DataFrame, right: pd.DataFrame, n: int, prospect_only: bool = False) -> dict:
    a = left.copy()
    b = right.copy()
    if prospect_only:
        a = a.loc[~a["is_account_customer"].fillna(False).astype(bool)]
        b = b.loc[~b["is_account_customer"].fillna(False).astype(bool)]
    a_ids = set(a.sort_values("rank").head(n)["business_id"].astype(str))
    b_ids = set(b.sort_values("rank").head(n)["business_id"].astype(str))
    overlap = len(a_ids & b_ids)
    return {
        "n": n,
        "prospect_only": prospect_only,
        "overlap_count": overlap,
        "overlap_pct": round(overlap / n * 100, 2) if n else None,
    }


def main() -> None:
    current = pd.read_csv(CURRENT_CSV, dtype={"business_id": str})
    alt = pd.read_csv(ALT_CSV, dtype={"business_id": str})

    value_cols = [
        "score",
        "final_value_eur",
        "expected_potential_eur",
        "ennustettu potentiaali",
        "avg_annual_sales_3y_eur",
        "recent_12m",
        "middle_12m",
        "oldest_12m",
    ]
    keep = ["business_id", "company", "rank", "priority", "is_account_customer"] + value_cols
    merged = current[keep].merge(
        alt[keep],
        on="business_id",
        how="outer",
        suffixes=("_invoiced", "_invoiced_processed"),
    )
    for col in value_cols + ["rank"]:
        left = f"{col}_invoiced"
        right = f"{col}_invoiced_processed"
        if left in merged.columns and right in merged.columns:
            merged[f"{col}_delta"] = pd.to_numeric(merged[right], errors="coerce") - pd.to_numeric(
                merged[left],
                errors="coerce",
            )
    merged["company"] = merged["company_invoiced_processed"].fillna(merged["company_invoiced"])
    merged.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    cur_metrics = load_json(CURRENT_METRICS)
    alt_metrics = load_json(ALT_METRICS)
    data_audit = load_json(DATA_AUDIT)

    metric_names = [
        "roc_auc",
        "average_precision",
        "positive_rate",
        "top_customers",
        "total_potential_eur",
        "account_customer_potential_eur",
        "non_account_potential_eur",
    ]
    metric_comparison = []
    for metric in metric_names:
        cur = cur_metrics.get(metric)
        new = alt_metrics.get(metric)
        delta = new - cur if cur is not None and new is not None else None
        metric_comparison.append(
            {
                "metric": metric,
                "invoiced_only": cur,
                "invoiced_processed": new,
                "delta": round(delta, 6) if isinstance(delta, float) else delta,
                "delta_pct": round((new / cur - 1) * 100, 2) if isinstance(cur, (int, float)) and cur else None,
            }
        )

    both_prospects = merged.loc[
        ~merged["is_account_customer_invoiced"].fillna(merged["is_account_customer_invoiced_processed"]).fillna(False).astype(bool)
    ].copy()
    biggest_prospect_increases = (
        both_prospects.sort_values("final_value_eur_delta", ascending=False)
        .head(20)[["business_id", "company", "final_value_eur_invoiced", "final_value_eur_invoiced_processed", "final_value_eur_delta", "rank_delta"]]
        .to_dict(orient="records")
    )
    biggest_prospect_decreases = (
        both_prospects.sort_values("final_value_eur_delta", ascending=True)
        .head(20)[["business_id", "company", "final_value_eur_invoiced", "final_value_eur_invoiced_processed", "final_value_eur_delta", "rank_delta"]]
        .to_dict(orient="records")
    )

    summary = {
        "current_model": "Invoiced only, delivery/handling excluded",
        "alternative_model": "Invoiced + Processed, delivery/handling excluded",
        "data_impact": data_audit,
        "metric_comparison": metric_comparison,
        "top_overlap": [
            top_overlap(current, alt, 100, False),
            top_overlap(current, alt, 500, False),
            top_overlap(current, alt, 1000, False),
            top_overlap(current, alt, 100, True),
            top_overlap(current, alt, 500, True),
            top_overlap(current, alt, 1000, True),
        ],
        "biggest_prospect_increases": biggest_prospect_increases,
        "biggest_prospect_decreases": biggest_prospect_decreases,
        "comparison_csv": str(OUTPUT_CSV.resolve()),
    }
    OUTPUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
