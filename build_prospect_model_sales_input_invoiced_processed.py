from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parent
OUTPUTS = BASE / "outputs"
SOURCE_CSV = OUTPUTS / "Innoflame_merged_sales_csv_source_with_L1_L2_L3_delivery_handling.csv"
OUTPUT_CSV = OUTPUTS / "prospect_model_sales_input_invoiced_processed_product_groups.csv"
AUDIT_JSON = OUTPUTS / "prospect_model_sales_input_invoiced_processed_product_groups.audit.json"


def main() -> None:
    df = pd.read_csv(SOURCE_CSV, dtype=str, encoding="utf-8-sig", keep_default_na=False)
    df["sales_value"] = pd.to_numeric(
        df["sales"].astype(str).str.replace(",", ".", regex=False),
        errors="coerce",
    ).fillna(0.0)
    df["sold_at_date"] = pd.to_datetime(df["sold_at"], errors="coerce")
    df["created_year_month"] = df["sold_at_date"].dt.to_period("M").astype(str)
    df["status_clean"] = df["status"].astype(str).str.strip()

    included_status = df["status_clean"].isin(["Invoiced", "Processed"])
    delivery_handling = df["product_group_l3_code"].astype(str).str.strip().eq("15.01.01")
    has_account = df["accountid"].astype(str).str.strip().ne("")
    has_month = df["sold_at_date"].notna()
    filtered = df.loc[included_status & ~delivery_handling & has_account & has_month].copy()

    output = (
        filtered.groupby(["accountid", "created_year_month"], dropna=False)["sales_value"]
        .sum()
        .reset_index()
        .rename(columns={"accountid": "account_id", "sales_value": "total_value"})
    )
    output["total_value"] = output["total_value"].round(6)
    output.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    missing_group = df["product_group_l3_code"].astype(str).str.strip().eq("")
    audit = {
        "source_csv": str(SOURCE_CSV.resolve()),
        "output_csv": str(OUTPUT_CSV.resolve()),
        "included_statuses": ["Invoiced", "Processed"],
        "source_rows": int(len(df)),
        "source_sales_eur": round(float(df["sales_value"].sum()), 2),
        "included_rows": int(included_status.sum()),
        "included_sales_eur": round(float(df.loc[included_status, "sales_value"].sum()), 2),
        "processed_rows": int(df["status_clean"].eq("Processed").sum()),
        "processed_sales_eur": round(float(df.loc[df["status_clean"].eq("Processed"), "sales_value"].sum()), 2),
        "excluded_delivery_handling_rows": int((included_status & delivery_handling).sum()),
        "excluded_delivery_handling_sales_eur": round(
            float(df.loc[included_status & delivery_handling, "sales_value"].sum()),
            2,
        ),
        "included_missing_product_group_rows": int((included_status & missing_group).sum()),
        "included_missing_product_group_sales_eur": round(
            float(df.loc[included_status & missing_group, "sales_value"].sum()),
            2,
        ),
        "model_input_rows_before_monthly_aggregation": int(len(filtered)),
        "model_input_sales_eur": round(float(filtered["sales_value"].sum()), 2),
        "model_input_monthly_rows": int(len(output)),
        "model_input_accounts": int(output["account_id"].nunique()),
        "first_month": str(output["created_year_month"].min()) if not output.empty else None,
        "last_month": str(output["created_year_month"].max()) if not output.empty else None,
    }
    AUDIT_JSON.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
