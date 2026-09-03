# ProductCode-puutteiden nimipohjainen täydennys

`run_current_customer_potential_new_sources.py` käyttää ensin ProductCodea tuoteryhmän auktoritatiiviseen master-liitokseen. Vasta ProductCode-puutteissa käytetään tuotteen `name`-kenttää varamenetelmänä.

## Säännöt

- Nimi normalisoidaan Unicode-muotoon, pienaakkosiksi ja ylimääräiset välilyönnit poistetaan.
- ProductCode-liitos tehdään aina ennen nimipohjaista täydennystä.
- Match tehdään vain, jos tuotemasterissa nimi vastaa yhtä yksiselitteistä ProductCodea ja tuoteryhmää.
- Epäselvät nimet ja tuotemasterista puuttuvat nimet jätetään täyttämättä väärän luokituksen estämiseksi.
- Täydennetty ProductCode kulkee normaalin tuotemasterin tuoteryhmäliitoksen kautta kaikkiin jatkolaskentoihin.

## Auditointi

Täydennyksistä kirjoitetaan `product_name_group_enrichment_audit_new_sources.csv`. Mallin `data_quality`-välilehdelle kirjataan ennen/jälkeen-määrät erikseen kaikille mukaan otetuille riveille ja Invoiced-riveille.
