# Innoflamen prospektimalli: tekninen kuvaus

## 1. Tiivistelmä

Prospektimalli on valvottu koneoppimismalli, joka etsii Profinderin yritysjoukosta nykyasiakasprofiilia muistuttavia yrityksiä. Malli opetetaan Innoflamen nykyasiakkaiden avulla ja pisteyttää sen jälkeen koko Profinder-yritysjoukon.

Mallin päätulos on järjestetty prospektilista, ei binäärinen kyllä/ei-päätös. Korkea sijoitus tarkoittaa, että yritys muistuttaa mallin käyttämää parasta asiakasjoukkoa ja sillä on mallin mukaan korkeampi kaupallinen potentiaali.

## 2. Käsittelyketju

```text
GoSystems-asiakkaat ─┐
GoSystems-myynti ────┼─> liitokset ja 3 vuoden asiakaspiirteet
Profinder-yritykset ─┘              │
                                    v
                         positiivinen asiakasluokka
                                    │
                                    v
                         logistinen regressio
                                    │
                                    v
                         kaikkien yritysten score
                                    │
                 nykyasiakkaat / konsernit / poistolistat pois
                                    │
                                    v
                segmenttiarvo + baselinearvo -> potentiaali -> rank
```

## 3. Opetusjoukko

### Nykyasiakkaat

Asiakasrekisterin `ID` yhdistetään myyntiaineiston `account_id`-kenttään. Yrityksen tunnisteena käytetään normalisoitua Y-tunnusta.

Opetukseen hyväksytään asiakasstatukset:

- `Active`
- `Gokeep+`

Myyntihistoriasta käytetään viimeisen noin kolmen vuoden aikajaksoa. Asiakkaalle lasketaan:

```text
sales_3y_total_eur = viimeisen 3 vuoden myynti
avg_annual_sales_3y_eur = sales_3y_total_eur / 3
```

Asiakkaat, joiden vuositasolle muunnettu myynti jää alle 4 000 euroon, jätetään mallin opetusjoukon ulkopuolelle.

### Positiivinen luokka

Positiiviseksi luokaksi määritellään `top_n_customers`-parametrin mukainen joukko parhaista nykyasiakkaista. Nykyisessä ajossa:

- `top_n_customers = 1000`
- parhaat asiakkaat järjestetään `avg_annual_sales_3y_eur`-arvon perusteella
- näille yrityksille annetaan `label = 1`
- muut koulutukseen kuuluvat nykyasiakkaat saavat `label = 0`

## 4. Muodostetut piirteet

### Numeeriset piirteet

- `revenue_k_eur`: liikevaihto tuhansina euroina
- `headcount`: henkilöstömäärä
- `growth_pct`: liikevaihdon muutosprosentti
- `revenue_per_employee`: liikevaihto / henkilöstö
- `segment_lift`: segmentin yliedustus parhaissa asiakkaissa

`revenue_per_employee` lasketaan vain, jos henkilöstömäärä on suurempi kuin nolla.

### Luokittelevat piirteet

- `industry`
- `revenue_bucket`
- `headcount_bucket`
- `company_segment`
- `growth_bucket`
- `municipality`
- `region`

Liikevaihto luokitellaan luokkiin `0-1M`, `1-5M`, `5-20M`, `20-100M` ja `100M+`. Henkilöstö luokitellaan luokkiin `1-10`, `10-50`, `50-250`, `250-1000` ja `1000+`.

Kasvuluokat ovat:

- `decline`: alle -5 %
- `stable`: -5 %–5 %
- `growth`: 5 %–20 %
- `high_growth`: yli 20 %

## 5. Segment lift

`segment_lift` kertoo, onko yrityksen koko- ja henkilöstösegmentti yliedustettuna parhaissa asiakkaissa suhteessa kaikkiin nykyasiakkaisiin.

```text
segment_lift =
  parhaiden asiakkaiden segmenttiosuus /
  kaikkien nykyasiakkaiden segmenttiosuus
```

Esimerkiksi lift 1,50 tarkoittaa, että segmenttiä esiintyy parhaissa asiakkaissa 1,5 kertaa sen verran kuin koko nykyasiakasjoukossa suhteellisesti odotettaisiin.

## 6. Käytetyt analyyttiset mallit

### 6.1 Logistinen regressio

Varsinainen pisteytys tehdään logistisella regressiolla.

Esikäsittely:

- numeeristen arvojen puuttuvat arvot korvataan mediaanilla
- numeeriset muuttujat standardoidaan `StandardScaler`-muunnoksella
- luokittelevien muuttujien puuttuvat arvot täytetään arvolla `unknown`
- luokittelevat muuttujat muunnetaan one-hot-koodaukseksi
- tuntemattomat kategoriat hyväksytään ilman mallin kaatumista

Luokitin käyttää:

- `LogisticRegression`
- `max_iter = 1000`
- `class_weight = balanced`

Mallin `score` on `predict_proba(... )[:, 1]`, eli logistisen regression tuottama positiivisen luokan piste. Sitä käytetään ennen kaikkea yritysten keskinäiseen järjestämiseen.

### 6.2 Segmentin mediaaniarvo

Jokaiselle prospektille lasketaan oman `company_segment`-segmentin parhaiden asiakkaiden mediaanimyynti:

```text
segment_median_value_eur =
parhaiden asiakkaiden segmentin avg_annual_sales_3y_eur-mediaani
```

Jos segmentiltä ei löydy riittävästi arvoa, käytetään parhaiden asiakkaiden kokonaismediaania.

### 6.3 Malliarvo

```text
model_value_eur = score * segment_median_value_eur
```

Tämä yhdistää profiilin samankaltaisuuden ja vastaavan parhaiden asiakkaiden tyypillisen vuosimyynnin.

### 6.4 Jatkuva baseline-arvo

Erillinen baseline käyttää yrityksen kokoa ja segmentin lift-arvoa. Se perustuu liikevaihdon ja henkilöstön logaritmisiin muunnoksiin, jotta hyvin suuret yritykset eivät dominoi laskentaa suoraan lineaarisesti.

Baseline sisältää:

- liikevaihtokomponentin
- henkilöstökomponentin
- segment lift -kertoimen, joka rajataan välille 0,7–1,8

Baseline ei ole toinen opetettu koneoppimismalli, vaan jatkuva vertailuarvo, joka vakauttaa potentiaalilaskentaa yrityksen koon suhteen.

### 6.5 Lopullinen potentiaali

```text
final_value_eur =
  0,70 * model_value_eur +
  0,30 * baseline_value_eur
```

Tulosteessa tämä pyöristetään kenttään `ennustettu potentiaali`.

## 7. Poistot ennen lopullista listaa

Yritys poistetaan prospektilistalta, jos jokin seuraavista täyttyy:

- yritys löytyy nykyasiakkaan omalla Y-tunnuksella
- yrityksen Y-tunnus löytyy emoyhtiö- tai konsernirajauksesta
- Y-tunnus löytyy ulkoisesta poistolistasta
- yrityksen nimessä on manuaalisesti poissuljettu termi, nykykoodissa `outokumpu`
- yritykseltä puuttuu Y-tunnus tai yritysnimi

Nykyisellä uusinta-ajolla lopullinen prospektimäärä oli 1 956.

## 8. Mallin validointi

Opetusdata jaetaan:

- 80 % train-aineistoon
- 20 % test-aineistoon
- jako on stratified
- `random_state = 42`

Raportoitavat mittarit ovat:

### ROC-AUC

Kuvaa mallin kykyä järjestää positiiviset yritykset negatiivisia korkeammalle eri kynnysarvoilla.

### Average precision

Kuvaa positiivisten yritysten löytymisen laatua erityisesti tilanteessa, jossa positiivinen luokka on vähemmistössä. Prospektoinnissa tämä on usein käytännöllinen lisämittari ROC-AUC:n rinnalle.

Nykyisen uusinta-ajon mittarit:

- ROC-AUC: 0,662
- Average precision: 0,317
- train-rivejä: 1 304
- test-rivejä: 326
- positiivinen osuus: 20,8 %

Mittarit kuvaavat mallin erottelukykyä testijaossa. Ne eivät kerro suoraan tulevan myynnin euroista.

## 9. Mitä malli ei tee

Malli ei:

- ennusta varmasti toteutuvaa tilausta
- optimoi katetta tai kannattavuutta
- arvioi myynnin kapasiteettia tai yhteydenoton onnistumista
- mallinna myyntiputken vaiheita
- tee kausaalipäätelmää siitä, mikä yrityksessä aiheuttaa ostamisen
- korvaa myyjän yritys- ja kontaktitason tarkistusta

## 10. Muut mallikomponentit projektissa

Projektissa on myös muita, erillisiä mallikomponentteja:

- `prospektointi/prospect_pipeline.py`: vaihtoehtoinen lead scoring- ja tuoterekomendaatioputki, joka voi käyttää tiedostolähteiden lisäksi BigQuery-lähteitä konfiguraation perusteella
- `prospektointi/run_current_customer_potential.py`: nykyasiakkaiden potentiaali- ja tuoteryhmäajot
- `backtest_2025_model_improvements.py`: malliparannusten backtestit ja vuoden 2025 validointi
- `run_product_group_submodel.py`: tuoteryhmäkohtainen potentiaali- ja suosituslaskenta

Tämä dokumentti kuvaa ensisijaisesti `prospect_model.py`-mallia ja sen tuottamaa prospektilistaa. Muita komponentteja ei pidä tulkita saman ajon sisäisiksi osiksi ilman erillistä konfiguraatio- ja versiontarkistusta.
