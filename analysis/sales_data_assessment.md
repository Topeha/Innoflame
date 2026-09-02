# Datan laatuanalyysi: myyntihistoria

Lähde: `outputs/Innoflame_merged_sales_csv_source_with_L1_L2_L3_delivery_handling.csv`

## Perustiedot

- rivimäärä: `857 774`
- uniikit tilaukset: `265 688`
- uniikit asiakastunnisteet `accountid`: `4 844`
- uniikit tuotteet `productcode`: `12 311`
- aikajakso: `1.1.2023` - `9.9.2025`
- duplikaattirivejä: `1`

## Sarakerakenne

Keskeiset sarakkeet:

- `source_file`
- `id`
- `status`
- `category`
- `productcode`
- `product_group_l1_code`
- `product_group_l1_name`
- `product_group_l2_code`
- `product_group_l2_name`
- `product_group_l3_code`
- `product_group_l3_name`
- `product_group_match_method`
- `optioncode`
- `name`
- `sales`
- `amount`
- `order`
- `reference`
- `sold_at`
- `accountid`
- `totalprice`

## Myyntidatan rakenne

### L1 / L2 / L3

- `product_group_l1_name` puuttuu noin `30 120` riviltä.
- `product_group_l2_name` puuttuu noin `30 120` riviltä.
- `product_group_l3_name` puuttuu noin `30 120` riviltä.
- Täysi hierarkia on silti käytettävissä valtaosassa rivejä.

### Kattavuus

- `source_file` on täysi.
- `status` on täysi.
- `accountid` on täysi.
- `sold_at` on täysi.
- `productcode` puuttuu noin `269 495` riviltä.
- `category` puuttuu noin `276 218` riviltä.
- `reference` puuttuu noin `4 288` riviltä.
- `totalprice` puuttuu noin `794 747` riviltä.

## Arvot ja aggregaatit

Kun sarakkeet muunnetaan numeerisiksi:

- `sales` summa: `71 347 498`
- `amount` summa: `30 290 093`
- `totalprice` summa: `1 794 597`

## Laatuhavainnot

- Myyntidata on selvästi rikkaampi kuin nykyinen prospektimalli tarvitsee.
- Nykyinen malli ei käytä tuoteryhmähierarkiaa, vaikka se on jo aineistossa.
- `accountid` on vahva liitosavain account-masteriin.
- `sold_at` mahdollistaa ajallisen trendi- ja kausianalyysin.
- `product_group_l1_name`, `product_group_l2_name` ja `product_group_l3_name` antavat suoran pohjan tuoteryhmäpotentiaalille.

## Puuttuvat tiedot

Seuraavat asiat jäävät osittain puutteellisiksi:

- osa tuotteista ei ole linkattavissa `productcode`:lla
- osa riveistä on edelleen ilman `category`-luokkaa
- `totalprice` ei ole täysi, joten potentiaali kannattaa edelleen johtaa ensisijaisesti `sales`- tai muusta valmiiksi validoidusta summasta

## Johtopäätös

Uusi myyntihistoria on rakenteellisesti käyttökelpoinen sekä mallin opetusdataan että tuoteryhmäpotentiaalin rakentamiseen. Se ei kuitenkaan vielä yksin riitä prospektimallin nykyiseen `accountid -> business_id`-liitokseen, vaan rinnalle tarvitaan account-master.

