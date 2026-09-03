# ProductCode-puutteiden nimipohjainen täydennys

`run_current_customer_potential_new_sources.py` täydentää myyntiaineiston puuttuvia ProductCode-arvoja tuotteen `name`-kentän avulla ennen tuoteryhmä- ja suosituslaskentaa.

## Säännöt

- Nimi normalisoidaan Unicode-muotoon, pienaakkosiksi ja ylimääräiset välilyönnit poistetaan.
- Match tehdään vain, jos tuotemasterissa nimi vastaa yhtä yksiselitteistä ProductCodea ja tuoteryhmää.
- Epäselvät nimet ja tuotemasterista puuttuvat nimet jätetään täyttämättä väärän luokituksen estämiseksi.
- Täydennetty ProductCode kulkee normaalin tuotemasterin tuoteryhmäliitoksen kautta kaikkiin jatkolaskentoihin.

## Auditointi

Täydennyksistä kirjoitetaan `product_name_group_enrichment_audit_new_sources.csv`. Mallin `data_quality`-välilehdelle kirjataan ennen/jälkeen-määrät erikseen kaikille mukaan otetuille riveille ja Invoiced-riveille.
