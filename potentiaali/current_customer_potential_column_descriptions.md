# Sarakeselitteet

Tama dokumentti kuvaa nykyasiakaspotentiaalin ja validointiraporttien sarakkeet.

## current_customer_potential_with_product_groups_one_row_per_customer.xlsx / customer_potential

Paataulu nykyasiakkaista: yksi rivi per asiakas, mallipisteytys, euromaarainen potentiaali ja perustelut.

- `Link`: Alkuperaisesta CRM-validointiaineistosta tullut linkki tai avauskentta.
- `Name`: Alkuperaisen CRM-validointiaineiston asiakasnimi.
- `CRM Group`: CRM-aineiston ryhma- tai konsernikentta, jos sellainen oli annettu.
- `Contact 1`: Ensimmainen CRM:ssa mainittu yhteyshenkilo.
- `Contact 2`: Toinen CRM:ssa mainittu yhteyshenkilo.
- `_input_row_id`: Alkuperaisen CRM-validointiaineiston rivinumero ennen asiakaskohtaista deduplikointia.
- `business_id`: Normalisoitu Y-tunnus muodossa 1234567-8. Paasiallinen yhdistysavain mallin, CRM:n ja myyntihistorian valilla.
- `account_id`: GoSystems/Account-aineiston asiakastilin tunniste, jos saatiin kohdistettua.
- `_normalized_name`: Tekninen nimikohdistuksen apukentta: normalisoitu asiakasnimi pienilla kirjaimilla, ilman yhtioehtoja ja sulkuteksteja.
- `rank`: Alkuperaisen mallin koko scoring-universumin sijoitus potentiaalin mukaan. Pienempi luku on parempi.
- `priority`: Prioriteettiluokka mallin rankin perusteella: A korkein, sitten B, C ja D.
- `company`: Mallissa kaytetty asiakas-/yritysnimi, yleensa account- tai yritysrekisterista.
- `score`: Mallin todennakoisyys-/samankaltaisuuspisteytys valilla 0-1. Korkeampi arvo tarkoittaa vahvempaa samankaltaisuutta parhaisiin asiakkaisiin.
- `segment_median_value_eur`: Saman yrityssegmentin parhaiden asiakkaiden mediaaniarvo euroina; kaytetaan potentiaalin mallikomponentissa.
- `model_value_eur`: Scoreen perustuva euromaarainen arvo: score kerrottuna segmentin mediaaniarvolla.
- `baseline_value_eur`: Alkuperaisen prospektimallin baseline-arvio euroina, joka perustuu mm. liikevaihtoon, henkilostoon ja segmenttiliftiin.
- `final_value_eur`: Lopullinen euromaarainen potentiaali ennen pyoristyksia / sama paatason potentiaalimittari.
- `estimated_potential_eur`: Mallin arvioitu asiakaspotentiaali euroina. Myynnille tarkein euromaarainen potentiaalikentta.
- `avg_annual_sales_3y_eur`: Asiakkaan toteutunut painotettu vuosimyynti 3 vuoden historiasta, jos ostohistoriaa loytyi.
- `revenue_k_eur`: Yrityksen liikevaihto tuhansina euroina Profinder-/yritysdatasta.
- `company_segment`: Yrityssegmentti muodossa liikevaihtoluokka_henkilostoluokka, esimerkiksi 10M-100M_100-249.
- `segment_lift`: Kuinka vahvasti kyseinen segmentti yliedustuu parhaiden asiakkaiden joukossa verrattuna asiakaskantaan. Yli 1 tarkoittaa positiivista segmenttisignaalia.
- `industry`: Yrityksen paatoimiala Profinder-/yritysdatasta.
- `positive_signals`: Tekstimuotoinen perustelu scorelle: esimerkiksi segmenttiosuma, liikevaihtoluokka, henkilostoluokka, kasvu tai toimiala.
- `is_account_customer`: Tosi/epatosi-kentta: onko rivi tunnistettu nykyiseksi asiakkaaksi account-aineiston perusteella.
- `reference_date`: Malliajon referenssipaiva, johon myyntihistoria ja lookback-laskenta suhteutetaan.
- `model_estimated_potential_eur`: Validointia varten nimetty sama mallipotentiaali euroina kuin estimated_potential_eur.
- `customer_potential_rank`: Nykyasiakasoutputin sisainen sijoitus mallipotentiaalin mukaan. Pienempi luku on parempi.
- `crm_source_row_count`: Kuinka monesta alkuperaisen CRM-validointiaineiston rivista tama asiakaskohtainen rivi muodostettiin.
- `crm_source_input_row_ids`: Alkuperaisten CRM-rivien _input_row_id-arvot, jotka yhdistettiin tahan asiakasriviin.

## current_customer_potential_with_product_groups_one_row_per_customer.xlsx / product_group_recommendations

Tuoteryhmatason white-space-suositukset asiakkaille. Ei SKU- tai tuotetasoa.

- `business_id`: Normalisoitu Y-tunnus muodossa 1234567-8. Paasiallinen yhdistysavain mallin, CRM:n ja myyntihistorian valilla.
- `company_segment`: Yrityssegmentti muodossa liikevaihtoluokka_henkilostoluokka, esimerkiksi 10M-100M_100-249.
- `product_group_code`: Suositeltavan tuoteryhman koodi alimman saatavilla olevan tuoteryhmatason mukaan.
- `product_group_name`: Suositeltavan tuoteryhman nimi alimman saatavilla olevan tuoteryhmatason mukaan.
- `recommendation_rank`: Tuoteryhmasuosituksen jarjestys kyseiselle asiakkaalle. 1 on vahvin suositus.
- `customer_sales_eur`: Asiakkaan toteutunut myynti kyseisessa tuoteryhmassa euroina myyntihistorian perusteella.
- `total_group_sales_eur`: Kyseisen tuoteryhman kokonaismyynti koko kaytetyssa myyntihistoriassa.
- `customer_group_share`: Asiakkaan tuoteryhmaosuuden osuus omasta kokonaismyynnista.
- `similar_customer_group_share`: Saman segmentin tai vertailuryhman asiakkaiden keskimaarainen tuoteryhmaosuus.
- `white_space_gap`: Erotus similar_customer_group_share - customer_group_share. Positiivinen arvo kertoo alipeitosta suhteessa vertailuryhmaan.
- `recommended_group_potential_eur`: Tuoteryhmalle allokoitu potentiaaliehdotus euroina: mallipotentiaali kerrottuna white-space-gapilla.

## current_customer_potential_with_product_groups_one_row_per_customer.xlsx / validation_against_crm

Mallin potentiaalin vertailu CRM-potentiaalitiedostoon seka mallissa olevat nykyasiakkaat, joita CRM-validointiaineistossa ei ole.

- `Link`: Alkuperaisesta CRM-validointiaineistosta tullut linkki tai avauskentta.
- `Name`: Alkuperaisen CRM-validointiaineiston asiakasnimi.
- `CRM Group`: CRM-aineiston ryhma- tai konsernikentta, jos sellainen oli annettu.
- `Contact 1`: Ensimmainen CRM:ssa mainittu yhteyshenkilo.
- `Contact 2`: Toinen CRM:ssa mainittu yhteyshenkilo.
- `_input_row_id`: Alkuperaisen CRM-validointiaineiston rivinumero ennen asiakaskohtaista deduplikointia.
- `business_id`: Normalisoitu Y-tunnus muodossa 1234567-8. Paasiallinen yhdistysavain mallin, CRM:n ja myyntihistorian valilla.
- `account_id`: GoSystems/Account-aineiston asiakastilin tunniste, jos saatiin kohdistettua.
- `_normalized_name`: Tekninen nimikohdistuksen apukentta: normalisoitu asiakasnimi pienilla kirjaimilla, ilman yhtioehtoja ja sulkuteksteja.
- `rank`: Alkuperaisen mallin koko scoring-universumin sijoitus potentiaalin mukaan. Pienempi luku on parempi.
- `priority`: Prioriteettiluokka mallin rankin perusteella: A korkein, sitten B, C ja D.
- `company`: Mallissa kaytetty asiakas-/yritysnimi, yleensa account- tai yritysrekisterista.
- `score`: Mallin todennakoisyys-/samankaltaisuuspisteytys valilla 0-1. Korkeampi arvo tarkoittaa vahvempaa samankaltaisuutta parhaisiin asiakkaisiin.
- `segment_median_value_eur`: Saman yrityssegmentin parhaiden asiakkaiden mediaaniarvo euroina; kaytetaan potentiaalin mallikomponentissa.
- `model_value_eur`: Scoreen perustuva euromaarainen arvo: score kerrottuna segmentin mediaaniarvolla.
- `baseline_value_eur`: Alkuperaisen prospektimallin baseline-arvio euroina, joka perustuu mm. liikevaihtoon, henkilostoon ja segmenttiliftiin.
- `final_value_eur`: Lopullinen euromaarainen potentiaali ennen pyoristyksia / sama paatason potentiaalimittari.
- `estimated_potential_eur`: Mallin arvioitu asiakaspotentiaali euroina. Myynnille tarkein euromaarainen potentiaalikentta.
- `avg_annual_sales_3y_eur`: Asiakkaan toteutunut painotettu vuosimyynti 3 vuoden historiasta, jos ostohistoriaa loytyi.
- `revenue_k_eur`: Yrityksen liikevaihto tuhansina euroina Profinder-/yritysdatasta.
- `company_segment`: Yrityssegmentti muodossa liikevaihtoluokka_henkilostoluokka, esimerkiksi 10M-100M_100-249.
- `segment_lift`: Kuinka vahvasti kyseinen segmentti yliedustuu parhaiden asiakkaiden joukossa verrattuna asiakaskantaan. Yli 1 tarkoittaa positiivista segmenttisignaalia.
- `industry`: Yrityksen paatoimiala Profinder-/yritysdatasta.
- `positive_signals`: Tekstimuotoinen perustelu scorelle: esimerkiksi segmenttiosuma, liikevaihtoluokka, henkilostoluokka, kasvu tai toimiala.
- `is_account_customer`: Tosi/epatosi-kentta: onko rivi tunnistettu nykyiseksi asiakkaaksi account-aineiston perusteella.
- `reference_date`: Malliajon referenssipaiva, johon myyntihistoria ja lookback-laskenta suhteutetaan.
- `model_estimated_potential_eur`: Validointia varten nimetty sama mallipotentiaali euroina kuin estimated_potential_eur.
- `customer_potential_rank`: Nykyasiakasoutputin sisainen sijoitus mallipotentiaalin mukaan. Pienempi luku on parempi.
- `crm_source_row_count`: Kuinka monesta alkuperaisen CRM-validointiaineiston rivista tama asiakaskohtainen rivi muodostettiin.
- `crm_source_input_row_ids`: Alkuperaisten CRM-rivien _input_row_id-arvot, jotka yhdistettiin tahan asiakasriviin.
- `crm_potential_eur`: CRM-validointiaineistosta laskettu potentiaali euroina. Asiakaskohtaisessa outputissa useiden CRM-rivien potentiaalit on summattu.
- `potential_diff_eur`: Mallipotentiaalin ja CRM-potentiaalin erotus euroina: model_estimated_potential_eur - crm_potential_eur.
- `potential_diff_pct`: Erotus suhteessa CRM-potentiaaliin. Tyhja, jos CRM-potentiaali on nolla.
- `validation_match_status`: CRM-vertailun status: exact_or_close, model_higher, crm_higher, missing_in_crm, missing_in_model tai missing_business_id.

## current_customer_potential_with_product_groups_one_row_per_customer.xlsx / run_log

Ajon loki: rivimaarat, osumat, puuttuvat featuret ja tuoteryhmakohdistuksen laadun mittarit.

- `metric`: Lokissa tai jakaumassa raportoitu mittarin nimi.
- `value`: Lokissa raportoidun mittarin arvo.

## current_customer_potential_with_product_groups_one_row_per_customer.xlsx / data_quality

Rivit tai mittarit, jotka vaativat datalaadun tarkistusta.

- `input_row_id`: Alkuperaisen CRM-aineiston rivitunniste datalaadun tarkistuslistalla.
- `business_id`: Normalisoitu Y-tunnus muodossa 1234567-8. Paasiallinen yhdistysavain mallin, CRM:n ja myyntihistorian valilla.
- `name`: Asiakkaan nimi datalaadun tarkistuslistalla.
- `reason`: Syy miksi rivi tai havainto nostettiin datalaadun tarkistukseen.

## current_customer_potential_validation_audit_one_row_per_customer.xlsx / technical_checks

Auditoinnin tekniset tarkistukset ja pass/review-statukset.

- `check`: Auditointiraportin teknisen tarkistuksen nimi.
- `value`: Lokissa raportoidun mittarin arvo.
- `status`: Auditointitarkistuksen tulos: pass, review tai info.

## current_customer_potential_validation_audit_one_row_per_customer.xlsx / validation_status_summary

CRM-validoinnin statusten jakauma.

- `validation_match_status`: CRM-vertailun status: exact_or_close, model_higher, crm_higher, missing_in_crm, missing_in_model tai missing_business_id.
- `rows`: Rivien lukumaara kyseisessa yhteenvedon luokassa.
- `share_of_validation_rows`: Osuus kaikista validointiriveista.

## current_customer_potential_validation_audit_one_row_per_customer.xlsx / priority_summary

Potentiaalin ja scorejen yhteenveto prioriteettiluokittain.

- `priority`: Prioriteettiluokka mallin rankin perusteella: A korkein, sitten B, C ja D.
- `rows`: Rivien lukumaara kyseisessa yhteenvedon luokassa.
- `matched_rows`: Rivien maara, joille loytyi mallipotentiaali.
- `avg_score`: Score-arvon keskiarvo valitussa ryhmassa.
- `median_potential_eur`: Mallipotentiaalin mediaani euroina valitussa ryhmassa.
- `total_potential_eur`: Mallipotentiaalin summa euroina valitussa ryhmassa.

## current_customer_potential_validation_audit_one_row_per_customer.xlsx / segment_summary

Potentiaalin ja scorejen yhteenveto yrityssegmenteittain.

- `company_segment`: Yrityssegmentti muodossa liikevaihtoluokka_henkilostoluokka, esimerkiksi 10M-100M_100-249.
- `rows`: Rivien lukumaara kyseisessa yhteenvedon luokassa.
- `avg_score`: Score-arvon keskiarvo valitussa ryhmassa.
- `median_score`: Score-arvon mediaani valitussa ryhmassa.
- `median_potential_eur`: Mallipotentiaalin mediaani euroina valitussa ryhmassa.
- `total_potential_eur`: Mallipotentiaalin summa euroina valitussa ryhmassa.

## current_customer_potential_validation_audit_one_row_per_customer.xlsx / distribution_summary

Keskeisten numeeristen mittareiden jakaumat.

- `metric`: Lokissa tai jakaumassa raportoitu mittarin nimi.
- `count`: Havaintojen lukumaara jakaumaraportissa.
- `min`: Pienin arvo jakaumaraportissa.
- `p10`: 10. persentiili eli arvo, jonka alle jaa 10 prosenttia havainnoista.
- `p25`: 25. persentiili.
- `median`: Mediaani eli 50. persentiili.
- `p75`: 75. persentiili.
- `p90`: 90. persentiili.
- `max`: Suurin arvo jakaumaraportissa.
- `mean`: Keskiarvo jakaumaraportissa.
- `sum`: Summa jakaumaraportissa.

## current_customer_potential_validation_audit_one_row_per_customer.xlsx / prior_output_comparison

Nykyisen outputin vertailu aiempiin malliajoihin.

- `source`: Vertailussa kaytetty tiedosto tai output-lahde.
- `rows`: Rivien lukumaara kyseisessa yhteenvedon luokassa.
- `score_count`: Montako score-arvoa vertailulahteessa oli.
- `score_median`: Score-arvon mediaani vertailulahteessa.
- `score_p90`: Score-arvon 90. persentiili vertailulahteessa.
- `potential_column`: Mista sarakkeesta potentiaali luettiin vertailulahteessa.
- `potential_count`: Montako potentiaaliarvoa vertailulahteessa oli.
- `potential_median_eur`: Potentiaalin mediaani vertailulahteessa.
- `potential_p90_eur`: Potentiaalin 90. persentiili vertailulahteessa.
- `potential_total_eur`: Potentiaalin kokonaissumma vertailulahteessa.

## current_customer_potential_validation_audit_one_row_per_customer.xlsx / product_group_summary

Tuoteryhmasuositusten yhteenveto tuoteryhmittain.

- `product_group_code`: Suositeltavan tuoteryhman koodi alimman saatavilla olevan tuoteryhmatason mukaan.
- `product_group_name`: Suositeltavan tuoteryhman nimi alimman saatavilla olevan tuoteryhmatason mukaan.
- `recommendation_rows`: Tuoteryhmasuositusrivien maara kyseiselle tuoteryhmalle.
- `customers`: Kuinka monelle asiakkaalle tuoteryhmaa suositeltiin.
- `total_recommended_potential_eur`: Tuoteryhman suositeltu potentiaali yhteensa euroina.
- `median_white_space_gap`: White-space-gapin mediaani tuoteryhmassa.
- `avg_similar_customer_group_share`: Vertailuryhman keskimaarainen tuoteryhmaosuus.
- `avg_customer_group_share`: Suosituksen saaneiden asiakkaiden keskimaarainen oma tuoteryhmaosuus.

## current_customer_potential_validation_audit_one_row_per_customer.xlsx / top_100_abs_crm_model_diff

100 suurinta absoluuttista eroa CRM-potentiaalin ja mallipotentiaalin valilla.

- `Name`: Alkuperaisen CRM-validointiaineiston asiakasnimi.
- `company`: Mallissa kaytetty asiakas-/yritysnimi, yleensa account- tai yritysrekisterista.
- `business_id`: Normalisoitu Y-tunnus muodossa 1234567-8. Paasiallinen yhdistysavain mallin, CRM:n ja myyntihistorian valilla.
- `priority`: Prioriteettiluokka mallin rankin perusteella: A korkein, sitten B, C ja D.
- `score`: Mallin todennakoisyys-/samankaltaisuuspisteytys valilla 0-1. Korkeampi arvo tarkoittaa vahvempaa samankaltaisuutta parhaisiin asiakkaisiin.
- `crm_potential_eur`: CRM-validointiaineistosta laskettu potentiaali euroina. Asiakaskohtaisessa outputissa useiden CRM-rivien potentiaalit on summattu.
- `model_estimated_potential_eur`: Validointia varten nimetty sama mallipotentiaali euroina kuin estimated_potential_eur.
- `potential_diff_eur`: Mallipotentiaalin ja CRM-potentiaalin erotus euroina: model_estimated_potential_eur - crm_potential_eur.
- `potential_diff_pct`: Erotus suhteessa CRM-potentiaaliin. Tyhja, jos CRM-potentiaali on nolla.
- `validation_match_status`: CRM-vertailun status: exact_or_close, model_higher, crm_higher, missing_in_crm, missing_in_model tai missing_business_id.
- `positive_signals`: Tekstimuotoinen perustelu scorelle: esimerkiksi segmenttiosuma, liikevaihtoluokka, henkilostoluokka, kasvu tai toimiala.
- `abs_potential_diff_eur`: CRM- ja mallipotentiaalin erotuksen itseisarvo euroina.

## current_customer_potential_validation_audit_one_row_per_customer.xlsx / top_100_model_higher

100 tapausta, joissa malli arvioi potentiaalin CRM:aa korkeammaksi.

- `Name`: Alkuperaisen CRM-validointiaineiston asiakasnimi.
- `company`: Mallissa kaytetty asiakas-/yritysnimi, yleensa account- tai yritysrekisterista.
- `business_id`: Normalisoitu Y-tunnus muodossa 1234567-8. Paasiallinen yhdistysavain mallin, CRM:n ja myyntihistorian valilla.
- `priority`: Prioriteettiluokka mallin rankin perusteella: A korkein, sitten B, C ja D.
- `score`: Mallin todennakoisyys-/samankaltaisuuspisteytys valilla 0-1. Korkeampi arvo tarkoittaa vahvempaa samankaltaisuutta parhaisiin asiakkaisiin.
- `crm_potential_eur`: CRM-validointiaineistosta laskettu potentiaali euroina. Asiakaskohtaisessa outputissa useiden CRM-rivien potentiaalit on summattu.
- `model_estimated_potential_eur`: Validointia varten nimetty sama mallipotentiaali euroina kuin estimated_potential_eur.
- `potential_diff_eur`: Mallipotentiaalin ja CRM-potentiaalin erotus euroina: model_estimated_potential_eur - crm_potential_eur.
- `potential_diff_pct`: Erotus suhteessa CRM-potentiaaliin. Tyhja, jos CRM-potentiaali on nolla.
- `validation_match_status`: CRM-vertailun status: exact_or_close, model_higher, crm_higher, missing_in_crm, missing_in_model tai missing_business_id.
- `positive_signals`: Tekstimuotoinen perustelu scorelle: esimerkiksi segmenttiosuma, liikevaihtoluokka, henkilostoluokka, kasvu tai toimiala.

## current_customer_potential_validation_audit_one_row_per_customer.xlsx / top_100_crm_higher

100 tapausta, joissa CRM arvioi potentiaalin mallia korkeammaksi.

- `Name`: Alkuperaisen CRM-validointiaineiston asiakasnimi.
- `company`: Mallissa kaytetty asiakas-/yritysnimi, yleensa account- tai yritysrekisterista.
- `business_id`: Normalisoitu Y-tunnus muodossa 1234567-8. Paasiallinen yhdistysavain mallin, CRM:n ja myyntihistorian valilla.
- `priority`: Prioriteettiluokka mallin rankin perusteella: A korkein, sitten B, C ja D.
- `score`: Mallin todennakoisyys-/samankaltaisuuspisteytys valilla 0-1. Korkeampi arvo tarkoittaa vahvempaa samankaltaisuutta parhaisiin asiakkaisiin.
- `crm_potential_eur`: CRM-validointiaineistosta laskettu potentiaali euroina. Asiakaskohtaisessa outputissa useiden CRM-rivien potentiaalit on summattu.
- `model_estimated_potential_eur`: Validointia varten nimetty sama mallipotentiaali euroina kuin estimated_potential_eur.
- `potential_diff_eur`: Mallipotentiaalin ja CRM-potentiaalin erotus euroina: model_estimated_potential_eur - crm_potential_eur.
- `potential_diff_pct`: Erotus suhteessa CRM-potentiaaliin. Tyhja, jos CRM-potentiaali on nolla.
- `validation_match_status`: CRM-vertailun status: exact_or_close, model_higher, crm_higher, missing_in_crm, missing_in_model tai missing_business_id.
- `positive_signals`: Tekstimuotoinen perustelu scorelle: esimerkiksi segmenttiosuma, liikevaihtoluokka, henkilostoluokka, kasvu tai toimiala.

## current_customer_potential_validation_audit_one_row_per_customer.xlsx / top_100_zero_crm_high_model

100 tapausta, joissa CRM-potentiaali on nolla mutta malli loytaa korkean potentiaalin.

- `Name`: Alkuperaisen CRM-validointiaineiston asiakasnimi.
- `company`: Mallissa kaytetty asiakas-/yritysnimi, yleensa account- tai yritysrekisterista.
- `business_id`: Normalisoitu Y-tunnus muodossa 1234567-8. Paasiallinen yhdistysavain mallin, CRM:n ja myyntihistorian valilla.
- `priority`: Prioriteettiluokka mallin rankin perusteella: A korkein, sitten B, C ja D.
- `score`: Mallin todennakoisyys-/samankaltaisuuspisteytys valilla 0-1. Korkeampi arvo tarkoittaa vahvempaa samankaltaisuutta parhaisiin asiakkaisiin.
- `crm_potential_eur`: CRM-validointiaineistosta laskettu potentiaali euroina. Asiakaskohtaisessa outputissa useiden CRM-rivien potentiaalit on summattu.
- `model_estimated_potential_eur`: Validointia varten nimetty sama mallipotentiaali euroina kuin estimated_potential_eur.
- `potential_diff_eur`: Mallipotentiaalin ja CRM-potentiaalin erotus euroina: model_estimated_potential_eur - crm_potential_eur.
- `potential_diff_pct`: Erotus suhteessa CRM-potentiaaliin. Tyhja, jos CRM-potentiaali on nolla.
- `validation_match_status`: CRM-vertailun status: exact_or_close, model_higher, crm_higher, missing_in_crm, missing_in_model tai missing_business_id.
- `positive_signals`: Tekstimuotoinen perustelu scorelle: esimerkiksi segmenttiosuma, liikevaihtoluokka, henkilostoluokka, kasvu tai toimiala.

## current_customer_potential_validation_audit_one_row_per_customer.xlsx / top_100_a_priority_customers

A-prioriteetin korkeimman potentiaalin asiakkaat kasintarkistukseen.

- `Name`: Alkuperaisen CRM-validointiaineiston asiakasnimi.
- `company`: Mallissa kaytetty asiakas-/yritysnimi, yleensa account- tai yritysrekisterista.
- `business_id`: Normalisoitu Y-tunnus muodossa 1234567-8. Paasiallinen yhdistysavain mallin, CRM:n ja myyntihistorian valilla.
- `priority`: Prioriteettiluokka mallin rankin perusteella: A korkein, sitten B, C ja D.
- `score`: Mallin todennakoisyys-/samankaltaisuuspisteytys valilla 0-1. Korkeampi arvo tarkoittaa vahvempaa samankaltaisuutta parhaisiin asiakkaisiin.
- `model_estimated_potential_eur`: Validointia varten nimetty sama mallipotentiaali euroina kuin estimated_potential_eur.
- `company_segment`: Yrityssegmentti muodossa liikevaihtoluokka_henkilostoluokka, esimerkiksi 10M-100M_100-249.
- `industry`: Yrityksen paatoimiala Profinder-/yritysdatasta.
- `positive_signals`: Tekstimuotoinen perustelu scorelle: esimerkiksi segmenttiosuma, liikevaihtoluokka, henkilostoluokka, kasvu tai toimiala.

## current_customer_potential_validation_audit_one_row_per_customer.xlsx / large_low_priority_review

Tarkistettavat tapaukset: suuri potentiaali mutta matalampi prioriteetti.

- `Name`: Alkuperaisen CRM-validointiaineiston asiakasnimi.
- `company`: Mallissa kaytetty asiakas-/yritysnimi, yleensa account- tai yritysrekisterista.
- `business_id`: Normalisoitu Y-tunnus muodossa 1234567-8. Paasiallinen yhdistysavain mallin, CRM:n ja myyntihistorian valilla.
- `priority`: Prioriteettiluokka mallin rankin perusteella: A korkein, sitten B, C ja D.
- `score`: Mallin todennakoisyys-/samankaltaisuuspisteytys valilla 0-1. Korkeampi arvo tarkoittaa vahvempaa samankaltaisuutta parhaisiin asiakkaisiin.
- `model_estimated_potential_eur`: Validointia varten nimetty sama mallipotentiaali euroina kuin estimated_potential_eur.
- `company_segment`: Yrityssegmentti muodossa liikevaihtoluokka_henkilostoluokka, esimerkiksi 10M-100M_100-249.
- `industry`: Yrityksen paatoimiala Profinder-/yritysdatasta.
- `positive_signals`: Tekstimuotoinen perustelu scorelle: esimerkiksi segmenttiosuma, liikevaihtoluokka, henkilostoluokka, kasvu tai toimiala.

## current_customer_potential_validation_audit_one_row_per_customer.xlsx / missing_business_id_review

CRM-rivit, joille ei loytynyt Y-tunnusta tai malliosumaa.

- `_input_row_id`: Alkuperaisen CRM-validointiaineiston rivinumero ennen asiakaskohtaista deduplikointia.
- `Name`: Alkuperaisen CRM-validointiaineiston asiakasnimi.
- `CRM Group`: CRM-aineiston ryhma- tai konsernikentta, jos sellainen oli annettu.
- `_normalized_name`: Tekninen nimikohdistuksen apukentta: normalisoitu asiakasnimi pienilla kirjaimilla, ilman yhtioehtoja ja sulkuteksteja.

## current_customer_potential_validation_audit_one_row_per_customer.xlsx / top_100_product_group_white_spa

100 suurinta tuoteryhma-white-space-suositusta.

- `business_id`: Normalisoitu Y-tunnus muodossa 1234567-8. Paasiallinen yhdistysavain mallin, CRM:n ja myyntihistorian valilla.
- `company_segment`: Yrityssegmentti muodossa liikevaihtoluokka_henkilostoluokka, esimerkiksi 10M-100M_100-249.
- `product_group_code`: Suositeltavan tuoteryhman koodi alimman saatavilla olevan tuoteryhmatason mukaan.
- `product_group_name`: Suositeltavan tuoteryhman nimi alimman saatavilla olevan tuoteryhmatason mukaan.
- `recommendation_rank`: Tuoteryhmasuosituksen jarjestys kyseiselle asiakkaalle. 1 on vahvin suositus.
- `customer_sales_eur`: Asiakkaan toteutunut myynti kyseisessa tuoteryhmassa euroina myyntihistorian perusteella.
- `total_group_sales_eur`: Kyseisen tuoteryhman kokonaismyynti koko kaytetyssa myyntihistoriassa.
- `customer_group_share`: Asiakkaan tuoteryhmaosuuden osuus omasta kokonaismyynnista.
- `similar_customer_group_share`: Saman segmentin tai vertailuryhman asiakkaiden keskimaarainen tuoteryhmaosuus.
- `white_space_gap`: Erotus similar_customer_group_share - customer_group_share. Positiivinen arvo kertoo alipeitosta suhteessa vertailuryhmaan.
- `recommended_group_potential_eur`: Tuoteryhmalle allokoitu potentiaaliehdotus euroina: mallipotentiaali kerrottuna white-space-gapilla.

## current_customer_potential_validation_audit_one_row_per_customer.xlsx / product_group_sanity_review

Tuoteryhmasuosituksia, joissa asiakkaalla on jo myyntia mutta vertailutaso on korkeampi.

- `business_id`: Normalisoitu Y-tunnus muodossa 1234567-8. Paasiallinen yhdistysavain mallin, CRM:n ja myyntihistorian valilla.
- `company_segment`: Yrityssegmentti muodossa liikevaihtoluokka_henkilostoluokka, esimerkiksi 10M-100M_100-249.
- `product_group_code`: Suositeltavan tuoteryhman koodi alimman saatavilla olevan tuoteryhmatason mukaan.
- `product_group_name`: Suositeltavan tuoteryhman nimi alimman saatavilla olevan tuoteryhmatason mukaan.
- `recommendation_rank`: Tuoteryhmasuosituksen jarjestys kyseiselle asiakkaalle. 1 on vahvin suositus.
- `customer_sales_eur`: Asiakkaan toteutunut myynti kyseisessa tuoteryhmassa euroina myyntihistorian perusteella.
- `total_group_sales_eur`: Kyseisen tuoteryhman kokonaismyynti koko kaytetyssa myyntihistoriassa.
- `customer_group_share`: Asiakkaan tuoteryhmaosuuden osuus omasta kokonaismyynnista.
- `similar_customer_group_share`: Saman segmentin tai vertailuryhman asiakkaiden keskimaarainen tuoteryhmaosuus.
- `white_space_gap`: Erotus similar_customer_group_share - customer_group_share. Positiivinen arvo kertoo alipeitosta suhteessa vertailuryhmaan.
- `recommended_group_potential_eur`: Tuoteryhmalle allokoitu potentiaaliehdotus euroina: mallipotentiaali kerrottuna white-space-gapilla.
