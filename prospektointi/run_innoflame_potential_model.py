"""Run the current-customer 12-month potential and product recommendation model.

The summary sales input is used for customer-level sales. Product-level sales are
used for product and product-group recommendations because the summary input does
not contain product codes.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


EXCLUDED_TERMS = (
    "kustannus", "cost", "freight", "delivery", "transport", "shipping",
    "pakkauskustannus", "kuljetus", "kuljetuspakkaus", "kuljetuslaatikko",
    "kuljetusalusta", "lava", "rahti", "toimitusmaksu", "käsittelymaksu",
)
DEFAULT_SUMMARY_SALES = Path(__file__).resolve().parent / "sales_import_test" / "GoSystems_sales_26_05_2026_model_input_corrected.csv"
DEFAULT_PRODUCT_SALES = Path(__file__).resolve().parents[1] / "Innoflame_merged_sales.csv"
DEFAULT_PRODUCT_MASTER = Path("C:/Users/TommiHavukainen/Downloads/INNOFLAME-TUOTELISTA-TUOTERYHMITTELY.xlsx")
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs" / "current_customer_potential"


def normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def column(frame: pd.DataFrame, *names: str) -> str | None:
    lookup = {normalized(name): name for name in frame.columns}
    for name in names:
        if normalized(name) in lookup:
            return lookup[normalized(name)]
    return None


def text_series(frame: pd.DataFrame, name: str | None) -> pd.Series:
    if name is None:
        return pd.Series("", index=frame.index, dtype="string")
    return frame[name].fillna("").astype("string").str.strip()


def clean_code(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().upper()


def read_summary_sales(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    account_col = column(frame, "account_id", "accountid", "customer_id")
    date_col = column(frame, "created_year_month", "sold_at", "created_at", "order_date")
    value_col = column(frame, "total_value", "totalprice", "sales", "net_sales")
    if not account_col or not date_col or not value_col:
        raise ValueError("Summary sales must contain account_id, date and total_value columns.")
    result = pd.DataFrame({
        "account_id": pd.to_numeric(frame[account_col], errors="coerce"),
        "sale_date": pd.to_datetime(frame[date_col], errors="coerce"),
        "sales_eur": pd.to_numeric(frame[value_col], errors="coerce").fillna(0.0),
    })
    return result.dropna(subset=["account_id", "sale_date"])


def read_product_sales(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    account_col = column(frame, "accountid", "account_id", "customer_id")
    code_col = column(frame, "productcode", "product_code", "sku", "code")
    name_col = column(frame, "name", "product_name", "title_fi")
    date_col = column(frame, "sold_at", "created_at", "order_date", "created_year_month")
    value_col = column(frame, "sales", "totalprice", "total_value", "net_sales")
    if not account_col or not code_col or not date_col or not value_col:
        raise ValueError("Product sales must contain account, productcode, date and sales columns.")
    result = pd.DataFrame({
        "account_id": pd.to_numeric(frame[account_col], errors="coerce"),
        "product_code": frame[code_col].map(clean_code),
        "product_name": text_series(frame, name_col),
        "description": text_series(frame, column(frame, "description", "description_fi")),
        "sale_date": pd.to_datetime(frame[date_col], errors="coerce"),
        "sales_eur": pd.to_numeric(frame[value_col], errors="coerce").fillna(0.0),
    })
    return result.dropna(subset=["account_id", "sale_date"]).loc[lambda x: x["product_code"].ne("")]


def enrich_product_groups(sales: pd.DataFrame, master_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    master_raw = pd.read_excel(master_path, sheet_name="Tuotteet")
    code_col = column(master_raw, "Tuotekoodi", "ProductCode", "product_code", "code", "sku")
    group_col = column(master_raw, "Koko ryhmäpolku", "ProductGroup", "product_group")
    fallback_group = column(master_raw, "Tuoteryhmä", "product group")
    name_col = column(master_raw, "Tuotteen nimi", "ProductName", "name", "title_fi")
    status_col = column(master_raw, "Tila", "status")
    if not code_col or not (group_col or fallback_group):
        raise ValueError("Product master must contain product code and product group columns.")

    master = pd.DataFrame({
        "product_code": master_raw[code_col].map(clean_code),
        "master_product_name": text_series(master_raw, name_col),
        "product_group": text_series(master_raw, group_col if group_col else fallback_group),
        "product_status": text_series(master_raw, status_col),
    })
    master = master.loc[master["product_code"].ne("")].drop_duplicates("product_code")
    master_text = master[["master_product_name", "product_group"]].agg(" ".join, axis=1).str.lower()
    master["recommendation_excluded"] = master_text.map(lambda value: any(term in value for term in EXCLUDED_TERMS))
    lookup = master.set_index("product_code")
    enriched = sales.copy()
    enriched["product_group"] = ""
    enriched["master_product_name"] = ""
    for _ in range(3):
        missing = enriched["product_group"].eq("")
        enriched.loc[missing, "product_group"] = enriched.loc[missing, "product_code"].map(lookup["product_group"]).fillna("")
        enriched.loc[missing, "master_product_name"] = enriched.loc[missing, "product_code"].map(lookup["master_product_name"]).fillna("")
        if not enriched["product_group"].eq("").sum():
            break

    combined_text = enriched[["product_name", "product_group", "description"]].fillna("").agg(" ".join, axis=1).str.lower()
    enriched["recommendation_excluded"] = combined_text.map(lambda value: any(term in value for term in EXCLUDED_TERMS))
    unmatched = (
        enriched.loc[enriched["product_group"].eq("")]
        .groupby(["product_code", "product_name"], as_index=False)
        .agg(sales_eur=("sales_eur", "sum"), sales_rows=("product_code", "size"))
        .sort_values("sales_eur", ascending=False)
    )
    quality = pd.DataFrame([
        {"metric": "missing_product_groups_before", "value": int(sales["product_code"].map(lookup["product_group"]).fillna("").eq("").sum())},
        {"metric": "missing_product_groups_after", "value": int(enriched["product_group"].eq("").sum())},
        {"metric": "master_fills", "value": int(enriched["product_group"].ne("").sum())},
        {"metric": "unmapped_product_codes", "value": int(unmatched["product_code"].nunique())},
        {"metric": "excluded_product_sales_rows", "value": int(enriched["recommendation_excluded"].sum())},
    ])
    return enriched, master, pd.concat([quality, unmatched.assign(metric="unmapped_product", value=unmatched["product_code"])[["metric", "value"]]], ignore_index=True)


def calculate_scoreboard(summary: pd.DataFrame, sales: pd.DataFrame) -> pd.DataFrame:
    reference_date = max(summary["sale_date"].max(), sales["sale_date"].max())
    current_start = reference_date - pd.DateOffset(months=12)
    previous_start = reference_date - pd.DateOffset(months=24)
    current = summary.loc[summary["sale_date"].gt(current_start)].groupby("account_id")["sales_eur"].sum()
    previous = summary.loc[summary["sale_date"].gt(previous_start) & summary["sale_date"].le(current_start)].groupby("account_id")["sales_eur"].sum()
    active = sales.loc[sales["sale_date"].gt(current_start)].groupby("account_id")["sale_date"].nunique()
    group_sales = sales.loc[~sales["recommendation_excluded"]].groupby(["account_id", "product_group"])["sales_eur"].sum().reset_index()
    group_sales = group_sales.loc[group_sales["product_group"].ne("")]
    adoption = group_sales.groupby("product_group")["account_id"].nunique() / group_sales["account_id"].nunique()
    customer_groups = group_sales.groupby("account_id")["product_group"].agg(set)
    gaps = {}
    for account_id, groups in customer_groups.items():
        gaps[account_id] = float(np.mean([1.0 - adoption.get(group, 0.0) for group in groups])) if groups else 0.0
    accounts = sorted(set(summary["account_id"]) | set(sales["account_id"]))
    result = pd.DataFrame({"account_id": accounts})
    result["CurrentSalesEUR"] = result["account_id"].map(current).fillna(0.0)
    result["PreviousSalesEUR"] = result["account_id"].map(previous).fillna(0.0)
    result["ActiveMonthsLast12"] = result["account_id"].map(active).fillna(0).astype(int)
    result["GroupWhiteSpaceRatio"] = result["account_id"].map(gaps).fillna(0.0)
    result["ActivityRatio"] = (result["ActiveMonthsLast12"] / 12.0).clip(0, 1)
    result["SalesMomentumRatio"] = np.where(result["PreviousSalesEUR"] > 0, result["CurrentSalesEUR"] / result["PreviousSalesEUR"], 1.0)
    growth_rate = (0.10 + 0.25 * result["GroupWhiteSpaceRatio"] + 0.15 * result["ActivityRatio"]).clip(0.10, 0.50)
    result["PotentialSalesNext12MonthsEUR"] = result["CurrentSalesEUR"] * (1.0 + growth_rate)
    result["PotentialGrowthEUR"] = result["PotentialSalesNext12MonthsEUR"] - result["CurrentSalesEUR"]
    result["PotentialGrowthPercent"] = np.where(result["CurrentSalesEUR"] > 0, result["PotentialGrowthEUR"] / result["CurrentSalesEUR"] * 100.0, 0.0)
    result["PotentialScore"] = (100 * (0.55 * result["PotentialGrowthEUR"].rank(pct=True) + 0.25 * result["ActivityRatio"] + 0.20 * result["GroupWhiteSpaceRatio"])).round().clip(1, 100).astype(int)
    result["SalesPriority"] = np.select([result["PotentialScore"].ge(70), result["PotentialScore"].ge(40)], ["High", "Medium"], default="Low")
    result["ReferenceDate"] = reference_date.date().isoformat()
    return result.sort_values(["PotentialGrowthEUR", "CurrentSalesEUR"], ascending=False).reset_index(drop=True)


def build_recommendations(scoreboard: pd.DataFrame, sales: pd.DataFrame, master: pd.DataFrame, max_per_customer: int) -> pd.DataFrame:
    usable = sales.loc[~sales["recommendation_excluded"] & sales["product_group"].ne("")].copy()
    last12 = usable[usable["sale_date"].gt(usable["sale_date"].max() - pd.DateOffset(months=12))]
    customer_total = last12.groupby("account_id")["sales_eur"].sum()
    product_total = usable.groupby("product_code")["sales_eur"].sum()
    product_buyers = usable.groupby("product_code")["account_id"].nunique()
    group_buyers = usable.groupby("product_group")["account_id"].nunique()
    all_buyers = max(1, usable["account_id"].nunique())
    bought = usable.groupby("account_id")["product_code"].agg(set).to_dict()
    group_name = usable.groupby("product_code")["product_group"].first()
    product_name = usable.assign(display_name=usable["product_name"].where(usable["product_name"].ne(""), usable["master_product_name"])).groupby("product_code")["display_name"].first()
    eligible_new = master.loc[
        master["product_code"].str.startswith(("IF", "DIF"), na=False)
        & ~master["recommendation_excluded"]
    ].copy()
    eligible_new["observed_sales_eur"] = eligible_new["product_code"].map(product_total).fillna(0.0)
    eligible_new["group_buyer_count"] = eligible_new["product_group"].map(group_buyers).fillna(0)
    eligible_new = eligible_new.loc[eligible_new["group_buyer_count"].gt(0)]
    eligible_new = eligible_new.sort_values(["group_buyer_count", "observed_sales_eur"], ascending=False).head(250)
    rows: list[dict[str, Any]] = []
    for account_id in scoreboard["account_id"]:
        growth = float(scoreboard.loc[scoreboard["account_id"].eq(account_id), "PotentialGrowthEUR"].iloc[0])
        total = max(float(customer_total.get(account_id, 0.0)), 1.0)
        own = usable.loc[usable["account_id"].eq(account_id)].groupby("product_code")["sales_eur"].sum()
        for code, sales_eur in own.items():
            share = float(sales_eur) / total
            rows.append({"account_id": account_id, "recommendation_type": "Current", "product_code": code, "product_name": product_name.get(code, ""), "product_group": group_name.get(code, ""), "potential_eur": growth * min(0.40, max(0.05, share * 0.75)), "purchase_probability": 1.0, "fit_score": min(1.0, share + 0.25), "explanation": f"Asiakas ostaa tuotetta jo; lisämyyntipotentiaali perustuu omaan ostohistoriaan ja asiakkaan seuraavan 12 kuukauden kasvupotentiaaliin."})
        candidates = eligible_new
        candidates = candidates.loc[~candidates["product_code"].isin(bought.get(account_id, set()))]
        for _, candidate in candidates.iterrows():
            code = candidate["product_code"]
            group = candidate["product_group"]
            popularity = float(product_buyers.get(code, 0)) / all_buyers
            group_fit = float(group_buyers.get(group, 0)) / all_buyers
            fit = 0.65 * group_fit + 0.35 * popularity
            if fit <= 0:
                continue
            rows.append({"account_id": account_id, "recommendation_type": "New", "product_code": code, "product_name": candidate["master_product_name"], "product_group": group, "potential_eur": growth * min(0.25, max(0.01, fit * 0.12)), "purchase_probability": fit, "fit_score": fit, "explanation": f"Tuote ei kuulu asiakkaan ostohistoriaan. Sopivuus perustuu tuoteryhmän vertailuasiakkaiden ostamiseen ({group_fit:.0%}) ja tuotteen yleiseen ostamiseen ({popularity:.0%}); ProductCode täyttää IF/DIF-säännön."})
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result = result.sort_values(["account_id", "recommendation_type", "potential_eur", "fit_score"], ascending=[True, True, False, False])
    result["recommendation_rank"] = result.groupby(["account_id", "recommendation_type"]).cumcount() + 1
    return result.loc[result["recommendation_rank"].le(max_per_customer)].reset_index(drop=True)


def add_top_recommendation_columns(scoreboard: pd.DataFrame, recommendations: pd.DataFrame) -> pd.DataFrame:
    result = scoreboard.copy()
    for kind, prefix in (("Current", "TopCurrentProductRecommendation"), ("New", "TopNewProductRecommendation")):
        subset = recommendations.loc[recommendations["recommendation_type"].eq(kind)]
        for rank in range(1, 4):
            top = subset.loc[subset["recommendation_rank"].eq(rank), ["account_id", "product_code", "potential_eur", "explanation"]].rename(columns={"product_code": f"{prefix}{rank}", "potential_eur": f"{prefix}{rank}PotentialEUR", "explanation": f"{prefix}{rank}Explanation"})
            result = result.merge(top, on="account_id", how="left")
    result["RecommendationExplanation"] = result[[c for c in result.columns if c.endswith("Explanation")]].fillna("").apply(lambda row: " ".join(x for x in row if x), axis=1)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Innoflame current-customer potential and product recommendations.")
    parser.add_argument("--sales-summary", type=Path, default=DEFAULT_SUMMARY_SALES)
    parser.add_argument("--product-sales", type=Path, default=DEFAULT_PRODUCT_SALES)
    parser.add_argument("--product-master", type=Path, default=DEFAULT_PRODUCT_MASTER)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-recommendations-per-customer", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = read_summary_sales(args.sales_summary)
    product_sales = read_product_sales(args.product_sales)
    enriched_sales, master, quality = enrich_product_groups(product_sales, args.product_master)
    scoreboard = calculate_scoreboard(summary, enriched_sales)
    recommendations = build_recommendations(scoreboard, enriched_sales, master, args.max_recommendations_per_customer)
    scoreboard = add_top_recommendation_columns(scoreboard, recommendations)
    top100 = scoreboard.head(100).copy()
    if recommendations.empty:
        top_if = top_dif = pd.DataFrame()
    else:
        product_summary = recommendations.groupby(["recommendation_type", "product_code", "product_name", "product_group"], as_index=False).agg(total_potential_eur=("potential_eur", "sum"), customers=("account_id", "nunique"), avg_purchase_probability=("purchase_probability", "mean"))
        top_if = product_summary.loc[(product_summary["recommendation_type"].eq("New")) & product_summary["product_code"].str.startswith("IF")].sort_values("total_potential_eur", ascending=False).head(10)
        top_dif = product_summary.loc[(product_summary["recommendation_type"].eq("New")) & product_summary["product_code"].str.startswith("DIF")].sort_values("total_potential_eur", ascending=False).head(10)
    summary_report = pd.DataFrame([
        {"metric": "customer_count", "value": len(scoreboard)},
        {"metric": "total_current_sales_eur", "value": scoreboard["CurrentSalesEUR"].sum()},
        {"metric": "total_potential_next_12_months_eur", "value": scoreboard["PotentialSalesNext12MonthsEUR"].sum()},
        {"metric": "total_potential_growth_eur", "value": scoreboard["PotentialGrowthEUR"].sum()},
        {"metric": "high_priority_customers", "value": int(scoreboard["SalesPriority"].eq("High").sum())},
        {"metric": "new_recommendation_rows", "value": int(recommendations["recommendation_type"].eq("New").sum()) if not recommendations.empty else 0},
    ])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    scoreboard.to_csv(args.output_dir / "customer_scoreboard.csv", index=False, encoding="utf-8-sig")
    top100.to_csv(args.output_dir / "top_100_customers.csv", index=False, encoding="utf-8-sig")
    recommendations.to_csv(args.output_dir / "product_recommendations.csv", index=False, encoding="utf-8-sig")
    quality.to_csv(args.output_dir / "data_quality.csv", index=False, encoding="utf-8-sig")
    summary_report.to_csv(args.output_dir / "portfolio_summary.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(args.output_dir / "innoflame_potential_model.xlsx", engine="openpyxl") as writer:
        scoreboard.to_excel(writer, sheet_name="customer_scoreboard", index=False)
        top100.to_excel(writer, sheet_name="top_100_customers", index=False)
        recommendations.to_excel(writer, sheet_name="recommendations", index=False)
        top_if.to_excel(writer, sheet_name="top_10_IF", index=False)
        top_dif.to_excel(writer, sheet_name="top_10_DIF", index=False)
        summary_report.to_excel(writer, sheet_name="portfolio_summary", index=False)
        quality.to_excel(writer, sheet_name="data_quality", index=False)
    print({"output_dir": str(args.output_dir), "customers": len(scoreboard), "recommendations": len(recommendations), "potential_growth_eur": round(float(scoreboard["PotentialGrowthEUR"].sum()), 2)})


if __name__ == "__main__":
    main()
