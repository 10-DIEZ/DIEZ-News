"""
Controlla le notizie via Google News RSS (gratis, nessuna API key) per:
- cambio allenatore (esoneri, dimissioni, nuovi allenatori)
- turnover / probabili formazioni / titolari in dubbio

Da eseguire ogni 2-3 ore (vedi workflow GitHub Actions).
Nessun limite di chiamate: Google News RSS è pubblico e gratuito.
"""

import urllib.parse

import feedparser

from config import COACH_CHANGE_KEYWORDS, LEAGUES, LINEUP_RUMOR_KEYWORDS
from utils import load_state, save_state, send_telegram_message, trim_list


def build_google_news_url(query: str) -> str:
    """Costruisce l'URL del feed RSS di Google News per una ricerca in italiano."""
    encoded = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl=it&gl=IT&ceid=IT:it"


def search_news(query: str, max_items: int = 8) -> list:
    """Interroga Google News RSS e restituisce le voci trovate."""
    url = build_google_news_url(query)
    feed = feedparser.parse(url)
    return feed.entries[:max_items]


def run():
    state = load_state()
    seen = set(state.get("news_seen", []))
    new_seen = list(seen)
    any_new = False

    for league in LEAGUES:
        league_name = league["name"]
        league_query_base = league["news_query_it"]

        # --- Cambio allenatore ---
        coach_query = f'{league_query_base} (' + " OR ".join(COACH_CHANGE_KEYWORDS) + ")"
        for item in search_news(coach_query):
            uid = f"coach|{item.get('link', item.get('title'))}"
            if uid in seen:
                continue
            testo = (
                f"👔 <b>Possibile cambio allenatore</b> — {league_name}\n"
                f"{item.get('title')}\n"
                f"{item.get('link')}"
            )
            send_telegram_message(testo)
            new_seen.append(uid)
            seen.add(uid)
            any_new = True

        # --- Turnover / probabili formazioni ---
        lineup_query = f'{league_query_base} (' + " OR ".join(LINEUP_RUMOR_KEYWORDS) + ")"
        for item in search_news(lineup_query):
            uid = f"lineup|{item.get('link', item.get('title'))}"
            if uid in seen:
                continue
            testo = (
                f"🔄 <b>Turnover / formazione</b> — {league_name}\n"
                f"{item.get('title')}\n"
                f"{item.get('link')}"
            )
            send_telegram_message(testo)
            new_seen.append(uid)
            seen.add(uid)
            any_new = True

    if any_new:
        state["news_seen"] = trim_list(new_seen)
        save_state(state)
        print("Stato aggiornato con nuove notizie.")
    else:
        print("Nessuna novità nelle notizie.")


if __name__ == "__main__":
    run()
