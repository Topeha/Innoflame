"""Add next product-group recommendations to an existing prospect output.

This is a post-processing step. It never recalculates or changes prospect
score, potential, segment, or rank.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROSPECTS = ROOT / "prospektointi" / "prospect_segment_model_all_prospects_final_without_netvisor.csv"
DEFAULT_CURRENT_CUSTOMERS = ROOT / "potentiaali" / "current_customer_potential_new_sources.csv"
DEFAULT_SALES = ROOT / "outputs" / "Innoflame_merged_sales_csv_source_with_L1_L2_L3_delivery_handling.csv"
DEFAULT_MASTER = ROOT / "tuoteryhmittely" / "INNOFLAME-TUOTELISTA-TUOTERYHMITTELY.xlsx"
DEFAULT_ACCOUNTS = ROOT / "potentiaali" / "Account_20.05.2026_combined_with_profinder.xlsx"


def normalize_business_id(value: object) -> str:
    if pd.isna(value):
        return ""
    digits = "".join(character for character in str(value).strip().upper().replace("FI", "") if character.isdigit())
    if len(digits) == 7:
        digits = "0" + digits
    return f"{digits[:-1]}-{digits[-1]}" if len(digits) >= 8 else ""


def normalize_code(value: object) -> str:
    return "" if pd.isna(value) else str(value).strip().upper()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add product recommendations to prospect output.")
    parser.add_argument("--prospects", default=str(DEFAULT_PROSPECTS))
    parser.add_argument("--current-customers", default=str(DEFAULT_CURRENT_CUSTOMERS))
    parser.add_argument("--sales", default=str(DEFAULT_SALES))
    parser.add_argument("--product-master", default=str(DEFAULT_MASTER))
    parser.add_argument("--accounts", default=str(DEFAULT_ACCOUNTS))
    parser.add_argument("--output", default=str(ROOT / "prospektointi" / "prospect_segment_model_all_prospects_final_with_product_recommendations.csv"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prospects = pd.read_csv(args.prospects, sep=None, engine="python")
    current = pd.read_csv(args.current_customers, sep=None, engine="python")
    sales = pd.read_csv(args.sales, sep=None, engine="python")
    accounts = pd.read_excel(args.accounts, dtype=str)
    master = pd.read_excel(args.product_master, sheet_name="Tuotteet", dtype=str)

    master = master.assign(
        product_code=master["Tuotekoodi"].map(normalize_code),
        product_group=master["Tuoteryhmä"].fillna("").astype(str).str.strip(),
        product_name=master["Tuotteen nimi"].fillna("").astype(str).str.strip(),
    )
    master = master.loc[master["product_code"].ne("") & master["product_group"].ne("")].drop_duplicates("product_code")

    account_col = "ID" if "ID" in accounts.columns else "account_id"
    business_col = next(column for column in accounts.columns if str(column).strip().casefold() in {"business id", "business_id", "y-tunnus", "y tunnus"})
    account_keys = accounts[[account_col, business_col]].copy()
    account_keys.columns = ["account_id", "business_id"]
    account_keys["account_id"] = pd.to_numeric(account_keys["account_id"], errors="coerce")
    account_keys["business_id"] = account_keys["business_id"].map(normalize_business_id)
    account_keys = account_keys.dropna(subset=["account_id"]).drop_duplicates("account_id")

    sales_account_col = next(column for column in ("accountid", "account_id") if column in sales.columns)
    sales_code_col = next(column for column in ("productcode", "ProductCode", "sku") if column in sales.columns)
    value_col = "sales" if "sales" in sales.columns else "total_value"
    sales_frame = sales[[sales_account_col, sales_code_col, value_col]].copy()
    sales_frame.columns = ["account_id", "product_code", "sales_eur"]
    sales_frame["account_id"] = pd.to_numeric(sales_frame["account_id"], errors="coerce")
    sales_frame["product_code"] = sales_frame["product_code"].map(normalize_code)
    sales_frame["sales_eur"] = pd.to_numeric(sales_frame["sales_eur"], errors="coerce").fillna(0.0)
    sales_frame = sales_frame.merge(account_keys, on="account_id", how="left").merge(
        master[["product_code", "product_group", "product_name"]], on="product_code", how="inner"
    )
    sales_frame = sales_frame.loc[sales_frame["business_id"].ne("") & sales_frame["sales_eur"].gt(0)].copy()

    current = current[["business_id", "company_segment"]].dropna(subset=["business_id"]).drop_duplicates("business_id")
    current["business_id"] = current["business_id"].map(normalize_business_id)
    sales_frame = sales_frame.merge(current, on="business_id", how="left")
    global_group_counts = sales_frame.groupby("product_group")["business_id"].nunique()
    global_group_sales = sales_frame.groupby("product_group")["sales_eur"].sum()
    product_sales = sales_frame.groupby(["product_group", "product_code", "product_name"], as_index=False)["sales_eur"].sum()
    examples = (
        product_sales.loc[product_sales["product_code"].str.startswith(("IF", "DIF"))]
        .sort_values(["product_group", "sales_eur", "product_code"], ascending=[True, False, True], kind="mergesort")
        .drop_duplicates("product_group")
        .set_index("product_group")
    )

    results = []
    for row in prospects.itertuples(index=False):
        business_id = normalize_business_id(getattr(row, "business_id", ""))
        segment = getattr(row, "company_segment", "")
        peers = sales_frame.loc[sales_frame["company_segment"].eq(segment)]
        if peers.empty:
            peers = sales_frame
        peer_counts = peers.groupby("product_group")["business_id"].nunique()
        peer_sales = peers.groupby("product_group")["sales_eur"].sum()
        peer_total = float(peer_sales.sum()) or 1.0
        peer_count = max(int(peers["business_id"].nunique()), 1)
        owned = set(sales_frame.loc[sales_frame["business_id"].eq(business_id), "product_group"])
        candidates = pd.DataFrame({"group": peer_counts.index})
        candidates["adoption"] = candidates["group"].map(peer_counts).fillna(0).div(peer_count)
        candidates["sales_share"] = candidates["group"].map(peer_sales).fillna(0).div(peer_total)
        candidates["score"] = 0.70 * candidates["adoption"] + 0.30 * candidates["sales_share"]
        candidates = candidates.loc[~candidates["group"].isin(owned)].sort_values(
            ["score", "adoption", "sales_share", "group"], ascending=[False, False, False, True], kind="mergesort"
        ).head(2)
        selected = []
        for group in candidates["group"]:
            example = examples.loc[group] if group in examples.index else None
            selected.append((
                str(group),
                str(example["product_code"]) if example is not None else "",
                str(example["product_name"]) if example is not None else "",
            ))
        selected += [("", "", "")] * (2 - len(selected))
        results.append({
            "business_id": business_id,
            "Suositus_Tuoteryhma_1": selected[0][0],
            "Suositus_Tuote_Koodi_1": selected[0][1],
            "Suositus_Tuote_1": selected[0][2],
            "Suositus_Tuoteryhma_2": selected[1][0],
            "Suositus_Tuote_Koodi_2": selected[1][1],
            "Suositus_Tuote_2": selected[1][2],
        })

    recommendations = pd.DataFrame(results)
    output = prospects.drop(columns=[column for column in recommendations.columns if column != "business_id" and column in prospects.columns], errors="ignore").merge(recommendations, on="business_id", how="left")
    output.to_csv(args.output, index=False, encoding="utf-8-sig")
    print({
        "output": str(Path(args.output).resolve()),
        "prospect_rows": len(output),
        "recommendation_rows": int(output["Suositus_Tuoteryhma_1"].notna().sum()),
        "example_product_rows": int(output[["Suositus_Tuote_1", "Suositus_Tuote_2"]].notna().sum().sum()),
        "product_master_products": len(master),
        "product_master_groups": int(master["product_group"].nunique()),
    })


if __name__ == "__main__":
    main()
