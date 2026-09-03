# Potentiaalimallin data-validointi

Raportti on muodostettu ennen malliajoa. Data-aineistoja ei muokata tässä tarkistuksessa.

- [x] Myyntiaineisto: löytyy (11,427,006 tavua).
- [x] Profinder-aineisto: löytyy (5,213,530 tavua).
- [x] Tuotemasteri: löytyy (771,977 tavua).
- [x] Account-rekisteri: löytyy (1,644,553 tavua).
- [x] CRM-potentiaalit: löytyy (1,545,521 tavua).
- [x] Poistolista: löytyy (2,121,446 tavua).

## Myyntiaineisto
- Rivejä: **57,707**
- Sarakkeet: `source_file, account_id, id, status, category, sku, name, price, amount, order, reference, created_at`
- Invoiced-rivejä: **55,568**
- Hylättävät/puuttuvat päivät: **0**
- Hylättävät/puuttuvat account_id:t: **0**
- Puuttuvat tai virheelliset price/amount-arvot: **0**
- Nolla- tai negatiiviset riviarvot: **6,640**
- Invoiced-rivien nolla- tai negatiiviset arvot: **6,336**
- Aikaväli: **2023-05-27 08:59:40+00:00 - 2026-05-26 13:26:41+00:00**
- Statusarvot: `{'Invoiced': 55568, 'Being processed': 1053, 'Waiting for delivery': 779, 'Processed': 178, 'New': 129}`
- Puuttuvat SKU/ProductCode-arvot: **34,664**
- Invoiced-rivien puuttuvat SKU/ProductCode-arvot: **33,254**

## Tuotemasteri
- Välilehti: `Tuotteet`
- Rivejä: **11,956**
- Tuotekoodit: **11,954**
- Puuttuvat tuoteryhmät: **0**
- Duplikaattiset tuotekoodit: **2**

## Account-rekisteri ja liitokset
- Rekisteririvejä: **5,406**
- Puuttuvat Account ID:t: **0**
- Duplikaattiset Account ID:t: **0**
- Puuttuvat Y-tunnukset: **11**
- Myynnin account_id-osumat rekisteriin: **44,447/57,707**

## Profinder
- Rivejä: **10,715**
- Sarakkeet: `Profinder ID, Y-tunnus, Toimipaikkatyyppi, Virallinen nimi, Markkinointinimi, Puhelinnumero, Sähköpostiosoite, Päättäjän vastuualue, Tehtävänimike, Titteli, Etunimi, Sukunimi, Päättäjän puhelinnumero, Päättäjän sähköpostiosoite, Henkilö ID, Henkilökuntaluokka, Liikevaihtoluokka, Päätoimiala (TOL2025), Sivutoimialat (TOL2025), Päätoimiala (Profinder), Sivutoimialat (Profinder), Perustettu, Tilikausi, Liikevaihto (tuhatta €), Liikevaihdon muutos (prosenttia), Tilikauden tulos (tuhatta €), Liikevoitto %, Henkilöstö, Henkilöstön muutos (prosenttia), Käyttökate %, Quick ratio, Current ratio, Pääoman tuotto %, Oma pääoma (tuhatta €), Taseen loppusumma (tuhatta €), Omavaraisuusaste, Yhtiömuoto, Toimipaikkojen lukumäärä, Kasvuluokka, Riskiluokka, Mobility-luokka, Yritys tuottaa, Palvelukategoria, WWW-osoite, Operaattoritunnus (verkkolasku), Verkkolaskuosoite, Työnantajarekisteri (pvm), Ennakkoperintärekisteri (pvm), Kaupparekisteri (pvm), ALV-velvollinen (pvm), Profinder ID.1, Y-tunnus.1, Toimipaikkatyyppi.1, Virallinen nimi.1, Markkinointinimi.1, Päätoimipaikan Profinder ID, Emoyhtiön Y-tunnus, Emoyhtiön päätoimipaikan Profinder ID, Käyntiosoite, Käyntiosoitteen postinumero, Käyntiosoitteen postitoimipaikka, Postiosoite, Postiosoitteen postinumero, Postiosoitteen postitoimipaikka, Kaupunginosa, Kunta, Kuntakoodi, Seutukunta, Seutukuntakoodi, Maakunta, Maakuntakoodi, GEOY, GEOX, Tietolähteet`
- Puuttuvat Y-tunnukset: **0**
- Duplikaattiset Y-tunnukset: **0**
- Account-rekisterin Y-tunnukset löytyvät Profinderista: **2,497/5,395**

## ProductCode-liitos
- Invoiced-rivien yksilölliset ProductCode-arvot: **4,348**
- Invoiced ProductCode-arvot löytyvät masterista: **2,837/4,348**
- Masterista puuttuvat yksilölliset ProductCode-arvot: **1,511**

## Tehtävät ennen malliajoa

1. **Korjaa tai hyväksy myyntiarvojen poikkeamat:** tarkista puuttuvat/virheelliset `price`- ja `amount`-arvot sekä nolla- ja negatiiviset rivit.
2. **Rajaa myynti:** käytä vain `status = Invoiced` -rivejä ja muodosta `total_value = price * amount` sekä `created_year_month = YYYY-MM`.
3. **Varmista Account-liitos:** selvitä myynnin account_id:t, joita Account-rekisterissä ei ole.
4. **Varmista Profinder-liitos:** tarkista puuttuvat tai duplikaattiset Y-tunnukset ja hyväksy ne rivit, joita ei voi yhdistää yritysdataan.
5. **Täydennä tuoteryhmät:** liitä `ProductCode` tuotemasteriin ja selvitä kaikki masterista puuttuvat koodit ennen suosituksia.
6. **Tarkista tuotemasterin duplikaatit:** yhdelle ProductCode-arvolle pitää olla yksi yksiselitteinen tuoteryhmä.
7. **Varmista poissulut:** kuljetus-, pakkaus- ja kustannustuotteet poistetaan suosituksista, vaikka niiden myyntihistoria säilyy laskennassa.
8. **Tee koeajo ja hyväksy data quality -raportti** ennen varsinaisen tuloksen julkaisemista.

### Johtopäätös
Malliajoa ei pidä julkaista ennen kuin yllä olevat tarkistukset on käsitelty. Tämä raportti erottaa rakenteelliset blockerit laadullisista tarkistustehtävistä.
