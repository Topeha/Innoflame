from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parent / "prospektointi"
OLD_CSV = BASE / "prospect_segment_model_all_prospects.csv"
NEW_CSV = BASE / "prospect_segment_model_all_prospects_corrected_sales_rerun.csv"
OUT_JSON = BASE / "prospect_segment_model_all_prospects_corrected_sales_rerun_comparison.json"
OUT_CSV = BASE / "prospect_segment_model_all_prospects_corrected_sales_rerun_comparison.csv"


def summary(frame: pd.DataFrame, label: str) -> dict[str, object]:
    return {
        "model": label,
        "rows": int(len(frame)),
        "total_potential_eur": round(float(frame["ennustettu potentiaali"].sum()), 2),
        "mean_potential_eur": round(float(frame["ennustettu potentiaali"].mean()), 2),
        "median_potential_eur": round(float(frame["ennustettu potentiaali"].median()), 2),
        "avg_score": round(float(frame["score"].mean()), 6),
        "top100_potential_eur": round(float(frame.nsmallest(100, "rank")["ennustettu potentiaali"].sum()), 2),
        "top500_potential_eur": round(float(frame.nsmallest(500, "rank")["ennustettu potentiaali"].sum()), 2),
        "top1000_potential_eur": round(float(frame.nsmallest(1000, "rank")["ennustettu potentiaali"].sum()), 2),
    }


def main() -> None:
    old = pd.read_csv(OLD_CSV, dtype={"business_id": str})
    new = pd.read_csv(NEW_CSV, dtype={"business_id": str})
    for frame in (old, new):
        for column in ("rank", "score", "ennustettu potentiaali"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    old_summary = summary(old, "old")
    new_summary = summary(new, "new")
    comparison = []
    for key, old_value in old_summary.items():
        new_value = new_summary[key]
        if key == "model":
            continue
        comparison.append(
            {
                "metric": key,
                "old": old_value,
                "new": new_value,
                "delta": round(float(new_value) - float(old_value), 2),
                "delta_pct": round(100 * (float(new_value) - float(old_value)) / float(old_value), 2)
                if float(old_value)
                else None,
            }
        )

    overlaps = []
    for n in (100, 500, 1000):
        old_ids = set(old.nsmallest(n, "rank")["business_id"].dropna())
        new_ids = set(new.nsmallest(n, "rank")["business_id"].dropna())
        overlap = old_ids & new_ids
        overlaps.append(
            {
                "top_n": n,
                "overlap": len(overlap),
                "overlap_pct_new": round(100 * len(overlap) / len(new_ids), 2) if new_ids else 0.0,
                "new_entries": len(new_ids - old_ids),
                "dropped_entries": len(old_ids - new_ids),
            }
        )

    merged = new[["business_id", "company", "rank", "ennustettu potentiaali"]].merge(
        old[["business_id", "company", "rank", "ennustettu potentiaali"]],
        on="business_id",
        how="outer",
        suffixes=("_new", "_old"),
        indicator=True,
    )
    merged["rank_delta"] = merged["rank_new"] - merged["rank_old"]
    merged["potential_delta"] = merged["ennustettu potentiaali_new"] - merged["ennustettu potentiaali_old"]
    merged.sort_values("rank_new", na_position="last").to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    result = {
        "old_summary": old_summary,
        "new_summary": new_summary,
        "comparison": comparison,
        "overlap": overlaps,
        "new_metrics": json.loads(NEW_CSV.with_suffix(".metrics.json").read_text(encoding="utf-8")),
        "sales_audit": json.loads(
            (BASE / "sales_import_test" / "GoSystems_sales_26_05_2026_model_input_corrected.audit.json").read_text(
                encoding="utf-8"
            )
        ),
        "comparison_csv": str(OUT_CSV.resolve()),
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
