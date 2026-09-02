# Prospektimallin tietokantataulut automaattiajoa varten

Tämä dokumentti kuvaa tietokantarakenteen, jolla Innoflamen prospektimalli voidaan ajaa automaattisesti ilman käsin ylläpidettäviä Excel- ja CSV-välivaiheita.

![Prospektimallin tietokantataulut](assets/prospektimallin_tietokantakaavio.png)

Mallin nykyinen logiikka tarvitsee vähintään:

- yritys-/prospektiuniversumin
- customer masterin eli nykyasiakkaat ja asiakasstatukset
- myyntihistorian
- tuotemasterin
- tuoteryhmä-/segmenttihierarkian, jos halutaan tuotekohtainen potentiaali
- poistolistat ja ajonhallinnan
- mallin tulostaulut

Alla oleva malli on relaatiomallinen ja sopii esimerkiksi BigQueryyn, SQL Serveriin, PostgreSQL:ään tai vastaavaan analytiikkatietokantaan. Taulujen nimet ovat ehdotuksia.

## Lähdedatan kuvaus

Prospektimallin päälähde on GoSystem. GoSystemista tulevat ensisijaisesti nykyasiakkaat, asiakasstatukset, myyntihistoria ja tuotetiedot. Näistä muodostetaan tietokannan ydintaulut `customer_master`, `sales_order_line` ja `product_master`.

Ulkoinen yritystieto tulee Profinderistä. Profinder toimii yritys- ja prospektiuniversumin rikastuslähteenä: sieltä saadaan esimerkiksi Y-tunnus, yrityksen nimi, emoyhtiön Y-tunnus, toimiala, liikevaihto, henkilöstö, sijainti ja yhteystiedot. Näistä muodostetaan pääosin `company_master` ja `contact_master`.

| Lähde | Rooli mallissa | Pääasialliset taulut |
| --- | --- | --- |
| GoSystem | Päälähde asiakkaisiin, myyntiin ja tuotteisiin | `customer_master`, `sales_order_line`, `product_master` |
| Profinder | Ulkoinen yritys- ja prospektitieto | `company_master`, `contact_master` |
| Netvisor / muu poistolista | Ulkoinen poistolista nykyisille tai muuten poistettaville yrityksille | `external_exclusion_business` |

### Profinder Historia API

Profinderin ulkoinen yritystieto kannattaa tuoda automaattisesti Historia API:n kautta. Dokumentaation mukaan API on osa Profinder B2B API -kokonaisuutta ja käyttää vastaavaa API key -kirjautumista kuin muu Profinder B2B API.

Historia API palauttaa muutokset eräajomallilla. Ensimmäisellä ajolla pyyntö voidaan tehdä ilman parametreja, jolloin vastauksesta saadaan talteen `nextHistoryId`. Seuraavissa ajoissa käytetään tallennettua `historyId`-arvoa. Vastauksen `data`-rivien `_status` kertoo muutostyypin:

- `ADDED`: uusi tieto
- `UPDATED`: muuttunut tieto
- `DELETED`: poistunut tieto

Rajapinnat:

| Endpoint | Käyttö | Sivutuksen `after` | Kohdetaulu |
| --- | --- | --- | --- |
| `GET /history/company` | Muuttuneet yritykset | viimeisen rivin `businessId` | `company_master`, `profinder_company_history` |
| `GET /history/financial` | Uudet tilitiedot | viimeisen rivin `id` | `profinder_financial_history`, `company_master` |
| `GET /history/office` | Muuttuneet toimipaikat | viimeisen rivin `profinderId` | `profinder_office_history`, `company_master` |
| `GET /history/decisionMaker` | Muuttuneet päättäjät | viimeisen rivin `profinderId` | `contact_master`, `profinder_decision_maker_history` |

Yhteiset vastauskentät:

| Kenttä | Kuvaus |
| --- | --- |
| `success` | Onnistuiko pyyntö. HTTP 200 ei yksin riitä, vaan tämän pitää olla `true`. |
| `requestHistoryId` | Pyynnössä käytetty history-id. |
| `requestHistoryIdDate` | Pyynnössä käytetyn history-id:n päivämäärä. |
| `nextHistoryId` | Seuraavaa ajoa varten tallennettava history-id. |
| `nextHistoryIdDate` | Seuraavan history-id:n päivämäärä. |
| `prevHistoryId` | Edellinen history-id, jos palautettu. |
| `prevHistoryIdDate` | Edellisen history-id:n päivämäärä, jos palautettu. |
| `data` | Muuttuneet rivit. |

Sivutus tehdään `size`- ja `after`-parametreilla. `size` voi olla 1-1000. Kaikki erän rivit on haettu, kun `data`-rivien määrä on pienempi kuin pyydetty `size`. Kun erä on käsitelty loppuun, viimeisessä vastauksessa tullut `nextHistoryId` tallennetaan seuraavaa ajoa varten.

Profinder suosittelee muuttuneiden tietojen hakua joka aamuyö, esimerkiksi klo 3-6 Suomen aikaa. Ajoa ei kannata ajastaa tasatunnille, jotta samanaikaisia rajapintakutsuja vältetään.

Suositeltu kontrollitaulu Profinder-ajolle:

| Kenttä | Kuvaus |
| --- | --- |
| `source_name` | Esimerkiksi `profinder_history_company`, `profinder_history_financial`, `profinder_history_office` tai `profinder_history_decision_maker`. |
| `last_history_id` | Viimeisin onnistuneesti käsitelty `nextHistoryId`. |
| `last_history_id_date` | Viimeisimmän history-id:n päivämäärä. |
| `last_run_at` | Viimeisin onnistunut haku. |
| `last_success_at` | Viimeisin onnistunut täysi erä. |
| `status` | Ajon tila, esimerkiksi `success`, `running` tai `failed`. |
| `error_message` | Virheviesti epäonnistuneesta ajosta. |

## Kokonaiskuva

Prospektimallin automaattiajo etenee näin:

1. Ladataan `company_master` eli koko pisteytettävä yritysjoukko.
2. Ladataan `customer_master` eli nykyasiakkaat, asiakasstatus ja liitosavaimet myyntihistoriaan.
3. Ladataan `sales_order_line` eli myyntirivit tai koosteistetut myyntirivit.
4. Ladataan `product_master` ja tarvittaessa tuoteryhmähierarkia.
5. Normalisoidaan Y-tunnukset samaan muotoon `1234567-8`.
6. Yhdistetään myynti asiakkaisiin.
7. Rajataan mallin opetukseen vain asiakasstatukset `Active` ja `Gokeep+`.
8. Lasketaan nykyasiakkaiden myynti viimeiseltä 3 vuodelta ja vuosikeskiarvo.
9. Muodostetaan top-asiakkaat, segment lift, mallifeaturet ja mallin label.
10. Pisteytetään yritysuniversumi.
11. Poistetaan nykyasiakkaat, konserniosumat, ulkoiset poistolistat ja manuaaliset poistosäännöt.
12. Lasketaan prospektin euroarvo ja prioriteetti.
13. Lasketaan haluttaessa tuotekohtainen potentiaali segmenttien ostojakaumien perusteella.
14. Kirjoitetaan ajon tulokset output-tauluihin.

## Pakolliset ydintaulut

### 1. `company_master`

Tarkoitus: koko yritysuniversumi, joka sisältää sekä nykyasiakkaat että prospektit. Tämä vastaa nykyistä Profinder-/yritysaineistoa.

Jyvä: yksi rivi per yritys per `business_id`.

Pääavain: `business_id`.

| Kenttä | Tyyppi | Pakollinen | Kuvaus |
| --- | --- | --- | --- |
| `business_id` | string | kyllä | Yrityksen Y-tunnus normalisoituna muodossa `1234567-8`. |
| `source_business_id` | string | suositus | Alkuperäinen lähdejärjestelmän Y-tunnus ennen normalisointia. |
| `company_name` | string | kyllä | Virallinen nimi. Nykyisessä Profinder-aineistossa `Virallinen nimi`. |
| `marketing_name` | string | ei | Markkinointinimi. |
| `parent_business_id` | string | kyllä | Emoyhtiön Y-tunnus. Jos puuttuu, täytetään yrityksen omalla `business_id`:llä. |
| `business_form` | string | ei | Yritysmuoto. Profinder Historia API:n kenttä `businessForm`. |
| `founded_date` | date | ei | Perustamispäivä. Profinder-kenttä `founded`. |
| `industry` | string | kyllä | Päätoimiala. Nykyisessä mallissa `Päätoimiala (Profinder)`. |
| `tol2008_code` | string | suositus | Toimialakoodi. Profinder-kenttä `tol2008Code`. |
| `tol2008_name` | string | suositus | Toimialan sanallinen kuvaus. Profinder-kenttä `tol2008`. |
| `revenue_k_eur` | numeric | kyllä | Liikevaihto tuhansina euroina. |
| `turnover_category` | string | suositus | Profinderin liikevaihtoluokka, esim. `2-10 milj. euroa`. |
| `headcount` | numeric | kyllä | Henkilöstömäärä. |
| `staff_category` | string | suositus | Profinderin henkilöstöluokka, esim. `20-49 henkilöä`. |
| `growth_pct` | numeric | kyllä | Liikevaihdon muutos prosentteina. |
| `growth_class` | string | ei | Profinderin kasvuluokka. |
| `risk_class` | string | ei | Profinderin riskiluokka. |
| `revenue_class` | string | suositus | Lähdejärjestelmän liikevaihtoluokka. |
| `headcount_class` | string | suositus | Lähdejärjestelmän henkilöstöluokka. |
| `municipality` | string | kyllä | Kunta. |
| `region` | string | kyllä | Maakunta tai alue. |
| `location` | string | suositus | Käyntiosoitteen postitoimipaikka. |
| `postal_code` | string | ei | Postinumero. |
| `street_address` | string | ei | Käyntiosoite. |
| `phone` | string | ei | Yrityksen puhelinnumero. |
| `email` | string | ei | Yrityksen yleinen sähköposti. |
| `website` | string | ei | Verkkosivu. |
| `employer_register_date` | date | ei | Työnantajarekisterin aloituspäivä. |
| `prepayment_register_date` | date | ei | Ennakkoperintärekisterin aloituspäivä. |
| `trade_register_date` | date | ei | Kaupparekisterin aloituspäivä. |
| `vat_liability_date` | date | ei | ALV-velvollisuuden aloituspäivä. |
| `profinder_status` | string | ei | Historia API:n `_status`: `ADDED`, `UPDATED` tai `DELETED`. |
| `source_system` | string | kyllä | Esim. `Profinder`, `GoSystems`, `manual_import`. |
| `source_updated_at` | timestamp | kyllä | Lähdedatan päivitysaika. |
| `valid_from` | date | suositus | Historiointia varten. |
| `valid_to` | date | ei | Historiointia varten. Tyhjä = nykyinen versio. |
| `is_current` | boolean | suositus | Nykyinen versio. |

Mallissa johdettavat kentät, joita ei tarvitse tallentaa tähän tauluun mutta voidaan materialisoida näkymään:

| Johdettu kenttä | Logiikka |
| --- | --- |
| `revenue_bucket` | `0-1M`, `1-5M`, `5-20M`, `20-100M`, `100M+`. |
| `headcount_bucket` | `1-10`, `10-50`, `50-250`, `250-1000`, `1000+`. |
| `company_segment` | `revenue_bucket || '_' || headcount_bucket`. |
| `growth_bucket` | alle -5 = `decline`, -5...5 = `stable`, 5...20 = `growth`, yli 20 = `high_growth`. |
| `revenue_per_employee` | `revenue_k_eur * 1000 / headcount`, kun `headcount > 0`. |

### 2. `customer_master`

Tarkoitus: nykyasiakkaiden masterdata, asiakasstatus, CRM-/ERP-tunnisteet ja konsernipoistoihin tarvittavat tunnukset. Tämä vastaa nykyistä Account-aineistoa.

Jyvä: yksi rivi per asiakastili per `account_id`. Samalla Y-tunnuksella voi olla useampi account, joten `business_id` ei yksin ole pääavain.

Pääavain: `account_id`.

| Kenttä | Tyyppi | Pakollinen | Kuvaus |
| --- | --- | --- | --- |
| `account_id` | string tai integer | kyllä | Asiakastilin tunniste. Nykyisessä mallissa Account `ID`. |
| `business_id` | string | kyllä | Asiakkaan Y-tunnus normalisoituna. Nykyisessä aineistossa `Business ID`. |
| `source_business_id` | string | suositus | Alkuperäinen Y-tunnus ennen normalisointia. |
| `parent_business_id` | string | kyllä | Emoyhtiön Y-tunnus. Käytetään konsernipoistoon. |
| `account_name` | string | kyllä | Asiakkaan nimi. Nykyisessä aineistossa `Company Name`. |
| `customer_status` | string | kyllä | Esim. `Active`, `Gokeep+`, `direct_delivery`, `inactive`. |
| `customer_type` | string | ei | Esim. suora asiakas, kumppani, verkkokauppa-asiakas. |
| `sales_owner` | string | ei | Myyjä tai asiakkuuden omistaja. |
| `sales_team` | string | ei | Myyntitiimi. |
| `customer_since` | date | ei | Asiakkuuden aloituspäivä. |
| `is_active_customer` | boolean | suositus | Tosi, jos asiakas tulkitaan nykyasiakkaaksi prospektipoistoissa. |
| `is_training_eligible` | boolean | suositus | Tosi, jos asiakas saa opettaa mallia. Nykyinen sääntö: status `Active` tai `Gokeep+`. |
| `source_system` | string | kyllä | Esim. `GoSystems`, `CRM`, `Netvisor`. |
| `source_updated_at` | timestamp | kyllä | Lähdedatan päivitysaika. |

Tärkeät säännöt:

- `customer_status in ('Active', 'Gokeep+')` hyväksytään mallin opetukseen.
- Nykyasiakkaat poistetaan prospektilistalta `business_id`:n perusteella.
- Nykyasiakkaan konserniosumat poistetaan `parent_business_id`:n perusteella.
- Jos `parent_business_id` puuttuu, se kannattaa täyttää `business_id`:llä.

### 3. `sales_order_line`

Tarkoitus: myyntihistoria asiakas- ja tuotetasolla. Tämä on tärkein tapahtumataulu sekä mallin opetukselle että tuotekohtaiselle potentiaalille.

Jyvä: yksi rivi per myyntirivi, laskurivi, tilausrivi tai koosteistettu asiakas-tuote-kuukausi-rivi.

Pääavain: `sales_line_id` tai yhdistelmäavain lähdejärjestelmän tunnisteista.

| Kenttä | Tyyppi | Pakollinen | Kuvaus |
| --- | --- | --- | --- |
| `sales_line_id` | string | kyllä | Yksilöllinen myyntirivin tunniste. |
| `account_id` | string tai integer | kyllä | Liitos `customer_master.account_id`:hen. Nykyisessä mallissa `account_id`. |
| `business_id` | string | suositus | Asiakkaan Y-tunnus denormalisoituna. Helpottaa validointia. |
| `order_id` | string | suositus | Tilaus- tai laskutunniste. |
| `order_date` | date | kyllä | Tilaus-, lasku- tai kirjauspäivä. |
| `created_year_month` | string tai date | kyllä | Kuukausi muodossa `YYYY-MM`, jos käytetään koosteajoa. |
| `status` | string | suositus | Esim. `Invoiced`. |
| `sku` | string | kyllä tuotepotentiaalille | Tuotekoodi. Nykyinen tuotepotentiaalikoodi käyttää tätä ensisijaisesti. |
| `product_id` | string | suositus | Liitos `product_master.product_id`:hen. |
| `product_name` | string | kyllä tuotepotentiaalille | Tuotenimi. Nykyinen koodi käyttää varalla kenttää `name`, jos `sku` puuttuu. |
| `product_category` | string | ei | Lähdejärjestelmän kategoria tai referenssi. |
| `quantity` | numeric | suositus | Määrä. Nykyisessä aineistossa `amount`. |
| `unit_price_eur` | numeric | suositus | Rivin yksikköhinta. Nykyisessä aineistossa `price`. |
| `net_sales_eur` | numeric | kyllä | Rivin myynti euroina. Nykyisessä mallissa `total_value`. |
| `margin_eur` | numeric | ei | Kate euroina, jos saatavilla. |
| `currency` | string | suositus | Oletus `EUR`. |
| `source_file` | string | ei | Lähdetiedosto tai erätunniste. |
| `source_system` | string | kyllä | Esim. `GoSystems`. |
| `source_updated_at` | timestamp | kyllä | Lähdedatan päivitysaika. |

Tärkeät säännöt:

- Malli tarvitsee vähintään `account_id`, `net_sales_eur` ja `order_date` tai `created_year_month`.
- Nykyisessä koodissa myynti liittyy asiakkuuteen näin: `sales_order_line.account_id -> customer_master.account_id`.
- Kolmen vuoden myynti lasketaan viimeisimmän myyntikuukauden perusteella.
- Asiakkaan vuosikeskiarvo: `avg_annual_sales_3y_eur = sales_3y_total_eur / 3`.
- Opetukseen otetaan vain asiakkaat, joiden vuosikeskiarvo on vähintään `4000 EUR`.
- Tuotekohtainen potentiaali tarvitsee tuotteen: ensisijaisesti `sku`, varalla `product_name`.

### 4. `product_master`

Tarkoitus: tuotemaster eli tuotteiden tunnisteet, nimet, hinnat, statukset ja tuoteryhmät. Tämä tarvitaan tuotekohtaiseen potentiaalin jakamiseen sekä suositusten selkeään raportointiin.

Jyvä: yksi rivi per tuote per `product_id` tai `sku`.

Pääavain: `product_id`. Uniikki vaihtoehtoinen avain: `sku`.

| Kenttä | Tyyppi | Pakollinen | Kuvaus |
| --- | --- | --- | --- |
| `product_id` | string | kyllä | Tuotteen sisäinen tunniste. Nykyisessä tuotetaulussa `product_id` tai `id`. |
| `sku` | string | kyllä | Tuotekoodi. Nykyisessä aineistossa usein `code` tai `sku`. |
| `product_name` | string | kyllä | Tuotteen nimi. Nykyisessä aineistossa `title_fi` / `product_name`. |
| `description` | string | ei | Tuotekuvaus. |
| `status` | string | kyllä | Esim. `Active`, `inactive`, `deleted`. |
| `supplier_id` | string | ei | Toimittaja tai provider. |
| `supplier_name` | string | ei | Toimittajan nimi. |
| `brand_id` | string | ei | Brändin tunniste. |
| `brand_name` | string | ei | Brändin nimi. |
| `price_eur` | numeric | suositus | Myyntihinta ilman ALV:tä. |
| `price_vat_eur` | numeric | ei | Myyntihinta ALV:n kanssa. |
| `buy_price_eur` | numeric | ei | Ostohinta. |
| `weight_g` | numeric | ei | Paino grammoina. |
| `width_value` | numeric | ei | Leveys. |
| `length_value` | numeric | ei | Pituus. |
| `depth_value` | numeric | ei | Syvyys. |
| `inventory_status` | string | ei | Varastotuotteen status. |
| `warehouse_category` | string | ei | Varastokategoria. |
| `product_group_l1_code` | string | suositus | Tuoteryhmätaso 1 koodi. |
| `product_group_l1_name` | string | suositus | Tuoteryhmätaso 1 nimi. |
| `product_group_l2_code` | string | suositus | Tuoteryhmätaso 2 koodi. |
| `product_group_l2_name` | string | suositus | Tuoteryhmätaso 2 nimi. |
| `product_group_l3_code` | string | suositus | Tuoteryhmätaso 3 koodi. |
| `product_group_l3_name` | string | suositus | Tuoteryhmätaso 3 nimi. |
| `product_group_l4_code` | string | suositus | Tuoteryhmätaso 4 koodi. |
| `product_group_l4_name` | string | suositus | Tuoteryhmätaso 4 nimi. |
| `product_group_path_code` | string | ei | Koko tuoteryhmäpolku koodeina. |
| `product_group_path_name` | string | ei | Koko tuoteryhmäpolku niminä. |
| `source_system` | string | kyllä | Esim. `GoSystems`, `Inventory`. |
| `source_updated_at` | timestamp | kyllä | Lähdedatan päivitysaika. |

Tärkeät säännöt:

- `sku` ja `product_id` pitää pystyä yhdistämään myyntiriveihin.
- Jos myyntirivillä on vain tuotenimi, tuotteen tunnistus on epävarmempi. Automaatiossa pitää suosia `sku`- tai `product_id`-liitosta.
- Tuoteryhmät kannattaa pitää masterissa valmiiksi rikastettuna, koska tuotekohtainen output on myynnille hyödyllisempi tuoteryhmittäin.

## Suositellut tukitaulut

### 5. `product_group_master`

Tarkoitus: tuoteryhmähierarkian master. Tämä voidaan myös sisällyttää `product_master`-tauluun, mutta erillinen hierarkiataulu helpottaa ylläpitoa.

Jyvä: yksi rivi per tuoteryhmätaso 4 tai per hierarkiapolku.

Pääavain: `product_group_l4_code`.

| Kenttä | Tyyppi | Pakollinen | Kuvaus |
| --- | --- | --- | --- |
| `product_group_l1_code` | string | kyllä | Päätason koodi. |
| `product_group_l1_name` | string | kyllä | Päätason nimi. |
| `product_group_l2_code` | string | kyllä | Tason 2 koodi. |
| `product_group_l2_name` | string | kyllä | Tason 2 nimi. |
| `product_group_l3_code` | string | kyllä | Tason 3 koodi. |
| `product_group_l3_name` | string | kyllä | Tason 3 nimi. |
| `product_group_l4_code` | string | kyllä | Tason 4 koodi. |
| `product_group_l4_name` | string | kyllä | Tason 4 nimi. |
| `product_group_source` | string | suositus | Mistä ryhmittely tuli, esim. inventaario, sääntö, fallback. |
| `is_active` | boolean | suositus | Onko ryhmä käytössä. |

### 6. `contact_master`

Tarkoitus: yrityksen ja päättäjien yhteystiedot myynnin listalle. Tätä ei tarvita mallin opetukseen, mutta tarvitaan myynnin käyttökelpoiseen outputiin.

Jyvä: yksi rivi per kontakti.

Pääavain: `contact_id`.

| Kenttä | Tyyppi | Pakollinen | Kuvaus |
| --- | --- | --- | --- |
| `contact_id` | string | kyllä | Kontaktin tunniste. |
| `business_id` | string | kyllä | Yrityksen Y-tunnus. |
| `first_name` | string | ei | Etunimi. |
| `last_name` | string | ei | Sukunimi. |
| `title` | string | ei | Titteli. |
| `job_title` | string | ei | Tehtävänimike. |
| `responsibility_area` | string | ei | Päättäjän vastuualue. |
| `office_profinder_id` | string | ei | Toimipaikan Profinder-tunniste, jos kontakti liittyy toimipaikkaan. |
| `phone` | string | ei | Päättäjän puhelinnumero. |
| `email` | string | ei | Päättäjän sähköpostiosoite. |
| `position` | string | ei | Päättäjän asema tai rooli. |
| `ranking` | integer | ei | Profinderin päättäjäranking. |
| `signature_clause` | string | ei | Nimenkirjoitusoikeuteen liittyvä teksti. |
| `profinder_status` | string | ei | Historia API:n `_status`: `ADDED`, `UPDATED` tai `DELETED`. |
| `is_primary` | boolean | ei | Ensisijainen kontakti yritykselle. |
| `source_system` | string | kyllä | Esim. Profinder. |
| `source_updated_at` | timestamp | kyllä | Päivitysaika. |

### 7. `external_exclusion_business`

Tarkoitus: ulkoiset poistolistat. Nykyisessä mallissa Netvisor-aineisto toimii tällaisena poistolistana.

Jyvä: yksi rivi per poistettava Y-tunnus per lähde.

Pääavain: `business_id`, `exclusion_source`.

| Kenttä | Tyyppi | Pakollinen | Kuvaus |
| --- | --- | --- | --- |
| `business_id` | string | kyllä | Poistettava Y-tunnus. |
| `exclusion_source` | string | kyllä | Esim. `Netvisor`, `manual`, `do_not_contact`. |
| `reason` | string | suositus | Poiston syy. |
| `valid_from` | date | kyllä | Poiston alkupäivä. |
| `valid_to` | date | ei | Poiston loppupäivä, jos määräaikainen. |
| `is_active` | boolean | kyllä | Onko poisto voimassa. |
| `created_at` | timestamp | kyllä | Lisäysaika. |

### 8. `manual_exclusion_rule`

Tarkoitus: manuaaliset nimisäännöt tai muut poistosäännöt. Nykyisessä mallissa nimipoistotermi on `outokumpu`.

Jyvä: yksi rivi per sääntö.

Pääavain: `rule_id`.

| Kenttä | Tyyppi | Pakollinen | Kuvaus |
| --- | --- | --- | --- |
| `rule_id` | string | kyllä | Säännön tunniste. |
| `rule_type` | string | kyllä | Esim. `name_contains`, `business_id_equals`, `industry_exclude`. |
| `rule_value` | string | kyllä | Esim. `outokumpu`. |
| `reason` | string | suositus | Miksi sääntö on olemassa. |
| `is_active` | boolean | kyllä | Onko sääntö käytössä. |
| `valid_from` | date | kyllä | Voimaantulo. |
| `valid_to` | date | ei | Voimassaolon loppu. |

### 9. `model_run`

Tarkoitus: ajonhallinta ja audit trail. Automaattiajo tarvitsee aina run-id:n, jotta tulokset voidaan jäljittää lähdedataan ja malliparametreihin.

Jyvä: yksi rivi per malliajo.

Pääavain: `run_id`.

| Kenttä | Tyyppi | Pakollinen | Kuvaus |
| --- | --- | --- | --- |
| `run_id` | string | kyllä | Yksilöllinen ajotunniste. |
| `run_started_at` | timestamp | kyllä | Ajon aloitusaika. |
| `run_finished_at` | timestamp | ei | Ajon päättymisaika. |
| `status` | string | kyllä | `running`, `success`, `failed`. |
| `as_of_date` | date | kyllä | Päivä, jonka datalla malli ajettiin. |
| `reference_date` | date | kyllä | Myyntihistorian viimeisin päivä/kuukausi. |
| `model_version` | string | kyllä | Mallikoodin tai parametrien versio. |
| `source_snapshot_id` | string | suositus | Lähdedatan snapshot/erätunniste. |
| `top_n_customers` | integer | kyllä | Nykyinen oletus `1000`. |
| `lookback_days` | integer | kyllä | Nykyinen oletus `1095` eli 3 vuotta. |
| `min_training_customer_annual_sales_eur` | numeric | kyllä | Nykyinen oletus `4000`. |
| `eligible_customer_statuses` | string tai array | kyllä | Nykyinen oletus `Active`, `Gokeep+`. |
| `error_message` | string | ei | Virheviesti epäonnistuneessa ajossa. |

### 10. `model_run_metric`

Tarkoitus: mallin metriikat ja laadun seuranta.

Jyvä: yksi rivi per mittari per ajo.

Pääavain: `run_id`, `metric_name`.

| Kenttä | Tyyppi | Pakollinen | Kuvaus |
| --- | --- | --- | --- |
| `run_id` | string | kyllä | Liitos `model_run`-tauluun. |
| `metric_name` | string | kyllä | Esim. `roc_auc`, `average_precision`, `train_rows`. |
| `metric_value` | numeric | kyllä | Mittarin arvo. |
| `metric_text` | string | ei | Tekstimuotoinen lisätieto. |

## Output-taulut

### 11. `prospect_score`

Tarkoitus: varsinainen prospektilista ja mallin tulokset.

Jyvä: yksi rivi per prospekti per ajo.

Pääavain: `run_id`, `business_id`.

| Kenttä | Tyyppi | Pakollinen | Kuvaus |
| --- | --- | --- | --- |
| `run_id` | string | kyllä | Ajon tunniste. |
| `rank` | integer | kyllä | Sijoitus. 1 = paras. |
| `priority` | string | kyllä | A, B, C tai D. |
| `company` | string | kyllä | Näytettävä yritysnimi. |
| `business_id` | string | kyllä | Prospektin Y-tunnus. |
| `parent_business_id` | string | kyllä | Emoyhtiön Y-tunnus. |
| `score` | numeric | kyllä | Mallin todennäköisyystyyppinen score. |
| `segment_median_value_eur` | numeric | kyllä | Segmentin top-asiakkaiden mediaanimyynti. |
| `model_value_eur` | numeric | kyllä | `score * segment_median_value_eur`. |
| `baseline_value_eur` | numeric | kyllä | Kokoon ja segmenttiin perustuva baseline-arvo. |
| `final_value_eur` | numeric | kyllä | Lopullinen arvo ennen pyöristystä. |
| `estimated_potential_eur` | numeric | kyllä | Myynnille näytettävä `ennustettu potentiaali`. |
| `revenue_k_eur` | numeric | kyllä | Liikevaihto tuhansina euroina. |
| `revenue_class` | string | suositus | Liikevaihtoluokka. |
| `headcount_class` | string | suositus | Henkilöstöluokka. |
| `company_segment` | string | kyllä | Mallin segmentti. |
| `segment_lift` | numeric | kyllä | Segmentin yliedustus top-asiakkaissa. |
| `industry` | string | kyllä | Toimiala. |
| `growth_bucket` | string | kyllä | Kasvuluokka. |
| `positive_signals` | string | suositus | Myynnille luettava perustelu. |
| `reference_date` | date | kyllä | Myyntihistorian viimeisin päivä/kuukausi. |
| `created_at` | timestamp | kyllä | Tuloksen kirjoitusaika. |

Prioriteettisääntö:

- `A`: rank 1-100
- `B`: rank 101-500
- `C`: rank 501-1000
- `D`: yli 1000

### 12. `prospect_product_potential`

Tarkoitus: prospektin potentiaalin jako tuotteille tai tuoteryhmille. Nykyinen koodi jakaa prospektin `estimated_potential_eur`-arvon segmentin historiallisten ostojakaumien mukaan.

Jyvä: yksi rivi per prospekti, tuote ja ajo.

Pääavain: `run_id`, `business_id`, `product_id`.

| Kenttä | Tyyppi | Pakollinen | Kuvaus |
| --- | --- | --- | --- |
| `run_id` | string | kyllä | Ajon tunniste. |
| `business_id` | string | kyllä | Prospektin Y-tunnus. |
| `product_id` | string | kyllä | Tuotteen tunniste. |
| `sku` | string | suositus | Tuotekoodi. |
| `product_name` | string | suositus | Tuotteen nimi. |
| `product_group_l1_name` | string | suositus | Tuoteryhmän päätaso. |
| `product_group_l2_name` | string | suositus | Tuoteryhmän taso 2. |
| `product_group_l3_name` | string | suositus | Tuoteryhmän taso 3. |
| `product_group_l4_name` | string | suositus | Tuoteryhmän taso 4. |
| `product_potential_eur` | numeric | kyllä | Tuotteelle allokoitu potentiaali. |
| `product_rank` | integer | kyllä | Tuotteen järjestys prospektin sisällä. |
| `weight` | numeric | suositus | Segmentin ostojakaumasta laskettu paino. |
| `created_at` | timestamp | kyllä | Tuloksen kirjoitusaika. |

Validointisääntö:

- Prospektin tuotepotentiaalien summan pitää täsmätä prospektin `estimated_potential_eur`-arvoon toleranssin sisällä.
- Nykyisessä koodissa toleranssi on `0.01`.

### 13. `prospect_exclusion_audit`

Tarkoitus: auditointi siitä, miksi yritys ei päätynyt lopulliselle prospektilistalle.

Jyvä: yksi rivi per yritys, poistosyy ja ajo.

Pääavain: `run_id`, `business_id`, `exclusion_reason`.

| Kenttä | Tyyppi | Pakollinen | Kuvaus |
| --- | --- | --- | --- |
| `run_id` | string | kyllä | Ajon tunniste. |
| `business_id` | string | kyllä | Yrityksen Y-tunnus. |
| `parent_business_id` | string | ei | Emoyhtiön Y-tunnus. |
| `company` | string | ei | Yrityksen nimi. |
| `exclusion_reason` | string | kyllä | Esim. `current_customer`, `external_exclusion`, `customer_group`, `manual_name_term`. |
| `matched_value` | string | ei | Arvo, johon poisto osui. |
| `created_at` | timestamp | kyllä | Kirjoitusaika. |

## Mallille tarvittavat näkymät

Automaattiajo kannattaa tehdä suoraan näkymistä, jotta lähdetaulujen nimet tai formaatit eivät vuoda mallikoodiin.

### `vw_model_company_features`

Yksi rivi per yritys.

Pakolliset kentät:

- `business_id`
- `company_name`
- `marketing_name`
- `parent_business_id`
- `industry`
- `revenue_k_eur`
- `headcount`
- `growth_pct`
- `revenue_class`
- `headcount_class`
- `municipality`
- `region`
- `location`
- `revenue_bucket`
- `headcount_bucket`
- `company_segment`
- `growth_bucket`
- `revenue_per_employee`

### `vw_model_customer_accounts`

Yksi rivi per asiakastili.

Pakolliset kentät:

- `account_id`
- `business_id`
- `parent_business_id`
- `account_name`
- `customer_status`
- `is_training_eligible`

### `vw_model_sales_history`

Yksi rivi per myyntirivi tai koosteistettu asiakas-tuote-kuukausi.

Pakolliset kentät:

- `sales_line_id`
- `account_id`
- `business_id`
- `order_date`
- `created_year_month`
- `sku`
- `product_id`
- `product_name`
- `quantity`
- `net_sales_eur`
- `margin_eur`

### `vw_model_product_master`

Yksi rivi per tuote.

Pakolliset kentät:

- `product_id`
- `sku`
- `product_name`
- `status`
- `product_group_l1_name`
- `product_group_l2_name`
- `product_group_l3_name`
- `product_group_l4_name`

## Avaimet ja liitokset

| Liitos | Tyyppi | Käyttö |
| --- | --- | --- |
| `sales_order_line.account_id -> customer_master.account_id` | many-to-one | Myynnin liitos asiakkuuksiin. |
| `customer_master.business_id -> company_master.business_id` | many-to-one | Asiakkaan yritysfeaturet ja nykyasiakkuuden tunnistus. |
| `sales_order_line.product_id -> product_master.product_id` | many-to-one | Tuotetiedot ja tuoteryhmät. |
| `sales_order_line.sku -> product_master.sku` | many-to-one | Vaihtoehtoinen tuoteliitos, jos `product_id` puuttuu. |
| `company_master.parent_business_id -> customer_master.parent_business_id/business_id` | lookup | Konsernipoisto. |
| `company_master.business_id -> external_exclusion_business.business_id` | lookup | Ulkoiset poistolistat. |

## Datalaadun minimivaatimukset

Ennen automaattiajoa kannattaa tarkistaa vähintään nämä:

1. `company_master.business_id` ei saa olla tyhjä ja sen pitää olla uniikki nykyisessä yritysuniversumissa.
2. `customer_master.account_id` ei saa olla tyhjä.
3. `customer_master.business_id` pitää löytyä ja olla normalisoitavissa.
4. `sales_order_line.account_id` pitää liittyä `customer_master.account_id`:hen riittävän kattavasti.
5. `sales_order_line.net_sales_eur` pitää olla numeerinen ja valuutan pitää olla tiedossa.
6. `sales_order_line.order_date` tai `created_year_month` pitää olla validi päivämäärä.
7. Mallin opetukseen pitää löytyä sekä positiivisia että negatiivisia nykyasiakkaita.
8. `Active`- ja `Gokeep+`-asiakkaita pitää olla tarpeeksi, ja osalla pitää olla vähintään `4000 EUR` vuosimyyntiä.
9. Tuotepotentiaalia varten myyntiriveillä pitää olla `sku`, `product_id` tai vähintään luotettava `product_name`.
10. `product_master.sku` tai `product_master.product_id` pitää vastata myyntirivien tuotetunnisteita.
11. `parent_business_id` pitää täyttää, jotta konsernipoistot toimivat.

## SQL-tyylinen minimirakenne

Alla on tiivis esimerkki ydintauluista. Tarkat tietotyypit kannattaa säätää käytettävän tietokannan mukaan.

```sql
create table company_master (
  business_id string not null,
  source_business_id string,
  company_name string not null,
  marketing_name string,
  parent_business_id string not null,
  industry string,
  revenue_k_eur numeric,
  headcount numeric,
  growth_pct numeric,
  revenue_class string,
  headcount_class string,
  municipality string,
  region string,
  location string,
  phone string,
  email string,
  website string,
  source_system string not null,
  source_updated_at timestamp not null,
  is_current boolean
);

create table customer_master (
  account_id string not null,
  business_id string not null,
  source_business_id string,
  parent_business_id string not null,
  account_name string not null,
  customer_status string not null,
  customer_type string,
  sales_owner string,
  sales_team string,
  customer_since date,
  is_active_customer boolean,
  is_training_eligible boolean,
  source_system string not null,
  source_updated_at timestamp not null
);

create table sales_order_line (
  sales_line_id string not null,
  account_id string not null,
  business_id string,
  order_id string,
  order_date date not null,
  created_year_month string,
  status string,
  sku string,
  product_id string,
  product_name string,
  product_category string,
  quantity numeric,
  unit_price_eur numeric,
  net_sales_eur numeric not null,
  margin_eur numeric,
  currency string,
  source_system string not null,
  source_updated_at timestamp not null
);

create table product_master (
  product_id string not null,
  sku string not null,
  product_name string not null,
  description string,
  status string not null,
  supplier_id string,
  supplier_name string,
  brand_id string,
  brand_name string,
  price_eur numeric,
  price_vat_eur numeric,
  buy_price_eur numeric,
  weight_g numeric,
  inventory_status string,
  warehouse_category string,
  product_group_l1_code string,
  product_group_l1_name string,
  product_group_l2_code string,
  product_group_l2_name string,
  product_group_l3_code string,
  product_group_l3_name string,
  product_group_l4_code string,
  product_group_l4_name string,
  product_group_path_code string,
  product_group_path_name string,
  source_system string not null,
  source_updated_at timestamp not null
);
```

## Nykyisten tiedostojen alustava vastaavuus

| Nykyinen tiedosto | Tuleva taulu |
| --- | --- |
| `haku_Myyntiin_ai_2026-04-23 (1).xlsx` | `company_master` ja `contact_master` |
| `Account_20.05.2026_combined_with_profinder.xlsx` | `customer_master` |
| `GoSystems_sales_26_05_2026_summarized.csv` | `sales_order_line` tai `sales_order_monthly_summary` |
| `GoSystems_sales_26_05_2026_combined.csv` | `sales_order_line` |
| `products_table_view.csv` | `product_master` |
| `product_master_enrichment/final_product_grouping/products_product_group_tree_final.csv` | rikastettu `product_master` |
| `product_master_enrichment/final_product_grouping/product_group_tree_final_summary.csv` | `product_group_master` |
| `Netvisor asiakastiedot 6-2026.xlsx` | `external_exclusion_business` |
| `prospect_segment_model_all_prospects.csv` | `prospect_score` |
| `prospect_product_potential.csv` | `prospect_product_potential` |

## Suositus ensimmäiseen toteutusvaiheeseen

Ensimmäiseen automaattiseen versioon riittää tämä:

1. Rakenna ja täytä `company_master`.
2. Rakenna ja täytä `customer_master`.
3. Rakenna ja täytä `sales_order_line`.
4. Rakenna ja täytä `product_master`.
5. Tee näkymät `vw_model_company_features`, `vw_model_customer_accounts`, `vw_model_sales_history` ja `vw_model_product_master`.
6. Lisää `external_exclusion_business`.
7. Lisää `model_run`, `model_run_metric`, `prospect_score` ja `prospect_product_potential`.

Kun nämä ovat käytössä, prospektimallin nykyiset Excel/CSV-lähteet voidaan vaihtaa tietokantanäkymiin ilman, että mallin liiketoimintalogiikkaa tarvitsee muuttaa olennaisesti.
