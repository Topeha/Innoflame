# Datan laatuanalyysi: Profinder

Lähde: `haku_Prospektointimasterlista_2026-08-12.xlsx`

## Perustiedot

- rivimäärä: `10 715`
- uniikkeja yrityksiä Y-tunnuksella: `10 715`
- duplikaatteja Y-tunnuksella: `0`
- puuttuvia Y-tunnuksia: `0`
- puuttuvia nimiä: `0`
- puuttuvia markkinointinimiä: `0`

## Sarakerakenne

Tiedostossa on yksi sheet:

- `Sheet1`

Keskeiset sarakkeet:

- `Y-tunnus`
- `Virallinen nimi`
- `Markkinointinimi`
- `Puhelinnumero`
- `Päättäjän vastuualue`
- `Tehtävänimike`
- `Titteli`
- `Etunimi`
- `Sukunimi`
- `Päättäjän puhelinnumero`
- `Päättäjän sähköpostiosoite`
- `Henkilö ID`
- `Henkilökuntaluokka`
- `Liikevaihtoluokka`
- `Päätoimiala (TOL2025)`
- `Sivutoimialat (TOL2025)`
- `Päätoimiala (Profinder)`
- `Sivutoimialat (Profinder)`
- `Perustettu`
- `Tilikausi`
- `Liikevaihto (tuhatta €)`
- `Liikevaihdon muutos (prosenttia)`
- `Henkilöstö`
- `Kasvuluokka`
- `Riskiluokka`
- `Mobility-luokka`
- `WWW-osoite`
- `Emoyhtiön Y-tunnus`
- `Käyntiosoitteen postitoimipaikka`
- `Kunta`
- `Maakunta`
- `Tietolähteet`

## Tärkeimmät laatuhavainnot

### Tunnisteet

- `Y-tunnus` on täysi ja yksikäsitteinen.
- `Emoyhtiön Y-tunnus` puuttuu merkittävältä osalta riveistä.

### Yritys- ja toimialatiedot

- `Päätoimiala (Profinder)` on hyvin täytetty, mutta puuttuu osalta riveistä.
- `Päätoimiala (TOL2025)` on mukana, eli uusi aineisto tarjoaa paremman luokituksen kuin nykyinen malli käyttää.

### Taloustiedot

- `Liikevaihto (tuhatta €)` ja `Henkilöstö` puuttuvat noin kolmannekselta riveistä.
- `Liikevaihtoluokka` ja `Henkilökuntaluokka` ovat paljon täydempiä kuin numeeriset arvot.
- Tämä tarkoittaa, että mallin pitää edelleen tukeutua luokkafallbackeihin.

### Yhteystiedot

- `Puhelinnumero` on puutteellinen noin 10 prosentissa riveistä.
- `Päättäjän puhelinnumero` ja `Päättäjän sähköpostiosoite` ovat mukana, mutta niitä pitää käyttää outputissa varovasti, koska kaikki rivit eivät ole täydellisiä.

### Sijainti

- `Kunta` puuttuu 178 riviltä.
- `Maakunta` puuttuu 178 riviltä.
- Pääpaino sijaintifutuureissa kannattaa pitää täydemmillä kentillä, kuten kunta ja maakunta.

## Duplikaatit

- Y-tunnusduplikaatteja ei ole.
- Markkinointinimissä on pieniä nimi-duplikaatteja, mikä on odotettua.

## Johtopäätös

Uusi Profinder-aineisto on käyttökelpoinen nykyisen mallin syötteeksi, mutta:

- osa numerisista kentistä puuttuu yhä
- nykyinen fallback-logiikka liikevaihtoluokkaan ja henkilöstöluokkaan on edelleen tarpeen
- aineisto tarjoaa nykyistä paremmat mahdollisuudet toimiala- ja kontaktipohjaiseen rikastukseen

## Puuttuvat tiedot

Seuraavat asiat jäävät edelleen osittain vajaiksi:

- emoyhtiötieto
- numeerinen liikevaihto
- numeerinen henkilöstö
- sijaintitieto pienellä osalla riveistä
- päätöksentekijän sähköposti ja puhelin kaikilta riveiltä

## Suositus

Profinder kannattaa ottaa käyttöön suoraan, mutta tuoda käyttöön myös:

- TOL2025-pohjainen toimialapolku
- päätöksentekijäkontaktin erillinen käyttökelpoisuustarkastus
- vahvempi fallback ketjuttamalla `Liikevaihtoluokka` ja `Henkilökuntaluokka`

