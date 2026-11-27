"""
Bot notizie calcio (versione 3): conferenze stampa e notizie generali di
tutte le squadre dei 5 campionati principali.

Come funziona un giro:
1. RACCOLTA
   - feed RSS diretti delle testate principali (letti per intero)
   - Google News: una ricerca per squadra (al massimo ogni
     TEAM_QUERY_INTERVAL_MINUTES minuti) + ricerche dedicate alle
     conferenze stampa per ogni campionato
2. FILTRI (veloci, sul titolo)
   - gia' visto / piu' vecchio di NEWS_MAX_AGE_HOURS ore
   - parole escluse (serie minori, giovanili, femminile, altri sport,
     scommesse, tv, dirette, pagelle, calciomercato...)
   - il titolo deve nominare una delle squadre seguite (o il suo allenatore)
   - niente resoconti con il risultato nel titolo, niente articoli su
     partite gia' giocate arrivati a distanza di ore/giorni
3. PRIORITA' E LIMITI: conferenze stampa > infortuni/formazioni/allenatore
   > notizie generali, con un massimo per squadra in una finestra mobile di
   ore (TEAM_CAPS: piu' alto per chi gioca entro MATCH_SOON_HOURS ore) e
   scarto delle copie della stessa notizia.
4. INVIO: link reale, immagine e data della pagina (se la pagina dice che
   l'articolo e' vecchio, si scarta), titolo e riassunto in italiano via
   Groq (con riserva di traduzione diretta), invio su Telegram con in fondo
   l'hashtag delle squadre e quello del tipo (#Inter #Juventus · #Infortuni;
   il tipo e' scritto anche in alto, accanto al campionato). Se c'e' il
   gruppo con gli Argomenti (vedi telegram_group.py) ogni notizia va
   nell'argomento del suo campionato, altrimenti nella chat privata col bot.
5. ARCHIVIO E SALUTE: ogni notizia inviata resta LOG_KEEP_HOURS ore nello
   stato ("log": squadre, tipo, titolo, indirizzo del post); i contatori del
   giorno ("stats": ricerche Google fallite, chiamate e token Groq, notizie
   per tipo...) servono a tenere d'occhio i limiti dei servizi gratuiti, e se
   qualcosa non va il bot lo scrive nella chat privata (HEALTH_* in config).

Il primo giro dopo l'aggiornamento non manda nulla: registra le notizie gia'
uscite, cosi' da quel momento arrivano solo quelle nuove (niente raffica).
"""

import hashlib
import html
import re
import threading
import time
import unicodedata
import urllib.parse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import feedparser
import requests
from deep_translator import GoogleTranslator, MyMemoryTranslator
from googlenewsdecoder import gnewsdecoder

from config import (
    BLOCKED_NEWS_DOMAINS,
    COACH_KEYWORDS,
    COACH_SURNAME_STOPLIST,
    DIRECT_RSS_FEEDS,
    DUPLICATE_SUPPRESS_HOURS,
    EXCLUDE_TITLE_WORDS,
    EXCLUDED_URL_PATTERNS,
    EXCLUDED_URL_SEGMENTS,
    GOOGLE_BREAKER_FAILS,
    GOOGLE_MAX_ITEMS,
    GOOGLE_TIMEOUT_SECONDS,
    GROQ_API_KEY,
    GROQ_GENERAL_DAILY_BUDGET,
    HASHTAGS,
    HEALTH_GAP_MINUTES,
    HEALTH_GOOGLE_FAILED_RUNS,
    HEALTH_GROQ_FAILURES,
    HEALTH_NOTICES,
    INCLUDE_TRANSFER_NEWS,
    INJURY_KEYWORDS,
    INJURY_KEYWORDS_BY_LANG,
    INJURY_NOT_KEYWORDS,
    INJURY_PLAYER_WORDS,
    LEAGUES,
    LINEUP_KEYWORDS,
    LINEUP_NOT_KEYWORDS,
    LOG_KEEP_HOURS,
    MATCH_SOON_HOURS,
    MAX_HASHTAGS,
    MAX_MESSAGES_PER_RUN,
    MAX_TYPE_LABELS,
    OFFICIAL_LINEUP_KEYWORDS,
    OTHER_SPORT_SITE_WORDS,
    NEWS_MAX_AGE_HOURS,
    POST_MATCH_HOURS,
    PRESS_KEYWORDS,
    PRESS_KEYWORDS_BY_LANG,
    PRESS_NOT_KEYWORDS,
    PRESS_QUERY_TERMS,
    QUERY_CONTEXT,
    SEEN_KEEP_DAYS,
    TEAM_CAPS,
    TEAM_HASHTAGS,
    TEAM_QUERY_INTERVAL_MINUTES,
    TEAMS,
    TRANSFER_URL_SEGMENTS,
    TRANSFER_WORDS,
    TYPE_TAGS,
)
from telegram_group import Destination
from utils import load_calendar, load_state, save_state, send_telegram_message

STATE_VERSION = 3
ROME = ZoneInfo("Europe/Rome")

# Il giro parte ogni 5 minuti e prima delle notizie controlla le quote: non
# deve durare troppo, altrimenti il controllo quote successivo slitta. Quello
# che non entra in un giro parte al successivo (aspetta in coda, non si
# sovrappone).
MAX_RUN_SECONDS = 270
PARALLEL_FETCH = 3          # ricerche/feed scaricati in parallelo
PARALLEL_RESOLVE = 4        # link decodificati / pagine lette in parallelo
PARALLEL_AI = 3             # riassunti Groq preparati in parallelo (con limite di frequenza)
HTTP_TIMEOUT = 15
PRESS_QUERY_CHUNK = 6       # squadre per ogni ricerca "conferenza stampa"
# (la pausa tra un invio e l'altro e' in config: SEND_DELAY_GROUP/PRIVATE_SECONDS)

# Groq: modelli provati in ordine. Piano gratuito: 30 richieste/minuto e
# 8000 token/minuto PER MODELLO, quindi le chiamate vengono distanziate e,
# se un modello e' al limite, si passa al successivo.
GROQ_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
# Dal 27/11/2026 il modello piu' forte e' prima di tutto per il bot quote (🔎 perche' degli avvisi): il suo tetto
# gratuito e' 200.000 token in 24 ore (finestra mobile) e le notizie ne usano al massimo questi; oltre, passano al
# modello successivo della lista. Stesse notizie, stessi riassunti: cambia solo il modello che li scrive.
GROQ_NEWS_TOKEN_CAP = {"openai/gpt-oss-120b": 150000}
GROQ_MIN_INTERVAL = 3.0

PRIORITY = {"official": 0, "press": 0, "key": 1, "general": 2}
CLASSES = ("official", "press", "key", "general")

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

GOOGLE_EDITIONS = {"it": "IT", "en": "GB", "es": "ES", "de": "DE", "fr": "FR"}

STOPWORDS = {
    "dopo", "contro", "della", "delle", "dello", "degli", "nella", "nelle", "nello", "sulla", "sulle",
    "alla", "alle", "allo", "anche", "come", "questa", "questo", "quella", "quello", "ecco", "perché",
    "sono", "stato", "stata", "essere", "tutti", "tutto", "ancora", "oggi", "domani", "with", "after",
    "from", "that", "this", "have", "will", "their", "they", "what", "when", "para", "tras", "como",
    "pero", "está", "sobre", "desde", "ante", "nach", "gegen", "nicht", "eine", "einen", "einem",
    "pour", "avec", "après", "dans", "sont", "plus", "contre", "mais", "face",
}


# =====================================================================
# Utilita' testo/date
# =====================================================================

def words_regex(words) -> re.Pattern:
    """Una sola espressione che trova una qualsiasi delle parole/frasi date (parole intere, maiuscole indifferenti)."""
    parts = sorted({w.lower() for w in words if w}, key=len, reverse=True)
    return re.compile(r"(?<!\w)(?:" + "|".join(re.escape(p) for p in parts) + r")(?!\w)", re.IGNORECASE)


def keyword_regex(words):
    """Come words_regex, ma una voce che comincia con "~" e' un'espressione regolare. None se la lista e' vuota."""
    plain = [w for w in words if w and not w.startswith("~")]
    parts = [words_regex(plain).pattern] if plain else []
    parts += [f"(?:{w[1:]})" for w in words if w.startswith("~")]
    return re.compile("|".join(parts), re.IGNORECASE) if parts else None


class Kind:
    """Riconosce un tipo di notizia dalle parole del titolo (vedi le liste XXX_KEYWORDS in config)."""

    def __init__(self, words, by_lang=None, not_words=None):
        self.any = keyword_regex(words)
        self.by_lang = {lang: keyword_regex(w) for lang, w in (by_lang or {}).items()}
        self.skip = keyword_regex(not_words or [])

    def clean(self, title: str) -> str:
        """Il titolo senza i modi di dire che ingannano ("senza dubbio", "minuti di recupero")."""
        return self.skip.sub(" ", title) if self.skip else title

    def found(self, title: str, lang: str) -> bool:
        text = self.clean(title)
        if self.any and self.any.search(text):
            return True
        rx = self.by_lang.get(lang)
        return bool(rx and rx.search(text))


EXCLUDE_RE = words_regex(EXCLUDE_TITLE_WORDS + ["serie a1", "serie a2"])
TRANSFER_RE = words_regex(TRANSFER_WORDS)
KINDS = {
    "press": Kind(PRESS_KEYWORDS, PRESS_KEYWORDS_BY_LANG, PRESS_NOT_KEYWORDS),
    "coach": Kind(COACH_KEYWORDS),
    "injury": Kind(INJURY_KEYWORDS, INJURY_KEYWORDS_BY_LANG, INJURY_NOT_KEYWORDS),
    "lineup": Kind(LINEUP_KEYWORDS, None, LINEUP_NOT_KEYWORDS),
}
OFFICIAL_RE = keyword_regex(OFFICIAL_LINEUP_KEYWORDS)
# "Bremer ko", "Bremer si ferma": parola valida solo dopo un nome che non e' una squadra
PLAYER_WORD_RE = {
    lang: re.compile(r"(?<!\w)([A-ZÀ-Þ][\w'’.-]*)\s+(?i:" + "|".join(re.escape(w) for w in words) + r")(?!\w)")
    for lang, words in INJURY_PLAYER_WORDS.items() if words
}

# Risultato nel titolo (es. "Milan-Atalanta 2-1", "Bayern 3:0") = resoconto
# di una partita gia' giocata. Non scambia per risultati i moduli (4-3-3),
# gli orari (20:45), le stagioni (2026-27) e le durate ("out 2-3 settimane").
_SCORE_RE = re.compile(
    r"(?<![\w.:/-])\d{1,2}\s?[-–]\s?\d{1,2}(?![\w/]|[-.:]\d)|(?<![\w.:/])\d\s?:\s?\d(?![\w/]|[-.:]\d)")
_DURATION_AFTER_RE = re.compile(
    r"^\s*(?:settiman|giorn|mes|partit|gar|turn|week|day|month|match|game|seman|d[ií]as?\b|partido|"
    r"woche|tag|monat|spiel|semaine|jour|mois|ore\b|hours?|minut)", re.IGNORECASE)


def has_score(title: str) -> bool:
    for m in _SCORE_RE.finditer(title):
        if _DURATION_AFTER_RE.match(title[m.end():]):
            continue
        return True
    return False


_ISO_DATE_RE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?)?\s*(Z|[+-]\d{2}:?\d{2})?")


def parse_iso_date(value: str):
    """Legge date tipo 2026-10-23T12:30:00+02:00 / ...Z / 2026-10-23 12:30. None se non riesce."""
    if not value:
        return None
    m = _ISO_DATE_RE.search(value)
    if not m:
        return None
    y, mo, d, hh, mm, ss, tz = m.groups()
    try:
        tzinfo = timezone.utc
        if tz and tz != "Z":
            sign = 1 if tz[0] == "+" else -1
            digits = tz[1:].replace(":", "")
            tzinfo = timezone(sign * timedelta(hours=int(digits[:2]), minutes=int(digits[2:4] or 0)))
        return datetime(int(y), int(mo), int(d), int(hh or 0), int(mm or 0), int(ss or 0), tzinfo=tzinfo)
    except ValueError:
        return None


def entry_published(entry):
    """Data di pubblicazione di una voce RSS (in UTC), o None se il feed non la indica."""
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            try:
                return datetime(*st[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


_URL_DATE_RES = [
    re.compile(r"/(20[2-3]\d)/(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])(?=/|$|[^\d])"),
    re.compile(r"[/_-](20[2-3]\d)-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])(?=[/_.-]|$)"),
]


def url_date(url: str):
    for rx in _URL_DATE_RES:
        m = rx.search(url)
        if m:
            try:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
            except ValueError:
                return None
    return None


_TRACKING_PARAMS = ("utm_", "ref", "fbclid", "gclid", "ocid", "cmpid", "ito", "xtor", "at_", "ns_", "rss", "src")


def normalize_url(url: str) -> str:
    """Toglie parametri di tracciamento e dettagli inutili, cosi' lo stesso articolo ha sempre la stessa chiave."""
    try:
        p = urlparse(url.strip())
        query = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)
                 if not k.lower().startswith(_TRACKING_PARAMS)]
        path = p.path.rstrip("/") or "/"
        host = p.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return urllib.parse.urlunparse(("https", host, path, "", urllib.parse.urlencode(query), ""))
    except ValueError:
        return url


def hkey(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def link_key(link: str) -> str:
    """Chiave di un link: i link Google News si usano cosi' come sono, quelli reali normalizzati."""
    if "news.google.com" in link:
        return hkey(link.strip())
    return hkey(normalize_url(link))


def domain_of(url: str) -> str:
    d = urlparse(url).netloc.lower()
    return d[4:] if d.startswith("www.") else d


def is_blocked_domain(url_or_domain: str) -> bool:
    domain = domain_of(url_or_domain) if "/" in url_or_domain else url_or_domain.lower()
    if not domain:
        return True
    return any(domain == b or domain.endswith("." + b) for b in BLOCKED_NEWS_DOMAINS)


def other_sport_site(*names) -> bool:
    """True se il sito (nome o indirizzo) e' di un altro sport: basket, volley, rugby... (OTHER_SPORT_SITE_WORDS)."""
    joined = " ".join(str(n).lower() for n in names if n)
    return any(w in joined for w in OTHER_SPORT_SITE_WORDS)


def url_problem(url: str, today_rome) -> str | None:
    """Motivo per scartare un articolo guardando solo il suo indirizzo, o None se va bene."""
    if not url or is_blocked_domain(url):
        return "sito bloccato"
    lowered = url.lower()
    if any(p in lowered for p in EXCLUDED_URL_PATTERNS):
        return "pagina automatica"
    segments = {s for s in urlparse(lowered).path.split("/") if s}
    if segments & EXCLUDED_URL_SEGMENTS:
        return "sezione esclusa"
    if not INCLUDE_TRANSFER_NEWS and segments & TRANSFER_URL_SEGMENTS:
        return "calciomercato"
    d = url_date(url)
    if d and d < today_rome - timedelta(days=1):
        return "data vecchia nell'indirizzo"
    return None


def title_tokens(title: str, ignore: set) -> set:
    words = re.findall(r"\w+", title.lower())
    return {w for w in words if len(w) > 3 and w not in ignore and w not in STOPWORDS and not w.isdigit()}


def is_similar(a: set, b: set) -> bool:
    if not a or not b:
        return False
    inter = len(a & b)
    m = min(len(a), len(b))
    if m >= 3:
        return inter / m >= 0.6
    if m == 2:
        return inter == 2 and max(len(a), len(b)) <= 6
    return False


# =====================================================================
# Squadre: riconoscimento nei titoli
# =====================================================================

_NAME_STRIP_PATTERNS = [
    r"^FC ", r"^AFC ", r"^AC ", r"^SS ", r"^SSC ", r"^US ", r"^UD ", r"^SC ", r"^CF ", r"^CA ", r"^CD ",
    r"^RC ", r"^RCD ", r"^VfL ", r"^VfB ", r"^SV ", r"^TSG ", r"^1\. FC ", r"^1\. FSV ", r"^AS ", r"^AJ ",
    r"^ES ", r"^OGC ", r" FC$", r" CF$", r" AFC$", r" AC$", r" Calcio$", r" \d{4}$", r" \d{2}$",
]


def auto_aliases(name: str, short: str) -> list:
    """Alias ricavati dal nome ufficiale, per squadre non presenti in config.TEAMS."""
    aliases = [name]
    stripped = name
    for pattern in _NAME_STRIP_PATTERNS:
        stripped = re.sub(pattern, "", stripped).strip() or stripped
    if stripped != name and len(stripped) > 3:
        aliases.append(stripped)
    if short and len(short) > 3 and short not in aliases:
        aliases.append(short)
    return aliases


def make_hashtag(text: str) -> str:
    """'Aston Villa' -> 'AstonVilla', 'Atlético' -> 'Atletico': solo lettere e numeri, senza accenti."""
    t = unicodedata.normalize("NFKD", (text or "").replace("ß", "ss"))
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    tag = "".join(p[:1].upper() + p[1:] for p in re.findall(r"[A-Za-z0-9]+", t))
    return re.sub(r"^\d+", "", tag)   # un hashtag non puo' iniziare con un numero


def _compile_alias(alias: str) -> re.Pattern:
    if alias.startswith("~"):
        return re.compile(alias[1:])
    return re.compile(r"(?<!\w)" + re.escape(alias) + r"(?!\w)")


def fold(text: str) -> str:
    """Minuscolo e senza accenti (Génésio -> genesio, Hoeneß -> hoeness)."""
    t = unicodedata.normalize("NFKD", (text or "").replace("ß", "ss"))
    return "".join(ch for ch in t if not unicodedata.combining(ch)).lower()


_SURNAME_PARTICLES = {"de", "di", "da", "del", "della", "dal", "dalla", "van", "von", "der", "den", "ten",
                      "ter", "le", "la", "du", "dos", "das", "san", "santa", "st", "mac", "mc"}
_STOPLIST_FOLDED = {fold(s) for s in COACH_SURNAME_STOPLIST}
_ACCENT_CLASSES = {
    "a": "aàáâäãåāą", "e": "eèéêëēėę", "i": "iìíîïī", "o": "oòóôöõøō", "u": "uùúûüūů", "c": "cçćč",
    "n": "nñńň", "s": "sśšş", "z": "zźżž", "y": "yýÿ", "l": "lł", "r": "rř", "g": "gğ", "d": "dđď", "t": "tť",
}


def surname_from(full: str) -> str:
    """Ultima parola del nome, con le particelle ('Daniele De Rossi' -> 'De Rossi', 'Beñat San José' -> 'San José')."""
    words = full.split()
    if not words:
        return ""
    i = len(words) - 1
    while i > 0 and words[i - 1].lower().rstrip(".") in _SURNAME_PARTICLES:
        i -= 1
    return " ".join(words[i:])


def _coach_aliases(display: str, last: str) -> list:
    """
    Nomi con cui riconoscere l'allenatore nei titoli. football-data.org a volte
    mette nel campo 'cognome' il nome intero ("Mikel Arteta", "José Mourinho"):
    il cognome va ricavato con attenzione, e un nome di battesimo da solo
    ("José", "Luis", "Antonio"...) non deve mai diventare un alias.
    """
    display = " ".join((display or "").split())
    last = " ".join((last or "").split())
    d, l = display.split(), last.split()
    out = []
    if 2 <= len(d) <= 4:
        out.append(display)
    if 2 <= len(l) <= 4 and fold(last) != fold(display):
        out.append(last)
    if len(l) == 1:
        surname = l[0]                                  # "Grosso"
    elif len(l) >= 2 and d and fold(l[0]) == fold(d[0]):
        surname = surname_from(last)                    # "Rúben Amorim" -> "Amorim"
    elif len(d) == 1:
        surname = d[0]                                  # "Fàbregas"
    elif len(l) >= 2 and fold(display).endswith(fold(last)):
        surname = last                                  # "Sanchez Flores", "De Rossi"
    elif len(d) >= 2:
        surname = surname_from(display)                 # "Pepe Bordalás" -> "Bordalás"
    else:
        surname = ""
    key = fold(surname)
    if surname and len(key.replace(" ", "")) >= 4 and key not in _STOPLIST_FOLDED \
            and all(fold(o) != key for o in out):
        out.append(surname)
    return out


def _compile_coach_alias(name: str) -> re.Pattern:
    """Come _compile_alias, ma accetta il nome con o senza accenti (Kovač/Kovac, Génésio/Genesio)."""
    parts = []
    for ch in name:
        base = fold(ch)
        if ch == "ß":
            parts.append("(?:ß|ss)")
        elif ch.isspace():
            parts.append(r"\s+")
        elif ch in "'’`":
            parts.append("['’`]")
        elif len(base) == 1 and base in _ACCENT_CLASSES:
            cls = _ACCENT_CLASSES[base]
            parts.append("[" + (cls.upper() if ch.isupper() else cls) + "]")
        else:
            parts.append(re.escape(ch))
    return re.compile(r"(?<!\w)" + "".join(parts) + r"(?!\w)")


class TeamIndex:
    """Le squadre seguite e i modi in cui i titoli le nominano."""

    def __init__(self, calendar_teams: list):
        league_info = {lg["name"]: lg for lg in LEAGUES}
        config_info = {}
        for league, teams in TEAMS.items():
            for name, info in teams.items():
                config_info[name] = (league, info)

        # Elenco squadre: da football-data.org se disponibile (sempre aggiornato
        # a inizio stagione), altrimenti quello di config.TEAMS
        by_league = {}
        for t in calendar_teams or []:
            if t.get("league") in league_info and t.get("name"):
                by_league.setdefault(t["league"], []).append(t)
        teams = []
        for league in league_info:
            if by_league.get(league):
                teams.extend(by_league[league])
            else:
                teams.extend({"name": n, "league": league} for n in TEAMS.get(league, {}))

        self.teams = {}      # nome -> dati squadra
        self.patterns = []   # (regex, squadra, lingua o None, e' allenatore?)
        self.ignore_words = {}
        for t in teams:
            name, league = t["name"], t["league"]
            lg = league_info[league]
            if name in config_info:
                info = config_info[name][1]
                aliases = list(info.get("alias", []))
            else:
                info = {}
                aliases = auto_aliases(name, t.get("shortName", ""))
            plain = [a for a in aliases if isinstance(a, str) and not a.startswith("~")]
            self.teams[name] = {
                "league": league,
                "flag": lg["flag"],
                "lang": lg["lang"],
                "country": lg["country"],
                "q": info.get("q") or (plain[0] if plain else name),
                "q_it": info.get("q_it") if lg["lang"] != "it" else None,
                # hashtag: quello scelto in config.HASHTAGS, altrimenti ricavato dal nome
                "tag": make_hashtag(HASHTAGS.get(name, "")) or make_hashtag(t.get("shortName", ""))
                       or make_hashtag(plain[0] if plain else "") or make_hashtag(name),
            }
            words = set(re.findall(r"[^\W\d_]{3,}", name.lower()))
            for a in aliases:
                text = a[1] if isinstance(a, tuple) else a
                lang = a[0] if isinstance(a, tuple) else None
                self.patterns.append((_compile_alias(text), name, lang, False))
                words |= set(re.findall(r"[^\W\d_]{3,}", text.lower()))
            for c in _coach_aliases(t.get("coach", ""), t.get("coach_last", "")):
                self.patterns.append((_compile_coach_alias(c), name, None, True))
                words |= set(re.findall(r"[^\W\d_]{3,}", c.lower()))
            self.ignore_words[name] = words

    def find(self, title: str, lang: str):
        """Squadre nominate nel titolo, in ordine di apparizione, piu' i punti in cui compaiono."""
        spans = self._find(title, lang)
        letters = [ch for ch in title if ch.isalpha()]
        if not spans and letters and sum(ch.isupper() for ch in letters) / len(letters) > 0.6:
            spans = self._find(title.title(), lang)   # titoli TUTTI MAIUSCOLI
        ordered = []
        for _, _, team, _ in spans:
            if team not in ordered:
                ordered.append(team)
        return ordered, spans

    def _find(self, title: str, lang: str):
        found = []
        for rx, team, alias_lang, is_coach in self.patterns:
            if alias_lang and alias_lang != lang:
                continue
            for m in rx.finditer(title):
                if m.end() > m.start():
                    found.append((m.end() - m.start(), m.start(), m.end(), team, is_coach))
        # i nomi piu' lunghi vincono ("Bayern Monaco" e' il Bayern, non il Monaco)
        found.sort(key=lambda x: (-x[0], x[1]))
        taken, result = [], []
        for _, s, e, team, is_coach in found:
            if any(s < te and ts < e for ts, te in taken):
                continue
            taken.append((s, e))
            result.append((s, e, team, is_coach))
        result.sort(key=lambda x: x[0])
        return result

    def ignore_for(self, teams: list) -> set:
        out = set()
        for t in teams:
            out |= self.ignore_words.get(t, set())
        return out

    def hashtags(self, teams: list) -> str:
        """'#Inter #Juventus' per le squadre nominate nel titolo (al massimo MAX_HASHTAGS)."""
        if not TEAM_HASHTAGS:
            return ""
        tags = []
        for t in teams:
            tag = self.teams.get(t, {}).get("tag")
            if tag and tag not in tags:
                tags.append(tag)
        return " ".join("#" + tag for tag in tags[:MAX_HASHTAGS])


class FixtureIndex:
    """Partite recenti e future, per riconoscere gli articoli su partite gia' giocate."""

    def __init__(self, fixtures: list):
        self.pairs = []
        for f in fixtures or []:
            ko = parse_iso_date(f.get("kickoff", ""))
            if ko and f.get("home") and f.get("away"):
                self.pairs.append((f["home"], f["away"], ko))

    def stale_reason(self, teams: set, published, now) -> str | None:
        for home, away, kickoff in self.pairs:
            if home in teams and away in teams and kickoff <= now:
                if published and published < kickoff:
                    return "anteprima di una partita gia' iniziata"
                if now - kickoff > timedelta(hours=POST_MATCH_HOURS):
                    return "partita gia' giocata"
        return None

    def official_lineup_plausible(self, teams: list, now) -> bool:
        """
        Un titolo sulle "formazioni ufficiali" e' credibile? Se nomina due squadre
        seguite, devono giocare davvero una contro l'altra adesso: altrimenti sono
        le formazioni della Primavera o della femminile. Con una squadra sola non
        si puo' verificare (coppe che non sono in calendario): si lascia passare.
        """
        if len(teams) < 2:
            return True
        named = set(teams)
        first, last = now - timedelta(hours=1.5), now + timedelta(hours=3)
        return any(home in named and away in named and first <= kickoff <= last
                   for home, away, kickoff in self.pairs)

    def playing_soon(self, now, hours: float) -> set:
        """Squadre con una partita che comincia entro 'hours' ore."""
        limit = now + timedelta(hours=hours)
        out = set()
        for home, away, kickoff in self.pairs:
            if now < kickoff <= limit:
                out.add(home)
                out.add(away)
        return out


_QUOTES = "\"'«“”‘’„‹"
_COLON_RE = re.compile(r"\s{0,2}:\s*")
_LEADS_RE = re.compile(r"(?:[,;:|•»\"“”]|\s[-–—])\s*$")
_FAR_QUOTE_RE = re.compile(r"[^:«»\"“”„]{1,40}:\s*[\"«“„]")


def coach_speaks(title: str, start: int, end: int) -> bool:
    """
    Il titolo riporta le parole dell'allenatore? Il suo nome sta in title[start:end].
    Si': "Conte: «Domani gioca...»", "Napoli, Conte: non sara' facile",
         "Sarri si giustifica con le assenze: «10 infortunati»".
    No:  "la panchina di Sarri: Kessie verso il recupero", "il post-Carrick: ...".
    """
    rest = title[end:]
    m = _COLON_RE.match(rest)
    if m and ":" in m.group(0):
        if rest[m.end():m.end() + 1] in _QUOTES and rest[m.end():]:
            return True
        # senza virgolette vale solo se il nome apre il titolo o segue una virgola/un trattino
        before = title[:start]
        return not before.strip() or bool(_LEADS_RE.search(before))
    return bool(_FAR_QUOTE_RE.match(rest))


def player_stopped(title: str, spans: list, lang: str) -> bool:
    """ "Bremer ko", "Bremer si ferma": infortunio. "Milan ko", "la Juve si ferma": no (e' una sconfitta)."""
    rx = PLAYER_WORD_RE.get(lang)
    if not rx:
        return False
    for m in rx.finditer(title):
        s, e = m.start(1), m.end(1)
        if not any(ts < e and s < te for ts, te, _, _ in spans):
            return True
    return False


def classify(title: str, spans: list, lang: str = "") -> tuple:
    """
    Tipo della notizia, dal titolo. Ritorna (classe, tipi):
    - classe: "official" (formazioni ufficiali), "press" (conferenza stampa),
      "key" (infortuni, formazioni, allenatore) o "general" (il resto):
      decide priorita' e limiti
    - tipi: quelli riconosciuti tra press, coach, injury, lineup, nell'ordine
      (diventano etichetta e hashtag: una notizia puo' averne piu' d'uno)
    """
    is_press = KINDS["press"].found(title, lang) or \
        any(is_coach and coach_speaks(title, start, end) for start, end, _, is_coach in spans)
    types = ["press"] if is_press else []
    if KINDS["coach"].found(title, lang):
        types.append("coach")
    if KINDS["injury"].found(title, lang) or player_stopped(title, spans, lang):
        types.append("injury")
    official = bool(OFFICIAL_RE and OFFICIAL_RE.search(title))
    if official or KINDS["lineup"].found(title, lang):
        types.append("lineup")
    return ("official" if official else "press" if is_press else "key" if types else "general"), types


_PREFIX_JOIN_RE = re.compile(r"\s*(?:[-–—/]|vs?\.?)\s*", re.IGNORECASE)     # "Juve-Lazio", "Juve vs Lazio"
_PREFIX_END_RE = re.compile(r"\s*(?:[,:;|.!]|\s[-–—])\s*")


def short_title(title: str, spans: list) -> str:
    """
    Il titolo senza le squadre all'inizio, per gli elenchi gia' divisi per
    squadra (le notizie sotto l'avviso quote):
    "Juventus, Bremer out" -> "Bremer out"; "Juve-Lazio, le ufficiali: ..." ->
    "Le ufficiali: ...". Gli allenatori restano ("Spalletti: «...»").
    """
    pos, found = 0, False
    for start, end, _, is_coach in sorted(spans):
        if is_coach or start < pos:
            continue
        gap = title[pos:start]
        if gap.strip() and not (found and _PREFIX_JOIN_RE.fullmatch(gap)):
            break
        pos, found = end, True
    if not found:
        return title
    m = _PREFIX_END_RE.match(title, pos)
    rest = title[m.end():].strip() if m else ""
    if len(rest) < 12:
        return title
    return rest[:1].upper() + rest[1:]


# Parole che, accanto ai nomi delle squadre, non fanno una notizia
_BARE_FILLER = {
    "contro", "gegen", "contra", "uefa", "champions", "europa", "conference", "league", "liga", "laliga",
    "ligue", "serie", "bundesliga", "premier", "sports", "enilive", "fase", "giornata", "jornada",
    "spieltag", "journée", "matchday", "fecha", "calcio", "football", "fútbol", "fussball", "fußball",
    "partido", "partita", "match", "spiel",
}
_FIXTURE_ONLY_RE = re.compile(r"^[^:,;!?\"«“]{2,60}\s(?:[-–—/]|vs?\.?)\s[^:,;!?\"«“]{2,60}$", re.IGNORECASE)


def is_bare_title(title: str, spans: list) -> bool:
    """
    Titolo fatto solo dei nomi delle squadre: "Lorient / Monaco", "SC Freiburg",
    "1. FC Nürnberg - 1. FC Köln". Sono pagine di calendario o statistiche,
    non notizie.
    """
    rest, pos = [], 0
    for start, end, _, _ in spans:
        rest.append(title[pos:start])
        pos = max(pos, end)
    rest.append(title[pos:])
    words = [w for w in re.findall(r"[^\W\d_]{3,}", " ".join(rest)) if w.lower() not in _BARE_FILLER]
    if not words:
        return True
    # "Squadra - Avversaria" e nient'altro (l'avversaria non e' tra le squadre seguite)
    return len(words) <= 2 and all(w[0].isupper() for w in words) and bool(_FIXTURE_ONLY_RE.match(title.strip()))


# =====================================================================
# Raccolta: feed RSS e Google News
# =====================================================================

_feed_error = [""]      # motivo dell'ultima richiesta fallita (per il registro)


def fetch_feed(url: str, timeout: float = HTTP_TIMEOUT):
    """Scarica un feed con timeout. Restituisce le voci, oppure None se la richiesta e' fallita."""
    try:
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=timeout)
        if resp.status_code != 200:
            _feed_error[0] = f"risposta {resp.status_code}"
            return None
        return feedparser.parse(resp.content).entries or []
    except requests.RequestException as e:
        _feed_error[0] = e.__class__.__name__
        return None


def clean_google_title(entry):
    """Google aggiunge ' - Nome testata' in fondo al titolo: lo togliamo (altrimenti '- Arsenal.com' sembrerebbe l'Arsenal)."""
    title = (entry.get("title") or "").strip()
    source = entry.get("source") or {}
    src_title = source.get("title", "") if hasattr(source, "get") else ""
    src_href = source.get("href", "") if hasattr(source, "get") else ""
    if src_title and title.endswith(" - " + src_title):
        title = title[: -len(src_title) - 3].strip()
    else:
        m = re.match(r"^(.*\S)\s+-\s+([^-]{2,60})$", title)
        if m:
            title, src_title = m.group(1).strip(), src_title or m.group(2).strip()
    return title, src_title, src_href


def collect_rss(stats: Counter) -> list:
    items = []

    def job(feed):
        url, lang = feed
        entries = fetch_feed(url)
        if not entries:
            print(f"[WARN] RSS diretto vuoto o non raggiungibile: {url}")
            return []
        out = []
        for e in entries:
            link = (e.get("link") or "").strip()
            title = html.unescape((e.get("title") or "").strip())
            if link and title:
                out.append({"title": title, "link": link, "published": entry_published(e), "lang": lang,
                            "origin": "rss", "source": domain_of(link)})
        return out

    with ThreadPoolExecutor(max_workers=PARALLEL_FETCH) as pool:
        for result in pool.map(job, DIRECT_RSS_FEEDS.items()):
            items.extend(result)
    stats["rss_items"] = len(items)
    return items


def google_url(query: str, lang: str) -> str:
    country = GOOGLE_EDITIONS.get(lang, "IT")
    return (f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}"
            f"&hl={lang}&gl={country}&ceid={country}:{lang}")


def build_google_queries(team_index: TeamIndex, state: dict, now_ts: float) -> list:
    """Ricerche da fare in questo giro: squadre 'scadute' + conferenze stampa per campionato."""
    queries = []
    queried = state.setdefault("team_queried", {})
    for name, t in team_index.teams.items():
        searches = [(t["lang"], t["q"])]
        if t["q_it"]:
            searches.append(("it", t["q_it"]))
        for lang, q in searches:
            key = f"{name}|{lang}"
            if now_ts - queried.get(key, 0) >= TEAM_QUERY_INTERVAL_MINUTES * 60 - 30:
                queries.append({"q": f'"{q}" {QUERY_CONTEXT[lang]} when:1d', "lang": lang, "key": key})
    for lg in LEAGUES:
        names = [t["q"] for t in team_index.teams.values() if t["league"] == lg["name"]]
        terms = " OR ".join(PRESS_QUERY_TERMS[lg["lang"]])
        for i in range(0, len(names), PRESS_QUERY_CHUNK):
            chunk = " OR ".join(f'"{n}"' for n in names[i:i + PRESS_QUERY_CHUNK])
            queries.append({"q": f"({terms}) ({chunk}) when:1d", "lang": lg["lang"], "key": None})
    # pulizia: squadre non piu' seguite
    valid = {f"{n}|{lang}" for n, t in team_index.teams.items() for lang in {t["lang"], "it"}}
    for k in list(queried):
        if k not in valid:
            queried.pop(k)
    return queries


def collect_google(queries: list, state: dict, now_ts: float, stats: Counter) -> list:
    queried = state.setdefault("team_queried", {})
    items = []
    lock = threading.Lock()
    tally = {"ok": 0, "fail": 0, "blocked": False}

    def job(q):
        # Interruttore: se Google sta rifiutando tutto (capita, a blocchi, dai
        # computer di GitHub) e' inutile insistere: si salta il resto del giro.
        if tally["blocked"]:
            return q, None
        entries = fetch_feed(google_url(q["q"], q["lang"]), timeout=GOOGLE_TIMEOUT_SECONDS)
        with lock:
            if entries is None:
                tally["fail"] += 1
                if (not tally["ok"] and tally["fail"] >= GOOGLE_BREAKER_FAILS) or \
                        (tally["fail"] >= 2 * GOOGLE_BREAKER_FAILS and tally["fail"] > 2 * tally["ok"]):
                    tally["blocked"] = True
            else:
                tally["ok"] += 1
        return q, entries

    failed = 0
    with ThreadPoolExecutor(max_workers=PARALLEL_FETCH) as pool:
        for q, entries in pool.map(job, queries):
            if entries is None:
                failed += 1
                continue
            if q["key"]:
                queried[q["key"]] = now_ts
            for e in entries[:GOOGLE_MAX_ITEMS]:
                link = (e.get("link") or "").strip()
                title, src_title, src_href = clean_google_title(e)
                if link and title:
                    items.append({"title": html.unescape(title), "link": link, "published": entry_published(e),
                                  "lang": q["lang"], "origin": "google",
                                  "source": domain_of(src_href) if src_href else src_title,
                                  "source_name": src_title})
    stats["google_queries"] = len(queries)
    stats["google_failed"] = failed
    stats["google_blocked"] = int(tally["blocked"])
    stats["google_items"] = len(items)
    if failed:
        why = f": {_feed_error[0]}" if _feed_error[0] else ""
        cut = " — Google rifiuta le richieste, resto del giro saltato" if tally["blocked"] else ""
        print(f"[WARN] {failed} ricerche Google News non riuscite su {len(queries)}{why}{cut} "
              f"(riprovo al prossimo giro)")
    return items


# =====================================================================
# Link reale, pagina, riassunto
# =====================================================================

_decode_lock = threading.Lock()
_decode_cache: dict = {}
_decode_error_logged = [False]


def resolve_real_url(google_link: str) -> str:
    """Decodifica il link 'mascherato' di Google News nell'indirizzo reale dell'articolo."""
    if not google_link or "news.google.com" not in google_link:
        return google_link
    with _decode_lock:
        if google_link in _decode_cache:
            return _decode_cache[google_link]
    real = google_link
    try:
        time.sleep(0.2)
        result = gnewsdecoder(google_link, interval=0)
        # le versioni recenti della libreria rispondono "success" invece di "status"
        if (result.get("status") or result.get("success")) and result.get("decoded_url"):
            real = result["decoded_url"]
        elif not _decode_error_logged[0]:
            _decode_error_logged[0] = True
            print(f"[WARN] decodifica link Google News non riuscita (riprovo al prossimo giro): {str(result)[:300]}")
    except Exception as e:
        if not _decode_error_logged[0]:
            _decode_error_logged[0] = True
            print(f"[WARN] decodifica link fallita: {e}")
    with _decode_lock:
        _decode_cache[google_link] = real
    return real


_META_TAG_RE = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
_ATTR_RE = re.compile(r'([\w:.\-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', re.DOTALL)
_JSONLD_DATE_RE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')
_META_KEYS = {
    "image": ["og:image", "og:image:url", "og:image:secure_url", "twitter:image", "twitter:image:src"],
    "description": ["og:description", "twitter:description", "description"],
    "site_name": ["og:site_name", "application-name"],
    "published": ["article:published_time", "og:article:published_time", "datepublished", "publishdate",
                  "publish-date", "pubdate", "sailthru.date", "parsely-pub-date", "dc.date.issued",
                  "dcterms.created", "article.published", "date"],
}
EMPTY_META = {"image": "", "description": "", "site_name": "", "published": None}


def parse_page_meta(page_html: str, page_url: str) -> dict:
    metas = {}
    for tag in _META_TAG_RE.findall(page_html):
        attrs = {k.lower(): (v1 or v2) for k, v1, v2 in _ATTR_RE.findall(tag)}
        key = (attrs.get("property") or attrs.get("name") or attrs.get("itemprop") or "").strip().lower()
        content = (attrs.get("content") or "").strip()
        if key and content and key not in metas:
            metas[key] = html.unescape(content)
    result = dict(EMPTY_META)
    for field in ("image", "description", "site_name"):
        for k in _META_KEYS[field]:
            if metas.get(k):
                result[field] = metas[k]
                break
    if result["image"]:
        result["image"] = urljoin(page_url, result["image"])
        if not result["image"].startswith("http"):
            result["image"] = ""
    for k in _META_KEYS["published"]:
        d = parse_iso_date(metas.get(k, ""))
        if d:
            result["published"] = d
            break
    if not result["published"]:
        m = _JSONLD_DATE_RE.search(page_html)
        if m:
            result["published"] = parse_iso_date(m.group(1))
    return result


def fetch_article_meta(url: str) -> dict:
    """Scarica la pagina e ne legge immagine, descrizione, nome del sito e data di pubblicazione."""
    try:
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=10)
        if resp.status_code != 200:
            return dict(EMPTY_META)
        return parse_page_meta(resp.text[:250000], resp.url or url)
    except requests.RequestException:
        return dict(EMPTY_META)


_groq_lock = threading.Lock()
_stats_lock = threading.Lock()
_groq_next = [0.0]
_groq_cooldown: dict = {}
_tok_24h: dict = {}         # token Groq usati dalle notizie nelle ultime 24 ore, per modello (a inizio giro)
_TITLE_RE = re.compile(r"\**\s*TITOLO\s*\**\s*:\s*\**\s*(.+)", re.IGNORECASE)
_SUMMARY_RE = re.compile(r"\**\s*RIASSUNTO\s*\**\s*:\s*\**\s*(.+)", re.IGNORECASE | re.DOTALL)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
# Frasi con cui un modello dice che non puo' rispondere (prima finivano pubblicate come titolo)
_REFUSAL_RE = re.compile(
    r"impossibil|non (?:posso|riesco|è possibile|e' possibile|sono in grado)|testo (?:originale )?"
    r"(?:non )?(?:fornito|disponibile|mancante)|nessun[ao]? (?:testo|descrizione)|mi dispiace|"
    r"\bsorry\b|\bcannot\b|can't|non ho (?:accesso|informazioni)|fornisci|fornire", re.IGNORECASE)


def _groq_wait_turn():
    with _groq_lock:
        wait = _groq_next[0] - time.time()
        if wait > 0:
            time.sleep(wait)
        _groq_next[0] = time.time() + GROQ_MIN_INTERVAL


def _model_params(model: str) -> dict:
    if model.startswith("openai/gpt-oss"):
        return {"reasoning_effort": "low", "include_reasoning": False}
    if model.startswith("qwen/"):
        return {"reasoning_format": "hidden"}
    return {}


def summarize_with_ai(title: str, description: str, source_lang: str, stats: Counter):
    """Titolo in italiano + breve riassunto naturale, via Groq (gratuito). None se non riesce."""
    if not GROQ_API_KEY:
        return None
    prompt = (
        f"Lingua originale: {source_lang}\n"
        f"Titolo originale: {title}\n"
        f"Descrizione originale: {description or '(assente)'}\n\n"
        "Rispondi SOLO in questo formato, in italiano fluente e naturale:\n"
        "TITOLO: <titolo in italiano, una riga>\n"
        "RIASSUNTO: <2-3 frasi che raccontano la notizia come farebbe un canale sportivo>\n\n"
        "Regole: usa solo i fatti presenti nel titolo e nella descrizione, non inventare nulla. "
        "Se la descrizione e' assente, scrivi un riassunto di una sola frase basato sul titolo. "
        "Non scrivere mai che il testo manca o che non puoi rispondere."
    )
    for model in GROQ_MODELS:
        if _groq_cooldown.get(model, 0) > time.time():
            continue
        cap = GROQ_NEWS_TOKEN_CAP.get(model)
        if cap and _tok_24h.get(model, 0) + stats["tok:" + model] >= cap:
            continue                # il resto di questo modello e' per il bot quote: si usa il successivo
        _groq_wait_turn()
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
                    "max_completion_tokens": 800,
                    **_model_params(model),
                },
                timeout=30,
            )
        except requests.RequestException as e:
            print(f"[WARN] chiamata Groq ({model}) fallita: {e}")
            continue
        with _stats_lock:
            stats["groq_calls"] += 1
        if resp.status_code == 429:
            try:
                retry = float(resp.headers.get("retry-after", "30"))
            except ValueError:
                retry = 30.0
            _groq_cooldown[model] = time.time() + min(max(retry, 5.0), 600.0)
            with _stats_lock:
                stats["groq_429"] += 1
            continue
        if resp.status_code in (400, 404):
            # modello ritirato o parametro non supportato: non riprovarlo in questo giro
            _groq_cooldown[model] = time.time() + 3600
            print(f"[WARN] Groq ({model}) ha risposto {resp.status_code}: {resp.text[:200]}")
            continue
        if resp.status_code != 200:
            print(f"[WARN] Groq ({model}) ha risposto {resp.status_code}: {resp.text[:200]}")
            continue
        try:
            data = resp.json()
            choice = data["choices"][0]
        except (ValueError, KeyError, IndexError, TypeError):
            continue
        used = (data.get("usage") or {}).get("total_tokens")
        if isinstance(used, int):
            with _stats_lock:
                stats["tok:" + model] += used     # consumo del giorno: tetto gratuito 200.000 per modello
        content = _THINK_RE.sub("", choice.get("message", {}).get("content") or "")
        title_match = _TITLE_RE.search(content)
        summary_match = _SUMMARY_RE.search(content)
        if not title_match:
            snippet = content[:150].replace("\n", " ") or "(vuota)"
            print(f"[WARN] Groq ({model}): risposta senza il formato atteso "
                  f"(finish_reason={choice.get('finish_reason')}, testo: {snippet})")
            continue
        ai_title = title_match.group(1).strip().strip("*").strip()
        ai_summary = summary_match.group(1).strip().strip("*").strip() if summary_match else ""
        if not ai_title or _REFUSAL_RE.search(ai_title):
            print(f"[WARN] Groq ({model}): titolo non valido ({ai_title[:80]}), provo il modello successivo")
            continue
        if _REFUSAL_RE.search(ai_summary):
            ai_summary = ""
        return {"title": ai_title[:250], "summary": ai_summary[:700]}
    return None


_MYMEMORY_LANG_MAP = {"en": "en-GB", "es": "es-ES", "de": "de-DE", "fr": "fr-FR", "it": "it-IT"}


def translate_to_italian(text: str, source_lang: str) -> str:
    """Traduzione di riserva (se Groq non risponde): prima MyMemory, poi Google Translate."""
    if not text or source_lang == "it":
        return text
    try:
        translated = MyMemoryTranslator(source=_MYMEMORY_LANG_MAP.get(source_lang, source_lang),
                                        target="it-IT").translate(text)
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
    return text


def clean_description(text: str, max_chars: int = 280) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "…"
    return text


def build_caption(meta: dict, title: str, summary: str, url: str, league_name: str, flag: str,
                  hashtags: str = "", types=()) -> str:
    """
    Didascalia: bandierina + campionato (+ tipo di notizia), titolo in grassetto,
    riassunto, fonte, hashtag delle squadre e del tipo.
    """
    source = meta.get("site_name") or domain_of(url)
    body = summary or clean_description(meta.get("description", ""))
    if body and body.strip().lower() == title.strip().lower():
        body = ""
    esc = lambda text: html.escape(text, quote=False)
    known = [t for t in types if t in TYPE_TAGS]
    head = f"{flag} <b>{esc(league_name)}</b>"
    if known:
        head += " · " + " · ".join(f"{TYPE_TAGS[t][0]} {TYPE_TAGS[t][1]}" for t in known[:MAX_TYPE_LABELS])
    head += f"\n\n<b>{esc(title)}</b>"
    tail = f"\n\n<i>Fonte: {esc(source)}</i>"
    tags = " · ".join(t for t in (hashtags, " ".join("#" + TYPE_TAGS[t][1] for t in known)) if t)
    if tags:
        tail += f"\n{esc(tags)}"
    if body:
        room = 1000 - len(head) - len(tail) - 2
        if len(body) > room:
            body = body[:max(room - 1, 0)].rsplit(" ", 1)[0] + "…"
        if body:
            return f"{head}\n{esc(body)}{tail}"
    return head + tail


# =====================================================================
# Stato
# =====================================================================

STATS_HISTORY_DAYS = 14     # contatori dei giorni passati tenuti nello stato


def fresh_state() -> dict:
    return {"version": STATE_VERSION, "seen": {}, "recent": [], "log": [], "team_queried": {},
            "stats": {}, "health": {}}


def prune_state(state: dict, now: datetime, today: str) -> None:
    now_ts = now.timestamp()
    keep_after = now_ts - SEEN_KEEP_DAYS * 86400
    state["seen"] = {k: v for k, v in state.get("seen", {}).items() if v >= keep_after}
    cutoff = now - timedelta(hours=DUPLICATE_SUPPRESS_HOURS)
    state["recent"] = [r for r in state.get("recent", [])
                       if (parse_iso_date(r.get("ts", "")) or cutoff - timedelta(seconds=1)) >= cutoff]
    # registro delle notizie inviate (limiti a finestra mobile, ultime notizie di una squadra)
    log_after = now_ts - LOG_KEEP_HOURS * 3600
    state["log"] = [e for e in state.get("log", []) if isinstance(e, dict) and e.get("t", 0) >= log_after]
    state.pop("caps", None)     # vecchio limite "al giorno", sostituito dalla finestra mobile
    # chiamate a Groq ora per ora (ultime 24 ore), per il tetto delle notizie generali
    hour = int(now_ts // 3600)
    hours = state.get("groq_hours") if isinstance(state.get("groq_hours"), dict) else {}
    state["groq_hours"] = {h: n for h, n in hours.items() if str(h).isdigit() and hour - int(h) < 24}
    # token Groq ora per ora per modello (ultime 24 ore), per il tetto delle notizie sul modello del bot quote.
    # Primo giro: il consumo di oggi conta come se fosse di adesso (prudente: libera il modello prima per le quote)
    toks = state.get("groq_tok_hours")
    if not isinstance(toks, dict):
        today_tok = ((state.get("stats") or {}).get("tok") or {}) if isinstance(state.get("stats"), dict) else {}
        toks = {str(hour): {m: n for m, n in today_tok.items() if isinstance(n, int)}}
    state["groq_tok_hours"] = {h: v for h, v in toks.items()
                               if str(h).isdigit() and hour - int(h) < 24 and isinstance(v, dict)}
    _tok_24h.clear()
    for bucket in state["groq_tok_hours"].values():
        for model, n in bucket.items():
            _tok_24h[model] = _tok_24h.get(model, 0) + (n if isinstance(n, int) else 0)
    # contatori del giorno: a mezzanotte quelli di ieri passano nello storico
    stats = state.get("stats") if isinstance(state.get("stats"), dict) else {}
    if stats.get("day") != today:
        if stats.get("day"):
            history = state.setdefault("stats_hist", [])
            history.append(stats)
            del history[:-STATS_HISTORY_DAYS]
        stats = {"day": today}
    state["stats"] = stats
    if not isinstance(state.get("health"), dict):
        state["health"] = {}


def notify_owner(dest, health: dict, kind: str, today: str, text: str) -> None:
    """Avviso di salute nella chat privata col bot: al massimo uno al giorno per tipo."""
    notified = health.setdefault("notified", {})
    if notified.get(kind) == today:
        return
    print(f"[SALUTE] {kind}: {re.sub(r'<[^>]+>', '', text).splitlines()[0]}")
    if not HEALTH_NOTICES or not dest.private_chat:
        notified[kind] = today
        return
    if send_telegram_message(text, disable_preview=True, chat_id=dest.private_chat):
        notified[kind] = today


# =====================================================================
# Giro principale
# =====================================================================

def run():
    start = time.time()

    def budget_ok(margin: float = 0) -> bool:
        return time.time() - start < MAX_RUN_SECONDS - margin

    now = datetime.now(timezone.utc)
    now_ts = now.timestamp()
    today_rome = now.astimezone(ROME).date()
    today = today_rome.isoformat()

    state = load_state()
    first_run = state.get("version") != STATE_VERSION
    if first_run:
        telegram_cfg = state.get("telegram")   # il collegamento al gruppo non va perso
        state = fresh_state()
        if isinstance(telegram_cfg, dict):
            state["telegram"] = telegram_cfg
    prune_state(state, now, today)
    seen = state["seen"]
    log = state["log"]
    day_stats = state["stats"]
    health = state["health"]
    stats = Counter()

    # Dove vanno le notizie: argomenti del gruppo, o chat privata (vedi telegram_group.py)
    dest = Destination(state)
    dest.prepare()

    # Il giro precedente e' troppo lontano? Di solito parte ogni 5 minuti: se e'
    # rimasto fermo a lungo, il timer esterno (cron-job.org) non sta funzionando.
    last_run = health.get("last_run")
    health["last_run"] = int(now_ts)
    if not first_run and last_run and now_ts - last_run >= HEALTH_GAP_MINUTES * 60:
        gap = int((now_ts - last_run) // 60)
        was = datetime.fromtimestamp(last_run, ROME).strftime("%H:%M")
        notify_owner(dest, health, "gap", today, (
            f"⏱ <b>Bot notizie fermo per {gap} minuti</b>\n\n"
            f"L'ultimo giro prima di questo era alle {was}. Di solito parte ogni 5 minuti.\n"
            "Se succede spesso, guarda la cronologia del cronjob su cron-job.org: il codice 401 "
            "vuol dire che il token di GitHub e' scaduto e va rifatto (e incollato di nuovo "
            "nell'intestazione Authorization)."))

    def mark_seen(*links):
        for link in links:
            if link:
                seen[link_key(link)] = int(now_ts)

    def is_seen(link: str) -> bool:
        return link_key(link) in seen

    calendar = load_calendar()
    team_index = TeamIndex(calendar.get("teams", []))
    fixtures = FixtureIndex(calendar.get("fixtures", []))
    teams_soon = fixtures.playing_soon(now, MATCH_SOON_HOURS) & set(team_index.teams)
    print(f"Squadre seguite: {len(team_index.teams)} · partite in calendario (ultimi giorni + prossimi): "
          f"{len(fixtures.pairs)} · squadre che giocano entro {MATCH_SOON_HOURS} ore: {len(teams_soon)}")

    # ---------------- 1. Raccolta ----------------
    raw = collect_rss(stats)
    queries = build_google_queries(team_index, state, now_ts)
    raw += collect_google(queries, state, now_ts, stats)
    print(f"Raccolti {stats['rss_items']} articoli da {len(DIRECT_RSS_FEEDS)} feed RSS e "
          f"{stats['google_items']} risultati da {stats['google_queries']} ricerche Google "
          f"in {time.time() - start:.0f}s")

    since = now - timedelta(hours=NEWS_MAX_AGE_HOURS)
    news_since = parse_iso_date(state.get("news_since", ""))
    if news_since and news_since > since:
        since = news_since

    # ---------------- 2. Filtri veloci ----------------
    candidates = []
    links_done = set()
    for it in raw:
        link = it["link"]
        if link in links_done:
            continue
        links_done.add(link)
        stats["trovati"] += 1
        if is_seen(link):
            stats["gia_visti"] += 1
            continue
        pub = it["published"]
        if pub and pub > now + timedelta(hours=1):
            pub = None   # data nel futuro: non affidabile, decide la data della pagina
        if pub and pub < since:
            stats["vecchi"] += 1
            continue
        title = it["title"]
        if EXCLUDE_RE.search(title):
            stats["esclusi"] += 1
            continue
        if it["origin"] == "rss" and url_problem(link, today_rome):
            stats["esclusi"] += 1
            continue
        if it["origin"] == "google" and it["source"] and \
                (is_blocked_domain(it["source"]) or other_sport_site(it["source"], it.get("source_name"))):
            stats["esclusi"] += 1
            continue
        teams, spans = team_index.find(title, it["lang"])
        if not teams:
            stats["altre_squadre"] += 1
            continue
        if has_score(title) or fixtures.stale_reason(set(teams), pub, now):
            stats["dopo_partita"] += 1
            continue
        category, types = classify(title, spans, it["lang"])
        if category == "official" and not fixtures.official_lineup_plausible(teams, now):
            category = "key"    # "ufficiali" di una partita che in calendario non c'e': limiti normali
        # mercato e titoli fatti solo dei nomi delle squadre: fuori, ma solo se la
        # notizia non e' una conferenza o un aggiornamento su infortuni/formazioni
        if not types and ((not INCLUDE_TRANSFER_NEWS and TRANSFER_RE.search(title)) or is_bare_title(title, spans)):
            stats["esclusi"] += 1
            continue
        it.update(published=pub, teams=teams, category=category, types=types)
        candidates.append(it)

    # Primo giro della nuova versione: registra tutto, non manda nulla
    if first_run:
        for c in candidates:
            mark_seen(c["link"])
        state["news_since"] = now.isoformat()
        save_state(state)
        print(f"PRIMO AVVIO della nuova versione: registrate {len(candidates)} notizie gia' uscite senza "
              f"inviarle. Da ora arrivano solo le notizie nuove.")
        return

    # ---------------- 3. Priorita', limiti per squadra, doppioni ----------------
    # Limite a finestra mobile: quante notizie di quella classe ha gia' avuto la
    # squadra nelle ultime ore (dal registro degli invii), piu' quelle scelte ora.
    sent_times = {}
    for e in log:
        if e.get("tm"):
            sent_times.setdefault((e["tm"][0], e.get("c")), []).append(e.get("t", 0))
    pending = Counter()

    def over_cap(team: str, category: str) -> bool:
        max_n, hours = TEAM_CAPS[category]["match" if team in teams_soon else "normal"]
        since_ts = now_ts - hours * 3600
        already = sum(1 for t in sent_times.get((team, category), ()) if t >= since_ts)
        return already + pending[(team, category)] >= max_n

    def already_out(c, token_sets, pool) -> bool:
        """Una notizia molto simile sulla stessa squadra e' gia' uscita (o e' gia' scelta in questo giro)?"""
        official = c["category"] == "official"
        teams = set(c["teams"])
        for r in pool:
            if official and not r.get("o"):
                continue    # le formazioni ufficiali non sono un doppione delle "probabili" di prima
            if teams & set(r["teams"]) and any(is_similar(tokens, set(r["tokens"])) for tokens in token_sets):
                return True
        return False

    def remember(pool, c, tokens, ts=None) -> None:
        entry = {"teams": c["teams"], "tokens": sorted(tokens)}
        if ts:
            entry["ts"] = ts
        if c["category"] == "official":
            entry["o"] = 1
        pool.append(entry)

    candidates.sort(key=lambda c: (PRIORITY[c["category"]], -(c["published"] or now).timestamp()))
    recent = state["recent"]
    run_recent = list(recent)
    selected = []
    for c in candidates:
        if len(selected) >= MAX_MESSAGES_PER_RUN:
            stats["rimandati"] += 1
            continue   # non segnato come visto: riprova al prossimo giro
        team = c["teams"][0]
        cap_key = (team, c["category"])
        if over_cap(team, c["category"]):
            mark_seen(c["link"])
            stats["limite_squadra"] += 1
            stats["cap:" + c["category"]] += 1
            continue
        c["ignore"] = team_index.ignore_for(c["teams"])
        c["tokens"] = title_tokens(c["title"], c["ignore"])
        if already_out(c, [c["tokens"]], run_recent):
            mark_seen(c["link"])
            stats["doppioni"] += 1
            continue
        pending[cap_key] += 1
        remember(run_recent, c, c["tokens"])
        c["cap_key"] = cap_key
        selected.append(c)

    # ---------------- 4a. Link reale e pagina (in parallelo) ----------------
    page_cutoff = since - timedelta(hours=2)   # 2 ore di tolleranza sui fusi orari dei siti

    def resolve(c):
        if not budget_ok(margin=120):
            return "tempo", c
        url = resolve_real_url(c["link"]) if c["origin"] == "google" else c["link"]
        if "news.google.com" in url:
            return "decodifica", c
        c["url"] = url
        if url_problem(url, today_rome):
            return "url", c
        if c["origin"] == "google" and is_seen(url):
            return "visto", c
        meta = fetch_article_meta(url)
        if meta["published"] and meta["published"] < page_cutoff:
            return "pagina_vecchia", c
        if other_sport_site(domain_of(url), meta.get("site_name")):
            return "url", c         # sito di basket, volley...: non e' calcio
        c["meta"] = meta
        return "ok", c

    ready = []
    with ThreadPoolExecutor(max_workers=PARALLEL_RESOLVE) as pool:
        for status, c in pool.map(resolve, selected):
            if status == "ok":
                ready.append(c)
            elif status == "tempo":
                stats["rimandati"] += 1
            elif status == "decodifica":
                stats["non_decodificati"] += 1
            else:
                mark_seen(c["link"], c.get("url"))
                if status == "visto":
                    stats["gia_visti"] += 1
                elif status == "pagina_vecchia":
                    stats["vecchi"] += 1
                else:
                    stats["esclusi"] += 1

    # ---------------- 4b. Titolo e riassunto in italiano (Groq) ----------------
    # I riassunti si preparano in parallelo e ogni notizia parte appena e'
    # pronta (sempre in ordine cronologico): nel gruppo Telegram accetta un
    # messaggio ogni ~3 secondi, cosi' quell'attesa non si somma a quella di Groq.
    groq_before = sum(state["groq_hours"].values())     # chiamate delle ultime 24 ore

    def prepare(c):
        if not budget_ok(margin=60):
            return c, "tempo"
        meta = c["meta"]
        use_ai = bool(GROQ_API_KEY)
        # Tetto gratuito di Groq: superata la soglia nelle ultime 24 ore, le notizie
        # generali lasciano i riassunti a conferenze, infortuni e formazioni.
        if use_ai and c["category"] == "general" and \
                groq_before + stats["groq_calls"] >= GROQ_GENERAL_DAILY_BUDGET:
            if c["lang"] != "it":
                return c, "tetto"       # estera: senza Groq non si traduce bene, si salta
            use_ai = False
            with _stats_lock:
                stats["senza_groq"] += 1
        ai = summarize_with_ai(c["title"], meta.get("description", ""), c["lang"], stats) if use_ai else None
        if ai:
            c["it_title"], c["summary"] = ai["title"], ai["summary"]
        else:
            if use_ai:
                with _stats_lock:
                    stats["groq_falliti"] += 1
            c["it_title"] = translate_to_italian(c["title"], c["lang"])
            c["summary"] = ""
            if meta.get("description") and c["lang"] != "it":
                meta["description"] = translate_to_italian(meta["description"], c["lang"])
        return c, "ok"

    # ---------------- 5. Invio ----------------
    def deliver(c):
        if not budget_ok():
            stats["rimandati"] += 1
            return
        # il titolo in italiano scritto da Groq a volte rivela cio' che l'originale
        # non diceva (es. "mercato" in un articolo spagnolo): stessi filtri del titolo
        if EXCLUDE_RE.search(c["it_title"]) or \
                (not INCLUDE_TRANSFER_NEWS and not c["types"] and TRANSFER_RE.search(c["it_title"])):
            mark_seen(c["link"], c["url"])
            stats["esclusi"] += 1
            return
        # stessa notizia gia' inviata in questo giro o uscita in un'altra lingua
        # (confronto anche sul titolo tradotto in italiano)
        tokens_it = title_tokens(c["it_title"], c["ignore"])
        if already_out(c, [tokens_it, c["tokens"]], recent):
            mark_seen(c["link"], c["url"])
            stats["doppioni"] += 1
            return
        info = team_index.teams[c["teams"][0]]
        meta = c["meta"]
        caption = build_caption(meta, c["it_title"], c["summary"], c["url"], info["league"], info["flag"],
                                team_index.hashtags(c["teams"]), c["types"])
        if not dest.send(info["league"], caption, meta.get("image", ""), "🔗 Leggi l'articolo", c["url"]):
            stats["invio_fallito"] += 1
            return   # non segnato: riprova al prossimo giro
        where = "argomento del gruppo" if dest.in_group else "chat privata"
        mark_seen(c["link"], c["url"])
        ts = now.isoformat()
        remember(recent, c, c["tokens"], ts)
        if tokens_it != c["tokens"]:
            remember(recent, c, tokens_it, ts)
        # registro degli invii: serve ai limiti e alle notizie sotto l'avviso quote
        # (monitor_quote.py: le ultime notizie delle due squadre, con il link al post)
        entry = {"t": int(time.time()), "tm": c["teams"], "c": c["category"], "y": c["types"],
                 "ti": c["it_title"][:140], "s": (meta.get("site_name") or domain_of(c["url"]))[:40]}
        short = short_title(c["it_title"], team_index.find(c["it_title"], "it")[1])
        if short != c["it_title"]:
            entry["tc"] = short[:140]                   # titolo senza la squadra davanti
        if dest.last_message_id and dest.last_thread_id:
            entry["m"], entry["th"] = dest.last_message_id, dest.last_thread_id     # post nel gruppo
        else:
            entry["u"] = c["url"]                       # chat privata: niente link al post, quello all'articolo
        log.append(entry)
        stats["inviati"] += 1
        stats["sent:" + c["category"]] += 1
        print(f"  INVIATA [{info['league']} · {c['teams'][0]} · {c['category']} → {where}] {c['title'][:110]}")
        time.sleep(dest.send_delay)

    ready.sort(key=lambda c: (c["published"] or now))   # invio in ordine cronologico
    with ThreadPoolExecutor(max_workers=PARALLEL_AI) as pool:
        for c, status in pool.map(prepare, ready):
            if status == "ok":
                deliver(c)
            elif status == "tetto":
                mark_seen(c["link"], c["url"])
                stats["saltate_tetto"] += 1
            else:
                stats["rimandati"] += 1

    # ---------------- 6. Contatori del giorno e controlli di salute ----------------
    def add(key: str, amount: int) -> None:
        if amount:
            day_stats[key] = day_stats.get(key, 0) + amount

    add("runs", 1)
    add("sent", stats["inviati"])
    if stats["groq_calls"]:
        hour = str(int(now_ts // 3600))
        state["groq_hours"][hour] = state["groq_hours"].get(hour, 0) + stats["groq_calls"]
    for category in CLASSES:
        add("sent_" + category, stats["sent:" + category])
        add("capped_" + category, stats["cap:" + category])
    add("dups", stats["doppioni"])
    add("undecoded", stats["non_decodificati"])
    add("tg_fail", stats["invio_fallito"])
    add("photo_up", dest.photo_uploads)
    add("g_q", stats["google_queries"])
    add("g_fail", stats["google_failed"])
    add("g_blocked", stats["google_blocked"])
    add("groq_calls", stats["groq_calls"])
    add("groq_429", stats["groq_429"])
    add("groq_failures", stats["groq_falliti"])
    add("no_ai", stats["senza_groq"])
    add("skipped_budget", stats["saltate_tetto"])
    tokens = day_stats.setdefault("tok", {})
    run_tok = {key[4:]: value for key, value in stats.items() if key.startswith("tok:") and value}
    for model, value in run_tok.items():
        tokens[model] = tokens.get(model, 0) + value
    if run_tok:                 # e ora per ora, per il tetto delle notizie sul modello del bot quote
        bucket = state["groq_tok_hours"].setdefault(str(int(now_ts // 3600)), {})
        for model, value in run_tok.items():
            bucket[model] = bucket.get(model, 0) + value
    day_stats.setdefault("sent", 0)
    day_stats.setdefault("groq_failures", 0)

    if stats["google_queries"]:
        all_failed = stats["google_failed"] >= stats["google_queries"]
        health["g_streak"] = health.get("g_streak", 0) + 1 if all_failed else 0
        if health["g_streak"] >= HEALTH_GOOGLE_FAILED_RUNS:
            notify_owner(dest, health, "google", today, (
                "⚠️ <b>Google News non risponde</b>\n\n"
                f"Da {health['g_streak']} giri di fila le ricerche del bot su Google News falliscono tutte. "
                "Le notizie dai feed diretti delle testate continuano ad arrivare e il bot riprova a ogni giro. "
                "Di solito si sblocca da solo; se dura piu' di un giorno va controllato."))
    if day_stats["groq_failures"] >= HEALTH_GROQ_FAILURES:
        notify_owner(dest, health, "groq", today, (
            "⚠️ <b>Riassunti non riusciti</b>\n\n"
            f"Oggi {day_stats['groq_failures']} riassunti non sono riusciti: probabilmente e' finito il tetto "
            "gratuito giornaliero di Groq. Le notizie continuano ad arrivare, ma senza riassunto "
            "(testo del sito o traduzione automatica) fino a domani."))

    save_state(state)
    print(
        f"Riepilogo: {stats['trovati']} articoli trovati → {stats['gia_visti']} gia' visti, "
        f"{stats['vecchi']} troppo vecchi, {stats['esclusi']} esclusi (serie minori/altri sport/live/"
        f"scommesse/mercato), {stats['altre_squadre']} non riguardano le squadre seguite, "
        f"{stats['dopo_partita']} su partite gia' giocate, {stats['limite_squadra']} oltre il limite "
        f"per squadra, {stats['doppioni']} doppioni, {stats['non_decodificati']} link non decodificati, "
        f"{stats['rimandati']} rimandati, {stats['saltate_tetto']} estere saltate per il tetto Groq, "
        f"{stats['invio_fallito']} invii non riusciti → "
        f"{stats['inviati']} inviati in {dest.describe()} "
        f"(oggi in tutto: {day_stats['sent']}; riassunti Groq falliti: {stats['groq_falliti']}, "
        f"limiti Groq raggiunti: {stats['groq_429']}) in {time.time() - start:.0f}s"
    )
    print(
        f"Oggi finora: formazioni ufficiali {day_stats.get('sent_official', 0)}, conferenze "
        f"{day_stats.get('sent_press', 0)}, infortuni/formazioni/allenatore {day_stats.get('sent_key', 0)}, "
        f"generali {day_stats.get('sent_general', 0)} · Groq: {sum(state['groq_hours'].values())} chiamate "
        f"nelle ultime 24 ore (tetto per le generali {GROQ_GENERAL_DAILY_BUDGET}), token di oggi per modello "
        f"{day_stats.get('tok', {})}, nelle 24 ore prima di questo giro {dict(_tok_24h)} (tetto notizie "
        f"{GROQ_NEWS_TOKEN_CAP}) · Google: {day_stats.get('g_fail', 0)} ricerche fallite su "
        f"{day_stats.get('g_q', 0)}"
    )


if __name__ == "__main__":
    run()
