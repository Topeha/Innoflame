from __future__ import annotations

import csv
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PACKAGE_DIR = ROOT / "outputs" / "tuoteryhmittely_lahdedata"
STAGING_DIR = PACKAGE_DIR / "Innoflame_tuoteryhmittely_lahdedata"
ZIP_PATH = PACKAGE_DIR / "Innoflame_tuoteryhmittely_lahdedata.zip"


SOURCES = [
    ("01_tuotemaster", ROOT / "products.json.gz", "Päätuotteet ja variantit sisältävä tuotemasteri."),
    ("01_tuotemaster", ROOT / "products_table_view.csv", "Tuotemasterista muodostettu taulukkonäkymä."),
    ("01_tuotemaster", ROOT / "products_table_view.xlsx", "Tuotemasterista muodostettu Excel-näkymä."),
    ("02_rikastus_ja_toimittajat", ROOT / "product_master_enrichment" / "Brand mapping.xlsx", "Brändien yhtenäistämisessä käytetty mapping."),
    ("02_rikastus_ja_toimittajat", ROOT / "product_master_enrichment" / "Kopio_Innoflame_found_products_with_logic_fi_selitetty_2.xlsx", "Aiempi tuotetietojen rikastuksen tukiaineisto."),
    ("02_rikastus_ja_toimittajat", ROOT / "product_master_enrichment" / "Product lists from suppliers.zip", "Toimittajalistat alkuperäisenä zip-pakettina."),
    ("03_tuoteryhmittely_ja_auditointi", ROOT / "product_master_enrichment" / "final_product_grouping" / "Innoflame_tuoteryhmittely.csv", "Valmis tuoteryhmittely CSV-muodossa auditointia varten."),
    ("03_tuoteryhmittely_ja_auditointi", ROOT / "product_master_enrichment" / "final_product_grouping" / "Innoflame_tuoteryhmittely.xlsx", "Valmis tuoteryhmittely Excel-muodossa auditointia varten."),
    ("03_tuoteryhmittely_ja_auditointi", ROOT / "outputs" / "product_grouping_summary" / "paatotuotteet_ryhmittain_yhteenveto.xlsx", "Päätuotetason yhteenveto ryhmittäin."),
    ("03_tuoteryhmittely_ja_auditointi", ROOT / "outputs" / "product_grouping_summary" / "tarkistettavat_ryhma_analyysi.xlsx", "Tarkistettavat-ryhmän analyysi."),
    ("03_tuoteryhmittely_ja_auditointi", ROOT / "outputs" / "product_grouping_summary" / "tarkistettavat_ryhma_luokitteluehdotukset.csv", "Tarkistettavat-ryhmän luokitteluehdotukset."),
    ("03_tuoteryhmittely_ja_auditointi", ROOT / "product_master_enrichment" / "final_product_grouping" / "high_confidence_suggestion_application_report.csv", "High-varmuuden siirtojen raportti."),
    ("03_tuoteryhmittely_ja_auditointi", ROOT / "product_master_enrichment" / "final_product_grouping" / "product_group_feedback_3level_mapping_report.csv", "Asiakaspalautteen pohjalta tehdyn 3-tason muutoksen raportti."),
]


SUPPLIER_FILES_DIR = ROOT / "product_master_enrichment" / "Product lists from suppliers"


def safe_copy(src: Path, target_dir: Path) -> Path | None:
    if not src.exists():
        return None
    target_dir.mkdir(parents=True, exist_ok=True)
    dst = target_dir / src.name
    shutil.copy2(src, dst)
    return dst


def main() -> None:
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, str]] = []

    for folder, src, description in SOURCES:
        copied = safe_copy(src, STAGING_DIR / folder)
        manifest_rows.append(
            {
                "folder": folder,
                "file": src.name,
                "source_path": str(src),
                "included": "yes" if copied else "missing",
                "size_bytes": str(src.stat().st_size) if src.exists() else "",
                "description": description,
            }
        )

    if SUPPLIER_FILES_DIR.exists():
        for src in sorted(SUPPLIER_FILES_DIR.iterdir()):
            if not src.is_file():
                continue
            copied = safe_copy(src, STAGING_DIR / "02_rikastus_ja_toimittajat" / "Product lists from suppliers")
            manifest_rows.append(
                {
                    "folder": "02_rikastus_ja_toimittajat/Product lists from suppliers",
                    "file": src.name,
                    "source_path": str(src),
                    "included": "yes" if copied else "missing",
                    "size_bytes": str(src.stat().st_size),
                    "description": "Toimittajalistan purettu lähdetiedosto.",
                }
            )

    readme = STAGING_DIR / "README.txt"
    readme.write_text(
        "\n".join(
            [
                "Innoflame tuoteryhmittely - lähdedatapaketin sisältö",
                f"Luotu: {datetime.now().isoformat(timespec='seconds')}",
                "",
                "Paketti sisältää tuoteryhmittelyssä käytetyt keskeiset lähtöaineistot sekä auditointia tukevat tiedostot.",
                "Varsinainen tuoteryhmittely on tehty päätuotetasolla. Variantit löytyvät products.json.gz-tiedoston options-rakenteesta.",
                "",
                "Kansiot:",
                "01_tuotemaster - tuotemaster ja siitä muodostetut näkymät",
                "02_rikastus_ja_toimittajat - brand mapping ja toimittajalistat",
                "03_tuoteryhmittely_ja_auditointi - valmis tuoteryhmittely ja tärkeimmät auditointiraportit",
                "",
                "Tarkka tiedostolista on manifest.csv-tiedostossa.",
            ]
        ),
        encoding="utf-8",
    )

    manifest = STAGING_DIR / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["folder", "file", "source_path", "included", "size_bytes", "description"],
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(STAGING_DIR.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(PACKAGE_DIR))

    print(f"folder={STAGING_DIR}")
    print(f"zip={ZIP_PATH}")
    print(f"files_in_manifest={len(manifest_rows)}")
    print(f"zip_size_bytes={ZIP_PATH.stat().st_size}")


if __name__ == "__main__":
    main()
