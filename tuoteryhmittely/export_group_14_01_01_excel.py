from pathlib import Path

import pandas as pd
from openpyxl.utils import get_column_letter


SOURCE = Path("product_master_enrichment/final_product_grouping/products_product_group_tree_feedback_3level.csv")
SUGGESTIONS = Path("outputs/product_grouping_summary/tarkistettavat_ryhma_luokitteluehdotukset.csv")
OUT_DIR = Path("outputs/product_grouping_summary")
OUT_XLSX = OUT_DIR / "tuoteryhma_14_01_01_tarkistettavat.xlsx"
OUT_CSV = OUT_DIR / "tuoteryhma_14_01_01_tarkistettavat.csv"


def autosize_worksheet(ws):
    ws.freeze_panes = "A2"
    for column_cells in ws.columns:
        col_letter = get_column_letter(column_cells[0].column)
        values = [str(cell.value) for cell in column_cells[:200] if cell.value is not None]
        width = min(max([len(v) for v in values] + [12]) + 2, 55)
        ws.column_dimensions[col_letter].width = width


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    products = pd.read_csv(SOURCE, dtype=str, keep_default_na=False, low_memory=False)
    group = products[products["product_group_l3_code"].eq("14.01.01")].copy()

    if SUGGESTIONS.exists():
        suggestions = pd.read_csv(SUGGESTIONS, dtype=str, keep_default_na=False, low_memory=False)
        suggestion_cols = ["code", "suggested_path", "confidence", "reason"]
        group = group.merge(
            suggestions[suggestion_cols].drop_duplicates("code"),
            on="code",
            how="left",
        )
    else:
        group["suggested_path"] = ""
        group["confidence"] = ""
        group["reason"] = ""

    preferred_cols = [
        "code",
        "product_name",
        "title_fi",
        "description_fi",
        "brand_name",
        "inventory_supplier",
        "product_group_l1_code",
        "product_group_l1_name",
        "product_group_l2_code",
        "product_group_l2_name",
        "product_group_l3_code",
        "product_group_l3_name",
        "product_group_path_name",
        "suggested_path",
        "confidence",
        "reason",
    ]
    ordered_cols = [c for c in preferred_cols if c in group.columns]
    ordered_cols += [c for c in group.columns if c not in ordered_cols]
    group = group[ordered_cols]

    group.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    path_name = ""
    if not group.empty and "product_group_path_name" in group.columns:
        path_name = group["product_group_path_name"].mode().iat[0]

    summary = pd.DataFrame(
        [
            ["Tuoteryhmäkoodi", "14.01.01"],
            ["Tuoteryhmä", "Tarkistettavat / tarkistettavat"],
            ["Polku", path_name],
            ["Tuotteita", len(group)],
            ["Korkean varmuuden ehdotuksia", int(group["confidence"].eq("high").sum())],
            ["Keskivarman tason ehdotuksia", int(group["confidence"].eq("medium").sum())],
            ["Manuaalisesti tarkistettavia / ilman ehdotusta", int(group["confidence"].eq("manual").sum() + group["confidence"].eq("").sum())],
        ],
        columns=["Mittari", "Arvo"],
    )

    suggestion_summary = (
        group.groupby(["confidence", "suggested_path", "reason"], dropna=False)
        .size()
        .reset_index(name="product_count")
        .sort_values(["confidence", "product_count"], ascending=[True, False])
    )

    suggested_moves = group[group["confidence"].isin(["high", "medium"])].copy()

    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Yhteenveto", index=False)
        suggestion_summary.to_excel(writer, sheet_name="Ehdotusten_yhteenveto", index=False)
        group.to_excel(writer, sheet_name="Tuotteet", index=False)
        suggested_moves.to_excel(writer, sheet_name="Ehdotetut_siirrot", index=False)

        for worksheet in writer.book.worksheets:
            autosize_worksheet(worksheet)

    print(f"Excel: {OUT_XLSX}")
    print(f"CSV: {OUT_CSV}")
    print(f"Rows: {len(group)}")


if __name__ == "__main__":
    main()
