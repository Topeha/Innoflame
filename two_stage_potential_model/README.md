# Innoflame two-stage potential model

Tämä projektikansio sisältää Innoflamen kaksivaiheisen potentiaalimallin.

## Mallin idea

Malli erottaa kaksi asiaa:

1. ostotodennäköisyys
2. ostavan asiakkaan 12 kuukauden myyntipotentiaali

Lopullinen arvo lasketaan:

```text
odotettu 12 kk potentiaali = ostotodennäköisyys * ennustettu ostavan asiakkaan vuosimyynti
```

Tämä eroaa aiemmasta markkinapotentiaalimallista, joka käytti vahvemmin yrityksen kokoon ja segmenttiin perustuvaa baseline-arvoa.

## Pääoutputit

- `outputs/innoflame_two_stage_potential.xlsx`: kaikki pisteytetyt yritykset
- `outputs/innoflame_two_stage_potential_customers_only.xlsx`: vain Account-asiakkaat
- `outputs/innoflame_two_stage_potential.metrics.json`: mallin metriikat

## Lähdeaineistot

Skripti lukee oletuksena Innoflame-kansion tiedostoja:

- `Account_20.05.2026_combined_with_profinder.xlsx`
- `GoSystems_sales_26_05_2026_summarized.csv`
- `haku_Myyntiin_ai_2026-04-23 (1).xlsx`

## Ajaminen

Projektikansiosta:

```powershell
python innoflame_two_stage_model.py
```

Tarvittavat Python-kirjastot ovat samat kuin aiemmassa prospektimallissa: `pandas`, `numpy`, `scikit-learn` ja Excel-exportiin `openpyxl`.

## Viimeisin ajotulos

Viimeisimmässä ajossa:

- kokonaisrivit: 8 395
- Account-asiakkaat: 5 391
- asiakkaat, joilla GoSystems-myyntihistoriaa: 3 049
- asiakkaat ilman GoSystems-myyntihistoriaa: 2 342
- kokonaispotentiaali: 6 230 048 EUR
- Account-asiakkaiden potentiaali: 3 613 904 EUR
