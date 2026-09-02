# Innoflame current prospect model v3

V3 is based on the current all-accounts prospect model, but customer sales targets are weighted toward the most recent year.

Default target formula:

`avg_annual_sales_3y_eur = 0.60 * recent_12m + 0.30 * middle_12m + 0.10 * oldest_12m`

This replaces the old unweighted three-year annual average used for selecting top customers and segment median values. The original unweighted value is retained in `avg_annual_sales_3y_eur_unweighted`.

Main outputs:
- `prospect_segment_model_all_accounts_v3.xlsx`: all scored companies/accounts.
- `prospect_segment_model_all_accounts_v3_customers_only.xlsx`: account customers only.
- `prospect_segment_model_all_accounts_v3.metrics.json`: model metrics and totals.

Interpretation:
- V3 reacts more strongly to recent buying behavior.
- Customers with declining historical purchases may receive lower target influence.
- Customers with strong recent sales may move higher in the priority list.
