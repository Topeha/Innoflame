from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


DEFAULT_SOURCE_XLSX = Path(r"C:\Users\TommiHavukainen\Downloads\GoSystems_sales_26_05_2026_all_rows (2).xlsx")
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "sales_import_test"
DEFAULT_ACCOUNTS_XLSX = Path(__file__).resolve().parents[1] / "Account_20.05.2026_combined_with_profinder.xlsx"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare raw GoSystems sales Excel for prospektointi/prospect_model.py.")
    parser.add_argument("--source-xlsx", default=str(DEFAULT_SOURCE_XLSX))
    parser.add_argument("--accounts", default=str(DEFAULT_ACCOUNTS_XLSX))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--statuses",
        nargs="+",
        default=["Invoiced"],
        help="Sales statuses to include in the model input. Default: Invoiced.",
    )
    return parser.parse_args()


def to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype("string").str.replace(",", ".", regex=False), errors="coerce")


def main() -> None:
    args = parse_args()
    source_xlsx = Path(args.source_xlsx)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sales = pd.read_excel(source_xlsx, sheet_name=0, dtype=str)
    required = {"account_id", "status", "price", "amount", "created_at"}
    missing = sorted(required - set(sales.columns))
    if missing:
        raise ValueError(f"Source Excel is missing required columns: {missing}")

    sales["account_id_clean"] = pd.to_numeric(sales["account_id"], errors="coerce")
    sales["status_clean"] = sales["status"].astype("string").str.strip()
    sales["price_num"] = to_number(sales["price"]).fillna(0.0)
    sales["amount_num"] = to_number(sales["amount"]).fillna(0.0)
    sales["total_value"] = sales["price_num"] * sales["amount_num"]
    sales["created_at_dt"] = pd.to_datetime(sales["created_at"], errors="coerce", utc=True)
    sales["created_year_month"] = sales["created_at_dt"].dt.tz_convert(None).dt.to_period("M").astype(str)

    include_statuses = {status.strip().casefold() for status in args.statuses}
    include_mask = (
        sales["status_clean"].str.casefold().isin(include_statuses)
        & sales["account_id_clean"].notna()
        & sales["created_at_dt"].notna()
    )

    summarized = (
        sales.loc[include_mask]
        .groupby(["account_id_clean", "created_year_month"], as_index=False)["total_value"]
        .sum()
        .rename(columns={"account_id_clean": "account_id"})
        .sort_values(["account_id", "created_year_month"])
    )
    summarized["account_id"] = summarized["account_id"].astype("Int64")
    summarized["total_value"] = summarized["total_value"].round(6)

    output_csv = output_dir / "GoSystems_sales_26_05_2026_model_input_invoiced.csv"
    summarized.to_csv(output_csv, index=False, encoding="utf-8-sig")

    accounts_join_audit = {}
    accounts_path = Path(args.accounts)
    if accounts_path.exists():
        accounts = pd.read_excel(accounts_path, dtype=str)
        account_ids = pd.to_numeric(accounts.get("ID"), errors="coerce").dropna().astype("int64")
        input_ids = summarized["account_id"].dropna().astype("int64")
        matched = input_ids.isin(set(account_ids.tolist()))
        accounts_join_audit = {
            "account_master": str(accounts_path.resolve()),
            "model_input_unique_account_ids": int(input_ids.nunique()),
            "matched_unique_account_ids": int(input_ids[matched].nunique()),
            "unmatched_unique_account_ids": int(input_ids[~matched].nunique()),
            "matched_account_id_pct": round(float(input_ids[matched].nunique() / input_ids.nunique() * 100), 2)
            if input_ids.nunique()
            else 0.0,
        }

    status_summary = (
        sales.groupby("status_clean", dropna=False)
        .agg(rows=("status_clean", "size"), sales_eur=("total_value", "sum"))
        .reset_index()
        .sort_values("rows", ascending=False)
    )
    status_summary["sales_eur"] = status_summary["sales_eur"].round(2)
    status_summary.to_csv(output_dir / "source_status_summary.csv", index=False, encoding="utf-8-sig")

    audit = {
        "source_xlsx": str(source_xlsx.resolve()),
        "output_csv": str(output_csv.resolve()),
        "included_statuses": args.statuses,
        "source_rows": int(len(sales)),
        "source_sales_eur_price_times_amount": round(float(sales["total_value"].sum()), 2),
        "rows_missing_account_id": int(sales["account_id_clean"].isna().sum()),
        "rows_missing_created_at": int(sales["created_at_dt"].isna().sum()),
        "included_rows_before_monthly_aggregation": int(include_mask.sum()),
        "included_sales_eur": round(float(sales.loc[include_mask, "total_value"].sum()), 2),
        "model_input_rows": int(len(summarized)),
        "model_input_accounts": int(summarized["account_id"].nunique()),
        "first_month": str(summarized["created_year_month"].min()) if not summarized.empty else None,
        "last_month": str(summarized["created_year_month"].max()) if not summarized.empty else None,
        "account_join_audit": accounts_join_audit,
        "status_summary_csv": str((output_dir / "source_status_summary.csv").resolve()),
    }
    (output_dir / "sales_import_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
