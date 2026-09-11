# Innoflamen prospektimalli: tekninen kuvaus

## 1. Tiivistelmä

Prospektimalli on valvottu koneoppimismalli, joka etsii uusimman Profinder-aineiston yritysjoukosta Innoflamen nykyasiakasprofiilia muistuttavia yrityksiä. Malli opetetaan Innoflamen nykyasiakkaiden ja päivitetyn myyntihistorian avulla ja pisteyttää sen jälkeen Profinder-yritysjoukon.

Mallin päätulos on järjestetty prospektilista, ei binäärinen kyllä/ei-päätös. Korkea sijoitus tarkoittaa, että yritys muistuttaa mallin käyttämää parasta asiakasjoukkoa ja sillä on mallin mukaan korkeampi kaupallinen potentiaali. Viimeisin toteutettu ajo tuotti 7 545 yrityksen mallilistan ennen erillisiä Netvisor- ja aiemman prospektilistan poistoja. Näiden liiketoimintasääntöjen jälkeen lopullinen uusi prospektilista sisältää 4 563 yritystä.

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
                 nykyasiakkaat / konsernit / nimitermit pois
                                    │
                                    v
                segmenttiarvo + baselinearvo -> potentiaali -> rank
                                    │
                                    v
          Netvisor- ja aiemman prospektilistan jälkisuodatus
```

### 2.1 Viimeisimmän ajon lähteet

Uusimman toteutetun ajon käytetyt aineistot ovat:

- Profinder: `haku_Prospektointimasterlista_2026-08-12.xlsx`
- Asiakasrekisteri: `Account_20.05.2026_combined.xlsx` (ajossa käytetty paikallinen työskentelykopio)
- Myyntihistoria: `prospektointi/sales_import_test/GoSystems_sales_26_05_2026_model_input_corrected.csv`
- Netvisor-jälkisuodatus: `potentiaali/Netvisor asiakastiedot 6-2026_y_tunnukset_normalisoitu.xlsx`

Profinder-aineistossa on 10 715 yksilöityä Y-tunnusta. Päivitetty myyntiaineisto on mallin aggregoitu syöte, jossa on 27 283 riviä, 4 844 asiakasta ja ajanjakso 2023-01–2026-08. Myyntisyötteessä ovat mukana L1-, L2- ja L3-tuoteryhmät sekä toimitus- ja käsittelymaksut.

## 3. Opetusjoukko

### Nykyasiakkaat

Asiakasrekisterin `ID` yhdistetään myyntiaineiston `account_id`-kenttään. Yrityksen tunnisteena käytetään normalisoitua Y-tunnusta.

Opetukseen hyväksytään asiakasstatukset:

- `Active`
- `Gokeep+`

Myyntihistoriasta käytetään viimeisen noin kolmen vuoden aikajaksoa. Päivitetyn syötteen aikajakso on 2023-01–2026-08. Asiakkaalle lasketaan:

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

Liikevaihto luokitellaan luokkiin `0-1M`, `1-5M`, `5-20M`, `20-100M` ja `100M+`. Henkilöstön numeeriset arvot luokitellaan luokkiin `1-10`, `10-50`, `50-250`, `250-1000` ja `1000+`. Profinderin tekstiluokat muunnetaan näin: `1-9` -> `1-10`, `10-19` ja `20-49` -> `10-50`, `50-99` ja `100-249` -> `50-250`, `250-499` ja `500-999` -> `250-1000`, ja `>999` -> `1000+`. Siksi Profinderin `20-49`-yritykset ovat mallissa mukana.

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
- Y-tunnus löytyy ajon aikana käytetystä ulkoisesta poistolistasta
- yrityksen nimessä on manuaalisesti poissuljettu termi, nykykoodissa `outokumpu`
- yritykseltä puuttuu Y-tunnus tai yritysnimi

Viimeisimmässä Profinder-ajossa mallin oma tulos oli 7 545 yritystä. Netvisor-poisto tehtiin erillisenä jälkikäsittelynä. Y-tunnukset normalisoidaan ennen vertailua muotoon `1234567-8`; esimerkiksi `FI09508951` muuttuu muotoon `0950895-1`. Tämän jälkeen Netvisorissa olevat yritykset poistetaan. Kun lisäksi aiemmalla prospektilistalla olleet yritykset poistetaan, lopulliseen uuteen listaan jäi 4 563 yritystä. Lopullisen listan uudelleentarkistuksessa ei ollut yhtään normalisoidulla Y-tunnuksella löytynyttä Netvisor-osumaa.

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

Viimeisimmän Profinder- ja päivitetyn myyntihistorian ajon mittarit:

- ROC-AUC: 0,7217
- Average precision: 0,2807
- train-rivejä: 1 994
- test-rivejä: 499
- positiivinen osuus: 15,3 %

Mittarit kuvaavat mallin erottelukykyä testijaossa. Ne eivät kerro suoraan tulevan myynnin euroista. Netvisor- ja aiemman prospektilistan poistot tehdään score-laskennan jälkeen, joten yllä olevat mittarit kuvaavat mallia ennen näitä liiketoimintasuodattimia.

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

## 11. Uusimman ajon toteutusohje

Uusi ajo toteutetaan seuraavassa järjestyksessä:

1. Lue uusin Profinder-aineisto ja normalisoi Y-tunnukset.
2. Lue asiakasrekisteri ja päivitetty aggregoitu myyntisyöte.
3. Yhdistä asiakasrekisteri myyntiin `account_id`-avaimella ja yritysaineistot normalisoidulla Y-tunnuksella.
4. Muodosta asiakaspiirteet, positiivinen luokka, segmenttilift, logistisen regression score, potentiaali ja rank.
5. Poista nykyasiakkaat, konserniin kuuluvat yritykset, puuttuvan Y-tunnuksen tai nimen rivit sekä manuaaliset nimitermit.
6. Vie mallin raakatulos erilliseen tiedostoon.
7. Normalisoi Netvisorin Y-tunnukset samaan muotoon ja poista Netvisor-osumat.
8. Poista tarvittaessa myös aiemman prospektilistan yritykset, jos tavoitteena on vain uudet prospektit.
9. Tarkista lopputulos: rivimäärä, yksilöidyt Y-tunnukset, Netvisor-osumat ja puuttuvat avainkentät.

Mallin tekninen suorituslogiikka on lähdekoodissa `prospektointi/prospect_model.py`. Tulosten jälkisuodatusta ja vertailua ei pidä yhdistää score-laskentaan, koska ne ovat erillisiä liiketoimintasääntöjä.
