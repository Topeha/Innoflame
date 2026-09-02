# Prospektimallin kuvaus

Tämä dokumentti kuvaa Innoflamen prospektimallin tarkoituksen, tarvittavat aineistot, tiedon käsittelyn, mallin ajamiseen vaadittavat tiedot ja syntyvät outputit.

## Tarkoitus

Prospektimallin tarkoitus on muodostaa myynnille priorisoitu lista yrityksistä, jotka muistuttavat parhaita nykyasiakkaita ja joilla arvioidaan olevan korkea myyntipotentiaali.

Malli:

- yhdistää asiakasrekisterin, myyntihistorian ja Profinder-yritysdatat
- opettaa mallin nykyasiakkaiden perusteella
- pisteyttää Profinder-aineiston yritykset
- poistaa nykyasiakkaat ja tunnistetut konserniosumat prospektilistalta
- laskee prospektille ennustetun euromääräisen potentiaalin
- tuottaa CSV- ja Excel-listan myynnin käyttöön

## Nykyinen toteutus

Mallikoodi on tiedostossa:

`prospect_model.py`

Nykyinen pääoutput:

`prospect_segment_model_all_prospects.csv`

Excel-versio:

`prospect_segment_model_all_prospects.xlsx`

Mallin metriikat:

`prospect_segment_model_all_prospects.metrics.json`

## Tarvittavat lähtöaineistot

Mallin ajamiseen tarvitaan kolme pääaineistoa.

### 1. Account-aineisto

Oletustiedosto:

`Account_20.05.2026_combined_with_profinder.xlsx`

Käyttötarkoitus:

- nykyasiakkaiden tunnistaminen
- myyntirivien yhdistäminen asiakkaisiin
- koulutusjoukon muodostaminen
- konsernirajauksen tekeminen

Pakolliset tai käytössä olevat sarakkeet:

- `Business ID`
- `ID`
- `customer_status`
- `Company Name`
- `Emoyhtiön Y-tunnus`

Tärkeät huomiot:

- `Business ID` normalisoidaan Y-tunnusmuotoon `1234567-8`
- `Emoyhtiön Y-tunnus` normalisoidaan samaan muotoon
- jos Excel lukee Y-tunnuksen numerona, esimerkiksi `18523029.0`, se muunnetaan ensin kokonaisluvuksi ja vasta sitten muotoon `1852302-9`
- koulutukseen hyväksytään vain statukset `Active` ja `Gokeep+`

### 2. Myyntidata

Oletustiedosto:

`GoSystems_sales_26_05_2026_summarized.csv`

Käyttötarkoitus:

- nykyasiakkaiden ostohistorian laskenta
- parhaiden asiakkaiden tunnistus
- mallin positiivisen luokan muodostaminen

Pakolliset tai käytössä olevat sarakkeet:

- `account_id`
- `total_value`
- `created_year_month`

Tärkeät huomiot:

- `account_id` yhdistetään Account-aineiston `ID`-kenttään
- `total_value` muunnetaan numeeriseksi
- `created_year_month` muunnetaan päivämääräksi kuukauden ensimmäiseen päivään
- oletuksena käytetään viimeisen 3 vuoden myyntihistoriaa

### 3. Profinder-/yritysaineisto

Oletustiedosto:

`haku_Myyntiin_ai_2026-04-23 (1).xlsx`

Käyttötarkoitus:

- pisteytettävien yritysten perusjoukko
- yritysprofiilien muodostaminen
- segmenttien ja potentiaalin laskenta

Pakolliset tai käytössä olevat sarakkeet:

- `Y-tunnus`
- `Virallinen nimi`
- `Markkinointinimi`
- `Emoyhtiön Y-tunnus`
- `Päätoimiala (Profinder)`
- `Liikevaihto (tuhatta €)`
- `Henkilöstö`
- `Liikevaihdon muutos (prosenttia)`
- `Liikevaihtoluokka`
- `Henkilökuntaluokka`
- `Kunta`
- `Maakunta`
- `Käyntiosoitteen postitoimipaikka`

Tärkeät huomiot:

- `Y-tunnus` normalisoidaan muotoon `1234567-8`
- `Emoyhtiön Y-tunnus` normalisoidaan samaan muotoon
- jos prospektiriviltä puuttuu `Emoyhtiön Y-tunnus`, käytetään sen tilalla yrityksen omaa `Y-tunnus` / `business_id` -arvoa
- yritykset deduplikoidaan `business_id`-kentän perusteella

## Tiedon käsittely

### 1. Y-tunnusten normalisointi

Kaikki Y-tunnukset muunnetaan samaan muotoon:

`1234567-8`

Normalisointi käsittelee seuraavia tilanteita:

- `FI`-alku poistetaan
- väliviivaton tunnus, kuten `18523029`, muutetaan muotoon `1852302-9`
- Excelin numeroksi lukema tunnus, kuten `18523029.0`, muunnetaan ensin muotoon `18523029`
- tyhjät tai virheelliset tunnukset jätetään tyhjiksi

### 2. Asiakasjoukon muodostaminen

Account-aineistosta muodostetaan nykyasiakkaiden tunnistejoukot:

- asiakkaan oma `business_id`
- asiakkaan `parent_business_id`, eli `Emoyhtiön Y-tunnus`

Näitä käytetään myöhemmin prospektien poistamiseen listalta.

### 3. Myyntihistorian laskenta

Myyntidata yhdistetään Account-aineistoon:

`sales.account_id -> accounts.ID`

Mukaan otetaan vain asiakkaat, joiden status on:

- `Active`
- `Gokeep+`

Tämän jälkeen lasketaan viimeisen 3 vuoden myynti:

- `sales_3y_total_eur`
- `avg_annual_sales_3y_eur = sales_3y_total_eur / 3`

Koulutusjoukkoon hyväksytään vain asiakkaat, joiden vuosikeskiarvo on vähintään:

`4 000 EUR`

### 4. Positiivisen luokan määritys

Mallin positiivinen luokka muodostetaan parhaista nykyasiakkaista.

Oletus:

`top_n_customers = 1000`

Eli:

- top 1 000 asiakasta 3 vuoden vuosikeskimyynnin perusteella saa labelin `1`
- muut nykyasiakkaat ovat vertailuryhmää

### 5. Yritysprofiilien muodostaminen

Profinder-aineistosta muodostetaan yritysprofiili.

Numeerisia muuttujia:

- `revenue_k_eur`
- `headcount`
- `growth_pct`
- `revenue_per_employee`
- `segment_lift`

Kategorisia muuttujia:

- `industry`
- `revenue_bucket`
- `headcount_bucket`
- `company_segment`
- `growth_bucket`
- `municipality`
- `region`

Lisäksi muodostetaan:

- `revenue_bucket`
- `headcount_bucket`
- `company_segment = revenue_bucket + "_" + headcount_bucket`
- `growth_bucket`
- `revenue_per_employee`

### 6. Segment lift

Segment lift kuvaa, kuinka vahvasti jokin yrityssegmentti esiintyy parhaiden asiakkaiden joukossa verrattuna kaikkiin asiakkaisiin.

Periaate:

`segment_lift = top-asiakkaiden segmenttiosuus / kaikkien asiakkaiden segmenttiosuus`

Korkea lift tarkoittaa, että segmentti on yliedustettuna parhaissa asiakkaissa.

### 7. Mallin koulutus

Nykyinen malli on:

`LogisticRegression`

Malliputki:

- numeeriset muuttujat:
  - puuttuvat arvot täytetään mediaanilla
  - muuttujat skaalataan
- kategoriset muuttujat:
  - puuttuvat arvot täytetään arvolla `unknown`
  - muuttujat one-hot-enkoodataan
- luokittelijana logistinen regressio
- `class_weight="balanced"`

Train/test-jako:

- testiosuus `20 %`
- satunnaissiemen `42`
- stratified split labelin mukaan

Metriikat:

- `roc_auc`
- `average_precision`
- `train_rows`
- `test_rows`
- `positive_rate`

## Prospektien poistosäännöt

Prospekti poistetaan lopulliselta listalta, jos jokin seuraavista täyttyy:

1. Prospektin oma `business_id` löytyy Account-aineiston `Business ID` -arvoista.
2. Prospektin oma `business_id` löytyy Account-aineiston `Emoyhtiön Y-tunnus` -arvoista.
3. Prospektin `parent_business_id` löytyy Account-aineiston `Business ID` -arvoista.
4. Prospektin `parent_business_id` löytyy Account-aineiston `Emoyhtiön Y-tunnus` -arvoista.
5. Prospektin nimi tai markkinointinimi sisältää manuaalisessa poistolistassa olevan konsernitermin.

Lisäsääntö:

- jos prospektin `Emoyhtiön Y-tunnus` puuttuu, `parent_business_id` asetetaan samaksi kuin prospektin oma `business_id`

Tämä estää tilanteita, joissa emoyhtiö jää prospektiksi vain siksi, että sen omalta riviltä puuttuu parent-tieto.

Nykyinen manuaalinen poistolista:

- `Outokumpu`

Tämä lisättiin, koska Account-aineistossa on `Outokumpu Oyj` nykyasiakkaana, mutta Profinder-aineiston Outokumpu-yhtiöt eivät yhdisty Account-aineistoon Y-tunnus- tai emoyhtiötunnisteilla.

## Prospektien pisteytys

Mallin tuottama `score` on todennäköisyystyyppinen arvo välillä 0-1.

Mitä suurempi `score`, sitä enemmän yrityksen profiili muistuttaa parhaita nykyasiakkaita.

## Potentiaalin laskenta

Lopullinen potentiaali ei perustu pelkkään scoreen, vaan yhdistää kolme asiaa:

- mallin score
- segmenttikohtainen asiakasmediaani
- yrityksen kokopohjainen baseline

### Segmenttikohtainen mediaani

Parhaista nykyasiakkaista lasketaan mediaanimyynti segmenteittäin.

`segment_median_value_eur`

Jos prospektin segmentille ei löydy omaa mediaania, käytetään kaikkien top-asiakkaiden mediaania.

### Malliarvo

`model_value_eur = score * segment_median_value_eur`

### Jatkuva baseline

Baseline huomioi:

- liikevaihdon
- henkilöstömäärän
- segment liftin

Baseline ei ole porrastettu luokkataulukko, vaan jatkuva funktio.

### Lopullinen potentiaali

Nykyinen kaava:

`final_value_eur = 0.70 * model_value_eur + 0.30 * baseline_value_eur`

Outputissa tämä näkyy sarakkeessa:

`ennustettu potentiaali`

## Output-sarakkeet

Lopullinen prospektilista sisältää muun muassa:

- `rank`
- `priority`
- `company`
- `business_id`
- `parent_business_id`
- `score`
- `segment_median_value_eur`
- `model_value_eur`
- `baseline_value_eur`
- `ennustettu potentiaali`
- `avg_annual_sales_3y_eur`
- `revenue_k_eur`
- `revenue_class`
- `headcount_class`
- `company_segment`
- `segment_lift`
- `industry`
- `growth_bucket`
- `positive_signals`
- `reference_date`

## Priority-luokat

Priority määräytyy rankin perusteella:

- `A`: rank 1-100
- `B`: rank 101-500
- `C`: rank 501-1000
- `D`: rank yli 1000

## Positive signals

`positive_signals` on selittävä tekstikenttä myynnille.

Se voi sisältää esimerkiksi:

- vahva segmenttiosuma
- liikevaihtoluokka
- henkilöstöluokka
- kasvuluokka
- toimiala

Tämän tarkoitus on auttaa myyjää ymmärtämään, miksi yritys nousi listalle.

## Mallin ajaminen

Perusajo oletusaineistoilla:

```powershell
& 'C:\Users\TommiHavukainen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  'C:\Users\TommiHavukainen\OneDrive - Unikie Oy\Customer\Innoflame\prospect_model.py' `
  --output 'C:\Users\TommiHavukainen\OneDrive - Unikie Oy\Customer\Innoflame\prospect_segment_model_all_prospects.csv'
```

Ajossa voi vaihtaa aineistot parametreilla:

```powershell
--accounts <Account Excel -tiedosto>
--sales <myyntidata CSV>
--companies <Profinder Excel -tiedosto>
--output <output CSV>
--top-n-customers <positiivisen luokan koko>
--lookback-days <myyntihistorian pituus päivinä>
--min-training-customer-annual-sales-eur <minimimyynti koulutusjoukkoon>
--random-state <satunnaissiemen>
```

## Tämänhetkisen ajon pääluvut

Viimeisimmässä ajossa:

- prospekteja: `2 655`
- potentiaali yhteensä: noin `61,4 MEUR`
- mediaanipotentiaali: `18,4 kEUR`
- keskiarvopotentiaali: `23,2 kEUR`
- top 100 potentiaali: noin `9,6 MEUR`
- ROC AUC: `0.675`
- Average Precision: `0.230`

## Tunnetut rajoitteet

1. Konsernirajaus toimii vain, jos aineistossa on oikea `Emoyhtiön Y-tunnus` tai jos yhtiön oma tunnus vastaa poistettavaa tunnusta.
2. Jos konsernirakenne puuttuu lähdedatasta kokonaan, malli ei voi päätellä konsernia pelkästä nimestä luotettavasti.
3. Nimitason osumia ei poisteta automaattisesti, koska ne voivat aiheuttaa false positive -poistoja.
4. Potentiaali on priorisointiarvio, ei tarjous, budjetti tai varma ostomäärä.
5. Malli tarvitsee säännöllisesti päivitetyt Account-, myynti- ja Profinder-aineistot pysyäkseen hyödyllisenä.

## Suositeltu jatkokehitys

- lisää erillinen konsernitaulu, jossa on käsin tai luotettavasta lähteestä ylläpidetty konserni-id
- lisää raportti poistetuista prospekteista ja poiston syystä
- lisää nimitason tarkistuslistaus, mutta ei automaattista poistoa ilman hyväksyntää
- rakenna myöhemmin erillinen regressiomalli euromääräiselle potentiaalille
- lisää malliajon yhteyteen automaattinen laaturaportti: rivimäärät, poistot, top-lista, tunnisteosumat ja nimitason mahdolliset osumat
