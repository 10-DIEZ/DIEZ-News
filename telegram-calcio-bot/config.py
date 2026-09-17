"""
Configurazione del sistema di monitoraggio calcio.
Focus ristretto e mirato: SOLO formazioni ufficiali, assenze/turnover
(infortuni, squalifiche, titolari in dubbio) e cambio allenatore.
Niente calciomercato, niente notizie generiche.
"""

import os

# --- Credenziali (lette da variabili d'ambiente / GitHub Secrets, MAI scritte qui) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
FOOTBALL_DATA_API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "")

FOOTBALL_DATA_HOST = "https://api.football-data.org/v4"

# --- Campionati seguiti ---
LEAGUES = [
    {
        "name": "Serie A", "flag": "🇮🇹", "fd_code": "SA",
        "native_lang": None, "native_country": None, "native_name": None,
    },
    {
        "name": "Premier League", "flag": "🏴", "fd_code": "PL",
        "native_lang": "en", "native_country": "GB", "native_name": "Premier League",
    },
    {
        "name": "La Liga", "flag": "🇪🇸", "fd_code": "PD",
        "native_lang": "es", "native_country": "ES", "native_name": "LaLiga",
    },
    {
        "name": "Bundesliga", "flag": "🇩🇪", "fd_code": "BL1",
        "native_lang": "de", "native_country": "DE", "native_name": "Bundesliga",
    },
    {
        "name": "Ligue 1", "flag": "🇫🇷", "fd_code": "FL1",
        "native_lang": "fr", "native_country": "FR", "native_name": "Ligue 1",
    },
    {
        "name": "Champions League", "flag": "⭐", "fd_code": "CL",
        "native_lang": None, "native_country": None, "native_name": None,
    },
]

# Coppe europee: ricerca generica di riserva sulla competizione (sempre attiva
# in aggiunta al calendario preciso di TheSportsDB, come rete di sicurezza).
EXTRA_COMPETITIONS_NO_FIXTURES = [
    {"name": "Europa League", "flag": "🟠"},
    {"name": "Conference League", "flag": "🔵"},
]

# Solo notizie pubblicate negli ultimi N giorni (filtro applicato dal codice)
NEWS_MAX_AGE_DAYS = 2

# Quante notizie al massimo recuperare per ogni singola ricerca
NEWS_MAX_ITEMS_PER_QUERY = 10

# --- Parole chiave per lingua: formazioni ufficiali ---
FORMATION_KEYWORDS = {
    "it": ["formazioni ufficiali", "formazione ufficiale"],
    "en": ["line-ups", "lineups", "starting XI", "confirmed team news"],
    "es": ["alineación oficial", "alineaciones oficiales", "once inicial"],
    "de": ["aufstellung", "startelf"],
    "fr": ["composition officielle", "compositions officielles"],
}

# --- Parole chiave per lingua: assenze / turnover / giocatori chiave mancanti ---
ABSENCE_KEYWORDS = {
    "it": ["turnover", "titolare in dubbio", "ballottaggio", "panchina", "infortunio",
           "infortunato", "squalificato", "diffidato", "assente", "si ferma"],
    "en": ["injury", "injured", "suspended", "doubt", "doubtful", "rotation",
           "benched", "sidelined", "out for"],
    "es": ["lesión", "lesionado", "sancionado", "duda", "rotación", "baja"],
    "de": ["verletzt", "gesperrt", "rotation", "fraglich", "fehlt"],
    "fr": ["blessé", "suspendu", "rotation", "incertain", "absent"],
}

# --- Parole chiave per lingua: cambio allenatore ---
COACH_KEYWORDS = {
    "it": ["esonerato", "esonero", "dimissioni", "nuovo allenatore", "nuovo tecnico"],
    "en": ["sacked", "resigns", "resignation", "appointed", "new manager", "new head coach"],
    "es": ["destituido", "dimite", "nuevo entrenador", "cesado"],
    "de": ["entlassen", "rücktritt", "neuer trainer"],
    "fr": ["limogé", "démission", "nouvel entraîneur"],
}

# --- Parole chiave per lingua: anteprima/probabili formazioni (escono PRIMA
# delle ufficiali, danno un primo segnale su chi potrebbe mancare) ---
PREVIEW_KEYWORDS = {
    "it": ["probabili formazioni", "anteprima", "vigilia", "verso"],
    "en": ["preview", "predicted lineup", "team news", "ahead of"],
    "es": ["previa", "alineación probable", "posible once"],
    "de": ["voraussichtliche aufstellung", "vorschau"],
    "fr": ["compo probable", "avant-match", "avant match"],
}

# --- Feed RSS diretti (bypassano Google News, che mostra solo i primi 10
# risultati per ricerca - con RSS diretti prendiamo TUTTI gli articoli
# recenti di ogni testata, cosi' non si perdono le squadre meno cliccate).
# ATTENZIONE: alcuni indirizzi (specialmente esteri) sono un primo tentativo,
# non tutti verificabili in anticipo - il codice logga quelli che non
# funzionano, li sistemiamo guardando i risultati reali del primo test.
DIRECT_RSS_FEEDS = {
    "https://www.gazzetta.it/rss/home.xml": "it",
    "https://www.ansa.it/sito/notizie/sport/calcio/calcio_rss.xml": "it",
    "https://www.corrieredellosport.it/rss/rss.shtml": "it",
    "http://feeds.bbci.co.uk/sport/football/rss.xml": "en",
    "https://www.theguardian.com/football/rss": "en",
    "https://www.marca.com/rss/futbol.xml": "es",
    "https://newsfeed.kicker.de/news/fussball": "de",
}

# ID delle competizioni su TheSportsDB (API gratuita alternativa), usata
# solo per il calendario di Europa League/Conference League - football-data.org
# non le copre nel piano gratuito.
THESPORTSDB_LEAGUE_IDS = {
    "Europa League": "4480",
    "Conference League": "5071",
}

# --- Fonti considerate affidabili (top + semi-top, italiane ed estere) ---
# Solo le notizie che arrivano da uno di questi siti vengono inviate.
ALLOWED_NEWS_DOMAINS = [
    # --- Italia: top ---
    "gazzetta.it", "sport.sky.it", "skysport.it", "corrieredellosport.it",
    "tuttosport.com", "sportmediaset.mediaset.it", "ansa.it", "goal.com",
    "repubblica.it", "corriere.it", "lastampa.it", "adnkronos.com",
    # --- Italia: semi-top / specializzati ---
    "calciomercato.com", "tuttomercatoweb.com", "fcinternews.it", "milannews.it",
    "juventusnews24.com", "footballitalia.net", "11contro11.it", "calcioefinanza.it",
    "legaseriea.it", "fanpage.it", "calcionews24.com", "ilnapolista.it",
    "sportitalia.com", "dazn.com", "calcioweb.eu", "calciolife.com",
    "ilfattoquotidiano.it", "ilgiornale.it", "today.it", "sportface.it",
    "calciostyle.it", "milanlive.it", "tuttojuve.com", "passioneinter.com",
    "asromalive.it", "spazionapoli.it",
    # --- Inghilterra ---
    "bbc.com", "bbc.co.uk", "skysports.com", "theguardian.com", "espn.com",
    # --- Spagna ---
    "marca.com", "as.com", "mundodeportivo.com", "sport.es",
    # --- Germania ---
    "kicker.de", "bild.de", "sport1.de",
    # --- Francia ---
    "lequipe.fr", "rmcsport.bfmtv.com",
]

# Pattern nell'URL che indicano pagine automatiche (video, risultati, live-blog)
EXCLUDED_URL_PATTERNS = [
    "/video/", "/videos/", "/highlights/", "/resume/", "/résumé/",
    "/live-blog/", "/match-centre/", "/matchcentre/", "/box-score/",
]

# --- Classificazione (in italiano, applicata DOPO la traduzione) ---
LABEL_KEYWORDS = [
    ("Formazioni ufficiali", ["formazioni ufficiali", "formazione ufficiale"]),
    ("Assenze e turnover", ["turnover", "titolare in dubbio", "ballottaggio", "panchina",
                            "infortunio", "infortunato", "squalificato", "diffidato",
                            "assente", "si ferma", "ko "]),
    ("Cambio allenatore", ["esonerato", "esonero", "dimissioni", "nuovo allenatore", "nuovo tecnico"]),
]
DEFAULT_LABEL = "Assenze e turnover"

# Se piu' testate scrivono della stessa notizia (stessa partita/campionato +
# stessa categoria) entro questa finestra di ore, mandiamo solo la prima e
# scartiamo i quasi-doppioni successivi.
DUPLICATE_SUPPRESS_HOURS = 3

# File dove viene salvato lo stato (cosa e' gia' stato notificato)
STATE_FILE = os.path.join(os.path.dirname(__file__), "state", "state.json")
