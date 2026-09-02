from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
INPUT_PATH = BASE_DIR / "products_enriched_4_level_category_tree_with_inventory.csv"
OUTPUT_CSV = BASE_DIR / "products_product_group_tree_final.csv"
OUTPUT_XLSX = BASE_DIR / "products_product_group_tree_final.xlsx"
OUTPUT_XLSX_FALLBACK = BASE_DIR / "products_product_group_tree_final_updated.xlsx"
NUMBERING_CSV = BASE_DIR / "product_group_tree_numbering.csv"
SUMMARY_CSV = BASE_DIR / "product_group_tree_final_summary.csv"


GENERIC_CATEGORY_VALUES = {
    "",
    "0",
    "muut",
    "muu",
    "marittelematon",
    "maarittelematon",
    "maeaerittelematoen",
    "määrittelemätön",
    "other",
    "others",
    "tarkistettava",
    "tarkistettavat",
    "muut / tarkistettavat",
}


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalize_text(value: object) -> str:
    text = clean_text(value).lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def compact_key(value: object) -> str:
    text = normalize_text(value)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def has_any(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


def inventory_category_path(category: str) -> tuple[str, str, str, str] | None:
    key = compact_key(category)
    if key in GENERIC_CATEGORY_VALUES:
        return None

    clothing = {
        "peruspuuvilla sekoite": ("Vaatteet", "Paidat", "T-paidat", "Perus T-paidat"),
        "t paidat": ("Vaatteet", "Paidat", "T-paidat", "T-paidat"),
        "t paita": ("Vaatteet", "Paidat", "T-paidat", "T-paidat"),
        "pikee ja kauluspaidat": ("Vaatteet", "Paidat", "Pikee- ja kauluspaidat", "Pikeepaidat ja kauluspaidat"),
        "pitkahihaiset": ("Vaatteet", "Paidat", "Pitkähihaiset paidat", "Pitkähihaiset"),
        "lyhythihaiset": ("Vaatteet", "Paidat", "Lyhythihaiset paidat", "Lyhythihaiset"),
        "hupparit ja colleget": ("Vaatteet", "Yläosat", "Hupparit ja colleget", "Hupparit ja colleget"),
        "takit": ("Vaatteet", "Ulkovaatteet", "Takit", "Takit"),
        "tuulitakki": ("Vaatteet", "Ulkovaatteet", "Takit", "Tuulitakit"),
        "liivit": ("Vaatteet", "Ulkovaatteet", "Liivit", "Liivit"),
        "fleecet": ("Vaatteet", "Ulkovaatteet", "Fleecet", "Fleecet"),
        "housut": ("Vaatteet", "Alaosat", "Housut", "Housut"),
        "muut housut": ("Vaatteet", "Alaosat", "Housut", "Muut housut"),
        "housut ja hameet": ("Vaatteet", "Alaosat", "Housut ja hameet", "Housut ja hameet"),
        "neuleet": ("Vaatteet", "Yläosat", "Neuleet", "Neuleet"),
        "kylpytakit": ("Vaatteet", "Koti- ja vapaa-ajan vaatteet", "Kylpytakit", "Kylpytakit"),
        "miehet": ("Vaatteet", "Kohderyhmät", "Miesten tuotteet", "Miesten tuotteet"),
        "unisex": ("Vaatteet", "Kohderyhmät", "Unisex", "Unisex"),
        "lapset": ("Vaatteet", "Kohderyhmät", "Lasten tuotteet", "Lasten tuotteet"),
    }
    if key in clothing:
        return clothing[key]

    accessories = {
        "lippalakki": ("Asusteet", "Päähineet", "Lippalakit", "Lippalakit"),
        "pipo": ("Asusteet", "Päähineet", "Pipot", "Pipot"),
        "paahineet": ("Asusteet", "Päähineet", "Muut päähineet", "Päähineet"),
        "tuubihuivi": ("Asusteet", "Huivit ja kaulatuotteet", "Tuubihuivit", "Tuubihuivit"),
        "huivit ja solmiot": ("Asusteet", "Huivit ja kaulatuotteet", "Huivit ja solmiot", "Huivit ja solmiot"),
        "kasineet": ("Asusteet", "Käsineet", "Käsineet", "Käsineet"),
        "kaulanauha": ("Asusteet", "Kaulanauhat", "Kaulanauhat", "Kaulanauhat"),
        "avaimenperat": ("Asusteet", "Avaimenperät", "Avaimenperät", "Avaimenperät"),
    }
    if key in accessories:
        return accessories[key]

    jewellery = {
        "kellot": ("Korut ja kellot", "Kellot", "Kellot", "Kellot"),
        "kellot ja korut": ("Korut ja kellot", "Korut", "Kellot ja korut", "Kellot ja korut"),
        "urheilukellot": ("Korut ja kellot", "Kellot", "Urheilukellot", "Urheilukellot"),
        "kaulakorut": ("Korut ja kellot", "Korut", "Kaulakorut", "Kaulakorut"),
        "korvakorut": ("Korut ja kellot", "Korut", "Korvakorut", "Korvakorut"),
        "hopea": ("Korut ja kellot", "Korut", "Hopeakorut", "Hopea"),
    }
    if key in jewellery:
        return jewellery[key]

    bags = {
        "laukut": ("Laukut ja matkatavarat", "Laukut", "Muut laukut", "Laukut"),
        "vapaa ajan laukut": ("Laukut ja matkatavarat", "Laukut", "Vapaa-ajan laukut", "Vapaa-ajan laukut"),
        "reppu": ("Laukut ja matkatavarat", "Reput", "Reput", "Reput"),
        "vapaa ajan reput": ("Laukut ja matkatavarat", "Reput", "Vapaa-ajan reput", "Vapaa-ajan reput"),
        "matkalaukku": ("Laukut ja matkatavarat", "Matkatavarat", "Matkalaukut", "Matkalaukut"),
        "ostoskassi": ("Laukut ja matkatavarat", "Ostoskassit", "Ostoskassit", "Ostoskassit"),
        "muut ostoskassit": ("Laukut ja matkatavarat", "Ostoskassit", "Muut ostoskassit", "Muut ostoskassit"),
        "ostoskassit ja korit": ("Laukut ja matkatavarat", "Ostoskassit", "Ostoskassit ja korit", "Ostoskassit ja korit"),
        "kylmalaukut ja korit": ("Laukut ja matkatavarat", "Kylmälaukut", "Kylmälaukut ja -korit", "Kylmälaukut ja -korit"),
    }
    if key in bags:
        return bags[key]

    drinkware = {
        "juomapullot": ("Koti ja keittiö", "Juoma-astiat", "Juomapullot", "Juomapullot"),
        "juoma ja termospullot": ("Koti ja keittiö", "Juoma-astiat", "Juoma- ja termospullot", "Juoma- ja termospullot"),
        "termospullot": ("Koti ja keittiö", "Juoma-astiat", "Termospullot", "Termospullot"),
        "termosmuki": ("Koti ja keittiö", "Juoma-astiat", "Termosmukit", "Termosmukit"),
        "mukit": ("Koti ja keittiö", "Juoma-astiat", "Mukit", "Mukit"),
        "posliinimuki": ("Koti ja keittiö", "Juoma-astiat", "Mukit", "Posliinimukit"),
        "kuohuviini ja viinilasit": ("Koti ja keittiö", "Juoma-astiat", "Lasit", "Kuohuviini- ja viinilasit"),
    }
    if key in drinkware:
        return drinkware[key]

    home = {
        "koti ja keittio": ("Koti ja keittiö", "Koti ja keittiö", "Muut koti- ja keittiötuotteet", "Koti ja keittiö"),
        "keittio": ("Koti ja keittiö", "Keittiö", "Muut keittiötuotteet", "Keittiö"),
        "tekstiilit": ("Koti ja keittiö", "Kodintekstiilit", "Muut tekstiilit", "Tekstiilit"),
        "kylpypyyhkeet": ("Koti ja keittiö", "Kodintekstiilit", "Pyyhkeet", "Kylpypyyhkeet"),
        "pyyhkeet": ("Koti ja keittiö", "Kodintekstiilit", "Pyyhkeet", "Pyyhkeet"),
        "peitot ja viltit": ("Koti ja keittiö", "Kodintekstiilit", "Peitot ja viltit", "Peitot ja viltit"),
        "esiliinat ja patalaput": ("Koti ja keittiö", "Keittiötekstiilit", "Esiliinat ja patalaput", "Esiliinat ja patalaput"),
        "grillaus": ("Koti ja keittiö", "Keittiö", "Grillaus", "Grillaus"),
        "veitset ja aterimet": ("Koti ja keittiö", "Keittiö", "Veitset ja aterimet", "Veitset ja aterimet"),
        "tarjoiluvadit": ("Koti ja keittiö", "Keittiö", "Tarjoiluastiat", "Tarjoiluvadit"),
        "maljat ja kulhot": ("Koti ja keittiö", "Keittiö", "Kulhot ja maljat", "Maljat ja kulhot"),
        "paistinpannut": ("Koti ja keittiö", "Keittiö", "Paistinpannut", "Paistinpannut"),
        "kynttilajalka": ("Koti ja keittiö", "Sisustus", "Kynttilät ja kynttilänjalat", "Kynttilänjalat"),
        "kukkakimput": ("Koti ja keittiö", "Sisustus", "Kukat", "Kukkakimput"),
    }
    if key in home:
        return home[key]

    office = {
        "kynat": ("Toimisto ja paperi", "Kirjoitusvälineet", "Kynät", "Kynät"),
        "muistikirja a5": ("Toimisto ja paperi", "Muistikirjat", "Muistikirjat", "Muistikirja A5"),
        "pakkaustarvikkeet": ("Pakkaukset", "Pakkaustarvikkeet", "Pakkaustarvikkeet", "Pakkaustarvikkeet"),
    }
    if key in office:
        return office[key]

    electronics = {
        "elektroniikka": ("Elektroniikka", "Elektroniikka", "Muut elektroniikkatuotteet", "Elektroniikka"),
        "kaiuttimet": ("Elektroniikka", "Audio", "Kaiuttimet", "Kaiuttimet"),
        "kuulokkeet": ("Elektroniikka", "Audio", "Kuulokkeet", "Kuulokkeet"),
        "varavirtalahteet": ("Elektroniikka", "Virta ja lataus", "Varavirtalähteet", "Varavirtalähteet"),
        "laturit ja kaapelit": ("Elektroniikka", "Virta ja lataus", "Laturit ja kaapelit", "Laturit ja kaapelit"),
        "lamput ja valaisimet": ("Elektroniikka", "Valaisimet", "Lamput ja valaisimet", "Lamput ja valaisimet"),
    }
    if key in electronics:
        return electronics[key]

    tools = {
        "akkukoneet niiden rungot ja sarjat": ("Työkalut ja turvallisuus", "Työkalut", "Akkukoneet", "Akkukoneet ja sarjat"),
        "monitoimityokalu": ("Työkalut ja turvallisuus", "Työkalut", "Monitoimityökalut", "Monitoimityökalut"),
        "mittanauha": ("Työkalut ja turvallisuus", "Työkalut", "Mittanauhat", "Mittanauhat"),
        "porantera ja ruuvikarkisarjat": ("Työkalut ja turvallisuus", "Tarvikkeet", "Poranterä- ja ruuvikärkisarjat", "Poranterä- ja ruuvikärkisarjat"),
        "tyokalu ja tarvikesarjat": ("Työkalut ja turvallisuus", "Työkalut", "Työkalu- ja tarvikesarjat", "Työkalu- ja tarvikesarjat"),
        "suojalasit": ("Työkalut ja turvallisuus", "Suojaimet", "Suojalasit", "Suojalasit"),
        "ensiapulaukut": ("Työkalut ja turvallisuus", "Turvallisuus", "Ensiapulaukut", "Ensiapulaukut"),
        "heijastin": ("Työkalut ja turvallisuus", "Turvallisuus", "Heijastimet", "Heijastimet"),
        "tyovaatteet": ("Työkalut ja turvallisuus", "Työvaatteet", "Työvaatteet", "Työvaatteet"),
        "tyokengat ja saappaat": ("Työkalut ja turvallisuus", "Työkengät", "Työkengät ja saappaat", "Työkengät ja saappaat"),
        "tekniset": ("Työkalut ja turvallisuus", "Tekniset tuotteet", "Muut tekniset tuotteet", "Tekniset tuotteet"),
    }
    if key in tools:
        return tools[key]

    leisure_food_gifts = {
        "elintarvikkeet": ("Elintarvikkeet", "Elintarvikkeet", "Muut elintarvikkeet", "Elintarvikkeet"),
        "makeiset": ("Elintarvikkeet", "Makeiset", "Makeiset", "Makeiset"),
        "kosmetiikka": ("Hyvinvointi", "Kosmetiikka", "Kosmetiikka", "Kosmetiikka"),
        "vapaa aika": ("Vapaa-aika", "Vapaa-aika", "Muut vapaa-ajan tuotteet", "Vapaa-aika"),
        "golf": ("Vapaa-aika", "Urheilu", "Golf", "Golf"),
        "retkeily": ("Vapaa-aika", "Ulkoilu", "Retkeily", "Retkeily"),
        "pelit": ("Vapaa-aika", "Pelit", "Pelit", "Pelit"),
        "aineettomat": ("Lahjat ja palvelut", "Aineettomat tuotteet", "Aineettomat", "Aineettomat"),
        "perfect finnish lahjakortit": ("Lahjat ja palvelut", "Lahjakortit", "Perfect Finnish lahjakortit", "Perfect Finnish lahjakortit"),
        "muut lahjakortit": ("Lahjat ja palvelut", "Lahjakortit", "Muut lahjakortit", "Muut lahjakortit"),
        "hyvantekevaisyys": ("Lahjat ja palvelut", "Hyväntekeväisyys", "Hyväntekeväisyys", "Hyväntekeväisyys"),
        "joulu": ("Sesonkituotteet", "Joulu", "Joulutuotteet", "Joulu"),
        "ekologiset": ("Vastuulliset tuotteet", "Ekologiset tuotteet", "Ekologiset", "Ekologiset"),
        "client owned product": ("Muut / tarkistettavat", "Asiakastuotteet", "Asiakkaan omat tuotteet", "Client owned product"),
        "setti": ("Muut / tarkistettavat", "Setit", "Setit", "Setti"),
    }
    if key in leisure_food_gifts:
        return leisure_food_gifts[key]

    return None


def text_rule_path(row: pd.Series) -> tuple[str, str, str, str] | None:
    title = " ".join(
        clean_text(row.get(col, ""))
        for col in ["title_fi", "product_name", "sku", "code"]
    )
    desc = clean_text(row.get("description_fi", ""))
    title_key = compact_key(title)
    text_key = compact_key(f"{title} {desc}")

    if has_any(
        title_key,
        "lahjakortti",
        "e lahjakortti",
        "vapaalippu",
        "leffalippu",
        "premiumlippu",
        "elokuvalippu",
        "herkkulippu",
        "hissilippu",
        "liput ",
        " lippu",
        "finnkino",
        "biorex",
        "lippupiste",
        "ranneke",
        "lehtitilaus",
        "bookbeat",
    ):
        return ("Lahjat ja palvelut", "Lahjakortit ja liput", "Lahjakortit ja pääsyliput", "Lahjakortit ja pääsyliput")
    if has_any(title_key, "tervetulopaketti", "tervetuloa set", "aloituspaketti", "start kit", "uuden tyontekijan"):
        return ("Lahjat ja palvelut", "Tuotepaketit ja setit", "Tervetulopaketit", "Tervetulopaketit")
    if has_any(title_key, "golfpaketti", "golf"):
        return ("Vapaa-aika", "Urheilu", "Golf", "Golf")
    if has_any(title_key, "ilmapallo"):
        return ("Promootio- ja käyttötavarat", "Tapahtumatuotteet", "Ilmapallot", "Ilmapallot")
    if has_any(title_key, "heijastin", "heijastinvaljaat"):
        return ("Työkalut ja turvallisuus", "Turvallisuus", "Heijastimet", "Heijastimet")
    if has_any(title_key, "hieronta", "hammasharja", "easyfit", "rela"):
        return ("Hyvinvointi", "Hyvinvointi", "Hyvinvointituotteet", "Hyvinvointituotteet")
    if has_any(title_key, "clothing set", "kurssipuku", "puku ", "staff clothing", "technicians clothing"):
        return ("Vaatteet", "Työ- ja tiimivaatteet", "Vaatesetit", "Vaatesetit")
    if has_any(title_key, "makita", "leatherman", "tyokalu", "akkuporakone", "porakone", "rullamitta", "tyomaaradio"):
        return ("Työkalut ja turvallisuus", "Työkalut", "Työkalu- ja tarvikesarjat", "Työkalut ja koneet")
    if has_any(title_key, "lenovo", "jbl", "garmin", "oura", "airfryer", "philips", "oclean"):
        return ("Elektroniikka", "Elektroniikka", "Elektroniikkatuotteet", "Elektroniikkatuotteet")
    if has_any(
        title_key,
        "iittala",
        "arabia",
        "marimekko",
        "kastehelmi",
        "aalto",
        "unikko",
        "lasit",
        "viinilasi",
        "maljakko",
        "huopa",
        "pussilakana",
        "lautaset",
        "kulho",
        "uunivuoka",
        "veitsi",
        "leikkuulauta",
        "keittiopyyhe",
        "laudeliina",
        "kuksa",
        "saunasetti",
        "aamiaissetti",
        "uunikinnas",
        "pannulappu",
        "vedenkeitin",
        "leivanpaahdin",
        "kuumajuomalasi",
    ):
        return ("Koti ja keittiö", "Koti ja keittiö", "Koti- ja keittiösetit", "Koti- ja keittiösetit")
    if has_any(
        title_key,
        "kahvi",
        "suklaa",
        "makeinen",
        "candy",
        "chocolate",
        "r kioski",
        "aamupalakombo",
        "slaideri",
        "panini",
        "wrapkombo",
        "jaatelo",
        "juoma",
        "herkku",
    ):
        return ("Elintarvikkeet", "Elintarvikkeet", "Elintarvikesetit", "Elintarvikesetit")
    if has_any(title_key, "kukkakimppu", "floristin valinta", "kimppu"):
        return ("Koti ja keittiö", "Sisustus", "Kukat", "Kukkakimput")
    if has_any(title_key, "matkalaukku", "spinner", "samsonite"):
        return ("Laukut ja matkatavarat", "Matkatavarat", "Matkalaukut", "Matkalaukut")
    if has_any(title_key, "laukku", "huivi", "rinkka", "toilettilaukku"):
        return ("Laukut ja matkatavarat", "Laukut", "Muut laukut", "Laukut ja laukku-/asustesetit")
    if has_any(title_key, "jumppakeppi", "teltta", "retkeily", "mil tec"):
        return ("Vapaa-aika", "Ulkoilu", "Retkeily", "Retkeilytuotteet")
    if has_any(title_key, "paketti", "setti", "tuotepaketti", "bundle"):
        return ("Lahjat ja palvelut", "Tuotepaketit ja setit", "Muut tuotepaketit", "Muut tuotepaketit")

    if has_any(title_key, "juomapullo", "bottle", "flaska") or has_any(text_key, "termospullo"):
        return ("Koti ja keittiö", "Juoma-astiat", "Juomapullot", "Juomapullot")
    if has_any(title_key, "muki", "mug", "cup"):
        return ("Koti ja keittiö", "Juoma-astiat", "Mukit", "Mukit")
    if has_any(text_key, "kynttila", "candle"):
        return ("Koti ja keittiö", "Sisustus", "Kynttilät ja kynttilänjalat", "Kynttilät")
    if has_any(title_key, "t paita", "t shirt", "tee"):
        return ("Vaatteet", "Paidat", "T-paidat", "T-paidat")
    if has_any(title_key, "huppari", "hoodie", "college"):
        return ("Vaatteet", "Yläosat", "Hupparit ja colleget", "Hupparit ja colleget")
    if has_any(title_key, "takki", "jacket"):
        return ("Vaatteet", "Ulkovaatteet", "Takit", "Takit")
    if has_any(title_key, "lippalakki", "baseball cap", "cap ") or title_key.endswith(" cap"):
        return ("Asusteet", "Päähineet", "Lippalakit", "Lippalakit")
    if has_any(title_key, "pipo", "beanie"):
        return ("Asusteet", "Päähineet", "Pipot", "Pipot")
    if has_any(title_key, "kassi", "bag", "tote"):
        return ("Laukut ja matkatavarat", "Ostoskassit", "Ostoskassit", "Ostoskassit")
    if has_any(title_key, "reppu", "backpack"):
        return ("Laukut ja matkatavarat", "Reput", "Reput", "Reput")
    if has_any(title_key, "kyna", "pen"):
        return ("Toimisto ja paperi", "Kirjoitusvälineet", "Kynät", "Kynät")
    if has_any(title_key, "muistikirja", "notebook"):
        return ("Toimisto ja paperi", "Muistikirjat", "Muistikirjat", "Muistikirjat")
    if has_any(title_key, "kaiutin", "speaker"):
        return ("Elektroniikka", "Audio", "Kaiuttimet", "Kaiuttimet")
    if has_any(title_key, "kuuloke", "headphone", "earbud"):
        return ("Elektroniikka", "Audio", "Kuulokkeet", "Kuulokkeet")
    if has_any(title_key, "powerbank", "varavirt"):
        return ("Elektroniikka", "Virta ja lataus", "Varavirtalähteet", "Varavirtalähteet")
    if has_any(title_key, "makeinen", "suklaa", "candy", "chocolate"):
        return ("Elintarvikkeet", "Makeiset", "Makeiset", "Makeiset")

    return None


def seasonal_rule_path(row: pd.Series) -> tuple[str, str, str, str] | None:
    title = " ".join(
        clean_text(row.get(col, ""))
        for col in ["title_fi", "product_name"]
    )
    title_key = compact_key(title)

    if not has_any(
        title_key,
        "joulu",
        "christmas",
        "xmas",
        "tonttu",
        "gnome",
        "pikkujoulu",
        "season s greetings",
        "seasons greetings",
        "paasiai",
        "easter",
        "halloween",
        "vappu",
        "ystavanpaiva",
        "isanpaiva",
        "aitienpaiva",
        "juhannus",
    ):
        return None

    if has_any(title_key, "paasiai", "easter"):
        return ("Sesonkituotteet", "Pääsiäinen", "Pääsiäistuotteet", "Pääsiäistuotteet")
    if has_any(title_key, "halloween"):
        return ("Sesonkituotteet", "Halloween", "Halloween-tuotteet", "Halloween-tuotteet")
    if has_any(title_key, "vappu"):
        return ("Sesonkituotteet", "Vappu", "Vapputuotteet", "Vapputuotteet")
    if has_any(title_key, "ystavanpaiva"):
        return ("Sesonkituotteet", "Ystävänpäivä", "Ystävänpäivän tuotteet", "Ystävänpäivän tuotteet")
    if has_any(title_key, "isanpaiva"):
        return ("Sesonkituotteet", "Isänpäivä", "Isänpäivän tuotteet", "Isänpäivän tuotteet")
    if has_any(title_key, "aitienpaiva"):
        return ("Sesonkituotteet", "Äitienpäivä", "Äitienpäivän tuotteet", "Äitienpäivän tuotteet")
    if has_any(title_key, "juhannus"):
        return ("Sesonkituotteet", "Juhannus", "Juhannustuotteet", "Juhannustuotteet")

    if has_any(title_key, "joululimppu", "joulukinkku", "joulupuuro", "uunipuuro", "puurosetti", "piparkakku", "joulun hetki", "herkullista joulua", "christmas chocolate", "chocolate box", "joulun parhaat maut", "herkkusetti"):
        return ("Sesonkituotteet", "Joulu", "Jouluherkut", "Jouluherkut")
    if has_any(title_key, "lahjakassi", "tonttulaatikko", "christmas kuusi", "kranssi"):
        return ("Sesonkituotteet", "Joulu", "Joulupakkaukset", "Joulupakkaukset")
    if has_any(title_key, "joulupaita", "jouluneule", "joulukollari", "tonttulakki", "ugly christmas sweater"):
        return ("Sesonkituotteet", "Joulu", "Jouluvaatteet", "Jouluvaatteet")
    if has_any(title_key, "joulukortti", "christmas card", "greetings card", "season s greetings", "seasons greetings"):
        return ("Sesonkituotteet", "Joulu", "Joulukortit", "Joulukortit")
    if has_any(title_key, "tonttu", "gnome", "winteria"):
        return ("Sesonkituotteet", "Joulu", "Joulukoristeet", "Joulutontut")
    if has_any(title_key, "pikkujoulu"):
        return ("Sesonkituotteet", "Joulu", "Pikkujoulutuotteet", "Pikkujoulutuotteet")

    return ("Sesonkituotteet", "Joulu", "Joulutuotteet", "Joulutuotteet")


def old_tree_path(row: pd.Series) -> tuple[str, str, str, str] | None:
    values = [
        clean_text(row.get("category_level_1_tree", "")),
        clean_text(row.get("category_level_2_tree", "")),
        clean_text(row.get("category_level_3_tree", "")),
        clean_text(row.get("category_level_4_tree", "")),
    ]
    l1_key = compact_key(values[0])
    if all(values) and l1_key not in GENERIC_CATEGORY_VALUES:
        if l1_key != "muut tarkistettavat":
            return tuple(values)  # type: ignore[return-value]
    return None


def choose_product_group(row: pd.Series) -> tuple[str, str, str, str, str]:
    seasonal_path = seasonal_rule_path(row)
    if seasonal_path:
        return (*seasonal_path, "seasonal_title_rule")

    inventory_category = clean_text(row.get("inventory_category", ""))
    path = inventory_category_path(inventory_category)
    if path:
        return (*path, "inventory_category_mapped")

    path = text_rule_path(row)
    if path:
        return (*path, "title_description_rule")

    gosystems = clean_text(row.get("gosystems_category_name", ""))
    path = inventory_category_path(gosystems)
    if path:
        return (*path, "gosystems_category_mapped")

    path = old_tree_path(row)
    if path:
        return (*path, "previous_tree_fallback")

    warehouse = clean_text(row.get("inventory_warehouse_category", "")) or clean_text(row.get("warehousecategory", ""))
    if warehouse and normalize_text(warehouse) not in GENERIC_CATEGORY_VALUES:
        return (warehouse, "Muut / tarkistettavat", "Tarkistettavat tuotteet", "Tarkistettava", "warehouse_fallback")

    return ("Muut / tarkistettavat", "Muut / tarkistettavat", "Tarkistettavat tuotteet", "Tarkistettava", "not_classified")


def add_group_numbering(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    levels = [
        ("product_group_l1_name", "product_group_l1_code"),
        ("product_group_l2_name", "product_group_l2_code"),
        ("product_group_l3_name", "product_group_l3_code"),
        ("product_group_l4_name", "product_group_l4_code"),
    ]

    for _, code_col in levels:
        df[code_col] = ""

    numbering_rows: list[dict[str, object]] = []

    l1_names = sorted(df["product_group_l1_name"].dropna().unique(), key=normalize_text)
    for i, l1 in enumerate(l1_names, 1):
        l1_code = f"{i:02d}"
        mask_l1 = df["product_group_l1_name"] == l1
        df.loc[mask_l1, "product_group_l1_code"] = l1_code
        numbering_rows.append({"level": 1, "code": l1_code, "name": l1, "parent_code": "", "product_count": int(mask_l1.sum())})

        l2_names = sorted(df.loc[mask_l1, "product_group_l2_name"].dropna().unique(), key=normalize_text)
        for j, l2 in enumerate(l2_names, 1):
            l2_code = f"{l1_code}.{j:02d}"
            mask_l2 = mask_l1 & (df["product_group_l2_name"] == l2)
            df.loc[mask_l2, "product_group_l2_code"] = l2_code
            numbering_rows.append({"level": 2, "code": l2_code, "name": l2, "parent_code": l1_code, "product_count": int(mask_l2.sum())})

            l3_names = sorted(df.loc[mask_l2, "product_group_l3_name"].dropna().unique(), key=normalize_text)
            for k, l3 in enumerate(l3_names, 1):
                l3_code = f"{l2_code}.{k:02d}"
                mask_l3 = mask_l2 & (df["product_group_l3_name"] == l3)
                df.loc[mask_l3, "product_group_l3_code"] = l3_code
                numbering_rows.append({"level": 3, "code": l3_code, "name": l3, "parent_code": l2_code, "product_count": int(mask_l3.sum())})

                l4_names = sorted(df.loc[mask_l3, "product_group_l4_name"].dropna().unique(), key=normalize_text)
                for m, l4 in enumerate(l4_names, 1):
                    l4_code = f"{l3_code}.{m:03d}"
                    mask_l4 = mask_l3 & (df["product_group_l4_name"] == l4)
                    df.loc[mask_l4, "product_group_l4_code"] = l4_code
                    numbering_rows.append({"level": 4, "code": l4_code, "name": l4, "parent_code": l3_code, "product_count": int(mask_l4.sum())})

    df["product_group_path_code"] = (
        df["product_group_l1_code"].astype(str)
        + " > "
        + df["product_group_l2_code"].astype(str)
        + " > "
        + df["product_group_l3_code"].astype(str)
        + " > "
        + df["product_group_l4_code"].astype(str)
    )
    df["product_group_path_name"] = (
        df["product_group_l1_name"].astype(str)
        + " > "
        + df["product_group_l2_name"].astype(str)
        + " > "
        + df["product_group_l3_name"].astype(str)
        + " > "
        + df["product_group_l4_name"].astype(str)
    )

    return df, pd.DataFrame(numbering_rows)


def build_outputs() -> None:
    df = pd.read_csv(INPUT_PATH, dtype=str, keep_default_na=False)

    group_rows = df.apply(choose_product_group, axis=1, result_type="expand")
    group_rows.columns = [
        "product_group_l1_name",
        "product_group_l2_name",
        "product_group_l3_name",
        "product_group_l4_name",
        "product_group_source",
    ]
    df = pd.concat([df, group_rows], axis=1)
    df, numbering = add_group_numbering(df)

    keep_columns = [
        "id",
        "code",
        "weigh",
        "packsize",
        "price",
        "pricemin",
        "pricemax",
        "price_vat",
        "buyprice",
        "brandiid",
        "warehouseinfo",
        "searchdata",
        "warehousecategory",
        "title_fi",
        "description_fi",
        "product_id",
        "product_name",
        "sku",
        "weight_value",
        "weight_unit",
        "weight_g",
        "width_value",
        "width_unit",
        "length_value",
        "length_unit",
        "depth_value",
        "depth_unit",
        "inventory_status",
        "inventory_supplier",
        "inventory_category",
        "inventory_warehouse_category",
        "inventory_sales_from_wh_selected_period",
        "product_group_l1_code",
        "product_group_l1_name",
        "product_group_l2_code",
        "product_group_l2_name",
        "product_group_l3_code",
        "product_group_l3_name",
        "product_group_l4_code",
        "product_group_l4_name",
        "product_group_path_code",
        "product_group_path_name",
        "product_group_source",
    ]
    keep_columns = [col for col in keep_columns if col in df.columns]
    final_df = df[keep_columns].copy()

    summary = (
        final_df.groupby(
            [
                "product_group_l1_code",
                "product_group_l1_name",
                "product_group_l2_code",
                "product_group_l2_name",
                "product_group_l3_code",
                "product_group_l3_name",
                "product_group_l4_code",
                "product_group_l4_name",
                "product_group_source",
            ],
            dropna=False,
        )
        .size()
        .reset_index(name="product_count")
        .sort_values(["product_group_l1_code", "product_group_l2_code", "product_group_l3_code", "product_group_l4_code"])
    )

    final_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    numbering.to_csv(NUMBERING_CSV, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_CSV, index=False, encoding="utf-8-sig")

    xlsx_path = OUTPUT_XLSX
    try:
        writer_context = pd.ExcelWriter(xlsx_path, engine="openpyxl")
    except PermissionError:
        xlsx_path = OUTPUT_XLSX_FALLBACK
        writer_context = pd.ExcelWriter(xlsx_path, engine="openpyxl")

    with writer_context as writer:
        final_df.to_excel(writer, sheet_name="products_final", index=False)
        numbering.to_excel(writer, sheet_name="group_numbering", index=False)
        summary.to_excel(writer, sheet_name="summary", index=False)

    print(f"Rows: {len(final_df)}")
    print(f"Columns: {len(final_df.columns)}")
    print(f"Product group paths: {final_df['product_group_path_name'].nunique()}")
    print("Product group source counts:")
    print(final_df["product_group_source"].value_counts().to_string())
    print("Output files:")
    print(OUTPUT_CSV)
    print(xlsx_path)
    print(NUMBERING_CSV)
    print(SUMMARY_CSV)


if __name__ == "__main__":
    build_outputs()
