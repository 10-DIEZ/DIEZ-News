"""
Controlla le notizie via Google News RSS (gratis, nessuna API key) per:
- cambio allenatore (esoneri, dimissioni, nuovi allenatori)
- turnover / probabili formazioni / titolari in dubbio

Da eseguire ogni 2-3 ore (vedi workflow GitHub Actions).
Nessun limite di chiamate: Google News RSS e' pubblico e gratuito.
"""

import time
import urllib.parse
from datetime import datetime, timedelta, timezone

import feedparser

from config import (
    COACH_CHANGE_KEYWORDS,
    LEAGUES,
    LINEUP_RUMOR_KEYWORDS,
    NEWS_MAX_AGE_DAYS,
)
from utils import load_state, save_state, send_telegram_message, trim_list


def build_google_news_url(query: str) -> str:
    """Costruisce l'URL del feed RSS di Google News per una ricerca in italiano."""
    query = f"{query} when:{NEWS_MAX_AGE_DAYS}d"
    encoded = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl=it&gl=IT&ceid=IT:it"


def search_news(query: str, max_items: int = 8) -> list:
    """Interroga Google News RSS e restituisce le voci trovate."""
    url = build_google_news_url(query)
    feed = feedparser.parse(url)
    return feed.entries[:max_items]


def is_recent_enough(entry) -> bool:
    """
    Controlla direttamente la data di pubblicazione della notizia,
    invece di fidarsi solo del filtro di Google (piu' affidabile
    per scartare articoli vecchi o di stagioni passate).
    """
    published_struct = entry.get("published_parsed")
    if not published_struct:
        # Se manca la data, la teniamo per non perdere notizie valide
        return True
    published_dt = datetime.fromtimestamp(time.mktime(published_struct), tz=timezone.utc)
    cutoff = datetime.now(timezone.utc) - timedelta(days=NEWS_MAX_AGE_DAYS)
    return published_dt >= cutoff


def format_date(entry) -> str:
    """Formatta la data della notizia in modo leggibile, se disponibile."""
    published_struct = entry.get("published_parsed")
    if not published_struct:
        return ""
    dt = datetime.fromtimestamp(time.mktime(published_struct), tz=timezone.utc)
    return dt.strftime("%d/%m %H:%M UTC")


def format_source(entry) -> str:
    """Estrae il nome della testata, se disponibile."""
    source = entry.get("source")
    if isinstance(source, dict):
        return source.get("title", "")
    return ""


def build_message(entry, league_name: str, emoji: str, category_label: str) -> str:
    """Costruisce un messaggio Telegram ben formattato, con titolo cliccabile."""
    title = entry.get("title", "Notizia")
    link = entry.get("link", "")
    source = format_source(entry)
    date_str = format_date(entry)

    lines = [f"{emoji} <b>{category_label}</b> — {league_name}"]
    lines.append("")
    lines.append(f'<a href="{link}">{title}</a>')

    meta_parts = [p for p in [source, date_str] if p]
    if meta_parts:
        lines.append("· ".join(meta_parts))

    return "\n".join(lines)


def run():
    state = load_state()
    seen = set(state.get("news_seen", []))
    new_seen = list(seen)
    any_new = False

    categories = [
        (COACH_CHANGE_KEYWORDS, "coach", "👔", "Possibile cambio allenatore"),
        (LINEUP_RUMOR_KEYWORDS, "lineup", "🔄", "Turnover / formazione"),
    ]

    for league in LEAGUES:
        league_name = league["name"]
        league_query_base = league["news_query_it"]

        for keywords, tag, emoji, label in categories:
            query = f'{league_query_base} (' + " OR ".join(keywords) + ")"
            for item in search_news(query):
                link = item.get("link", item.get("title"))
                uid = f"{tag}|{link}"
                if uid in seen:
                    continue
                if not is_recent_enough(item):
                    continue

                testo = build_message(item, league_name, emoji, label)
                send_telegram_message(testo)
                new_seen.append(uid)
                seen.add(uid)
                any_new = True

    if any_new:
        state["news_seen"] = trim_list(new_seen)
        save_state(state)
        print("Stato aggiornato con nuove notizie.")
    else:
        print("Nessuna novita nelle notizie.")


if __name__ == "__main__":
    run()
