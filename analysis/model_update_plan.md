# Join-analyysi ja mallin päivityssuunnitelma

## Join-avaimet

### Yritysaineistot

- uusi Profinder: `Y-tunnus`
- account-master: `Business ID`
- nykyinen prospektimalli: normalisoi molemmat samaan muotoon `1234567-8`

### Myyntihistoria

- myyntiaineisto käyttää `accountid`
- account-master yhdistää `ID`-kentän avulla `accountid`-arvoon
- tämän jälkeen saadaan `Business ID`

## Löytyykö Y-tunnus kaikista aineistoista

- Profinderissä `Y-tunnus` löytyy kaikilta riveiltä
- account-masterissa `Business ID` puuttuu yhdeltä riviltä
- myyntihistoriassa `Y-tunnus` ei ole suora kenttä, vaan se pitää hakea account-masterin kautta

## Löytyykö asiakasnumeroita

- myyntihistoriassa on `accountid`
- account-masterissa on `ID`
- nykyinen malli käyttää tätä liitosta myynnin ja asiakkaan yhdistämiseen

## Löytyykö account master

- kyllä, käytössä on `Account_20.05.2026_combined_with_profinder.xlsx`
- se sisältää sekä asiakasstatuksen että Profinder-rikastuksen

## Löytyykö vanhoja join-tauluja

Kyllä, työtilassa on useita rinnakkaisia versioita ja join-kerroksia, mm.:

- `Account_20.05.2026_combined.xlsx`
- `Account_20.05.2026_combined_normalized.xlsx`
- `Account_20.05.2026_combined_with_profinder.xlsx`
- `GoSystems_accounts_25_06_2026_updated_business_ids_fi_normalized.xlsx`
- `haku_Myyntiin_ai_2026-04-23 (1).xlsx`

## Join-osumat

Laskettu uuden Profinderin ja account-masterin välillä:

- Profinder-yksilöllisiä yrityksiä: `10 715`
- account-masterin yksilöllisiä yrityksiä: `5 391`
- osumia Y-tunnuksella: `2 493`
- osuus Profinderistä: noin `23.3 %`
- osuus account-masterista: noin `46.2 %`

## Myyntihistorian kattavuus

`GoSystems_sales_26_05_2026_summarized.csv` sisältää:

- `857 774` myyntiriviä
- `4 844` uniikkia `accountid`-arvoa

Myyntiriveistä account-masterin kautta business ID:hen pääsevät vain ne rivit, joilla `accountid` löytyy account-masterista.

## Kuinka moni yritys osuu myyntihistoriaan

Sovitus account-masterin kautta osoittaa, että myyntihistoriaa löytyy huomattavalle osalle account-masterin yrityksistä, mutta ei kaikille Profinder-yrityksille. Tämä on odotettavaa, koska Profinder sisältää laajemman prospektijoukon kuin CRM/account-master.

## Kuinka moni yritys jää ilman osumaa

- suuri osa Profinder-yrityksistä ei ole nykyasiakkaita eikä siis näy myyntihistoriassa suoraan
- tämä on prospektoinnin kannalta hyvä asia, koska lista jää prospekteiksi

## Kuinka moni nykyasiakas löytyy Profinderistä

- nykyisen account-masterin ja Profinderin päällekkäisyys on noin `2 493` yritystä

## Kuinka moni potentiaalinen prospekti jää jäljelle

- Profinderissä on `10 715` yritystä
- nykyasiakasosuman jälkeen jäljelle jää noin `8 222` yritystä ennen muita poistoja

## Onko nykyinen malli ajettavissa sellaisenaan uusilla aineistoilla

Kyllä, pääosin.

Perusteet:

- Profinderin keskeiset sarakkeet vastaavat nykyisen mallin käyttämiä kenttiä
- myyntihistoriasta voidaan edelleen rakentaa `accountid -> business_id`-liitos
- nykyinen malli nojaa samoihin yritystunnisteisiin ja segmenttifutuureihin

Mutta:

- uusi myyntihistoria pitää joko muuntaa nykyisen mallin odottamaan kuukausikoosteeseen tai päivittää loaderi lukemaan uuden rakenteen
- tuoteryhmäpotentiaali vaatii erillisen uuden laskentakerroksen

## Suositeltu päivitysprosessi

1. Vaihda yrityslähteeksi `haku_Prospektointimasterlista_2026-08-12.xlsx`.
2. Säilytä account-master nykyisen asiakas- ja statuslogiikan lähteenä.
3. Käytä uutta myyntihistoriaa business-ID-tason historian muodostamiseen account-masterin kautta.
4. Lisää tuoteryhmäkohtainen aggregointi L1/L2/L3-tasolle.
5. Säilytä nykyinen score-logiikka, mutta siirrä tuoteryhmäehdotukset omaksi submodeliksi.

