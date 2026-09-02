# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import html
import json
import math
import os
import re
import time
import urllib.parse
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "product_master_enrichment" / "final_product_grouping"

DEFAULT_INPUT_FILE = DATA_DIR / "products_product_group_tree_final_weight_value_updated_20260629_152451.xlsx"
if not DEFAULT_INPUT_FILE.exists():
    DEFAULT_INPUT_FILE = DATA_DIR / "products_product_group_tree_final.xlsx"

STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_FILE = DATA_DIR / f"{DEFAULT_INPUT_FILE.stem}_web_enriched_{STAMP}.xlsx"
LOG_FILE = DATA_DIR / f"{DEFAULT_INPUT_FILE.stem}_web_enrichment_log_{STAMP}.csv"
SUMMARY_FILE = DATA_DIR / f"{DEFAULT_INPUT_FILE.stem}_web_enrichment_summary_{STAMP}.json"

WEIGHT_COLUMN = "weight_value"
REQUIRED_COLUMNS = [WEIGHT_COLUMN, "brand_website", "product_name"]

NEW_COLUMNS = [
    "web_extracted_weight",
    "web_extracted_weight_unit",
    "web_extracted_dimensions",
    "web_extracted_dimension_unit",
    "web_extraction_source_url",
    "web_extraction_status",
    "web_extraction_confidence",
    "web_extraction_notes",
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

REQUEST_TIMEOUT_SECONDS = int(os.environ.get("WEB_ENRICH_TIMEOUT", "15"))
REQUEST_DELAY_SECONDS = float(os.environ.get("WEB_ENRICH_DELAY", "0.5"))
MAX_PRODUCT_LINKS_PER_ROW = int(os.environ.get("WEB_ENRICH_MAX_LINKS", "6"))
MAX_HOME_LINKS_TO_SCAN = int(os.environ.get("WEB_ENRICH_MAX_HOME_LINKS", "120"))
MAX_ROWS = int(os.environ.get("WEB_ENRICH_MAX_ROWS", "0"))

PAGE_CACHE: dict[str, tuple[str | None, str | None]] = {}
CANDIDATE_CACHE: dict[tuple[str, str], tuple[list[str], str]] = {}


class LinkAndTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.text_parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if tag == "a":
            for name, value in attrs:
                if name.lower() == "href" and value:
                    self.links.append(value.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data:
            self.text_parts.append(data)

    @property
    def text(self) -> str:
        return clean_text(" ".join(self.text_parts))


def load_excel(file_path: Path) -> pd.DataFrame:
    if not file_path.exists():
        raise FileNotFoundError(f"Tiedostoa ei löydy: {file_path}")
    df = pd.read_excel(file_path, engine="openpyxl")
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        raise ValueError("Excelistä puuttuu pakollisia sarakkeita: " + ", ".join(missing_columns))
    for col in NEW_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df


def is_missing_or_zero_weight(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    value_str = str(value).strip()
    if not value_str:
        return True
    try:
        return float(value_str.replace(",", ".")) == 0
    except ValueError:
        return False


def normalize_url(url: Any) -> str | None:
    if url is None or (isinstance(url, float) and math.isnan(url)):
        return None
    text = str(url).strip()
    if not text or text.lower() == "nan":
        return None
    if not text.startswith(("http://", "https://")):
        text = "https://" + text
    parsed = urllib.parse.urlparse(text)
    if not parsed.netloc:
        return None
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))


def get_domain(url: str) -> str:
    return urllib.parse.urlparse(url).netloc.lower()


def clean_text(text: str) -> str:
    text = html.unescape(text or "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def tokenize_product_name(product_name: str) -> list[str]:
    tokens = re.findall(r"[A-Za-zÅÄÖåäö0-9]+", str(product_name).lower())
    stopwords = {"and", "the", "for", "with", "sis", "cm", "mm", "kpl", "sekä", "ja"}
    return [token for token in tokens if len(token) >= 3 and token not in stopwords]


def product_name_match_score(product_name: str, page_text: str) -> float:
    if not product_name or not page_text:
        return 0.0
    product_name_lower = str(product_name).lower().strip()
    page_text_lower = page_text.lower()
    if product_name_lower in page_text_lower:
        return 1.0
    tokens = tokenize_product_name(product_name)
    if not tokens:
        return 0.0
    matched = sum(1 for token in tokens if token in page_text_lower)
    return matched / len(tokens)


def fetch_page(url: str) -> tuple[str | None, str | None]:
    if url in PAGE_CACHE:
        return PAGE_CACHE[url]
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "fi-FI,fi;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=True)
        if response.status_code >= 400:
            PAGE_CACHE[url] = (None, f"HTTP error {response.status_code}")
            return PAGE_CACHE[url]
        PAGE_CACHE[url] = (response.text, None)
        return PAGE_CACHE[url]
    except requests.RequestException as exc:
        PAGE_CACHE[url] = (None, str(exc))
        return PAGE_CACHE[url]


def parse_html(base_url: str, html_text: str) -> tuple[str, list[str]]:
    parser = LinkAndTextParser()
    parser.feed(html_text)
    base_domain = get_domain(base_url)
    links: list[str] = []
    for href in parser.links:
        absolute_url = urllib.parse.urljoin(base_url, href)
        parsed = urllib.parse.urlparse(absolute_url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc.lower() != base_domain:
            continue
        clean_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", parsed.query, ""))
        links.append(clean_url)
    seen: set[str] = set()
    unique_links = []
    for link in links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)
    return parser.text, unique_links


def rank_candidate_links(product_name: str, links: list[str]) -> list[str]:
    tokens = tokenize_product_name(product_name)
    scored_links: list[tuple[float, str]] = []
    for link in links[:MAX_HOME_LINKS_TO_SCAN]:
        link_lower = urllib.parse.unquote(link.lower())
        score = sum(1 for token in tokens if token in link_lower)
        for hint in ["product", "products", "tuote", "tuotteet", "shop", "catalog", "item", "collection"]:
            if hint in link_lower:
                score += 0.5
        if score > 0:
            scored_links.append((score, link))
    scored_links.sort(key=lambda item: item[0], reverse=True)
    return [link for _, link in scored_links[:MAX_PRODUCT_LINKS_PER_ROW]]


def get_candidate_pages(brand_url: str, product_name: str) -> tuple[list[str], str]:
    cache_key = (brand_url, " ".join(tokenize_product_name(product_name)))
    if cache_key in CANDIDATE_CACHE:
        return CANDIDATE_CACHE[cache_key]
    candidate_urls = [brand_url]
    html_text, error = fetch_page(brand_url)
    time.sleep(REQUEST_DELAY_SECONDS)
    if html_text is None:
        CANDIDATE_CACHE[cache_key] = (candidate_urls, error or "")
        return CANDIDATE_CACHE[cache_key]
    _, links = parse_html(brand_url, html_text)
    candidate_urls.extend(rank_candidate_links(product_name, links))
    seen: set[str] = set()
    unique_urls = []
    for url in candidate_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    CANDIDATE_CACHE[cache_key] = (unique_urls[: MAX_PRODUCT_LINKS_PER_ROW + 1], "")
    return CANDIDATE_CACHE[cache_key]


def normalize_weight_unit(unit: str) -> str:
    unit = (unit or "").lower().strip()
    if unit in {"gram", "grams"}:
        return "g"
    if unit in {"kilogram", "kilograms"}:
        return "kg"
    return unit


def extract_weight(text: str) -> tuple[str | None, str | None, str | None]:
    text = clean_text(text)
    if not text:
        return None, None, None
    weight_keywords = (
        r"weight|net weight|gross weight|product weight|item weight|"
        r"paino|nettopaino|netto paino|bruttopaino|brutto paino|paino noin"
    )
    number_pattern = r"(\d+(?:[.,]\d+)?)"
    unit_pattern = r"(kg|g|gram|grams|kilogram|kilograms)"
    patterns = [
        rf"(?i)\b(?:{weight_keywords})\b\s*[:\-]?\s*{number_pattern}\s*{unit_pattern}\b",
        rf"(?i){number_pattern}\s*{unit_pattern}\s*(?:\b(?:{weight_keywords})\b)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        value = None
        unit = None
        for group in match.groups():
            if not group:
                continue
            if re.fullmatch(r"\d+(?:[.,]\d+)?", group):
                value = group.replace(",", ".")
            elif re.fullmatch(unit_pattern, group, flags=re.IGNORECASE):
                unit = normalize_weight_unit(group)
        return value, unit, match.group(0)
    return None, None, None


def normalize_dimension_unit(unit: str) -> str:
    unit = (unit or "").lower().strip()
    if unit in {"millimeter", "millimetre"}:
        return "mm"
    if unit in {"centimeter", "centimetre"}:
        return "cm"
    return unit


def normalize_dimension_value(value: str) -> str:
    value = (value or "").replace("×", "x").replace("*", "x").replace(",", ".")
    value = re.sub(r"\bby\b", "x", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*x\s*", " x ", value)
    return re.sub(r"\s+", " ", value).strip()


def extract_dimensions(text: str) -> tuple[str | None, str | None, str | None]:
    text = clean_text(text)
    if not text:
        return None, None, None
    dimension_keywords = (
        r"dimensions|dimension|size|product size|item size|measurements|"
        r"length|width|height|depth|mitat|koko|pituus|leveys|korkeus|syvyys"
    )
    number_pattern = r"\d+(?:[.,]\d+)?"
    separator_pattern = r"(?:x|×|\*|by)"
    unit_pattern = r"(mm|cm|m|millimeter|millimetre|centimeter|centimetre)"
    patterns = [
        rf"(?i)\b(?:{dimension_keywords})\b\s*[:\-]?\s*({number_pattern}\s*{separator_pattern}\s*{number_pattern}(?:\s*{separator_pattern}\s*{number_pattern})?)\s*{unit_pattern}\b",
        rf"(?i)({number_pattern}\s*{separator_pattern}\s*{number_pattern}(?:\s*{separator_pattern}\s*{number_pattern})?)\s*{unit_pattern}\s*(?:\b(?:{dimension_keywords})\b)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return normalize_dimension_value(match.group(1)), normalize_dimension_unit(match.group(2)), match.group(0)
    generic_match = re.search(
        rf"(?i)\b({number_pattern}\s*{separator_pattern}\s*{number_pattern}(?:\s*{separator_pattern}\s*{number_pattern})?)\s*{unit_pattern}\b",
        text,
    )
    if generic_match:
        return normalize_dimension_value(generic_match.group(1)), normalize_dimension_unit(generic_match.group(2)), generic_match.group(0)
    return None, None, None


def determine_confidence(name_score: float, has_weight: bool, has_dimensions: bool) -> str:
    if name_score >= 0.9 and has_weight and has_dimensions:
        return "high"
    if name_score >= 0.7 and (has_weight or has_dimensions):
        return "high"
    if name_score >= 0.4 and (has_weight or has_dimensions):
        return "medium"
    if has_weight or has_dimensions:
        return "low"
    return "none"


def build_notes(weight_match: str | None, dimensions_match: str | None, name_score: float) -> str:
    notes = [f"product_name_match_score={name_score:.2f}"]
    if weight_match:
        notes.append(f"weight_match='{weight_match[:150]}'")
    if dimensions_match:
        notes.append(f"dimensions_match='{dimensions_match[:150]}'")
    return " | ".join(notes)


def process_row(row_index: int, row: pd.Series) -> dict[str, Any]:
    product_name = row.get("product_name", "")
    brand_website = row.get("brand_website", "")
    result = {
        "row_index": row_index,
        "product_id": row.get("product_id", ""),
        "sku": row.get("sku", ""),
        "product_name": product_name,
        "brand_name": row.get("brand_name", ""),
        "brand_website": brand_website,
        "attempted_url_or_query": "",
        "source_url": "",
        "extracted_weight": "",
        "extracted_weight_unit": "",
        "extracted_dimensions": "",
        "extracted_dimension_unit": "",
        "status": "",
        "confidence": "none",
        "notes": "",
        "error_message": "",
    }
    if not str(product_name).strip():
        result["status"] = "missing_product_name"
        return result
    name_weight_value, name_weight_unit, name_weight_match = extract_weight(str(product_name))
    name_dimensions_value, name_dimension_unit, name_dimensions_match = extract_dimensions(str(product_name))
    brand_url = normalize_url(brand_website)
    if not brand_url:
        if name_weight_value or name_dimensions_value:
            result.update(
                {
                    "source_url": "product_name",
                    "extracted_weight": name_weight_value or "",
                    "extracted_weight_unit": name_weight_unit or "",
                    "extracted_dimensions": name_dimensions_value or "",
                    "extracted_dimension_unit": name_dimension_unit or "",
                    "status": "fallback_product_name_found",
                    "confidence": "low",
                    "notes": build_notes(name_weight_match, name_dimensions_match, 1.0),
                }
            )
        else:
            result["status"] = "missing_brand_website"
        return result
    result["attempted_url_or_query"] = brand_url
    candidate_urls, first_error = get_candidate_pages(brand_url, str(product_name))
    best_result = None
    for url in candidate_urls:
        html_text, error = fetch_page(url)
        time.sleep(REQUEST_DELAY_SECONDS)
        if html_text is None:
            result["error_message"] = error or first_error
            continue
        page_text, _ = parse_html(url, html_text)
        weight_value, weight_unit, weight_match = extract_weight(page_text)
        dimensions_value, dimension_unit, dimensions_match = extract_dimensions(page_text)
        name_score = product_name_match_score(str(product_name), page_text)
        if (weight_value or dimensions_value) and name_score >= 0.4:
            current = {
                "source_url": url,
                "extracted_weight": weight_value or "",
                "extracted_weight_unit": weight_unit or "",
                "extracted_dimensions": dimensions_value or "",
                "extracted_dimension_unit": dimension_unit or "",
                "confidence": determine_confidence(name_score, bool(weight_value), bool(dimensions_value)),
                "notes": build_notes(weight_match, dimensions_match, name_score),
            }
            if weight_value and dimensions_value:
                best_result = current
                break
            if best_result is None:
                best_result = current
    if best_result:
        result.update(best_result)
        if result["extracted_weight"] and result["extracted_dimensions"]:
            result["status"] = "success_weight_and_dimensions_found"
        elif result["extracted_weight"]:
            result["status"] = "success_weight_found"
        elif result["extracted_dimensions"]:
            result["status"] = "success_dimensions_found"
    else:
        if name_weight_value or name_dimensions_value:
            result.update(
                {
                    "source_url": "product_name",
                    "extracted_weight": name_weight_value or "",
                    "extracted_weight_unit": name_weight_unit or "",
                    "extracted_dimensions": name_dimensions_value or "",
                    "extracted_dimension_unit": name_dimension_unit or "",
                    "status": "fallback_product_name_found",
                    "confidence": "low",
                    "notes": build_notes(name_weight_match, name_dimensions_match, 1.0),
                }
            )
        else:
            result["status"] = "not_found"
            if not result["error_message"]:
                result["notes"] = "Paino- tai mittatietoja ei löytynyt skannatuilta sivuilta."
    return result


def save_outputs(df: pd.DataFrame, log_rows: list[dict[str, Any]]) -> None:
    df.to_excel(OUTPUT_FILE, index=False, engine="openpyxl")
    fieldnames = [
        "row_index",
        "product_id",
        "sku",
        "product_name",
        "brand_name",
        "brand_website",
        "attempted_url_or_query",
        "source_url",
        "extracted_weight",
        "extracted_weight_unit",
        "extracted_dimensions",
        "extracted_dimension_unit",
        "status",
        "confidence",
        "notes",
        "error_message",
    ]
    with LOG_FILE.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(log_rows)


def main() -> None:
    print(f"Ladataan Excel: {DEFAULT_INPUT_FILE}")
    df = load_excel(DEFAULT_INPUT_FILE)
    total_rows = len(df)
    rows_to_process = []
    for idx, row in df.iterrows():
        has_brand_site = bool(str(row.get("brand_website", "")).strip()) and str(row.get("brand_website", "")).lower() != "nan"
        if is_missing_or_zero_weight(row.get(WEIGHT_COLUMN)) and has_brand_site:
            rows_to_process.append(idx)
    if MAX_ROWS > 0:
        rows_to_process = rows_to_process[:MAX_ROWS]
    print(f"Rivejä yhteensä: {total_rows}")
    print(f"Käsiteltäviä rivejä, joissa {WEIGHT_COLUMN} on tyhjä/0 ja brand_website löytyy: {len(rows_to_process)}")
    log_rows: list[dict[str, Any]] = []
    for counter, idx in enumerate(rows_to_process, start=1):
        row = df.loc[idx]
        print(f"[{counter}/{len(rows_to_process)}] {row.get('product_name', '')} | {row.get('brand_website', '')}")
        result = process_row(idx, row)
        log_rows.append(result)
        df.at[idx, "web_extracted_weight"] = result.get("extracted_weight", "")
        df.at[idx, "web_extracted_weight_unit"] = result.get("extracted_weight_unit", "")
        df.at[idx, "web_extracted_dimensions"] = result.get("extracted_dimensions", "")
        df.at[idx, "web_extracted_dimension_unit"] = result.get("extracted_dimension_unit", "")
        df.at[idx, "web_extraction_source_url"] = result.get("source_url", "")
        df.at[idx, "web_extraction_status"] = result.get("status", "")
        df.at[idx, "web_extraction_confidence"] = result.get("confidence", "")
        df.at[idx, "web_extraction_notes"] = result.get("notes", "")
        print(f"  -> {result.get('status')} | weight={result.get('extracted_weight')} {result.get('extracted_weight_unit')} | dim={result.get('extracted_dimensions')} {result.get('extracted_dimension_unit')}")
    save_outputs(df, log_rows)
    summary = {
        "input_file": str(DEFAULT_INPUT_FILE),
        "output_file": str(OUTPUT_FILE),
        "log_file": str(LOG_FILE),
        "total_rows": total_rows,
        "processed_rows": len(rows_to_process),
        "weights_found": sum(1 for row in log_rows if row.get("extracted_weight")),
        "dimensions_found": sum(1 for row in log_rows if row.get("extracted_dimensions")),
        "not_found": sum(1 for row in log_rows if row.get("status") == "not_found"),
        "errors": sum(1 for row in log_rows if row.get("error_message")),
    }
    SUMMARY_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
