"""Validate the data files required by the current potential-model run."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parent
SALES = BASE.parent / "GoSystems_sales_26_05_2026_summarized.csv"
PROFINDER = BASE / "haku_Prospektointimasterlista_2026-08-12.xlsx"
PRODUCT_MASTER = BASE / "INNOFLAME-TUOTELISTA-TUOTERYHMITTELY.xlsx"
ACCOUNTS = BASE / "Account_20.05.2026_combined_with_profinder.xlsx"
CRM = BASE / "CRM_potentials_03.06.2026_03.07.2026 (1).xlsx"
EXCLUSIONS = BASE / "Netvisor asiakastiedot 6-2026.xlsx"
REPORT = BASE / "data_validation_before_model_run.md"


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def find_column(frame: pd.DataFrame, *names: str) -> str | None:
    columns = {norm(c): c for c in frame.columns}
    return next((columns[norm(name)] for name in names if norm(name) in columns), None)


def clean_id(value: object) -> str:
    if pd.isna(value):
        return ""
    digits = "".join(c for c in str(value) if c.isdigit())
    if len(digits) == 7:
        digits = "0" + digits
    return f"{digits[:-1]}-{digits[-1]}" if len(digits) >= 8 else ""


def check_file(path: Path, label: str) -> list[str]:
    if not path.exists():
        return [f"- [ ] **BLOCKER** {label}: tiedostoa ei löydy: `{path}`"]
    return [f"- [x] {label}: löytyy ({path.stat().st_size:,} tavua)."]


def main() -> None:
    lines = ["# Potentiaalimallin data-validointi", "", "Raportti on muodostettu ennen malliajoa. Data-aineistoja ei muokata tässä tarkistuksessa.", ""]
    for path, label in [(SALES, "Myyntiaineisto"), (PROFINDER, "Profinder-aineisto"), (PRODUCT_MASTER, "Tuotemasteri"), (ACCOUNTS, "Account-rekisteri"), (CRM, "CRM-potentiaalit"), (EXCLUSIONS, "Poistolista")]:
        lines.extend(check_file(path, label))

    sales = pd.read_csv(SALES, sep=None, engine="python")
    account_col = find_column(sales, "account_id", "accountid")
    status_col = find_column(sales, "status")
    sku_col = find_column(sales, "sku", "productcode", "product_code")
    date_col = find_column(sales, "created_at", "sold_at", "order_date")
    price_col = find_column(sales, "price")
    amount_col = find_column(sales, "amount")
    value_col = find_column(sales, "total_value", "sales", "totalprice")
    sales_value = pd.to_numeric(sales[price_col], errors="coerce") * pd.to_numeric(sales[amount_col], errors="coerce") if price_col and amount_col else (pd.to_numeric(sales[value_col].astype("string").str.replace(",", ".", regex=False), errors="coerce") if value_col else pd.Series(dtype=float))
    sales_date = pd.to_datetime(sales[date_col], errors="coerce", dayfirst=True, utc=True) if date_col else pd.Series(dtype="datetime64[ns, UTC]")
    invoiced = sales[status_col].astype("string").str.strip().str.casefold().eq("invoiced") if status_col else pd.Series(False, index=sales.index)
    invoiced_value = sales_value.loc[invoiced] if len(sales_value) else pd.Series(dtype=float)
    lines += ["", "## Myyntiaineisto", f"- Rivejä: **{len(sales):,}**", f"- Sarakkeet: `{', '.join(map(str, sales.columns))}`", f"- Invoiced-rivejä: **{int(invoiced.sum()):,}**", f"- Hylättävät/puuttuvat päivät: **{int(sales_date.isna().sum()):,}**", f"- Hylättävät/puuttuvat account_id:t: **{int(pd.to_numeric(sales[account_col], errors='coerce').isna().sum()):,}**" if account_col else "- [ ] **BLOCKER** `account_id` puuttuu.", f"- Puuttuvat tai virheelliset price/amount-arvot: **{int(sales_value.isna().sum()):,}**" if len(sales_value) else "- [ ] **BLOCKER** `price` tai `amount` puuttuu.", f"- Nolla- tai negatiiviset riviarvot: **{int(sales_value.fillna(0).le(0).sum()):,}**" if len(sales_value) else "", f"- Invoiced-rivien nolla- tai negatiiviset arvot: **{int(invoiced_value.le(0).sum()):,}**" if len(invoiced_value) else "", f"- Aikaväli: **{sales_date.min()} - {sales_date.max()}**" if not sales_date.empty else ""]
    if status_col:
        lines.append(f"- Statusarvot: `{sales[status_col].value_counts(dropna=False).to_dict()}`")
    if sku_col:
        lines.append(f"- Puuttuvat SKU/ProductCode-arvot: **{int(sales[sku_col].isna().sum()):,}**")
        lines.append(f"- Invoiced-rivien puuttuvat SKU/ProductCode-arvot: **{int(sales.loc[invoiced, sku_col].isna().sum()):,}**")
    else:
        lines.append("- [ ] **BLOCKER** `sku`/`ProductCode` puuttuu tuotetason suosituksia varten.")

    master = pd.read_excel(PRODUCT_MASTER, sheet_name="Tuotteet")
    master_code = find_column(master, "Tuotekoodi", "ProductCode", "code", "sku")
    master_group = find_column(master, "Koko ryhmäpolku", "Tuoteryhmä", "ProductGroup", "product_group")
    master_codes = master[master_code].dropna().astype(str).str.strip().str.upper() if master_code else pd.Series(dtype="string")
    master_groups = master[master_group].fillna("").astype(str).str.strip() if master_group else pd.Series(dtype="string")
    lines += ["", "## Tuotemasteri", f"- Välilehti: `Tuotteet`", f"- Rivejä: **{len(master):,}**", f"- Tuotekoodit: **{master_codes.nunique():,}**", f"- Puuttuvat tuoteryhmät: **{int(master_groups.eq('').sum()):,}**", f"- Duplikaattiset tuotekoodit: **{int(master_codes.duplicated().sum()):,}**"]
    if not master_code or not master_group:
        lines.append("- [ ] **BLOCKER** Tuotemasterista puuttuu `Tuotekoodi` tai tuoteryhmä.")

    accounts = pd.read_excel(ACCOUNTS)
    account_id = find_column(accounts, "ID", "account_id", "accountid")
    account_business = find_column(accounts, "Business ID", "Y-tunnus", "Y-tunnus.1")
    account_ids = pd.to_numeric(accounts[account_id], errors="coerce") if account_id else pd.Series(dtype=float)
    account_business_ids = accounts[account_business].map(clean_id) if account_business else pd.Series(dtype="string")
    sales_ids = pd.to_numeric(sales[account_col], errors="coerce") if account_col else pd.Series(dtype=float)
    lines += ["", "## Account-rekisteri ja liitokset", f"- Rekisteririvejä: **{len(accounts):,}**", f"- Puuttuvat Account ID:t: **{int(account_ids.isna().sum()):,}**", f"- Duplikaattiset Account ID:t: **{int(account_ids.dropna().duplicated().sum()):,}**", f"- Puuttuvat Y-tunnukset: **{int(account_business_ids.eq('').sum()):,}**", f"- Myynnin account_id-osumat rekisteriin: **{int(sales_ids.dropna().isin(set(account_ids.dropna())).sum()):,}/{int(sales_ids.notna().sum()):,}**"]

    profinder = pd.read_excel(PROFINDER)
    prof_id = find_column(profinder, "Y-tunnus", "business_id", "Business ID")
    prof_ids = profinder[prof_id].map(clean_id) if prof_id else pd.Series(dtype="string")
    lines += ["", "## Profinder", f"- Rivejä: **{len(profinder):,}**", f"- Sarakkeet: `{', '.join(map(str, profinder.columns))}`", f"- Puuttuvat Y-tunnukset: **{int(prof_ids.eq('').sum()):,}**" if prof_id else "- [ ] **BLOCKER** Profinderista ei löytynyt Y-tunnus-saraketta.", f"- Duplikaattiset Y-tunnukset: **{int(prof_ids[prof_ids.ne('')].duplicated().sum()):,}**" if prof_id else "", f"- Account-rekisterin Y-tunnukset löytyvät Profinderista: **{int(account_business_ids[account_business_ids.ne('')].isin(set(prof_ids[prof_ids.ne('')])).sum()):,}/{int(account_business_ids.ne('').sum()):,}**" if prof_id else ""]

    if sku_col and master_code:
        sales_codes = sales.loc[invoiced, sku_col].dropna().astype(str).str.strip().str.upper()
        master_code_set = set(master_codes)
        matched_codes = sales_codes[sales_codes.isin(master_code_set)]
        lines += ["", "## ProductCode-liitos", f"- Invoiced-rivien yksilölliset ProductCode-arvot: **{sales_codes.nunique():,}**", f"- Invoiced ProductCode-arvot löytyvät masterista: **{matched_codes.nunique():,}/{sales_codes.nunique():,}**", f"- Masterista puuttuvat yksilölliset ProductCode-arvot: **{sales_codes[~sales_codes.isin(master_code_set)].nunique():,}**"]

    lines += ["", "## Tehtävät ennen malliajoa", "", "1. **Tarkista myyntiarvot:** `sales` käsitellään rivin kokonaismyyntinä ja `totalprice` yksikköhintana; tarkista nolla- ja negatiiviset Invoiced-rivit.", "2. **Rajaa myynti:** käytä vain `status = Invoiced` -rivejä ja muodosta `created_year_month = YYYY-MM` lähteen `sold_at`-päivästä.", "3. **Varmista Account-liitos:** selvitä myynnin account_id:t, joita Account-rekisterissä ei ole.", "4. **Varmista Profinder-liitos:** tarkista puuttuvat tai duplikaattiset Y-tunnukset ja hyväksy ne rivit, joita ei voi yhdistää yritysdataan.", "5. **Täydennä tuoteryhmät:** liitä `ProductCode` tuotemasteriin ja selvitä kaikki masterista puuttuvat koodit ennen suosituksia.", "6. **Tarkista tuotemasterin duplikaatit:** yhdelle ProductCode-arvolle pitää olla yksi yksiselitteinen tuoteryhmä.", "7. **Varmista poissulut:** kuljetus-, pakkaus- ja kustannustuotteet poistetaan suosituksista, vaikka niiden myyntihistoria säilyy laskennassa.", "8. **Tee koeajo ja hyväksy data quality -raportti** ennen varsinaisen tuloksen julkaisemista.", "", "### Johtopäätös", "Malliajoa ei pidä julkaista ennen kuin yllä olevat tarkistukset on käsitelty. Tämä raportti erottaa rakenteelliset blockerit laadullisista tarkistustehtävistä."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    main()
