"""
Configurazione del sistema di monitoraggio calcio.
Modifica qui i campionati, le stagioni e le parole chiave.
"""

import os

# --- Credenziali (lette da variabili d'ambiente / GitHub Secrets, MAI scritte qui) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY", "")

API_FOOTBALL_HOST = "https://v3.football.api-sports.io"

# --- Campionati seguiti (ID API-Football + query notizie + bandiera per la grafica) ---
# Se la stagione cambia (es. da 2026 a 2027), aggiorna SEASON qui sotto.
SEASON = 2026

LEAGUES = [
    {"id": 135, "name": "Serie A", "flag": "🇮🇹", "news_query_it": 'Serie A calcio -"Serie B"'},
    {"id": 39, "name": "Premier League", "flag": "🏴", "news_query_it": "Premier League calcio"},
    {"id": 140, "name": "La Liga", "flag": "🇪🇸", "news_query_it": "Liga spagnola calcio"},
    {"id": 78, "name": "Bundesliga", "flag": "🇩🇪", "news_query_it": "Bundesliga calcio"},
    {"id": 61, "name": "Ligue 1", "flag": "🇫🇷", "news_query_it": "Ligue 1 calcio"},
]

# --- Parole chiave per la ricerca notizie (cambio allenatore / turnover) ---
COACH_CHANGE_KEYWORDS = [
    "esonerato", "esonero", "dimissioni allenatore", "nuovo allenatore",
    "sacked", "resigns as manager", "new head coach", "appointed manager",
]

LINEUP_RUMOR_KEYWORDS = [
    "probabili formazioni", "turnover", "titolare in dubbio", "panchina",
    "diffidato", "squalificato", "infortunio", "ballottaggio",
]

# Solo notizie pubblicate negli ultimi N giorni (filtro applicato dal codice,
# non solo dalla ricerca Google) - scarta articoli vecchi/di stagioni passate
NEWS_MAX_AGE_DAYS = 2

# Quante notizie al massimo recuperare per ogni ricerca (campionato x categoria)
NEWS_MAX_ITEMS_PER_QUERY = 5

# File dove viene salvato lo stato (cosa e' gia' stato notificato)
STATE_FILE = os.path.join(os.path.dirname(__file__), "state", "state.json")
