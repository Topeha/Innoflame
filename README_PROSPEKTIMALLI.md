# Innoflamen prospektimalli

Tämä kansio sisältää Innoflamen prospektimallin teknisen kuvauksen, tiedostoluettelon ja myynnin käyttöohjeen.

## Sisältö

- [Tekninen kuvaus](PROSPEKTIMALLI_TEKNINEN_KUVAUS.md)
- [Tiedostot ja ajaminen](PROSPEKTIMALLI_TIEDOSTOT.md)
- [Myynnin koulutusmateriaali](PROSPEKTIMALLI_MYYNNIN_KOULUTUS.md)

## Mallin tarkoitus

Malli etsii Profinderin yritysjoukosta yrityksiä, joiden profiili muistuttaa Innoflamen parhaita nykyasiakkaita. Se tuottaa yrityksille:

- todennäköisyyttä kuvaavan `score`-arvon
- euromääräisen `ennustettu potentiaali`-arvon
- prioriteettiluokan A-D
- järjestysnumeron myynnin työlistaa varten
- lyhyet `positive_signals`-perustelut

Mallia käytetään priorisointiin. Potentiaali ei ole lupaus tulevasta myynnistä eikä yrityskohtainen tarjous- tai liikevaihtoennuste.

## Nykyinen viimeisin ajo

- Myyntiaineisto: `GoSystems_sales_26_05_2026_summarized.csv`
- Mallin kuukausisyöte: `prospektointi/sales_import_test/GoSystems_sales_26_05_2026_model_input_corrected.csv`
- Yritysdata: `haku_Myyntiin_ai_2026-04-23 (1).xlsx`
- Asiakasdata: `Account_20.05.2026_combined_with_profinder.xlsx`
- Poistolista: `Netvisor asiakastiedot 6-2026.xlsx`
- Tulokset: `prospektointi/prospect_segment_model_all_prospects_corrected_sales_rerun.csv`

Uusinta-ajossa oli 1 956 prospektia. Kokonaispotentiaali oli 41,86 M€ ja Top 100 -listan päällekkäisyys aiempaan ajoon nähden 95 %.

## Nopein aloitus

Nykyasiakkaiden 12 kuukauden potentiaali ja tuotekohtaiset suositukset ajetaan näin:

```powershell
python prospektointi\run_innoflame_potential_model.py
```

Oletusajo käyttää projektin kuukausitason myyntisyötettä, `Innoflame_merged_sales.csv`-tuotetason historiaa ja Downloads-kansiossa olevaa tuotemasteria. Tulokset kirjoitetaan kansioon `outputs/current_customer_potential`.

Lue ensin tekninen kuvaus ja sen jälkeen myynnin koulutusmateriaali. Mallin ajo tehdään aina projektin juuresta ja syöttöpolut annetaan eksplisiittisesti:

```powershell
python prospektointi\prospect_model.py `
  --accounts "Account_20.05.2026_combined_with_profinder.xlsx" `
  --sales "prospektointi\sales_import_test\GoSystems_sales_26_05_2026_model_input_corrected.csv" `
  --companies "haku_Myyntiin_ai_2026-04-23 (1).xlsx" `
  --exclude-business-ids-file "Netvisor asiakastiedot 6-2026.xlsx" `
  --output "prospektointi\prospect_segment_model_all_prospects_corrected_sales_rerun.csv" `
  --top-n-customers 1000 `
  --lookback-days 1095 `
  --random-state 42
```

Ennen ajoa on suositeltavaa tehdä uusi kuukausisyöte ja tallentaa sen audit-tiedosto. Katso [Tiedostot ja ajaminen](PROSPEKTIMALLI_TIEDOSTOT.md).
