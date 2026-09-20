"""
Monitoraggio mirato per i 5 campionati seguiti - SOLO 3 categorie:
formazioni ufficiali, assenze/turnover (infortuni, squalifiche, dubbi,
giocatori chiave mancanti), cambio allenatore. Niente calciomercato,
niente coppe europee (tolte: senza calendario preciso gratuito non si
poteva garantire la copertura completa richiesta).

Obiettivo: non deve scappare nessuna notizia rilevante sui 5 campionati.

Fonti:
- Google News (italiano + lingua nativa del campionato), fino a 20
  risultati per ricerca
- RSS diretti delle testate (scaricati una volta, poi filtrati in locale -
  cosi' non si perdono le squadre meno cliccate sepolte nei risultati Google)
- Ricerca per singola partita di oggi con i nomi esatti delle due squadre
  (e piccole varianti del nome, per gestire abbreviazioni comuni)

Titolo tradotto e riassunto naturale generati da Groq (AI gratuita),
con fallback a traduzione diretta se Groq non e' disponibile.
Anti-doppioni: controllato PRIMA di chiamare Groq/scaricare l'immagine,
per non sprecare risorse su notizie che verrebbero comunque scartate.

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
    ACTIVE_WINDOW_DAYS,
    BLOCKED_NEWS_DOMAINS,
    COACH_KEYWORDS,
    DIRECT_RSS_FEEDS,
    DUPLICATE_SUPPRESS_HOURS,
    EXCLUDED_URL_PATTERNS,
    GROQ_API_KEY,
    LEAGUES,
    NEWS_MAX_AGE_DAYS,
    NEWS_MAX_ITEMS_PER_QUERY,
    PRESS_CONFERENCE_KEYWORDS,
    PREVIEW_KEYWORDS,
    STOP_BEFORE_KICKOFF_HOURS,
)
from utils import load_state, save_state, send_telegram_message, send_telegram_photo, trim_list

GROQ_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

# In alcune lingue il nome del campionato e' ambiguo (es. "Bundesliga" in
# tedesco esiste anche per basket/pallamano) e "allenatore/Trainer" e'
# generico in tutti gli sport - escludiamo esplicitamente gli altri sport.
OTHER_SPORTS_EXCLUDE = ["basketball", "handball", "eishockey", "pallacanestro",
                        "pallamano", "volleyball", "rugby", "hockey"]

_TITLE_RE = re.compile(r"TITOLO:\s*(.+)")
_SUMMARY_RE = re.compile(r"RIASSUNTO:\s*(.+)", re.DOTALL)

SEND_DELAY_SECONDS = 1.5
MAX_MESSAGES_PER_RUN = 40
MAX_RUN_SECONDS = 480  # 8 minuti: si ferma da solo qualunque cosa succeda, non aspetta un'ora

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
        re.compile(r'<meta[^>]+name=["\']twitter:image["\'][^>]*content=["\']([^"\']+)["\']', re.IGNORECASE),
        re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*name=["\']twitter:image["\']', re.IGNORECASE),
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

# Prefissi/suffissi comuni che la stampa spesso omette rispetto al nome
# ufficiale (es. "Bayer 04 Leverkusen" -> stampa scrive spesso "Leverkusen").
# Uso per generare una seconda variante di ricerca, non sostituisce il nome
# completo (cerchiamo entrambi).
_NAME_STRIP_PATTERNS = [
    r"^FC ", r"^AFC ", r"^AC ", r"^SS ", r"^US ", r"^UD ", r"^SC ", r"^CF ",
    r"^Real ", r"^Real$", r"^VfL ", r"^VfB ", r"^SV ", r"^1\. FC ", r"^TSG ",
    r"^RC ", r"^RCD ", r"^CA ", r"^CD ", r"^Stade ", r"^Olympique ", r"^AS ",
    r" FC$", r" CF$", r" AFC$", r" AC$",
    r"^Bayer \d+ ", r"^Borussia ", r"^1\. FSV ", r"^SpVgg ",
]


def name_variants(name: str) -> list:
    """
    Genera fino a 2 varianti del nome squadra: quella completa (sempre per
    prima, ordine garantito) e una versione 'corta' togliendo prefissi/
    suffissi societari comuni - la stampa spesso usa la versione corta
    (es. 'Leverkusen' invece di 'Bayer 04 Leverkusen').
    """
    variants = [name]
    stripped = name
    for pattern in _NAME_STRIP_PATTERNS:
        new_stripped = re.sub(pattern, "", stripped).strip()
        if new_stripped and new_stripped != stripped:
            stripped = new_stripped
    if stripped and stripped != name and len(stripped) > 2:
        variants.append(stripped)
    return variants


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
    """Tra gli articoli RSS gia' scaricati, tiene quelli che nominano entrambe le squadre (con varianti, esclusi altri sport)."""
    home_variants = [v.lower() for v in name_variants(home)]
    away_variants = [v.lower() for v in name_variants(away)]
    matches = []
    for entry, lang in direct_items:
        title = entry.get("title", "").lower()
        summary = entry.get("summary", "").lower()
        text = f"{title} {summary}"
        if any(sport in text for sport in OTHER_SPORTS_EXCLUDE):
            continue
        if any(h in text for h in home_variants) and any(a in text for a in away_variants):
            matches.append((entry, lang))
    return matches


def filter_direct_items_for_text(direct_items: list, required_text: str, keyword_sets: list) -> list:
    """Tra gli articoli RSS gia' scaricati, tiene quelli che nominano required_text + una parola chiave (esclusi altri sport)."""
    required_l = required_text.lower()
    matches = []
    for entry, lang in direct_items:
        title = entry.get("title", "").lower()
        summary = entry.get("summary", "").lower()
        text = f"{title} {summary}"
        if required_l not in text:
            continue
        if any(sport in text for sport in OTHER_SPORTS_EXCLUDE):
            continue
        if any(kw.lower() in text for kw in keyword_sets):
            matches.append((entry, lang))
    return matches


def is_fixture_active(fixture: dict) -> bool:
    """
    Una partita e' 'attiva' per la ricerca mirata solo tra ACTIVE_WINDOW_DAYS
    giorni prima e STOP_BEFORE_KICKOFF_HOURS ore prima del calcio d'inizio.
    Prima non serve cercare (non esce ancora nulla), dopo non serve piu'
    (arriverebbero solo notizie ormai inutili, a ridosso o dopo la partita).
    """
    kickoff_str = fixture.get("kickoff")
    if not kickoff_str:
        return True  # nessun orario noto: meglio cercare che perdere la partita
    try:
        kickoff = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))
    except ValueError:
        return True
    now = datetime.now(timezone.utc)
    hours_to_kickoff = (kickoff - now).total_seconds() / 3600
    return STOP_BEFORE_KICKOFF_HOURS <= hours_to_kickoff <= ACTIVE_WINDOW_DAYS * 24


def classify_topic(original_title: str) -> str:
    """
    Classificazione VELOCE (prima di tradurre/chiamare Groq): controlla il
    titolo originale, in qualsiasi lingua, contro tutte le parole chiave.
    Serve solo per raggruppare i doppioni, non per la grafica (non piu'
    mostrata all'utente).
    """
    lowered = original_title.lower()
    coach_kw = [kw for kws in COACH_KEYWORDS.values() for kw in kws]
    absence_kw = [kw for kws in ABSENCE_KEYWORDS.values() for kw in kws]
    preview_kw = [kw for kws in PREVIEW_KEYWORDS.values() for kw in kws]
    press_kw = [kw for kws in PRESS_CONFERENCE_KEYWORDS.values() for kw in kws]

    if any(kw.lower() in lowered for kw in coach_kw):
        return "Cambio allenatore"
    if any(kw.lower() in lowered for kw in press_kw):
        return "Conferenza stampa"
    if any(kw.lower() in lowered for kw in absence_kw + preview_kw):
        return "Assenze e turnover"
    return "Assenze e turnover"


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
                    "max_tokens": 300,
                    "reasoning_format": "hidden",
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


_decode_cache: dict = {}


def resolve_real_url(google_link: str) -> str:
    """
    Decodifica un link 'mascherato' di Google News nell'URL reale.
    Con una cache per non rifare la stessa decodifica piu' volte nello
    stesso giro - capita spesso che lo stesso articolo esca da piu'
    combinazioni di ricerca (es. "Rennes"+"Lens" e "Stade Rennais"+"Racing Lens").
    """
    if not google_link:
        return google_link
    if google_link in _decode_cache:
        return _decode_cache[google_link]
    try:
        time.sleep(0.3)  # piccola pausa per non sovraccaricare il servizio di decodifica
        result = gnewsdecoder(google_link, interval=0)
        if result.get("status") and result.get("decoded_url"):
            _decode_cache[google_link] = result["decoded_url"]
            return result["decoded_url"]
    except Exception as e:
        print(f"[WARN] decodifica link fallita: {e}")
    _decode_cache[google_link] = google_link
    return google_link


def is_blocked_domain(url: str) -> bool:
    """Blacklist invece di whitelist: blocca solo spam/scommesse/social noti, lascia passare il resto."""
    if not url:
        return True
    domain = urlparse(url).netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return any(domain == blocked or domain.endswith("." + blocked) for blocked in BLOCKED_NEWS_DOMAINS)


def is_excluded_url(url: str) -> bool:
    """Scarta pagine automatiche (video/risultati/live-blog)."""
    lowered = url.lower()
    return any(pattern in lowered for pattern in EXCLUDED_URL_PATTERNS)


# MyMemory vuole codici lingua-paese estesi, non quelli corti (ISO 639-1)
_MYMEMORY_LANG_MAP = {
    "en": "en-GB",
    "es": "es-ES",
    "de": "de-DE",
    "fr": "fr-FR",
    "it": "it-IT",
}


def translate_to_italian(text: str, source_lang: str) -> str:
    """
    Traduce un testo in italiano. MyMemory provato per primo (Google Translate
    viene sistematicamente bloccato dagli IP condivisi di GitHub Actions).
    """
    if not text or source_lang == "it":
        return text

    mymemory_lang = _MYMEMORY_LANG_MAP.get(source_lang, source_lang)
    try:
        translated = MyMemoryTranslator(source=mymemory_lang, target="it-IT").translate(text)
        if translated and translated.strip().lower() != text.strip().lower():
            return translated
    except Exception as e:
        print(f"[WARN] MyMemory Translate fallito ({source_lang}): {e}")

    try:
        translated = GoogleTranslator(source=source_lang, target="it").translate(text)
        if translated:
            return translated
    except Exception as e:
        print(f"[WARN] Google Translate fallito ({source_lang}): {e}")

    print(f"[WARN] Traduzione non riuscita per: {text[:60]}...")
    return text


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


def build_caption(meta: dict, title: str, ai_summary: str, real_link: str, league_name: str, flag: str) -> str:
    source = site_display_name(meta.get("site_name", ""), real_link)

    lines = [f"{flag} <b>{league_name}</b>", ""]
    lines.append(f"<b>{title}</b>")

    body = ai_summary or clean_description(meta.get("description", ""))
    if body and body.lower() != title.strip().lower():
        lines.append(body)

    lines.append("")
    lines.append(f"<i>Fonte: {source}</i>")
    return "\n".join(lines)


def build_message(real_link: str, title: str, league_name: str, flag: str) -> str:
    header = f"{flag} <b>{league_name}</b>"
    return f"{header}\n{title}\n{real_link}"


def gather_coach_items(league: dict, direct_items: list) -> list:
    """Ricerca cambio allenatore per un campionato: Google News (italiano + lingua nativa) + RSS diretti."""
    items = []
    sports_excl_it = " ".join(f'-{s}' for s in ["basket", "pallacanestro", "pallamano", "rugby"])
    kw_it = " OR ".join(COACH_KEYWORDS["it"])
    query_it = f'"{league["name"]}" calcio ({kw_it}) {sports_excl_it}'
    items.extend((e, "it") for e in search_news(query_it, lang="it", country="IT"))

    if league.get("native_lang"):
        sports_excl_native = " ".join(f'-{s}' for s in OTHER_SPORTS_EXCLUDE)
        kw_native = " OR ".join(COACH_KEYWORDS[league["native_lang"]])
        query_native = f'"{league["native_name"]}" ({kw_native}) {sports_excl_native}'
        native_entries = search_news(query_native, lang=league["native_lang"], country=league["native_country"])
        items.extend((e, league["native_lang"]) for e in native_entries)

    all_coach_kw = [kw for kws in COACH_KEYWORDS.values() for kw in kws]
    items.extend(filter_direct_items_for_text(direct_items, league["name"], all_coach_kw))

    return items


def gather_fixture_items(fixture: dict, direct_items: list) -> list:
    """
    Ricerca mirata su una singola partita di oggi: conferenza stampa +
    assenze/turnover + anteprima/probabili formazioni (NIENTE formazioni
    ufficiali, tolte di proposito: l'utente le recupera altrove, meglio
    concentrare la ricerca su cio' che serve davvero al suo progetto).
    Cerca in italiano, nella lingua/stampa locale del campionato, e negli
    RSS diretti gia' scaricati.
    """
    home, away = fixture["home"], fixture["away"]
    home_variants = name_variants(home)
    away_variants = name_variants(away)
    items = []

    kw_it = " OR ".join(PRESS_CONFERENCE_KEYWORDS["it"] + ABSENCE_KEYWORDS["it"] + PREVIEW_KEYWORDS["it"])
    for h in home_variants:
        for a in away_variants:
            query_it = f'"{h}" "{a}" ({kw_it})'
            items.extend((e, "it") for e in search_news(query_it, lang="it", country="IT", max_items=8))

    native_lang = fixture.get("native_lang")
    if native_lang:
        kw_native = " OR ".join(
            PRESS_CONFERENCE_KEYWORDS[native_lang] + ABSENCE_KEYWORDS[native_lang] + PREVIEW_KEYWORDS[native_lang]
        )
        for h in home_variants:
            for a in away_variants:
                query_native = f'"{h}" "{a}" ({kw_native})'
                native_entries = search_news(query_native, lang=native_lang, country=fixture["native_country"], max_items=8)
                items.extend((e, native_lang) for e in native_entries)

    items.extend(filter_direct_items_for_fixture(direct_items, home, away))

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
    start_time = time.time()

    def time_budget_ok() -> bool:
        return (time.time() - start_time) < MAX_RUN_SECONDS

    state = load_state()
    seen = set(state.get("news_seen", []))
    new_seen = list(seen)
    any_new = False
    sent_this_run = 0
    groq_failures_this_run = 0

    sources_to_check = []

    direct_items = fetch_direct_rss_items()

    for league in LEAGUES:
        if not time_budget_ok():
            print("[INFO] Tempo massimo raggiunto durante la raccolta (cambio allenatore), continuo al prossimo giro.")
            break
        sources_to_check.append((league["name"], league["flag"], gather_coach_items(league, direct_items), league["name"]))

    all_fixtures = state.get("today_fixtures", [])
    today_fixtures = [f for f in all_fixtures if is_fixture_active(f)]
    for fixture in today_fixtures:
        if not time_budget_ok():
            print(f"[INFO] Tempo massimo raggiunto durante la raccolta partite ({len(sources_to_check)} fonti raccolte finora), continuo al prossimo giro.")
            break
        topic_base = f'{fixture["home"]}|{fixture["away"]}'
        sources_to_check.append((fixture["league"], fixture["flag"], gather_fixture_items(fixture, direct_items), topic_base))

    print(f"Partite totali in calendario: {len(all_fixtures)} — attive ora (finestra {ACTIVE_WINDOW_DAYS}gg/{STOP_BEFORE_KICKOFF_HOURS}h): {len(today_fixtures)}")

    topics_sent = state.setdefault("topics_sent", {})

    for league_name, flag, entries, topic_base in sources_to_check:
        if sent_this_run >= MAX_MESSAGES_PER_RUN:
            break
        if not time_budget_ok():
            print("[INFO] Tempo massimo raggiunto durante l'invio, mi fermo qui per questo giro.")
            break

        for item, item_lang in entries:
            if sent_this_run >= MAX_MESSAGES_PER_RUN:
                break

            google_link = item.get("link", "")
            real_link = resolve_real_url(google_link)

            if "news.google.com" in real_link:
                # decodifica fallita: non mandiamo il link grezzo illeggibile,
                # ci riproveremo al prossimo giro (la cache e' solo per questo run)
                continue

            if is_blocked_domain(real_link):
                continue
            if is_excluded_url(real_link):
                continue

            uid = f"news|{real_link}"
            if uid in seen:
                continue
            if not is_recent_enough(item):
                continue

            original_title = item.get("title", "Notizia")

            # Anti-doppioni CONTROLLATO SUBITO (prima di Groq/immagine):
            # classificazione veloce sul titolo originale, senza tradurre.
            category_label = classify_topic(original_title)
            topic_key = f"{topic_base}::{category_label}"
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

            # Da qui in poi solo notizie DAVVERO nuove: ora vale la pena
            # spendere una chiamata Groq e scaricare l'immagine.
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

            inviato_con_foto = False
            if meta.get("image"):
                caption = build_caption(meta, title, ai_summary, real_link, league_name, flag)
                inviato_con_foto = send_telegram_photo(meta["image"], caption, "🔗 Leggi l'articolo", real_link)

            if not inviato_con_foto:
                testo_fallback = build_message(real_link, title, league_name, flag)
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


if __name__ == "__main__":
    run()
