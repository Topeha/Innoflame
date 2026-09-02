from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parent
SOURCE_CSV = BASE / "outputs" / "Innoflame_merged_sales_csv_source_with_L1_L2_L3_delivery_handling.csv"
OUTPUT_JSON = BASE / "outputs" / "processed_inclusion_impact_data_summary.json"
OUTPUT_CSV = BASE / "outputs" / "processed_inclusion_impact_year_status.csv"


def summarize(df: pd.DataFrame, mask: pd.Series) -> dict[str, int | float]:
    selected = df.loc[mask]
    return {
        "rows": int(mask.sum()),
        "sales_eur": round(float(selected["sales_value"].sum()), 2),
        "accounts": int(selected["accountid"].nunique()),
        "monthly_account_rows": int(selected.groupby(["accountid", "year_month"], dropna=False).size().shape[0]),
        "missing_group_rows": int((mask & df["missing_group"]).sum()),
        "missing_group_sales_eur": round(float(df.loc[mask & df["missing_group"], "sales_value"].sum()), 2),
    }


def main() -> None:
    df = pd.read_csv(SOURCE_CSV, dtype=str, encoding="utf-8-sig", keep_default_na=False)
    df["sales_value"] = pd.to_numeric(
        df["sales"].astype(str).str.replace(",", ".", regex=False),
        errors="coerce",
    ).fillna(0.0)
    df["sold_at_date"] = pd.to_datetime(df["sold_at"], errors="coerce")
    df["year"] = df["sold_at_date"].dt.year
    df["year_month"] = df["sold_at_date"].dt.to_period("M").astype(str)
    df["status_clean"] = df["status"].astype(str).str.strip()
    df["delivery_handling"] = df["product_group_l3_code"].astype(str).str.strip().eq("15.01.01")
    df["missing_group"] = df["product_group_l3_code"].astype(str).str.strip().eq("")
    df["has_account"] = df["accountid"].astype(str).str.strip().ne("")
    df["has_month"] = df["sold_at_date"].notna()

    invoiced = df["status_clean"].eq("Invoiced")
    processed = df["status_clean"].eq("Processed")
    base_mask = invoiced & ~df["delivery_handling"] & df["has_account"] & df["has_month"]
    processed_increment_mask = processed & ~df["delivery_handling"] & df["has_account"] & df["has_month"]
    combined_mask = (invoiced | processed) & ~df["delivery_handling"] & df["has_account"] & df["has_month"]

    year_status = (
        df.loc[combined_mask]
        .groupby(["year", "status_clean"], dropna=False)
        .agg(rows=("id", "size"), sales_eur=("sales_value", "sum"), accounts=("accountid", "nunique"))
        .reset_index()
        .sort_values(["year", "status_clean"])
    )
    year_status["sales_eur"] = year_status["sales_eur"].round(2)

    summary = {
        "source_csv": str(SOURCE_CSV.resolve()),
        "current_invoiced_only": summarize(df, base_mask),
        "processed_increment": summarize(df, processed_increment_mask),
        "invoiced_plus_processed": summarize(df, combined_mask),
        "processed_delivery_handling_excluded": {
            "rows": int((processed & df["delivery_handling"]).sum()),
            "sales_eur": round(float(df.loc[processed & df["delivery_handling"], "sales_value"].sum()), 2),
        },
    }
    cur = summary["current_invoiced_only"]
    inc = summary["processed_increment"]
    combo = summary["invoiced_plus_processed"]
    summary["change_vs_invoiced_only"] = {
        "rows_delta": int(combo["rows"] - cur["rows"]),
        "rows_delta_pct": round((combo["rows"] / cur["rows"] - 1) * 100, 2) if cur["rows"] else None,
        "sales_delta_eur": round(float(combo["sales_eur"] - cur["sales_eur"]), 2),
        "sales_delta_pct": round((combo["sales_eur"] / cur["sales_eur"] - 1) * 100, 2) if cur["sales_eur"] else None,
        "accounts_delta": int(combo["accounts"] - cur["accounts"]),
        "monthly_account_rows_delta": int(combo["monthly_account_rows"] - cur["monthly_account_rows"]),
        "processed_share_of_combined_sales_pct": round(float(inc["sales_eur"] / combo["sales_eur"] * 100), 2)
        if combo["sales_eur"]
        else None,
    }

    OUTPUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    year_status.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"year_status_csv={OUTPUT_CSV}")


if __name__ == "__main__":
    main()
