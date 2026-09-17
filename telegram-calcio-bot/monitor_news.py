"""
Monitoraggio mirato per i 5 campionati seguiti - SOLO 3 categorie:
formazioni ufficiali, assenze/turnover (infortuni, squalifiche, dubbi),
cambio allenatore. Niente calciomercato, niente notizie generiche.

Fonti:
- Google News (italiano + lingua nativa del campionato)
- RSS diretti delle testate (scaricati una volta, poi filtrati in locale -
  cosi' non si perdono le squadre meno cliccate sepolte nei risultati Google)
- Calendario preciso per campionati + Champions League + (quando disponibile)
  Europa League/Conference League, per ricerca mirata per singola partita

Titolo tradotto e riassunto naturale generati da Groq (AI gratuita),
con fallback a traduzione diretta se Groq non e' disponibile.
Anti-doppioni: se piu' testate coprono la stessa notizia, manda solo la prima.

Da eseguire ogni 5 minuti (vedi workflow GitHub Actions).
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
    ABSENCE_KEYWORDS,
    ALLOWED_NEWS_DOMAINS,
    COACH_KEYWORDS,
    DEFAULT_LABEL,
    DIRECT_RSS_FEEDS,
    DUPLICATE_SUPPRESS_HOURS,
    EXCLUDED_URL_PATTERNS,
    EXTRA_COMPETITIONS_NO_FIXTURES,
    FORMATION_KEYWORDS,
    GROQ_API_KEY,
    LABEL_KEYWORDS,
    LEAGUES,
    NEWS_MAX_AGE_DAYS,
    NEWS_MAX_ITEMS_PER_QUERY,
    PREVIEW_KEYWORDS,
)
from utils import load_state, save_state, send_telegram_message, send_telegram_photo, trim_list

GROQ_MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.6-27b"]
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

_TITLE_RE = re.compile(r"TITOLO:\s*(.+)")
_SUMMARY_RE = re.compile(r"RIASSUNTO:\s*(.+)", re.DOTALL)

SEND_DELAY_SECONDS = 1.5
MAX_MESSAGES_PER_RUN = 40

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


def fetch_direct_rss_items() -> list:
    """Scarica tutti i feed RSS diretti configurati (una volta sola per esecuzione)."""
    items = []
    for url, lang in DIRECT_RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            entries = feed.entries or []
            if not entries:
                print(f"[WARN] RSS diretto vuoto o non raggiungibile: {url}")
            items.extend((e, lang) for e in entries)
        except Exception as e:
            print(f"[WARN] errore leggendo RSS diretto {url}: {e}")
    print(f"RSS diretti: {len(items)} articoli raccolti da {len(DIRECT_RSS_FEEDS)} fonti")
    return items


def filter_direct_items_for_fixture(direct_items: list, home: str, away: str) -> list:
    """Tra gli articoli RSS gia' scaricati, tiene solo quelli che nominano entrambe le squadre."""
    home_l, away_l = home.lower(), away.lower()
    matches = []
    for entry, lang in direct_items:
        title = entry.get("title", "").lower()
        summary = entry.get("summary", "").lower()
        text = f"{title} {summary}"
        if home_l in text and away_l in text:
            matches.append((entry, lang))
    return matches


def filter_direct_items_for_text(direct_items: list, required_text: str, keyword_sets: list) -> list:
    """Tra gli articoli RSS gia' scaricati, tiene quelli che nominano required_text + una parola chiave."""
    required_l = required_text.lower()
    matches = []
    for entry, lang in direct_items:
        title = entry.get("title", "").lower()
        summary = entry.get("summary", "").lower()
        text = f"{title} {summary}"
        if required_l not in text:
            continue
        keywords = keyword_sets if isinstance(keyword_sets, list) else []
        if any(kw.lower() in text for kw in keywords):
            matches.append((entry, lang))
    return matches


def summarize_with_ai(title: str, description: str, source_lang: str) -> dict | None:
    """Traduce il titolo in italiano e scrive un breve riassunto naturale, via Groq (gratuito)."""
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

    for model in GROQ_MODELS:
        try:
            resp = requests.post(
                GROQ_ENDPOINT,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": model,
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
                print(f"[WARN] Groq ({model}) ha risposto {resp.status_code}: {resp.text[:200]}")
                continue

            content = resp.json()["choices"][0]["message"]["content"]
            title_match = _TITLE_RE.search(content)
            summary_match = _SUMMARY_RE.search(content)

            if not title_match:
                print(f"[WARN] Groq ({model}): risposta senza il formato atteso, provo il modello successivo.")
                continue

            return {
                "title": title_match.group(1).strip(),
                "summary": summary_match.group(1).strip() if summary_match else "",
            }
        except Exception as e:
            print(f"[WARN] chiamata Groq ({model}) fallita: {e}")
            continue

    print(f"[WARN] TUTTI i modelli Groq {GROQ_MODELS} hanno fallito - controlla https://console.groq.com/docs/deprecations")
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
    """Traduce un testo in italiano, con un servizio di riserva se il primo fallisce."""
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
    """Etichetta in base a parole chiave nel titolo (testo gia' tradotto in italiano)."""
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

    lines = [f"{flag} <b>{league_name}</b>", ""]
    lines.append(f"<b>{title}</b>")

    body = ai_summary or clean_description(meta.get("description", ""))
    if body and body.lower() != title.strip().lower():
        lines.append(body)

    lines.append("")
    lines.append(f"<i>Fonte: {source}</i>")
    return "\n".join(lines)


def build_message(real_link: str, title: str, league_name: str, flag: str, category_label: str) -> str:
    header = f"{flag} <b>{league_name}</b>"
    return f"{header}\n{title}\n{real_link}"


def gather_coach_items(league: dict, direct_items: list) -> list:
    """Ricerca cambio allenatore per un campionato: Google News (italiano + lingua nativa) + RSS diretti."""
    items = []
    kw_it = " OR ".join(COACH_KEYWORDS["it"])
    query_it = f'"{league["name"]}" calcio ({kw_it})'
    items.extend((e, "it") for e in search_news(query_it, lang="it", country="IT"))

    if league.get("native_lang"):
        kw_native = " OR ".join(COACH_KEYWORDS[league["native_lang"]])
        query_native = f'"{league["native_name"]}" ({kw_native})'
        native_entries = search_news(query_native, lang=league["native_lang"], country=league["native_country"])
        items.extend((e, league["native_lang"]) for e in native_entries)

    all_coach_kw = [kw for kws in COACH_KEYWORDS.values() for kw in kws]
    items.extend(filter_direct_items_for_text(direct_items, league["name"], all_coach_kw))

    return items


def gather_fixture_items(fixture: dict, direct_items: list) -> list:
    """
    Ricerca mirata su una singola partita di oggi: formazioni ufficiali +
    assenze/turnover + anteprima/probabili formazioni, con i nomi esatti
    delle due squadre. Cerca in italiano, nella lingua/stampa locale del
    campionato, e negli RSS diretti gia' scaricati.
    """
    home, away = fixture["home"], fixture["away"]
    items = []

    kw_it = " OR ".join(FORMATION_KEYWORDS["it"] + ABSENCE_KEYWORDS["it"] + PREVIEW_KEYWORDS["it"])
    query_it = f'"{home}" "{away}" ({kw_it})'
    items.extend((e, "it") for e in search_news(query_it, lang="it", country="IT", max_items=8))

    native_lang = fixture.get("native_lang")
    if native_lang:
        kw_native = " OR ".join(
            FORMATION_KEYWORDS[native_lang] + ABSENCE_KEYWORDS[native_lang] + PREVIEW_KEYWORDS[native_lang]
        )
        query_native = f'"{home}" "{away}" ({kw_native})'
        native_entries = search_news(query_native, lang=native_lang, country=fixture["native_country"], max_items=8)
        items.extend((e, native_lang) for e in native_entries)

    items.extend(filter_direct_items_for_fixture(direct_items, home, away))

    return items


def gather_generic_competition_items(competition_name: str, direct_items: list) -> list:
    """
    Per le coppe europee (quando non abbiamo trovato le partite esatte di
    oggi): ricerca generica sulla competizione, non per singola partita.
    Formazioni ufficiali, assenze/turnover e anteprima, in italiano + RSS diretti.
    """
    kw_it = " OR ".join(FORMATION_KEYWORDS["it"] + ABSENCE_KEYWORDS["it"] + PREVIEW_KEYWORDS["it"])
    query_it = f'"{competition_name}" ({kw_it})'
    entries = search_news(query_it, lang="it", country="IT")
    items = [(e, "it") for e in entries]

    all_kw = FORMATION_KEYWORDS["it"] + ABSENCE_KEYWORDS["it"] + PREVIEW_KEYWORDS["it"]
    items.extend(filter_direct_items_for_text(direct_items, competition_name, all_kw))

    return items


def prune_topics(state: dict) -> None:
    """Toglie dallo stato le voci 'argomento gia' segnalato' piu' vecchie di un giorno."""
    topics = state.get("topics_sent", {})
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    kept = {}
    for key, iso_ts in topics.items():
        try:
            ts = datetime.fromisoformat(iso_ts)
            if ts >= cutoff:
                kept[key] = iso_ts
        except ValueError:
            continue
    state["topics_sent"] = kept


def run():
    state = load_state()
    seen = set(state.get("news_seen", []))
    new_seen = list(seen)
    any_new = False
    sent_this_run = 0
    groq_failures_this_run = 0

    sources_to_check = []

    direct_items = fetch_direct_rss_items()

    for league in LEAGUES:
        sources_to_check.append((league["name"], league["flag"], gather_coach_items(league, direct_items), league["name"]))

    today_fixtures = state.get("today_fixtures", [])
    today_cup_fixtures = state.get("today_cup_fixtures", [])
    all_today_fixtures = today_fixtures + today_cup_fixtures
    for fixture in all_today_fixtures:
        topic_base = f'{fixture["home"]}|{fixture["away"]}'
        sources_to_check.append((fixture["league"], fixture["flag"], gather_fixture_items(fixture, direct_items), topic_base))

    for comp in EXTRA_COMPETITIONS_NO_FIXTURES:
        sources_to_check.append((comp["name"], comp["flag"], gather_generic_competition_items(comp["name"], direct_items), comp["name"]))

    print(f"Partite di oggi: {len(today_fixtures)} campionati + {len(today_cup_fixtures)} coppe minori")

    for league_name, flag, entries, topic_base in sources_to_check:
        if sent_this_run >= MAX_MESSAGES_PER_RUN:
            break

        for item, item_lang in entries:
            if sent_this_run >= MAX_MESSAGES_PER_RUN:
                break

            google_link = item.get("link", "")
            real_link = resolve_real_url(google_link)

            if not is_allowed_domain(real_link):
                continue
            if is_excluded_url(real_link):
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
                if GROQ_API_KEY:
                    groq_failures_this_run += 1
                title = translate_to_italian(original_title, item_lang)
                ai_summary = ""
                if meta.get("description"):
                    meta["description"] = translate_to_italian(meta["description"], item_lang)

            category_label = classify_label(title)

            topic_key = f"{topic_base}::{category_label}"
            topics_sent = state.setdefault("topics_sent", {})
            last_sent_iso = topics_sent.get(topic_key)
            is_duplicate = False
            if last_sent_iso:
                try:
                    last_sent_dt = datetime.fromisoformat(last_sent_iso)
                    if datetime.now(timezone.utc) - last_sent_dt < timedelta(hours=DUPLICATE_SUPPRESS_HOURS):
                        is_duplicate = True
                except ValueError:
                    pass

            if is_duplicate:
                new_seen.append(uid)
                seen.add(uid)
                any_new = True
                continue

            inviato_con_foto = False
            if meta.get("image"):
                caption = build_caption(meta, title, ai_summary, real_link, league_name, flag, category_label)
                inviato_con_foto = send_telegram_photo(meta["image"], caption, "🔗 Leggi l'articolo", real_link)

            if not inviato_con_foto:
                testo_fallback = build_message(real_link, title, league_name, flag, category_label)
                send_telegram_message(testo_fallback, disable_preview=True)

            new_seen.append(uid)
            seen.add(uid)
            any_new = True
            sent_this_run += 1
            topics_sent[topic_key] = datetime.now(timezone.utc).isoformat()
            time.sleep(SEND_DELAY_SECONDS)

    prune_topics(state)

    stats = state.setdefault("stats", {"week_sent": 0, "week_groq_failures": 0})
    stats["week_sent"] = stats.get("week_sent", 0) + sent_this_run
    stats["week_groq_failures"] = stats.get("week_groq_failures", 0) + groq_failures_this_run

    if any_new:
        state["news_seen"] = trim_list(new_seen)
        save_state(state)
        print(f"Stato aggiornato: {sent_this_run} notizie inviate.")
    else:
        save_state(state)
        print("Nessuna novita nelle notizie.")


if __name__ == "__main__":
    run()
