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

# --- Campionati seguiti (ID API-Football + nome per le ricerche Google News) ---
# Se la stagione cambia (es. da 2026 a 2027), aggiorna SEASON qui sotto.
SEASON = 2026

LEAGUES = [
    {"id": 135, "name": "Serie A", "news_query_it": "Serie A"},
    {"id": 39, "name": "Premier League", "news_query_it": "Premier League"},
    {"id": 140, "name": "La Liga", "news_query_it": "Liga spagnola"},
    {"id": 78, "name": "Bundesliga", "news_query_it": "Bundesliga"},
    {"id": 61, "name": "Ligue 1", "news_query_it": "Ligue 1"},
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

# File dove viene salvato lo stato (cosa è già stato notificato)
STATE_FILE = os.path.join(os.path.dirname(__file__), "state", "state.json")
