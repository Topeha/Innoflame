import csv
import json
from pathlib import Path


BASE = Path(r"C:\Users\TommiHavukainen\OneDrive - Unikie Oy\Customer\Innoflame")
SOURCE_JSON = BASE / "GoSystems_accounts_25_06_2026.json"
OUTPUT_CSV = BASE / "GoSystems_accounts_25_06_2026.csv"

FIELDNAMES = [
    "id",
    "name",
    "company_name",
    "business_id",
    "country",
    "category",
    "salespersons",
    "salesperson_emails",
    "created_at",
    "updated_at",
    "last_offer",
    "last_activity",
    "potentials",
]


def join_salespersons(account, field):
    values = []
    for salesperson in account.get("salespersons") or []:
        value = salesperson.get(field)
        if value:
            values.append(str(value))
    return "; ".join(values)


def format_potentials(account):
    values = []
    for potential in account.get("potentials") or []:
        values.append(
            ":".join(
                [
                    str(potential.get("type") or ""),
                    str(potential.get("state") or ""),
                    str(potential.get("probability") or ""),
                    str(potential.get("value") or ""),
                    str(potential.get("commment") or ""),
                ]
            )
        )
    return " | ".join(values)


with SOURCE_JSON.open(encoding="utf-8-sig") as handle:
    payload = json.load(handle)

rows = []
for account in payload.get("data") or []:
    rows.append(
        {
            "id": account.get("id", ""),
            "name": account.get("name", ""),
            "company_name": account.get("company_name", ""),
            "business_id": account.get("business_id", ""),
            "country": account.get("country", ""),
            "category": account.get("category", ""),
            "salespersons": join_salespersons(account, "name"),
            "salesperson_emails": join_salespersons(account, "email"),
            "created_at": account.get("created_at", ""),
            "updated_at": account.get("updated_at", ""),
            "last_offer": account.get("last_offer", ""),
            "last_activity": account.get("last_activity", ""),
            "potentials": format_potentials(account),
        }
    )

with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
    writer.writeheader()
    writer.writerows(rows)

print(f"rows={len(rows)}")
print(f"csv={OUTPUT_CSV}")
