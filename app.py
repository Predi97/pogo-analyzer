#!/usr/bin/env python3
"""
PokéGO Analyzer — lokalny serwer Flask
Analizuje PGSStats.json z PGSharp: meta tiers, AI porady, eventy, ekwipunek.

Uruchomienie:
    pip install -r requirements.txt
    cp .env.example .env && vim .env   # ustaw klucz AI
    python app.py
"""

import bisect
import json
import hashlib
import logging
import math
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

def _now() -> datetime:
    """Timezone-aware UTC now."""
    return datetime.now(timezone.utc)

def _now_iso() -> str:
    return _now().isoformat()
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Paths & config ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / "baza_pogo.db"

AI_PROVIDER       = os.getenv("AI_PROVIDER", "gemini")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AZURE_ENDPOINT    = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_API_KEY     = os.getenv("AZURE_OPENAI_KEY", "")
AZURE_DEPLOYMENT  = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
AZURE_API_VERSION = os.getenv("AZURE_API_VERSION", "2024-02-01")

TIER_REFRESH_HOURS  = 24
EVENT_REFRESH_HOURS = 6

SCRAPEDDUCK_URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/events.min.json"
POKEBASE_URL    = "https://pokebase.app/pokemon-go/tier-lists"

SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "pogo-local-2024-changeme")

# ── Singleton in-memory state (single-user local app) ─────────────────────────
_state: dict = {"pokemons": [], "items": [], "loaded": False}

# ── Database ──────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS ai_cache (
            hash        TEXT PRIMARY KEY,
            label       TEXT,
            response    TEXT NOT NULL,
            model       TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tier_list (
            pokemon_name TEXT,
            tier         TEXT,
            category     TEXT,
            scraped_at   TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (pokemon_name, category)
        );

        CREATE TABLE IF NOT EXISTS events (
            id          TEXT PRIMARY KEY,
            name        TEXT,
            start_time  TEXT,
            end_time    TEXT,
            event_type  TEXT,
            raw_json    TEXT,
            fetched_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS event_strategies (
            event_id     TEXT,
            account_hash TEXT,
            strategy     TEXT NOT NULL,
            created_at   TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (event_id, account_hash)
        );

        CREATE TABLE IF NOT EXISTS scrape_log (
            source      TEXT PRIMARY KEY,
            last_ok     TEXT,
            last_err    TEXT
        );

        CREATE TABLE IF NOT EXISTS last_upload (
            id       INTEGER PRIMARY KEY CHECK(id=1),
            raw_json TEXT NOT NULL,
            saved_at TEXT DEFAULT (datetime('now'))
        );
        """)
    log.info("DB ready: %s", DB_PATH)


# ── Pokedex & item dictionaries ───────────────────────────────────────────────

DEX: dict[int, str] = {
    1:"Bulbasaur",2:"Ivysaur",3:"Venusaur",4:"Charmander",5:"Charmeleon",
    6:"Charizard",7:"Squirtle",8:"Wartortle",9:"Blastoise",10:"Caterpie",
    11:"Metapod",12:"Butterfree",13:"Weedle",14:"Kakuna",15:"Beedrill",
    16:"Pidgey",17:"Pidgeotto",18:"Pidgeot",19:"Rattata",20:"Raticate",
    21:"Spearow",22:"Fearow",23:"Ekans",24:"Arbok",25:"Pikachu",26:"Raichu",
    27:"Sandshrew",28:"Sandslash",
    29:"Nidoran♀",30:"Nidorina",31:"Nidoqueen",32:"Nidoran♂",33:"Nidorino",
    34:"Nidoking",35:"Clefairy",36:"Clefable",37:"Vulpix",38:"Ninetales",
    39:"Jigglypuff",40:"Wigglytuff",41:"Zubat",42:"Golbat",43:"Oddish",
    44:"Gloom",45:"Vileplume",46:"Paras",47:"Parasect",48:"Venonat",
    49:"Venomoth",50:"Diglett",51:"Dugtrio",52:"Meowth",53:"Persian",
    54:"Psyduck",55:"Golduck",56:"Mankey",57:"Primeape",58:"Growlithe",
    59:"Arcanine",60:"Poliwag",61:"Poliwhirl",62:"Poliwrath",
    63:"Abra",64:"Kadabra",65:"Alakazam",66:"Machop",67:"Machoke",68:"Machamp",
    69:"Bellsprout",70:"Weepinbell",71:"Victreebel",72:"Tentacool",73:"Tentacruel",
    74:"Geodude",75:"Graveler",76:"Golem",77:"Ponyta",78:"Rapidash",
    79:"Slowpoke",80:"Slowbro",81:"Magnemite",82:"Magneton",83:"Farfetch'd",
    84:"Doduo",85:"Dodrio",86:"Seel",87:"Dewgong",88:"Grimer",89:"Muk",
    90:"Shellder",91:"Cloyster",92:"Gastly",93:"Haunter",94:"Gengar",
    95:"Onix",96:"Drowzee",97:"Hypno",98:"Krabby",99:"Kingler",
    100:"Voltorb",101:"Electrode",102:"Exeggcute",103:"Exeggutor",
    104:"Cubone",105:"Marowak",106:"Hitmonlee",107:"Hitmonchan",108:"Lickitung",
    109:"Koffing",110:"Weezing",111:"Rhyhorn",112:"Rhydon",113:"Chansey",
    114:"Tangela",115:"Kangaskhan",116:"Horsea",117:"Seadra",118:"Goldeen",
    119:"Seaking",120:"Staryu",121:"Starmie",122:"Mr. Mime",123:"Scyther",
    124:"Jynx",125:"Electabuzz",126:"Magmar",127:"Pinsir",128:"Tauros",
    129:"Magikarp",130:"Gyarados",131:"Lapras",132:"Ditto",133:"Eevee",
    134:"Vaporeon",135:"Jolteon",136:"Flareon",137:"Porygon",
    138:"Omanyte",139:"Omastar",140:"Kabuto",141:"Kabutops",142:"Aerodactyl",
    143:"Snorlax",144:"Articuno",145:"Zapdos",146:"Moltres",
    147:"Dratini",148:"Dragonair",149:"Dragonite",150:"Mewtwo",151:"Mew",
    152:"Chikorita",153:"Bayleef",154:"Meganium",155:"Cyndaquil",156:"Quilava",
    157:"Typhlosion",158:"Totodile",159:"Croconaw",160:"Feraligatr",
    161:"Sentret",162:"Furret",163:"Hoothoot",164:"Noctowl",
    165:"Ledyba",166:"Ledian",167:"Spinarak",168:"Ariados",169:"Crobat",
    170:"Chinchou",171:"Lanturn",172:"Pichu",173:"Cleffa",174:"Igglybuff",
    175:"Togepi",176:"Togetic",177:"Natu",178:"Xatu",179:"Mareep",
    180:"Flaaffy",181:"Ampharos",182:"Bellossom",183:"Marill",184:"Azumarill",
    185:"Sudowoodo",186:"Politoed",187:"Hoppip",188:"Skiploom",189:"Jumpluff",
    190:"Aipom",191:"Sunkern",192:"Sunflora",193:"Yanma",194:"Wooper",
    195:"Quagsire",196:"Espeon",197:"Umbreon",198:"Murkrow",199:"Slowking",
    200:"Misdreavus",201:"Unown",202:"Wobbuffet",203:"Girafarig",
    204:"Pineco",205:"Forretress",206:"Dunsparce",207:"Gligar",208:"Steelix",
    209:"Snubbull",210:"Granbull",211:"Qwilfish",212:"Scizor",213:"Shuckle",
    214:"Heracross",215:"Sneasel",216:"Teddiursa",217:"Ursaring",218:"Slugma",
    219:"Magcargo",220:"Swinub",221:"Piloswine",222:"Corsola",223:"Remoraid",
    224:"Octillery",225:"Delibird",226:"Mantine",227:"Skarmory",
    228:"Houndour",229:"Houndoom",230:"Kingdra",231:"Phanpy",232:"Donphan",
    233:"Porygon2",234:"Stantler",235:"Smeargle",236:"Tyrogue",237:"Hitmontop",
    238:"Smoochum",239:"Elekid",240:"Magby",241:"Miltank",242:"Blissey",
    243:"Raikou",244:"Entei",245:"Suicune",246:"Larvitar",247:"Pupitar",
    248:"Tyranitar",249:"Lugia",250:"Ho-Oh",251:"Celebi",
    252:"Treecko",253:"Grovyle",254:"Sceptile",255:"Torchic",256:"Combusken",
    257:"Blaziken",258:"Mudkip",259:"Marshtomp",260:"Swampert",
    261:"Poochyena",262:"Mightyena",263:"Zigzagoon",264:"Linoone",
    265:"Wurmple",266:"Silcoon",267:"Beautifly",268:"Cascoon",269:"Dustox",
    270:"Lotad",271:"Lombre",272:"Ludicolo",273:"Seedot",274:"Nuzleaf",
    275:"Shiftry",276:"Taillow",277:"Swellow",278:"Wingull",279:"Pelipper",
    280:"Ralts",281:"Kirlia",282:"Gardevoir",283:"Surskit",284:"Masquerain",
    285:"Shroomish",286:"Breloom",287:"Slakoth",288:"Vigoroth",289:"Slaking",
    290:"Nincada",291:"Ninjask",292:"Shedinja",293:"Whismur",294:"Loudred",
    295:"Exploud",296:"Makuhita",297:"Hariyama",298:"Azurill",299:"Nosepass",
    300:"Skitty",301:"Delcatty",302:"Sableye",303:"Mawile",304:"Aron",
    305:"Lairon",306:"Aggron",307:"Meditite",308:"Medicham",309:"Electrike",
    310:"Manectric",311:"Plusle",312:"Minun",313:"Volbeat",314:"Illumise",
    315:"Roselia",316:"Gulpin",317:"Swalot",318:"Carvanha",319:"Sharpedo",
    320:"Wailmer",321:"Wailord",322:"Numel",323:"Camerupt",324:"Torkoal",
    325:"Spoink",326:"Grumpig",327:"Spinda",328:"Trapinch",329:"Vibrava",
    330:"Flygon",331:"Cacnea",332:"Cacturne",333:"Swablu",334:"Altaria",
    335:"Zangoose",336:"Seviper",337:"Lunatone",338:"Solrock",339:"Barboach",
    340:"Whiscash",341:"Corphish",342:"Crawdaunt",343:"Baltoy",344:"Claydol",
    345:"Lileep",346:"Cradily",347:"Anorith",348:"Armaldo",349:"Feebas",
    350:"Milotic",351:"Castform",352:"Kecleon",353:"Shuppet",354:"Banette",
    355:"Duskull",356:"Dusclops",357:"Tropius",358:"Chimecho",359:"Absol",
    360:"Wynaut",361:"Snorunt",362:"Glalie",363:"Spheal",364:"Sealeo",
    365:"Walrein",366:"Clamperl",367:"Huntail",368:"Gorebyss",369:"Relicanth",
    370:"Luvdisc",371:"Bagon",372:"Shelgon",373:"Salamence",
    374:"Beldum",375:"Metang",376:"Metagross",377:"Regirock",378:"Regice",
    379:"Registeel",380:"Latias",381:"Latios",382:"Kyogre",383:"Groudon",
    384:"Rayquaza",385:"Jirachi",386:"Deoxys",
    387:"Turtwig",388:"Grotle",389:"Torterra",390:"Chimchar",391:"Monferno",
    392:"Infernape",393:"Piplup",394:"Prinplup",395:"Empoleon",
    396:"Starly",397:"Staravia",398:"Staraptor",399:"Bidoof",400:"Bibarel",
    401:"Kricketot",402:"Kricketune",403:"Shinx",404:"Luxio",405:"Luxray",
    406:"Budew",407:"Roserade",408:"Cranidos",409:"Rampardos",
    410:"Shieldon",411:"Bastiodon",412:"Burmy",413:"Wormadam",414:"Mothim",
    415:"Combee",416:"Vespiquen",417:"Pachirisu",418:"Buizel",419:"Floatzel",
    420:"Cherubi",421:"Cherrim",422:"Shellos",423:"Gastrodon",
    424:"Ambipom",425:"Drifloon",426:"Drifblim",427:"Buneary",428:"Lopunny",
    429:"Mismagius",430:"Honchkrow",431:"Glameow",432:"Purugly",
    433:"Chingling",434:"Stunky",435:"Skuntank",436:"Bronzor",437:"Bronzong",
    438:"Bonsly",439:"Mime Jr.",440:"Happiny",441:"Chatot",442:"Spiritomb",
    443:"Gible",444:"Gabite",445:"Garchomp",446:"Munchlax",447:"Riolu",
    448:"Lucario",449:"Hippopotas",450:"Hippowdon",451:"Skorupi",452:"Drapion",
    453:"Croagunk",454:"Toxicroak",455:"Carnivine",456:"Finneon",457:"Lumineon",
    458:"Mantyke",459:"Snover",460:"Abomasnow",461:"Weavile",462:"Magnezone",
    463:"Lickilicky",464:"Rhyperior",465:"Tangrowth",466:"Electivire",
    467:"Magmortar",468:"Togekiss",469:"Yanmega",470:"Leafeon",471:"Glaceon",
    472:"Gliscor",473:"Mamoswine",474:"Porygon-Z",475:"Gallade",
    476:"Probopass",477:"Dusknoir",478:"Froslass",479:"Rotom",
    480:"Uxie",481:"Mesprit",482:"Azelf",483:"Dialga",484:"Palkia",
    485:"Heatran",486:"Regigigas",487:"Giratina",488:"Cresselia",
    489:"Phione",490:"Manaphy",491:"Darkrai",492:"Shaymin",493:"Arceus",
    494:"Victini",495:"Snivy",496:"Servine",497:"Serperior",498:"Tepig",
    499:"Pignite",500:"Emboar",501:"Oshawott",502:"Dewott",503:"Samurott",
    504:"Patrat",505:"Watchog",506:"Lillipup",507:"Herdier",508:"Stoutland",
    509:"Purrloin",510:"Liepard",511:"Pansage",512:"Simisage",513:"Pansear",
    514:"Simisear",515:"Panpour",516:"Simipour",517:"Munna",518:"Musharna",
    519:"Pidove",520:"Tranquill",521:"Unfezant",522:"Blitzle",523:"Zebstrika",
    524:"Roggenrola",525:"Boldore",526:"Gigalith",527:"Woobat",528:"Swoobat",
    529:"Drilbur",530:"Excadrill",531:"Audino",532:"Timburr",533:"Gurdurr",
    534:"Conkeldurr",535:"Tympole",536:"Palpitoad",537:"Seismitoad",
    538:"Throh",539:"Sawk",540:"Sewaddle",541:"Swadloon",542:"Leavanny",
    543:"Venipede",544:"Whirlipede",545:"Scolipede",546:"Cottonee",
    547:"Whimsicott",548:"Petilil",549:"Lilligant",550:"Basculin",
    551:"Sandile",552:"Krokorok",553:"Krookodile",554:"Darumaka",
    555:"Darmanitan",556:"Maractus",557:"Dwebble",558:"Crustle",
    559:"Scraggy",560:"Scrafty",561:"Sigilyph",562:"Yamask",563:"Cofagrigus",
    564:"Tirtouga",565:"Carracosta",566:"Archen",567:"Archeops",
    568:"Trubbish",569:"Garbodor",570:"Zorua",571:"Zoroark",
    572:"Minccino",573:"Cinccino",574:"Gothita",575:"Gothorita",576:"Gothitelle",
    577:"Solosis",578:"Duosion",579:"Reuniclus",580:"Ducklett",581:"Swanna",
    582:"Vanillite",583:"Vanillish",584:"Vanilluxe",585:"Deerling",
    586:"Sawsbuck",587:"Emolga",588:"Karrablast",589:"Escavalier",
    590:"Foongus",591:"Amoonguss",592:"Frillish",593:"Jellicent",
    594:"Alomomola",595:"Joltik",596:"Galvantula",597:"Ferroseed",
    598:"Ferrothorn",599:"Klink",600:"Klang",601:"Klinklang",
    602:"Tynamo",603:"Eelektrik",604:"Eelektross",605:"Elgyem",606:"Beheeyem",
    607:"Litwick",608:"Lampent",609:"Chandelure",610:"Axew",611:"Fraxure",
    612:"Haxorus",613:"Cubchoo",614:"Beartic",615:"Cryogonal",
    616:"Shelmet",617:"Accelgor",618:"Stunfisk",619:"Mienfoo",620:"Mienshao",
    621:"Druddigon",622:"Golett",623:"Golurk",624:"Pawniard",625:"Bisharp",
    626:"Bouffalant",627:"Rufflet",628:"Braviary",629:"Vullaby",630:"Mandibuzz",
    631:"Heatmor",632:"Durant",633:"Deino",634:"Zweilous",635:"Hydreigon",
    636:"Larvesta",637:"Volcarona",638:"Cobalion",639:"Terrakion",
    640:"Virizion",641:"Tornadus",642:"Thundurus",643:"Reshiram",644:"Zekrom",
    645:"Landorus",646:"Kyurem",647:"Keldeo",648:"Meloetta",649:"Genesect",
    650:"Chespin",651:"Quilladin",652:"Chesnaught",653:"Fennekin",
    654:"Braixen",655:"Delphox",656:"Froakie",657:"Frogadier",658:"Greninja",
    659:"Bunnelby",660:"Diggersby",661:"Fletchling",662:"Fletchinder",
    663:"Talonflame",664:"Scatterbug",665:"Spewpa",666:"Vivillon",
    667:"Litleo",668:"Pyroar",669:"Flabébé",670:"Floette",671:"Florges",
    672:"Skiddo",673:"Gogoat",674:"Pancham",675:"Pangoro",676:"Furfrou",
    677:"Espurr",678:"Meowstic",679:"Honedge",680:"Doublade",681:"Aegislash",
    682:"Spritzee",683:"Aromatisse",684:"Swirlix",685:"Slurpuff",
    686:"Inkay",687:"Malamar",688:"Binacle",689:"Barbaracle",690:"Skrelp",
    691:"Dragalge",692:"Clauncher",693:"Clawitzer",694:"Helioptile",
    695:"Heliolisk",696:"Tyrunt",697:"Tyrantrum",698:"Amaura",699:"Aurorus",
    700:"Sylveon",701:"Hawlucha",702:"Dedenne",703:"Carbink",704:"Goomy",
    705:"Sliggoo",706:"Goodra",707:"Klefki",708:"Phantump",709:"Trevenant",
    710:"Pumpkaboo",711:"Gourgeist",712:"Bergmite",713:"Avalugg",
    714:"Noibat",715:"Noivern",716:"Xerneas",717:"Yveltal",718:"Zygarde",
    719:"Diancie",720:"Hoopa",721:"Volcanion",
    722:"Rowlet",723:"Dartrix",724:"Decidueye",725:"Litten",726:"Torracat",
    727:"Incineroar",728:"Popplio",729:"Brionne",730:"Primarina",
    731:"Pikipek",732:"Trumbeak",733:"Toucannon",734:"Yungoos",735:"Gumshoos",
    736:"Grubbin",737:"Charjabug",738:"Vikavolt",739:"Crabrawler",
    740:"Crabominable",741:"Oricorio",742:"Cutiefly",743:"Ribombee",
    744:"Rockruff",745:"Lycanroc",746:"Wishiwashi",747:"Mareanie",
    748:"Toxapex",749:"Mudbray",750:"Mudsdale",751:"Dewpider",752:"Araquanid",
    753:"Fomantis",754:"Lurantis",755:"Morelull",756:"Shiinotic",
    757:"Salandit",758:"Salazzle",759:"Stufful",760:"Bewear",
    761:"Bounsweet",762:"Steenee",763:"Tsareena",764:"Comfey",
    765:"Oranguru",766:"Passimian",767:"Wimpod",768:"Golisopod",
    769:"Sandygast",770:"Palossand",771:"Pyukumuku",772:"Type: Null",
    773:"Silvally",774:"Minior",775:"Komala",776:"Turtonator",
    777:"Togedemaru",778:"Mimikyu",779:"Bruxish",780:"Drampa",781:"Dhelmise",
    782:"Jangmo-o",783:"Hakamo-o",784:"Kommo-o",785:"Tapu Koko",
    786:"Tapu Lele",787:"Tapu Bulu",788:"Tapu Fini",789:"Cosmog",
    790:"Cosmoem",791:"Solgaleo",792:"Lunala",793:"Nihilego",794:"Buzzwole",
    795:"Pheromosa",796:"Xurkitree",797:"Celesteela",798:"Kartana",
    799:"Guzzlord",800:"Necrozma",801:"Magearna",802:"Marshadow",
    803:"Poipole",804:"Naganadel",805:"Stakataka",806:"Blacephalon",
    807:"Zeraora",808:"Meltan",809:"Melmetal",
    810:"Grookey",811:"Thwackey",812:"Rillaboom",813:"Scorbunny",
    814:"Raboot",815:"Cinderace",816:"Sobble",817:"Drizzile",818:"Inteleon",
    819:"Skwovet",820:"Greedent",821:"Rookidee",822:"Corvisquire",
    823:"Corviknight",824:"Blipbug",825:"Dottler",826:"Orbeetle",
    827:"Nickit",828:"Thievul",829:"Gossifleur",830:"Eldegoss",
    831:"Wooloo",832:"Dubwool",833:"Chewtle",834:"Drednaw",835:"Yamper",
    836:"Boltund",837:"Rolycoly",838:"Carkol",839:"Coalossal",840:"Applin",
    841:"Flapple",842:"Appletun",843:"Silicobra",844:"Sandaconda",
    845:"Cramorant",846:"Arrokuda",847:"Barraskewda",848:"Toxel",
    849:"Toxtricity",850:"Sizzlipede",851:"Centiskorch",852:"Clobbopus",
    853:"Grapploct",854:"Sinistea",855:"Polteageist",856:"Hatenna",
    857:"Hattrem",858:"Hatterene",859:"Impidimp",860:"Morgrem",861:"Grimmsnarl",
    862:"Obstagoon",863:"Perrserker",864:"Cursola",865:"Sirfetch'd",
    866:"Mr. Rime",867:"Runerigus",868:"Milcery",869:"Alcremie",870:"Falinks",
    871:"Pincurchin",872:"Snom",873:"Frosmoth",874:"Stonjourner",875:"Eiscue",
    876:"Indeedee",877:"Morpeko",878:"Cufant",879:"Copperajah",
    880:"Dracozolt",881:"Arctozolt",882:"Dracovish",883:"Arctovish",
    884:"Duraludon",885:"Dreepy",886:"Drakloak",887:"Dragapult",
    888:"Zacian",889:"Zamazenta",890:"Eternatus",891:"Kubfu",892:"Urshifu",
    893:"Zarude",894:"Regieleki",895:"Regidrago",896:"Glastrier",
    897:"Spectrier",898:"Calyrex",899:"Wyrdeer",900:"Kleavor",901:"Ursaluna",
    902:"Basculegion",903:"Sneasler",904:"Overqwil",905:"Enamorus",
    906:"Sprigatito",907:"Floragato",908:"Meowscarada",909:"Fuecoco",
    910:"Crocalor",911:"Skeledirge",912:"Quaxly",913:"Quaxwell",
    914:"Quaquaval",915:"Lechonk",916:"Oinkologne",917:"Tarountula",
    918:"Spidops",919:"Nymble",920:"Lokix",921:"Pawmi",922:"Pawmo",
    923:"Pawmot",924:"Tandemaus",925:"Maushold",926:"Fidough",927:"Dachsbun",
    928:"Smoliv",929:"Dolliv",930:"Arboliva",931:"Squawkabilly",932:"Nacli",
    933:"Naclstack",934:"Garganacl",935:"Charcadet",936:"Armarouge",
    937:"Ceruledge",938:"Tadbulb",939:"Bellibolt",940:"Wattrel",
    941:"Kilowattrel",942:"Maschiff",943:"Mabosstiff",944:"Shroodle",
    945:"Grafaiai",946:"Bramblin",947:"Brambleghast",948:"Toedscool",
    949:"Toedscruel",950:"Klawf",951:"Capsakid",952:"Scovillain",
    953:"Rellor",954:"Rabsca",955:"Flittle",956:"Espathra",957:"Tinkatink",
    958:"Tinkatuff",959:"Tinkaton",960:"Wiglett",961:"Wugtrio",
    962:"Bombirdier",963:"Finizen",964:"Palafin",965:"Varoom",
    966:"Revavroom",967:"Cyclizar",968:"Orthworm",969:"Glimmet",
    970:"Glimmora",971:"Greavard",972:"Houndstone",973:"Flamigo",
    974:"Cetoddle",975:"Cetitan",976:"Veluza",977:"Dondozo",978:"Tatsugiri",
    979:"Annihilape",980:"Clodsire",981:"Farigiraf",982:"Dudunsparce",
    983:"Kingambit",984:"Great Tusk",985:"Scream Tail",986:"Brute Bonnet",
    987:"Flutter Mane",988:"Slither Wing",989:"Sandy Shocks",
    990:"Iron Treads",991:"Iron Bundle",992:"Iron Hands",993:"Iron Jugulis",
    994:"Iron Moth",995:"Iron Thorns",996:"Frigibax",997:"Arctibax",
    998:"Baxcalibur",999:"Gimmighoul",1000:"Gholdengo",
}

ITEMS: dict[int, str] = {
    # Balls
    1:"Poké Ball", 2:"Great Ball", 3:"Ultra Ball", 4:"Master Ball",
    # Potions
    101:"Potion", 102:"Super Potion", 103:"Hyper Potion", 104:"Max Potion",
    # Revives
    201:"Revive", 202:"Max Revive",
    # Misc
    301:"Lucky Egg", 401:"Incense",
    # TMs (legacy IDs)
    501:"Fast TM", 502:"Charged TM",
    # Buddy food
    650:"Buddy Beans", 651:"Buddy Snack",
    # Berries
    701:"Razz Berry", 702:"Bluk Berry", 703:"Nanab Berry", 705:"Pinap Berry",
    706:"Golden Razz Berry", 708:"Silver Pinap Berry", 709:"Poffin",
    # Camera
    801:"GO Snapshot",
    # Incubators — 901=infinite, 902=3-use, 903=super, 905=adventure
    901:"Infinite Incubator", 902:"Egg Incubator", 903:"Super Incubator", 905:"Adventure Incubator",
    # Evolution items (real IDs from PGSharp)
    1101:"Sun Stone", 1102:"King's Rock", 1103:"Metal Coat", 1104:"Dragon Scale",
    1105:"Up-Grade", 1106:"Sinnoh Stone", 1107:"Unova Stone", 1150:"Evolution Stone",
    # TMs (new IDs)
    1201:"Fast TM", 1202:"Charged TM", 1203:"Elite Fast TM", 1204:"Elite Charged TM",
    # Candy
    1301:"Rare Candy", 1302:"XL Rare Candy",
    # Passes
    1303:"Remote Raid Pass", 1401:"Raid Pass", 1402:"Premium Raid Pass",
    # Misc collectibles
    1404:"Star Piece", 1410:"PokéCoins", 1411:"Coin Bag",
    1502:"Rocket Radar", 1505:"Shadow Gem", 1506:"Mega Energy",
}

# Human-readable fallback for names sourced directly from the JSON
_ITEM_NAME_MAP: dict[str, str] = {
    "TroyDisk": "Fast TM",
    "MoveRerollFastAttack": "Fast TM",
    "MoveRerollSpecialAttack": "Charged TM",
    "MoveRerollEliteFastAttack": "Elite Fast TM",
    "MoveRerollEliteSpecialAttack": "Elite Charged TM",
    "IncubatorBasicUnlimited": "Infinite Incubator",
    "IncubatorBasic": "Egg Incubator",
    "IncubatorSuper": "Super Incubator",
    "IncubatorSpecial": "Adventure Incubator",
    "LuckyEgg": "Lucky Egg",
    "IncenseOrdinary": "Incense",
    "RazzBerry": "Razz Berry",
    "PinapBerry": "Pinap Berry",
    "GoldenRazzBerry": "Golden Razz Berry",
    "GoldenPinapBerry": "Silver Pinap Berry",
    "SpecialCamera": "GO Snapshot",
    "SunStone": "Sun Stone",
    "KingsRock": "King's Rock",
    "UpGrade": "Up-Grade",
    "Gen5EvolutionStone": "Unova Stone",
    "OtherEvolutionStoneA": "Evolution Stone",
    "XlRareCandy": "XL Rare Candy",
    "RareCandy": "Rare Candy",
    "StarPiece": "Star Piece",
    "Mp": "Mega Energy",
    "LeaderMap": "Rocket Radar",
    "ShadowGem": "Shadow Gem",
    "EnhancedCurrency": "PokéCoins",
    "EnhancedCurrencyHolder": "Coin Bag",
}


def _resolve_item_name(iid: int, json_name: str) -> str:
    """Return human-readable item name. Prefers curated dict, then JSON name mapping."""
    if iid in ITEMS:
        return ITEMS[iid]
    if json_name in _ITEM_NAME_MAP:
        return _ITEM_NAME_MAP[json_name]
    if json_name.startswith("EventPassPoint"):
        return "Event Points"
    if json_name:
        # CamelCase → spaced words
        spaced = re.sub(r"(?<=[a-z])(?=[A-Z0-9])", " ", json_name)
        spaced = re.sub(r"(?<=[0-9])(?=[A-Z])", " ", spaced).strip()
        return spaced
    return f"Item #{iid}"

# ── CPM → level ───────────────────────────────────────────────────────────────

_CPM: list[tuple[float, float]] = [
    (1,.094),(1.5,.135137432),(2,.16639787),(2.5,.192650919),(3,.21573247),
    (3.5,.236572661),(4,.25572005),(4.5,.273530381),(5,.29024988),(5.5,.306057377),
    (6,.3210876),(6.5,.335445036),(7,.34921268),(7.5,.362457751),(8,.37523559),
    (8.5,.387592406),(9,.39956728),(9.5,.411193551),(10,.42250001),(10.5,.432926419),
    (11,.44310755),(11.5,.4530599578),(12,.46279839),(12.5,.472336083),(13,.48168495),
    (13.5,.4908558),(14,.49985844),(14.5,.508701765),(15,.51739395),(15.5,.525942511),
    (16,.53435433),(16.5,.542635767),(17,.55079269),(17.5,.558830576),(18,.56675452),
    (18.5,.574569153),(19,.58227891),(19.5,.589877521),(20,.59740001),(20.5,.604823665),
    (21,.61215729),(21.5,.619399365),(22,.62656713),(22.5,.633644533),(23,.64065295),
    (23.5,.647576426),(24,.65443563),(24.5,.661214806),(25,.667934),(25.5,.674577537),
    (26,.68116492),(26.5,.687680648),(27,.69414365),(27.5,.700538673),(28,.70688421),
    (28.5,.713164996),(29,.71939909),(29.5,.725571552),(30,.7317),(30.5,.734741009),
    (31,.73776948),(31.5,.740785574),(32,.74378943),(32.5,.746781211),(33,.74976104),
    (33.5,.752729087),(34,.75568551),(34.5,.758630378),(35,.76156384),(35.5,.764486065),
    (36,.76739717),(36.5,.770297266),(37,.7731865),(37.5,.776064962),(38,.77893275),
    (38.5,.781790055),(39,.78463697),(39.5,.787473578),(40,.79030001),(40.5,.792803968),
    (41,.79530001),(41.5,.797800015),(42,.80030001),(42.5,.802799985),(43,.80530001),
    (43.5,.807800014),(44,.81030001),(44.5,.812799986),(45,.81530001),(45.5,.817800014),
    (46,.82030001),(46.5,.822799985),(47,.82530001),(47.5,.827800015),(48,.83030001),
    (48.5,.832799985),(49,.83530001),(49.5,.837800015),(50,.84029999),
]


# Sorted CPM values for fast bisect in rank calculations
_CPM_VALUES: list[float] = sorted(c for _, c in _CPM)

def cpm_to_level(cpm: float) -> float:
    if not cpm:
        return 1.0
    return min(_CPM, key=lambda x: abs(x[1] - cpm))[0]


# ── Parser ────────────────────────────────────────────────────────────────────

_FORM_SUFFIXES = (
    "Galarian", "Hisuian", "Alolan", "Paldean",
    "Female", "Male", "Normal",
)


def _pokemon_name(pid: int, form_name: str) -> str:
    base = DEX.get(pid, f"#{pid}")
    if not form_name or form_name == "Unset":
        return base
    for sfx in _FORM_SUFFIXES:
        if form_name.endswith(sfx):
            return base if sfx == "Normal" else f"{base} ({sfx[0]})"
    return base


def parse_pgo_json(raw: dict) -> dict:
    """
    Walk the entire JSON tree and pull out:
      - arrays whose first element has 'individualAttack'  → pokemons
      - items from top-level 'items' key OR nested arrays  → items
    Works regardless of nesting depth.
    """
    pokemon_rows: list[dict] = []
    item_map: dict[int, int] = {}
    item_json_names: dict[int, str] = {}  # id → itemName from JSON

    # ── Items: try top-level 'items' key first (PGSharp format)
    raw_items = raw.get("items", [])
    if isinstance(raw_items, list):
        for it in raw_items:
            if not isinstance(it, dict):
                continue
            # PGSharp uses 'item' field; fallback to 'itemId'
            iid = it.get("item") or it.get("itemId")
            cnt = it.get("count", 0)
            jname = it.get("itemName", "") or ""
            if iid is not None and cnt:
                item_map[iid] = item_map.get(iid, 0) + cnt
                if jname and iid not in item_json_names:
                    item_json_names[iid] = jname

    def _walk(node):
        if isinstance(node, list):
            if node and isinstance(node[0], dict):
                if "individualAttack" in node[0] and "pokemonId" in node[0]:
                    pokemon_rows.extend(node)
                    return
                # Nested items arrays (older PGSharp versions)
                if not item_map and "itemId" in node[0] and "count" in node[0]:
                    for it in node:
                        iid = it.get("itemId")
                        if iid is not None:
                            item_map[iid] = item_map.get(iid, 0) + it.get("count", 0)
                    return
            for item in node:
                _walk(item)
        elif isinstance(node, dict):
            for v in node.values():
                _walk(v)

    _walk(raw)

    pokemons: list[dict] = []
    for p in pokemon_rows:
        if not p.get("pokemonId") or p.get("isEgg"):
            continue
        pid  = p["pokemonId"]
        pd   = p.get("pokemonDisplay") or {}
        iv_a = p.get("individualAttack", 0)
        iv_d = p.get("individualDefense", 0)
        iv_s = p.get("individualStamina", 0)
        iv   = round((iv_a + iv_d + iv_s) / 45 * 100, 1)
        cpm  = (p.get("cpMultiplier") or 0.0) + (p.get("additionalCpMultiplier") or 0.0)
        year = 0
        if p.get("creationTimeMs"):
            year = datetime.fromtimestamp(p["creationTimeMs"] / 1000).year

        pokemons.append({
            "pid":    pid,
            "name":   _pokemon_name(pid, pd.get("formName", "")),
            "cp":     p.get("cp", 0),
            "lvl":    cpm_to_level(cpm),
            "iv_a":   iv_a,
            "iv_d":   iv_d,
            "iv_s":   iv_s,
            "iv_pct": iv,
            "shiny":  bool(pd.get("shiny")),
            "shadow": pd.get("alignment", 0) == 1,
            "fav":    bool(p.get("favorite")),
            "lucky":  bool(p.get("isLucky")),
            "hundo":  iv == 100.0,
            "year":   year,
            "nick":   p.get("nickname") or "",
            "move1":  p.get("move1"),
            "move2":  p.get("move2"),
            "move3":  p.get("move3"),
        })

    pokemons.sort(key=lambda x: -x["cp"])

    items = [
        {"id": iid, "name": _resolve_item_name(iid, item_json_names.get(iid, "")), "count": cnt}
        for iid, cnt in sorted(item_map.items(), key=lambda kv: -kv[1])
    ]

    return {"pokemons": pokemons, "items": items}


# ── Tier list (Pokebase) ──────────────────────────────────────────────────────

# Fallback snapshot — merged with live scrape results
_FALLBACK_TIERS: dict[str, dict[str, str]] = {
    "Mewtwo":        {"raid":"S", "pvp_master":"S"},
    "Shadow Mewtwo": {"raid":"S"},
    "Rayquaza":      {"raid":"S", "pvp_master":"A"},
    "Kyogre":        {"raid":"S", "pvp_master":"A"},
    "Groudon":       {"raid":"S", "pvp_master":"A"},
    "Darkrai":       {"raid":"S"},
    "Giratina":      {"raid":"A", "pvp_master":"S", "pvp_ultra":"S"},
    "Dialga":        {"raid":"A", "pvp_master":"S"},
    "Palkia":        {"raid":"A", "pvp_master":"A"},
    "Garchomp":      {"raid":"A", "pvp_master":"S"},
    "Lucario":       {"raid":"A", "pvp_great":"A"},
    "Tyranitar":     {"raid":"A", "pvp_master":"A"},
    "Excadrill":     {"raid":"A", "pvp_great":"A"},
    "Machamp":       {"raid":"A"},
    "Swampert":      {"raid":"A", "pvp_great":"S", "pvp_ultra":"A"},
    "Mamoswine":     {"raid":"A"},
    "Rhyperior":     {"raid":"A"},
    "Dragonite":     {"raid":"A", "pvp_master":"A"},
    "Salamence":     {"raid":"A", "pvp_master":"A"},
    "Metagross":     {"raid":"A", "pvp_master":"A"},
    "Gengar":        {"raid":"A"},
    "Chandelure":    {"raid":"A"},
    "Roserade":      {"raid":"A"},
    "Togekiss":      {"pvp_great":"A", "pvp_ultra":"A", "pvp_master":"A"},
    "Altaria":       {"pvp_great":"S"},
    "Walrein":       {"pvp_great":"S", "pvp_ultra":"A"},
    "Bastiodon":     {"pvp_great":"S"},
    "Registeel":     {"pvp_great":"S", "pvp_ultra":"S"},
    "Cresselia":     {"pvp_ultra":"S", "pvp_great":"A"},
    "Gallade":       {"pvp_great":"A", "pvp_ultra":"A"},
    "Whimsicott":    {"pvp_great":"A"},
    "Galvantula":    {"pvp_great":"S"},
    "Toxapex":       {"pvp_great":"S"},
    "Azumarill":     {"pvp_great":"S"},
    "Medicham":      {"pvp_great":"S"},
    "Lanturn":       {"pvp_great":"A"},
    "Umbreon":       {"pvp_great":"S", "pvp_ultra":"A"},
    "Mew":           {"pvp_great":"A"},
    "Nihilego":      {"raid":"A", "pvp_ultra":"S"},
    "Xurkitree":     {"raid":"A"},
    "Buzzwole":      {"pvp_ultra":"A"},
    "Zacian":        {"pvp_master":"S"},
    "Ho-Oh":         {"pvp_master":"A"},
    "Lugia":         {"pvp_master":"A"},
    "Hydreigon":     {"raid":"A", "pvp_ultra":"A"},
    "Greninja":      {"pvp_great":"A", "pvp_ultra":"A"},
    "Corviknight":   {"pvp_ultra":"A"},
    "Goodra":        {"pvp_ultra":"S"},
    "Toxapex":       {"pvp_great":"S"},
    "Galarian Corsola": {"pvp_great":"S"},
}


def _tier_refresh_needed() -> bool:
    with get_db() as db:
        row = db.execute("SELECT last_ok FROM scrape_log WHERE source='pokebase'").fetchone()
    if not row or not row["last_ok"]:
        return True
    try:
        last = _parse_dt(row["last_ok"])
        if not last:
            return True
        return _now() - last > timedelta(hours=TIER_REFRESH_HOURS)
    except ValueError:
        return True


def scrape_pokebase() -> dict[str, dict[str, str]]:
    """
    Attempts to scrape tier data from pokebase.app.
    Strategy:
      1. Look for JSON embedded in <script id="__NEXT_DATA__"> (Next.js)
      2. Parse visible tier HTML divs / table rows
      3. Fall back gracefully — always returns at least FALLBACK_TIERS
    """
    tiers: dict[str, dict[str, str]] = {}

    try:
        resp = requests.get(POKEBASE_URL, headers=SCRAPE_HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Strategy 1 — Next.js __NEXT_DATA__
        next_tag = soup.find("script", id="__NEXT_DATA__")
        if next_tag and next_tag.string:
            try:
                page_data = json.loads(next_tag.string)
                props = (page_data.get("props") or {}).get("pageProps") or {}
                # Common field names across tier-list sites
                for key in ("tierList", "tiers", "data", "pokemonList"):
                    tier_data = props.get(key)
                    if isinstance(tier_data, list):
                        for entry in tier_data:
                            name = entry.get("name") or entry.get("pokemon")
                            tier = entry.get("tier") or entry.get("rank")
                            cat  = entry.get("category", "raid")
                            if name and tier:
                                tiers.setdefault(name, {})[cat] = tier.upper()
                        break
            except (json.JSONDecodeError, AttributeError):
                pass

        # Strategy 2 — HTML tier containers
        if not tiers:
            for tier_label in ("S", "A", "B", "C", "D"):
                selectors = [
                    f'[data-tier="{tier_label}"]',
                    f'.tier-{tier_label}',
                    f'[class*="tier-{tier_label.lower()}"]',
                ]
                for sel in selectors:
                    for div in soup.select(sel):
                        for el in div.select("span, p, .name, [class*='name']"):
                            name = el.get_text(strip=True)
                            if 2 < len(name) < 40:
                                tiers.setdefault(name, {})["raid"] = tier_label

        log.info("Pokebase scrape: %d Pokémon with tier data", len(tiers))

    except Exception as exc:
        log.warning("Pokebase scrape failed (%s) — using fallback data", exc)
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO scrape_log (source, last_err) VALUES ('pokebase', ?)",
                (str(exc),),
            )

    # Merge: fallback first, live data wins on conflict
    merged = {k: dict(v) for k, v in _FALLBACK_TIERS.items()}
    for name, cats in tiers.items():
        merged.setdefault(name, {}).update(cats)

    now = _now_iso()
    with get_db() as db:
        for name, cats in merged.items():
            for cat, tier in cats.items():
                db.execute(
                    "INSERT OR REPLACE INTO tier_list (pokemon_name, tier, category, scraped_at) "
                    "VALUES (?, ?, ?, ?)",
                    (name, tier, cat, now),
                )
        db.execute(
            "INSERT OR REPLACE INTO scrape_log (source, last_ok) VALUES ('pokebase', ?)",
            (now,),
        )

    log.info("Tier list saved: %d entries total", sum(len(c) for c in merged.values()))
    return merged


def get_tier_list() -> dict[str, dict[str, str]]:
    if _tier_refresh_needed():
        scrape_pokebase()
    tiers: dict[str, dict[str, str]] = {}
    with get_db() as db:
        rows = db.execute("SELECT pokemon_name, tier, category FROM tier_list").fetchall()
    for row in rows:
        tiers.setdefault(row["pokemon_name"], {})[row["category"]] = row["tier"]
    return tiers


def _tier_for(name: str, tiers: dict) -> dict:
    """Tier lookup with form-name fallback."""
    return tiers.get(name) or tiers.get(name.split(" (")[0]) or {}


_TIER_ORDER = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}


def _best_tier(tier_dict: dict) -> Optional[str]:
    tiers = [t for t in tier_dict.values() if t in _TIER_ORDER]
    return min(tiers, key=lambda t: _TIER_ORDER[t]) if tiers else None


# ── Events (ScrapedDuck) ──────────────────────────────────────────────────────

def _events_refresh_needed() -> bool:
    with get_db() as db:
        row = db.execute("SELECT last_ok FROM scrape_log WHERE source='events'").fetchone()
    if not row or not row["last_ok"]:
        return True
    try:
        last = _parse_dt(row["last_ok"])
        if not last:
            return True
        return _now() - last > timedelta(hours=EVENT_REFRESH_HOURS)
    except ValueError:
        return True


def fetch_events(force: bool = False) -> list[dict]:
    if not force and not _events_refresh_needed():
        return []
    try:
        resp = requests.get(SCRAPEDDUCK_URL, headers=SCRAPE_HEADERS, timeout=15)
        resp.raise_for_status()
        events_raw: list[dict] = resp.json()

        now_str = _now_iso()
        with get_db() as db:
            for ev in events_raw:
                ev_id = ev.get("id") or hashlib.md5(
                    (ev.get("name", "") + ev.get("start", "")).encode()
                ).hexdigest()[:12]
                db.execute(
                    "INSERT OR REPLACE INTO events "
                    "(id, name, start_time, end_time, event_type, raw_json, fetched_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (
                        ev_id,
                        ev.get("name", ""),
                        ev.get("start", ""),
                        ev.get("end", ""),
                        ev.get("type", ""),
                        json.dumps(ev),
                        now_str,
                    ),
                )
            db.execute(
                "INSERT OR REPLACE INTO scrape_log (source, last_ok) VALUES ('events', ?)",
                (now_str,),
            )
        log.info("Events fetched: %d", len(events_raw))
        return events_raw
    except Exception as exc:
        log.error("Events fetch failed: %s", exc)
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO scrape_log (source, last_err) VALUES ('events', ?)",
                (str(exc),),
            )
        return []


def _parse_dt(s: str) -> Optional[datetime]:
    """Parse ISO datetime string, always returns timezone-aware (UTC) datetime."""
    try:
        s = s.strip()
        # Replace Z suffix
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        # If naive, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None


def get_events() -> list[dict]:
    fetch_events()
    with get_db() as db:
        rows = db.execute(
            "SELECT id, name, start_time, end_time, event_type, raw_json "
            "FROM events ORDER BY start_time ASC LIMIT 80"
        ).fetchall()

    now = _now()
    upcoming, active, ended = [], [], []

    for row in rows:
        try:
            raw = json.loads(row["raw_json"]) if row["raw_json"] else {}
        except (json.JSONDecodeError, TypeError):
            raw = {}

        start_dt = _parse_dt(row["start_time"])
        end_dt   = _parse_dt(row["end_time"])

        if start_dt and end_dt:
            if now < start_dt:
                status     = "upcoming"
                days_until = max(0, (start_dt - now).days)
            elif now > end_dt:
                status     = "ended"
                days_until = None
            else:
                status     = "active"
                days_until = 0
        else:
            status     = "unknown"
            days_until = None

        entry = {
            "id":         row["id"],
            "name":       row["name"],
            "start":      row["start_time"],
            "end":        row["end_time"],
            "type":       row["event_type"],
            "status":     status,
            "days_until": days_until,
            "bonuses":    raw.get("bonuses", []),
            "spawns":     raw.get("spawns", [])[:20],
            "shinies":    raw.get("shinies", [])[:20],
            "link":       raw.get("link", ""),
            "heading":    raw.get("heading", ""),
            "extraData":  raw.get("extraData", {}),
        }
        if status == "upcoming":
            upcoming.append(entry)
        elif status == "active":
            active.append(entry)
        else:
            ended.append(entry)

    # upcoming: soonest first; active: most recently started first; ended: most recent first
    upcoming.sort(key=lambda e: e["start"] or "")
    active.sort(key=lambda e: e["start"] or "", reverse=True)
    ended.sort(key=lambda e: e["end"] or "", reverse=True)

    return upcoming + active + ended


# ── AI caching helpers ────────────────────────────────────────────────────────

def _make_hash(*parts) -> str:
    payload = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()[:20]


def _get_cache(h: str) -> Optional[str]:
    with get_db() as db:
        row = db.execute("SELECT response FROM ai_cache WHERE hash=?", (h,)).fetchone()
    return row["response"] if row else None


def _set_cache(h: str, label: str, response: str) -> None:
    with get_db() as db:
        db.execute(
            "INSERT OR REPLACE INTO ai_cache (hash, label, response, model) VALUES (?,?,?,?)",
            (h, label[:120], response, AI_PROVIDER),
        )


# ── AI service ────────────────────────────────────────────────────────────────

_gemini_model_cache: list = [0.0, []]  # [timestamp, [model_ids]]


def _gemini_models() -> list[str]:
    """Fetch available Gemini flash models from the API, cached for 1 h."""
    if _gemini_model_cache[1] and time.time() - _gemini_model_cache[0] < 3600:
        return _gemini_model_cache[1]
    try:
        r = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": GEMINI_API_KEY}, timeout=10,
        )
        r.raise_for_status()
        available = []
        for m in r.json().get("models", []):
            name = m.get("name", "")
            if name.startswith("models/"):
                name = name[7:]
            methods = m.get("supportedGenerationMethods", [])
            if "generateContent" in methods and "flash" in name and "gemini" in name:
                available.append(name)
        available.sort(key=lambda n: (
            0 if "2.5" in n else 1 if "2.0" in n else 2 if "1.5" in n else 3, n
        ))
        if available:
            _gemini_model_cache[0] = time.time()
            _gemini_model_cache[1] = available
            log.info("Gemini models available: %s", available)
            return available
    except Exception as exc:
        log.warning("Gemini model list failed: %s — using fallback", exc)
    fallback = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
    _gemini_model_cache[0] = time.time()
    _gemini_model_cache[1] = fallback
    return fallback


def call_ai(prompt: str, system: str = "") -> str:
    """Dispatch to the configured AI provider."""
    provider = AI_PROVIDER.lower()
    if provider == "gemini":
        return _gemini(prompt, system)
    if provider == "anthropic":
        return _anthropic(prompt, system)
    if provider == "azure":
        return _azure(prompt, system)
    return _openai(prompt, system)


def _gemini(prompt: str, system: str) -> str:
    if not GEMINI_API_KEY:
        raise ValueError("Ustaw GEMINI_API_KEY w pliku .env")

    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"maxOutputTokens": 2000, "temperature": 0.7},
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    }

    errors: list[str] = []
    for model in _gemini_models():
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={GEMINI_API_KEY}"
        )
        for attempt in range(2):
            try:
                r = requests.post(url, json=payload, timeout=40)
                if r.status_code == 404:
                    errors.append(f"404 {model}")
                    _gemini_model_cache[0] = 0.0  # wymuś odświeżenie listy
                    _gemini_model_cache[1] = []
                    break
                if r.status_code == 429:
                    if attempt == 0:
                        log.warning("Gemini 429 on %s — retry za 5s…", model)
                        time.sleep(5)
                        continue
                    errors.append(f"429 {model}")
                    break
                r.raise_for_status()
                data = r.json()
                log.info("Gemini OK: %s", model)
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            except requests.exceptions.HTTPError as e:
                code = e.response.status_code if e.response is not None else 0
                if code == 429 and attempt == 0:
                    time.sleep(5)
                    continue
                errors.append(f"{code} {model}")
                break
            except (KeyError, IndexError):
                raise ValueError(f"Nieoczekiwana odpowiedź Gemini: {r.text[:300]}")

    raise ValueError(
        f"Gemini niedostępny: {'; '.join(errors)}. "
        "Sprawdź klucz API. Darmowy tier: 15 req/min — poczekaj chwilę. "
        "Wcześniej wygenerowane odpowiedzi są w cache."
    )


def _openai(prompt: str, system: str) -> str:
    if not OPENAI_API_KEY:
        raise ValueError("Ustaw OPENAI_API_KEY w pliku .env")
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system or "Jesteś ekspertem Pokemon GO."},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens": 2000,
        "temperature": 0.7,
    }
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _azure(prompt: str, system: str) -> str:
    if not AZURE_API_KEY or not AZURE_ENDPOINT:
        raise ValueError("Ustaw AZURE_OPENAI_KEY + AZURE_OPENAI_ENDPOINT w pliku .env")
    url = (
        f"{AZURE_ENDPOINT.rstrip('/')}/openai/deployments/"
        f"{AZURE_DEPLOYMENT}/chat/completions?api-version={AZURE_API_VERSION}"
    )
    payload = {
        "messages": [
            {"role": "system", "content": system or "Jesteś ekspertem Pokemon GO."},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens": 2000,
        "temperature": 0.7,
    }
    r = requests.post(
        url,
        headers={"api-key": AZURE_API_KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _anthropic(prompt: str, system: str) -> str:
    if not ANTHROPIC_API_KEY:
        raise ValueError("Ustaw ANTHROPIC_API_KEY w pliku .env")
    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 2000,
        "system": system or "Jesteś ekspertem Pokemon GO. Odpowiadaj po polsku.",
        "messages": [{"role": "user", "content": prompt}],
    }
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["content"][0]["text"].strip()


# ── Prompts ───────────────────────────────────────────────────────────────────

_SYSTEM_EXPERT = (
    "Jesteś starszym ekspertem Pokemon GO z pełną wiedzą o meta raidowym, PvP (GL/UL/ML), "
    "systemach ewolucji, rarity i ekonomii gry. Odpowiadaj po polsku. "
    "Używaj konkretnych liczb i nazw. Bądź zwięzły: max 6 zdań na sekcję."
)

_SYSTEM_TACTICIAN = (
    "Jesteś taktycznym doradcą Pokemon GO. Tworzysz spersonalizowane, praktyczne "
    "strategie eventowe. Odpowiadaj po polsku. Używaj bullet-pointów i konkretnych "
    "liczb/nazw. Bądź bezpośredni — co dokładnie robić i kiedy."
)


def _build_pokemon_prompt(p: dict, tier_data: dict, top_items: list[str]) -> str:
    return f"""Przeanalizuj tego Pokemona z mojego konta:

**{p['name']}** (Pokédex #{p['pid']})
- CP: {p['cp']} | Level: {p['lvl']} | IV: {p['iv_a']}/{p['iv_d']}/{p['iv_s']} = {p['iv_pct']}%
- Shiny: {'✅' if p['shiny'] else '❌'} | Shadow: {'✅' if p['shadow'] else '❌'} | Lucky: {'✅' if p.get('lucky') else '❌'}
- Złapany: {p.get('year', '?')}
- Tier lista: {json.dumps(tier_data) if tier_data else 'brak danych w bazie'}

Mój ekwipunek (top): {', '.join(top_items) or 'brak danych'}

Odpowiedź w sekcjach:

**💎 Wartość** — czy to cenny okaz (meta / rare / hundo / lucky / shiny)?
**⚔️ Bojowy potencjał** — ocena pod raidy, PvP GL, UL i ML
**📋 Rekomendacja** — konkretnie: power up / evolve / transfer / purify / zachować?
**🎒 Przedmioty** — jakie z moich przedmiotów tu zastosować i dlaczego?"""


def _build_items_prompt(items: list[dict], top_pokes: list[dict]) -> str:
    items_str = "\n".join(f"  - {it['name']}: {it['count']}×" for it in items)
    pokes_str = "\n".join(
        f"  - {p['name']} CP{p['cp']} IV{p['iv_pct']}% {'Shadow' if p['shadow'] else ''}"
        for p in top_pokes
    )
    return f"""Przeanalizuj mój ekwipunek i dopasuj go do pokemonów.

**Ekwipunek:**
{items_str or '  (brak)'}

**Moje najlepsze Pokemony (IV≥80%):**
{pokes_str or '  (brak)'}

**1. Elite TM** — na kogo dokładnie użyć Elite Fast i Elite Charged TM?
**2. Sinnoh Stone / Unova Stone** — konkretne rekomendacje z listy wyżej
**3. Co wyrzucić** — jakie przedmioty zbierają kurz (wymień nazwy + liczby)?
**4. Strategia zbierania** — czego za mało, a czego za dużo?"""


def _build_event_prompt(event: dict, relevant_pokes: list[dict], items: list[dict]) -> str:
    bonuses = "\n".join(f"  - {b}" for b in event.get("bonuses", [])) or "  brak danych"
    spawns  = ", ".join(
        (s.get("name") or s) if isinstance(s, dict) else str(s)
        for s in event.get("spawns", [])[:15]
    ) or "brak danych"
    pokes_str = "\n".join(
        f"  - {p['name']} CP{p['cp']} IV{p['iv_pct']}% L{p['lvl']} {'Shadow' if p['shadow'] else ''}"
        for p in relevant_pokes
    ) or "  Brak pasujących pokemonów"
    items_str = "\n".join(f"  - {it['name']}: {it['count']}×" for it in items[:18])

    return f"""Stwórz strategię na event Pokemon GO dla mojego konta.

**Event:** {event['name']}
**Status:** {event['status']} | Start: {event['start']} | Koniec: {event['end']}
{f"**Za:** {event['days_until']} dni" if event.get('days_until') is not None else ""}
**Typ:** {event['type']}

**Bonusy eventu:**
{bonuses}

**Pojawiające się Pokemony:** {spawns}

**Moje Pokemony pasujące do eventu:**
{pokes_str}

**Mój ekwipunek:**
{items_str or '  brak danych'}

Strategia:

**1. TL;DR** — co najważniejszego daje ten event (1-2 zdania)?
**2. TOP 3 priorytety** — co robić w pierwszej kolejności?
**3. Moje Pokemony** — co zatrzymać/ewoluować/power-up'ować pod ten event?
**4. Ekwipunek** — jakie itemy zużyć podczas eventu (kiedy i ile)?
**5. Pułapki** — co NIE warto robić / na co uważać?"""


# ── Base stats & scoring ──────────────────────────────────────────────────────
# [baseAtk, baseDef, baseSta]  — top meta + commonly owned pokemon
_BS: dict[int, tuple[int,int,int]] = {
    6:(223,176,186),9:(171,207,188),25:(112,96,111),62:(182,187,207),
    65:(271,167,162),68:(234,162,193),80:(177,180,216),89:(190,169,233),
    91:(186,256,163),94:(261,149,163),99:(207,175,146),103:(233,149,190),
    105:(144,200,155),112:(222,171,233),113:(60,128,510),125:(198,173,163),
    126:(206,156,163),127:(238,182,130),129:(29,85,85),130:(237,186,216),
    131:(165,174,277),143:(190,169,330),144:(192,249,207),145:(253,185,207),
    146:(251,181,207),147:(119,91,121),148:(163,137,163),149:(263,198,209),
    150:(300,182,214),151:(210,210,225),152:(92,122,128),154:(168,202,190),
    157:(223,176,186),160:(182,187,225),169:(194,178,198),171:(146,137,268),
    176:(139,166,146),181:(211,172,207),184:(112,152,225),186:(174,192,207),
    196:(261,175,163),197:(126,240,216),198:(175,127,121),205:(161,205,155),
    207:(134,110,130),208:(148,272,181),212:(236,181,172),214:(234,179,190),
    215:(189,146,146),217:(236,144,207),220:(90,69,130),221:(181,138,200),
    226:(148,226,163),229:(224,144,181),232:(214,214,207),237:(173,207,137),
    242:(129,169,510),246:(115,93,137),247:(155,133,172),248:(251,207,225),
    249:(193,310,235),250:(263,301,212),251:(187,210,225),254:(223,169,172),
    257:(240,141,190),260:(208,175,225),282:(237,195,169),286:(241,153,172),
    297:(209,114,207),302:(141,136,137),303:(155,141,137),306:(198,314,200),
    308:(211,175,155),315:(150,130,128),321:(175,147,347),330:(205,168,190),
    334:(141,201,181),350:(192,219,216),362:(162,162,190),365:(182,176,277),
    373:(277,168,216),376:(257,228,190),379:(143,285,190),380:(228,246,190),
    381:(268,212,190),382:(270,228,225),383:(270,228,225),384:(284,170,234),
    395:(210,175,197),405:(232,161,197),408:(218,71,128),409:(295,109,172),
    411:(94,285,176),444:(172,125,172),445:(261,193,239),448:(236,144,172),
    450:(201,191,239),460:(178,158,207),461:(243,171,172),462:(238,205,172),
    464:(241,190,230),466:(249,163,181),467:(247,174,181),468:(225,217,198),
    469:(231,140,178),470:(216,219,163),471:(238,205,163),472:(185,222,181),
    473:(247,146,242),474:(264,150,178),475:(237,195,169),476:(135,275,155),
    477:(180,254,163),478:(171,150,172),480:(156,270,163),481:(212,212,163),
    482:(261,193,163),483:(275,211,205),484:(280,215,189),485:(251,213,192),
    486:(287,210,221),487:(187,225,284),488:(152,258,260),491:(285,198,207),
    493:(238,238,237),508:(170,206,198),526:(226,175,180),530:(255,129,199),
    534:(243,158,209),547:(113,179,155),549:(202,170,181),553:(229,162,198),
    555:(200,107,172),558:(188,218,163),563:(136,166,184),596:(201,164,155),
    609:(271,182,155),612:(284,172,187),623:(222,154,205),635:(225,170,209),
    637:(310,140,172),658:(223,169,176),663:(176,155,186),675:(186,152,175),
    697:(227,152,172),700:(203,205,216),706:(220,242,163),709:(152,178,177),
    715:(205,139,198),745:(171,162,163),748:(114,252,163),760:(242,198,242),
    784:(270,187,211),785:(258,167,172),786:(223,228,172),787:(187,253,172),
    788:(162,253,172),793:(254,253,163),794:(321,153,186),795:(309,105,163),
    796:(330,116,163),797:(272,228,219),798:(354,177,148),799:(319,227,297),
    800:(277,153,176),808:(118,116,99),809:(226,190,264),812:(214,155,210),
    815:(241,145,183),818:(231,175,176),820:(241,159,183),834:(202,172,211),
    839:(198,205,219),841:(226,149,185),849:(202,148,174),864:(145,197,155),
    888:(254,239,192),889:(192,285,192),908:(200,173,172),914:(210,175,197),
    916:(131,150,190),923:(167,149,172),945:(193,143,181),
}

# pre-evo pid → final-form pid (meta-relevant chains only)
_EVOLVE_CHAIN: dict[int, int] = {
    # Gen 1
    66:68,   67:68,        # Machop/Machoke → Machamp
    92:94,   93:94,        # Gastly/Haunter → Gengar
    108:463,               # Lickitung → Lickilicky
    111:464, 112:464,      # Rhyhorn/Rhydon → Rhyperior
    114:465,               # Tangela → Tangrowth
    125:466,               # Electabuzz → Electivire
    126:467,               # Magmar → Magmortar
    133:197,               # Eevee → Umbreon (GL S-tier)
    147:149, 148:149,      # Dratini/Dragonair → Dragonite
    # Gen 2
    175:468, 176:468,      # Togepi/Togetic → Togekiss
    183:184, 298:184,      # Marill/Azurill → Azumarill
    193:469,               # Yanma → Yanmega
    207:472,               # Gligar → Gliscor
    220:473, 221:473,      # Swinub/Piloswine → Mamoswine
    233:474,               # Porygon2 → Porygon-Z
    246:248, 247:248,      # Larvitar/Pupitar → Tyranitar
    # Gen 3
    258:260, 259:260,      # Mudkip/Marshtomp → Swampert
    280:282, 281:282,      # Ralts/Kirlia → Gardevoir
    285:286,               # Shroomish → Breloom
    296:297,               # Makuhita → Hariyama
    307:308,               # Meditite → Medicham
    315:407, 406:407,      # Roselia/Budew → Roserade
    328:330, 329:330,      # Trapinch/Vibrava → Flygon
    333:334,               # Swablu → Altaria
    361:478,               # Snorunt → Froslass
    363:365, 364:365,      # Spheal/Sealeo → Walrein
    371:373, 372:373,      # Bagon/Shelgon → Salamence
    374:376, 375:376,      # Beldum/Metang → Metagross
    410:411,               # Shieldon → Bastiodon
    # Gen 4
    443:445, 444:445,      # Gible/Gabite → Garchomp
    447:448,               # Riolu → Lucario
    595:596,               # Joltik → Galvantula
    607:609, 608:609,      # Litwick/Lampent → Chandelure
    610:612, 611:612,      # Axew/Fraxure → Haxorus
    # Gen 5
    529:530,               # Drilbur → Excadrill
    532:534, 533:534,      # Timburr/Gurdurr → Conkeldurr
    # Gen 6
    656:658, 657:658,      # Froakie/Frogadier → Greninja
    # Gen 7
    747:748,               # Mareanie → Toxapex
    # Gen 8+
    633:635, 634:635,      # Deino/Zweilous → Hydreigon
    636:637,               # Larvesta → Volcarona
    704:706, 705:706,      # Goomy/Sliggoo → Goodra
}

_CPM_TABLE: list[tuple[float,float]] = [
    (1,.094),(5,.29024988),(10,.42250001),(15,.51739395),(20,.59740001),
    (25,.667934),(30,.7317),(35,.76156384),(40,.79030001),(50,.84029999),
]

def _cpm(lvl: float) -> float:
    for i, (l, c) in enumerate(_CPM_TABLE):
        if lvl <= l:
            if i == 0: return c
            l0,c0 = _CPM_TABLE[i-1]
            return c0 + (c-c0)*(lvl-l0)/(l-l0)
    return _CPM_TABLE[-1][1]

def _max_cp(pid: int, iv_a: int, iv_d: int, iv_s: int) -> int:
    bs = _BS.get(pid)
    if not bs: return 0
    a,d,s = bs
    c = _cpm(50)
    return max(10, int((a+iv_a)*((d+iv_d)**0.5)*((s+iv_s)**0.5)*c*c/10))

def _raid_score(pid: int, iv_a: int, iv_d: int, iv_s: int, tiers: dict, name: str) -> float:
    """Higher = better raid attacker. Formula mirrors actual PoGO DPS*TDO weighting."""
    bs = _BS.get(pid)
    if not bs: return 0.0
    a,d,s = bs
    eff_a = (a + iv_a) * _cpm(40)
    eff_d = (d + iv_d) * _cpm(40)
    eff_s = (s + iv_s) * _cpm(40)
    # Raid DPS proxy: attack^1.5, TDO proxy: hp * def
    dps   = eff_a ** 1.5
    tdo   = eff_s * eff_d
    score = dps * (tdo ** 0.5)
    # Tier bonus
    tier_data = _tier_for(name, tiers)
    tier = _best_tier(tier_data)
    bonus = {"S":2.0,"A":1.5,"B":1.2}.get(tier, 1.0)
    return score * bonus

def _pvp_cp(pid: int, iv_a: int, iv_d: int, iv_s: int, cp_limit: int) -> tuple[float,int]:
    """Returns (level_used, best_cp) at or under cp_limit."""
    bs = _BS.get(pid)
    if not bs: return (0.0, 0)
    a,d,s = bs
    best_lvl, best_cp = 0.0, 0
    lvl = 1.0
    while lvl <= 51:
        c = _cpm(lvl)
        cp = max(10, int((a+iv_a)*((d+iv_d)**0.5)*((s+iv_s)**0.5)*c*c/10))
        if cp <= cp_limit:
            best_lvl, best_cp = lvl, cp
        elif cp > cp_limit:
            break
        lvl += 0.5
    return (best_lvl, best_cp)

# ── PvP IV Rank ───────────────────────────────────────────────────────────────
# Rank 1 = best possible IV combo for that pokemon in that league.
# Lower ATK IVs are often better because they allow a higher level under the CP cap,
# resulting in more HP/bulk — the opposite of raid logic.

# (pid, cp_limit) → list of 4096 stat products sorted ASC
_rank_cache: dict[tuple, list] = {}


def _stat_product(ea: float, ed: float, es: float, c: float) -> float:
    """PvPoke stat product: EffAtk × EffDef × EffHP where EffHP uses game floor."""
    return ea * c * ed * c * math.floor(es * c)


def _best_cpm_idx(ea: float, ed: float, es: float, cp_limit: int) -> int:
    """Return index into _CPM_VALUES for the highest level where CP ≤ cp_limit."""
    cp_base = ea * math.sqrt(ed) * math.sqrt(es) / 10.0
    if cp_base <= 0:
        return -1
    max_cpm = math.sqrt((cp_limit + 1) / cp_base)
    idx = bisect.bisect_right(_CPM_VALUES, max_cpm) - 1
    # Guard: float rounding can push computed CP 1 over limit
    if idx >= 0 and max(10, math.floor(cp_base * _CPM_VALUES[idx] ** 2)) > cp_limit:
        idx -= 1
    return idx


def _build_rank_table(pid: int, cp_limit: int) -> list:
    """Compute all 4096 stat products for a species at a given CP cap. Cached."""
    key = (pid, cp_limit)
    if key in _rank_cache:
        return _rank_cache[key]
    bs = _BS.get(pid)
    if not bs:
        _rank_cache[key] = []
        return []
    ba, bd, bst = bs
    products: list[float] = []
    for id_ in range(16):
        ed = bd + id_
        for is_ in range(16):
            es = bst + is_
            for ia in range(16):
                ea = ba + ia
                idx = _best_cpm_idx(ea, ed, es, cp_limit)
                if idx < 0:
                    products.append(0.0)
                    continue
                products.append(_stat_product(ea, ed, es, _CPM_VALUES[idx]))
    products.sort()  # ascending — rank = len - bisect_right(sp) + 1
    _rank_cache[key] = products
    return products


def _pvp_iv_rank(pid: int, iv_a: int, iv_d: int, iv_s: int, cp_limit: int) -> tuple:
    """Return (rank, total, pct_of_max).
    rank 1 = best stat product. pct_of_max is 0–100 float.
    Returns (0, 0, 0.0) if species unknown.
    """
    table = _build_rank_table(pid, cp_limit)
    if not table:
        return (0, 0, 0.0)
    bs = _BS.get(pid)
    if not bs:
        return (0, 0, 0.0)
    ba, bd, bst = bs
    ea = ba + iv_a
    ed = bd + iv_d
    es = bst + iv_s
    idx = _best_cpm_idx(ea, ed, es, cp_limit)
    if idx < 0:
        return (len(table), len(table), 0.0)
    sp = _stat_product(ea, ed, es, _CPM_VALUES[idx])
    rank = len(table) - bisect.bisect_right(table, sp) + 1
    pct  = round(sp / table[-1] * 100, 2) if table[-1] > 0 else 0.0
    return (rank, len(table), pct)


def _pvp_score(pid: int, iv_a: int, iv_d: int, iv_s: int,
               cp_limit: int, tiers: dict, name: str, league_key: str) -> float:
    lvl, cp = _pvp_cp(pid, iv_a, iv_d, iv_s, cp_limit)
    if cp < max(10, cp_limit // 5):  # won't reach meaningful CP in this league
        return 0.0
    bs = _BS.get(pid)
    if not bs: return 0.0
    a,d,s = bs
    c = _cpm(lvl)
    eff_a = (a + iv_a) * c
    eff_d = (d + iv_d) * c
    eff_s = (s + iv_s) * c
    # PvP score: balance of bulk and attack; low ATK IV preferred
    score = eff_a * (eff_d ** 1.2) * (eff_s ** 1.2)
    tier_data = _tier_for(name, tiers)
    tier = tier_data.get(league_key) or _best_tier(tier_data)
    bonus = {"S":2.2,"A":1.6,"B":1.2}.get(tier, 1.0)
    return score * bonus

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "Brak pliku w żądaniu"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Pusty plik"}), 400
    try:
        raw = json.load(f)
        parsed = parse_pgo_json(raw)
        _state["pokemons"] = parsed["pokemons"]
        _state["items"]    = parsed["items"]
        _state["loaded"]   = True
        n = len(parsed["pokemons"])
        log.info("Uploaded: %d pokemons, %d item types", n, len(parsed["items"]))
        # Persist raw JSON so state survives server restart
        try:
            with get_db() as db:
                db.execute(
                    "INSERT OR REPLACE INTO last_upload (id, raw_json, saved_at) VALUES (1, ?, ?)",
                    (json.dumps(raw), _now_iso()),
                )
        except Exception as db_exc:
            log.warning("Could not persist upload: %s", db_exc)
        return jsonify({
            "ok": True,
            "stats": {
                "total":    n,
                "shinies":  sum(1 for p in parsed["pokemons"] if p["shiny"]),
                "shadows":  sum(1 for p in parsed["pokemons"] if p["shadow"]),
                "hundos":   sum(1 for p in parsed["pokemons"] if p["hundo"]),
                "luckies":  sum(1 for p in parsed["pokemons"] if p["lucky"]),
                "item_types": len(parsed["items"]),
            },
        })
    except Exception as exc:
        log.exception("Upload parse error")
        return jsonify({"error": str(exc)}), 400


@app.route("/api/pokemons")
def api_pokemons():
    tiers = get_tier_list()

    # Build spawn index from active + upcoming events: lowercase_name → [event_name, …]
    event_spawn_index: dict[str, list[str]] = {}
    try:
        for ev in get_events():
            if ev["status"] not in ("active", "upcoming"):
                continue
            label = ev["name"][:22].rstrip()
            for s in ev.get("spawns", []):
                pname = (s if isinstance(s, str) else s.get("name", "")).strip().lower()
                if pname:
                    event_spawn_index.setdefault(pname, []).append(label)
    except Exception:
        pass  # never break the pokemon list because of event fetch failure

    result = []
    for p in _state["pokemons"]:
        tier_data  = _tier_for(p["name"], tiers)
        event_tags = event_spawn_index.get(p["name"].lower(), [])
        gl_rank, _, _gl_pct = _pvp_iv_rank(p["pid"], p["iv_a"], p["iv_d"], p["iv_s"], 1500)
        result.append({**p, "tiers": tier_data, "best_tier": _best_tier(tier_data),
                       "event_tags": event_tags, "gl_rank": gl_rank})
    return jsonify(result)


@app.route("/api/items")
def api_items():
    return jsonify(_state["items"])


@app.route("/api/raid-candidates")
def api_raid_candidates():
    """Top raid attackers from current box, scored by DPS*TDO proxy + tier bonus."""
    tiers = get_tier_list()
    scored = []
    for p in _state["pokemons"]:
        if p.get("isEgg"): continue
        score = _raid_score(p["pid"], p["iv_a"], p["iv_d"], p["iv_s"], tiers, p["name"])
        if score < 1: continue
        max_cp = _max_cp(p["pid"], p["iv_a"], p["iv_d"], p["iv_s"])
        tier_data = _tier_for(p["name"], tiers)
        scored.append({**p, "raid_score": round(score), "max_cp": max_cp,
                       "tiers": tier_data, "best_tier": _best_tier(tier_data)})
    scored.sort(key=lambda x: -x["raid_score"])
    return jsonify(scored[:60])


@app.route("/api/pvp-candidates")
def api_pvp_candidates():
    """Top PvP pokemon per league from current box."""
    league = request.args.get("league", "GL")
    limits   = {"GL": 1500, "UL": 2500, "ML": 100000}
    keys     = {"GL": "pvp_great", "UL": "pvp_ultra", "ML": "pvp_master"}
    cp_limit = limits.get(league, 1500)
    lkey     = keys.get(league, "pvp_great")

    tiers = get_tier_list()
    scored = []
    for p in _state["pokemons"]:
        if p.get("isEgg"): continue
        if league != "ML" and p["cp"] > cp_limit: continue
        score = _pvp_score(p["pid"], p["iv_a"], p["iv_d"], p["iv_s"],
                           cp_limit, tiers, p["name"], lkey)
        if score < 1: continue
        lvl, best_cp         = _pvp_cp(p["pid"], p["iv_a"], p["iv_d"], p["iv_s"], cp_limit)
        rank, total, rank_pct = _pvp_iv_rank(p["pid"], p["iv_a"], p["iv_d"], p["iv_s"], cp_limit)
        tier_data = _tier_for(p["name"], tiers)
        scored.append({**p, "pvp_score": round(score), "pvp_cp": best_cp,
                       "pvp_lvl": lvl, "tiers": tier_data,
                       "best_tier": _best_tier(tier_data),
                       "pvp_rank": rank, "pvp_rank_total": total, "pvp_rank_pct": rank_pct})
    scored.sort(key=lambda x: -x["pvp_score"])
    return jsonify(scored[:60])


@app.route("/api/develop-candidates")
def api_develop_candidates():
    tiers = get_tier_list()
    evolve, power_up, purify, elite_tm = [], [], [], []

    for p in _state["pokemons"]:
        if p.get("isEgg"):
            continue
        own_tiers    = _tier_for(p["name"], tiers)
        own_tier     = _best_tier(own_tiers)

        # ── Ewolucje ──────────────────────────────────────────────
        final_pid  = _EVOLVE_CHAIN.get(p["pid"])
        if final_pid:
            final_name  = DEX.get(final_pid, f"#{final_pid}")
            final_tiers = _tier_for(final_name, tiers)
            final_tier  = _best_tier(final_tiers)
            if final_tier in ("S", "A") and p["iv_pct"] >= 80:
                evolve.append({**p, "final_name": final_name,
                                "final_tier": final_tier, "tiers": final_tiers})

        # ── Power Up ───────────────────────────────────────────────
        if own_tier in ("S", "A") and p["iv_pct"] >= 80 and p["lvl"] < 40:
            power_up.append({**p, "tiers": own_tiers, "best_tier": own_tier})

        # ── Purify ─────────────────────────────────────────────────
        if p["shadow"]:
            pur_iv = round((min(15,p["iv_a"]+2)+min(15,p["iv_d"]+2)+min(15,p["iv_s"]+2))/45*100, 1)
            if pur_iv >= 80:
                purify.append({**p, "purified_iv": pur_iv,
                               "tiers": own_tiers, "best_tier": own_tier})

        # ── Elite TM ───────────────────────────────────────────────
        if own_tier in ("S", "A") and p["lvl"] >= 35:
            elite_tm.append({**p, "tiers": own_tiers, "best_tier": own_tier})

    evolve.sort(key=lambda x: (_TIER_ORDER.get(x["final_tier"],9), -x["iv_pct"]))
    power_up.sort(key=lambda x: (_TIER_ORDER.get(x.get("best_tier",""),9), -x["iv_pct"]))
    purify.sort(key=lambda x: -x["purified_iv"])
    elite_tm.sort(key=lambda x: (_TIER_ORDER.get(x.get("best_tier",""),9), -x["lvl"]))

    return jsonify({
        "evolve":   evolve[:40],
        "power_up": power_up[:40],
        "purify":   purify[:40],
        "elite_tm": elite_tm[:40],
    })


@app.route("/api/analyze-pokemon", methods=["POST"])
def analyze_pokemon():
    body = request.json or {}
    p = body.get("pokemon")
    if not p:
        return jsonify({"error": "Brak danych pokemona"}), 400

    h = _make_hash(p["pid"], p["iv_a"], p["iv_d"], p["iv_s"],
                   p.get("shadow"), p.get("shiny"), "v3")

    cached = _get_cache(h)
    if cached:
        return jsonify({"response": cached, "cached": True})

    tiers     = get_tier_list()
    tier_data = _tier_for(p["name"], tiers)
    top_items = [f"{it['name']} ×{it['count']}" for it in _state["items"][:12]]

    try:
        resp = call_ai(_build_pokemon_prompt(p, tier_data, top_items), _SYSTEM_EXPERT)
        _set_cache(h, p["name"], resp)
        return jsonify({"response": resp, "cached": False})
    except Exception as exc:
        log.error("AI error: %s", exc)
        return jsonify({"error": f"Błąd AI: {exc}"}), 500


@app.route("/api/analyze-items", methods=["POST"])
def analyze_items():
    items = _state["items"]
    if not items:
        return jsonify({"error": "Brak danych ekwipunku"}), 400

    top_pokes = [p for p in _state["pokemons"] if p["iv_pct"] >= 80][:15]
    h = _make_hash(
        [(it["id"], it["count"]) for it in items[:25]],
        [(p["pid"], p["iv_pct"]) for p in top_pokes[:10]],
        "items_v3",
    )

    cached = _get_cache(h)
    if cached:
        return jsonify({"response": cached, "cached": True})

    try:
        resp = call_ai(_build_items_prompt(items, top_pokes), _SYSTEM_EXPERT)
        _set_cache(h, "items_analysis", resp)
        return jsonify({"response": resp, "cached": False})
    except Exception as exc:
        return jsonify({"error": f"Błąd AI: {exc}"}), 500


@app.route("/api/events")
def api_events():
    return jsonify(get_events())


@app.route("/api/events/refresh", methods=["POST"])
def api_refresh_events():
    evs = fetch_events(force=True)
    return jsonify({"ok": True, "count": len(evs)})


@app.route("/api/event-strategy", methods=["POST"])
def api_event_strategy():
    body  = request.json or {}
    event = body.get("event")
    if not event:
        return jsonify({"error": "Brak danych eventu"}), 400

    acct_hash = _make_hash(
        [(p["pid"], p["cp"], p["iv_pct"]) for p in _state["pokemons"][:25]],
        [(it["id"], it["count"]) for it in _state["items"][:15]],
    )
    h = f"evt_{event['id']}_{acct_hash}"

    cached = _get_cache(h)
    if cached:
        return jsonify({"response": cached, "cached": True})

    # Find pokemon relevant to this event's spawns
    spawn_names = {
        (s.get("name") or s).lower()
        for s in event.get("spawns", []) + event.get("shinies", [])
        if s
    }
    relevant = [
        p for p in _state["pokemons"]
        if any(sn in p["name"].lower() for sn in spawn_names if sn)
    ][:12]

    try:
        resp = call_ai(
            _build_event_prompt(event, relevant, _state["items"]),
            _SYSTEM_TACTICIAN,
        )
        _set_cache(h, event["name"], resp)
        return jsonify({"response": resp, "cached": False})
    except Exception as exc:
        return jsonify({"error": f"Błąd AI: {exc}"}), 500


@app.route("/api/tier-list")
def api_tier_list():
    return jsonify(get_tier_list())


@app.route("/api/tier-list/refresh", methods=["POST"])
def api_refresh_tiers():
    data = scrape_pokebase()
    return jsonify({"ok": True, "count": len(data)})


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    global AI_PROVIDER, GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, AZURE_API_KEY, AZURE_ENDPOINT
    if request.method == "POST":
        body = request.json or {}
        if "provider"      in body: AI_PROVIDER       = body["provider"]
        if "gemini_key"    in body: GEMINI_API_KEY    = body["gemini_key"]
        if "openai_key"    in body: OPENAI_API_KEY    = body["openai_key"]
        if "anthropic_key" in body: ANTHROPIC_API_KEY = body["anthropic_key"]
        if "azure_key"     in body: AZURE_API_KEY     = body["azure_key"]
        if "azure_endpoint"in body: AZURE_ENDPOINT    = body["azure_endpoint"]
        return jsonify({"ok": True, "provider": AI_PROVIDER})

    return jsonify({
        "provider":         AI_PROVIDER,
        "has_gemini":       bool(GEMINI_API_KEY),
        "has_openai":       bool(OPENAI_API_KEY),
        "has_anthropic":    bool(ANTHROPIC_API_KEY),
        "has_azure":        bool(AZURE_API_KEY and AZURE_ENDPOINT),
        "azure_deployment": AZURE_DEPLOYMENT,
    })


@app.route("/api/cache/stats")
def api_cache_stats():
    with get_db() as db:
        total  = db.execute("SELECT COUNT(*) FROM ai_cache").fetchone()[0]
        today  = db.execute(
            "SELECT COUNT(*) FROM ai_cache WHERE created_at > datetime('now', '-24 hours')"
        ).fetchone()[0]
        saved  = total * 0.002  # ~$0.002 per call estimate
    return jsonify({"total": total, "today": today, "est_saved_usd": round(saved, 2)})


@app.route("/api/status")
def api_status():
    if not _state["loaded"]:
        return jsonify({"loaded": False})
    pokemons = _state["pokemons"]
    return jsonify({
        "loaded": True,
        "stats": {
            "total":      len(pokemons),
            "shinies":    sum(1 for p in pokemons if p["shiny"]),
            "shadows":    sum(1 for p in pokemons if p["shadow"]),
            "hundos":     sum(1 for p in pokemons if p["hundo"]),
            "luckies":    sum(1 for p in pokemons if p["lucky"]),
            "item_types": len(_state["items"]),
        },
    })


# ── Startup ───────────────────────────────────────────────────────────────────

def _load_last_state():
    """Restore last uploaded JSON from DB so state survives server restarts."""
    try:
        with get_db() as db:
            row = db.execute("SELECT raw_json FROM last_upload WHERE id=1").fetchone()
        if not row:
            return
        raw = json.loads(row["raw_json"])
        parsed = parse_pgo_json(raw)
        _state["pokemons"] = parsed["pokemons"]
        _state["items"]    = parsed["items"]
        _state["loaded"]   = True
        log.info("Restored last upload: %d pokemons", len(parsed["pokemons"]))
    except Exception as exc:
        log.warning("Could not restore last upload: %s", exc)


if __name__ == "__main__":
    init_db()
    _load_last_state()
    # Background tier refresh so first page load is fast
    if _tier_refresh_needed():
        log.info("Starting background tier scrape…")
        threading.Thread(target=scrape_pokebase, daemon=True).start()
    app.run(debug=True, host="127.0.0.1", port=5000)