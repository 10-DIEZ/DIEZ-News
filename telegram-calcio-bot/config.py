"""
Configurazione del sistema di monitoraggio calcio.
Modifica qui i campionati, le stagioni e le parole chiave.
"""

import os

# --- Credenziali (lette da variabili d'ambiente / GitHub Secrets, MAI scritte qui) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

API_FOOTBALL_HOST = "https://v3.football.api-sports.io"

# --- Campionati seguiti ---
# Se la stagione cambia (es. da 2026 a 2027), aggiorna SEASON qui sotto.
SEASON = 2026

# Per ogni campionato: query di ricerca ampia (tutte le notizie principali,
# non solo categorie specifiche), sia in italiano sia (per i campionati
# esteri) nella lingua originale, cosi' troviamo anche le notizie delle
# testate locali - poi tradotte automaticamente in italiano.
LEAGUES = [
    {
        "id": 135, "name": "Serie A", "flag": "🇮🇹",
        "news_query_it": 'Serie A calcio -"Serie B"',
        "native_lang": None, "native_country": None, "news_query_native": None,
    },
    {
        "id": 39, "name": "Premier League", "flag": "🏴",
        "news_query_it": "Premier League calcio",
        "native_lang": None, "native_country": None, "news_query_native": None,
    },
    {
        "id": 140, "name": "La Liga", "flag": "🇪🇸",
        "news_query_it": "Liga spagnola calcio",
        "native_lang": None, "native_country": None, "news_query_native": None,
    },
    {
        "id": 78, "name": "Bundesliga", "flag": "🇩🇪",
        "news_query_it": "Bundesliga calcio",
        "native_lang": None, "native_country": None, "news_query_native": None,
    },
    {
        "id": 61, "name": "Ligue 1", "flag": "🇫🇷",
        "news_query_it": "Ligue 1 calcio",
        "native_lang": None, "native_country": None, "news_query_native": None,
    },
]

# Solo notizie pubblicate negli ultimi N giorni (filtro applicato dal codice,
# non solo dalla ricerca Google) - scarta articoli vecchi/di stagioni passate
NEWS_MAX_AGE_DAYS = 2

# Quante notizie al massimo recuperare per ogni ricerca (per campionato)
NEWS_MAX_ITEMS_PER_QUERY = 25

# --- Fonti considerate affidabili (solo testate italiane, top + semi-top) ---
# Le testate italiane coprono gia' tutti e 5 i campionati (anche l'estero),
# quindi niente piu' ricerche in altre lingue: piu' semplice e affidabile.
# Solo le notizie che arrivano da uno di questi siti vengono inviate.
# Aggiungi o rimuovi domini qui in qualsiasi momento (senza "www.").
ALLOWED_NEWS_DOMAINS = [
    # --- Top ---
    "gazzetta.it",
    "sport.sky.it",
    "skysport.it",
    "corrieredellosport.it",
    "tuttosport.com",
    "sportmediaset.mediaset.it",
    "ansa.it",
    "eurosport.it",
    "goal.com",
    "repubblica.it",
    "corriere.it",
    # --- Semi-top / specializzati ---
    "calciomercato.com",
    "tuttomercatoweb.com",
    "fcinternews.it",
    "milannews.it",
    "juventusnews24.com",
    "footballitalia.net",
    "11contro11.it",
    "calcioefinanza.it",
    "legaseriea.it",
    "fanpage.it",
    "calcionews24.com",
    "ilnapolista.it",
    "sportitalia.com",
    "dazn.com",
]

# Pattern nell'URL che indicano pagine automatiche (video, risultati, live-blog)
# e non vere notizie scritte - vengono scartate anche se il dominio e' affidabile
EXCLUDED_URL_PATTERNS = [
    "/video/", "/videos/", "/highlights/", "/resume/", "/résumé/",
    "/live-blog/", "/match-centre/", "/matchcentre/", "/box-score/",
]

# --- Classificazione automatica (solo informativa, NON filtra le notizie) ---
# Assegna un'etichetta al messaggio in base a parole chiave nel titolo.
LABEL_KEYWORDS = [
    ("Cambio allenatore", ["esonerato", "esonero", "dimissioni", "nuovo allenatore", "nuovo tecnico", "sacked", "resign"]),
    ("Formazioni / turnover", ["probabili formazioni", "formazione", "turnover", "titolare", "panchina", "ballottaggio", "diffidato", "formazioni ufficiali"]),
    ("Infortuni / squalifiche", ["infortunio", "infortunato", "squalifica", "squalificato", "si ferma", "ko ", "stop forzato", "lesione"]),
    ("Calciomercato", ["calciomercato", "mercato", "trattativa", "trasferimento", "rinnovo", "addio", "cessione", "acquisto", "colpo di mercato"]),
]
DEFAULT_LABEL = "Notizia"

# File dove viene salvato lo stato (cosa e' gia' stato notificato)
STATE_FILE = os.path.join(os.path.dirname(__file__), "state", "state.json")
