"""
Controlla le notizie via Google News RSS (gratis, nessuna API key) per:
- cambio allenatore (esoneri, dimissioni, nuovi allenatori)
- turnover / probabili formazioni / titolari in dubbio

Da eseguire ogni 5 minuti (vedi workflow GitHub Actions).
Nessun limite di chiamate: Google News RSS e' pubblico e gratuito.

I link di Google News sono "mascherati" (news.google.com/rss/articles/...):
vengono risolti nel link reale dell'articolo cosi' Telegram puo' generare
la sua anteprima grande automatica (immagine + titolo + descrizione),
esattamente come un post di un canale news.
"""

import time
import urllib.parse
from datetime import datetime, timedelta, timezone

import feedparser
from googlenewsdecoder import gnewsdecoder

from config import (
    COACH_CHANGE_KEYWORDS,
    LEAGUES,
    LINEUP_RUMOR_KEYWORDS,
    NEWS_MAX_AGE_DAYS,
    NEWS_MAX_ITEMS_PER_QUERY,
)
from utils import load_state, save_state, send_telegram_message, trim_list


def build_google_news_url(query: str) -> str:
    """Costruisce l'URL del feed RSS di Google News per una ricerca in italiano."""
    query = f"{query} when:{NEWS_MAX_AGE_DAYS}d"
    encoded = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl=it&gl=IT&ceid=IT:it"


def search_news(query: str, max_items: int = NEWS_MAX_ITEMS_PER_QUERY) -> list:
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
        return True
    published_dt = datetime.fromtimestamp(time.mktime(published_struct), tz=timezone.utc)
    cutoff = datetime.now(timezone.utc) - timedelta(days=NEWS_MAX_AGE_DAYS)
    return published_dt >= cutoff


def resolve_real_url(google_link: str) -> str:
    """
    Risolve il link 'mascherato' di Google News nell'URL reale dell'articolo.
    Se la decodifica fallisce (sito irraggiungibile, formato cambiato ecc.)
    restituisce il link originale come fallback.
    """
    if not google_link:
        return google_link
    try:
        result = gnewsdecoder(google_link, interval=0)
        if result.get("status") and result.get("decoded_url"):
            return result["decoded_url"]
    except Exception as e:
        print(f"[WARN] decodifica link fallita: {e}")
    return google_link


def build_message(real_link: str, fallback_title: str, league_name: str, flag: str, category_label: str) -> str:
    """
    Etichetta campionato + tipo di notizia, poi il titolo dell'articolo,
    poi il link reale. Il titolo viene sempre incluso: alcuni siti
    (es. certe pagine di Gazzetta) bloccano la generazione dell'anteprima
    di Telegram, quindi senza titolo resterebbe solo un link nudo.
    Quando il sito la permette, sotto comparira' comunque la card grande
    con l'immagine generata da Telegram.
    """
    header = f"{flag} <b>{league_name}</b> · {category_label}"
    return f"{header}\n{fallback_title}\n{real_link}"

    # Se non siamo riusciti a risolvere il link reale, Telegram non potra'
    # generare l'anteprima: aggiungiamo il titolo come testo di riserva.
    if "news.google.com" in real_link:
        return f"{header}\n{fallback_title}\n{real_link}"

    return f"{header}\n{real_link}"


def run():
    state = load_state()
    seen = set(state.get("news_seen", []))
    new_seen = list(seen)
    any_new = False

    categories = [
        (COACH_CHANGE_KEYWORDS, "coach", "Cambio allenatore"),
        (LINEUP_RUMOR_KEYWORDS, "lineup", "Turnover / formazioni"),
    ]

    for league in LEAGUES:
        league_name = league["name"]
        flag = league["flag"]
        league_query_base = league["news_query_it"]

        for keywords, tag, label in categories:
            query = f'{league_query_base} (' + " OR ".join(keywords) + ")"
            for item in search_news(query):
                google_link = item.get("link", "")
                real_link = resolve_real_url(google_link)

                uid = f"{tag}|{real_link}"
                if uid in seen:
                    continue
                if not is_recent_enough(item):
                    continue

                testo = build_message(real_link, item.get("title", "Notizia"), league_name, flag, label)
                send_telegram_message(testo, disable_preview=False)
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
