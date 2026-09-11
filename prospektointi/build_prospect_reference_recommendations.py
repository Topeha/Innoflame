"""Build customer references and product-group recommendations for prospects.

The script is a post-processing model. Existing prospect score, potential,
segment, and rank columns are copied unchanged.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROSPECTS = ROOT / "prospektointi" / "prospect_segment_model_all_prospects_final_with_product_recommendations_without_netvisor_parent.csv"
DEFAULT_CURRENT = ROOT / "potentiaali" / "current_customer_potential_new_sources.csv"
DEFAULT_PROFINDER = ROOT / "potentiaali" / "haku_Prospektointimasterlista_2026-08-12.xlsx"
DEFAULT_ACCOUNTS = ROOT / "potentiaali" / "Account_20.05.2026_combined_with_profinder_working_copy.xlsx"
DEFAULT_SALES = ROOT / "outputs" / "Innoflame_merged_sales_csv_source_with_L1_L2_L3_delivery_handling.csv"
DEFAULT_PRODUCT_MASTER = ROOT / "tuoteryhmittely" / "INNOFLAME-TUOTELISTA-TUOTERYHMITTELY.xlsx"


def normalize_business_id(value: object) -> str:
    if pd.isna(value):
        return ""
    digits = "".join(character for character in str(value).upper().replace("FI", "") if character.isdigit())
    if len(digits) == 7:
        digits = "0" + digits
    return f"{digits[:-1]}-{digits[-1]}" if len(digits) >= 8 else ""


def number(value: object) -> float:
    if pd.isna(value):
        return 0.0
    return float(pd.to_numeric(str(value).replace(",", "."), errors="coerce") or 0.0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build prospect customer references and product recommendations.")
    parser.add_argument("--prospects", default=str(DEFAULT_PROSPECTS))
    parser.add_argument("--current-customers", default=str(DEFAULT_CURRENT))
    parser.add_argument("--profinder", default=str(DEFAULT_PROFINDER))
    parser.add_argument("--accounts", default=str(DEFAULT_ACCOUNTS))
    parser.add_argument("--sales", default=str(DEFAULT_SALES))
    parser.add_argument("--product-master", default=str(DEFAULT_PRODUCT_MASTER))
    parser.add_argument("--output", default=str(ROOT / "prospektointi" / "prospect_segment_model_final_with_references.csv"))
    return parser.parse_args()


def load_profiles(path: str, profinder: pd.DataFrame) -> pd.DataFrame:
    frame = pd.read_csv(path, sep=None, engine="python", dtype=str)
    frame.columns = [str(column).lstrip("\ufeff") for column in frame.columns]
    frame["business_id"] = frame["business_id"].map(normalize_business_id)
    prof = profinder.copy()
    prof["business_id"] = prof["Y-tunnus"].map(normalize_business_id)
    prof = prof.drop_duplicates("business_id")
    prof = prof.rename(columns={
        "Kunta": "municipality",
        "Maakunta": "region",
        "Henkilöstö": "headcount",
        "Liikevaihdon muutos (prosenttia)": "growth_pct",
        "Päätoimiala (Profinder)": "industry_profinder",
        "Virallinen nimi": "profinder_company",
    })
    keep = [column for column in ["business_id", "municipality", "region", "headcount", "growth_pct", "industry_profinder", "profinder_company"] if column in prof.columns]
    frame = frame.merge(prof[keep], on="business_id", how="left")
    frame["revenue_k_eur"] = pd.to_numeric(frame.get("revenue_k_eur", 0), errors="coerce")
    frame["headcount"] = pd.to_numeric(frame.get("headcount", 0), errors="coerce")
    frame["growth_pct"] = pd.to_numeric(frame.get("growth_pct", 0), errors="coerce")
    frame["industry"] = frame.get("industry", frame.get("industry_profinder", "")).fillna(frame.get("industry_profinder", ""))
    frame["revenue_per_employee"] = np.where(frame["headcount"].gt(0), frame["revenue_k_eur"] * 1000 / frame["headcount"], np.nan)
    for column in ["industry", "headcount_class", "company_segment", "growth_bucket", "municipality", "region"]:
        if column not in frame.columns:
            frame[column] = "unknown"
        frame[column] = frame[column].fillna("unknown").astype(str).replace("", "unknown")
    return frame


def build_sales_groups(sales_path: str, accounts_path: str, product_master_path: str) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    sales = pd.read_csv(sales_path, sep=None, engine="python", dtype=str)
    sales.columns = [str(column).lstrip("\ufeff") for column in sales.columns]
    account_col = "accountid" if "accountid" in sales.columns else "account_id"
    product_col = next(column for column in ("productcode", "ProductCode", "sku") if column in sales.columns)
    value_col = "sales" if "sales" in sales.columns else "total_value"
    accounts = pd.read_excel(accounts_path, dtype=str)
    account_id_col = "ID" if "ID" in accounts.columns else "account_id"
    business_col = next(column for column in accounts.columns if str(column).strip().casefold() in {"business id", "business_id", "y-tunnus", "y tunnus"})
    keys = accounts[[account_id_col, business_col]].copy()
    keys.columns = ["account_id", "business_id"]
    keys["account_id"] = pd.to_numeric(keys["account_id"], errors="coerce")
    keys["business_id"] = keys["business_id"].map(normalize_business_id)
    master = pd.read_excel(product_master_path, sheet_name="Tuotteet", dtype=str)
    master["product_code"] = master["Tuotekoodi"].map(lambda value: "" if pd.isna(value) else str(value).strip().upper())
    master["product_group"] = master["Tuoteryhmä"].fillna("").astype(str).str.strip()
    master["product_name"] = master["Tuotteen nimi"].fillna("").astype(str).str.strip()
    master = master.loc[master["product_code"].ne("") & master["product_group"].ne("")].drop_duplicates("product_code")
    frame = sales[[account_col, product_col, value_col]].copy()
    frame.columns = ["account_id", "product_code", "sales_eur"]
    frame["account_id"] = pd.to_numeric(frame["account_id"], errors="coerce")
    frame["product_code"] = frame["product_code"].map(lambda value: "" if pd.isna(value) else str(value).strip().upper())
    frame["sales_eur"] = frame["sales_eur"].map(number)
    frame = frame.merge(keys, on="account_id", how="left").merge(master[["product_code", "product_group", "product_name"]], on="product_code", how="inner")
    frame = frame.loc[frame["business_id"].ne("") & frame["sales_eur"].gt(0)].copy()
    top_groups = {}
    grouped = frame.groupby(["business_id", "product_group"], as_index=False)["sales_eur"].sum()
    for business_id, part in grouped.groupby("business_id"):
        top_groups[business_id] = part.sort_values(["sales_eur", "product_group"], ascending=[False, True]).head(3)["product_group"].tolist()
    return frame, top_groups


def main() -> None:
    args = parse_args()
    profinder = pd.read_excel(args.profinder, dtype=str)
    prospects = load_profiles(args.prospects, profinder)
    current = load_profiles(args.current_customers, profinder)
    current = current.drop_duplicates("business_id")
    sales_groups, top_groups = build_sales_groups(args.sales, args.accounts, args.product_master)
    sales_groups = sales_groups.merge(current[["business_id", "company_segment"]], on="business_id", how="left")
    current["annual_sales"] = pd.to_numeric(current.get("avg_annual_sales_3y_eur", 0), errors="coerce").fillna(0.0)
    current["annual_sales"] = current["annual_sales"].where(
        current["annual_sales"].gt(0),
        current["business_id"].map(sales_groups.groupby("business_id")["sales_eur"].sum()).fillna(0.0) / 3.0,
    )
    current["group_count"] = current["business_id"].map(sales_groups.groupby("business_id")["product_group"].nunique()).fillna(0)

    numeric = ["revenue_k_eur", "headcount", "revenue_per_employee", "growth_pct"]
    categorical = ["industry", "headcount_class", "company_segment", "growth_bucket", "municipality", "region"]
    combined = pd.concat([current[numeric + categorical], prospects[numeric + categorical]], ignore_index=True)
    transformer = ColumnTransformer([
        ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), numeric),
        ("categorical", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), categorical),
    ])
    matrix = transformer.fit_transform(combined)
    current_matrix = matrix[: len(current)]
    prospect_matrix = matrix[len(current):]
    similarities = cosine_similarity(prospect_matrix, current_matrix)
    max_sales = max(float(current["annual_sales"].max()), 1.0)
    max_groups = max(float(current["group_count"].max()), 1.0)
    records = []
    for prospect_index, prospect in prospects.reset_index(drop=True).iterrows():
        order = np.argsort(-similarities[prospect_index])[:10]
        rows = []
        for customer_index in order:
            similarity = float(np.clip(similarities[prospect_index, customer_index], 0.0, 1.0))
            customer = current.iloc[customer_index]
            reference_score = 0.60 * similarity + 0.25 * float(customer["annual_sales"]) / max_sales + 0.15 * float(customer["group_count"]) / max_groups
            rows.append((reference_score, similarity, customer))
        rows.sort(key=lambda value: (-value[0], -value[1], str(value[2]["company"])))
        selected = rows[:3]
        group_scores: dict[str, float] = {}
        for _, similarity, customer in rows:
            for group in top_groups.get(customer["business_id"], []):
                group_scores[group] = group_scores.get(group, 0.0) + similarity
        recommended = sorted(group_scores.items(), key=lambda item: (-item[1], item[0]))[:5]
        record = {"business_id": prospect["business_id"]}
        for slot in range(3):
            if slot < len(selected):
                score, similarity, customer = selected[slot]
                record[f"reference_company_{slot + 1}"] = customer.get("company", customer.get("profinder_company", ""))
                record[f"reference_company_{slot + 1}_similarity"] = round(similarity, 6)
                record[f"reference_company_{slot + 1}_score"] = round(score, 6)
                record[f"reference_company_{slot + 1}_top_products"] = " | ".join(top_groups.get(customer["business_id"], []))
            else:
                record[f"reference_company_{slot + 1}"] = ""
                record[f"reference_company_{slot + 1}_similarity"] = ""
                record[f"reference_company_{slot + 1}_score"] = ""
                record[f"reference_company_{slot + 1}_top_products"] = ""
        for slot in range(5):
            if slot < len(recommended):
                group, score = recommended[slot]
                record[f"recommended_product_group_{slot + 1}"] = group
                record[f"recommended_product_group_{slot + 1}_score"] = round(score, 6)
            else:
                record[f"recommended_product_group_{slot + 1}"] = ""
                record[f"recommended_product_group_{slot + 1}_score"] = ""
        names = [record[f"reference_company_{slot}"] for slot in range(1, 4) if record[f"reference_company_{slot}"]]
        groups = [record[f"recommended_product_group_{slot}"] for slot in range(1, 6) if record[f"recommended_product_group_{slot}"]]
        record["sales_explanation"] = (
            f"Yritys muistuttaa erityisesti yrityksiä {', '.join(names)}. "
            f"Vastaavan profiilin asiakkaiden ostetuimmat tuoteryhmät ovat {', '.join(groups[:3])}."
            if names and groups else "Vertailuryhmälle ei löytynyt riittävästi ostohistoriaa."
        )
        records.append(record)
    recommendations = pd.DataFrame(records)
    output = prospects.merge(recommendations, on="business_id", how="left")
    output.to_csv(args.output, index=False, encoding="utf-8-sig")
    print({"output": str(Path(args.output).resolve()), "prospect_rows": len(output), "current_customer_rows": len(current), "reference_rows": len(records), "product_group_rows": len(sales_groups)})


if __name__ == "__main__":
    main()
