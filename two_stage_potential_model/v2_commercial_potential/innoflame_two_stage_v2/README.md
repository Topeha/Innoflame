# Innoflame two-stage model v2

V2 keeps the original two-stage forecast and adds a calibrated commercial potential value for sales prioritization.

Main output:
- `ennustettu_12kk_myynti_eur`: conservative 12-month expected sales, calculated as purchase probability x predicted buyer sales.
- `market_potential_eur`: current market-potential estimate from the previous all-accounts model.
- `kaupallinen_potentiaali_eur`: v2 sales-prioritization potential, blended from 12-month expected sales, buyer potential, and market potential.
- `ennustettu potentiaali`: same as `kaupallinen_potentiaali_eur`, kept for compatibility with earlier files.

Formula:
`min(market_potential, 0.50 * expected_12m + 0.30 * buyer_potential + 0.20 * market_potential)`

The blended value is adjusted with segment/revenue boosts and minimum floors for stronger-fit accounts. It is intended for prioritization and account planning, not as a pure budget forecast.
