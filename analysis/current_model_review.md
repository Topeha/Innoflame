# Nykytilaraportti

Lähde: `prospektointi/prospect_model.py`, `prospektointi/prospect_pipeline.py`, `prospektointi/prospect_model_kuvaus.md`, `prospektointi/prospektimallin_muuttujayhteenveto.md`

## Nykyisen mallin logiikka

Nykyinen prospektimalli on käytännössä kaksivaiheinen:

1. Koulutetaan logistinen regressiomalli nykyasiakkaista.
2. Pisteytetään kaikki yritykset ja muutetaan score euromääräiseksi potentiaaliksi segmenttimediaanin ja baseline-kaavan avulla.

Päälogiikka löytyy tiedostosta [`prospektointi/prospect_model.py`](/C:/Users/TommiHavukainen/OneDrive%20-%20Unikie%20Oy/Customer/Innoflame/prospektointi/prospect_model.py):

- `build_modeling_frame()` kokoaa harjoitus- ja scoring-aineiston.
- `feature_columns()` määrittää mallin featuret.
- `train_model()` opettaa logistisen regression.
- `score_prospects()` laskee lopullisen rankingin ja potentiaalin.

## Nykyiset lähdeaineistot

Koodin mukaan nykyinen malli käyttää näitä tiedostoja:

- `Account_20.05.2026_combined_with_profinder.xlsx`
- `GoSystems_sales_26_05_2026_summarized.csv`
- `haku_Myyntiin_ai_2026-04-23 (1).xlsx`
- `Netvisor asiakastiedot 6-2026.xlsx`

Huomio:

- `prospect_model.py` lukee myyntidatan `created_year_month`-kentästä, joten sen inputin pitää olla kuukausitasoinen kooste.
- Ulkoinen poistolista on vapaaehtoinen, mutta jos tiedosto löytyy, sen `Y-tunnus`-arvot poistetaan prospekteista.

## Nykyinen feature engineering

Numeeriset featuret:

- `revenue_k_eur`
- `headcount`
- `growth_pct`
- `revenue_per_employee`
- `segment_lift`

Kategoriset featuret:

- `industry`
- `revenue_bucket`
- `headcount_bucket`
- `company_segment`
- `growth_bucket`
- `municipality`
- `region`

Featuret rakennetaan näin:

- liikevaihto ja henkilöstö luetaan Profinderista
- `revenue_bucket` johdetaan liikevaihdosta ja varasijaisesti liikevaihtoluokasta
- `headcount_bucket` johdetaan henkilöstöstä ja varasijaisesti henkilöstöluokasta
- `company_segment` muodostetaan yhdistämällä liikevaihto- ja henkilöstöluokka
- `revenue_per_employee` lasketaan liikevaihdosta ja henkilöstöstä
- `growth_bucket` johdetaan kasvuprosentista
- `segment_lift` lasketaan top-asiakkaiden segmenttiosumasta

## Nykyinen score-laskenta

Mallin lopullinen arvo muodostuu näin:

- `score = predict_proba(...)[:, 1]`
- `segment_median_value_eur` = top-asiakkaiden segmenttimediaani
- `model_value_eur = score * segment_median_value_eur`
- `baseline_value_eur = continuous_baseline_value(...)`
- `final_value_eur = 0.70 * model_value_eur + 0.30 * baseline_value_eur`
- `ennustettu potentiaali = round(final_value_eur)`

Ranking:

- `rank` perustuu `final_value_eur`-arvoon
- `priority` on `A/B/C/D` rank-sijoituksen mukaan

## Suodatussäännöt

Prospekti poistetaan, jos se on:

- nykyasiakas
- nykyasiakkaan emoyhtiö
- nykyasiakkaan konserniyhtiö
- ulkoisen poistolistan yritys
- manuaalisen nimisäännön osuma

Nykyinen manuaalinen nimipoisto on:

- `outokumpu`

## Mitä dataa malli tarvitsee toimiakseen

Pakolliset syötteet:

- yritysaineisto, jossa on `Y-tunnus`, nimi, toimiala, liikevaihto, henkilöstö, sijainti ja konsernitieto
- account-aineisto, jossa on `Business ID`, `ID` ja `customer_status`
- myyntiaineisto, jossa on `account_id`, `total_value` ja `created_year_month`

Malli ei vaadi suoraan kontaktitietoja laskentaan, mutta nykyinen output sisältää niitä myyntikäyttöä varten.

## Nykyisen mallin keskeiset havainnot

- Malli on edelleen rakenteeltaan kevyt ja läpinäkyvä.
- Se on vahvasti riippuvainen Profinderin `Y-tunnus`-tasoisesta identifioinnista.
- Tuoteryhmädataa ei käytetä nykyisessä prospektiscore-mallissa.
- Malli ei vielä hyödynnä nykyistä myyntihistoriaa tuoteryhmätasoisesti, vaikka dataa on jo saatavilla.

## Arvio

Nykyinen malli voidaan päivittää uuteen Profinder- ja myyntiaineistoon ilman kokonaisuudistusta, koska:

- peruskentät ovat edelleen olemassa
- join-avaimet ovat samat
- nykyinen score-logiikka nojaa yritystietoihin, ei kovakoodattuun lähdeformaattiin

Rakenteellinen uudelleenkirjoitus ei ole pakollinen. Suurin muutos on datan latauskerroksessa ja siinä, että uusi myyntidata pitää tuoda käyttöön siten, että nykyinen malli saa edelleen tarvitsemansa kuukausikoosteen tai vastaavan laskentakerroksen.

