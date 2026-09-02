import csv
import json
import tarfile
from pathlib import Path


BASE = Path(r"C:\Users\TommiHavukainen\OneDrive - Unikie Oy\Customer\Innoflame")
ARCHIVE = BASE / "GoSystems_sales_26_05_2026.tar.gz"
OUTPUT_CSV = BASE / "GoSystems_sales_26_05_2026_combined.csv"

FIELDNAMES = [
    "source_file",
    "account_id",
    "id",
    "status",
    "category",
    "sku",
    "name",
    "price",
    "amount",
    "order",
    "reference",
    "created_at",
]


files = 0
rows_written = 0

with tarfile.open(ARCHIVE, "r:gz") as tar, OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
    writer.writeheader()

    for member in tar:
        if not member.isfile() or not member.name.endswith(".json"):
            continue
        files += 1
        extracted = tar.extractfile(member)
        if extracted is None:
            continue

        payload = json.load(extracted)
        account_id = payload.get("account_id", "")
        for item in payload.get("data") or []:
            writer.writerow(
                {
                    "source_file": member.name,
                    "account_id": account_id,
                    "id": item.get("id", ""),
                    "status": item.get("status", ""),
                    "category": item.get("category", ""),
                    "sku": item.get("sku", ""),
                    "name": item.get("name", ""),
                    "price": item.get("price", ""),
                    "amount": item.get("amount", ""),
                    "order": item.get("order", ""),
                    "reference": item.get("reference", ""),
                    "created_at": item.get("created_at", ""),
                }
            )
            rows_written += 1

print(f"files={files}")
print(f"rows={rows_written}")
print(f"csv={OUTPUT_CSV}")
