# Feature-ehdotukset

## Nykyiset featuret

Nykyinen malli käyttää:

- `revenue_k_eur`
- `headcount`
- `growth_pct`
- `revenue_per_employee`
- `segment_lift`
- `industry`
- `revenue_bucket`
- `headcount_bucket`
- `company_segment`
- `growth_bucket`
- `municipality`
- `region`

## Uuden Profinder-aineiston mahdollistamat parannukset

### 1. TOL2025-pohjainen toimiala

Nykyinen malli käyttää pääosin `Päätoimiala (Profinder)`-kenttää.

Suositus:

- lisää `Päätoimiala (TOL2025)` featureksi
- pidä `Päätoimiala (Profinder)` varafutuurina tai selitetekstinä

### 2. Toimialapolku

Suositus:

- rakenna toimialapolku `Päätoimiala (TOL2025)` + `Sivutoimialat (TOL2025)`
- käytä sitä tuoteryhmäehdotuksen taustatietona

### 3. Konsernirakenne

Suositus:

- lisää `Emoyhtiön Y-tunnus`
- lisää konserni-indikaattori, esimerkiksi `is_parent_company`, `is_group_child`
- lisää konsernin koko esimerkiksi konsernin yritysmäärä tai osumajoukko, jos se voidaan laskea

### 4. Päättäjätiedot

Suositus:

- lisää `Päättäjän vastuualue`
- lisää `Titteli`
- lisää `Tehtävänimike`
- lisää `Päättäjän puhelinnumero`
- lisää `Päättäjän sähköpostiosoite`

Nämä eivät välttämättä kuulu score-mallin ytimeen, mutta ovat arvokkaita käyttökelpoisessa myyntilistassa.

### 5. Sijainti

Suositus:

- käytä `Kunta`
- käytä `Maakunta`
- lisää tarvittaessa alueen binning, jos myyntiorganisaatio toimii alueittain

### 6. Kokoluokka

Suositus:

- pidä `Liikevaihto (tuhatta €)` ja `Henkilöstö` numeerisina featureina
- säilytä `Liikevaihtoluokka` ja `Henkilökuntaluokka` fallbackeina

### 7. Kasvu ja riski

Suositus:

- lisää `Kasvuluokka`
- lisää `Riskiluokka`
- lisää `Mobility-luokka`

## Uuden myyntidatan mahdollistamat featuret

### 1. Tuoteryhmäpreferenssi

Suositus:

- lasketaan asiakkaan ostohistoriasta L1/L2/L3-jakauma
- käytetään frekvenssiä, euromäärää ja tuoreutta

Mahdolliset featuret:

- `top_l1_group`
- `top_l2_group`
- `top_l3_group`
- `l1_group_entropy`
- `l2_group_entropy`
- `l3_group_entropy`
- `last_purchase_days`
- `purchase_recency_weighted_l1_share`

### 2. Ostokäyttäytyminen

Suositus:

- `sales_3y_total_eur`
- `order_count_3y`
- `distinct_products_3y`
- `distinct_product_groups_l1_3y`
- `distinct_product_groups_l2_3y`
- `distinct_product_groups_l3_3y`

### 3. Toimitus- ja käsittelykulut

Jos delivery/handling-kentät ovat mukana luotettavasti:

- `delivery_fee_total`
- `handling_fee_total`
- `delivery_fee_share`
- `handling_fee_share`

## Featuret, jotka kannattaa säilyttää

- `segment_lift`
- `company_segment`
- `revenue_per_employee`
- `growth_bucket`

Nämä ovat läpinäkyviä ja tukevat nykyistä mallia hyvin.

## Featuret, jotka kannattaa lisätä seuraavassa versiossa

1. `Päätoimiala (TOL2025)`
2. `Emoyhtiön Y-tunnus`
3. `Kasvuluokka`
4. `Riskiluokka`
5. `Päättäjän vastuualue`
6. L1/L2/L3-tuoteryhmäpreferenssit
7. Tuoreushistoria ostokäyttäytymisestä

