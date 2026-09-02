# Prospektimallin muuttujayhteenveto

Tämä yhteenveto kuvaa nykyisen prospektimallin muuttujat: miten saraketta luetaan, mistä tieto tulee ja miten laskennalliset muuttujat muodostetaan.

Tarkastelun pääkohde on `prospect_segment_model_all_prospects.csv`. Myynnille tallennettava Excel `prospect_segment_model_all_prospects_yhteystiedoilla_tallennettava.xlsx` sisältää suppeamman version samoista tiedoista: siitä on poistettu osa mallin sisäisistä arvoista, kuten `score`, `segment_median_value_eur`, `model_value_eur`, `baseline_value_eur`, `avg_annual_sales_3y_eur` ja `reference_date`.

## Lähdeaineistot

| Lähde | Käyttö mallissa |
| --- | --- |
| `haku_Myyntiin_ai_2026-04-23 (1).xlsx` | Profinder-/yritysaineisto. Tästä tulevat yritysten perustiedot, yhteystiedot, toimiala, liikevaihto, henkilöstö, kasvutieto, sijainti ja emoyhtiötunnus. |
| `Account_20.05.2026_combined_with_profinder.xlsx` | Nykyasiakkaiden tunnistus, asiakasstatus, Account ID -liitos myyntidataan ja konsernipoistot. |
| `GoSystems_sales_26_05_2026_summarized.csv` | Myyntihistoria. Tästä lasketaan asiakkaiden 3 vuoden myynti ja vuosikeskiarvo. |
| `Netvisor asiakastiedot 6-2026.xlsx` | Ulkoinen poistolista: Y-tunnukset poistetaan prospektilistalta, jos ne löytyvät Netvisor-aineistosta. |

Y-tunnukset normalisoidaan mallissa samaan muotoon `1234567-8`: `FI`-alku poistetaan, pelkät numerot muutetaan väliviivalliseen muotoon ja Excelin numeroksi lukemat tunnukset käsitellään kokonaislukuina.

## Lopputiedoston muuttujat

| Muuttuja | Miten luetaan | Mistä tulee / miten muodostetaan |
| --- | --- | --- |
| `rank` | Prospektin sijoitus potentiaalin mukaan. `1` on paras. | Lasketaan `final_value_eur`-arvosta: suurempi potentiaali saa paremman sijan. Tasatilanteissa säilytetään järjestys `rank(method="first")`. |
| `priority` | Myynnin prioriteettiluokka. | Johdetaan `rank`-arvosta: A = 1-100, B = 101-500, C = 501-1000, D = yli 1000. |
| `company` | Yrityksen näytettävä nimi. | Profinderin `Virallinen nimi`; jos puuttuu, käytetään `Markkinointinimi`; jos sekin puuttuu, käytetään `business_id`. |
| `business_id` | Yrityksen oma Y-tunnus normalisoituna. | Profinderin `Y-tunnus`, normalisoitu mallin `normalize_business_id`-funktiolla. |
| `parent_business_id` | Konserni-/emoyhtiötunnus normalisoituna. | Profinderin `Emoyhtiön Y-tunnus`; jos puuttuu, asetetaan samaksi kuin `business_id`. Käytetään konsernipoistoihin. |
| `Puhelinnumero` | Yrityksen puhelinnumero. | Suoraan Profinder-aineiston `Puhelinnumero`-sarakkeesta. Ei mallilaskentaa. |
| `Sähköpostiosoite` | Yrityksen sähköpostiosoite. | Suoraan Profinder-aineiston `Sähköpostiosoite`-sarakkeesta. Ei mallilaskentaa. |
| `Päättäjän vastuualue` | Kontaktihenkilön vastuualue. | Suoraan Profinder-aineistosta. Ei mallilaskentaa. |
| `Tehtävänimike` | Kontaktihenkilön tehtävänimike. | Suoraan Profinder-aineistosta. Ei mallilaskentaa. |
| `Titteli` | Kontaktihenkilön titteli. | Suoraan Profinder-aineistosta. Ei mallilaskentaa. |
| `Etunimi` | Kontaktihenkilön etunimi. | Suoraan Profinder-aineistosta. Ei mallilaskentaa. |
| `Sukunimi` | Kontaktihenkilön sukunimi. | Suoraan Profinder-aineistosta. Ei mallilaskentaa. |
| `Päättäjän puhelinnumero` | Kontaktihenkilön puhelinnumero. | Suoraan Profinder-aineistosta. Ei mallilaskentaa. |
| `score` | Mallin todennäköisyystyyppinen osuma-arvo välillä 0-1. Mitä suurempi arvo, sitä enemmän yritys muistuttaa parhaita nykyasiakkaita. | Logistisen regressiomallin `predict_proba`-tulos. Malli käyttää numeerisia ja kategorisia yrityspiirteitä. |
| `segment_median_value_eur` | Prospektin segmentille laskettu tyypillinen vuosimyyntitaso euroina. | Top-asiakkaista lasketaan `avg_annual_sales_3y_eur`-mediaani per `company_segment`. Jos segmentille ei löydy mediaania, käytetään kaikkien top-asiakkaiden mediaania. |
| `model_value_eur` | Mallin scoreen perustuva euromääräinen arvo. | `score * segment_median_value_eur`. |
| `baseline_value_eur` | Yrityksen koosta ja segmenttiosumasta laskettu jatkuva baseline-arvo. | Lasketaan liikevaihdosta, henkilöstöstä ja `segment_lift`-arvosta: `(revenue_component + headcount_component) * lift_component`. |
| `ennustettu potentiaali` | Lopullinen myynnille näytettävä potentiaali euroina. | Pyöristetty kokonaisluvuksi kaavasta `0.70 * model_value_eur + 0.30 * baseline_value_eur`. |
| `avg_annual_sales_3y_eur` | Nykyasiakkaan keskimääräinen vuosimyynti viimeiseltä 3 vuodelta. Prospekteilla yleensä tyhjä. | Myyntidatasta: viimeisen 3 vuoden `total_value` summataan per asiakas ja jaetaan kolmella. |
| `revenue_k_eur` | Yrityksen liikevaihto tuhansina euroina. | Profinderin `Liikevaihto (tuhatta €)`, muunnetaan numeeriseksi. |
| `revenue_class` | Profinderin oma liikevaihtoluokka. | Suoraan Profinderin `Liikevaihtoluokka`-sarakkeesta. Käytetään varalla `revenue_bucket`-luokan muodostuksessa. |
| `headcount_class` | Profinderin oma henkilöstöluokka. | Suoraan Profinderin `Henkilökuntaluokka`-sarakkeesta. Käytetään ensisijaisesti `headcount_bucket`-luokan muodostuksessa. |
| `company_segment` | Yrityksen koko-/segmenttiluokka. | Johdetaan muodossa `revenue_bucket + "_" + headcount_bucket`, esimerkiksi `100M+_1000+`. |
| `segment_lift` | Kuinka vahvasti segmentti esiintyy top-asiakkaissa suhteessa kaikkiin asiakkaisiin. Yli 1 tarkoittaa yliedustusta. | `top-asiakkaiden segmenttiosuus / kaikkien nykyasiakkaiden segmenttiosuus`. Puuttuvat arvot täytetään nollalla. |
| `industry` | Yrityksen toimiala. | Profinderin `Päätoimiala (Profinder)`. Käytetään mallin kategorisena muuttujana ja `positive_signals`-tekstissä. |
| `growth_bucket` | Kasvuluokka mallia varten. | Johdetaan `growth_pct`-arvosta: alle -5 = `decline`, -5...5 = `stable`, 5...20 = `growth`, yli 20 = `high_growth`. |
| `positive_signals` | Myynnille luettava selitysteksti siitä, miksi yritys nousi listalle. | Rakennetaan säännöillä: mukaan otetaan enintään 4 signaalia, kuten vahva segmenttiosuma, liikevaihtoluokka, henkilöstöluokka, kasvuluokka ja toimiala. |
| `reference_date` | Malliajon myyntihistorian viimeisin kuukausi/päivä. | Myyntidatan `created_year_month` muunnetaan päivämääräksi ja suurin arvo otetaan referenssipäiväksi. |
| `Emoyhtiön Y-tunnus` | Emoyhtiön Y-tunnus myynnille tutulla sarakenimellä. | Profinder-lähtösarake. Sisällöltään vastaa käytännössä `parent_business_id`-tunnusta, mutta sarake on säilytetty alkuperäisellä nimellä tallennettavassa outputissa. |

## Mallin sisäiset muuttujat ja laskennat

| Muuttuja | Miten luetaan | Miten muodostetaan |
| --- | --- | --- |
| `account_id` | Account-aineiston numeerinen asiakastunniste. | Accountin `ID` muunnetaan numeroksi. Myyntidatan `account_id` liittyy tähän. |
| `customer_status` | Asiakkaan status koulutuskelpoisuuden arviointiin. | Account-aineiston `customer_status`; malliin hyväksytään vain `Active` ja `Gokeep+`. |
| `sales_3y_total_eur` | Asiakkaan kokonaismyynti 3 vuoden tarkastelujaksolla. | Myyntidatan `total_value` summataan per `business_id` viimeisen `lookback_days = 365 * 3` päivän ajalta. |
| `current_customer` | Onko yritys nykyasiakas. | `1`, jos Profinderin `business_id` löytyy Account-aineiston Y-tunnuksista, muuten `0`. |
| `label` | Mallin opetuksen tavoitemuuttuja. | `1`, jos nykyasiakas kuuluu top 1000 asiakkaaseen `avg_annual_sales_3y_eur`-arvon perusteella; muuten `0`. |
| `growth_pct` | Liikevaihdon muutosprosentti. | Profinderin `Liikevaihdon muutos (prosenttia)`, muunnetaan numeroksi ja rajataan välille -100...200. |
| `revenue_bucket` | Liikevaihdon malliluokka. | Ensisijaisesti `revenue_k_eur`: alle 1M, 1-5M, 5-20M, 20-100M, 100M+. Jos numeerinen arvo puuttuu, päätellään `revenue_class`-tekstistä. |
| `headcount_bucket` | Henkilöstön malliluokka. | Ensisijaisesti päätellään `headcount_class`-tekstistä, muuten numeerisesta `headcount`-arvosta: 1-10, 10-50, 50-250, 250-1000, 1000+. |
| `revenue_per_employee` | Liikevaihto työntekijää kohden. | `revenue_k_eur * 1000 / headcount`, jos `headcount > 0`; muuten tyhjä. |
| `excluded_current_customer` | Poistetaanko siksi, että yritys on nykyasiakas. | `business_id` löytyy Account-aineiston `Business ID` -joukosta. |
| `excluded_external_business_id` | Poistetaanko ulkoisen poistolistan vuoksi. | `business_id` löytyy Netvisor-aineiston `Y-tunnus`-joukosta. |
| `excluded_customer_parent_company` | Poistetaanko siksi, että yrityksen Y-tunnus on nykyasiakkaan emoyhtiötunnus. | Prospektin `business_id` löytyy Account-aineiston `parent_business_id`-joukosta. |
| `excluded_customer_group` | Poistetaanko konserniosuman vuoksi. | Prospektin `parent_business_id` löytyy nykyasiakkaiden omista tai emoyhtiötunnuksista. |
| `excluded_manual_name_term` | Poistetaanko manuaalisen nimisäännön vuoksi. | Yrityksen nimi tai markkinointinimi sisältää manuaalisen termin. Nykyisessä mallissa termi on `outokumpu`. |

## Mallin käyttämät featuret

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

Numeerisissa featureissä puuttuvat arvot täytetään mediaanilla ja arvot skaalataan. Kategorisissa featureissä puuttuvat arvot täytetään arvolla `unknown` ja ne one-hot-enkoodataan. Luokittelijana käytetään logistista regressiota asetuksella `class_weight="balanced"`.

## Keskeiset kaavat

| Laskenta | Kaava |
| --- | --- |
| 3 vuoden vuosikeskimyynti | `avg_annual_sales_3y_eur = sales_3y_total_eur / 3` |
| Segment lift | `segment_lift = top-asiakkaiden segmenttiosuus / kaikkien nykyasiakkaiden segmenttiosuus` |
| Malliarvo | `model_value_eur = score * segment_median_value_eur` |
| Liikevaihtokomponentti baselinessa | `max(log1p(revenue_eur) - log1p(1 000 000), 0) * 22 000` |
| Henkilöstökomponentti baselinessa | `log1p(employee_count) * 6 500` |
| Lift-komponentti baselinessa | `segment_lift` rajattuna välille 0.7...1.8 |
| Baseline-arvo | `(revenue_component + headcount_component) * lift_component` |
| Lopullinen potentiaali | `final_value_eur = 0.70 * model_value_eur + 0.30 * baseline_value_eur` |
| Myynnille näytettävä potentiaali | `ennustettu potentiaali = round(final_value_eur)` |

## Huomiot

- `score` ei yksin määrää lopullista järjestystä. Lopullinen järjestys perustuu `final_value_eur`-arvoon, jossa yhdistyvät mallin score, top-asiakkaiden segmenttimyynti ja yrityksen kokopohjainen baseline.
- Kontaktitiedot ja alkuperäinen `Emoyhtiön Y-tunnus` ovat Profinder-lähtöisiä lisäsarakkeita. Niitä ei lasketa `prospect_model.py`-mallissa, vaan ne on lisätty lopputiedostoon lähdedatan perusteella.
- Prospektit poistetaan ennen lopullista listaa, jos ne ovat nykyasiakkaita, nykyasiakkaan konserniyhtiöitä, Netvisor-aineistossa olevia asiakkaita tai manuaalisen nimipoistosäännön osumia.
