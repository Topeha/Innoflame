# ProductCode-puutteiden nimipohjainen täydennys

`run_current_customer_potential_new_sources.py` käyttää ensin ProductCodea tuoteryhmän auktoritatiiviseen master-liitokseen. Vasta ProductCode-puutteissa käytetään tuotteen `name`-kenttää varamenetelmänä.

## Säännöt

- Nimi normalisoidaan Unicode-muotoon, pienaakkosiksi ja ylimääräiset välilyönnit poistetaan.
- ProductCode-liitos tehdään aina ennen nimipohjaista täydennystä.
- Match tehdään vain, jos tuotemasterissa nimi vastaa yhtä yksiselitteistä ProductCodea ja tuoteryhmää.
- Piste-, yhdysmerkki- ja välilyöntierot käsitellään toisena nimivariaationa.
- Myyntirivin kategoriaa verrataan tuotemasterin yksiselitteisiin ryhmäpolun osiin.
- Jos aineistossa on kuvauskenttä, se yhdistetään tuotemasterin kuvaukseen yksiselitteisenä osumana.
- Korkean varmuuden sumea nimiosuma hyväksytään vain, jos paras osuma on selvästi seuraavaa parempi.
- Tuotteen nimi, kuvaus ja kategoria eivät ohita olemassa olevaa ProductCode-liitosta.
- Kuljetus-, toimitus-, rahti-, pakkaus- ja kustannusviitteiset nimet luokitellaan `Muut pakkaukset` -ryhmään, jos ProductCode-liitosta ei ole.
- Epäselvät nimet ja tuotemasterista puuttuvat nimet jätetään täyttämättä väärän luokituksen estämiseksi.
- Täydennetty ProductCode kulkee normaalin tuotemasterin tuoteryhmäliitoksen kautta kaikkiin jatkolaskentoihin.

## Auditointi

Täydennyksistä kirjoitetaan `product_name_group_enrichment_audit_new_sources.csv`. Mallin `data_quality`-välilehdelle kirjataan ennen/jälkeen-määrät erikseen kaikille mukaan otetuille riveille ja Invoiced-riveille.

Auditoinnin `product_name_match`-arvot kertovat käytetyn menetelmän: `unique_master_name`, `normalized_master_name`, `description_exact`, `category_exact` tai `fuzzy_high_confidence`. Epäselvät ja löytymättömät nimet jäävät tarkistettaviksi.
