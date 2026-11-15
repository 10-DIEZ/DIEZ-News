"""
Configurazione del bot notizie calcio (versione 3).

COSA MANDA: conferenze stampa e notizie generali di TUTTE le squadre dei
5 campionati principali (Serie A, Premier League, LaLiga, Bundesliga,
Ligue 1).

COME DECIDE: una notizia passa solo se il suo TITOLO nomina una di queste
squadre (o il suo allenatore). Niente piu' ricerche per "nome del
campionato": erano quelle a far entrare Eccellenza, Serie B, Bundesliga
austriaca, Ligue 2 e simili.

TEMPI: solo notizie pubblicate nelle ultime NEWS_MAX_AGE_HOURS ore, e
niente articoli su partite gia' giocate arrivati a distanza di giorni.

Tutto quello che si puo' voler regolare (limiti, tempi, parole escluse,
fonti, nomi delle squadre) e' in questo file.
"""

import os

# --- Credenziali (lette da variabili d'ambiente / GitHub Secrets, MAI scritte qui) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
# Facoltativo: id del gruppo Telegram (inizia con -100). Di solito NON serve:
# il bot trova il gruppo da solo (vedi "GRUPPO CON ARGOMENTI" qui sotto).
TELEGRAM_GROUP_ID = os.environ.get("TELEGRAM_GROUP_ID", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
FOOTBALL_DATA_API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "")

FOOTBALL_DATA_HOST = "https://api.football-data.org/v4"
TELEGRAM_API_BASE = os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org")

# Bandiera dell'Inghilterra (scritta in codice perche' copiando il simbolo si
# perdeva un pezzo e restava solo la bandiera nera)
_ENGLAND_FLAG = "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F"

# --- I 5 campionati seguiti ---
# lang/country: lingua e paese usati per le ricerche Google News locali
LEAGUES = [
    {"name": "Serie A", "flag": "🇮🇹", "fd_code": "SA", "lang": "it", "country": "IT"},
    {"name": "Premier League", "flag": _ENGLAND_FLAG, "fd_code": "PL", "lang": "en", "country": "GB"},
    {"name": "La Liga", "flag": "🇪🇸", "fd_code": "PD", "lang": "es", "country": "ES"},
    {"name": "Bundesliga", "flag": "🇩🇪", "fd_code": "BL1", "lang": "de", "country": "DE"},
    {"name": "Ligue 1", "flag": "🇫🇷", "fd_code": "FL1", "lang": "fr", "country": "FR"},
]

# =====================================================================
# GRUPPO CON ARGOMENTI (un argomento per campionato)
# =====================================================================
# Come si attiva (tutto da Telegram, niente da cambiare su GitHub):
#   1. crea un gruppo con dentro solo te e il bot
#   2. nelle impostazioni del gruppo attiva gli "Argomenti"
#   3. nomina il bot amministratore (con il permesso di gestire gli argomenti)
# Al giro successivo (entro 5 minuti) il bot trova il gruppo, riconosce che
# l'hai aggiunto tu, crea un argomento per campionato e da li' in poi manda
# ogni notizia nell'argomento del suo campionato. Finche' il gruppo non e'
# pronto, le notizie arrivano nella chat privata col bot, come prima.
# Non creare gli argomenti a mano: li crea il bot (e ne ricorda gli indirizzi).
#
# Nome e colore di ogni argomento. Colori ammessi da Telegram:
# 7322096 azzurro, 16766590 giallo, 13338331 viola, 9367192 verde,
# 16749490 rosa, 16478047 rosso
TOPICS = {
    "Serie A": {"name": "🇮🇹 Serie A", "color": 7322096},
    "Premier League": {"name": _ENGLAND_FLAG + " Premier League", "color": 13338331},
    "La Liga": {"name": "🇪🇸 La Liga", "color": 16478047},
    "Bundesliga": {"name": "🇩🇪 Bundesliga", "color": 16766590},
    "Ligue 1": {"name": "🇫🇷 Ligue 1", "color": 9367192},
}

# Telegram accetta al massimo 20 messaggi al minuto in un gruppo:
# pausa tra un invio e l'altro (secondi), nel gruppo e nella chat privata
SEND_DELAY_GROUP_SECONDS = 3.2
SEND_DELAY_PRIVATE_SECONDS = 1.2

# =====================================================================
# HASHTAG DELLE SQUADRE
# =====================================================================
# In fondo a ogni notizia: l'hashtag delle squadre nominate nel titolo
# (es. #Inter #Juventus). Toccandolo, Telegram mostra tutte le notizie di
# quella squadra. False per toglierli.
TEAM_HASHTAGS = True
MAX_HASHTAGS = 3

# Hashtag di ogni squadra (chiave = nome ufficiale di football-data.org, come
# in TEAMS qui sotto), con il nome che usa la stampa italiana (#Barcellona,
# #Lipsia, #Marsiglia), lo stesso che leggi nei riassunti. Solo lettere senza
# accenti, numeri e _ (niente spazi). Una squadra che non e' qui (es. una
# neopromossa) riceve un hashtag ricavato in automatico dal suo nome.
HASHTAGS = {
    # Serie A
    "Atalanta BC": "Atalanta", "Bologna FC 1909": "Bologna", "Cagliari Calcio": "Cagliari",
    "Como 1907": "Como", "ACF Fiorentina": "Fiorentina", "Frosinone Calcio": "Frosinone",
    "Genoa CFC": "Genoa", "FC Internazionale Milano": "Inter", "Juventus FC": "Juventus",
    "SS Lazio": "Lazio", "US Lecce": "Lecce", "AC Milan": "Milan", "AC Monza": "Monza",
    "SSC Napoli": "Napoli", "Parma Calcio 1913": "Parma", "AS Roma": "Roma",
    "US Sassuolo Calcio": "Sassuolo", "Torino FC": "Torino", "Udinese Calcio": "Udinese",
    "Venezia FC": "Venezia",
    # Premier League
    "Arsenal FC": "Arsenal", "Aston Villa FC": "AstonVilla", "AFC Bournemouth": "Bournemouth",
    "Brentford FC": "Brentford", "Brighton & Hove Albion FC": "Brighton", "Chelsea FC": "Chelsea",
    "Coventry City FC": "Coventry", "Crystal Palace FC": "CrystalPalace", "Everton FC": "Everton",
    "Fulham FC": "Fulham", "Hull City AFC": "HullCity", "Ipswich Town FC": "Ipswich",
    "Leeds United FC": "Leeds", "Liverpool FC": "Liverpool", "Manchester City FC": "ManCity",
    "Manchester United FC": "ManUtd", "Newcastle United FC": "Newcastle",
    "Nottingham Forest FC": "NottinghamForest", "Sunderland AFC": "Sunderland",
    "Tottenham Hotspur FC": "Tottenham",
    # La Liga
    "Deportivo Alavés": "Alaves", "Athletic Club": "AthleticBilbao", "Club Atlético de Madrid": "AtleticoMadrid",
    "FC Barcelona": "Barcellona", "RC Celta de Vigo": "Celta", "RC Deportivo La Coruña": "Deportivo",
    "Elche CF": "Elche", "RCD Espanyol de Barcelona": "Espanyol", "Getafe CF": "Getafe",
    "Levante UD": "Levante", "Málaga CF": "Malaga", "CA Osasuna": "Osasuna",
    "Real Racing Club de Santander": "RacingSantander", "Rayo Vallecano de Madrid": "Rayo",
    "Real Betis Balompié": "Betis", "Real Madrid CF": "RealMadrid", "Real Sociedad de Fútbol": "RealSociedad",
    "Sevilla FC": "Siviglia", "Valencia CF": "Valencia", "Villarreal CF": "Villarreal",
    # Bundesliga
    "FC Augsburg": "Augsburg", "Bayer 04 Leverkusen": "Leverkusen", "FC Bayern München": "Bayern",
    "Borussia Dortmund": "Dortmund", "SV 07 Elversberg": "Elversberg", "Eintracht Frankfurt": "Eintracht",
    "SC Freiburg": "Friburgo", "Hamburger SV": "Amburgo", "TSG 1899 Hoffenheim": "Hoffenheim",
    "1. FC Köln": "Colonia", "RB Leipzig": "Lipsia", "1. FSV Mainz 05": "Mainz",
    "Borussia Mönchengladbach": "Gladbach", "SC Paderborn 07": "Paderborn", "FC Schalke 04": "Schalke",
    "VfB Stuttgart": "Stoccarda", "1. FC Union Berlin": "UnionBerlino", "SV Werder Bremen": "Werder",
    # Ligue 1
    "Angers SCO": "Angers", "AJ Auxerre": "Auxerre", "Stade Brestois 29": "Brest", "Le Havre AC": "LeHavre",
    "Racing Club de Lens": "Lens", "Le Mans FC": "LeMans", "Lille OSC": "Lille", "FC Lorient": "Lorient",
    "Olympique Lyonnais": "Lione", "Olympique de Marseille": "Marsiglia", "AS Monaco FC": "Monaco",
    "OGC Nice": "Nizza", "Paris FC": "ParisFC", "Paris Saint-Germain FC": "PSG",
    "Stade Rennais FC 1901": "Rennes", "RC Strasbourg Alsace": "Strasburgo", "Toulouse FC": "Tolosa",
    "ES Troyes AC": "Troyes",
}

# Competizioni scaricate SOLO per riconoscere le partite gia' giocate
# (es. Bayern-Arsenal di Champions): le notizie su quelle partite arrivate
# giorni dopo vengono scartate. Non aggiungono notizie.
CALENDAR_EXTRA_COMPETITIONS = ["CL"]

# =====================================================================
# TEMPI
# =====================================================================
# Notizie piu' vecchie di cosi' non vengono mai mandate (prima erano 2 giorni:
# era il motivo principale delle notizie "fuori tempo massimo").
NEWS_MAX_AGE_HOURS = 12

# Articoli che nominano le due squadre di una partita GIA' INIZIATA:
# - anteprime scritte prima del calcio d'inizio -> scartate (ormai inutili)
# - articoli del dopo-partita -> mandati solo entro queste ore dal calcio d'inizio
POST_MATCH_HOURS = 8

# Calendario: giorni passati (per il filtro qui sopra) e giorni futuri
CALENDAR_PAST_DAYS = 3
FIXTURE_LOOKAHEAD_DAYS = 6

# Ogni quante ore riscaricare l'elenco squadre (e allenatori) da football-data.org
TEAMS_REFRESH_HOURS = 24

# Stessa notizia da piu' testate: se nelle ultime N ore e' gia' uscita una
# notizia molto simile sulla stessa squadra, le copie vengono scartate.
DUPLICATE_SUPPRESS_HOURS = 12

# Per quanti giorni ricordare i link gia' visti (oltre l'eta' massima non servono)
SEEN_KEEP_DAYS = 3

# Per quante ore tenere l'elenco delle notizie inviate (titolo, squadre, tipo,
# indirizzo del post): serve ai limiti qui sotto e a ritrovare le ultime
# notizie di una squadra.
LOG_KEEP_HOURS = 48

# =====================================================================
# QUANTITA'
# =====================================================================
# Massimo di notizie per singola squadra, per tipo, in una FINESTRA MOBILE
# di ore: (quante, in quante ore). Es. (3, 6) = al massimo 3 nelle ultime 6 ore.
# - official: formazioni UFFICIALI (escono un'ora prima della partita, proprio
#   quando si muovono le quote): hanno un limite a parte, cosi' passano sempre
#   anche se la squadra ha gia' avuto le sue notizie sulle probabili formazioni
# - press: conferenze stampa e dichiarazioni dell'allenatore
# - key: infortuni, squalifiche, assenze, formazioni, cambio allenatore
# - general: tutto il resto (notizie generali sulla squadra)
# "match" = limiti per le squadre che giocano entro MATCH_SOON_HOURS ore: e'
# li' che le quote si muovono e servono piu' informazioni.
# Prima il limite era "al giorno" (2 conferenze, 3 key, 2 generali) e si
# azzerava a mezzanotte: partiva una raffica di notte e la sera, a quota
# esaurita, non passava quasi piu' nulla. Le notizie oltre il limite vengono
# scartate (non rimandate). La priorita' va a ufficiali, conferenze e "key".
TEAM_CAPS = {
    "official": {"normal": (2, 3), "match": (2, 3)},
    "press": {"normal": (2, 12), "match": (3, 12)},
    "key": {"normal": (2, 6), "match": (3, 6)},
    "general": {"normal": (1, 8), "match": (2, 8)},
}
MATCH_SOON_HOURS = 36

# Massimo di messaggi per singolo giro. Nel gruppo Telegram accetta 20
# messaggi al minuto: 45 messaggi sono poco piu' di 2 minuti di invii, cosi'
# il giro dopo (che controlla anche le quote) parte comunque in tempo. Quelle
# che non entrano partono al giro successivo.
MAX_MESSAGES_PER_RUN = 45

# Riassunti Groq (piano gratuito: 1000 richieste e 200.000 token al giorno
# per ognuno dei 3 modelli, cioe' circa 1100 riassunti al giorno in tutto).
# Superate queste chiamate nelle ULTIME 24 ORE, le notizie GENERALI non usano
# piu' Groq: quelle italiane escono con titolo e descrizione del sito, quelle
# estere (che andrebbero tradotte) vengono saltate. Cosi' i riassunti che
# restano vanno a conferenze, infortuni, formazioni e allenatore.
GROQ_GENERAL_DAILY_BUDGET = 600

# Calciomercato (trattative, offerte, voci): escluso. Metti True per riaverlo.
INCLUDE_TRANSFER_NEWS = False

# =====================================================================
# RICERCHE GOOGLE NEWS
# =====================================================================
# Ogni squadra viene cercata al massimo una volta ogni N minuti (se il bot
# gira ogni 5 minuti, le ricerche si distribuiscono sui giri successivi)
TEAM_QUERY_INTERVAL_MINUTES = 15
GOOGLE_MAX_ITEMS = 100
# A volte Google News blocca il computer di GitHub su cui gira il bot (succede
# in circa un giro su venti): se le prime N ricerche del giro falliscono tutte,
# le altre si saltano e si riprova al giro dopo, invece di restare appesi minuti.
GOOGLE_BREAKER_FAILS = 6
GOOGLE_TIMEOUT_SECONDS = 10

# Parole aggiunte alla ricerca di ogni squadra per restare sul calcio
# (senza, "Torino" o "Roma" restituirebbero anche cronaca cittadina)
QUERY_CONTEXT = {
    "it": '(calcio OR "Serie A")',
    "en": '(football OR "Premier League")',
    "es": "(fútbol OR LaLiga)",
    "de": "(Fußball OR Bundesliga)",
    "fr": '(football OR "Ligue 1")',
}

# Ricerca dedicata alle conferenze stampa (ogni giro, per campionato)
PRESS_QUERY_TERMS = {
    "it": ['"conferenza stampa"', '"in conferenza"'],
    "en": ['"press conference"'],
    "es": ['"rueda de prensa"'],
    "de": ["Pressekonferenz"],
    "fr": ['"conférence de presse"'],
}

# --- Feed RSS diretti (letti per intero a ogni giro). Tolti i siti dedicati
# a una sola squadra (Inter, Milan, Juve, Napoli): con le notizie generali
# avrebbero riempito il canale di quelle 4 squadre.
DIRECT_RSS_FEEDS = {
    "https://www.gazzetta.it/rss/home.xml": "it",
    "https://www.ansa.it/sito/notizie/sport/calcio/calcio_rss.xml": "it",
    "https://www.corrieredellosport.it/rss/calcio": "it",
    "http://feeds.bbci.co.uk/sport/football/rss.xml": "en",
    "https://www.theguardian.com/football/rss": "en",
    "https://www.skysports.com/rss/12040": "en",
    "https://www.marca.com/rss/futbol.xml": "es",
    "https://as.com/rss/futbol/portada.xml": "es",
    "https://newsfeed.kicker.de/news/fussball": "de",
    "https://dwh.lequipe.fr/api/edito/rss?path=/Football": "fr",
}

# =====================================================================
# SQUADRE
# =====================================================================
# Chiave = nome ufficiale usato da football-data.org (deve coincidere).
# "alias": i nomi con cui la stampa chiama la squadra, cercati nel TITOLO
#   come parola intera e rispettando le maiuscole.
#   - "Testo"          -> vale per articoli in qualsiasi lingua
#   - ("es", "Testo")  -> vale solo per articoli in quella lingua
#   - "~regex"         -> espressione regolare, per i nomi ambigui
#                         (es. "Inter" ma non "Inter Miami")
# "q": nome usato nella ricerca Google News nella lingua del campionato
#      (se manca, il primo alias)
# "q_it": per le squadre estere, nome usato ANCHE nella ricerca in italiano
#      (solo per le squadre di cui la stampa italiana scrive spesso)
# Una squadra che arriva da football-data.org ma non e' in questo elenco
# (es. una neopromossa la prossima stagione) viene comunque seguita, con
# alias ricavati automaticamente dal nome ufficiale.
TEAMS = {
    "Serie A": {
        "Atalanta BC": {"alias": ["Atalanta"]},
        "Bologna FC 1909": {"alias": ["Bologna", ("es", "Bolonia")]},
        "Cagliari Calcio": {"alias": ["Cagliari"]},
        "Como 1907": {
            "alias": [("it", "Como"), ("en", "Como"), ("de", "Como"), ("fr", "Como"),
                      ("es", r"~\b(?:el|del|al) Como\b"), "Como 1907"],
            "q": "Como",
        },
        "ACF Fiorentina": {"alias": ["Fiorentina"]},
        "Frosinone Calcio": {"alias": ["Frosinone"]},
        "Genoa CFC": {"alias": ["Genoa"]},
        "FC Internazionale Milano": {
            "alias": [r"~\bInter\b(?!\s+(?:Miami|Turku|Allies|Bratislava|Escaldes|de Limeira))",
                      "Internazionale"],
            "q": "Inter",
        },
        "Juventus FC": {"alias": ["Juventus", r"~\bJuve\b(?!\s+Stabia)"]},
        "SS Lazio": {"alias": ["Lazio"]},
        "US Lecce": {"alias": ["Lecce"]},
        "AC Milan": {"alias": ["Milan", "AC Milan"], "q": "Milan"},
        "AC Monza": {"alias": ["Monza"]},
        "SSC Napoli": {"alias": ["Napoli", ("es", "Nápoles"), ("de", "Neapel"), ("fr", "Naples")]},
        "Parma Calcio 1913": {"alias": ["Parma"]},
        "AS Roma": {"alias": ["Roma", "AS Roma"], "q": "Roma"},
        "US Sassuolo Calcio": {"alias": ["Sassuolo"]},
        "Torino FC": {"alias": ["Torino", ("it", "Toro")]},
        "Udinese Calcio": {"alias": ["Udinese"]},
        "Venezia FC": {"alias": ["Venezia"]},
    },
    "Premier League": {
        "Arsenal FC": {"alias": ["Arsenal"], "q_it": "Arsenal"},
        "Aston Villa FC": {"alias": ["Aston Villa", ("en", "Villa")], "q_it": "Aston Villa"},
        "AFC Bournemouth": {"alias": ["Bournemouth"]},
        "Brentford FC": {"alias": ["Brentford"]},
        "Brighton & Hove Albion FC": {"alias": ["Brighton", "Brighton & Hove Albion"], "q": "Brighton"},
        "Chelsea FC": {"alias": ["Chelsea"], "q_it": "Chelsea"},
        "Coventry City FC": {"alias": ["Coventry City", "Coventry"], "q": "Coventry City"},
        "Crystal Palace FC": {"alias": ["Crystal Palace", ("en", "Palace")]},
        "Everton FC": {"alias": ["Everton"]},
        "Fulham FC": {"alias": ["Fulham"]},
        "Hull City AFC": {"alias": ["Hull City", ("en", r"~\bHull\b(?!\s+(?:FC|KR))")], "q": "Hull City"},
        "Ipswich Town FC": {"alias": ["Ipswich Town", "Ipswich"], "q": "Ipswich Town"},
        "Leeds United FC": {"alias": ["Leeds United", "Leeds"], "q": "Leeds United"},
        "Liverpool FC": {"alias": ["Liverpool"], "q_it": "Liverpool"},
        "Manchester City FC": {"alias": ["Manchester City", "Man City"], "q": "Manchester City",
                               "q_it": "Manchester City"},
        "Manchester United FC": {"alias": ["Manchester United", "Man United", "Man Utd", "Manchester Utd"],
                                 "q": "Manchester United", "q_it": "Manchester United"},
        "Newcastle United FC": {"alias": ["Newcastle United", "Newcastle"], "q": "Newcastle United",
                                "q_it": "Newcastle"},
        "Nottingham Forest FC": {"alias": ["Nottingham Forest", "Nottingham", ("en", "Forest")],
                                 "q": "Nottingham Forest"},
        "Sunderland AFC": {"alias": ["Sunderland"]},
        "Tottenham Hotspur FC": {"alias": ["Tottenham", ("en", "Spurs")], "q_it": "Tottenham"},
    },
    "La Liga": {
        "Deportivo Alavés": {"alias": ["Alavés", "Alaves", "Deportivo Alavés"], "q": "Alavés"},
        "Athletic Club": {"alias": ["Athletic Club", "Athletic Bilbao", r"~(?<!The )\bAthletic\b"],
                          "q": "Athletic Club"},
        "Club Atlético de Madrid": {
            "alias": ["Atlético de Madrid", "Atletico de Madrid", "Atlético Madrid", "Atletico Madrid",
                      "Atleti",
                      r"~\bAtl[eé]tico\b(?!\s+(?:Mineiro|Nacional|San Luis|Ottawa|Tucum[aá]n|Baleares|"
                      r"Paranaense|Goianiense|Junior|Huila|Bucaramanga|Morelia|Rafaela|Grau|Balboa|"
                      r"Sanluque[nñ]o|Saguntino|Antoniano|Astorga|Levante|Malague[nñ]o|Ottawa))"],
            "q": "Atlético de Madrid", "q_it": "Atletico Madrid",
        },
        "FC Barcelona": {"alias": [r"~\bBarcelona\b(?!\s+(?:SC|Sporting))", "Barcellona", "Barça", "Barca"],
                         "q": "Barcelona", "q_it": "Barcellona"},
        "RC Celta de Vigo": {"alias": ["Celta de Vigo", "Celta Vigo", r"~\bCelta\b(?!\s+Fortuna)"],
                             "q": "Celta"},
        "RC Deportivo La Coruña": {
            "alias": ["Deportivo La Coruña", "Deportivo de La Coruña", "Deportivo Coruña", "Dépor", "Depor",
                      ("es", r"~\b(?:el|del|al) Deportivo\b(?!\s+Alav)")],
            "q": "Deportivo",
        },
        "Elche CF": {"alias": ["Elche"]},
        "RCD Espanyol de Barcelona": {"alias": ["Espanyol", "Espanyol de Barcelona"], "q": "Espanyol"},
        "Getafe CF": {"alias": ["Getafe"]},
        "Levante UD": {"alias": ["Levante"]},
        "Málaga CF": {"alias": ["Málaga", "Malaga"], "q": "Málaga"},
        "CA Osasuna": {"alias": ["Osasuna"]},
        "Real Racing Club de Santander": {
            "alias": ["Racing de Santander", "Racing Santander",
                      ("es", r"~\b(?:el|del|al) Racing\b(?!\s+(?:de Ferrol|Club|de Avellaneda))")],
            "q": "Racing de Santander",
        },
        "Rayo Vallecano de Madrid": {"alias": ["Rayo Vallecano", r"~\bRayo\b(?!\s+(?:Majadahonda|Cantabria))"],
                                     "q": "Rayo Vallecano"},
        "Real Betis Balompié": {"alias": ["Real Betis", "Betis"], "q": "Betis"},
        "Real Madrid CF": {"alias": ["Real Madrid"], "q_it": "Real Madrid"},
        "Real Sociedad de Fútbol": {"alias": [r"~\bReal Sociedad\b(?!\s+B\b)"], "q": "Real Sociedad"},
        "Sevilla FC": {"alias": [r"~\bSevilla\b(?!\s+Atl[eé]tico)", "Siviglia", ("fr", "Séville")],
                       "q": "Sevilla", "q_it": "Siviglia"},
        "Valencia CF": {"alias": [r"~\bValencia\b(?!\s+(?:Basket|Mestalla))"], "q": "Valencia"},
        "Villarreal CF": {"alias": [r"~\bVillarreal\b(?!\s+B\b)"], "q": "Villarreal"},
    },
    "Bundesliga": {
        "FC Augsburg": {"alias": ["Augsburg"]},
        "Bayer 04 Leverkusen": {"alias": ["Bayer Leverkusen", "Bayer 04", "Leverkusen", r"~\bBayer\b(?!\s+(?:AG|Konzern))"],
                                "q": "Bayer Leverkusen", "q_it": "Leverkusen"},
        "FC Bayern München": {
            "alias": ["Bayern Monaco", "Bayern München", "Bayern Munich", "FC Bayern", r"~\bBayern\b(?!\s+II\b)"],
            "q": "FC Bayern", "q_it": "Bayern Monaco",
        },
        "Borussia Dortmund": {"alias": ["Borussia Dortmund", r"~\bDortmund\b(?!\s+II\b)", r"~\bBVB\b(?!\s+II\b)"],
                              "q": "Borussia Dortmund", "q_it": "Borussia Dortmund"},
        "SV 07 Elversberg": {"alias": ["Elversberg"]},
        "Eintracht Frankfurt": {
            "alias": ["Eintracht Frankfurt", ("it", "Francoforte"), "SGE",
                      r"~\bEintracht\b(?!\s+(?:Braunschweig|Trier|Norderstedt|Spandau|Hohkeppel))"],
            "q": "Eintracht Frankfurt", "q_it": "Eintracht Francoforte",
        },
        "SC Freiburg": {"alias": [r"~\bFreiburg\b(?!\s+II\b)", ("it", "Friburgo")], "q": "SC Freiburg"},
        "Hamburger SV": {"alias": ["Hamburger SV", "HSV", ("it", "Amburgo")], "q": "Hamburger SV"},
        "TSG 1899 Hoffenheim": {"alias": [r"~\bHoffenheim\b(?!\s+II\b)"], "q": "Hoffenheim"},
        "1. FC Köln": {"alias": ["1. FC Köln", "FC Köln", "Köln", ("it", "Colonia"), ("en", "Cologne"),
                                 ("fr", "Cologne")], "q": "1. FC Köln"},
        "RB Leipzig": {"alias": ["RB Leipzig", "Leipzig", ("it", "Lipsia")], "q": "RB Leipzig", "q_it": "Lipsia"},
        "1. FSV Mainz 05": {"alias": [r"~\bMainz(?: 05)?\b(?!\s+(?:05\s+)?II\b)", ("it", "Magonza")], "q": "Mainz 05"},
        "Borussia Mönchengladbach": {"alias": ["Borussia Mönchengladbach", "Mönchengladbach", "Gladbach",
                                               "M'gladbach"], "q": "Borussia Mönchengladbach"},
        "SC Paderborn 07": {"alias": ["Paderborn"]},
        "FC Schalke 04": {"alias": [r"~\bSchalke(?: 04)?\b(?!\s+II\b)", "S04"], "q": "Schalke 04"},
        "VfB Stuttgart": {"alias": [r"~\bStuttgart\b(?!\s+II\b)", ("it", "Stoccarda"),
                                    r"~\bVfB\b(?!\s+(?:Lübeck|Oldenburg|Stuttgart\s+II))"], "q": "VfB Stuttgart"},
        "1. FC Union Berlin": {"alias": ["Union Berlin", ("it", "Union Berlino"), "1. FC Union"], "q": "Union Berlin"},
        "SV Werder Bremen": {"alias": ["Werder Bremen", "Werder", ("it", "Brema")], "q": "Werder Bremen"},
    },
    "Ligue 1": {
        "Angers SCO": {"alias": ["Angers"], "q": "Angers SCO"},
        "AJ Auxerre": {"alias": ["Auxerre", "AJA"], "q": "Auxerre"},
        "Stade Brestois 29": {"alias": ["Brest", "Stade Brestois"], "q": "Stade Brestois"},
        "Le Havre AC": {"alias": ["Le Havre", ("fr", "HAC")], "q": "Le Havre"},
        "Racing Club de Lens": {"alias": ["Lens", "RC Lens"], "q": "RC Lens"},
        "Le Mans FC": {"alias": ["Le Mans"], "q": "Le Mans FC"},
        "Lille OSC": {"alias": ["Lille", "LOSC"], "q": "LOSC", "q_it": "Lille"},
        "FC Lorient": {"alias": ["Lorient"]},
        "Olympique Lyonnais": {"alias": ["Lyon", ("it", "Lione"), "Olympique Lyonnais",
                                         ("fr", r"~\bOL\b(?!\s+Reign)")], "q": "Lyon", "q_it": "Lione"},
        "Olympique de Marseille": {"alias": ["Marseille", ("it", "Marsiglia"), ("es", "Marsella"),
                                             "Olympique de Marseille", ("fr", "OM")],
                                   "q": "Marseille", "q_it": "Marsiglia"},
        "AS Monaco FC": {"alias": ["Monaco", "AS Monaco"], "q": "AS Monaco", "q_it": "Monaco"},
        "OGC Nice": {"alias": ["OGC Nice", "Nice", ("it", "Nizza"), ("de", "Nizza"), ("es", "Niza"), "OGCN"],
                     "q": "OGC Nice"},
        "Paris FC": {"alias": ["Paris FC"]},
        "Paris Saint-Germain FC": {"alias": ["PSG", "Paris Saint-Germain", "Paris Saint Germain", "Paris SG"],
                                   "q": "PSG", "q_it": "PSG"},
        "Stade Rennais FC 1901": {"alias": ["Rennes", "Stade Rennais"], "q": "Stade Rennais"},
        "RC Strasbourg Alsace": {"alias": ["Strasbourg", ("it", "Strasburgo"), "RCSA"], "q": "RC Strasbourg"},
        "Toulouse FC": {"alias": ["Toulouse", ("it", "Tolosa"), "TFC"], "q": "Toulouse FC"},
        "ES Troyes AC": {"alias": ["Troyes", "ESTAC"], "q": "Troyes"},
    },
}

# Cognomi degli allenatori (presi da football-data.org) troppo comuni o
# ambigui per essere usati da soli: la squadra si riconosce solo dal nome
# completo (es. "Davide Ancelotti", non "Ancelotti" che di solito e' Carlo).
# Contiene anche nomi di battesimo, come rete di sicurezza.
COACH_SURNAME_STOPLIST = {
    "Still", "Ancelotti", "Pellegrini", "Castro", "Oliveira", "Enrique", "Luis", "Luís", "José", "Jose",
    "Juan", "Carlos", "Antonio", "Hugo", "Paulo", "Mikel", "Unai", "Xabi", "Carles", "Manolo", "Beñat",
    "Cesc", "Claudio", "Filipe", "Rúben", "Ruben", "Pepe", "Marco", "Daniel", "David", "Michael",
    "Frank", "Slot", "Rose", "King", "Moore", "Silva", "Martínez", "Martinez", "Fernández", "Fernandez",
    "García", "Garcia", "González", "Gonzalez", "Rodríguez", "Rodriguez", "López", "Lopez", "Pérez",
    "Perez", "Sánchez", "Sanchez", "Gómez", "Gomez", "Díaz", "Diaz", "Müller", "Muller", "Schmidt",
    "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker", "Martin", "Bernard", "Thomas", "Robert",
    "Richard", "Petit", "Durand", "Rossi", "Russo", "Ferrari", "Esposito", "Bianchi", "Romano", "Colombo",
    "Ricci", "Marino", "Greco", "Bruno", "Gallo", "Conti", "Costa", "Giordano", "Mancini", "Rizzo",
    "Lombardi", "Moretti", "Smith", "Jones", "Brown", "Taylor", "Wilson", "Davies", "Evans", "Johnson",
    "Roberts", "Walker", "Wright", "Thompson", "White", "Hall", "Green", "Wood", "Little", "Will",
}

# =====================================================================
# TIPO DI NOTIZIA (decide priorita', limiti, l'etichetta e l'hashtag del tipo)
# =====================================================================
# Una notizia di cui si riconosce il tipo lo porta scritto due volte:
# - in alto, accanto al campionato:   🇮🇹 Serie A · 🚑 Infortuni
#   (si vede subito scorrendo l'argomento o i risultati di una ricerca)
# - in fondo, dopo gli hashtag delle squadre:   #Juventus #Lazio · #Infortuni
#   (toccando #Infortuni si vedono tutte le notizie di quel tipo)
# Le notizie generali non hanno ne' etichetta ne' hashtag di tipo.
# "Infortuni" vale per tutte le assenze: infortuni, squalifiche, rientri.
TYPE_TAGS = {
    "press": ("🎙", "Conferenza"),
    "coach": ("👔", "Allenatore"),
    "injury": ("🚑", "Infortuni"),
    "lineup": ("📋", "Formazioni"),
}
MAX_TYPE_LABELS = 2     # etichette in alto (gli hashtag in fondo ci sono tutti)

# Come sono fatte le liste qui sotto:
# - XXX_KEYWORDS: parole/frasi che valgono in qualsiasi lingua
# - XXX_KEYWORDS_BY_LANG: parole che contano solo negli articoli di quella
#   lingua ("out" in italiano vuol dire infortunato, in inglese quasi mai)
# - XXX_NOT_KEYWORDS: modi di dire che contengono una di quelle parole ma
#   parlano d'altro ("senza dubbio", "minuti di recupero"): vengono ignorati
# - una voce che comincia con "~" e' un'espressione regolare (serve per le
#   parole composte tedesche e poco altro)

# Conferenze stampa. "conferenza" da sola vale (in italiano e' quasi sempre
# quella dell'allenatore); in francese serve la frase intera, perche'
# "Conférence" e' anche la Conference League. Vale come conferenza anche un
# titolo che riporta le parole dell'allenatore ("Conte: «Domani gioca...»").
PRESS_KEYWORDS = [
    "conferenza stampa", "in conferenza", "conferenza", "sala stampa", "le parole di",
    "press conference", "presser", "pre-match press", "media conference", "news conference",
    "rueda de prensa", "conferencia de prensa", "sala de prensa", "en rueda",
    "~\\w*pressekonferenz", "conférence de presse", "en conférence", "point presse", "les mots forts",
]
PRESS_KEYWORDS_BY_LANG = {"de": ["pk"]}     # "PK" in tedesco = Pressekonferenz
PRESS_NOT_KEYWORDS = [
    "conferenza dei servizi", "conferenza di servizi", "conference league", "conferenza episcopale",
    "conferenza programmatica", "conferenza stato-regioni",
]

# Cambio allenatore
COACH_KEYWORDS = [
    "esonero", "esonerato", "esonerati", "dimissioni", "si dimette", "nuovo allenatore", "nuovo tecnico",
    "traghettatore", "cambio in panchina", "cambio di allenatore", "panchina a rischio",
    "rischia la panchina", "panchina che scotta", "salta la panchina", "panchina di",
    "esordio in panchina", "debutto in panchina",
    "sacked", "sacking", "sack", "sacks", "appointed", "appoints", "new manager", "new head coach",
    "new boss", "resigns", "resigned", "interim", "caretaker", "steps down", "part company",
    "parts company", "parted company",
    "destituido", "destitución", "destituye", "cesado", "despedido", "nuevo entrenador", "dimite",
    "dimisión", "interino",
    "entlassen", "entlassung", "freigestellt", "beurlaubt", "neuer trainer", "rücktritt",
    "interimstrainer", "trainerwechsel", "trainerentlassung", "trainer-aus",
    "limogé", "limogeage", "démission", "nouvel entraîneur", "intérim", "intérimaire",
]

# Formazioni: probabili, scelte, convocati
LINEUP_KEYWORDS = [
    "probabili formazioni", "probabile formazione", "formazione", "formazioni", "undici titolare",
    "probabile undici", "undici iniziale", "titolare", "titolari", "turnover", "rotazioni",
    "ballottaggio", "ballottaggi", "in panchina", "dalla panchina", "convocati", "convocazioni",
    "dal primo minuto", "dal 1'", "le scelte di", "possibili scelte", "maglia da titolare",
    "verso una maglia",
    "team news", "line-up", "lineup", "line-ups", "lineups", "starting xi", "predicted xi",
    "starting lineup", "starting line-up", "rotation", "benched", "left out of",
    "alineación", "alineaciones", "posible once", "once probable", "once titular", "rotaciones",
    "convocatoria", "convocados", "titular", "titulares", "suplente", "suplentes",
    "aufstellung", "aufstellungen", "startelf", "kader",
    "composition", "compositions", "compo", "compos", "onze de départ", "onze probable", "titulaire",
    "titulaires", "dans le groupe", "sur le groupe", "le groupe pour", "le groupe de",
    "le groupe des", "le groupe du", "groupe retenu", "groupe convoqué",
    "~le groupe \\w+ pour", "~groupe de \\d+ joueurs",
]
# Formazioni UFFICIALI (vedi TEAM_CAPS "official")
OFFICIAL_LINEUP_KEYWORDS = [
    "formazioni ufficiali", "formazione ufficiale", "le ufficiali",
    "confirmed lineups", "confirmed line-ups", "confirmed lineup", "confirmed line-up", "confirmed team",
    "confirmed xi", "xi confirmed", "lineups confirmed", "line-ups confirmed", "lineup confirmed",
    "line-up confirmed", "team confirmed:", "team news confirmed", "official lineups",
    "official line-ups", "~confirmed \\w+ (?:team|xi|line-?ups?)",
    "alineaciones confirmadas", "alineaciones oficiales", "alineación confirmada", "alineación oficial",
    "once confirmado", "once oficial", "onces confirmados", "onces oficiales",
    "offizielle aufstellung", "offizielle aufstellungen", "aufstellungen sind da", "aufstellung ist da",
    "compos officielles", "compositions officielles", "composition officielle", "compo officielle",
]
LINEUP_NOT_KEYWORDS = [
    # qui "panchina" e' quella dell'allenatore, e "formazione" vuol dire "squadra"
    "esordio in panchina", "debutto in panchina", "cambio in panchina", "prima in panchina",
    "~formazione (?:giallo|ner|bianco|rosso|azzurr|viola|granata|blucerchiat|gialloblù)\\w*",
]

# Infortuni, squalifiche, assenze, recuperi
INJURY_KEYWORDS = [
    # italiano
    "infortunio", "infortuni", "infortunato", "infortunati", "infortunata", "infermeria", "lesione",
    "lesioni", "stiramento", "risentimento muscolare", "affaticamento", "elongazione", "distorsione",
    "frattura", "problema muscolare", "problemi muscolari", "problemi fisici", "guaio muscolare",
    "operato al", "operato alla", "sarà operato", "è stato operato", "intervento chirurgico",
    "squalifica", "squalificato", "squalificati", "squalifiche", "diffidato", "diffidati",
    "indisponibile", "indisponibili", "assente", "assenti", "assenza", "assenze", "forfait", "ai box",
    "in dubbio", "a disposizione", "esami strumentali", "affaticato", "acciaccato", "acciaccati",
    "tegola", "differenziato", "si allena a parte", "lavoro a parte",
    "~(?:torn\\w+|rientr\\w+|di nuovo|lavoro|allenamento) in gruppo", "influenzato",
    "sindrome influenzale", "attacco febbrile", "tempi di recupero", "recuperato", "recuperati",
    "rientro", "rientri", "rientra", "rientrano", "rientrato", "saltare", "brutte notizie",
    "ginocchio", "caviglia", "polpaccio", "flessore", "flessori", "adduttore", "adduttori", "menisco",
    "crociato", "tendine", "pubalgia", "bicipite femorale", "quadricipite", "soleo", "trauma",
    "contusione", "lombalgia", "ricaduta",
    # inglese
    "injury", "injuries", "injured", "hamstring", "groin", "ankle", "calf", "knee", "thigh",
    "achilles", "concussion",
    "surgery", "ruled out", "sidelined", "doubtful", "fitness", "suspended", "suspension", "banned",
    "back in training", "returns to training", "back fit", "fit again", "scan", "out injured",
    "out of action", "absentee", "absentees", "unavailable", "illness", "withdraws", "withdrawn",
    # spagnolo
    "lesión", "lesiones", "lesionado", "lesionados", "enfermería", "parte médico", "pruebas médicas",
    "alta médica", "recibe el alta", "quirófano", "esguince", "rotura", "molestias", "rodilla",
    "tobillo", "isquiotibiales", "sóleo", "gemelo", "musculares", "sanción",
    "sancionado", "sancionados", "se pierde", "recupera a", "recuperan a",
    # tedesco
    "verletzt", "verletzte", "~\\w*verletzung(?:en)?", "ausfall", "ausfälle", "fällt aus",
    "fallen aus", "~f[aä]ll(?:t|en)\\b[^.:!?|]{0,70}\\baus(?=\\s*(?:$|[.,:;!?|–-]))", "fraglich",
    "gesperrt", "sperre", "gelbsperre", "untersuchung", "zerrung", "angeschlagen", "lazarett",
    "zurück im training", "kreuzbandriss", "muskelfaserriss", "bänderriss", "muskelbündelriss",
    "sehnenriss", "meniskusriss", "innenbandriss", "syndesmoseriss", "sprunggelenk",
    "oberschenkel", "adduktoren", "~muskel(?:verletzung|problem|beschwerden)\\w*", "~muskulär\\w*",
    # francese
    "blessé", "blessés", "blessure", "blessures", "forfaits", "absent", "absents", "absence",
    "absences", "incertain", "incertains", "suspendu", "suspendus", "infirmerie", "préservé",
    "ménagé", "mis au repos", "apte", "aptes", "inapte", "opéré", "point médical", "genou",
    "cheville", "mollet", "cuisse", "ischios", "adducteurs", "musculaire",
]
INJURY_KEYWORDS_BY_LANG = {
    "it": ["out", "stop", "salta", "saltano", "dubbio", "dubbi", "recupera", "recuperano", "recupero",
           "esami", "emergenza"],
    "en": ["doubt", "doubts", "ban", "to miss", "will miss", "set to miss"],
    "es": ["baja", "bajas", "duda", "dudas"],
    "de": ["fehlt", "fehlen", "comeback"],
}
INJURY_NOT_KEYWORDS = [
    "senza dubbio", "senza dubbi", "nessun dubbio", "mai avuto dubbi", "non ha dubbi", "non ho dubbi",
    "non ci sono dubbi", "ogni dubbio", "minuti di recupero", "fermato nel recupero",
    "gol nel recupero", "rete nel recupero", "pari nel recupero", "beffa nel recupero",
    "vince nel recupero", "segna nel recupero", "decide nel recupero", "pieno recupero",
    "recupero palla", "recupero della", "gara di recupero", "partita di recupero",
    "recupero di campionato", "stop al mercato", "stop al campionato", "stop alle", "stop alla",
    "non stop", "salta la conferenza", "salta la panchina", "salta l'accordo", "salta tutto",
    "salta la trattativa", "saltare il banco", "saltare l'accordo", "saltare la trattativa",
    "saltare la panchina",
    "out-of", "hits out", "hit out", "miss out", "misses out", "missed out", "missing out",
    "crying out", "no doubt", "without doubt", "without a doubt",
    "sube y baja", "a la baja", "baja forma", "sin duda", "sin dudas", "no hay duda", "ninguna duda",
    "ans d'absence", "ans d’absence",
]
# In italiano "ko" e "si ferma" parlano di un infortunio solo dopo il nome di
# un giocatore ("Bremer ko", "Bremer si ferma"): dopo il nome di una squadra
# sono una sconfitta ("Milan ko a Bergamo", "la Juve si ferma").
INJURY_PLAYER_WORDS = {"it": ["ko", "k.o.", "si ferma", "si fermano"]}

# =====================================================================
# ESCLUSIONI
# =====================================================================
# Se il TITOLO contiene una di queste parole/frasi, la notizia viene scartata
# (maiuscole/minuscole indifferenti, parole intere).
EXCLUDE_TITLE_WORDS = [
    # serie minori, giovanili, femminile
    "serie b", "serie c", "serie d", "lega pro", "eccellenza", "promozione", "prima categoria",
    "seconda categoria", "terza categoria", "dilettanti", "primavera", "next gen", "nextgen",
    "milan futuro", "under 23", "under-23", "u23", "u-23", "under 21", "under-21", "u21", "u-21",
    "under 20", "u20", "under 19", "under-19", "u19", "u-19", "under 18", "u18", "under 17", "u17",
    "under 16", "u16", "u15", "giovanili", "settore giovanile", "allievi", "juniores", "youth",
    "academy", "femminile", "femminili", "women", "women's", "womens", "wsl", "nwsl", "lionesses",
    "frauen", "frauen-bundesliga", "féminine", "féminines", "feminine", "femenino", "femenina",
    "liga f", "arkema", "championship", "league one", "league two", "national league", "efl trophy",
    "vanarama", "segunda división", "segunda division", "hypermotion", "primera federación",
    "primera rfef", "segunda federación", "segunda rfef", "tercera", "castilla", "atlètic", "filial",
    "2. bundesliga", "zweite liga", "3. liga", "dritte liga", "regionalliga", "oberliga", "ligue 2",
    "national 2", "national 3",
    "sub-23", "sub 23", "sub-21", "sub 21", "sub-19", "sub 19", "sub-18", "sub-17", "sub 17", "sub-16",
    "juvenil", "juveniles", "u 23", "u 21", "u 19", "u 17", "1ª federación", "1ª rfef", "2ª rfef",
    "bilbao athletic", "sevilla atlético", "betis deportivo", "villarreal b", "real sociedad b",
    "sevilla b", "celta fortuna", "équipe réserve", "équipe amateur", "lyon-duchère", "la duchère",
    # cronaca e cultura delle citta'/regioni che hanno il nome di una squadra (Lecce, Lazio, Venezia...)
    "stagione lirica", "consiglio comunale", "consiglio regionale", "regione lazio",
    "provincia di lecce", "intergruppo", "sagra", "mercatino", "elezioni comunali",
    "elezioni regionali", "ca' foscari", "ca’ foscari", "bataille d'échecs", "bataille d’échecs",
    "torneo solidario", "torneo benéfico", "cuddly toy",
    # pagine di statistiche e calendari automatici (nessuna notizia dentro)
    "h2h", "historial de enfrentamientos", "direkter vergleich", "statistiken", "statistiche di",
    "estadísticas de", "stats for", "resultado ·", "resumen y goles", "por la fecha", "cómo seguir",
    "dónde seguir",
    # squadre di altri campionati con nomi uguali
    "inter miami", "mls", "inter turku", "juve stabia", "liga mx", "brasileirão", "brasileirao",
    "saudi pro league", "lok leipzig", "lokomotive leipzig", "chemie leipzig", "viktoria köln",
    "fortuna köln", "stuttgarter kickers", "forest green", "coventry blaze", "leeds rhinos", "hull fc",
    "hull kr", "olimpia milano", "virtus", "reyer", "unicaja", "asvel", "sig strasbourg",
    # altri sport
    "basket", "basketball", "baloncesto", "pallacanestro", "eurolega", "euroleague", "euroliga",
    "eurocup", "nba", "wnba", "acb", "bbl", "lba", "volley", "volleyball", "pallavolo", "voleibol",
    "handball", "pallamano", "balonmano", "rugby", "top 14", "six nations", "sei nazioni",
    "champions cup", "hockey", "eishockey", "nhl", "tennis", "atp", "wta", "sinner", "alcaraz",
    "djokovic", "musetti", "paolini", "coppa davis", "davis cup", "billie jean king", "nitto",
    "formula 1", "formula uno", "f1", "gran premio", "grand prix", "motogp", "moto2", "moto3",
    "superbike", "sbk", "nascar", "indycar", "wec", "24 ore", "24 heures", "24 hours", "wrc", "dakar",
    "ciclismo", "cycling", "ciclista", "tour de france", "giro d'italia", "vuelta", "uci", "golf",
    "ryder cup", "pga", "boxe", "boxing", "ufc", "mma", "atletica", "athletics", "nuoto", "swimming",
    "sci alpino", "biathlon", "pallanuoto", "waterpolo", "scherma", "nfl", "super bowl", "mlb",
    "cricket", "darts", "snooker", "futsal", "calcio a 5", "fútbol sala", "futbol sala",
    "beach soccer", "esports", "e-sports", "efootball", "ea sports fc", "kings league", "padel",
    "pádel", "maratona", "marathon", "olimpiadi", "olympics", "paralimpiadi", "america's cup",
    # scommesse, fantacalcio, tv, biglietti
    "pronostico", "pronostici", "quote", "scommesse", "scommessa", "betting", "odds", "betting tips",
    "prediction", "predictions", "pronóstico", "pronósticos", "apuestas", "cuotas", "prognose",
    "wett-tipp", "wettquoten", "quoten", "pronostic", "pronostics", "cotes", "paris sportifs",
    "bookmaker", "bookmakers", "bet builder", "betbuilder", "acca", "accumulator", "free bet", "tips",
    "quota", "promo code", "bonus code", "codice promo", "codice bonus", "kalshi", "free bets",
    "betting offer", "sign-up offer", "fantacalcio", "fanta", "fantasy", "fpl", "comunio", "kickbase",
    "biwenger", "mon petit gazon", "dove vedere", "dove vederla", "dove vederlo", "dove seguire",
    "dove seguirla", "dove seguirlo", "orario e canale", "canale tv", "in chiaro", "dazn", "in tv", "streaming", "diretta tv", "where to watch",
    "how to watch", "tv channel", "live stream", "dónde ver", "cómo ver", "en directo", "en vivo",
    "wo läuft", "übertragung", "où regarder", "sur quelle chaîne", "à quelle heure", "biglietti",
    "tickets", "entradas", "billets",
    # dirette, highlights, pagelle (roba del dopo-partita)
    "live", "in diretta", "minuto per minuto", "as it happened", "live blog", "liveblog",
    "live-ticker", "liveticker", "ticker", "directo", "en direct", "highlights", "gol e highlights",
    "sintesi", "pagelle", "voti", "tabellino", "player ratings", "ratings", "notas", "uno a uno",
    "einzelkritik", "noten", "les notes", "moviola", "quiz",
]

# Calciomercato (usate solo se INCLUDE_TRANSFER_NEWS = False)
TRANSFER_WORDS = [
    "calciomercato", "mercato", "trattativa", "trattative", "offerta", "prestito", "cessione",
    "clausola", "sul taccuino", "prepara l'assalto", "pronto all'assalto", "pronta all'assalto",
    "assalto a gennaio",
    "transfer", "transfers", "loan", "rumour", "rumours", "rumor", "rumors", "to sign", "lead race",
    "leads race", "join race", "joins race", "race to sign", "asking price", "january exit",
    "summer exit", "exit talks", "opening bid", "bid rejected", "swoop", "linked with",
    "renew interest", "register interest", "set to join", "selling", "release clause",
    "fichaje", "fichajes", "traspaso", "cesión", "mercado", "oferta", "ofertas", "cláusula",
    "se fija en", "puja por", "pretendido por",
    "transfert", "transferts", "une piste", "intéressé par",
    "wechsel", "leihe", "gerücht", "gerüchte", "wintertransfers", "sommertransfers", "ablöse",
    "im visier", "winterschlussverkauf",
]

# Sezioni del sito (pezzi dell'indirizzo tra due "/") che indicano altri
# sport, serie minori, video, dirette, fantacalcio...
EXCLUDED_URL_SEGMENTS = {
    "video", "videos", "live", "diretta", "live-blog", "liveblog", "highlights", "gallery",
    "galleries", "foto", "fotogallery", "photos", "pictures", "podcast", "podcasts", "tennis", "tenis",
    "formula-1", "formula1", "f1", "motogp", "moto", "motori", "motorsport", "motor", "basket",
    "basketball", "baloncesto", "nba", "volley", "volleyball", "ciclismo", "cycling", "radsport",
    "rugby", "golf", "atletica", "athletics", "nuoto", "swimming", "sport-invernali", "wintersport",
    "boxe", "boxing", "handball", "balonmano", "eishockey", "hockey", "nfl", "us-sport", "esports",
    "serie-b", "serie-c", "serie-d", "lega-pro", "dilettanti", "eccellenza", "primavera",
    "calcio-femminile", "femminile", "women", "womens-football", "frauen", "feminin", "femenino",
    "futbol-femenino", "championship", "league-one", "league-two", "segunda", "segunda-division",
    "primera-rfef", "2-bundesliga", "3-liga", "regionalliga", "ligue-2", "fantacalcio", "fantasy",
    "scommesse", "betting", "pronostici", "mas-deporte", "mas-deportes", "otros-deportes", "altri-sport",
}
TRANSFER_URL_SEGMENTS = {"calciomercato", "mercato", "fichajes", "transfers", "transfer-news",
                         "transfert", "transferts", "transfermarkt"}

# Pezzi di indirizzo che indicano pagine automatiche
EXCLUDED_URL_PATTERNS = [
    "/video/", "/videos/", "/highlights/", "/resume/", "/résumé/",
    "/live-blog/", "/match-centre/", "/matchcentre/", "/box-score/",
]

# Siti bloccati del tutto (social, scommesse, calcio dilettantistico, ecc.)
BLOCKED_NEWS_DOMAINS = [
    "reddit.com", "pinterest.com", "facebook.com", "twitter.com", "x.com",
    "youtube.com", "instagram.com", "tiktok.com", "wikipedia.org",
    "bettingexpert.com", "oddschecker.com", "sportsgambler.com",
    "betway.com", "bwin.com", "williamhill.com", "bet365.com",
    "tuttocampo.it", "competition.dz", "fussballdaten.de",
]

# =====================================================================
# AVVISI DI SALUTE (nella chat privata col bot, al massimo uno al giorno per tipo)
# =====================================================================
# Il bot ti scrive in privato se si accorge che qualcosa non va:
# - e' rimasto fermo piu' di HEALTH_GAP_MINUTES minuti (timer di cron-job.org
#   fermo? token GitHub scaduto?)
# - Google News non risponde da HEALTH_GOOGLE_FAILED_RUNS giri di fila
# - in un giorno sono falliti HEALTH_GROQ_FAILURES riassunti (tetto gratuito
#   di Groq esaurito?)
HEALTH_NOTICES = True
HEALTH_GAP_MINUTES = 45
HEALTH_GOOGLE_FAILED_RUNS = 12
HEALTH_GROQ_FAILURES = 25

# --- File di stato ---
# state.json: scritto SOLO dal workflow notizie (link gia' visti, limiti del giorno)
STATE_FILE = os.path.join(os.path.dirname(__file__), "state", "state.json")
# fixtures.json: scritto SOLO dal workflow calendario (partite e squadre)
FIXTURES_FILE = os.path.join(os.path.dirname(__file__), "state", "fixtures.json")
