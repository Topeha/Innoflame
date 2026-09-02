# CSV Data Descriptions

This document describes the two CSV inputs expected by the prospecting pipeline:

1. `companies.csv`: Profinder or company master data
2. `sales_history.csv`: historical customer sales
3. optional `accounts.xlsx`: account master used to attach customer status
4. optional `accounts_direct_delivery.xlsx`: account master used to tag `customer_status = direct_delivery`
5. optional `accounts_gokeep_plus.xlsx`: account master used to tag `customer_status = Gokeep+`

The pipeline can start with CSV files first and later be switched to BigQuery by changing the config only.

## General rules

- File encoding: `UTF-8`
- Delimiter: comma `,`
- Header row: required
- Missing values: leave empty
- Decimal separator: dot `.`
- Dates: ISO format `YYYY-MM-DD`
- Identifiers:
  - `business_id` should be stable across both files
  - use the same exact identifier format in both files

## File 1: `companies.csv`

Purpose: one row per company, including both existing customers and non-customers.

Minimum required columns:

| Column | Type | Required | Example | Description |
| --- | --- | --- | --- | --- |
| `business_id` | string | yes | `1234567-8` | Unique company identifier used to join company data with sales history. |
| `industry` | string | yes | `Manufacturing` | Main industry or business category. |
| `revenue` | float | yes | `1250000.0` | Annual revenue or best available revenue estimate. |
| `headcount` | float | yes | `42` | Number of employees. |
| `growth` | float | yes | `0.18` | Growth metric, for example year-over-year growth rate. |
| `location` | string | yes | `Helsinki` | Main location, region, city, or sales area. |

Recommended optional columns:

| Column | Type | Required | Example | Description |
| --- | --- | --- | --- | --- |
| `municipality` | string | no | `Helsinki` | More detailed location field. |
| `postal_code` | string | no | `00100` | Postal code if available. |
| `company_form` | string | no | `Oy` | Legal entity form. |
| `founded_year` | int | no | `2014` | Year company was founded. |
| `website` | string | no | `example.fi` | Optional web domain. |

Notes:

- There should be only one row per `business_id`.
- Existing customers should also be included here, because the model needs the full company universe for training and similarity.
- If your real source uses different names, map them in `config.yaml` under `columns` and `features`.

Example:

```csv
business_id,industry,revenue,headcount,growth,location,municipality
1234567-8,Manufacturing,1250000.0,42,0.18,Helsinki,Helsinki
2345678-9,Construction,820000.0,15,-0.03,Tampere,Tampere
3456789-0,IT Services,5400000.0,75,0.27,Espoo,Espoo
```

## File 2: `sales_history.csv`

Purpose: one row per order line, invoice line, or sales event.

Minimum required columns:

| Column | Type | Required | Example | Description |
| --- | --- | --- | --- | --- |
| `business_id` | string | yes | `1234567-8` | Company identifier matching `companies.csv`. |
| `customer_id` | string | no | `CUST-00125` | Optional customer identifier if different from business id. |
| `customer_status` | string | yes for training unless joined from accounts file | `Active` | Customer status after joining customer master data. Only `Active` and `Gokeep+` are used for model training and recommendation learning. |
| `order_date` | date | yes | `2025-11-15` | Order, invoice, or booking date used for time-aware training. |
| `product_service` | string | yes | `Managed IT` | Product or service purchased. |
| `net_sales` | float | yes | `3500.0` | Net sales amount for the row. Required for annual customer value, training eligibility, and prospect potential filtering. |
| `margin` | float | no | `950.0` | Margin or contribution amount if available. |

Recommended optional columns:

| Column | Type | Required | Example | Description |
| --- | --- | --- | --- | --- |
| `quantity` | float | no | `3` | Ordered quantity. |
| `sales_rep` | string | no | `north_team` | Sales owner or team. |
| `product_family` | string | no | `IT Services` | Higher level product grouping. |
| `channel` | string | no | `direct` | Sales channel. |
| `order_id` | string | no | `SO-2025-004512` | Transaction identifier. |

Notes:

- Multiple rows per `business_id` are expected.
- The same company may have many purchases across time.
- Model training and recommendation learning must use only rows where `customer_status` is `Active` or `Gokeep+`.
- Customers with trailing annual sales below `4000 EUR` are excluded from model teaching and recommendation learning.
- `order_date` is critical for the training split and lookback label creation.
- `product_service` should be a business-meaningful label, not just an internal numeric code if possible.

Example:

```csv
 business_id,customer_id,customer_status,order_date,product_service,net_sales,margin
1234567-8,CUST-00125,Active,2025-11-15,Managed IT,3500.0,950.0
1234567-8,CUST-00125,Gokeep+,2026-01-03,Cloud Migration,12500.0,4100.0
2345678-9,CUST-00981,Other,2025-09-27,Workwear,2200.0,680.0
```

## How the pipeline uses the files

### Lead scoring

- `companies.csv` provides the feature space for all companies.
- `sales_history.csv` is used to create the target label:
  - `customer_status` can come either directly from sales data or from a separate account master join
  - a second account list can explicitly tag matching rows as `direct_delivery`
  - a third account list can explicitly tag matching rows as `Gokeep+`
  - only rows with eligible customer statuses are used for model teaching
  - only customers above the configured annual sales floor are used as teaching examples
  - `label = 1` if company purchased within the configured lookback window
  - otherwise `label = 0`

### Next-best-offer

- Similarity model uses company attributes from `companies.csv`
- Neighbor purchases come from `sales_history.csv`
- Co-occurrence rules are learned from product combinations in `sales_history.csv`
- Both are filtered to eligible statuses such as `Active` and `Gokeep+`
- Prospects with estimated annual potential below `4000 EUR` are filtered out from Innoflame's final list

## Recommended first local config

Use a local CSV config like this:

```yaml
sources:
  companies:
    type: csv
    path: data/companies.csv
  sales:
    type: csv
    path: data/sales_history.csv
  accounts:
    type: excel
    path: data/Account_20.05.2026_active.xlsx
  accounts_direct_delivery:
    type: excel
    path: data/Account_20.05.2026_direct_delivery.xlsx
  accounts_gokeep_plus:
    type: excel
    path: data/Account_20.05.2026_Gokeep+.xlsx

columns:
  business_id: business_id
  customer_id: customer_id
  customer_status: customer_status
  account_business_id: Business ID
  account_status: status
  order_date: order_date
  product: product_service
  net_sales: net_sales
  margin: margin

features:
  numeric_company:
    - revenue
    - headcount
    - growth
  categorical_company:
    - industry
    - location
  extra_company:
    - municipality

output:
  mode: csv
  csv_uri: output/prospect_scores.csv
```

Additional business rules in the current model:

- `eligible_customer_statuses = [Active, Gokeep+]`
- `direct_delivery` can be attached from a separate account list but is not included in model teaching unless explicitly added to `eligible_customer_statuses`
- `Gokeep+` can be attached from a separate account list and is included in model teaching by default
- `min_training_customer_annual_sales_eur = 4000`
- `min_annual_potential_eur = 4000`
- potential segments:
  - `A >= 100000 EUR`
  - `B >= 50000 EUR`
  - `C >= 10000 EUR`
  - `Below C = 4000-9999 EUR`
  - `Partner < 4000 EUR`

## Common mapping examples

If your source column names differ, map them like this:

| Real source column | Config target |
| --- | --- |
| `ytunnus` | `business_id` |
| `toimiala` | `industry` |
| `liikevaihto` | `revenue` |
| `henkilosto` | `headcount` |
| `kasvu_pct` | `growth` |
| `kaupunki` | `location` |
| `tilaus_pvm` | `order_date` |
| `tuote_nimi` | `product_service` |

## Validation checklist

Before first run, verify:

1. Both CSV files open correctly in UTF-8.
2. `business_id` format matches exactly across both files.
3. `order_date` is a real date field in `YYYY-MM-DD` format.
4. `customer_status` exists in the sales data and contains at least `Active` or `Gokeep+`.
5. Company feature columns listed in config actually exist in `companies.csv`.
6. `net_sales` is populated well enough to calculate annual customer value.
7. Product names are clean enough for recommendation output.
