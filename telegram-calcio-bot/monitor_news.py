"""
Controlla tutte le notizie principali di calcio via Google News RSS
(gratis, nessuna API key per la ricerca) per i 5 campionati seguiti -
ricerca sia in italiano sia, per i campionati esteri, nella lingua
originale. Titolo tradotto e riassunto naturale generati da un modello
AI gratuito (Groq), con fallback automatico se non disponibile.

Da eseguire ogni 5 minuti (vedi workflow GitHub Actions).

I link di Google News sono "mascherati" (news.google.com/rss/articles/...):
vengono risolti nel link reale dell'articolo, da cui si estraggono
immagine/descrizione/nome sito (meta-dati pubblici della pagina) per
mandare un post foto+didascalia in stile canale news.
"""

import html
import re
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import feedparser
import requests
from deep_translator import GoogleTranslator, MyMemoryTranslator
from googlenewsdecoder import gnewsdecoder

from config import (
    ALLOWED_NEWS_DOMAINS,
    DEFAULT_LABEL,
    EXCLUDED_URL_PATTERNS,
    GROQ_API_KEY,
    LABEL_KEYWORDS,
    LEAGUES,
    NEWS_MAX_AGE_DAYS,
    NEWS_MAX_ITEMS_PER_QUERY,
)
from utils import load_state, save_state, send_telegram_message, send_telegram_photo, trim_list

SEND_DELAY_SECONDS = 1.5
MAX_MESSAGES_PER_RUN = 25

GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

_TITLE_RE = re.compile(r"TITOLO:\s*(.+)")
_SUMMARY_RE = re.compile(r"RIASSUNTO:\s*(.+)", re.DOTALL)

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


def summarize_with_ai(title: str, description: str, source_lang: str) -> dict | None:
    """
    Chiede a un modello Groq (gratuito) di tradurre il titolo in italiano e
    scrivere un breve riassunto naturale in italiano (2-3 frasi), nello stile
    di un post da canale di notizie sportive. Restituisce None se il
    servizio non e' configurato o la richiesta fallisce, cosi' il chiamante
    puo' ricadere sul metodo di riserva (meta-dati + traduzione diretta).
    """
    if not GROQ_API_KEY:
        print("[INFO] GROQ_API_KEY non configurata: uso il metodo di riserva (traduzione diretta).")
        return None

    prompt = (
        f"Lingua originale del testo: {source_lang}\n"
        f"Titolo originale: {title}\n"
        f"Descrizione originale: {description or '(non disponibile)'}\n\n"
        "Rispondi SOLO in questo formato, in italiano fluente e naturale:\n"
        "TITOLO: <titolo tradotto e ben scritto, una riga>\n"
        "RIASSUNTO: <2-3 frasi che raccontano la notizia in modo naturale, "
        "come farebbe un canale sportivo, senza inventare fatti non presenti nel testo originale>"
    )

    try:
        resp = requests.post(
            GROQ_ENDPOINT,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": "Sei un redattore sportivo che traduce e riassume notizie di calcio in italiano, in modo chiaro e naturale."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.4,
                "max_tokens": 220,
            },
            timeout=20,
        )
        if resp.status_code != 200:
            print(f"[WARN] Groq ha risposto {resp.status_code}: {resp.text[:200]}")
            return None

        content = resp.json()["choices"][0]["message"]["content"]
        title_match = _TITLE_RE.search(content)
        summary_match = _SUMMARY_RE.search(content)

        if not title_match:
            return None

        return {
            "title": title_match.group(1).strip(),
            "summary": summary_match.group(1).strip() if summary_match else "",
        }
    except Exception as e:
        print(f"[WARN] chiamata Groq fallita: {e}")
        return None

    prompt = (
        f"Lingua originale del testo: {source_lang}\n"
        f"Titolo originale: {title}\n"
        f"Descrizione originale: {description or '(non disponibile)'}\n\n"
        "Rispondi SOLO in questo formato, in italiano fluente e naturale:\n"
        "TITOLO: <titolo tradotto e ben scritto, una riga>\n"
        "RIASSUNTO: <2-3 frasi che raccontano la notizia in modo naturale, "
        "come farebbe un canale sportivo, senza inventare fatti non presenti nel testo originale>"
    )

    try:
        resp = requests.post(
            GROQ_ENDPOINT,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": "Sei un redattore sportivo che traduce e riassume notizie di calcio in italiano, in modo chiaro e naturale."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.4,
                "max_tokens": 220,
            },
            timeout=20,
        )
        if resp.status_code != 200:
            print(f"[WARN] Groq ha risposto {resp.status_code}: {resp.text[:200]}")
            return None

        content = resp.json()["choices"][0]["message"]["content"]
        title_match = _TITLE_RE.search(content)
        summary_match = _SUMMARY_RE.search(content)

        if not title_match:
            return None

        return {
            "title": title_match.group(1).strip(),
            "summary": summary_match.group(1).strip() if summary_match else "",
        }
    except Exception as e:
        print(f"[WARN] chiamata Groq fallita: {e}")
        return None


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


def build_google_news_url(query: str, lang: str = "it", country: str = "IT") -> str:
    query = f"{query} when:{NEWS_MAX_AGE_DAYS}d"
    encoded = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl={lang}&gl={country}&ceid={country}:{lang}"


def search_news(query: str, lang: str = "it", country: str = "IT", max_items: int = NEWS_MAX_ITEMS_PER_QUERY) -> list:
    url = build_google_news_url(query, lang, country)
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

def is_excluded_url(url: str) -> bool:
    """Scarta pagine automatiche (video/risultati/live-blog), anche da domini affidabili."""
    lowered = url.lower()
    return any(pattern in lowered for pattern in EXCLUDED_URL_PATTERNS)

def translate_to_italian(text: str, source_lang: str) -> str:
    """
    Traduce un testo in italiano, con un servizio di riserva se il primo fallisce
    (capita che Google Translate blocchi le richieste dagli IP di GitHub Actions,
    condivisi tra moltissimi utenti).
    """
    if not text or source_lang == "it":
        return text

    try:
        translated = GoogleTranslator(source=source_lang, target="it").translate(text)
        if translated and translated.strip().lower() != text.strip().lower():
            return translated
    except Exception as e:
        print(f"[WARN] Google Translate fallito ({source_lang}): {e}")

    try:
        translated = MyMemoryTranslator(source=source_lang, target="it").translate(text)
        if translated:
            return translated
    except Exception as e:
        print(f"[WARN] MyMemory Translate fallito ({source_lang}): {e}")

    print(f"[WARN] Traduzione non riuscita per: {text[:60]}...")
    return text


def classify_label(text: str) -> str:
    """Etichetta informativa in base a parole chiave nel titolo (non filtra nulla)."""
    lowered = text.lower()
    for label, keywords in LABEL_KEYWORDS:
        if any(kw in lowered for kw in keywords):
            return label
    return DEFAULT_LABEL


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


def build_caption(meta: dict, title: str, ai_summary: str, real_link: str, league_name: str, flag: str, category_label: str) -> str:
    source = site_display_name(meta.get("site_name", ""), real_link)

    lines = [f"{flag} <b>{league_name}</b> · {category_label}", ""]
    lines.append(f"<b>{title}</b>")

    body = ai_summary or clean_description(meta.get("description", ""))
    if body and body.lower() != title.strip().lower():
        lines.append(body)

    lines.append("")
    lines.append(f"<i>Fonte: {source}</i>")
    lines.append(real_link)
    return "\n".join(lines)


def build_message(real_link: str, title: str, league_name: str, flag: str, category_label: str) -> str:
    header = f"{flag} <b>{league_name}</b> · {category_label}"
    return f"{header}\n{title}\n{real_link}"


def gather_league_items(league: dict) -> list:
    """Raccoglie le notizie di un campionato: ricerca in italiano + (se previsto) nella lingua originale."""
    items = []
    items.extend((entry, "it") for entry in search_news(league["news_query_it"], lang="it", country="IT"))

    if league.get("native_lang") and league.get("news_query_native"):
        native_entries = search_news(
            league["news_query_native"],
            lang=league["native_lang"],
            country=league["native_country"],
        )
        items.extend((entry, league["native_lang"]) for entry in native_entries)

    return items


def run():
    state = load_state()
    seen = set(state.get("news_seen", []))
    new_seen = list(seen)
    any_new = False
    sent_this_run = 0

    for league in LEAGUES:
        if sent_this_run >= MAX_MESSAGES_PER_RUN:
            break
        league_name = league["name"]
        flag = league["flag"]

        for item, item_lang in gather_league_items(league):
            if sent_this_run >= MAX_MESSAGES_PER_RUN:
                break

            google_link = item.get("link", "")
            real_link = resolve_real_url(google_link)

            if not is_allowed_domain(real_link):
                continue

            uid = f"news|{real_link}"
            if uid in seen:
                continue
            if not is_recent_enough(item):
                continue

            original_title = item.get("title", "Notizia")

            meta = fetch_article_meta(real_link)

            ai_result = summarize_with_ai(original_title, meta.get("description", ""), item_lang)

            if ai_result:
                title = ai_result["title"]
                ai_summary = ai_result["summary"]
            else:
                title = translate_to_italian(original_title, item_lang)
                ai_summary = ""
                if meta.get("description"):
                    meta["description"] = translate_to_italian(meta["description"], item_lang)

            category_label = classify_label(title)

            inviato_con_foto = False
            if meta.get("image"):
                caption = build_caption(meta, title, ai_summary, real_link, league_name, flag, category_label)
                inviato_con_foto = send_telegram_photo(meta["image"], caption)

            if not inviato_con_foto:
                testo_fallback = build_message(real_link, title, league_name, flag, category_label)
                send_telegram_message(testo_fallback, disable_preview=False)

            new_seen.append(uid)
            seen.add(uid)
            any_new = True
            sent_this_run += 1
            time.sleep(SEND_DELAY_SECONDS)

    if any_new:
        state["news_seen"] = trim_list(new_seen)
        save_state(state)
        print(f"Stato aggiornato: {sent_this_run} notizie inviate.")
    else:
        print("Nessuna novita nelle notizie.")


if __name__ == "__main__":
    run()
