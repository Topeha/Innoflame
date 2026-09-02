# Prospektimallin taulukuvaus

Tämä dokumentti kuvaa prospektimallin automaattiajoon tarvittavat tietokantataulut tiiviissä muodossa. Taulut on jaettu lähdetauluihin, tukitauluihin ja tulostauluihin.

![Prospektimallin tietokantataulut](assets/prospektimallin_tietokantakaavio.png)

## Lähdedatan kuvaus

Prospektimallin päälähde on GoSystem. GoSystemista tulevat ensisijaisesti asiakasdata, myyntihistoria ja tuotetiedot. Näistä muodostetaan `customer_master`, `sales_order_line` ja `product_master`.

Ulkoinen yritystieto tulee Profinderistä. Profinder täydentää yritysten perustietoja, kuten Y-tunnus, nimi, emoyhtiön Y-tunnus, toimiala, liikevaihto, henkilöstö, sijainti ja yhteystiedot. Näistä muodostetaan pääosin `company_master` ja `contact_master`.

| Lähde | Rooli mallissa | Pääasialliset taulut |
| --- | --- | --- |
| GoSystem | Päälähde asiakkaisiin, myyntiin ja tuotteisiin | `customer_master`, `sales_order_line`, `product_master` |
| Profinder | Ulkoinen yritys- ja prospektitieto | `company_master`, `contact_master` |
| Netvisor / muu poistolista | Ulkoinen poistolista nykyisille tai muuten poistettaville yrityksille | `external_exclusion_business` |

### Profinder Historia API

Profinderin yritystieto kannattaa tuoda automaattisesti Historia API:n kautta. API kuuluu Profinder B2B API -kokonaisuuteen ja käyttää API key -kirjautumista. Historia API palauttaa muuttuneet tiedot erissä `historyId`, `size` ja `after` -parametrien avulla.

| Endpoint | Käyttö | Kohdetaulu |
| --- | --- | --- |
| `GET /history/company` | Muuttuneet, uudet ja poistuneet yritykset | `company_master`, `profinder_company_history` |
| `GET /history/financial` | Uudet tilitiedot | `profinder_financial_history`, `company_master` |
| `GET /history/office` | Muuttuneet, uudet ja poistuneet toimipaikat | `profinder_office_history`, `company_master` |
| `GET /history/decisionMaker` | Muuttuneet, uudet ja poistuneet päättäjät | `contact_master`, `profinder_decision_maker_history` |

Historia API:n vastauksessa yhteiset ohjauskentät ovat `success`, `requestHistoryId`, `requestHistoryIdDate`, `nextHistoryId`, `nextHistoryIdDate`, `prevHistoryId`, `prevHistoryIdDate` ja `data`. Varsinaisissa riveissä `_status` kertoo muutoksen tyypin: `ADDED`, `UPDATED` tai `DELETED`.

Säännöllisessä ajossa viimeisin onnistuneesti käsitelty `nextHistoryId` pitää tallentaa erilliseen kontrollitauluun. Sivutus tehdään `size`-parametrilla, jonka arvo voi olla 1-1000, ja `after`-parametrilla. Yrityshaussa `after` on viimeisen rivin `businessId`; tilitiedoissa `id`; toimipaikoissa ja päättäjissä `profinderId`.

Suositeltu lisätaulu ajonhallintaan:

| Kenttä | Kuvaus |
| --- | --- |
| `source_name` | Esimerkiksi `profinder_history_company`, `profinder_history_financial`, `profinder_history_office` tai `profinder_history_decision_maker`. |
| `last_history_id` | Viimeisin onnistuneesti käsitelty `nextHistoryId`. |
| `last_history_id_date` | Viimeisimmän history-id:n päivämäärä. |
| `last_run_at` | Viimeisin onnistunut haku. |
| `status` | Ajon tila. |

## 1. `company_master`

Kuvaus: yritys- ja prospektimasteri. Sisältää koko pisteytettävän yritysjoukon eli sekä nykyasiakkaat että prospektit.

Jyvä: yksi rivi per yritys.

Pääavain: `business_id`.

| Kenttä | Kuvaus |
| --- | --- |
| `business_id` | Yrityksen Y-tunnus normalisoituna muodossa `1234567-8`. |
| `source_business_id` | Alkuperäinen Y-tunnus lähdejärjestelmästä. |
| `company_name` | Yrityksen virallinen nimi. |
| `marketing_name` | Yrityksen markkinointinimi. |
| `parent_business_id` | Emoyhtiön Y-tunnus. Jos puuttuu, käytetään yrityksen omaa Y-tunnusta. |
| `business_form` | Yritysmuoto. Profinder-kenttä `businessForm`. |
| `founded_date` | Perustamispäivä. Profinder-kenttä `founded`. |
| `industry` | Yrityksen päätoimiala. |
| `tol2008_code` | Toimialakoodi. Profinder-kenttä `tol2008Code`. |
| `tol2008_name` | Toimialan sanallinen kuvaus. Profinder-kenttä `tol2008`. |
| `revenue_k_eur` | Liikevaihto tuhansina euroina. |
| `turnover_category` | Profinderin liikevaihtoluokka, esimerkiksi `2-10 milj. euroa`. |
| `headcount` | Henkilöstömäärä. |
| `staff_category` | Profinderin henkilöstöluokka, esimerkiksi `20-49 henkilöä`. |
| `growth_pct` | Liikevaihdon muutosprosentti. |
| `growth_class` | Profinderin kasvuluokka. |
| `risk_class` | Profinderin riskiluokka. |
| `revenue_class` | Lähdejärjestelmän liikevaihtoluokka. |
| `headcount_class` | Lähdejärjestelmän henkilöstöluokka. |
| `municipality` | Kunta. |
| `region` | Maakunta tai alue. |
| `location` | Postitoimipaikka tai muu sijaintitieto. |
| `phone` | Yrityksen puhelinnumero. |
| `email` | Yrityksen yleinen sähköposti. |
| `website` | Yrityksen verkkosivu. |
| `employer_register_date` | Työnantajarekisterin aloituspäivä. |
| `prepayment_register_date` | Ennakkoperintärekisterin aloituspäivä. |
| `trade_register_date` | Kaupparekisterin aloituspäivä. |
| `vat_liability_date` | ALV-velvollisuuden aloituspäivä. |
| `profinder_status` | Historia API:n `_status`: `ADDED`, `UPDATED` tai `DELETED`. |
| `source_system` | Lähdejärjestelmä, esimerkiksi Profinder. |
| `source_updated_at` | Lähdedatan päivitysaika. |

## 2. `customer_master`

Kuvaus: asiakasmasteri. Sisältää nykyasiakkaat, asiakasstatukset ja myyntihistorian liitosavaimet.

Jyvä: yksi rivi per asiakastili.

Pääavain: `account_id`.

| Kenttä | Kuvaus |
| --- | --- |
| `account_id` | Asiakastilin tunniste ERP-/CRM-järjestelmässä. |
| `business_id` | Asiakkaan Y-tunnus normalisoituna. |
| `source_business_id` | Alkuperäinen Y-tunnus lähdejärjestelmästä. |
| `parent_business_id` | Emoyhtiön Y-tunnus konsernipoistoja varten. |
| `account_name` | Asiakkaan nimi. |
| `customer_status` | Asiakasstatus, esimerkiksi `Active`, `Gokeep+`, `direct_delivery` tai `inactive`. |
| `customer_type` | Asiakkuuden tyyppi, jos käytössä. |
| `sales_owner` | Asiakkuuden omistaja tai vastuuhenkilö. |
| `sales_team` | Myyntitiimi. |
| `customer_since` | Asiakkuuden aloituspäivä. |
| `is_active_customer` | Tieto siitä, poistetaanko yritys nykyasiakkaana prospektilistalta. |
| `is_training_eligible` | Tieto siitä, saako asiakas opettaa mallia. Nykyinen sääntö: `Active` tai `Gokeep+`. |
| `source_system` | Lähdejärjestelmä. |
| `source_updated_at` | Lähdedatan päivitysaika. |

## 3. `sales_order_line`

Kuvaus: myyntihistoria. Sisältää asiakkaiden tilaus-, lasku- tai myyntirivit. Taulua käytetään mallin opetukseen, asiakkaiden vuosimyynnin laskentaan ja tuotekohtaiseen potentiaaliin.

Jyvä: yksi rivi per myyntirivi tai asiakas-tuote-kuukausi-kooste.

Pääavain: `sales_line_id`.

| Kenttä | Kuvaus |
| --- | --- |
| `sales_line_id` | Yksilöllinen myyntirivin tunniste. |
| `account_id` | Liitos `customer_master.account_id`-kenttään. |
| `business_id` | Asiakkaan Y-tunnus denormalisoituna. |
| `order_id` | Tilaus- tai laskutunniste. |
| `order_date` | Tilaus-, lasku- tai kirjauspäivä. |
| `created_year_month` | Myyntikuukausi muodossa `YYYY-MM`. |
| `status` | Rivin tila, esimerkiksi `Invoiced`. |
| `sku` | Tuotekoodi. Tuotepotentiaalissa ensisijainen tuotetunniste. |
| `product_id` | Tuotteen sisäinen tunniste. |
| `product_name` | Tuotteen nimi. Käytetään varalla, jos `sku` puuttuu. |
| `product_category` | Lähdejärjestelmän tuotekategoria. |
| `quantity` | Myyty määrä. |
| `unit_price_eur` | Yksikköhinta euroina. |
| `net_sales_eur` | Rivin myynti euroina. Mallille pakollinen kenttä. |
| `margin_eur` | Kate euroina, jos saatavilla. |
| `currency` | Valuutta, oletus `EUR`. |
| `source_system` | Lähdejärjestelmä, esimerkiksi GoSystems. |
| `source_updated_at` | Lähdedatan päivitysaika. |

## 4. `product_master`

Kuvaus: tuotemasteri. Sisältää tuotteiden tunnisteet, nimet, hinnat, statukset ja tuoteryhmät. Tarvitaan tuotekohtaiseen potentiaalin jakamiseen ja myynnin raportointiin.

Jyvä: yksi rivi per tuote.

Pääavain: `product_id`.

Vaihtoehtoinen avain: `sku`.

| Kenttä | Kuvaus |
| --- | --- |
| `product_id` | Tuotteen sisäinen tunniste. |
| `sku` | Tuotekoodi. |
| `product_name` | Tuotteen nimi. |
| `description` | Tuotekuvaus. |
| `status` | Tuotteen status, esimerkiksi `Active`. |
| `supplier_id` | Toimittajan tunniste. |
| `supplier_name` | Toimittajan nimi. |
| `brand_id` | Brändin tunniste. |
| `brand_name` | Brändin nimi. |
| `price_eur` | Myyntihinta ilman ALV:tä. |
| `price_vat_eur` | Myyntihinta ALV:n kanssa. |
| `buy_price_eur` | Ostohinta. |
| `weight_g` | Tuotteen paino grammoina. |
| `inventory_status` | Varasto- tai saatavuusstatus. |
| `warehouse_category` | Varastokategoria. |
| `product_group_l1_code` | Tuoteryhmän päätason koodi. |
| `product_group_l1_name` | Tuoteryhmän päätason nimi. |
| `product_group_l2_code` | Tuoteryhmän tason 2 koodi. |
| `product_group_l2_name` | Tuoteryhmän tason 2 nimi. |
| `product_group_l3_code` | Tuoteryhmän tason 3 koodi. |
| `product_group_l3_name` | Tuoteryhmän tason 3 nimi. |
| `product_group_l4_code` | Tuoteryhmän tason 4 koodi. |
| `product_group_l4_name` | Tuoteryhmän tason 4 nimi. |
| `product_group_path_code` | Koko tuoteryhmäpolku koodeina. |
| `product_group_path_name` | Koko tuoteryhmäpolku niminä. |
| `source_system` | Lähdejärjestelmä. |
| `source_updated_at` | Lähdedatan päivitysaika. |

## 5. `product_group_master`

Kuvaus: tuoteryhmähierarkian master. Voidaan toteuttaa erillisenä tauluna tai sisällyttää `product_master`-tauluun.

Jyvä: yksi rivi per tuoteryhmäpolku.

Pääavain: `product_group_l4_code`.

| Kenttä | Kuvaus |
| --- | --- |
| `product_group_l1_code` | Päätason koodi. |
| `product_group_l1_name` | Päätason nimi. |
| `product_group_l2_code` | Tason 2 koodi. |
| `product_group_l2_name` | Tason 2 nimi. |
| `product_group_l3_code` | Tason 3 koodi. |
| `product_group_l3_name` | Tason 3 nimi. |
| `product_group_l4_code` | Tason 4 koodi. |
| `product_group_l4_name` | Tason 4 nimi. |
| `product_group_source` | Ryhmittelyn lähde, esimerkiksi sääntö, inventaario tai fallback. |
| `is_active` | Onko tuoteryhmä käytössä. |

## 6. `contact_master`

Kuvaus: yritysten ja päättäjien yhteystiedot. Ei tarvita mallin opetukseen, mutta tarvitaan myynnin lopulliselle prospektilistalle.

Jyvä: yksi rivi per kontakti.

Pääavain: `contact_id`.

| Kenttä | Kuvaus |
| --- | --- |
| `contact_id` | Kontaktin tunniste. |
| `business_id` | Yrityksen Y-tunnus. |
| `first_name` | Etunimi. |
| `last_name` | Sukunimi. |
| `title` | Titteli. |
| `job_title` | Tehtävänimike. |
| `responsibility_area` | Päättäjän vastuualue. |
| `office_profinder_id` | Toimipaikan Profinder-tunniste, jos kontakti liittyy toimipaikkaan. |
| `phone` | Kontaktin puhelinnumero. |
| `email` | Kontaktin sähköpostiosoite. |
| `position` | Päättäjän asema tai rooli. |
| `ranking` | Profinderin päättäjäranking. |
| `signature_clause` | Nimenkirjoitusoikeuteen liittyvä teksti. |
| `profinder_status` | Historia API:n `_status`: `ADDED`, `UPDATED` tai `DELETED`. |
| `is_primary` | Onko kontakti yrityksen ensisijainen kontakti. |
| `source_system` | Lähdejärjestelmä. |
| `source_updated_at` | Lähdedatan päivitysaika. |

## 7. `external_exclusion_business`

Kuvaus: ulkoiset poistolistat. Esimerkiksi Netvisorissa olevat asiakkaat tai muut yritykset, joita ei haluta prospektilistalle.

Jyvä: yksi rivi per poistettava Y-tunnus per lähde.

Pääavain: `business_id`, `exclusion_source`.

| Kenttä | Kuvaus |
| --- | --- |
| `business_id` | Poistettava Y-tunnus. |
| `exclusion_source` | Poistolistan lähde, esimerkiksi `Netvisor` tai `manual`. |
| `reason` | Poiston syy. |
| `valid_from` | Poiston alkupäivä. |
| `valid_to` | Poiston loppupäivä, jos määräaikainen. |
| `is_active` | Onko poisto voimassa. |
| `created_at` | Lisäysaika. |

## 8. `manual_exclusion_rule`

Kuvaus: manuaaliset poistosäännöt, esimerkiksi yrityksen nimeen perustuvat poistot.

Jyvä: yksi rivi per sääntö.

Pääavain: `rule_id`.

| Kenttä | Kuvaus |
| --- | --- |
| `rule_id` | Säännön tunniste. |
| `rule_type` | Säännön tyyppi, esimerkiksi `name_contains` tai `business_id_equals`. |
| `rule_value` | Säännössä käytettävä arvo, esimerkiksi poistettava nimiosa. |
| `reason` | Säännön perustelu. |
| `is_active` | Onko sääntö käytössä. |
| `valid_from` | Voimaantulopäivä. |
| `valid_to` | Voimassaolon loppupäivä. |

## 9. `model_run`

Kuvaus: malliajon ajonhallinta ja audit trail. Jokaisella automaattiajolla pitää olla oma `run_id`.

Jyvä: yksi rivi per malliajo.

Pääavain: `run_id`.

| Kenttä | Kuvaus |
| --- | --- |
| `run_id` | Yksilöllinen ajotunniste. |
| `run_started_at` | Ajon aloitusaika. |
| `run_finished_at` | Ajon päättymisaika. |
| `status` | Ajon tila: `running`, `success` tai `failed`. |
| `as_of_date` | Päivä, jonka datalla malli ajetaan. |
| `reference_date` | Myyntihistorian viimeisin päivä tai kuukausi. |
| `model_version` | Mallikoodin tai parametrien versio. |
| `source_snapshot_id` | Lähdedatan snapshot- tai erätunniste. |
| `top_n_customers` | Kuinka monta parasta asiakasta muodostaa positiivisen luokan. Nykyinen oletus `1000`. |
| `lookback_days` | Myyntihistorian tarkasteluikkuna. Nykyinen oletus `1095`. |
| `min_training_customer_annual_sales_eur` | Minimi vuosimyynti opetukseen. Nykyinen oletus `4000`. |
| `eligible_customer_statuses` | Opetukseen hyväksytyt statukset, nykyisin `Active` ja `Gokeep+`. |
| `error_message` | Virheviesti, jos ajo epäonnistuu. |

## 10. `model_run_metric`

Kuvaus: malliajon metriikat ja laadun seuranta.

Jyvä: yksi rivi per mittari per ajo.

Pääavain: `run_id`, `metric_name`.

| Kenttä | Kuvaus |
| --- | --- |
| `run_id` | Liitos `model_run`-tauluun. |
| `metric_name` | Mittarin nimi, esimerkiksi `roc_auc`, `average_precision`, `train_rows` tai `positive_rate`. |
| `metric_value` | Mittarin numeerinen arvo. |
| `metric_text` | Tekstimuotoinen lisätieto. |

## 11. `prospect_score`

Kuvaus: prospektimallin päätulos. Sisältää pisteytetyt prospektit, prioriteetit ja euroarvoisen potentiaalin.

Jyvä: yksi rivi per prospekti per ajo.

Pääavain: `run_id`, `business_id`.

| Kenttä | Kuvaus |
| --- | --- |
| `run_id` | Malliajon tunniste. |
| `rank` | Prospektin sijoitus. `1` on paras. |
| `priority` | Prioriteetti: `A`, `B`, `C` tai `D`. |
| `company` | Myynnille näytettävä yritysnimi. |
| `business_id` | Prospektin Y-tunnus. |
| `parent_business_id` | Emoyhtiön Y-tunnus. |
| `score` | Mallin score välillä 0-1. |
| `segment_median_value_eur` | Segmentin top-asiakkaiden mediaanimyynti. |
| `model_value_eur` | Scoreen perustuva euroarvo. |
| `baseline_value_eur` | Yrityksen kokoon ja segmenttiin perustuva baseline-arvo. |
| `final_value_eur` | Lopullinen potentiaali ennen pyöristystä. |
| `estimated_potential_eur` | Myynnille näytettävä ennustettu potentiaali. |
| `revenue_k_eur` | Liikevaihto tuhansina euroina. |
| `revenue_class` | Liikevaihtoluokka. |
| `headcount_class` | Henkilöstöluokka. |
| `company_segment` | Mallin koko-/yrityssegmentti. |
| `segment_lift` | Segmentin yliedustus top-asiakkaissa. |
| `industry` | Toimiala. |
| `growth_bucket` | Kasvuluokka. |
| `positive_signals` | Selitysteksti myynnille. |
| `reference_date` | Myyntihistorian viimeisin päivä tai kuukausi. |
| `created_at` | Tuloksen kirjoitusaika. |

## 12. `prospect_product_potential`

Kuvaus: tuotekohtainen potentiaali prospekteille. Jakaa prospektin kokonaispotentiaalin tuotteille tai tuoteryhmille historiallisten ostojakaumien perusteella.

Jyvä: yksi rivi per prospekti, tuote ja ajo.

Pääavain: `run_id`, `business_id`, `product_id`.

| Kenttä | Kuvaus |
| --- | --- |
| `run_id` | Malliajon tunniste. |
| `business_id` | Prospektin Y-tunnus. |
| `product_id` | Tuotteen tunniste. |
| `sku` | Tuotekoodi. |
| `product_name` | Tuotteen nimi. |
| `product_group_l1_name` | Tuoteryhmän päätaso. |
| `product_group_l2_name` | Tuoteryhmän taso 2. |
| `product_group_l3_name` | Tuoteryhmän taso 3. |
| `product_group_l4_name` | Tuoteryhmän taso 4. |
| `product_potential_eur` | Tuotteelle allokoitu potentiaali euroina. |
| `product_rank` | Tuotteen järjestys prospektin sisällä. |
| `weight` | Tuotteen paino segmentin ostojakaumassa. |
| `created_at` | Tuloksen kirjoitusaika. |

## 13. `prospect_exclusion_audit`

Kuvaus: audit-taulu yrityksille, jotka poistettiin prospektilistalta. Taulu kertoo, miksi yritys ei päätynyt lopulliseen listaan.

Jyvä: yksi rivi per yritys, poistosyy ja ajo.

Pääavain: `run_id`, `business_id`, `exclusion_reason`.

| Kenttä | Kuvaus |
| --- | --- |
| `run_id` | Malliajon tunniste. |
| `business_id` | Yrityksen Y-tunnus. |
| `parent_business_id` | Emoyhtiön Y-tunnus. |
| `company` | Yrityksen nimi. |
| `exclusion_reason` | Poiston syy, esimerkiksi `current_customer`, `external_exclusion`, `customer_group` tai `manual_name_term`. |
| `matched_value` | Arvo, johon poisto osui. |
| `created_at` | Kirjoitusaika. |

## Keskeiset liitokset

| Liitos | Käyttö |
| --- | --- |
| `sales_order_line.account_id -> customer_master.account_id` | Myynnin yhdistäminen asiakkaisiin. |
| `customer_master.business_id -> company_master.business_id` | Asiakkaiden yritysfeaturet ja nykyasiakkuuden tunnistus. |
| `sales_order_line.product_id -> product_master.product_id` | Myyntirivien yhdistäminen tuotteisiin. |
| `sales_order_line.sku -> product_master.sku` | Vaihtoehtoinen tuoteliitos. |
| `company_master.business_id -> external_exclusion_business.business_id` | Ulkoiset poistolistat. |
| `company_master.parent_business_id -> customer_master.business_id / parent_business_id` | Konsernipoistot. |

## Pakolliset taulut ensimmäiseen automaattiajoon

Ensimmäinen automaattiajo onnistuu näillä tauluilla:

| Taulu | Pakollisuus |
| --- | --- |
| `company_master` | Pakollinen |
| `customer_master` | Pakollinen |
| `sales_order_line` | Pakollinen |
| `product_master` | Pakollinen, jos halutaan tuotekohtainen potentiaali |
| `external_exclusion_business` | Suositeltu |
| `model_run` | Pakollinen automaattiajon hallintaan |
| `model_run_metric` | Suositeltu |
| `prospect_score` | Pakollinen tulostaulu |
| `prospect_product_potential` | Pakollinen, jos halutaan tuotekohtainen potentiaali |
