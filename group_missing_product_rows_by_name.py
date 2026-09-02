import json
import os
import re
from collections import Counter
from datetime import datetime

import pandas as pd


BASE_DIR = r"C:\Users\TommiHavukainen\OneDrive - Unikie Oy\Customer\Innoflame"
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
SALES_CSV = os.path.join(
    OUTPUT_DIR, "Innoflame_merged_sales_csv_source_with_L1_L2_L3_delivery_handling.csv"
)
OUT_CSV = os.path.join(OUTPUT_DIR, "missing_product_groups_by_name_current.csv")
OUT_JSON = os.path.join(OUTPUT_DIR, "missing_product_groups_by_name_current_summary.json")


def has_group(df):
    return (
        df["product_group_l3_code"].notna()
        & (df["product_group_l3_code"].astype(str).str.strip() != "")
        & df["product_group_l3_name"].notna()
        & (df["product_group_l3_name"].astype(str).str.strip() != "")
    )


def norm_text(value):
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = text.replace("-", " ")
    text = re.sub(r"(?<=\d)\s*x\s*(?=\d)", "x", text)
    text = re.sub(r"\s+", " ", text)
    return text


def sample_values(values, max_items=8):
    cleaned = []
    for value in values:
        if pd.isna(value):
            continue
        text = str(value).strip()
        if not text or text.lower() == "nan":
            continue
        cleaned.append(text)
    return " | ".join(list(dict.fromkeys(cleaned))[:max_items])


KEYWORD_GROUPS = [
    ("takki", "01.05.03 Takit"),
    ("tikkitakki", "01.05.03 Takit"),
    ("softshell", "01.05.03 Takit"),
    ("kuoritakki", "01.05.03 Takit"),
    ("pyyhe", "03.03.03 Pyyhkeet ja laudeliinat"),
    ("kylpypyyhe", "03.03.03 Pyyhkeet ja laudeliinat"),
    ("saunapyyhe", "03.03.03 Pyyhkeet ja laudeliinat"),
    ("muki", "03.01.01 Mukit"),
    ("juomapullo", "03.01.05 Pullot"),
    ("pullo", "03.01.05 Pullot"),
    ("pipo", "01.01.06 Pipot"),
    ("lippalakki", "01.01.04 Lippalakit"),
    ("huppari", "01.04.01 Hupparit ja colleget"),
    ("college", "01.04.01 Hupparit ja colleget"),
    ("kassi", "05.01.01 Muut kassit"),
    ("reppu", "05.02.01 Muut reput"),
    ("kaulanauha", "02.01.03 Kaulanauhat"),
    ("avainnauha", "02.01.03 Kaulanauhat"),
    ("avaimenperä", "02.01.01 Avaimenperät"),
    ("heijastin", "02.01.02 Heijastimet"),
    ("latauskaapeli", "11.06.01 Laturit ja kaapelit"),
    ("kaiutin", "11.01.01 Kaiuttimet"),
    ("kuulokkeet", "11.01.02 Kuulokkeet"),
]


def suggest_group(name):
    normalized = norm_text(name)
    for keyword, group in KEYWORD_GROUPS:
        if re.search(r"(?<![a-zåäö])" + re.escape(keyword) + r"(?![a-zåäö])", normalized):
            return keyword, group
    return "", ""


def main():
    df = pd.read_csv(SALES_CSV, low_memory=False)
    missing = df[~has_group(df)].copy()
    missing["sales_numeric"] = pd.to_numeric(missing["sales"], errors="coerce").fillna(0)
    missing["name_normalized"] = missing["name"].map(norm_text)

    rows = []
    for name, group in missing.groupby("name", dropna=False, sort=False):
        keyword, suggested_group = suggest_group(name)
        rows.append(
            {
                "name": "" if pd.isna(name) else name,
                "name_normalized": norm_text(name),
                "row_count": int(len(group)),
                "sales_sum_eur": round(float(group["sales_numeric"].sum()), 2),
                "unique_productcode_count": int(
                    group["productcode"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().nunique()
                ),
                "missing_productcode_rows": int(
                    group["productcode"].isna().sum()
                    + (group["productcode"].astype(str).str.strip() == "").sum()
                ),
                "example_productcodes": sample_values(group["productcode"]),
                "example_optioncodes": sample_values(group["optioncode"]),
                "example_categories": sample_values(group["category"]),
                "example_references": sample_values(group["reference"]),
                "suggested_keyword": keyword,
                "suggested_group_from_keyword": suggested_group,
            }
        )

    out = pd.DataFrame(rows)
    out = out.sort_values(["row_count", "sales_sum_eur"], ascending=[False, False])
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    top_keywords = Counter(out.loc[out["suggested_keyword"] != "", "suggested_keyword"])
    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_csv": SALES_CSV,
        "rows_missing_group": int(len(missing)),
        "unique_names_missing_group": int(out["name"].nunique(dropna=False)),
        "output_csv": OUT_CSV,
        "top_20_names": out.head(20).to_dict("records"),
        "names_with_keyword_suggestion": int((out["suggested_keyword"] != "").sum()),
        "top_suggested_keywords_by_name_count": dict(top_keywords.most_common(20)),
    }
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
