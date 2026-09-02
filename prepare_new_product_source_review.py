from __future__ import annotations

import csv
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_ZIP = Path(r"C:\Users\TommiHavukainen\Downloads\products.zip")
OUTPUT_ROOT = ROOT / "outputs" / "uusi_tuoteryhmittelylahde"

CURRENT_GROUPING_FILES = [
    ROOT / "outputs" / "Innoflame_merged_sales_csv_source_with_L1_L2_L3_delivery_handling.csv",
    ROOT / "outputs" / "Innoflame_merged_sales_csv_source_with_L1_L2_L3_delivery_handling.xlsx",
    ROOT / "outputs" / "Innoflame_merged_sales_csv_source_full_audit.json",
    ROOT / "outputs" / "Innoflame_merged_sales_csv_source_full_audit.xlsx",
    ROOT / "outputs" / "Innoflame_unmatched_product_groups_by_name.csv",
    ROOT / "outputs" / "Innoflame_unmatched_product_groups_by_name.xlsx",
    ROOT / "outputs" / "Innoflame_tuoteryhmittely_kooste.pptx",
    ROOT / "outputs" / "Innoflame_tuoteryhmittely_menetelmadokumentti.docx",
]


def copy_if_exists(src: Path, dst_dir: Path) -> dict[str, object]:
    row: dict[str, object] = {
        "source": str(src),
        "target": "",
        "exists": src.exists(),
        "size_bytes": "",
    }
    if src.exists():
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / src.name
        shutil.copy2(src, dst)
        row["target"] = str(dst)
        row["size_bytes"] = src.stat().st_size
    return row


def inspect_zip(path: Path) -> dict[str, object]:
    info: dict[str, object] = {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "is_zip": False,
        "member_count": 0,
        "members": [],
        "status": "missing",
    }
    if not path.exists():
        return info
    info["is_zip"] = zipfile.is_zipfile(path)
    if not info["is_zip"]:
        info["status"] = "not_a_zip"
        return info
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
    info["member_count"] = len(names)
    info["members"] = names
    info["status"] = "empty_zip" if not names else "ready_for_extraction"
    return info


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_ROOT / f"ajo_{timestamp}"
    backup_dir = run_dir / "00_vanha_tuoteryhmittely_sailytetty"
    incoming_dir = run_dir / "01_uusi_lahde"
    incoming_dir.mkdir(parents=True, exist_ok=True)

    backup_rows = [copy_if_exists(path, backup_dir) for path in CURRENT_GROUPING_FILES]
    source_copy = copy_if_exists(SOURCE_ZIP, incoming_dir)
    zip_info = inspect_zip(SOURCE_ZIP)

    write_csv(run_dir / "vanhan_tuoteryhmittelyn_varmuuskopiot.csv", backup_rows)

    plan_lines = [
        "Uuden tuoteryhmittelylähteen käsittelysuunnitelma",
        "",
        "Periaate: nykyistä tuoteryhmittelyä ei ylikirjoiteta. Kaikki uuden lähteen käsittely tehdään erillisessä ajokansiossa, ja nykyinen tuoteryhmittely on kopioitu talteen ennen jatkotoimia.",
        "",
        "1. Säilytä nykyinen tuoteryhmittely",
        "- Nykyinen Innoflame_merged_sales_csv_source_with_L1_L2_L3_delivery_handling.csv ja .xlsx on kopioitu kansioon 00_vanha_tuoteryhmittely_sailytetty.",
        "- Myös nykyinen PPT-kooste ja menetelmädokumentti on kopioitu samaan turvakansioon, jos tiedostot löytyivät.",
        "",
        "2. Tarkista uusi lähde",
        f"- Lähde: {SOURCE_ZIP}",
        f"- Tila: {zip_info['status']}",
        f"- Zipin koko: {zip_info['size_bytes']} tavua",
        f"- Tiedostoja zipissä: {zip_info['member_count']}",
        "",
        "3. Kun oikea lähde on saatavilla",
        "- pura zip erilliseen 01_uusi_lahde-kansioon",
        "- tunnista päätuotteet ja variantit",
        "- kartoita kentät: id, productid, code, sku, vendorcode, title_fi, description_fi, searchdata ja mahdolliset kategoriakentät",
        "- vertaa uutta lähdettä nykyiseen tuoteryhmittelyyn product_id/code-avaimilla",
        "- tee muutosraportti ennen mitään päivitystä",
        "- päivitä tuoteryhmittely vasta hyväksyttävien high-varmuuden ehdotusten perusteella",
        "- säilytä vanha tuoteryhmittely aina varmuuskopiona ja kirjoita uusi tulos uudella nimellä tai erilliseen versioon",
        "",
        "Huomio",
        "Nykyinen products.zip on tyhjä zip-arkisto, joten varsinaista purkua tai kenttäanalyysiä ei voi vielä tehdä.",
    ]
    (run_dir / "suunnitelma_ja_tilanne.txt").write_text("\n".join(plan_lines), encoding="utf-8")

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "run_dir": str(run_dir),
        "old_grouping_preserved": True,
        "backup_files": backup_rows,
        "source_copy": source_copy,
        "source_zip": zip_info,
        "next_action": "Toimita sisältöä sisältävä products.zip. Nykyinen zip on tyhjä.",
    }
    (run_dir / "yhteenveto.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
