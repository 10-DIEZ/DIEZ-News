"""
Controlla le notizie via Google News RSS (gratis, nessuna API key) per:
- cambio allenatore (esoneri, dimissioni, nuovi allenatori)
- turnover / probabili formazioni / titolari in dubbio

Da eseguire ogni 5 minuti (vedi workflow GitHub Actions).
Nessun limite di chiamate: Google News RSS e' pubblico e gratuito.

I link di Google News sono "mascherati" (news.google.com/rss/articles/...):
vengono risolti nel link reale dell'articolo, da cui si estraggono
immagine/descrizione/nome sito (meta-dati pubblici della pagina) per
mandare un post foto+didascalia in stile canale news, gratis.
"""

import html
import re
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import feedparser
import requests
from googlenewsdecoder import gnewsdecoder

from config import (
    ALLOWED_NEWS_DOMAINS,
    COACH_CHANGE_KEYWORDS,
    LEAGUES,
    LINEUP_RUMOR_KEYWORDS,
    NEWS_MAX_AGE_DAYS,
    NEWS_MAX_ITEMS_PER_QUERY,
)
from utils import load_state, save_state, send_telegram_message, send_telegram_photo, trim_list

SEND_DELAY_SECONDS = 1.5
MAX_MESSAGES_PER_RUN = 20

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

_META_PATTERNS = {
    "image": [
        re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', re.IGNORECASE),
        re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']', re.IGNORECASE),
    ],
    "description": [
        re.compile(r'<meta[^>]+property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']', re.IGNORECASE),
        re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*property=["\']og:description["\']', re.IGNORECASE),
        re.compile(r'<meta[^>]+name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', re.IGNORECASE),
    ],
    "site_name": [
        re.compile(r'<meta[^>]+property=["\']og:site_name["\'][^>]*content=["\']([^"\']+)["\']', re.IGNORECASE),
        re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*property=["\']og:site_name["\']', re.IGNORECASE),
    ],
}


def fetch_article_meta(url: str) -> dict:
    """Scarica la pagina e ne estrae immagine/descrizione/nome sito dai meta-dati pubblici."""
    result = {"image": "", "description": "", "site_name": ""}
    try:
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=8)
        if resp.status_code != 200:
            return result
        html_head = resp.text[:60000]
        for field, patterns in _META_PATTERNS.items():
            for pattern in patterns:
                m = pattern.search(html_head)
                if m:
                    result[field] = html.unescape(m.group(1)).strip()
                    break
    except requests.RequestException as e:
        print(f"[WARN] impossibile leggere meta-dati di {url}: {e}")
    return result


def build_google_news_url(query: str) -> str:
    query = f"{query} when:{NEWS_MAX_AGE_DAYS}d"
    encoded = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl=it&gl=IT&ceid=IT:it"


def search_news(query: str, max_items: int = NEWS_MAX_ITEMS_PER_QUERY) -> list:
    url = build_google_news_url(query)
    feed = feedparser.parse(url)
    return feed.entries[:max_items]


def is_recent_enough(entry) -> bool:
    published_struct = entry.get("published_parsed")
    if not published_struct:
        return True
    published_dt = datetime.fromtimestamp(time.mktime(published_struct), tz=timezone.utc)
    cutoff = datetime.now(timezone.utc) - timedelta(days=NEWS_MAX_AGE_DAYS)
    return published_dt >= cutoff


def resolve_real_url(google_link: str) -> str:
    if not google_link:
        return google_link
    try:
        result = gnewsdecoder(google_link, interval=0)
        if result.get("status") and result.get("decoded_url"):
            return result["decoded_url"]
    except Exception as e:
        print(f"[WARN] decodifica link fallita: {e}")
    return google_link


def is_allowed_domain(url: str) -> bool:
    if not url:
        return False
    domain = urlparse(url).netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return any(domain == allowed or domain.endswith("." + allowed) for allowed in ALLOWED_NEWS_DOMAINS)


def clean_description(text: str, max_chars: int = 280) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "…"
    return text


def site_display_name(meta_site_name: str, url: str) -> str:
    if meta_site_name:
        return meta_site_name
    domain = urlparse(url).netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def build_caption(meta: dict, fallback_title: str, real_link: str, league_name: str, flag: str, category_label: str) -> str:
    description = clean_description(meta.get("description", ""))
    source = site_display_name(meta.get("site_name", ""), real_link)

    lines = [f"{flag} <b>{league_name}</b> · {category_label}", ""]
    lines.append(f"<b>{fallback_title}</b>")
    if description and description.lower() != fallback_title.strip().lower():
        lines.append(description)
    lines.append("")
    lines.append(f"<i>Fonte: {source}</i>")
    lines.append(real_link)
    return "\n".join(lines)


def build_message(real_link: str, fallback_title: str, league_name: str, flag: str, category_label: str) -> str:
    header = f"{flag} <b>{league_name}</b> · {category_label}"
    return f"{header}\n{fallback_title}\n{real_link}"


def run():
    state = load_state()
    seen = set(state.get("news_seen", []))
    new_seen = list(seen)
    any_new = False
    sent_this_run = 0

    categories = [
        (COACH_CHANGE_KEYWORDS, "coach", "Cambio allenatore"),
        (LINEUP_RUMOR_KEYWORDS, "lineup", "Turnover / formazioni"),
    ]

    for league in LEAGUES:
        if sent_this_run >= MAX_MESSAGES_PER_RUN:
            break
        league_name = league["name"]
        flag = league["flag"]
        league_query_base = league["news_query_it"]

        for keywords, tag, label in categories:
            if sent_this_run >= MAX_MESSAGES_PER_RUN:
                break
            query = f'{league_query_base} (' + " OR ".join(keywords) + ")"
            for item in search_news(query):
                if sent_this_run >= MAX_MESSAGES_PER_RUN:
                    break
                google_link = item.get("link", "")
                real_link = resolve_real_url(google_link)

                if not is_allowed_domain(real_link):
                    continue

                uid = f"{tag}|{real_link}"
                if uid in seen:
                    continue
                if not is_recent_enough(item):
                    continue

                testo_fallback = build_message(real_link, item.get("title", "Notizia"), league_name, flag, label)
                meta = fetch_article_meta(real_link)

                inviato_con_foto = False
                if meta.get("image"):
                    caption = build_caption(meta, item.get("title", "Notizia"), real_link, league_name, flag, label)
                    inviato_con_foto = send_telegram_photo(meta["image"], caption)

                if not inviato_con_foto:
                    send_telegram_message(testo_fallback, disable_preview=False)

                new_seen.append(uid)
                seen.add(uid)
                any_new = True
                sent_this_run += 1
                time.sleep(SEND_DELAY_SECONDS)

    if any_new:
        state["news_seen"] = trim_list(new_seen)
        save_state(state)
        print("Stato aggiornato con nuove notizie.")
    else:
        print("Nessuna novita nelle notizie.")


if __name__ == "__main__":
    run()
