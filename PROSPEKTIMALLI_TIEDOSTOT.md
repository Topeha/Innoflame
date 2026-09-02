# Prospektimallin tiedostot ja ajaminen

Tämä dokumentti kuvaa mallin tarvitsemat tiedostot, niiden roolit, tärkeät sarakkeet ja ajon tuottamat tulokset.

## 1. Tiedostokokonaisuus

| Tiedosto | Rooli | Pakollinen ajossa |
| --- | --- | --- |
| `prospektointi/prospect_model.py` | Varsinainen pisteytys- ja potentiaalimalli | Kyllä |
| `Account_20.05.2026_combined_with_profinder.xlsx` | GoSystemsin asiakasrekisteri ja asiakastilit | Kyllä |
| `GoSystems_sales_26_05_2026_summarized.csv` | Korjattu GoSystems-myyntiaineisto | Kyllä, valmistelun lähde |
| `prospektointi/sales_import_test/GoSystems_sales_26_05_2026_model_input_corrected.csv` | Mallin kuukausitason myyntisyöte | Kyllä |
| `haku_Myyntiin_ai_2026-04-23 (1).xlsx` | Profinder-yritys- ja taloustiedot | Kyllä |
| `Netvisor asiakastiedot 6-2026.xlsx` | Ulkoinen poistolista | Suositeltava |
| `prospektointi/prepare_gosystems_sales_for_model.py` | Raakaa GoSystems-Exceliä varten tehtävä valmistelu | Tarvitaan raakasyötteessä |
| `prospektointi/sales_import_test/GoSystems_sales_26_05_2026_model_input_corrected.audit.json` | Syötteen rivimäärä-, euro- ja aikaväliauditointi | Suositeltava |
| `prospektointi/prospect_segment_model_all_prospects_corrected_sales_rerun.csv` | Uusi yrityskohtainen tuloslista | Tuloste |
| `prospektointi/prospect_segment_model_all_prospects_corrected_sales_rerun.metrics.json` | Mallin validointimittarit ja poistolaskurit | Tuloste |
| `prospektointi/prospect_segment_model_all_prospects_corrected_sales_rerun_comparison.csv` | Yrityskohtainen vertailu vanhaan ajoon | Vertailutuloste |
| `Innoflame_prospektimalli_uusinta_vertailu.xlsx` | Myynnin Excel-yhteenveto | Jakelutiedosto |
| `Innoflame_prospektimalli_uusinta_vertailu.pptx` | Johtoryhmä- ja myyntiesitys | Jakelutiedosto |

## 2. Asiakasrekisteri

`Account_20.05.2026_combined_with_profinder.xlsx` sisältää asiakastilit ja niiden yritystunnisteet.

Mallin kannalta keskeiset sarakkeet ovat:

- `ID`: asiakastilin tunniste, joka yhdistetään myyntidatan `account_id`-kenttään
- `Business ID`: yrityksen Y-tunnus
- `Company Name`: yrityksen nimi
- `customer_status`: asiakasstatus
- `Emoyhtiön Y-tunnus`: konsernipoistoja varten

Koulutusjoukkoon hyväksytään nykyisessä mallissa vain statukset `Active` ja `Gokeep+`. Kaikki GoSystemsin asiakasyritykset ja niiden tunnistettavat konserniyhtiöt poistetaan lopullisesta prospektilistasta.

## 3. Myyntiaineisto

### Nykyisen uusinta-ajon syöte

Nykyinen `GoSystems_sales_26_05_2026_summarized.csv` on puolipiste-eroteltu korjattu aineisto. Siinä ovat muun muassa:

- `accountid`
- `sales`
- `sold_at`
- `status`
- `productcode`
- `name`

Uusinta-ajossa siitä muodostettiin mallin vaatima kuukausisyöte seuraavasti:

| Lähdekenttä | Mallikenttä | Käsittely |
| --- | --- | --- |
| `accountid` | `account_id` | Muunnetaan numeeriseksi |
| `sales` | `total_value` | Käytetään myyntiarvona sellaisenaan |
| `sold_at` | `created_year_month` | Muunnetaan muotoon `YYYY-MM` |
| sama `account_id` + kuukausi | yksi rivi | Summataan kuukausitasolle |

Uusinta-ajon auditointi:

- 857 774 lähderiviä
- 4 844 asiakastiliä
- 27 283 asiakas-kuukausiriviä
- 121,90 M€ myyntiä
- ajanjakso `2023-01`–`2026-08`

Huomio: tässä uusinta-ajossa korjatun `sales`-kentän statusrajauksia ei tehty uudelleen valmisteluvaiheessa. Jos halutaan ajaa raakaa GoSystems-Exceliä tai käyttää vain laskutettuja rivejä, käytetään erillistä valmisteluskriptiä.

### Raakasyötteen valmistelu

`prospektointi/prepare_gosystems_sales_for_model.py` lukee raakaa GoSystems-Exceliä, laskee rivimyynnin:

```text
total_value = price * amount
```

ja muodostaa asiakas-kuukausitason syötteen. Oletuksena mukaan otetaan vain `Invoiced`-statuksen rivit.

Esimerkki:

```powershell
python prospektointi\prepare_gosystems_sales_for_model.py `
  --source-xlsx "GoSystems_sales_26_05_2026_all_rows (2).xlsx" `
  --accounts "Account_20.05.2026_combined_with_profinder.xlsx" `
  --output-dir "prospektointi\sales_import_test"
```

Valmistelu tuottaa:

- `GoSystems_sales_26_05_2026_model_input_invoiced.csv`
- `source_status_summary.csv`
- `sales_import_audit.json`

## 4. Profinder-yritysdata

`haku_Myyntiin_ai_2026-04-23 (1).xlsx` muodostaa pisteytettävän yritysjoukon. Keskeiset sarakkeet ovat:

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

Y-tunnukset normalisoidaan muotoon `1234567-8`. Yritykset deduplikoidaan Y-tunnuksella.

## 5. Poistolista

`Netvisor asiakastiedot 6-2026.xlsx` luetaan ulkoisena Y-tunnuspoistolistana. Sen avulla voidaan poistaa prospektilistalta yritykset, joiden ei haluta tulevan myynnin työlistalle vaikka ne eivät löytyisi varsinaisesta GoSystems-asiakasrekisteristä.

## 6. Malliajo

Varsinainen malli ajetaan `prospektointi/prospect_model.py`-tiedostolla.

Täysi ajo:

```powershell
python prospektointi\prospect_model.py `
  --accounts "Account_20.05.2026_combined_with_profinder.xlsx" `
  --sales "prospektointi\sales_import_test\GoSystems_sales_26_05_2026_model_input_corrected.csv" `
  --companies "haku_Myyntiin_ai_2026-04-23 (1).xlsx" `
  --exclude-business-ids-file "Netvisor asiakastiedot 6-2026.xlsx" `
  --output "prospektointi\prospect_segment_model_all_prospects_rerun.csv" `
  --top-n-customers 1000 `
  --lookback-days 1095 `
  --random-state 42
```

Parametrit:

| Parametri | Merkitys | Nykyinen arvo |
| --- | --- | --- |
| `--top-n-customers` | Kuinka monta parasta nykyasiakasta muodostaa positiivisen luokan | 1000 |
| `--lookback-days` | Myyntihistorian pituus | 1095 päivää, noin 3 vuotta |
| `--min-training-customer-annual-sales-eur` | Pienin vuositasolle muunnettu myynti koulutusjoukossa | 4 000 € |
| `--random-state` | Toistettavan train/test-jaon siemen | 42 |

## 7. Tulostiedostot

### Prospektilista

`prospect_segment_model_all_prospects_corrected_sales_rerun.csv` sisältää yhden rivin per prospekti.

Tärkeimmät kentät:

| Kenttä | Kuvaus |
| --- | --- |
| `rank` | Järjestysnumero, 1 on korkein prioriteetti |
| `priority` | A = 1-100, B = 101-500, C = 501-1000, D = yli 1000 |
| `company` | Yrityksen nimi |
| `business_id` | Y-tunnus |
| `parent_business_id` | Emoyhtiön Y-tunnus |
| `score` | Logistisen mallin todennäköisyyspiste |
| `segment_median_value_eur` | Parhaiden asiakkaiden vastaavan segmentin mediaanimyynti |
| `model_value_eur` | `score * segment_median_value_eur` |
| `baseline_value_eur` | Yrityksen koon ja segmentin jatkuva vertailuarvo |
| `ennustettu potentiaali` | Lopullinen yhdistelmäarvo euroina |
| `positive_signals` | Luettavat perustelut pisteelle |
| `reference_date` | Myyntiaineiston viimeinen mallissa käytetty päivämäärä |

### Metriikat

`*.metrics.json` sisältää muun muassa:

- `roc_auc`
- `average_precision`
- `train_rows`
- `test_rows`
- `positive_rate`
- poistetut nykyasiakkaat
- poistetut konserniyritykset
- ulkoisen poistolistan osumat
- manuaalisella nimirajauksella poistetut yritykset

## 8. Ajon laadunvarmistus

Ennen julkaisua tarkista aina:

1. Syöte-auditoinnin rivimäärä, eurot ja ensimmäinen/viimeinen kuukausi.
2. `account_id`-liitosten osuus Account-aineistoon.
3. Nykyasiakkaiden ja konserniyritysten poistot.
4. Prospektien lukumäärä ja Top 100 -lista.
5. Suurimmat potentiaalin muutokset edelliseen ajoon verrattuna.
6. Muutama yritys käsin: nimi, Y-tunnus, toimiala, liikevaihto ja henkilöstö.

## 9. Rajoitteet

- Malli ei ennusta suoraan toteutuvaa tilausta tai voittoa.
- Malli ei käytä katetta, kapasiteettia, myyntialueen kuormaa tai yhteydenoton onnistumista.
- Malli ei ole aikasarjaennuste eikä kausaalimalli.
- Tulokset riippuvat Profinder-tietojen ajantasaisuudesta ja Y-tunnusten liitoksista.
- Uusi tai puutteellisesti kuvattu yritys voi saada heikomman tai epätarkan pisteen.
- `score` on ranking-piste, ei suoraan prosenttimuotoinen ostotodennäköisyys.
