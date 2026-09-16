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

# Coppe europee SENZA calendario preciso gratuito (football-data.org non le
# copre nel piano free): ricerca generica sulla competizione, non per singola
# partita. Solo formazioni ufficiali e assenze/turnover (niente allenatori,
# gia' coperto dalla ricerca per club nei campionati sopra).
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

# --- Fonti considerate affidabili (top + semi-top, italiane ed estere) ---
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

# File dove viene salvato lo stato (cosa e' gia' stato notificato)
STATE_FILE = os.path.join(os.path.dirname(__file__), "state", "state.json")
