import csv
from collections import OrderedDict
from pathlib import Path


BASE = Path(r"C:\Users\TommiHavukainen\OneDrive - Unikie Oy\Customer\Innoflame")
SOURCE_CSV = BASE / "GoSystems_sales_26_05_2026_combined_with_year_month.csv"
OUTPUT_CSV = BASE / "GoSystems_sales_26_05_2026_summarized.csv"

GROUP_FIELDS = [
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
    "created_year_month",
]


def to_float(value):
    if value is None:
        return 0.0
    text = str(value).strip().replace(",", ".")
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


groups = OrderedDict()
input_rows = 0

with SOURCE_CSV.open(newline="", encoding="utf-8-sig") as handle:
    reader = csv.DictReader(handle)
    for row in reader:
        input_rows += 1
        key = tuple(row.get(field, "") for field in GROUP_FIELDS)
        if key not in groups:
            groups[key] = {field: row.get(field, "") for field in GROUP_FIELDS}
            groups[key]["row_count"] = 0
            groups[key]["total_value"] = 0.0

        groups[key]["row_count"] += 1
        groups[key]["total_value"] += to_float(row.get("price")) * to_float(row.get("amount"))

fieldnames = GROUP_FIELDS + ["row_count", "total_value"]
with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    for row in groups.values():
        row["total_value"] = f"{row['total_value']:.2f}"
        writer.writerow(row)

print(f"input_rows={input_rows}")
print(f"output_rows={len(groups)}")
print(f"csv={OUTPUT_CSV}")
