# Profinder-tietomalli Innoflame-projektiin

Tämä kuvaus määrittelee, mitä tietoja Profinderista tarvitaan Innoflamen prospektointi- ja potentiaalilaskennan käyttöön.

## 1. Kokonaisrakenne

Suositeltu tietomalli kannattaa jakaa neljään päätauluun:

- `companies` - yrityksen perustiedot ja luokittelu
- `company_contacts` - henkilö- ja kontaktitiedot
- `company_financials` - talous- ja kokoluokkadata
- `prospect_scores` - mallin tuottamat pisteet, potentiaali ja esitystiedot

## 2. Mitä tietoja Profinderista tarvitaan

### 2.1 Yrityksen tunnistaminen

Tarvitaan vähintään:

- `business_id` / `Y-tunnus`
- yrityksen nimi
- markkinointinimi
- Profinder ID
- emoyhtiön tunnus, jos saatavilla
- päätoimipaikan tunnus, jos saatavilla

Käyttötarkoitus:

- yhdistäminen muihin lähteisiin
- duplikaattien hallinta
- konsernirakenteen tunnistus

### 2.2 Sijainti

Tarvitaan:

- käyntiosoite
- postiosoite
- postinumero
- postitoimipaikka
- kunta
- maakunta
- maa

Käyttötarkoitus:

- maantieteellinen segmentointi
- myyntialueiden kohdistus
- alueellisen potentiaalin tarkastelu

### 2.3 Toimiala

Tarvitaan:

- päätoimiala
- sivutoimialat
- toimialaluokitus
- palvelukategoria
- yrityksen kuvaus tai liiketoiminnan kuvaus, jos saatavilla

Käyttötarkoitus:

- prospektoinnin segmentointi
- toimialapainotettu potentiaali
- tulosten suodatus ja kohdistus

Toimialojen tarkempi liiketoiminnallinen rajaus tehdään erillisessä prospektointisäännöstössä eikä sitä kovakoodata tietomallin perustekstiin.

### 2.4 Talous- ja kokoluokkatiedot

Tarvitaan:

- liikevaihto
- liikevaihdon muutos
- henkilöstömäärä
- henkilöstön muutos
- liikevoitto %
- käyttökate %
- quick ratio
- current ratio
- omavaraisuusaste
- taseen loppusumma
- oma pääoma
- pääoman tuotto %
- perustamisvuosi
- tilikausi
- kasvuluokka
- riskiluokka
- mobility-luokka
- henkilöstöluokka
- liikevaihtoluokka

Käyttötarkoitus:

- potentiaalin skaalaus
- yrityksen kokoluokan arviointi
- priorisointi
- riskin ja kasvun painotus

### 2.5 Kontaktitiedot

Tarvitaan:

- henkilön nimi
- etunimi
- sukunimi
- titteli
- tehtävänimike
- päättäjän vastuualue
- puhelinnumero
- sähköpostiosoite
- päättäjän puhelinnumero
- päättäjän sähköpostiosoite
- henkilön ID

Käyttötarkoitus:

- myynnin käyttöön menevä kontaktilista
- päättäjän tunnistaminen
- tulosten muuttaminen toimenpiteiksi

### 2.6 Metatiedot

Tarvitaan:

- lähdetiedoston nimi
- lähdeversio
- päivitysaika
- Tietolähteet-kenttä

Käyttötarkoitus:

- audit trail
- päivitysten vertailu
- datan alkuperän seuranta

## 3. Suositellut taulut

### `companies`

Yrityksen perustiedot ja luokittelu.

Pääavaimet:

- `business_id`
- `profinder_id`

### `company_contacts`

Yksi tai useampi henkilö per yritys.

Pääavaimet:

- `contact_id`
- `business_id`

### `company_financials`

Talous- ja kokoluokatiedot.

Pääavaimet:

- `business_id`
- `reporting_period`

### `prospect_scores`

Mallin tuottamat pisteet ja segmentointi.

Pääavaimet:

- `business_id`
- `run_id`

## 4. Minimivaatimus mallille

Jos dataa halutaan pitää minimissä, tarvitaan vähintään:

- `business_id`
- yrityksen nimi
- toimiala
- sijainti
- liikevaihto tai liikevaihtoluokka
- henkilöstö tai henkilöstöluokka

Jos tulokset halutaan myös myyntiin käyttökelpoisiksi, mukaan kannattaa lisätä:

- henkilön nimi
- titteli
- puhelinnumero
- sähköposti

## 5. Tulosten esittämiseen tarvittava näkymä

Lopullisessa näkymässä kannattaa näyttää ainakin:

- yrityksen nimi
- business ID
- toimiala
- sijainti
- potentiaalipisteet
- potentiaalisegmentti
- arvioitu potentiaali
- henkilön nimi
- titteli
- puhelinnumero
- sähköposti
- positiiviset signaalit

## 6. Suositus Innoflamelle

Käytännöllisin malli on:

- yritys perustaulussa
- kontaktit erillisessä taulussa
- taloustiedot erillisessä taulussa
- mallipisteet ja potentiaali erillisissä output-tauluissa

Näin samaa yritystä voidaan käyttää useassa ajossa ilman että kontaktit tai pisteet sekoittuvat keskenään.
