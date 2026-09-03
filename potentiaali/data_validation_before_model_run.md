# Potentiaalimallin data-validointi

Raportti on muodostettu ennen malliajoa. Data-aineistoja ei muokata tässä tarkistuksessa.

- [x] Myyntiaineisto: löytyy (115,104,712 tavua).
- [x] Profinder-aineisto: löytyy (5,213,530 tavua).
- [x] Tuotemasteri: löytyy (771,977 tavua).
- [x] Account-rekisteri: löytyy (1,644,553 tavua).
- [x] CRM-potentiaalit: löytyy (1,545,521 tavua).
- [x] Poistolista: löytyy (2,121,446 tavua).

## Myyntiaineisto
- Rivejä: **857,774**
- Sarakkeet: `source_file, id, status, category, productcode, optioncode, name, sales, amount, order, reference, sold_at, accountid, totalprice`
- Invoiced-rivejä: **61,869**
- Hylättävät/puuttuvat päivät: **0**
- Hylättävät/puuttuvat account_id:t: **0**
- Puuttuvat tai virheelliset price/amount-arvot: **0**
- Nolla- tai negatiiviset riviarvot: **84,491**
- Invoiced-rivien nolla- tai negatiiviset arvot: **3,941**
- Aikaväli: **2023-01-01 00:00:00+00:00 - 2026-08-11 00:00:00+00:00**
- Statusarvot: `{'Processed': 606541, 'Archived': 170189, 'Invoiced': 61869, 'Ready to archive': 17907, 'Waiting for delivery': 535, 'Being processed': 427, 'Canceled': 230, 'New': 54, 'Draft': 17, 'Processed and waiting for return': 5}`
- Puuttuvat SKU/ProductCode-arvot: **269,495**
- Invoiced-rivien puuttuvat SKU/ProductCode-arvot: **40,220**

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
- Myynnin account_id-osumat rekisteriin: **545,862/857,774**

## Profinder
- Rivejä: **10,715**
- Sarakkeet: `Profinder ID, Y-tunnus, Toimipaikkatyyppi, Virallinen nimi, Markkinointinimi, Puhelinnumero, Sähköpostiosoite, Päättäjän vastuualue, Tehtävänimike, Titteli, Etunimi, Sukunimi, Päättäjän puhelinnumero, Päättäjän sähköpostiosoite, Henkilö ID, Henkilökuntaluokka, Liikevaihtoluokka, Päätoimiala (TOL2025), Sivutoimialat (TOL2025), Päätoimiala (Profinder), Sivutoimialat (Profinder), Perustettu, Tilikausi, Liikevaihto (tuhatta €), Liikevaihdon muutos (prosenttia), Tilikauden tulos (tuhatta €), Liikevoitto %, Henkilöstö, Henkilöstön muutos (prosenttia), Käyttökate %, Quick ratio, Current ratio, Pääoman tuotto %, Oma pääoma (tuhatta €), Taseen loppusumma (tuhatta €), Omavaraisuusaste, Yhtiömuoto, Toimipaikkojen lukumäärä, Kasvuluokka, Riskiluokka, Mobility-luokka, Yritys tuottaa, Palvelukategoria, WWW-osoite, Operaattoritunnus (verkkolasku), Verkkolaskuosoite, Työnantajarekisteri (pvm), Ennakkoperintärekisteri (pvm), Kaupparekisteri (pvm), ALV-velvollinen (pvm), Profinder ID.1, Y-tunnus.1, Toimipaikkatyyppi.1, Virallinen nimi.1, Markkinointinimi.1, Päätoimipaikan Profinder ID, Emoyhtiön Y-tunnus, Emoyhtiön päätoimipaikan Profinder ID, Käyntiosoite, Käyntiosoitteen postinumero, Käyntiosoitteen postitoimipaikka, Postiosoite, Postiosoitteen postinumero, Postiosoitteen postitoimipaikka, Kaupunginosa, Kunta, Kuntakoodi, Seutukunta, Seutukuntakoodi, Maakunta, Maakuntakoodi, GEOY, GEOX, Tietolähteet`
- Puuttuvat Y-tunnukset: **0**
- Duplikaattiset Y-tunnukset: **0**
- Account-rekisterin Y-tunnukset löytyvät Profinderista: **2,497/5,395**

## ProductCode-liitos
- Invoiced-rivien yksilölliset ProductCode-arvot: **4,659**
- Invoiced ProductCode-arvot löytyvät masterista: **3,202/4,659**
- Masterista puuttuvat yksilölliset ProductCode-arvot: **1,457**

## Tehtävät ennen malliajoa

1. **Tarkista myyntiarvot:** `sales` käsitellään rivin kokonaismyyntinä ja `totalprice` yksikköhintana; tarkista nolla- ja negatiiviset Invoiced-rivit.
2. **Rajaa myynti:** käytä vain `status = Invoiced` -rivejä ja muodosta `created_year_month = YYYY-MM` lähteen `sold_at`-päivästä.
3. **Varmista Account-liitos:** selvitä myynnin account_id:t, joita Account-rekisterissä ei ole.
4. **Varmista Profinder-liitos:** tarkista puuttuvat tai duplikaattiset Y-tunnukset ja hyväksy ne rivit, joita ei voi yhdistää yritysdataan.
5. **Täydennä tuoteryhmät:** liitä `ProductCode` tuotemasteriin ja selvitä kaikki masterista puuttuvat koodit ennen suosituksia.
6. **Tarkista tuotemasterin duplikaatit:** yhdelle ProductCode-arvolle pitää olla yksi yksiselitteinen tuoteryhmä.
7. **Varmista poissulut:** kuljetus-, pakkaus- ja kustannustuotteet poistetaan suosituksista, vaikka niiden myyntihistoria säilyy laskennassa.
8. **Tee koeajo ja hyväksy data quality -raportti** ennen varsinaisen tuloksen julkaisemista.

### Johtopäätös
Malliajoa ei pidä julkaista ennen kuin yllä olevat tarkistukset on käsitelty. Tämä raportti erottaa rakenteelliset blockerit laadullisista tarkistustehtävistä.
