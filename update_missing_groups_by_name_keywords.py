import json
import os
import re
import shutil
from collections import Counter
from datetime import datetime

import pandas as pd


BASE_DIR = r"C:\Users\TommiHavukainen\OneDrive - Unikie Oy\Customer\Innoflame"
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
CSV_PATH = os.path.join(
    OUTPUT_DIR, "Innoflame_merged_sales_csv_source_with_L1_L2_L3_delivery_handling.csv"
)

GROUP_COLS = [
    "product_group_l1_code",
    "product_group_l1_name",
    "product_group_l2_code",
    "product_group_l2_name",
    "product_group_l3_code",
    "product_group_l3_name",
]

RULES = [
    ("tikkitakki", ("1", "Vaatteet", "01.05", "Takit ja liivit", "01.05.03", "Takit")),
    ("softshell takki", ("1", "Vaatteet", "01.05", "Takit ja liivit", "01.05.03", "Takit")),
    ("softshelltakki", ("1", "Vaatteet", "01.05", "Takit ja liivit", "01.05.03", "Takit")),
    ("kuoritakki", ("1", "Vaatteet", "01.05", "Takit ja liivit", "01.05.03", "Takit")),
    ("fleecetakki", ("1", "Vaatteet", "01.05", "Takit ja liivit", "01.05.03", "Takit")),
    ("sadetakki", ("1", "Vaatteet", "01.05", "Takit ja liivit", "01.05.03", "Takit")),
    ("talvitakki", ("1", "Vaatteet", "01.05", "Takit ja liivit", "01.05.03", "Takit")),
    ("takki", ("1", "Vaatteet", "01.05", "Takit ja liivit", "01.05.03", "Takit")),
    ("kylpypyyhe", ("3", "Koti ja keittiö", "03.03", "Kodintekstiilit", "03.03.03", "Pyyhkeet ja laudeliinat")),
    ("saunapyyhe", ("3", "Koti ja keittiö", "03.03", "Kodintekstiilit", "03.03.03", "Pyyhkeet ja laudeliinat")),
    ("keittiöpyyhe", ("3", "Koti ja keittiö", "03.03", "Kodintekstiilit", "03.03.03", "Pyyhkeet ja laudeliinat")),
    ("pyyhe", ("3", "Koti ja keittiö", "03.03", "Kodintekstiilit", "03.03.03", "Pyyhkeet ja laudeliinat")),
    ("laudeliina", ("3", "Koti ja keittiö", "03.03", "Kodintekstiilit", "03.03.03", "Pyyhkeet ja laudeliinat")),
    ("tupsupipo", ("1", "Vaatteet", "01.01", "Asusteet", "01.01.06", "Pipot")),
    ("pipo", ("1", "Vaatteet", "01.01", "Asusteet", "01.01.06", "Pipot")),
    ("lippalakki", ("1", "Vaatteet", "01.01", "Asusteet", "01.01.04", "Lippalakit")),
    ("huppari", ("1", "Vaatteet", "01.04", "Paidat ja yläosat", "01.04.01", "Hupparit ja colleget")),
    ("college", ("1", "Vaatteet", "01.04", "Paidat ja yläosat", "01.04.01", "Hupparit ja colleget")),
    ("colleget", ("1", "Vaatteet", "01.04", "Paidat ja yläosat", "01.04.01", "Hupparit ja colleget")),
    ("juomapullo", ("3", "Koti ja keittiö", "03.01", "Juoma-astiat", "03.01.05", "Pullot")),
    ("vesipullo", ("3", "Koti ja keittiö", "03.01", "Juoma-astiat", "03.01.05", "Pullot")),
    ("termos", ("3", "Koti ja keittiö", "03.01", "Juoma-astiat", "03.01.05", "Pullot")),
    ("muki", ("3", "Koti ja keittiö", "03.01", "Juoma-astiat", "03.01.01", "Mukit")),
    ("kaulanauha", ("2", "Promootio- ja tapahtumatuotteet", "02.01", "Jakotuotteet", "02.01.03", "Kaulanauhat")),
    ("avainnauha", ("2", "Promootio- ja tapahtumatuotteet", "02.01", "Jakotuotteet", "02.01.03", "Kaulanauhat")),
    ("avaimenperä", ("2", "Promootio- ja tapahtumatuotteet", "02.01", "Jakotuotteet", "02.01.01", "Avaimenperät")),
    ("heijastin", ("2", "Promootio- ja tapahtumatuotteet", "02.01", "Jakotuotteet", "02.01.02", "Heijastimet")),
    ("latauskaapeli", ("11", "Elektroniikka", "11.06", "Virta ja lataus", "11.06.01", "Laturit ja kaapelit")),
    ("kaapeli", ("11", "Elektroniikka", "11.06", "Virta ja lataus", "11.06.01", "Laturit ja kaapelit")),
    ("kaiutin", ("11", "Elektroniikka", "11.01", "Audio", "11.01.01", "Kaiuttimet")),
    ("kuulokkeet", ("11", "Elektroniikka", "11.01", "Audio", "11.01.02", "Kuulokkeet")),
    ("puuvillakassi", ("5", "Laukut ja matkatavarat", "05.01", "Kassit", "05.01.01", "Muut kassit")),
    ("ostoskassi", ("5", "Laukut ja matkatavarat", "05.01", "Kassit", "05.01.01", "Muut kassit")),
    ("kassi", ("5", "Laukut ja matkatavarat", "05.01", "Kassit", "05.01.01", "Muut kassit")),
    ("retkeilyreppu", ("5", "Laukut ja matkatavarat", "05.02", "Reput", "05.02.01", "Muut reput")),
    ("reppu", ("5", "Laukut ja matkatavarat", "05.02", "Reput", "05.02.01", "Muut reput")),
]


def has_group(df):
    return (
        df["product_group_l3_code"].notna()
        & (df["product_group_l3_code"].astype(str).str.strip() != "")
        & df["product_group_l3_name"].notna()
        & (df["product_group_l3_name"].astype(str).str.strip() != "")
    )


def normalize_name(value):
    if pd.isna(value):
        return ""
    text = str(value).lower()
    # Some legacy exports have mojibake in console output; keep this harmless normalizer.
    text = text.replace("�", "ä")
    text = text.replace("-", " ")
    text = re.sub(r"(?<=\d)\s*x\s*(?=\d)", "x", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def matches_word(normalized_name, word):
    pattern = r"(?<![a-zåäö])" + re.escape(word) + r"(?![a-zåäö])"
    return re.search(pattern, normalized_name) is not None


def find_rule(normalized_name):
    for word, group in RULES:
        if matches_word(normalized_name, word):
            return word, group
    return None, None


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_csv = CSV_PATH.replace(
        ".csv", f".backup_before_name_keyword_grouping_{timestamp}.csv"
    )
    audit_csv = os.path.join(OUTPUT_DIR, "name_keyword_grouping_update_rows.csv")
    audit_json = os.path.join(OUTPUT_DIR, "name_keyword_grouping_update_audit.json")

    shutil.copy2(CSV_PATH, backup_csv)
    df = pd.read_csv(CSV_PATH, low_memory=False)

    missing_before = ~has_group(df)
    audit_rows = []
    word_counts = Counter()
    group_counts = Counter()

    for idx in df.index[missing_before]:
        word, group = find_rule(normalize_name(df.at[idx, "name"]))
        if not group:
            continue
        for col, value in zip(GROUP_COLS, group):
            df.at[idx, col] = value
        df.at[idx, "product_group_match_method"] = "manual_name_keyword_rule"
        word_counts[word] += 1
        group_counts[group[5]] += 1
        audit_rows.append(
            {
                "csv_row_number": int(idx) + 2,
                "matched_keyword": word,
                "source_file": df.at[idx, "source_file"],
                "id": df.at[idx, "id"],
                "category": df.at[idx, "category"],
                "productcode": df.at[idx, "productcode"],
                "optioncode": df.at[idx, "optioncode"],
                "name": df.at[idx, "name"],
                "sales": df.at[idx, "sales"],
                "reference": df.at[idx, "reference"],
                **{col: df.at[idx, col] for col in GROUP_COLS},
            }
        )

    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
    pd.DataFrame(audit_rows).to_csv(audit_csv, index=False, encoding="utf-8-sig")

    missing_after = ~has_group(df)
    audit = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "source_csv": CSV_PATH,
        "backup_csv": backup_csv,
        "updated_rows": len(audit_rows),
        "missing_group_rows_before": int(missing_before.sum()),
        "missing_group_rows_after": int(missing_after.sum()),
        "updated_sales_eur": float(
            pd.to_numeric(pd.DataFrame(audit_rows).get("sales", pd.Series(dtype=float)), errors="coerce")
            .fillna(0)
            .sum()
        ),
        "rows_by_keyword": dict(word_counts.most_common()),
        "rows_by_group": dict(group_counts.most_common()),
        "audit_rows_csv": audit_csv,
    }
    with open(audit_json, "w", encoding="utf-8") as fh:
        json.dump(audit, fh, ensure_ascii=False, indent=2)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
