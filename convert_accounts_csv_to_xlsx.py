import csv
from pathlib import Path

import openpyxl
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font


BASE = Path(r"C:\Users\TommiHavukainen\OneDrive - Unikie Oy\Customer\Innoflame")
SOURCE_CSV = BASE / "GoSystems_accounts_25_06_2026.csv"
OUTPUT_XLSX = BASE / "GoSystems_accounts_25_06_2026.xlsx"


def excel_safe(value):
    if value is None:
        return ""
    return ILLEGAL_CHARACTERS_RE.sub("", str(value))


with SOURCE_CSV.open(newline="", encoding="utf-8-sig") as handle:
    rows = list(csv.DictReader(handle))
    fieldnames = list(rows[0].keys()) if rows else []

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Accounts"
ws.append(fieldnames)
for cell in ws[1]:
    cell.font = Font(bold=True)

for row in rows:
    ws.append([excel_safe(row.get(field, "")) for field in fieldnames])

ws.freeze_panes = "A2"
ws.auto_filter.ref = ws.dimensions
for column_cells in ws.columns:
    header = column_cells[0].value or ""
    max_len = len(str(header))
    for cell in column_cells[1:200]:
        if cell.value is not None:
            max_len = max(max_len, len(str(cell.value)))
    ws.column_dimensions[column_cells[0].column_letter].width = min(max(max_len + 2, 10), 45)

wb.save(OUTPUT_XLSX)
print(f"rows={len(rows)}")
print(f"xlsx={OUTPUT_XLSX}")
