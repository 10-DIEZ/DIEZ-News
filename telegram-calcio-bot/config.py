"""
Configurazione del sistema di monitoraggio calcio.
Focus: SOLO i 5 campionati principali (niente coppe europee - senza
calendario preciso gratuito era impossibile garantire copertura completa).
Categorie: formazioni ufficiali, assenze/turnover, cambio allenatore.
Obiettivo dichiarato: non deve scappare nessuna notizia rilevante.
"""

import os

# --- Credenziali (lette da variabili d'ambiente / GitHub Secrets, MAI scritte qui) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
FOOTBALL_DATA_API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "")

FOOTBALL_DATA_HOST = "https://api.football-data.org/v4"

# --- I 5 campionati seguiti (niente piu' coppe europee) ---
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
]

# Solo notizie pubblicate negli ultimi N giorni (filtro applicato dal codice)
NEWS_MAX_AGE_DAYS = 2

# Quante notizie al massimo recuperare per ogni singola ricerca (alzato da
# 8/10 a 20 ora che il budget non si spalma piu' sulle coppe europee)
NEWS_MAX_ITEMS_PER_QUERY = 20

# --- Parole chiave per lingua: formazioni ufficiali ---
FORMATION_KEYWORDS = {
    "it": ["formazioni ufficiali", "formazione ufficiale", "formazioni confermate"],
    "en": ["line-ups", "lineups", "starting XI", "confirmed team news", "confirmed lineup", "starting lineup"],
    "es": ["alineación oficial", "alineaciones oficiales", "once inicial", "once titular"],
    "de": ["aufstellung", "startelf", "startaufstellung"],
    "fr": ["composition officielle", "compositions officielles", "onze de départ"],
}

# --- Parole chiave per lingua: assenze / turnover / giocatori chiave mancanti ---
ABSENCE_KEYWORDS = {
    "it": ["turnover", "titolare in dubbio", "ballottaggio", "panchina", "infortunio",
           "infortunato", "squalificato", "diffidato", "assente", "si ferma", "recupera",
           "salta la partita", "out", "acciaccato"],
    "en": ["injury", "injured", "suspended", "doubt", "doubtful", "rotation",
           "benched", "sidelined", "out for", "fitness test", "injury update",
           "ruled out", "return to training"],
    "es": ["lesión", "lesionado", "sancionado", "duda", "rotación", "baja",
           "descarte", "parte médico", "vuelve a los entrenamientos"],
    "de": ["verletzt", "gesperrt", "rotation", "fraglich", "fehlt", "ausfall",
           "muskelverletzung", "kehrt zurück"],
    "fr": ["blessé", "suspendu", "rotation", "incertain", "absent", "forfait",
           "de retour à l'entraînement", "infirmerie"],
}

# --- Parole chiave per lingua: cambio allenatore ---
COACH_KEYWORDS = {
    "it": ["esonerato", "esonero", "dimissioni", "nuovo allenatore", "nuovo tecnico", "si dimette"],
    "en": ["sacked", "resigns", "resignation", "appointed", "new manager", "new head coach", "stepped down", "fired"],
    "es": ["destituido", "dimite", "nuevo entrenador", "cesado", "presenta su dimisión"],
    "de": ["entlassen", "rücktritt", "neuer trainer", "freigestellt"],
    "fr": ["limogé", "démission", "nouvel entraîneur", "démis de ses fonctions"],
}

# --- Parole chiave per lingua: anteprima/probabili formazioni (escono PRIMA
# delle ufficiali, danno un primo segnale su chi potrebbe mancare) ---
PREVIEW_KEYWORDS = {
    "it": ["probabili formazioni", "anteprima", "vigilia", "verso", "come arriva"],
    "en": ["preview", "predicted lineup", "team news", "ahead of", "how to watch"],
    "es": ["previa", "alineación probable", "posible once", "así llega"],
    "de": ["voraussichtliche aufstellung", "vorschau", "so kommt"],
    "fr": ["compo probable", "avant-match", "avant match", "à l'approche de"],
}

# --- Feed RSS diretti: presi per intero (non filtrati/limitati da Google),
# cosi' le squadre meno cliccate non restano sepolte. Mix di generaliste
# (coprono TUTTE le squadre del campionato, non solo le big) e alcune di
# club per approfondimento extra sulle squadre piu' seguite.
# ATTENZIONE: alcuni indirizzi (specialmente esteri) sono un primo tentativo,
# non tutti verificabili in anticipo - il codice logga quelli che non
# funzionano nel log di ogni run, li sistemiamo guardando i risultati reali.
DIRECT_RSS_FEEDS = {
    # Italia - generaliste (coprono tutta la Serie A)
    "https://www.gazzetta.it/rss/home.xml": "it",
    "https://www.ansa.it/sito/notizie/sport/calcio/calcio_rss.xml": "it",
    "https://www.corrieredellosport.it/rss/rss.shtml": "it",
    "https://www.tuttomercatoweb.com/rss": "it",
    "https://www.calciomercato.com/rss": "it",
    # Italia - focus club (approfondimento extra sulle big)
    "https://www.fcinternews.it/rss/": "it",
    "https://www.milannews.it/rss": "it",
    "https://www.tuttojuve.com/rss": "it",
    "https://www.spazionapoli.it/feed": "it",
    # Inghilterra - generaliste
    "http://feeds.bbci.co.uk/sport/football/rss.xml": "en",
    "https://www.theguardian.com/football/rss": "en",
    "https://www.skysports.com/rss/12040": "en",
    # Spagna - generaliste
    "https://www.marca.com/rss/futbol.xml": "es",
    "https://as.com/rss/futbol/portada.xml": "es",
    # Germania - generaliste
    "https://newsfeed.kicker.de/news/fussball": "de",
    # Francia - generaliste
    "https://dwh.lequipe.fr/api/edito/rss?path=/Football": "fr",
}

# --- Domini BLOCCATI (spam, scommesse, social, contenuti non pertinenti).
# Cambiato da whitelist a blacklist: una whitelist esclude per costruzione
# le testate che dimentichiamo di aggiungere, una blacklist lascia passare
# tutto tranne cio' che sappiamo essere spazzatura - meglio per l'obiettivo
# "non deve scappare nulla".
BLOCKED_NEWS_DOMAINS = [
    "reddit.com", "pinterest.com", "facebook.com", "twitter.com", "x.com",
    "youtube.com", "instagram.com", "tiktok.com", "wikipedia.org",
    "bettingexpert.com", "oddschecker.com", "sportsgambler.com",
    "betway.com", "bwin.com", "williamhill.com", "bet365.com",
]

# Pattern nell'URL che indicano pagine automatiche (video, risultati, live-blog)
EXCLUDED_URL_PATTERNS = [
    "/video/", "/videos/", "/highlights/", "/resume/", "/résumé/",
    "/live-blog/", "/match-centre/", "/matchcentre/", "/box-score/",
]

# Se piu' testate scrivono della stessa notizia (stessa partita/campionato +
# stessa categoria) entro questa finestra di ore, mandiamo solo la prima e
# scartiamo i quasi-doppioni successivi. Il controllo avviene PRIMA di
# chiamare Groq/scaricare l'immagine, per non sprecare risorse su doppioni.
DUPLICATE_SUPPRESS_HOURS = 3

# File dove viene salvato lo stato (cosa e' gia' stato notificato)
STATE_FILE = os.path.join(os.path.dirname(__file__), "state", "state.json")
