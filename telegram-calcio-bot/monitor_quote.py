"""
Bot QUOTE: come si muovono le quote dei 5 campionati e delle coppe europee (OddsPapi, piano gratuito).

COSA FA
- Alle 19 manda il RIEPILOGO delle partite di domani (un messaggio per
  campionato o coppa): per ogni partita una riga di quote con le frecce del movimento,
  il giudizio con la FORZA del segnale (1-10) e un pronostico ricavato solo
  dall'andamento delle quote, con la probabilita' e la quota giusta.
- 40 minuti prima di ogni orario d'inizio (le formazioni ufficiali escono circa
  un'ora prima) legge lo STORICO delle quote di ogni partita su 3 book
  (Pinnacle, Sbobet, Singbet) e confronta:
      APERTURA = le quote del venerdi' alle 15:00 per le partite del weekend
                 (venerdi'-lunedi'), del martedi' alle 15:00 per i turni
                 infrasettimanali: lo stesso momento delle quote di apertura
                 usate nello studio del foglio Mercato del Pace Index;
      ADESSO   = le quote a ridosso, con le formazioni uscite.
- Ogni movimento (handicap asiatico, linea gol, Goal/No Goal) ha una FORZA da
  1 a 10 = quanto si e' mosso (1-5) + quanti book sono d'accordo (0-2) + se ha
  tenuto o e' tornato indietro (0-2) + se un altro mercato dice la stessa cosa
  (0-1). Ti scrive SOLO da FORZA_MIN_AVVISO (4/10) in su: 7-10 forte, 4-6
  medio (da farsi domande), sotto 4 rumore.
- Il messaggio: tabellina apertura/adesso (Pinnacle), ANDAMENTO della quota in
  barre (e ↩️ se e' tornata indietro di almeno un quinto dal suo punto estremo),
  SQUADRE (corner, gol e tiri in porta di ogni squadra), CONFERME degli altri
  book, QUANDO si e' mosso
  (chi per primo, cosa e' cambiato dopo le formazioni), LETTURA (cosa puo'
  voler dire, come domanda), colore per la riga "Mercato" della Direzione
  generale e pronostico dalle quote con la quota giusta (senza margine).
- La legenda la manda la prima volta e quando cambia (LEGEND_VERSION).
- Il venerdi' alle 15 (e il martedi', se c'e' il turno infrasettimanale)
  aggiorna l'elenco delle partite e te lo dice con un messaggio breve.
- COPPE (Champions, Europa e Conference League): le partite arrivano
  dall'elenco OddsPapi, letto il LUNEDI' alle 15 (una chiamata, a parte da
  quella dei campionati). Il lunedi' alle 15 e' anche la loro APERTURA (dopo il
  turno di campionato). Tutte le partite, tranne a luglio e agosto
  (preliminari): li' solo quelle con almeno una squadra dei 5 campionati
  (CUPS_ONLY_TOP5 / CUPS_TOP5_MONTHS). Le squadre dei 5 campionati hanno gli
  stessi nomi italiani e hashtag del campionato. Riepilogo e avvisi uguali.
- Ogni partita controllata lascia i suoi numeri nello stato ("stats"): servono
  a tarare le soglie.
- Tutto nell'argomento "📈 Quote" del gruppo (lo crea il bot).

QUANTO CONSUMA: lo storico delle quote NON conta nelle 250 chiamate al mese
del piano gratuito (verificato con il contatore dell'account il 6/11/2026).
Contano solo gli aggiornamenti dell'elenco partite (venerdi' i campionati,
lunedi' le coppe, a volte il martedi'), i nomi delle squadre nuove e l'elenco
dei mercati (1 al mese): 15-30 chiamate al mese. Un contatore (allineato a
quello dell'account) non fa mai superare il limite.

COME PARTE: lo lancia il giro ogni 5 minuti del bot notizie (monitor-news.yml,
avviato da cron-job.org). Quasi sempre controlla l'ora ed esce subito.
Prove a mano: workflow "Prova bot quote".

STATO: state/quote_state.json (solo questo file; lo stato delle notizie lo
legge e basta, per sapere qual e' il gruppo Telegram).

Uso: python monitor_quote.py                   giro normale
     python monitor_quote.py --mode test       prova (diagnostica + messaggio di prova)
     python monitor_quote.py --mode ora        controllo subito delle prossime partite
     python monitor_quote.py --mode apertura   aggiorna subito l'elenco delle partite (campionati e coppe)
     python monitor_quote.py --mode riepilogo  riepilogo subito delle partite di domani
     python monitor_quote.py --mode rivedi [--partita Roma]
                                               rilegge le partite gia' giocate come 40 minuti prima:
                                               con --partita manda quelle partite; senza, il conto
                                               forti/medi/rumore della settimana e le 3 piu' forti
     --partita con test, ora, riepilogo e rivedi: una squadra (es. Roma) o una competizione
     (SA, PL, PD, BL1, FL1, CL, EL, ECL, "coppe"); con una competizione rivedi fa il conto di quella
"""

import argparse
import bisect
import html
import json
import math
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

from config import FIXTURES_FILE, HASHTAGS, SEND_DELAY_GROUP_SECONDS, STATE_FILE
from utils import send_telegram_message, telegram_api

# =====================================================================
# IMPOSTAZIONI (tutto quello che si puo' voler regolare)
# =====================================================================
ROME = ZoneInfo("Europe/Rome")
API_BASE = "https://api.oddspapi.io/v4"
API_KEY = os.environ.get("ODDSPAPI_API_KEY", "").strip()
QUOTE_STATE_FILE = os.path.join(os.path.dirname(__file__), "state", "quote_state.json")

# I 3 book confrontati (lo storico ne accetta al massimo 3 per chiamata): Pinnacle e' il riferimento
BOOKMAKERS = ["pinnacle", "sbobet", "singbet"]
BOOK_LABEL = {"pinnacle": "Pinnacle", "singbet": "Singbet", "sbobet": "Sbobet", "bet365": "Bet365"}
BOOK_SHORT = {"pinnacle": "Pinn", "sbobet": "Sbo", "singbet": "Sing"}
SOT_BOOK = "bet365"             # tiri in porta di squadra se nessuno dei 3 book li quota: solo informazione
SOT_MAX_TRIES = 8               # se in 8 partite quel book non li ha mai, smette di chiederli

# Campionati: codice football-data (calendario del bot notizie) -> nome, paese, id OddsPapi di riserva
LEAGUES_Q = {
    "SA": {"name": "Serie A", "flag": "🇮🇹", "country": "italy", "names": ("serie a",), "id": 23},
    "PL": {"name": "Premier League", "flag": "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F",
           "country": "england", "names": ("premier league",), "id": 17},
    "PD": {"name": "La Liga", "flag": "🇪🇸", "country": "spain", "names": ("laliga", "la liga"), "id": 8},
    "BL1": {"name": "Bundesliga", "flag": "🇩🇪", "country": "germany", "names": ("bundesliga",), "id": 35},
    "FL1": {"name": "Ligue 1", "flag": "🇫🇷", "country": "france", "names": ("ligue 1",), "id": 34},
}

# Coppe europee: le partite arrivano dall'elenco OddsPapi (il calendario gratuito di football-data ha solo la
# Champions), con una chiamata a parte (l'elenco ammette al massimo 3 coppe per chiamata).
CUPS_Q = {
    "CL": {"name": "Champions League", "flag": "⭐", "names": ("uefa champions league",), "id": 7},
    "EL": {"name": "Europa League", "flag": "🟠", "names": ("uefa europa league",), "id": 679},
    "ECL": {"name": "Conference League", "flag": "🟢",
            "names": ("uefa conference league", "uefa europa conference league"), "id": 34480},
}
COMPS_Q = {**LEAGUES_Q, **CUPS_Q}
CUPS_ONLY_TOP5 = False          # coppe: True = solo le partite con almeno una squadra dei 5 campionati; False = tutte...
CUPS_TOP5_MONTHS = (7, 8)       # ...ma a luglio e agosto (preliminari: anche 80-90 partite il giovedi') solo quelle
CUP_APERTURA_DAY = 0            # coppe: quote di riferimento del lunedi' alle 15:00 (dopo il turno di campionato)
TOP5_KEEP_DAYS = 120            # squadre dei 5 campionati ricordate (per il filtro delle coppe) fino a 120 giorni

APERTURA_DAYS = (1, 4)          # quote di riferimento dei campionati: martedi' (1) e venerdi' (4)...
APERTURA_HOUR = 15              # ...alle 15:00
APERTURA_WINDOW_HOURS = 3       # giro delle 15 (aggiornamento elenco): va bene fino alle 18
LOOKAHEAD_DAYS = 6              # partite tenute nell'elenco
RIDOSSO_MINUTES = 40            # minuti prima del fischio d'inizio
RIDOSSO_LATEST_MINUTES = 12     # in ritardo si fa fino a 12 minuti prima, poi si salta
MERGE_MINUTES = 15              # orari d'inizio entro 15 minuti: un solo controllo
REFRESH_MIN_HOURS = 6           # elenco partite riletto al massimo ogni 6 ore se manca una partita
HIST_PAUSE = 5.3                # lo storico vuole 5 secondi tra una chiamata e l'altra
API_PAUSE = 1.2                 # le altre: 1 secondo tra due chiamate allo stesso indirizzo (una rifiutata conta lo stesso)
MONTH_LIMIT = 250               # chiamate al mese del piano gratuito
MONTH_RESERVE = 12              # tenute da parte per le prove a mano
RUN_BUDGET_SECONDS = 170        # tempo massimo per giro (il giro ogni 5 minuti deve poi controllare le notizie)
RIEPILOGO_HOUR = 19             # riepilogo delle partite di domani alle 19 (fino alle 23 se il giro e' in ritardo)
RIEPILOGO_WINDOW_HOURS = 4

AH_HOME_SIGN = 1                # la linea del mercato e' quella della squadra di casa (-0,5 = casa favorita: verificato)
FAV_GAP = 0.05                  # sotto 5 punti di differenza non c'e' una favorita
ARROW_PTS = 1.5                 # freccia accanto a una quota: probabilita' mossa di almeno 1,5 punti...
ARROW_STRONG_PTS = 5.0          # ...doppia freccia da 5 punti in su
STALE_HOURS = 6                 # linea principale: una linea ferma da 6 ore piu' delle altre deve essere 1 punto piu'
STALE_MAX_HOURS = 72            # equilibrata per vincere; ferma da piu' di 72 ore = tolta dal book

# Forza del segnale (1-10) = 2 x ampiezza (1-5) + book (3 su 3 +1, 2 su 3 0, uno solo -1)
#                            + tenuta (ha tenuto 0, tornato un po' indietro -1, rientrato -2) + altro mercato (+1)
# L'ampiezza si misura in punti di probabilita' (senza margine) SULLA LINEA DELL'APERTURA: se la linea principale
# e' cambiata, si guarda come si e' mossa la quota della linea di partenza (cosi' un cambio di linea "di confine"
# non conta come un movimento grande).
FORZA_MIN_AVVISO = 4            # avviso a 40 minuti da 4/10 in su (sotto e' rumore)
FORZA_FORTE = 7                 # da 7/10: segnale forte
LEV_SIDE = (3.0, 4.5, 6.0, 8.0, 10.0)   # handicap asiatico (o solo 1X2): punti per l'ampiezza 1-5
LEV_GOL = (3.5, 5.0, 6.5, 8.5, 10.5)    # linea gol: punti dell'Over per l'ampiezza 1-5
LEV_GG = (3.5, 5.0, 6.5, 8.0, 10.0)     # Goal/No Goal: punti del GG per l'ampiezza 1-5
LINE_PTS = 6.0                  # se la linea dell'apertura non c'e' piu': un quarto di linea vale circa 6 punti
MIN_BOOK_PTS = 1.5              # un book "si muove" (conferme, frecce, altro mercato) da 1,5 punti
EVENT_PTS = 3.0                 # corner/gol/tiri di squadra con la linea ferma: freccia da 3 punti dell'Over
FORMAZIONI_MINUTES = 60         # le formazioni ufficiali escono circa un'ora prima
TENUTA_OK = 0.8                 # tenuta: adesso almeno l'80% del punto piu' alto = ha tenuto (2 punti)...
TENUTA_MEZZA = 0.5              # ...almeno la meta' = e' tornato un po' indietro (1); meno = rientrato (0)

SPARK = "▁▂▃▄▅▆▇█"             # andamento della quota: barra alta = quota alta
SPARK_POINTS = 10               # la quota in 10 tratti uguali dall'apertura ad adesso (11 barre)
SPARK_MIN_PTS = 4.0             # sotto 4 punti di probabilita' di differenza le barre restano quasi piatte

TOPIC_NAME = "📈 Quote"
TOPIC_COLOR = 9367192           # verde
KEEP_DAYS = 8                   # partite finite tenute nello stato una settimana (per "rivedi")
LEGEND_VERSION = 3              # se cambia, la legenda viene rimandata una volta (2 = forza, squadre, conferme; 3 = coppe)
APERTURA_TRIES = 3              # elenco partite non letto all'apertura: si riprova al giro dopo, al massimo 3 volte
MARKETS_VERSION = 4             # se cambia, l'elenco dei mercati viene riletto subito (3-4 = corner, gol e tiri di squadra)
STATS_KEEP = 400                # numeri delle partite tenuti per tarare le soglie
RIVEDI_DAYS = 8                 # "rivedi": partite giocate negli ultimi 8 giorni
RIVEDI_BUDGET_SECONDS = 480     # "rivedi" di tutta la settimana: al massimo 8 minuti di letture
RIVEDI_TOP = 3                  # ...e nel gruppo le 3 partite piu' forti
MUTO = False                    # --muto (solo prove a mano): i messaggi vanno nel registro, non nel gruppo


# =====================================================================
# Stato e calendario
# =====================================================================
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, type(default)) else default
    except (OSError, ValueError):
        return default


def load_qstate() -> dict:
    st = load_json(QUOTE_STATE_FILE, {})
    if st.get("version") != 2:          # stato delle prime versioni: si riparte puliti (tenendo argomento e nomi)
        st = {k: st[k] for k in ("topic", "tournaments", "participants", "month", "calls") if k in st}
        st["version"] = 2
    for key, default in (("month", ""), ("calls", 0), ("fixtures", {}), ("done", []), ("topic", {}),
                         ("tournaments", {}), ("participants", {}), ("markets", {}), ("markets_month", ""),
                         ("notices", []), ("log", []), ("refresh_at", ""), ("stats", [])):
        st.setdefault(key, default)
    month = now_utc().astimezone(ROME).strftime("%Y-%m")
    if st["month"] != month:
        st["month"], st["calls"] = month, 0
        st["notices"] = [n for n in st["notices"] if not n.startswith("limit:")]
    return st


def save_qstate(st: dict) -> None:
    os.makedirs(os.path.dirname(QUOTE_STATE_FILE), exist_ok=True)
    tmp = QUOTE_STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, QUOTE_STATE_FILE)


def parse_time(value):
    """startTime di OddsPapi o kickoff del calendario -> datetime UTC (accetta secondi, millisecondi o testo ISO)."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        if v > 1e12:
            v /= 1000.0
        return datetime.fromtimestamp(v, timezone.utc)
    try:
        s = str(value).strip().replace("Z", "+00:00")
        if s.isdigit():
            return parse_time(int(s))
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def calendar_matches(st: dict | None = None, finished: bool = False) -> list:
    """Partite dei 5 campionati dal calendario del bot notizie (state/fixtures.json) e, con lo stato, quelle delle
    coppe dall'elenco OddsPapi (la Champions del calendario notizie non si usa: arriva gia' da OddsPapi).
    finished: anche le partite gia' finite (per imparare i nomi delle squadre)."""
    cal = load_json(FIXTURES_FILE, {})
    teams = {t.get("name"): t for t in cal.get("teams", []) if isinstance(t, dict)}
    skip = ("POSTPONED", "CANCELLED", "SUSPENDED", "AWARDED") + (() if finished else ("FINISHED",))
    out = []
    for f in cal.get("fixtures", []):
        code = f.get("competition")
        if code not in LEAGUES_Q or f.get("status") in skip:
            continue
        ko = parse_time(f.get("kickoff"))
        if not ko:
            continue
        out.append({"code": code, "home": f.get("home", ""), "away": f.get("away", ""), "ko": ko,
                    "home_short": (teams.get(f.get("home")) or {}).get("shortName") or f.get("home", ""),
                    "away_short": (teams.get(f.get("away")) or {}).get("shortName") or f.get("away", "")})
    if st is not None:
        out += cup_matches(st)[0]
    return sorted(out, key=lambda m: m["ko"])


def cup_matches(st: dict, lo: datetime | None = None, hi: datetime | None = None) -> tuple:
    """Partite delle coppe dall'elenco OddsPapi tenuto nello stato: (partite, quante lasciate fuori dal filtro).
    Tutte; solo quelle con almeno una squadra dei 5 campionati con CUPS_ONLY_TOP5 o nei mesi CUPS_TOP5_MONTHS
    (preliminari d'estate)."""
    top5 = st.get("top5") or {}
    out, skipped = [], 0
    for fid, rec in st["fixtures"].items():
        if rec.get("code") not in CUPS_Q:
            continue
        ko = parse_time(rec.get("start"))
        if not ko or (lo and ko < lo) or (hi and ko > hi):
            continue
        p1, p2 = str(rec.get("p1")), str(rec.get("p2"))
        only5 = CUPS_ONLY_TOP5 or ko.astimezone(ROME).month in CUPS_TOP5_MONTHS
        if only5 and p1 not in top5 and p2 not in top5:
            skipped += 1
            continue
        (h, hs), (a, as_) = cup_team(st, p1), cup_team(st, p2)
        if not h or not a:
            print(f"[WARN] coppe: mancano i nomi delle squadre della partita {fid}")
            continue
        out.append({"code": rec["code"], "home": h, "away": a, "ko": ko, "home_short": hs, "away_short": as_,
                    "fid": fid})
    return sorted(out, key=lambda m: m["ko"]), skipped


def apertura_time(ko: datetime, code: str = "") -> datetime:
    """Momento delle quote di riferimento: per i campionati l'ultimo martedi' o venerdi' alle 15:00 almeno 2 ore prima
    del fischio, per le coppe l'ultimo lunedi' alle 15:00."""
    days = (CUP_APERTURA_DAY,) if code in CUPS_Q else APERTURA_DAYS
    limit = (ko - timedelta(hours=2)).astimezone(ROME)
    for back in range(0, 8):
        d = (limit - timedelta(days=back)).date()
        if d.weekday() in days:
            t = datetime(d.year, d.month, d.day, APERTURA_HOUR, tzinfo=ROME)
            if t <= limit:
                return t.astimezone(timezone.utc)
    return (limit - timedelta(days=3)).astimezone(timezone.utc)


# =====================================================================
# OddsPapi
# =====================================================================
class QuotaExhausted(Exception):
    pass


_LAST_CALL = {}


def api_get(path: str, params: dict, st: dict, counts: bool = True, force: bool = False):
    """Chiamata a OddsPapi. counts=False per quelle che non consumano (account, storico)."""
    if not API_KEY:
        raise RuntimeError("manca il secret ODDSPAPI_API_KEY")
    if counts and not force and st["calls"] >= MONTH_LIMIT - MONTH_RESERVE:
        raise QuotaExhausted(f"chiamate del mese finite ({st['calls']}/{MONTH_LIMIT})")
    if path in _LAST_CALL:          # pausa obbligatoria tra due chiamate allo stesso indirizzo
        wait = (HIST_PAUSE if path == "/historical-odds" else API_PAUSE) - (time.monotonic() - _LAST_CALL[path])
        if wait > 0:
            time.sleep(wait)
    q = dict(params or {})
    q["apiKey"] = API_KEY
    for attempt in range(4):
        try:
            resp = requests.get(API_BASE + path, params=q, timeout=60)
        except requests.RequestException as e:
            if attempt == 3:
                raise RuntimeError(f"rete: {e.__class__.__name__}")
            time.sleep(3)
            continue
        finally:
            _LAST_CALL[path] = time.monotonic()
        if counts:
            st["calls"] += 1
        try:
            data = resp.json()
        except ValueError:
            data = None
        if resp.status_code == 200:
            return data
        text = json.dumps(data)[:300] if data is not None else resp.text[:300]
        if resp.status_code == 429:
            low = text.lower()
            if "limit_exceeded" in low or "request_limit" in low or "quota" in low:
                st["calls"] = max(st["calls"], MONTH_LIMIT)
                raise QuotaExhausted("OddsPapi: chiamate del mese finite")
            if counts:
                st["calls"] -= 1        # rifiutata per troppa fretta: non consumata
            wait = 2.0
            if isinstance(data, dict):
                err = data.get("error") if isinstance(data.get("error"), dict) else data
                wait = float(err.get("retryMs") or 0) / 1000.0 or float(err.get("retryAfterSec") or 0) or 2.0
            wait = min(max(wait, 1.0), 12.0)
            print(f"[OddsPapi] troppo veloce, aspetto {wait:.1f}s")
            time.sleep(wait)
            continue
        raise RuntimeError(f"OddsPapi {path}: HTTP {resp.status_code} {text}")
    raise RuntimeError(f"OddsPapi {path}: troppi tentativi")


def sync_calls(st: dict) -> None:
    """Allinea il contatore a quello dell'account OddsPapi (la lettura dell'account non consuma)."""
    try:
        acc = api_get("/account", {}, st, counts=False, force=True)
    except Exception as e:      # noqa: BLE001
        print(f"[WARN] account non letto: {e}")
        return
    for sub in (acc or {}).get("subscriptions") or []:
        if isinstance(sub, dict) and sub.get("is_active") is not False and "request_count" in sub:
            try:
                used, limit = int(sub["request_count"]), int(sub.get("request_limit") or MONTH_LIMIT)
            except (TypeError, ValueError):
                continue
            st["calls"] = used
            st["limit"] = limit
            return


def as_list(data) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in ("data", "fixtures", "items", "results", "tournaments", "markets", "participants"):
            if isinstance(data.get(k), list):
                return data[k]
        if "fixtureId" in data or "marketId" in data or "tournamentId" in data:
            return [data]
        vals = list(data.values())
        if vals and all(isinstance(v, dict) for v in vals):
            return vals
    return []


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", str(text or "").replace("ß", "ss"))
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def ensure_tournaments(st: dict, force: bool = False) -> dict:
    """Id OddsPapi dei 5 campionati (per nome e paese) e delle coppe (per nome), cercati una volta; se non si
    trovano, quelli di riserva."""
    have = st.get("tournaments") or {}
    if have and all(c in have for c in COMPS_Q) and not force:
        return have
    try:
        items = as_list(api_get("/tournaments", {"sportId": 10}, st))
    except QuotaExhausted:
        raise
    except Exception as e:      # noqa: BLE001
        print(f"[WARN] elenco campionati non letto ({e}): uso gli id di riserva")
        items = []
    found = {}
    for code, lg in COMPS_Q.items():
        best = None
        for t in items:
            name = norm(t.get("tournamentName") or t.get("name"))
            cat = norm(t.get("categoryName") or t.get("categorySlug") or t.get("category"))
            if name in lg["names"] and (code in CUPS_Q or lg["country"] in cat):
                tid = t.get("tournamentId") or t.get("id")
                if best is None or tid == lg["id"]:
                    best = tid
        found[code] = int(best) if best else int(have.get(code) or lg["id"])
    st["tournaments"] = found
    print("Id OddsPapi di campionati e coppe:", found)
    uefa = [f"{t.get('tournamentId') or t.get('id')}:{t.get('tournamentName') or t.get('name')}"
            f"[{t.get('categoryName') or t.get('categorySlug') or t.get('category')}]"
            for t in items if "uefa" in norm(t.get("tournamentName") or t.get("name"))]
    print(f"   competizioni UEFA nell'elenco ({len(items)} in tutto): {uefa[:20]}")
    return found


_SKIP_WORDS = {"half", "halves", "first", "second", "1st", "2nd", "player", "players", "card", "cards", "booking",
               "bookings", "minute", "minutes", "odd", "even", "exact", "range", "race", "interval", "margin",
               "winning", "method", "scorer", "anytime"}


def classify_market(m: dict) -> list | None:
    """Un mercato di /markets -> [tipo, linea, periodo, esiti in ordine, gruppo, squadra] (None = non usato).
    gruppo: 'main' = 1X2, handicap asiatico, linea gol e Goal/No Goal della partita; 'ct' = corner della partita;
    'tc' = corner di una squadra; 'tg' = gol di una squadra; 'ts' = tiri in porta di una squadra.
    squadra: 'home' / 'away' per i mercati di una sola squadra, '' per gli altri."""
    if int(m.get("sportId") or 10) != 10 or m.get("playerProp"):
        return None
    mtype = str(m.get("marketType") or "").lower()
    words = norm(m.get("marketName")).split()
    ws = set(words) | set(norm(mtype).split())          # anche il tipo (es. "corners-totals", "team-totals")
    if ws & _SKIP_WORDS:
        return None                     # tempi, cartellini, giocatori, pari/dispari...
    period = str(m.get("period") or "").lower()
    handicap = float(m.get("handicap") or 0)
    corner = bool(ws & {"corner", "corners"})
    shots = bool(ws & {"shot", "shots", "sot", "shotsontarget"})
    sot = shots and bool(ws & {"target", "sot", "shotsontarget", "ontarget"})
    side = ""
    if ws & {"team", "home", "away"}:
        home, away = bool(ws & {"1", "home"}), bool(ws & {"2", "away"})
        if home == away:
            return None                 # non si capisce di quale squadra
        side = "home" if home else "away"
    if corner or shots or side:
        if "total" not in mtype or (shots and not sot) or handicap <= 0:
            return None                 # handicap dei corner, tiri totali, sì/no di squadra...: non usati
        if corner:
            group = "tc" if side else "ct"
        elif sot:
            if not side:
                return None             # tiri in porta della partita: non usati
            group = "ts"
        else:
            group = "tg"
        order = outcome_order("totals", m.get("outcomes") or [])
        return ["totals", handicap, period, order, group, side] if order else None
    first_words = {(norm(o.get("outcomeName")).split() or [""])[0] for o in (m.get("outcomes") or [])}
    if first_words & {"yes", "no"}:     # mercati Si'/No: si tiene solo Goal/No Goal (entrambe segnano)
        if not ((("both" in words and "score" in words) or "btts" in words) and
                not any(w in words for w in ("and", "win", "result", "over", "under", "double", "1x2"))):
            return None
        mtype = "btts"
    elif mtype not in ("1x2", "spreads", "totals"):
        return None
    order = outcome_order(mtype, m.get("outcomes") or [])
    if not order:
        return None                     # non si capisce quale esito e' casa/Over: meglio non usarlo
    return [mtype, handicap, period, order, "main", ""]


def ensure_markets(st: dict, force: bool = False) -> dict:
    """Descrizione dei mercati (id -> classify_market), riletta una volta al mese (e subito se cambia il modo di
    leggerli, MARKETS_VERSION)."""
    same = st.get("markets_v") == MARKETS_VERSION
    if st["markets"] and st["markets_month"] == st["month"] and same and not force:
        return st["markets"]
    last = parse_time(st.get("markets_try"))
    if not force and last and now_utc() - last < timedelta(hours=20 if same else 1):
        return st["markets"]
    st["markets_try"] = now_utc().isoformat(timespec="seconds")
    try:
        items = as_list(api_get("/markets", {"language": "en"}, st))
    except QuotaExhausted:
        raise
    except Exception as e:      # noqa: BLE001
        print(f"[WARN] elenco mercati non letto ({e})")
        return st["markets"]
    meta, names, types, skipped = {}, {}, {}, []
    for m in items:
        try:
            if int(m.get("sportId") or 10) != 10:
                continue
            mt = str(m.get("marketType") or "")
            types[mt] = types.get(mt, 0) + 1
            info = classify_market(m)
            if info:
                meta[str(m["marketId"])] = info
                if info[4] != "main":
                    names.setdefault(info[4], set()).add(str(m.get("marketName")))
            elif re.search(r"corner|team|home|away|shot|target", f"{m.get('marketName')} {mt}", re.I) and \
                    len(skipped) < 40:
                skipped.append(f"{m.get('marketId')}:{m.get('marketName')}[{mt},{m.get('handicap')},{m.get('period')}]")
        except (KeyError, TypeError, ValueError):
            continue
    if meta:
        st["markets"], st["markets_month"], st["markets_v"] = meta, st["month"], MARKETS_VERSION
    kinds = {}
    for v in meta.values():
        kinds[v[4]] = kinds.get(v[4], 0) + 1
    print(f"Mercati letti: {len(meta)} {kinds} (main = 1X2, asiatico, linea gol, GG · ct/tc = corner partita/squadra · "
          f"tg = gol di squadra · ts = tiri in porta di squadra)")
    print(f"   tipi di mercato del calcio su OddsPapi: {dict(sorted(types.items(), key=lambda kv: -kv[1])[:25])}")
    for k, ns in sorted(names.items()):
        print(f"   {k}: {sorted(ns)[:8]}")
    if skipped:
        print(f"   non usati (corner/squadra/tiri): {skipped}")
    return st["markets"]


_SIDE_NAMES = {"home": ("1", "home", "w1", "team1", "1 ah", "ah1", "h"), "draw": ("x", "draw", "d"),
               "away": ("2", "away", "w2", "team2", "2 ah", "ah2", "a")}


def outcome_order(mtype: str, outcomes: list) -> list | None:
    """Id degli esiti nell'ordine giusto, letto dai NOMI (gli id non sono sempre in ordine):
    1X2 -> [1, X, 2]; handicap -> [casa, ospite]; linea gol -> [Over, Under]; Goal/No Goal -> [GG, NG]."""
    by = {}
    for o in outcomes:
        try:
            oid, name = int(o["outcomeId"]), norm(o.get("outcomeName"))
        except (KeyError, TypeError, ValueError):
            continue
        if mtype == "totals":
            side = "over" if name.startswith("over") else "under" if name.startswith("under") else None
        elif mtype == "btts":
            side = "yes" if (name.startswith("yes") or name == "gg") else "no" if (name.startswith("no") or name == "ng") \
                else None
        else:
            side = next((s for s, names in _SIDE_NAMES.items() if name in names), None)
        if side and side not in by:
            by[side] = oid
    want = {"totals": ("over", "under"), "spreads": ("home", "away"), "1x2": ("home", "draw", "away"),
            "btts": ("yes", "no")}[mtype]
    return [by[s] for s in want] if all(s in by for s in want) else None


def ensure_participants(st: dict, ids: set) -> dict:
    """Nomi delle squadre (solo quelle che servono), letti una volta e tenuti nello stato."""
    missing = {str(i) for i in ids if i is not None} - set(st["participants"])
    if not missing:
        return st["participants"]
    last = parse_time(st.get("participants_try"))
    if last and now_utc() - last < timedelta(hours=12):
        return st["participants"]   # gia' provato da poco (per le coppe i nomi servono: si riprova dopo 12 ore)
    st["participants_try"] = now_utc().isoformat(timespec="seconds")
    try:
        data = api_get("/participants", {"sportId": 10, "language": "en"}, st)
    except QuotaExhausted:
        raise
    except Exception as e:      # noqa: BLE001
        print(f"[WARN] nomi delle squadre non letti ({e})")
        return st["participants"]
    if isinstance(data, dict) and not any(isinstance(v, dict) for v in list(data.values())[:5]) and \
            all(str(k).isdigit() for k in list(data.keys())[:5]):
        pairs = data.items()                             # {id: nome}
    else:
        pairs = [(p.get("participantId") or p.get("id"),
                  p.get("participantName") or p.get("name") or p.get("participantShortName")) for p in as_list(data)]
    for pid, name in pairs:
        if str(pid) in missing and name:
            st["participants"][str(pid)] = str(name)
    print(f"Nomi squadre: {len(st['participants'])} in memoria")
    return st["participants"]


_SNAPSHOT = {}          # ultimo elenco letto (solo per la prova: confronto con lo storico)


def refresh_fixtures(st: dict, force: bool = False, which: str = "campionati", days: int | None = None) -> int:
    """Elenco delle partite con il loro id OddsPapi (Pinnacle): UNA chiamata per i 5 campionati e UNA per le coppe
    (l'elenco ammette poche competizioni per chiamata). which: 'campionati', 'coppe' o 'tutto'."""
    tour = ensure_tournaments(st)
    code_by_tid = {str(v): k for k, v in tour.items()}
    groups = []
    if which in ("campionati", "tutto"):
        groups.append(("campionati", [c for c in LEAGUES_Q if c in tour]))
    if which in ("coppe", "tutto"):
        groups.append(("coppe", [c for c in CUPS_Q if c in tour]))
    horizon = now_utc() + timedelta(days=days or LOOKAHEAD_DAYS + 2)
    n, counts, errors, raw = 0, {}, [], {}
    for label, codes in groups:
        if not codes:
            continue
        try:
            data = api_get("/odds-by-tournaments", {"tournamentIds": ",".join(str(tour[c]) for c in codes),
                                                    "bookmaker": "pinnacle"}, st, force=force)
        except QuotaExhausted:
            raise
        except Exception as e:      # noqa: BLE001
            print(f"[WARN] elenco {label} non letto: {e}")
            errors.append(e)
            continue
        for fx in as_list(data):
            try:
                fid = str(fx["fixtureId"])
            except (KeyError, TypeError):
                continue
            tid = str(fx.get("tournamentId"))
            raw[tid] = raw.get(tid, 0) + 1
            start = parse_time(fx.get("startTime"))
            code = code_by_tid.get(str(fx.get("tournamentId")), (st["fixtures"].get(fid) or {}).get("code", ""))
            if not start or start > horizon or code not in codes:
                continue
            _SNAPSHOT[fid] = fx
            rec = st["fixtures"].setdefault(fid, {})
            rec.update(code=code, p1=fx.get("participant1Id"), p2=fx.get("participant2Id"), start=start.isoformat())
            counts[code] = counts.get(code, 0) + 1
            n += 1
        if label == "campionati":
            st["refresh_at"] = now_utc().isoformat(timespec="seconds")
    if errors and len(errors) == len([g for g in groups if g[1]]):
        raise errors[0]
    ensure_participants(st, {r.get("p1") for r in st["fixtures"].values()} | {r.get("p2") for r in st["fixtures"].values()})
    print(f"Elenco partite aggiornato ({which}): {n} partite {counts} (nell'elenco per id: {raw}; chiamate del mese "
          f"{st['calls']}/{MONTH_LIMIT})")
    return n


# ---------------------------------------------------------------------
# Lettura dello storico: quote di ogni book in un certo momento
# ---------------------------------------------------------------------
def _pick_main(cands: list):
    """Tra le linee (linea, prezzo1, prezzo2, ultimo aggiornamento) sceglie quella principale: la piu' equilibrata.
    Una linea tolta dal book resta nello storico con il suo ultimo prezzo: per questo una linea ferma da piu' ore
    delle altre deve essere un po' piu' equilibrata per vincere (1 punto ogni STALE_HOURS ore), e quelle ferme da
    piu' di STALE_MAX_HOURS ore non contano. (Prima bastavano 6 ore di differenza per scartarla: in un momento
    passato veniva scartata anche la linea principale ferma da qualche ora, e si prendeva una linea sbilanciata.)"""
    if not cands:
        return None
    newest = max(c[3] for c in cands)
    alive = [c for c in cands if c[3] >= newest - timedelta(hours=STALE_MAX_HOURS)] or cands

    def score(c):
        age = (newest - c[3]).total_seconds() / 3600.0
        return abs(1 / c[1] - 1 / c[2]) + 0.01 * age / STALE_HOURS
    best = min(alive, key=score)
    return [best[0], best[1], best[2]]


def _fresh_lines(cands: list) -> dict:
    """Tutte le linee ancora aggiornate: {"2.5": [Over, Under], ...} (per Over 2,5, gol di squadra, pronostico e per
    misurare il movimento sulla linea dell'apertura: una linea ferma da 6 ore piu' delle altre puo' essere stata
    tolta dal book, e il suo ultimo prezzo non direbbe com'e' adesso)."""
    if not cands:
        return {}
    newest = max(c[3] for c in cands)
    return {f"{c[0]:g}": [c[1], c[2]] for c in cands if c[3] >= newest - timedelta(hours=STALE_HOURS)}


EVENT_GROUPS = ("tc", "tg", "ts")


class BookHist:
    """Storico di un book: per ogni mercato gli esiti (nell'ordine giusto) con i cambi di prezzo in ordine di tempo."""

    def __init__(self, slug: str, bk: dict, meta: dict):
        self.slug = slug
        self.mk = []            # (id mercato, info, gruppo, squadra, [(tempi, cambi) per esito])
        for mid, m in ((bk or {}).get("markets") or {}).items():
            info = meta.get(str(mid))
            if not info or len(info) < 4 or info[2] not in ("fulltime", "result", ""):
                continue
            outs = (m or {}).get("outcomes") or {}
            series = []
            for oid in info[3]:
                pls = (outs.get(str(oid)) or {}).get("players") or {}
                entries = next(iter(pls.values()), []) if isinstance(pls, dict) and pls else []
                rows = []
                for e in entries if isinstance(entries, list) else []:
                    t = parse_time(e.get("createdAt")) if isinstance(e, dict) else None
                    if t:
                        rows.append((t, e))
                rows.sort(key=lambda r: r[0])
                series.append(([r[0] for r in rows], [r[1] for r in rows]))
            group = info[4] if len(info) > 4 else "main"
            side = info[5] if len(info) > 5 else ""
            self.mk.append((str(mid), info, group, side, series))

    @staticmethod
    def _price(ser, at):
        """Prezzo in vigore al momento 'at' (None = l'ultimo) e quando e' stato messo."""
        times, entries = ser
        if not times:
            return None, None
        i = len(times) - 1 if at is None else bisect.bisect_right(times, at) - 1
        if i < 0:
            return None, None
        e = entries[i]
        if e.get("active") is False:
            return None, times[i]
        try:
            p = float(e.get("price"))
        except (TypeError, ValueError):
            return None, times[i]
        return (p if p > 1.0 else None), times[i]

    def snapshot(self, at=None, groups=None, mtypes=None) -> dict:
        """Quote al momento 'at' (None = le ultime): 1X2, asiatico e linea gol principali, tutte le linee gol, GG,
        corner della partita e, per ogni squadra, corner, gol e tiri in porta (linea principale e tutte le linee).
        groups / mtypes: solo quei gruppi / tipi di mercato (piu' veloce per l'andamento)."""
        res = {"x": None, "ah": None, "ou": None, "lines": {}, "gg": None, "ct": None,
               "tc": {}, "tg": {}, "ts": {}, "ev_lines": {}}
        ah, ou, ct = [], [], []
        ev = {g: {"home": [], "away": []} for g in EVENT_GROUPS}
        for mid, info, group, side, series in self.mk:
            if (groups and group not in groups) or (mtypes and info[0] not in mtypes):
                continue
            prices, times = [], []
            for ser in series:
                p, t = self._price(ser, at)
                prices.append(p)
                times.append(t)
            if not all(prices):
                continue
            last = max(times)
            if group == "main":
                if info[0] == "1x2":
                    if len(prices) == 3 and (res["x"] is None or mid == "101"):
                        res["x"] = prices
                elif info[0] == "btts":
                    if len(prices) == 2 and (res["gg"] is None or mid == "104"):
                        res["gg"] = prices
                elif len(prices) == 2:
                    if info[0] == "spreads":
                        ah.append((AH_HOME_SIGN * info[1], prices[0], prices[1], last))
                    elif info[0] == "totals" and info[1] > 0:
                        ou.append((info[1], prices[0], prices[1], last))
            elif len(prices) == 2:
                if group == "ct":
                    ct.append((info[1], prices[0], prices[1], last))
                elif group in ev and side in ("home", "away"):
                    ev[group][side].append((info[1], prices[0], prices[1], last))
        res["ah"], res["ou"], res["lines"] = _pick_main(ah), _pick_main(ou), _fresh_lines(ou)
        res["ah_lines"] = _fresh_lines(ah)
        res["ct"] = _pick_main(ct)
        for g, sides in ev.items():
            for side, cands in sides.items():
                main = _pick_main(cands)
                if main:
                    res[g][side] = main
                    res["ev_lines"][f"{g}|{side}"] = _fresh_lines(cands)
        return res

    def ladder(self, at, mtype: str) -> str:
        """Per il registro: tutte le linee di un mercato principale al momento 'at' (linea prezzo1/prezzo2 e da
        quante ore e' fermo il prezzo)."""
        ref_t = at or now_utc()
        out = []
        for mid, info, group, sd, series in self.mk:
            if group != "main" or info[0] != mtype:
                continue
            got = [self._price(ser, at) for ser in series]
            if len(got) == 2 and all(p for p, _ in got):
                age = (ref_t - max(t for _, t in got)).total_seconds() / 3600
                out.append((info[1], got[0][0], got[1][0], age))
        return " ".join(f"{l:g}:{p1:.2f}/{p2:.2f}({a:.0f}h)" for l, p1, p2, a in sorted(out))

    def first_time(self, groups=None, side=None, mids=None):
        """Primo prezzo pubblicato dei mercati scelti."""
        best = None
        for mid, info, group, sd, series in self.mk:
            if (groups and group not in groups) or (side and sd != side) or (mids and mid not in mids):
                continue
            for times, _ in series:
                if times and (best is None or times[0] < best):
                    best = times[0]
        return best

    def first_spread_time(self):
        best = None
        for mid, info, group, sd, series in self.mk:
            if group == "main" and info[0] == "spreads":
                for times, _ in series:
                    if times and (best is None or times[0] < best):
                        best = times[0]
        return best

    def change_times(self, groups, start, end, mtypes=None) -> list:
        """Momenti in cui cambia un prezzo dei mercati scelti, dopo 'start' e fino a 'end' (None = fino in fondo)."""
        out = set()
        for mid, info, group, sd, series in self.mk:
            if group not in groups or (mtypes and info[0] not in mtypes):
                continue
            for times, _ in series:
                lo = bisect.bisect_right(times, start) if start else 0
                hi = len(times) if end is None else bisect.bisect_right(times, end)
                out.update(times[lo:hi])
        return sorted(out)


def has_data(snap: dict) -> bool:
    return bool(snap and (snap.get("x") or snap.get("ah") or snap.get("ou") or snap.get("gg") or snap.get("ct")
                          or snap.get("tc") or snap.get("tg") or snap.get("ts")))


def first_quotes(h: BookHist) -> dict:
    """Le prime quote di un book: appena pubblicato il 1X2 (o l'handicap asiatico, se arriva dopo)."""
    t = h.first_time({"main"}, mids={"101"}) or h.first_time({"main"})
    if not t:
        return {}
    snap = h.snapshot(t + timedelta(minutes=1))
    if not snap.get("ah"):
        t2 = h.first_spread_time()
        if t2 and t < t2 < t + timedelta(days=2):
            snap = h.snapshot(t2 + timedelta(minutes=1))
    return snap if has_data(snap) else {}


_HIST_INFO = {}         # per la prova: mercati trovati nello storico per ogni book (tutti, usati)
_HIST_UNKNOWN = {}      # per la prova: id dei mercati dello storico che il bot non usa (per scoprire corner e simili)


def fetch_history(st: dict, fid: str, books: list, force: bool = False) -> dict:
    """Storico grezzo di una partita sui book scelti (NON consuma chiamate): {book: {...}}."""
    hist = api_get("/historical-odds", {"fixtureId": fid, "bookmakers": ",".join(books)}, st,
                   counts=False, force=force)
    if isinstance(hist, dict) and fid in hist and isinstance(hist[fid], dict):
        hist = hist[fid]
    bks = hist.get("bookmakers") if isinstance(hist, dict) else None
    return bks if isinstance(bks, dict) else {}


def read_history(st: dict, fid: str, ap_at: datetime, at: datetime | None = None, force: bool = False,
                 books: list | None = None) -> dict:
    """Storico della partita: quote all'apertura (base) e al momento 'at' (None = adesso) su ogni book.
    Se la partita e' stata pubblicata dopo l'apertura si parte dalla prima quota; corner, gol e tiri di squadra
    pubblicati dopo l'apertura partono dalla loro prima quota."""
    meta = ensure_markets(st)
    bks = fetch_history(st, fid, books or BOOKMAKERS, force=force)
    _HIST_INFO.clear()
    for slug, bk in bks.items():
        mk = (bk or {}).get("markets") or {}
        _HIST_INFO[slug] = (len(mk), sum(1 for k in mk if k in meta))
        _HIST_UNKNOWN[slug] = sorted((k for k in mk if k not in meta), key=lambda k: int(k) if str(k).isdigit() else 0)[:40]
    bh = {slug: BookHist(slug, bk, meta) for slug, bk in bks.items()}
    ref_at = at or now_utc()
    now = {s: h.snapshot(at) for s, h in bh.items()}
    now = {s: v for s, v in now.items() if has_data(v)}
    opened = None
    for h in bh.values():
        t = h.first_time({"main"}, mids={"101"})
        if t and (opened is None or t < opened):
            opened = t
    base, first, base_at = {}, False, ap_at
    if ap_at <= ref_at:
        base = {s: h.snapshot(ap_at) for s, h in bh.items()}
        base = {s: v for s, v in base.items() if has_data(v)}
    if not base and opened and opened <= ref_at:
        first, base_at = True, opened + timedelta(minutes=1)
        base = {s: first_quotes(h) for s, h in bh.items()}
        base = {s: v for s, v in base.items() if v}
    for s, b in base.items():
        n, h = now.get(s) or {}, bh[s]
        if n.get("ct") and not b.get("ct"):
            t0 = h.first_time({"ct"})
            if t0 and t0 <= ref_at:
                b["ct"] = h.snapshot(t0 + timedelta(minutes=1), {"ct"}).get("ct")
        for g in EVENT_GROUPS:
            for side in (n.get(g) or {}):
                if side in (b.get(g) or {}):
                    continue
                t0 = h.first_time({g}, side=side)
                if t0 and t0 <= ref_at:
                    snap = h.snapshot(t0 + timedelta(minutes=1), {g})
                    if side in snap.get(g, {}):
                        b.setdefault(g, {})[side] = snap[g][side]
                        b.setdefault("ev_lines", {})[f"{g}|{side}"] = snap["ev_lines"].get(f"{g}|{side}", {})
    return {"base": base, "now": now, "base_at": base_at, "first": first, "bh": bh, "at": at}


# =====================================================================
# Lettura dei movimenti: segnali e forza (1-10)
# =====================================================================
def novig(prices):
    inv = [1.0 / p for p in prices]
    s = sum(inv)
    return [x / s for x in inv]


def tier(value: float, ths) -> int:
    return sum(1 for t in ths if value >= t - 1e-9)


def _sign(x: float) -> int:
    return 1 if x > 1e-9 else -1 if x < -1e-9 else 0


def side_move(a: dict, b: dict) -> dict | None:
    """Movimento verso la squadra di casa (dir +1) o l'ospite (-1), in punti di probabilita' senza margine.
    Con l'asiatico: la quota della linea dell'apertura adesso (se c'e' ancora), se no la linea di adesso con un
    quarto = LINE_PTS punti; senza asiatico il 1X2."""
    if a.get("ah") and b.get("ah"):
        dline = round(b["ah"][0] - a["ah"][0], 2)
        same = (b.get("ah_lines") or {}).get(f"{a['ah'][0]:g}")
        if same:
            meas = (novig(same)[0] - novig(a["ah"][1:])[0]) * 100
        else:                                           # linea piu' negativa = casa piu' favorita
            meas = (novig(b["ah"][1:])[0] - novig(a["ah"][1:])[0]) * 100 - dline / 0.25 * LINE_PTS
        return {"dir": _sign(meas), "lvl": tier(abs(meas), LEV_SIDE), "meas": meas, "dline": dline, "src": "ah"}
    if a.get("x") and b.get("x"):
        pa, pb = novig(a["x"]), novig(b["x"])
        pts = ((pb[0] - pa[0]) - (pb[2] - pa[2])) / 2 * 100
        return {"dir": _sign(pts), "lvl": tier(abs(pts), LEV_SIDE), "meas": pts, "dline": 0.0, "src": "x"}
    return None


def gol_move(a: dict, b: dict) -> dict | None:
    """Movimento della linea gol: dir +1 = piu' gol (Over), -1 = meno gol (Under). Misura come side_move: l'Over
    della linea dell'apertura adesso, se no la linea di adesso con un quarto = LINE_PTS punti."""
    if not (a.get("ou") and b.get("ou")):
        return None
    dline = round(b["ou"][0] - a["ou"][0], 2)
    same = (b.get("lines") or {}).get(f"{a['ou'][0]:g}")
    if same:
        meas = (novig(same)[0] - novig(a["ou"][1:])[0]) * 100
    else:
        meas = (novig(b["ou"][1:])[0] - novig(a["ou"][1:])[0]) * 100 + dline / 0.25 * LINE_PTS
    return {"dir": _sign(meas), "lvl": tier(abs(meas), LEV_GOL), "meas": meas, "dline": dline, "src": "ou"}


def gg_move(a: dict, b: dict) -> dict | None:
    """Goal/No Goal: dir +1 = GG piu' probabile, -1 = NG."""
    if not (a.get("gg") and b.get("gg")):
        return None
    pts = (novig(b["gg"])[0] - novig(a["gg"])[0]) * 100
    return {"dir": _sign(pts), "lvl": tier(abs(pts), LEV_GG), "meas": pts, "dline": 0.0, "src": "gg"}


MOVE_FN = {"side": side_move, "gol": gol_move, "gg": gg_move}
MOVE_TYPES = {"side": {"spreads", "1x2"}, "gol": {"totals"}, "gg": {"btts"}}     # mercati che servono a ogni segnale
LINE_KEY = {"side": "ah", "gol": "ou"}
PATH_POINTS = 150               # andamento: al massimo 150 momenti per book (basta e non rallenta il giro)


def combine(fam: str, moves: dict) -> dict | None:
    """Segnale di un mercato: almeno 2 book mossi nella stessa direzione; l'ampiezza e' la seconda piu' alta (cioe'
    confermata da 2 book). Con un solo book con le quote serve ampiezza 2 (e i book contano -1 nella forza)."""
    valid = {s: m for s, m in moves.items() if m}
    for d in (1, -1):
        lv = sorted((m["lvl"] for m in valid.values() if m["dir"] == d and m["lvl"] >= 1), reverse=True)
        agree = [s for s in BOOKMAKERS if s in valid and valid[s]["dir"] == d and abs(valid[s]["meas"]) >= MIN_BOOK_PTS]
        if len(lv) >= 2:
            return {"fam": fam, "dir": d, "lvl": lv[1], "books": agree, "n": len(valid)}
        if len(valid) == 1 and lv and lv[0] >= 2:
            return {"fam": fam, "dir": d, "lvl": lv[0], "books": agree, "n": 1}
    return None


def forza_of(lvl: int, nbooks: int, ratio: float, coe: int) -> tuple:
    """Forza 1-10 = 2 x ampiezza + book (3 d'accordo +1, 2 0, uno solo -1) + tenuta (ha tenuto 0, tornato un po'
    indietro -1, rientrato -2) + altro mercato (+1). Ritorna (forza, punti book, punti tenuta)."""
    acc = 1 if nbooks >= 3 else 0 if nbooks == 2 else -1
    ten = 0 if ratio >= TENUTA_OK else -1 if ratio >= TENUTA_MEZZA else -2
    return max(1, min(10, 2 * lvl + acc + ten + coe)), acc, ten


def move_path(R: dict, slug: str, fam: str, end) -> list:
    """Andamento del movimento di un book dall'apertura al momento del controllo: [(momento, movimento)]."""
    h, a = R["bh"].get(slug), R["base"].get(slug)
    if not h or not a:
        return []
    fn, mt = MOVE_FN[fam], MOVE_TYPES[fam]
    times = [t for t in h.change_times({"main"}, R["base_at"], end, mt) if end is None or t < end]
    if len(times) > PATH_POINTS:
        step = len(times) / float(PATH_POINTS)
        times = [times[int(i * step)] for i in range(PATH_POINTS)]
    out = []
    for t in times:
        mv = fn(a, h.snapshot(t, {"main"}, mt))
        if mv:
            out.append((t, mv))
    mv = fn(a, h.snapshot(R["at"], {"main"}, mt))
    if mv:
        out.append((end or now_utc(), mv))
    return out


def tenuta(pth: list, d: int) -> float:
    """Quanto del punto piu' alto del movimento c'e' ancora adesso (1 = ha tenuto tutto, 0 = rientrato)."""
    if not pth:
        return 1.0
    cur = pth[-1][1]["meas"] * d
    peak = max(mv["meas"] * d for _, mv in pth)
    if peak <= 0:
        return 0.0
    return max(0.0, min(1.0, cur / peak))


def event_move(a, b, g: str) -> tuple:
    """Linea di una squadra (corner, gol, tiri in porta) da a a b: (dir +1 piu' eventi / -1 meno / 0, forte?)."""
    if not a:
        return 0, False
    dline = round(b[0] - a[0], 2)
    if abs(dline) > 1e-9:
        return _sign(dline), abs(dline) >= (0.5 if g == "tg" else 1.0) - 1e-9
    pts = (novig(b[1:])[0] - novig(a[1:])[0]) * 100
    if abs(pts) >= EVENT_PTS:
        return _sign(pts), abs(pts) >= 2 * EVENT_PTS
    return 0, False


def team_events(R: dict, extra: dict | None = None) -> dict:
    """Corner, gol e tiri in porta di squadra dal primo book che li ha (Pinnacle prima); i tiri in porta anche da
    SOT_BOOK (extra), solo come informazione. {gruppo: {"src": book, "home": (apertura, adesso, dir, forte), ...}}"""
    out = {}
    sources = [(s, R) for s in BOOKMAKERS] + ([(SOT_BOOK, extra)] if extra else [])
    for g in EVENT_GROUPS:
        for s, RR in sources:
            if s == SOT_BOOK and g != "ts":
                continue
            n = (RR["now"].get(s) or {}).get(g) or {}
            if not n:
                continue
            b0 = (RR["base"].get(s) or {}).get(g) or {}
            row = {"src": s}
            for side in ("home", "away"):
                if n.get(side):
                    d, strong = event_move(b0.get(side), n[side], g)
                    row[side] = (b0.get(side), n[side], d, strong)
            out[g] = row
            break
    return out


def coerenza(fam: str, d: int, a: dict, b: dict, evdir: dict) -> int:
    """1 se un altro mercato dice la stessa cosa: asiatico <-> 1X2 o gol della squadra; linea gol <-> GG o gol delle
    squadre; GG <-> linea gol."""
    if fam == "side":
        if a.get("ah") and a.get("x") and b.get("x"):
            x = side_move({"x": a["x"]}, {"x": b["x"]})
            if x and x["meas"] * d >= MIN_BOOK_PTS:
                return 1
        team, other = ("home", "away") if d > 0 else ("away", "home")
        return 1 if evdir.get(f"tg|{team}") == 1 or evdir.get(f"tg|{other}") == -1 else 0
    if fam == "gol":
        g = gg_move(a, b)
        if g and g["meas"] * d >= MIN_BOOK_PTS:
            return 1
        return 1 if evdir.get("tg|home") == d or evdir.get("tg|away") == d else 0
    g = gol_move(a, b)
    return 1 if g and g["meas"] * d >= MIN_BOOK_PTS else 0


def line_force(moves: dict, books: list, d: int) -> int:
    """Per il colore della riga Mercato: 2 = asiatico spostato di un quarto verso la squadra con un movimento vero
    (ampiezza 3, cioe' da 6 punti), 3 = di mezzo gol (ampiezza 5), 1 = il resto; confermato da 2 book."""
    fs = []
    for s in books:
        m = moves.get(s)
        if not m:
            continue
        toward = abs(m["dline"]) >= 0.25 - 1e-9 and _sign(-m["dline"]) == d
        fs.append(3 if toward and abs(m["dline"]) >= 0.5 - 1e-9 and m["lvl"] >= 5 else
                  2 if toward and m["lvl"] >= 3 else 1)
    fs.sort(reverse=True)
    if not fs:
        return 1
    return fs[1] if len(fs) >= 2 else fs[0]


def favourite(odds: dict) -> str | None:
    """Favorita secondo il 1X2 senza margine del primo book che ce l'ha (None se quasi alla pari)."""
    for slug in BOOKMAKERS:
        x = (odds.get(slug) or {}).get("x")
        if x:
            p = novig(x)
            return ("home" if p[0] > p[2] else "away") if abs(p[0] - p[2]) >= FAV_GAP else None
    return None


def goal_pick_line(direction: str, line: float) -> float:
    """Linea x,5 da giocare: Over -> la piu' alta non sopra la linea principale (2,75 -> 2,5), Under -> la piu'
    bassa non sotto (2,25 -> 2,5)."""
    if direction == "over":
        return max(0.5, math.floor(line - 0.5 + 1e-9) + 0.5)
    return math.ceil(line - 0.5 - 1e-9) + 0.5


def _line_prob(now: dict, ref: str | None, line: float, over: bool):
    """Probabilita' (senza margine) di Over/Under 'line' adesso: dal book di riferimento, se no da un altro."""
    for s in [ref] + [b for b in BOOKMAKERS if b != ref]:
        lp = ((now.get(s) or {}).get("lines") or {}).get(f"{line:g}")
        if lp:
            return novig(lp)[0 if over else 1]
    return None


def _team_scores_prob(now: dict, ref: str | None, side: str):
    """Probabilita' (senza margine) che la squadra segni almeno un gol (gol di squadra Over 0,5)."""
    for s in [ref] + [b for b in BOOKMAKERS if b != ref]:
        lp = (((now.get(s) or {}).get("ev_lines") or {}).get(f"tg|{side}") or {}).get("0.5")
        if lp:
            return novig(lp)[0]
    return None


def _price_pair(fam: str, d: int, a: dict, b: dict):
    """Quota che racconta il movimento, prima e dopo: 1 o 2 (squadra), Over della linea gol di adesso, GG."""
    if fam == "side":
        if a.get("x") and b.get("x"):
            i = 0 if d > 0 else 2
            return ("1" if d > 0 else "2", a["x"][i], b["x"][i])
    elif fam == "gol":
        if b.get("ou"):
            key = f"{b['ou'][0]:g}"
            pa, pb = (a.get("lines") or {}).get(key), (b.get("lines") or {}).get(key)
            if pa and pb:
                return (f"Over {fmt_goal(b['ou'][0])}", pa[0], pb[0])
    elif a.get("gg") and b.get("gg"):
        return ("GG", a["gg"][0], b["gg"][0])
    return None


def _half_time(pth: list, d: int):
    """Momento in cui il movimento ha fatto meta' della strada (rispetto a dove e' adesso)."""
    if not pth:
        return None
    final = pth[-1][1]["meas"] * d
    if final <= 0:
        return None
    for t, mv in pth:
        if mv["meas"] * d >= 0.5 * final:
            return t
    return None


def timing(R: dict, sig: dict, ko: datetime | None, at_eff: datetime) -> dict:
    """QUANDO del segnale principale: cambio di linea (quando e' arrivata la linea di adesso) o momento del grosso
    del movimento, chi si e' mosso per primo, cosa e' cambiato dopo le formazioni (ultima ora prima della partita)."""
    fam, d, sref, pth = sig["fam"], sig["dir"], sig["ref"], sig["path"]
    if not pth:
        return {}
    res = {"fam": fam, "late": False}
    final = pth[-1][1]
    key = LINE_KEY.get(fam)
    base_line = ((R["base"].get(sref) or {}).get(key) or [None])[0] if key else None
    if key and base_line is not None and abs(final["dline"]) > 1e-9:
        t_set = None
        for t, mv in pth:
            if abs(mv["dline"] - final["dline"]) > 1e-9:
                t_set = None
            elif t_set is None:
                t_set = t
        res["line"] = (t_set, base_line, base_line + final["dline"])
    else:
        res["t_half"] = _half_time(pth, d)
        res["pp"] = _price_pair(fam, d, R["base"].get(sref) or {}, R["now"].get(sref) or {})
    order = []
    for s in sig["books"]:
        p = pth if s == sref else move_path(R, s, fam, at_eff)
        th = _half_time(p, d)
        if th:
            order.append((th, s))
    res["order"] = sorted(order)
    if ko:
        t60 = ko - timedelta(minutes=FORMAZIONI_MINUTES)
        if R["base_at"] < t60 < at_eff:
            prev = [mv for t, mv in pth if t <= t60]
            m60 = prev[-1] if prev else {"meas": 0.0, "dline": 0.0}     # niente prima: fermo dall'apertura
            delta = (final["meas"] - m60["meas"]) * d
            snap60, snap1 = R["bh"][sref].snapshot(t60, {"main"}), R["now"].get(sref) or {}
            main_t = res["line"][0] if res.get("line") else res.get("t_half")
            if main_t and main_t > t60:
                res["after"] = ("main",)                # il movimento e' arrivato dopo le formazioni
            elif key and abs(final["dline"] - m60["dline"]) > 1e-9 and base_line is not None:
                res["after"] = ("line", base_line + m60["dline"], base_line + final["dline"])
            else:
                dd = delta
                if fam == "side" and abs(dd) < MIN_BOOK_PTS and snap60.get("x") and snap1.get("x"):
                    xm = side_move({"x": snap60["x"]}, {"x": snap1["x"]})      # asiatico fermo: guarda il 1X2
                    dd = xm["meas"] * d if xm else dd
                kind = "more" if dd >= MIN_BOOK_PTS else "back" if dd <= -MIN_BOOK_PTS else "still"
                res["after"] = (kind, _price_pair(fam, d, snap60, snap1))
            fin = final["meas"] * d
            res["late"] = fin > 0 and delta >= 0.5 * fin
    return res


def analyze(R: dict, ko: datetime | None = None, extra: dict | None = None) -> dict:
    """Segnali (asiatico/1X2, linea gol, Goal/No Goal) con la forza, colore per la riga Mercato, pronostico dalle
    quote, eventi di squadra, conferme e QUANDO. Si mostrano (e fanno partire l'avviso) i segnali da
    FORZA_MIN_AVVISO in su."""
    base, now = R["base"], R["now"]
    books = [s for s in BOOKMAKERS if s in base and s in now]
    ref = next((s for s in BOOKMAKERS if s in books), next((s for s in BOOKMAKERS if s in now), None))
    a, b = base.get(ref) or {}, now.get(ref) or {}
    at_eff = R.get("at") or now_utc()
    events = team_events(R, extra)
    evdir = {f"{g}|{side}": row[side][2] for g, row in events.items() for side in ("home", "away") if side in row}
    sigs = []
    for fam in ("side", "gol", "gg"):
        moves = {s: MOVE_FN[fam](base[s], now[s]) for s in books}
        sig = combine(fam, moves)
        if not sig:
            continue
        sref = ref if ref in sig["books"] else (sig["books"][0] if sig["books"] else ref)
        pth = move_path(R, sref, fam, at_eff)
        ratio = tenuta(pth, sig["dir"])
        coe = coerenza(fam, sig["dir"], base.get(sref) or {}, now.get(sref) or {}, evdir)
        forza, acc, ten = forza_of(sig["lvl"], len(sig["books"]), ratio, coe)
        sig.update(moves=moves, ref=sref, path=pth, acc=acc, ten=ten, ratio=ratio, coe=coe, forza=forza)
        if fam == "side":
            sig["force"] = line_force(moves, sig["books"], sig["dir"])
        sigs.append(sig)
    shown = [s for s in sigs if s["forza"] >= FORZA_MIN_AVVISO]
    fav = favourite(base)
    an = {"R": R, "ref": ref, "a": a, "b": b, "base": base, "now": now, "fav": fav, "sigs": sigs, "shown": shown,
          "forza": max((s["forza"] for s in sigs), default=0), "events": events, "color": None, "team": None,
          "picks": [], "ko": ko, "at": at_eff, "timing": {}, "late": False}
    side = next((s for s in shown if s["fam"] == "side"), None)
    gol = next((s for s in shown if s["fam"] == "gol"), None)
    gg = next((s for s in shown if s["fam"] == "gg"), None)
    px = novig(b["x"]) if b.get("x") else None
    if side:
        team = "home" if side["dir"] > 0 else "away"
        if fav is None or team == fav:
            an["color"], an["team"] = ("verde_forte" if side["force"] >= 2 else "verde"), team
            home = team == "home"
            if an["color"] == "verde_forte":
                an["picks"].append(("1" if home else "2", (px[0] if home else px[2]) if px else None))
            else:
                an["picks"].append(("1X" if home else "X2", (px[0] + px[1] if home else px[1] + px[2]) if px else None))
        else:
            an["color"], an["team"] = ("rosso_forte" if side["force"] >= 3 else "rosso"), fav
            home_fav = fav == "home"
            an["picks"].append(("X2" if home_fav else "1X", (px[1] + px[2] if home_fav else px[0] + px[1]) if px else None))
            under = "away" if home_fav else "home"
            p = _team_scores_prob(now, ref, under)
            if p:
                an["picks"].append(("segna", p, under))     # contro quota: la sfavorita segna
    if gol:
        cur = b.get("ou") or next((now[s]["ou"] for s in BOOKMAKERS if (now.get(s) or {}).get("ou")), None)
        if cur:
            over = gol["dir"] > 0
            line = goal_pick_line("over" if over else "under", cur[0])
            an["picks"].append((f"{'Over' if over else 'Under'} {fmt_goal(line)}", _line_prob(now, ref, line, over)))
    if gg:
        yes = gg["dir"] > 0
        gp = next((novig(now[s]["gg"]) for s in [ref] + BOOKMAKERS if (now.get(s) or {}).get("gg")), None)
        an["picks"].append(("GG" if yes else "NG", (gp[0] if yes else gp[1]) if gp else None))
    if shown:
        main = max(shown, key=lambda s: (s["forza"], {"side": 2, "gol": 1, "gg": 0}[s["fam"]]))
        an["timing"] = timing(R, main, ko, at_eff)
        an["late"] = bool(an["timing"].get("late"))
    return an


# =====================================================================
# Nomi, hashtag e messaggi
# =====================================================================
def esc(text) -> str:
    return html.escape(str(text or ""), quote=False)


def split_camel(tag: str) -> str:
    """'AstonVilla' -> 'Aston Villa', 'ParisFC' -> 'Paris FC' (nomi della stampa italiana, come negli hashtag)."""
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", tag or "").strip()


def make_hashtag(text: str) -> str:
    t = unicodedata.normalize("NFKD", (text or "").replace("ß", "ss"))
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    tag = "".join(p[:1].upper() + p[1:] for p in re.findall(r"[A-Za-z0-9]+", t))
    return re.sub(r"^\d+", "", tag)


_STRIP = {"fc", "cf", "ac", "as", "ss", "ssc", "us", "sc", "afc", "cfc", "calcio", "club", "de", "del", "la", "le", "1",
          "rc", "rcd", "ud", "sv", "vfb", "vfl", "tsg", "fsv", "bc", "ogc", "osc", "aj", "sco", "es", "stade", "olympique",
          "real", "town", "city", "united", "hotspur", "albion", "hove", "and", "04", "05", "07", "1899", "1907", "1909",
          "1913", "1901", "29"}


def _tokens(name: str) -> set:
    return {w for w in norm(name).split() if w not in _STRIP and len(w) > 1}


def _similar(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    if inter == 0:
        na, nb = norm(a).replace(" ", ""), norm(b).replace(" ", "")
        return 0.5 if (na and nb and (na in nb or nb in na)) else 0.0
    return inter / min(len(ta), len(tb))


def _name_sim(name: str, m: dict, side: str) -> float:
    return max(_similar(name, m[side]), _similar(name, m[f"{side}_short"]))


def find_fixture(st: dict, m: dict, strict: bool = False) -> str | None:
    """Id OddsPapi della partita del calendario (stesso campionato e orario, nomi simili). Le partite delle coppe
    ce l'hanno gia' (vengono dall'elenco OddsPapi). strict: solo se la scelta e' sicura (per imparare i nomi)."""
    if m.get("fid"):
        return m["fid"]
    pn = st["participants"]
    cands = []
    for fid, rec in st["fixtures"].items():
        start = parse_time(rec.get("start"))
        if rec.get("code") == m["code"] and start and abs((start - m["ko"]).total_seconds()) <= 25 * 60:
            n1, n2 = pn.get(str(rec.get("p1")), ""), pn.get(str(rec.get("p2")), "")
            cands.append((_name_sim(n1, m, "home") + _name_sim(n2, m, "away"), fid))
    if not cands:
        return None
    cands.sort(reverse=True)
    if strict:
        sure = cands[0][0] >= 1.0 and (len(cands) == 1 or cands[0][0] - cands[1][0] >= 0.5)
        return cands[0][1] if sure else None
    if cands[0][0] > 0 or len(cands) == 1:
        return cands[0][1]
    return None


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def learn_teams(st: dict) -> None:
    """Squadre dei 5 campionati imparate dall'elenco OddsPapi (nessuna chiamata): id -> campionato (il filtro delle
    coppe) e id -> nome del calendario, preso dalle partite di campionato abbinate con sicurezza (cosi' nelle coppe
    nomi italiani e hashtag sono gli stessi del campionato)."""
    today = now_utc().astimezone(ROME).date().isoformat()
    top5 = st.get("top5") if isinstance(st.get("top5"), dict) else {}
    for rec in st["fixtures"].values():
        if rec.get("code") in LEAGUES_Q:
            for p in (rec.get("p1"), rec.get("p2")):
                if p is not None:
                    top5[str(p)] = [rec["code"], today]
    fd = st.get("team_fd") if isinstance(st.get("team_fd"), dict) else {}
    pn = st["participants"]
    for m in calendar_matches(finished=True):
        fid = find_fixture(st, m, strict=True)
        rec = st["fixtures"].get(fid) if fid else None
        if not rec or rec.get("p1") is None or rec.get("p2") is None:
            continue
        p1, p2 = str(rec["p1"]), str(rec["p2"])
        n1, n2 = pn.get(p1, ""), pn.get(p2, "")
        if _name_sim(n1, m, "away") + _name_sim(n2, m, "home") > _name_sim(n1, m, "home") + _name_sim(n2, m, "away"):
            p1, p2 = p2, p1             # casa e trasferta invertite nell'elenco: si segue il calendario
        fd[p1], fd[p2] = m["home"], m["away"]
    limit = (now_utc() - timedelta(days=TOP5_KEEP_DAYS)).astimezone(ROME).date().isoformat()
    st["top5"] = {k: v for k, v in top5.items() if isinstance(v, list) and len(v) == 2 and str(v[1]) >= limit}
    st["team_fd"] = {k: v for k, v in fd.items() if k in st["top5"]}


def fd_team_name(st: dict, pid: str) -> str:
    """Nome del calendario di una squadra dei 5 campionati: quello imparato dalle partite di campionato o, se non
    ancora, quello con le stesse parole del nome OddsPapi (solo se uno solo); '' se non si sa."""
    known = (st.get("team_fd") or {}).get(pid)
    if known:
        return known
    name = st["participants"].get(pid, "")
    if not name:
        return ""
    hits = [k for k, v in HASHTAGS.items() if max(_jaccard(name, k), _jaccard(name, split_camel(v))) >= 0.99]
    return hits[0] if len(hits) == 1 else ""


_CLUB_TAGS = {"FC", "SK", "AC", "PFC", "GNK", "HNK", "NK", "FK", "SC", "CF", "AFC", "BK", "IF", "SV", "KV", "CFC",
              "OFK", "PFK", "FF", "TC", "SL", "BSC", "KAA", "KRC", "RSC", "IK", "CS"}


def club_name(name: str) -> str:
    """Nome di una squadra straniera senza le sigle di societa' all'inizio o alla fine: 'SK Sturm Graz' -> 'Sturm Graz',
    'Heart of Midlothian FC' -> 'Heart of Midlothian' (anche l'hashtag viene piu' pulito)."""
    words = str(name or "").split()
    while len(words) > 1 and words[0] in _CLUB_TAGS:
        words = words[1:]
    while len(words) > 1 and words[-1] in _CLUB_TAGS:
        words = words[:-1]
    return " ".join(words)


def cup_team(st: dict, pid: str) -> tuple:
    """Squadra di una partita di coppa: (nome, nome breve). Per quelle dei 5 campionati il nome del calendario, con
    il nome italiano e l'hashtag del campionato; per le altre il nome OddsPapi senza sigle (FC, SK...)."""
    op = st["participants"].get(pid, "")
    if pid in (st.get("top5") or {}):
        fd = fd_team_name(st, pid)
        if fd:
            return fd, split_camel(HASHTAGS.get(fd, "")) or op or fd
    return club_name(op), club_name(op)


def team_names(m: dict) -> dict:
    home = split_camel(HASHTAGS.get(m["home"], "")) or m["home_short"] or m["home"]
    away = split_camel(HASHTAGS.get(m["away"], "")) or m["away_short"] or m["away"]
    tags = [make_hashtag(HASHTAGS.get(m["home"], "")) or make_hashtag(home),
            make_hashtag(HASHTAGS.get(m["away"], "")) or make_hashtag(away)]
    return {"home": home, "away": away, "tags": [t for t in tags if t]}


def fmt_num(x: float, dec: int = 2) -> str:
    return f"{x:.{dec}f}".replace(".", ",")


def fmt_goal(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def fmt_line(h: float, plain: bool = False) -> str:
    if abs(h) < 1e-9:
        return "0"
    return (("-" if plain else "−") if h < 0 else "+") + fmt_goal(abs(h))


def when_text(t: datetime | None) -> str:
    if not t:
        return "?"
    t = t.astimezone(ROME)
    days = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
    return f"{days[t.weekday()]} {t:%H:%M}"


def day_text(t: datetime) -> str:
    t = t.astimezone(ROME)
    return f"{['lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom'][t.weekday()]} {t.day}"


def base_label(base_at: datetime | None, first: bool) -> str:
    return f"dalla prima quota ({when_text(base_at)})" if first else f"dall'apertura ({when_text(base_at)})"


def arrow_p(pa: float, pb: float) -> str:
    """Freccia accanto a una quota (pa, pb = probabilita' prima e adesso): ▼ scesa = piu' probabile, ▲ salita."""
    d = (pb - pa) * 100
    if abs(d) < ARROW_PTS:
        return ""
    return ("▼" if d > 0 else "▲") * (2 if abs(d) >= ARROW_STRONG_PTS else 1)


def arrow_l(la: float, lb: float) -> str:
    """Freccia accanto a una linea: AH ▼ = casa piu' favorita, Gol ▲ = piu' gol attesi; doppia da mezzo gol."""
    d = lb - la
    if abs(d) < 0.01:
        return ""
    return ("▲" if d > 0 else "▼") * (2 if abs(d) >= 0.5 - 1e-9 else 1)


def match_title(names: dict) -> str:
    """'#Venezia – #Udinese': i nomi sono gia' gli hashtag (tocchi e vedi notizie e quote della squadra)."""
    tags = names.get("tags") or []
    if len(tags) == 2:
        return f"#{tags[0]} – #{tags[1]}"
    return f"{esc(names['home'])} – {esc(names['away'])}"


def _pre(lines: list) -> str:
    return "<pre>" + esc("\n".join(lines)) + "</pre>"


def fmt_table(names: dict, a: dict, b: dict, an: dict | None = None) -> str:
    """Tabellina apertura/adesso del book di riferimento (caratteri a larghezza fissa, sta nello schermo del
    telefono). Se mancano i corner di squadra, in fondo i corner della partita."""
    rows = []
    if a.get("x") and b.get("x"):
        pa, pb = novig(a["x"]), novig(b["x"])
        for i, lab in enumerate(("1", "X", "2")):
            rows.append((lab, fmt_num(a["x"][i]), fmt_num(b["x"][i]), arrow_p(pa[i], pb[i])))
    if a.get("ah") and b.get("ah"):
        rows.append((f"AH {names['home'][:11]}", fmt_line(a["ah"][0], True), fmt_line(b["ah"][0], True),
                     arrow_l(a["ah"][0], b["ah"][0])))
    if a.get("ou") and b.get("ou"):
        rows.append(("Linea gol", fmt_goal(a["ou"][0]), fmt_goal(b["ou"][0]), arrow_l(a["ou"][0], b["ou"][0])))
    oa, ob = (a.get("lines") or {}).get("2.5"), (b.get("lines") or {}).get("2.5")
    if oa and ob:
        rows.append(("Over 2,5", fmt_num(oa[0]), fmt_num(ob[0]), arrow_p(novig(oa)[0], novig(ob)[0])))
    if a.get("gg") and b.get("gg"):
        rows.append(("GG", fmt_num(a["gg"][0]), fmt_num(b["gg"][0]), arrow_p(novig(a["gg"])[0], novig(b["gg"])[0])))
    if an is not None and not an["events"].get("tc") and a.get("ct") and b.get("ct"):
        rows.append(("Corner tot.", fmt_goal(a["ct"][0]), fmt_goal(b["ct"][0]), arrow_l(a["ct"][0], b["ct"][0])))
    if not rows:
        return ""
    w = max(len(r[0]) for r in rows)
    return _pre([f"{'':<{w}} {'apert.':>6} {'adesso':>6}"] +
                [f"{r[0]:<{w}} {r[1]:>6} {r[2]:>6} {r[3]}".rstrip() for r in rows])


EVENT_LABEL = {"tc": "Corner", "tg": "Gol squadra", "ts": "Tiri porta"}


def _ev_cell(item) -> tuple:
    if not item:
        return "—", ""
    a, b, d, strong = item
    val = f"{fmt_goal(a[0])}→{fmt_goal(b[0])}" if a and abs(a[0] - b[0]) > 1e-9 else fmt_goal(b[0])
    return val, ("" if d == 0 else ("▲" if d > 0 else "▼") * (2 if strong else 1))


def fmt_teams(an: dict, names: dict) -> tuple:
    """Tabellina SQUADRE: linea di adesso di corner, gol e tiri in porta di ogni squadra, con la freccia
    (▲ = piu' eventi attesi) e 'a→b' se la linea e' cambiata. Ritorna (tabellina, nota sotto)."""
    rows, note = [], ""
    for g in EVENT_GROUPS:
        row = an["events"].get(g)
        if not row or not (row.get("home") or row.get("away")):
            continue
        lab = EVENT_LABEL[g]
        if row["src"] not in BOOKMAKERS:
            lab += "*"
            note = f"* tiri in porta: {BOOK_LABEL.get(row['src'], row['src'])}, solo informazione"
        rows.append((lab, _ev_cell(row.get("home")), _ev_cell(row.get("away"))))
    if not rows:
        return "", ""
    hn, aw_n = names["home"][:11], names["away"][:11]
    lw = max(len(r[0]) for r in rows)
    hw = max(len(hn), max(len(r[1][0]) for r in rows))
    aw = max(len(aw_n), max(len(r[2][0]) for r in rows))
    lines = [f"{'':<{lw}} {hn:>{hw}}    {aw_n:>{aw}}".rstrip()]
    for lab, (hv, ha), (av, aa) in rows:
        lines.append(f"{lab:<{lw}} {hv:>{hw}} {ha:<2} {av:>{aw}} {aa:<2}".rstrip())
    return _pre(lines), note


def _book_arrow(fam: str, m: dict | None) -> str:
    """Freccia di un book nella griglia CONFERME, con lo stesso significato della riga della tabellina:
    AH ▼ = casa piu' favorita, Linea gol ▲ = piu' gol, GG ▼ = GG piu' probabile; = fermo, · non quotato."""
    if m is None:
        return "·"
    if fam in LINE_KEY and abs(m["dline"]) >= 0.25 - 1e-9 and m["dir"] == _sign(-m["dline"] if fam == "side" else m["dline"]):
        up = m["dline"] > 0
        return ("▲" if up else "▼") * (2 if abs(m["dline"]) >= 0.5 - 1e-9 else 1)
    if abs(m["meas"]) < MIN_BOOK_PTS:
        return "="
    pos = m["meas"] > 0
    ar = ("▲" if pos else "▼") if fam == "gol" else ("▼" if pos else "▲")
    return ar * (2 if abs(m["meas"]) >= ARROW_STRONG_PTS else 1)


def fmt_grid(an: dict, names: dict) -> str:
    """Griglia CONFERME: come si sono mossi i 3 book sui mercati del segnale."""
    rows = []
    for s in an["shown"]:
        lab = {"side": f"AH {names['home'][:11]}", "gol": "Linea gol", "gg": "GG"}[s["fam"]]
        rows.append((lab, [_book_arrow(s["fam"], s["moves"].get(bk)) for bk in BOOKMAKERS]))
    if not rows:
        return ""
    w = max(len("Conferme"), max(len(r[0]) for r in rows))
    lines = [(f"{'Conferme':<{w}}  " + "  ".join(f"{BOOK_SHORT[bk]:^4}" for bk in BOOKMAKERS)).rstrip()]
    for lab, cells in rows:
        lines.append((f"{lab:<{w}}  " + "  ".join(f"{c:^4}" for c in cells)).rstrip())
    return _pre(lines)


def quando_text(an: dict, names: dict) -> str:
    """⏱ QUANDO: cambio di linea o grosso del movimento, chi per primo, cosa e' cambiato dopo le formazioni."""
    tm = an.get("timing") or {}
    if not tm:
        return ""
    fam = tm["fam"]
    fl = (lambda v: fmt_line(v, True)) if fam == "side" else fmt_goal
    lab = {"side": f"AH {esc(names['home'])}", "gol": "linea gol", "gg": "GG"}[fam]
    parts = []
    if tm.get("line") and tm["line"][0]:
        t, l0, l1 = tm["line"]
        parts.append(f"{when_text(t)} {lab} {fl(l0)} → {fl(l1)}")
    elif tm.get("t_half"):
        txt = f"il grosso {when_text(tm['t_half'])}"
        if tm.get("pp"):
            txt += f" ({tm['pp'][0]} {fmt_num(tm['pp'][1])} → {fmt_num(tm['pp'][2])})"
        parts.append(txt)
    order = tm.get("order") or []
    if len(order) >= 2:
        if order[-1][0] - order[0][0] <= timedelta(minutes=10):
            who = "tutti insieme"
        else:
            who = f"prima {BOOK_LABEL[order[0][1]]}, poi " + " e ".join(BOOK_LABEL[s] for _, s in order[1:])
        if parts:
            parts[-1] += f" ({who})"
        else:
            parts.append(who)
    aft = tm.get("after")
    if aft:
        if aft[0] == "main":
            parts.append("arrivato dopo le formazioni")
        elif aft[0] == "line":
            parts.append(f"dopo le formazioni: {lab} {fl(aft[1])} → {fl(aft[2])}")
        else:
            pp = aft[1]
            det = f" ({pp[0]} {fmt_num(pp[1])} → {fmt_num(pp[2])})" if pp and abs(pp[1] - pp[2]) > 1e-9 else ""
            parts.append({"more": f"dopo le formazioni si muove ancora{det}",
                          "back": f"dopo le formazioni torna un po' indietro{det}",
                          "still": "dopo le formazioni: ferma"}[aft[0]])
    return "⏱ <b>Quando</b>: " + " · ".join(parts) if parts else ""


def lettura(an: dict, names: dict) -> str:
    """💡 LETTURA: cosa puo' voler dire il movimento, incrociando asiatico, gol e corner, come domanda da verificare."""
    shown = an["shown"]
    side = next((s for s in shown if s["fam"] == "side"), None)
    gol = next((s for s in shown if s["fam"] == "gol"), None)
    gg = next((s for s in shown if s["fam"] == "gg"), None)
    fav, late = an["fav"], an.get("late")
    N = {k: esc(names[k]) for k in ("home", "away")}
    other = {"home": "away", "away": "home"}

    def corner_note(team: str) -> str:
        item = (an["events"].get("tc") or {}).get(team)
        if item and item[2] > 0:
            return f" La linea corner di {N[team]} sale."
        if item and item[2] < 0:
            return f" Ma la linea corner di {N[team]} scende."
        return ""

    txt = ""
    if side and an["color"] in ("verde", "verde_forte"):
        T = an["team"]
        if gol and gol["dir"] < 0:
            txt = (f"{N[T]} più favorita ma meno gol attesi: {N[T]} dovrebbe fare la partita contro una squadra "
                   f"chiusa → occhio a corner e tiri di {N[T]} e all'Under." + corner_note(T))
        elif gol and gol["dir"] > 0:
            txt = (f"{N[T]} più favorita e più gol attesi: il mercato si aspetta che {N[T]} segni → gol e tiri in "
                   f"porta di {N[T]}.")
        else:
            txt = (f"Il mercato crede nella vittoria di {N[T]} e la linea gol non cambia: conferma per il segno e per "
                   f"gli eventi di {N[T]} (tiri in porta, corner).")
    elif side:
        F = an["team"]
        U = other[F]
        txt = (f"La favorita {N[F]} perde fiducia{' proprio dopo le formazioni' if late else ''}. <b>Perché?</b> "
               f"Controlla chi manca in {N[F]}. Se il motivo regge, valuta il contro quota su {N[U]} con linee basse "
               f"(segna, tiri in porta).")
    elif gol:
        if fav and gol["dir"] < 0:
            txt = (f"Meno gol attesi ma {N[fav]} resta favorita: partita chiusa, con {N[fav]} che attacca una squadra "
                   f"bassa → occhio a corner e tiri di {N[fav]}. <b>Perché è scesa?</b> Guarda modulo e formazione "
                   f"di {N[other[fav]]}." + corner_note(fav))
        elif fav:
            txt = (f"Più gol attesi con {N[fav]} favorita: partita aperta → gol e tiri di {N[fav]}, occhio anche al "
                   f"GG. <b>Perché è salita?</b> Guarda le formazioni.")
        elif gol["dir"] < 0:
            txt = ("Meno gol attesi e nessuna favorita: partita bloccata per tutte e due → eventi bassi. "
                   "<b>Perché?</b> Guarda formazioni e moduli.")
        else:
            txt = ("Più gol attesi e partita equilibrata: più eventi per tutte e due, occhio al GG. "
                   "<b>Perché?</b> Guarda formazioni e moduli.")
    elif gg:
        txt = ("Il mercato sposta il Goal verso il GG: tutte e due dovrebbero segnare." if gg["dir"] > 0 else
               "Il mercato sposta il Goal verso il NG: una delle due potrebbe restare a zero.")
    if txt and late and an["color"] not in ("rosso", "rosso_forte"):
        txt += " Il grosso è arrivato dopo le formazioni: guarda chi gioca."
    return f"💡 {txt}" if txt else ""


COLOR_TXT = {"verde_forte": "Verde forte", "verde": "Verde", "rosso": "Rosso", "rosso_forte": "Rosso forte"}


def _prob_change(an: dict, team: str, sep: str = " → ") -> str:
    a, b = an["a"].get("x"), an["b"].get("x")
    if not (a and b):
        return ""
    i = 0 if team == "home" else 2
    return f"{round(novig(a)[i] * 100)}%{sep}{round(novig(b)[i] * 100)}%"


def signal_head(an: dict, s: dict, names: dict, short: bool = False) -> str:
    """Riga del segnale: giudizio (stessi colori del foglio Mercato), forza, book d'accordo."""
    if s["fam"] == "side":
        team = esc(names[an["team"]])
        head = {"verde_forte": f"🟢🟢 <b>Calo forte {team}</b>", "verde": f"🟢 <b>Calo {team}</b>",
                "rosso": f"🔴 <b>Si alza la quota di {team}</b> (favorita)",
                "rosso_forte": f"🔴🔴 <b>Si alza molto la quota di {team}</b> (favorita)"}[an["color"]]
        if short:
            ch = _prob_change(an, an["team"], "→")
            head += (f" {ch}" if ch else "") + f" · {COLOR_TXT[an['color']]}"
    elif s["fam"] == "gol":
        head = "📈 <b>Gol verso l'Over</b>" if s["dir"] > 0 else "📉 <b>Gol verso l'Under</b>"
    else:
        head = "⚽ <b>GG più probabile</b>" if s["dir"] > 0 else "⚽ <b>NG più probabile</b>"
    head += f" · forza <b>{s['forza']}/10</b>"
    if not short:
        head += f" · {len(s['books'])} book su {s['n']}"
    return head


def judgement_short(an: dict, names: dict) -> str:
    """Giudizio del riepilogo: i segnali da FORZA_MIN_AVVISO in su, se no quote stabili (o movimenti leggeri)."""
    if an["shown"]:
        return "\n".join(signal_head(an, s, names, short=True) for s in an["shown"])
    x = an["b"].get("x")
    extra = ""
    if x:
        p = novig(x)
        fav = ("home" if p[0] > p[2] else "away") if abs(p[0] - p[2]) >= FAV_GAP else None
        extra = f" (favorita {esc(names[fav])} {round(max(p[0], p[2]) * 100)}%)" if fav else " (partita equilibrata)"
    weak = f" · movimenti leggeri, forza {an['forza']}/10" if an["sigs"] else ""
    return f"⚪ Quote stabili{extra}{weak}"


def picks_text(an: dict, names: dict, short: bool = False) -> str:
    """🎯 pronostico dalle quote, con la probabilita' di adesso (senza margine) e la quota giusta."""
    out = []
    for p in an["picks"]:
        label = f"{names[p[2]]} segna" if len(p) > 2 else p[0]
        txt = f"<b>{esc(label)}</b>"
        if p[1]:
            txt += f" ({round(p[1] * 100)}% · {'giusta' if short else 'quota giusta'} {fmt_num(1 / p[1])})"
        out.append(txt)
    return "🎯 " + " · ".join(out) if out else ""


def build_message(m: dict, names: dict, an: dict, base_at: datetime, first: bool, note: str = "formazioni uscite",
                  prefix: str = "") -> str:
    """Avviso a ridosso (una partita): segnali con la forza, tabellina, squadre, conferme, quando, lettura,
    colore per la riga Mercato, pronostico con la quota giusta."""
    lg = COMPS_Q.get(m["code"], {"flag": ""})
    rows = [f"{prefix}{lg['flag']} <b>{match_title(names)}</b> · {m['ko'].astimezone(ROME):%H:%M}"]
    rows += [signal_head(an, s, names) for s in an["shown"]]
    rows.append(fmt_table(names, an["a"], an["b"], an))
    for s in an["shown"]:
        rows += andamento(an, s, names)
    teams, tnote = fmt_teams(an, names)
    if teams:
        rows.append(teams)
        if tnote:
            rows.append(f"<i>{esc(tnote)}</i>")
    rows.append(fmt_grid(an, names))
    rows.append(quando_text(an, names))
    rows.append(lettura(an, names))
    if an["color"]:
        rows.append(f"Mercato: <b>{COLOR_TXT[an['color']]}</b> a {esc(names[an['team']])}")
    rows.append(picks_text(an, names))
    rows.append(f"<i>{BOOK_LABEL.get(an['ref'], '')} · {base_label(base_at, first)} → adesso ({when_text(an['at'])})"
                f"{', ' + note if note else ''}</i>")
    return "\n".join(r for r in rows if r)


def signal_price(an: dict, s: dict, names: dict) -> dict | None:
    """La quota che racconta un segnale: 1X2 della squadra del giudizio (calo: la sua quota scende; favorita in
    salita: la sua quota sale), Over/Under sulla linea gol dell'apertura, GG/NG. {label, get, mtypes, falling}"""
    fam, d = s["fam"], s["dir"]
    if fam == "side":
        team = an.get("team") or ("home" if d > 0 else "away")
        idx = 0 if team == "home" else 2
        return {"label": esc(names[team]), "mtypes": {"1x2"},
                "falling": an.get("color") not in ("rosso", "rosso_forte"),
                "get": lambda snap: (snap.get("x") or [None, None, None])[idx]}
    if fam == "gol":
        line = ((an["R"]["base"].get(s["ref"]) or {}).get("ou") or [None])[0]
        if line is None:
            return None
        key, k = f"{line:g}", (0 if d > 0 else 1)
        return {"label": f"{'Over' if d > 0 else 'Under'} {fmt_goal(line)}", "mtypes": {"totals"}, "falling": True,
                "get": lambda snap: ((snap.get("lines") or {}).get(key) or [None, None])[k]}
    k = 0 if d > 0 else 1
    return {"label": "GG" if d > 0 else "NG", "mtypes": {"btts"}, "falling": True,
            "get": lambda snap: (snap.get("gg") or [None, None])[k]}


def andamento(an: dict, s: dict, names: dict) -> list:
    """📊 Andamento della quota del segnale dall'apertura ad adesso, in barre (barra alta = quota alta, una barra per
    ogni tratto di tempo uguale) e, se il movimento e' tornato indietro di almeno un quinto dal suo punto estremo
    (la tenuta che toglie forza), la riga ↩️ con il punto estremo e quando."""
    R = an.get("R") or {}
    sp = signal_price(an, s, names) if R else None
    h = (R.get("bh") or {}).get(s["ref"]) if R else None
    t0, t1 = R.get("base_at"), R.get("at") or an.get("at") or now_utc()
    if not sp or not h or not t0 or t1 <= t0:
        return []

    def price(t):
        return sp["get"](h.snapshot(t, {"main"}, sp["mtypes"]))
    pts, last = [], None
    for i in range(SPARK_POINTS + 1):
        v = price(t0 + (t1 - t0) * (i / SPARK_POINTS)) or last
        pts.append(v)
        last = v
    first = next((v for v in pts if v), None)
    if not first:
        return []
    pts = [v or first for v in pts]
    probs = [1.0 / v for v in pts]
    span = max(max(probs) - min(probs), SPARK_MIN_PTS / 100.0)
    lo = (max(probs) + min(probs) - span) / 2
    bars = "".join(SPARK[max(0, min(7, int(round((1 - (p - lo) / span) * 7))))] for p in probs)
    out = [f"📊 Andamento quota {sp['label']}: {fmt_num(pts[0])} {bars} {fmt_num(pts[-1])}"]
    if s.get("ratio", 1.0) < TENUTA_OK:
        best, best_t = None, None
        for t in [t0] + h.change_times({"main"}, t0, t1, sp["mtypes"]):
            v = price(t)
            if v and (best is None or (v < best if sp["falling"] else v > best)):
                best, best_t = v, t
        how = "un po' indietro (forza −1)" if s["ratio"] >= TENUTA_MEZZA else "indietro per più di metà (forza −2)"
        beyond = best and (best <= min(pts[0], pts[-1]) - 0.01 if sp["falling"] else best >= max(pts[0], pts[-1]) + 0.01)
        if beyond:
            out.append(f"↩️ Era {'scesa' if sp['falling'] else 'salita'} fino a {fmt_num(best)} ({when_text(best_t)}), "
                       f"adesso {fmt_num(pts[-1])}: è tornata {how}")
        else:
            peak = max(s.get("path") or [(None, {"meas": 0.0})], key=lambda it: it[1]["meas"] * s["dir"])[0]
            out.append(f"↩️ Il movimento è tornato {how}" + (f" dal punto più alto ({when_text(peak)})" if peak else ""))
    return out


def riepilogo_row(m: dict, names: dict, an: dict | None) -> str:
    """Una partita nel riepilogo: titolo, una riga di quote (adesso, con le frecce), giudizio con la forza e
    pronostico con la quota giusta."""
    title = f"<b>{match_title(names)}</b> {m['ko'].astimezone(ROME):%H:%M}"
    if not an or not an["b"]:
        return f"{title}\n<i>quote non trovate su OddsPapi</i>"
    a, b = an["a"], an["b"]
    bits = []
    if b.get("x"):
        pa, pb = (novig(a["x"]) if a.get("x") else None), novig(b["x"])
        bits.append("1X2 " + " ".join(fmt_num(b["x"][i]) + (arrow_p(pa[i], pb[i]) if pa else "") for i in range(3)))
    if b.get("ah"):
        old = f"{fmt_line(a['ah'][0])}→" if a.get("ah") and abs(a["ah"][0] - b["ah"][0]) > 0.01 else ""
        bits.append(f"AH {old}{fmt_line(b['ah'][0])}")
    if b.get("ou"):
        old = f"{fmt_goal(a['ou'][0])}→" if a.get("ou") and abs(a["ou"][0] - b["ou"][0]) > 0.01 else ""
        bits.append(f"Gol {old}{fmt_goal(b['ou'][0])}")
    ob, oa = (b.get("lines") or {}).get("2.5"), (a.get("lines") or {}).get("2.5")
    if ob:
        bits.append("O2,5 " + fmt_num(ob[0]) + (arrow_p(novig(oa)[0], novig(ob)[0]) if oa else ""))
    if b.get("gg"):
        bits.append("GG " + fmt_num(b["gg"][0]) + (arrow_p(novig(a["gg"])[0], novig(b["gg"])[0]) if a.get("gg") else ""))
    rows = [title, " · ".join(bits), judgement_short(an, names)]
    if an["shown"]:
        main = max(an["shown"], key=lambda s: (s["forza"], {"side": 2, "gol": 1, "gg": 0}[s["fam"]]))
        rows += andamento(an, main, names)
    rows.append(picks_text(an, names, short=True))
    return "\n".join(r for r in rows if r)


LEGEND_SHORT = ("<i>▼ quota scesa (più probabile) · ▲ salita · AH = handicap della squadra di casa · 📊 andamento "
                "della quota dall'apertura (barra alta = quota alta) · ↩️ tornata indietro · forza 1-10: "
                f"da {FORZA_FORTE} forte, {FORZA_MIN_AVVISO}-{FORZA_FORTE - 1} medio, sotto {FORZA_MIN_AVVISO} "
                "rumore · 🎯 pronostico solo dall'andamento delle quote, tra parentesi la probabilità di adesso e la "
                "quota giusta (senza margine)</i>")

LEGEND = ("📖 <b>Come leggere i messaggi delle quote</b>\n\n"
          "<b>Quando arrivano</b>\n"
          f"• ore {RIEPILOGO_HOUR}: <b>riepilogo</b> delle partite di domani, un messaggio per campionato o coppa\n"
          f"• {RIDOSSO_MINUTES} minuti prima della partita (formazioni uscite): solo se un movimento ha "
          f"<b>forza {FORZA_MIN_AVVISO}/10 o più</b>\n"
          "• venerdì alle 15 (martedì se c'è il turno infrasettimanale): <b>apertura</b>, le quote di riferimento\n"
          f"• lunedì alle 15: <b>apertura delle coppe</b> ({CUPS_Q['CL']['flag']} Champions, {CUPS_Q['EL']['flag']} "
          f"Europa e {CUPS_Q['ECL']['flag']} Conference League"
          + (": solo le partite con almeno una squadra dei 5 campionati" if CUPS_ONLY_TOP5 else
             ": tutte le partite; a luglio e agosto, nei preliminari, solo quelle con squadre dei 5 campionati")
          + ")\n\n"
          "<b>Forza del segnale (1-10)</b>\n"
          "quanto si è mosso (linea asiatica o linea gol spostata = tanto) + quanti book sono d'accordo + se ha "
          "tenuto o è tornato indietro + se un altro mercato dice la stessa cosa\n"
          f"{FORZA_FORTE}-10 forte · {FORZA_MIN_AVVISO}-{FORZA_FORTE - 1} medio, da farsi domande · sotto "
          f"{FORZA_MIN_AVVISO} rumore: a {RIDOSSO_MINUTES} minuti non arriva\n\n"
          "<b>Tabella</b> (Pinnacle, apertura e adesso)\n"
          "▼ quota scesa = più probabile · ▲ quota salita · doppia freccia = movimento forte\n"
          "AH = handicap asiatico della squadra di casa (▼ = casa più favorita) · Linea gol (▲ = più gol attesi) · "
          "Over 2,5 · GG\n\n"
          "📊 <b>Andamento</b>: la quota del segnale dall'apertura ad adesso, una barra per ogni tratto di tempo "
          "uguale; barra alta = quota alta (▇▆▄▂▁ = la quota è scesa piano piano, ▇▇▇▇▁ = è scesa tutta alla fine)\n"
          "↩️ <b>Tornata indietro</b>: era arrivata più in là e ha restituito almeno un quinto del movimento; c'è il "
          "punto più basso (o più alto) e quando. Un po' indietro: forza −1 · più di metà: forza −2\n\n"
          "<b>Squadre</b>: la linea di adesso di corner, gol e tiri in porta di ogni squadra (Pinnacle; * = altro "
          "book, solo informazione) · ▲ = più eventi attesi · a→b = linea cambiata\n"
          "<b>Conferme</b>: come si sono mossi Pinnacle, Sbobet e Singbet, con le stesse frecce della tabella "
          "(= fermo, · non quotato)\n"
          "⏱ <b>Quando</b>: a che ora si è mosso, chi per primo e cosa è cambiato dopo le formazioni\n"
          "💡 <b>Lettura</b>: cosa può voler dire il movimento, come domanda da verificare: non è una verità\n\n"
          "<b>Giudizio</b> (colore per la riga «Mercato» del foglio)\n"
          "🟢🟢 calo forte: linea asiatica spostata verso la squadra → Verde forte\n"
          "🟢 calo: stessa linea, quota scesa → Verde\n"
          "🔴 si alza la quota della favorita → Rosso · 🔴🔴 di mezzo gol → Rosso forte\n"
          "📈 📉 linea gol su o giù · ⚽ Goal/No Goal\n\n"
          "<b>🎯 Pronostico dalle quote</b> (solo dall'andamento delle quote, non è un'analisi della partita)\n"
          "calo forte → segno secco · calo → doppia chance · favorita in salita → doppia chance contro di lei e la "
          "sfavorita che segna · linea gol su → Over · giù → Under · GG/NG\n"
          "Tra parentesi la probabilità di adesso senza margine e la <b>quota giusta</b>: se il tuo book paga di "
          "più, c'è valore.")


# =====================================================================
# Telegram: argomento "Quote"
# =====================================================================
_THREAD_GONE = ("message thread not found", "thread not found", "topic_deleted", "topic deleted",
                "topic_id_invalid", "message_thread_id_invalid")
class QuoteTopic:
    def __init__(self, st: dict):
        self.st = st
        news = load_json(STATE_FILE, {})
        tg = news.get("telegram") or {}
        self.group_id = tg.get("group_id") if tg.get("ready") else None
        self.recreated = False

    def _create(self) -> int | None:
        payload = {"chat_id": self.group_id, "name": TOPIC_NAME, "icon_color": TOPIC_COLOR}
        res = telegram_api("createForumTopic", payload)
        if not res and "icon" in (res.description or "").lower():
            payload.pop("icon_color")
            res = telegram_api("createForumTopic", payload)
        tid = res.result.get("message_thread_id") if res and isinstance(res.result, dict) else None
        if tid:
            self.st["topic"] = {"group_id": self.group_id, "thread_id": tid}
            print(f"Creato l'argomento «{TOPIC_NAME}» (id {tid})")
            if send_telegram_message(LEGEND, disable_preview=True, chat_id=self.group_id, thread_id=tid):
                self.st["legend"] = LEGEND_VERSION
        return tid

    def target(self):
        if not self.group_id:
            return None, None
        topic = self.st.get("topic") or {}
        if topic.get("group_id") == self.group_id and topic.get("thread_id"):
            return self.group_id, topic["thread_id"]
        tid = self._create()
        return (self.group_id, tid) if tid else (None, None)

    def send(self, text: str) -> bool:
        if MUTO:                        # prova muta: il messaggio va solo nel registro
            print("[MUTO] messaggio:\n" + re.sub(r"</?(b|i|pre)>", "", text) + "\n[/MUTO]")
            return True
        for _ in range(2):
            chat_id, thread_id = self.target()
            res = send_telegram_message(text, disable_preview=True, chat_id=chat_id, thread_id=thread_id)
            if res:
                return True
            desc = (res.description or "").lower()
            if thread_id and any(k in desc for k in _THREAD_GONE) and not self.recreated:
                print("[WARN] l'argomento Quote non esiste piu': lo ricreo")
                self.recreated = True
                self.st["topic"] = {}
                continue
            return False
        return False


# =====================================================================
# Orari: cosa c'e' da fare adesso
# =====================================================================
def kickoff_groups(cal: list) -> list:
    groups = []
    for m in cal:
        if groups and (m["ko"] - groups[-1]["first"]).total_seconds() <= MERGE_MINUTES * 60:
            groups[-1]["matches"].append(m)
            groups[-1]["last"] = m["ko"]
        else:
            groups.append({"first": m["ko"], "last": m["ko"], "matches": [m]})
    return groups


def apertura_matches(cal: list, now: datetime) -> list:
    """Partite che hanno come apertura le 15:00 di oggi (venerdi': weekend; martedi': turno infrasettimanale;
    lunedi': coppe)."""
    loc = now.astimezone(ROME)
    ap = datetime(loc.year, loc.month, loc.day, APERTURA_HOUR, tzinfo=ROME).astimezone(timezone.utc)
    return [m for m in cal if m["ko"] > now and apertura_time(m["ko"], m["code"]) == ap]


def due_apertura(st: dict, cal: list, now: datetime) -> str | None:
    loc = now.astimezone(ROME)
    if not (APERTURA_HOUR <= loc.hour < APERTURA_HOUR + APERTURA_WINDOW_HOURS):
        return None
    key = f"A|{loc:%Y-%m-%d}T{APERTURA_HOUR:02d}"
    if key in st["done"]:
        return None
    if loc.weekday() == CUP_APERTURA_DAY:
        return key              # coppe: l'elenco si legge comunque (le partite delle coppe arrivano da li')
    if loc.weekday() not in APERTURA_DAYS or not apertura_matches(cal, now):
        return None             # martedi' senza turno infrasettimanale
    return key


def due_riepilogo(st: dict, cal: list, now: datetime):
    """Alle 19 (fino alle 23) il riepilogo delle partite di domani, se ce ne sono."""
    loc = now.astimezone(ROME)
    if not (RIEPILOGO_HOUR <= loc.hour < RIEPILOGO_HOUR + RIEPILOGO_WINDOW_HOURS):
        return None, []
    day = (loc + timedelta(days=1)).date()
    key = f"S|{day.isoformat()}"
    matches = [m for m in cal if m["ko"].astimezone(ROME).date() == day]
    if key in st["done"] or not matches:
        return None, []
    return key, matches


def next_day_matches(cal: list, now: datetime) -> list:
    """Per il riepilogo a mano: le partite di domani, se no quelle del prossimo giorno con partite."""
    tomorrow = (now.astimezone(ROME) + timedelta(days=1)).date()
    day_m = [m for m in cal if m["ko"].astimezone(ROME).date() == tomorrow]
    if day_m:
        return day_m
    fut = [m for m in cal if m["ko"] > now]
    if not fut:
        return []
    d = fut[0]["ko"].astimezone(ROME).date()
    return [m for m in fut if m["ko"].astimezone(ROME).date() == d]


def due_ridosso(st: dict, cal: list, now: datetime):
    for g in kickoff_groups(cal):       # tutte le partite, anche quelle gia' iniziate: cosi' i gruppi non cambiano
        start_at = g["first"] - timedelta(minutes=RIDOSSO_MINUTES)
        latest = g["first"] - timedelta(minutes=RIDOSSO_LATEST_MINUTES)
        key = f"R|{g['first'].isoformat()[:16]}"
        if start_at <= now <= latest and key not in st["done"] and \
                any(match_key(m) not in st["done"] for m in g["matches"]):
            return key, g
    return None, None


# =====================================================================
# Azioni
# =====================================================================
def do_apertura(st: dict, topic: QuoteTopic, key: str | None, cal: list, force: bool = False) -> list:
    """Aggiorna l'elenco delle partite (lunedi' le coppe, martedi' e venerdi' i campionati, a mano tutto) e lo dice
    con un messaggio breve. Se l'elenco non arriva si riprova al giro dopo (al massimo APERTURA_TRIES volte).
    Ritorna il calendario aggiornato."""
    now = now_utc()
    cups_day = bool(key) and now.astimezone(ROME).weekday() == CUP_APERTURA_DAY
    which = "coppe" if cups_day else "campionati" if key else "tutto"
    try:
        n = refresh_fixtures(st, force=force, which=which)
    except QuotaExhausted:
        raise
    except Exception as e:      # noqa: BLE001
        if not key:
            raise
        tries = st["ap_tries"] = {key: (st.get("ap_tries") or {}).get(key, 0) + 1}
        print(f"[WARN] elenco partite non letto ({e}): tentativo {tries[key]} di {APERTURA_TRIES}")
        if tries[key] >= APERTURA_TRIES:
            st["done"].append(key)
            topic.send(f"⚠️ Bot quote: elenco delle partite non aggiornato ({esc(str(e)[:150])}).")
        return cal
    st.pop("ap_tries", None)
    if key:
        st["done"].append(key)
    learn_teams(st)
    cal = calendar_matches(st)
    soon = apertura_matches(cal, now) if key else [m for m in cal if now < m["ko"] <= now + timedelta(days=4)]
    if not soon:
        print("Apertura: nessuna partita da segnalare")
        return cal
    per = {}
    for m in soon:
        per[m["code"]] = per.get(m["code"], 0) + 1
    detail = " · ".join(f"{COMPS_Q[c]['flag']} {per[c]}" for c in COMPS_Q if c in per)
    last = max(m["ko"] for m in soon)
    head = (f"📸 <b>Apertura {'delle coppe' if cups_day else 'delle quote'}</b> ({when_text(now)}): riferimento "
            f"fissato per {len(soon)} partite fino a {when_text(last).split()[0]}") if key else \
        f"📸 <b>Elenco partite aggiornato a mano</b> ({when_text(now)}): {len(soon)} partite nei prossimi 4 giorni"
    cups, left = "", cup_matches(st, now, last)[1]
    if left:
        cups = (f"Coppe: solo le partite con almeno una squadra dei 5 campionati"
                f"{'' if CUPS_ONLY_TOP5 else ' (preliminari)'}, {left} lasciate fuori · ")
    topic.send(f"{head} · {detail}\n"
               f"<i>{cups}Riepilogo alle {RIEPILOGO_HOUR} del giorno prima, avvisi {RIDOSSO_MINUTES} minuti prima "
               f"solo da forza {FORZA_MIN_AVVISO}/10 · elenco OddsPapi {n} partite · chiamate usate {st['calls']}/"
               f"{st.get('limit', MONTH_LIMIT)}</i>")
    return cal


def match_key(m: dict) -> str:
    """Chiave di una partita (per non rifarla). Per le coppe con l'id OddsPapi: i nomi possono cambiare quando il bot
    impara quelli italiani dalle partite di campionato."""
    if m["code"] in CUPS_Q and m.get("fid"):
        return f"M|{m['ko'].isoformat()[:16]}|{m['code']}|{m['fid']}"
    return f"M|{m['ko'].isoformat()[:16]}|{m['code']}|{m['home']}"


def stats_entry(m: dict, an: dict, src: str) -> dict:
    """Numeri di una partita controllata (per tarare le soglie): forza e pezzi della forza di ogni segnale."""
    return {"k": match_key(m), "src": src, "lg": m["code"], "m": f"{m['home_short']}-{m['away_short']}",
            "f": an["forza"], "sent": bool(an["shown"]),
            "sig": [[s["fam"], s["dir"], s["forza"], s["lvl"], s["acc"], s["ten"], s["coe"]] for s in an["sigs"]],
            "t": now_utc().isoformat(timespec="minutes")}


def save_stats(st: dict, entry: dict) -> None:
    st["stats"] = [e for e in st.get("stats", []) if not (e.get("k") == entry["k"] and e.get("src") == entry["src"])]
    st["stats"].append(entry)
    st["stats"] = st["stats"][-STATS_KEEP:]


def add_sot(st: dict, fid: str, m: dict, R: dict, an: dict, force: bool = False) -> dict:
    """Tiri in porta di squadra da SOT_BOOK (solo informazione) se nessuno dei 3 book li quota: una lettura in piu'
    dello storico (gratis). Se in SOT_MAX_TRIES partite non li ha mai, smette di chiederli."""
    if not SOT_BOOK or an["events"].get("ts"):
        return an
    if not any(len(v) > 4 and v[4] == "ts" for v in (st.get("markets") or {}).values()):
        return an
    sot = st.setdefault("sot", {"tries": 0, "hits": 0})
    if sot.get("hits", 0) == 0 and sot.get("tries", 0) >= SOT_MAX_TRIES:
        return an
    sot["tries"] = sot.get("tries", 0) + 1
    try:
        R2 = read_history(st, fid, apertura_time(m["ko"], m["code"]), at=R.get("at"), force=force,
                          books=[SOT_BOOK])
    except QuotaExhausted:
        raise
    except Exception as e:      # noqa: BLE001
        print(f"  tiri in porta ({SOT_BOOK}) non letti: {e}")
        return an
    if (R2["now"].get(SOT_BOOK) or {}).get("ts"):
        sot["hits"] = sot.get("hits", 0) + 1
        return analyze(R, m["ko"], extra=R2)
    return an


def do_ridosso(st: dict, topic: QuoteTopic, key: str | None, group: dict | None, cal: list, force: bool = False) -> int:
    """Per ogni partita del gruppo: storico (gratis) -> apertura e adesso sui 3 book -> forza dei segnali ->
    messaggio se almeno un segnale arriva a FORZA_MIN_AVVISO. Ogni partita controllata viene segnata e salvata
    subito: se il giro si interrompe (o finisce il tempo), il giro dopo riprende dalle partite mancanti, senza
    doppioni."""
    manual = key is None
    if group is None:                       # controllo a mano: il prossimo gruppo di partite
        groups = kickoff_groups([m for m in cal if m["ko"] > now_utc()])
        if not groups:
            print("Nessuna partita in arrivo nel calendario")
            return 0
        group = groups[0]
    todo = [m for m in group["matches"] if manual or match_key(m) not in st["done"]]
    missing = [m for m in todo if not find_fixture(st, m)]
    last = parse_time(st.get("refresh_at"))
    if missing and (force or not last or now_utc() - last > timedelta(hours=REFRESH_MIN_HOURS)):
        print(f"{len(missing)} partite senza id OddsPapi: aggiorno l'elenco")
        refresh_fixtures(st, force=force)
    sent = checked = 0
    unfinished = False
    for m in todo:
        if not manual and time.monotonic() - _START > RUN_BUDGET_SECONDS:
            print("Tempo del giro finito: le partite rimaste al prossimo giro (tra 5 minuti)")
            unfinished = True
            break
        names = team_names(m)
        fid = find_fixture(st, m)
        if not fid:
            print(f"  {names['home']} - {names['away']}: non trovata su OddsPapi")
        else:
            try:
                R = read_history(st, fid, apertura_time(m["ko"], m["code"]), force=force)
                checked += 1
            except QuotaExhausted:
                raise
            except Exception as e:      # noqa: BLE001
                print(f"  {names['home']} - {names['away']}: storico non letto ({e}): riprovo al prossimo giro")
                unfinished = True
                continue
            an = analyze(R, m["ko"])
            if an["shown"]:
                an = add_sot(st, fid, m, R, an, force=force)
            save_stats(st, stats_entry(m, an, "a mano" if manual else "ridosso"))
            sig_txt = ", ".join(f"{s['fam']} {s['forza']}" for s in an["sigs"]) or "nessun movimento"
            if not an["shown"]:
                print(f"  {names['home']} - {names['away']}: sotto la soglia ({sig_txt})")
            elif topic.send(build_message(m, names, an, R["base_at"], R["first"],
                                          "controllo a mano" if manual else "formazioni uscite")):
                sent += 1
                print(f"  {names['home']} - {names['away']}: SEGNALE ({sig_txt}) -> inviato")
                time.sleep(SEND_DELAY_GROUP_SECONDS)
            else:
                print(f"  {names['home']} - {names['away']}: SEGNALE, ma Telegram non ha accettato: riprovo")
                unfinished = True
                continue
        if not manual:
            st["done"].append(match_key(m))
            save_qstate(st)
    if key and not unfinished:
        st["done"].append(key)
    if manual and sent == 0:
        topic.send(f"🔎 Controllo a mano delle partite di {when_text(group['first'])}: nessun movimento da "
                   f"{FORZA_MIN_AVVISO}/10 in su dall'apertura ({checked} partite lette su {len(todo)}).")
    st["log"].append(f"{now_utc().isoformat(timespec='minutes')} {'a mano' if manual else 'ridosso'} "
                     f"{len(todo)} partite, {checked} lette, {sent} messaggi{' (da finire)' if unfinished else ''}")
    return sent


def riepilogo_messages(rows: list, header_day: str, preview: bool) -> list:
    """Un messaggio per campionato (spezzato se troppo lungo); la legenda breve in fondo all'ultimo."""
    found = [r for r in rows if r.get("base")]
    common_base = max({r["base"] for r in found}, key=lambda b: sum(r["base"] == b for r in found)) if found else ""
    common_ref = max({r["ref"] for r in found}, key=lambda b: sum(r["ref"] == b for r in found)) if found else ""
    msgs = []
    for code, lg in COMPS_Q.items():
        lrows = sorted((r for r in rows if r["code"] == code), key=lambda r: r["ko"])
        if not lrows:
            continue
        head = (f"{'🧪 ESEMPIO · ' if preview else ''}📋 {lg['flag']} <b>{lg['name']} · {header_day}</b>\n"
                f"<i>quote {BOOK_LABEL.get(common_ref, '')} · movimenti {common_base} a adesso</i>")
        chunk = head
        for r in lrows:
            text = r["text"]
            notes = [n for n in (r.get("base") if r.get("base") != common_base else "",
                                 f"quote {BOOK_LABEL.get(r.get('ref'), '')}" if r.get("ref") != common_ref else "") if n]
            if r.get("base") and notes:
                text += f"\n<i>({', '.join(notes)})</i>"
            if len(chunk) + len(text) > 3800:
                msgs.append(chunk)
                chunk = head
            chunk += "\n\n" + text
        msgs.append(chunk)
    if msgs:
        msgs[-1] += "\n\n" + LEGEND_SHORT
    return msgs


def do_riepilogo(st: dict, topic: QuoteTopic, key: str | None, matches: list, force: bool = False,
                 preview: bool = False) -> list:
    """Riepilogo delle partite di un giorno: ogni partita viene letta (storico, gratis) e la sua riga salvata subito;
    se il tempo del giro finisce si riprende al giro dopo. Quando ci sono tutte: un messaggio per campionato.
    Ritorna le analisi fatte in questo giro (per l'esempio della prova)."""
    tag = key or ("prova" if preview else "mano")
    rp = st.get("riep") if isinstance(st.get("riep"), dict) else {}
    if rp.get("key") != tag:
        rp = {"key": tag, "rows": {}, "fail": {}}
    st["riep"] = rp
    todo = [m for m in matches if match_key(m) not in rp["rows"]]
    missing = [m for m in todo if not find_fixture(st, m)]
    last = parse_time(st.get("refresh_at"))
    if missing and (force or not last or now_utc() - last > timedelta(hours=REFRESH_MIN_HOURS)):
        print(f"{len(missing)} partite senza id OddsPapi: aggiorno l'elenco")
        refresh_fixtures(st, force=force)
    done_now, unfinished = [], False
    for m in todo:
        if not force and time.monotonic() - _START > RUN_BUDGET_SECONDS:
            print("Riepilogo: tempo del giro finito, continuo al prossimo giro")
            unfinished = True
            break
        names = team_names(m)
        mk = match_key(m)
        fid = find_fixture(st, m)
        an, base_at, first = None, None, False
        if fid:
            try:
                R = read_history(st, fid, apertura_time(m["ko"], m["code"]), force=force)
                an = analyze(R, m["ko"])
                base_at, first = R["base_at"], R["first"]
                done_now.append((m, names, an, base_at, first))
            except QuotaExhausted:
                raise
            except Exception as e:      # noqa: BLE001
                rp["fail"][mk] = rp["fail"].get(mk, 0) + 1
                print(f"  {names['home']} - {names['away']}: storico non letto ({e})")
                if rp["fail"][mk] < 3 and not force:     # a mano non si aspetta: riga "quote non trovate"
                    unfinished = True
                    continue
        else:
            print(f"  {names['home']} - {names['away']}: non trovata su OddsPapi")
        rp["rows"][mk] = {"code": m["code"], "ko": m["ko"].isoformat(), "text": riepilogo_row(m, names, an),
                          "base": base_label(base_at, first) if an and an["b"] else "", "ref": an["ref"] if an else ""}
        if key:
            save_qstate(st)
    if unfinished:
        return done_now
    rows = [rp["rows"][match_key(m)] for m in matches if match_key(m) in rp["rows"]]
    if rows:
        day = matches[0]["ko"].astimezone(ROME)
        today = now_utc().astimezone(ROME).date()
        rel = "oggi " if day.date() == today else "domani " if day.date() == today + timedelta(days=1) else ""
        for text in riepilogo_messages(rows, rel + day_text(day), preview):
            topic.send(text)
            time.sleep(SEND_DELAY_GROUP_SECONDS)
    if key:
        st["done"].append(key)
    st["riep"] = {}
    st["log"].append(f"{now_utc().isoformat(timespec='minutes')} riepilogo {tag}: {len(rows)} partite")
    return done_now


def send_legend(st: dict, topic: QuoteTopic, force: bool = False) -> None:
    """La legenda (come leggere i messaggi): una volta, e di nuovo solo se cambia."""
    if MUTO:
        return
    if (force or st.get("legend") != LEGEND_VERSION) and topic.send(LEGEND):
        st["legend"] = LEGEND_VERSION


def snapshot_main(fx, meta: dict) -> dict:
    """Per la prova: linee principali di Pinnacle nell'elenco (segnate 'mainLine' dal book), da confrontare con lo storico."""
    out = {}
    try:
        markets = fx["bookmakerOdds"]["pinnacle"]["markets"]
    except (KeyError, TypeError):
        return out
    for mid, mk in markets.items():
        info = meta.get(str(mid))
        if not info or len(info) < 4 or info[2] not in ("fulltime", "result", ""):
            continue
        pls = [next(iter(((mk.get("outcomes") or {}).get(str(o)) or {}).get("players", {}).values()), {}) for o in info[3]]
        if not all(isinstance(p, dict) and p.get("price") for p in pls):
            continue
        prices = [float(p["price"]) for p in pls]
        if info[0] == "1x2" and str(mid) == "101":
            out["x"] = prices
        elif any(p.get("mainLine") for p in pls):
            line = AH_HOME_SIGN * info[1] if info[0] == "spreads" else info[1]
            out.setdefault("ah" if info[0] == "spreads" else "ou", []).append([line] + prices)
    return out


def _safe_account(acc) -> str:
    """Dell'account solo i numeri del piano (mai email o dati personali: il registro e' pubblico)."""
    out = []
    for sub in (acc or {}).get("subscriptions") or []:
        if isinstance(sub, dict):
            out.append({k: sub.get(k) for k in ("plan", "request_limit", "request_count", "websocket_access", "is_active")})
    return json.dumps(out)


def describe(an: dict) -> str:
    """Per il registro: segnali con i pezzi della forza."""
    out = []
    for s in an["sigs"]:
        mv = s["moves"].get(s["ref"]) or {}
        out.append(f"{s['fam']} {'+' if s['dir'] > 0 else '-'} forza {s['forza']} = 2x{s['lvl']} "
                   f"({abs(mv.get('meas', 0)):.1f} punti, linea {mv.get('dline', 0):+g}) book {s['acc']:+d} "
                   f"({','.join(s['books'])}) tenuta {s['ten']:+d} ({s['ratio']:.2f}) mercato +{s['coe']}")
    return " | ".join(out) or "nessun movimento"


def query_codes(query: str) -> set:
    """Competizioni chieste per codice o nome (es. "CL", "Europa League", "coppe", "campionati"); vuoto = una squadra."""
    q = norm(query)
    if q in ("coppe", "coppa"):
        return set(CUPS_Q)
    if q in ("campionati", "campionato"):
        return set(LEAGUES_Q)
    return {c for c in COMPS_Q if q and (norm(c) == q or norm(COMPS_Q[c]["name"]) == q)}


def filter_matches(matches: list, query: str) -> list:
    """Partite di una squadra (es. "Roma") o di una competizione (SA, PL, PD, BL1, FL1, CL, EL, ECL, "coppe",
    "campionati")."""
    q = norm(query)
    if not q:
        return matches
    codes = query_codes(query)
    if codes:
        return [m for m in matches if m["code"] in codes]
    return [m for m in matches if any(q in norm(x) for x in (
        m["home"], m["away"], m["home_short"], m["away_short"],
        split_camel(HASHTAGS.get(m["home"], "")), split_camel(HASHTAGS.get(m["away"], ""))))]


TEST_LOOKAHEAD_DAYS = 15        # prova: elenco partite fino a 15 giorni (per vedere anche le coppe della settimana dopo)


def path_text(R: dict, s: dict, ko: datetime) -> str:
    """Per il registro (rivedi di una squadra): come si e' mosso un segnale dall'apertura (punti di probabilita'
    verso la sua direzione), nei momenti in cui cambia di almeno 1 punto o di linea, con il punto piu' alto e il
    valore alle 19 del giorno prima (l'ora del riepilogo)."""
    pth, d, h = s.get("path") or [], s["dir"], R["bh"].get(s["ref"])
    if not pth or not h:
        return "-"
    steps, last = [], None
    for t, mv in pth:
        v = mv["meas"] * d
        if last is None or abs(v - last[0]) >= 1.0 or abs(mv["dline"] - last[1]) > 1e-9:
            steps.append(f"{when_text(t)} {v:+.1f}" + (f" (linea {mv['dline']:+g})" if abs(mv["dline"]) > 1e-9 else ""))
            last = (v, mv["dline"])
    if len(steps) > 14:
        steps = steps[:7] + ["..."] + steps[-7:]
    peak_t, peak = max(((t, mv["meas"] * d) for t, mv in pth), key=lambda it: it[1])
    rie = (ko.astimezone(ROME) - timedelta(days=1)).replace(hour=RIEPILOGO_HOUR, minute=0, second=0, microsecond=0)
    before = [mv["meas"] * d for t, mv in pth if t <= rie]

    def x_at(t):
        x = h.snapshot(t, {"main"}).get("x")
        return "/".join(fmt_num(v) for v in x) if x else "-"
    return (f"{' → '.join(steps)} | alle {RIEPILOGO_HOUR} del giorno prima {(before[-1] if before else 0.0):+.1f} "
            f"(1X2 {x_at(rie)}) | massimo {peak:+.1f} {when_text(peak_t)} (1X2 {x_at(peak_t)}) | adesso "
            f"{pth[-1][1]['meas'] * d:+.1f} (tenuta {s['ratio']:.2f})")


def do_test(st: dict, topic: QuoteTopic, cal: list, query: str = "") -> None:
    """Prova: diagnostica nel registro, poi nel gruppo la legenda e un ESEMPIO di riepilogo e di avviso
    sulle prossime partite (con la prima quota come riferimento se l'apertura non e' ancora arrivata).
    Con 'query' le prossime partite di quella squadra o competizione (es. "CL", "coppe", "Roma")."""
    print("=== PROVA BOT QUOTE ===")
    print(f"Account: piano gratuito, chiamate usate {st['calls']}/{st.get('limit', MONTH_LIMIT)}")
    refresh_fixtures(st, force=True, which="tutto", days=TEST_LOOKAHEAD_DAYS)
    learn_teams(st)
    cal = calendar_matches(st)
    meta = ensure_markets(st, force=st.get("markets_v") != MARKETS_VERSION)
    kinds = {}
    for v in meta.values():
        kinds[v[4] if len(v) > 4 else "main"] = kinds.get(v[4] if len(v) > 4 else "main", 0) + 1
    print("Mercati usati:", kinds)
    now = now_utc()
    cups, skipped = cup_matches(st, now)
    print(f"Squadre dei 5 campionati conosciute: {len(st.get('top5') or {})} (nomi del calendario: "
          f"{len(st.get('team_fd') or {})}) · coppe in arrivo: {len(cups)} partite tenute, {skipped} lasciate fuori")
    for m in cups[:40]:
        names = team_names(m)
        print(f"   {m['code']} {when_text(m['ko'])} {names['home']} - {names['away']} {' '.join('#' + t for t in names['tags'])}"
              f" (apertura {when_text(apertura_time(m['ko'], m['code']))})")
    day_m = next_day_matches(filter_matches(cal, query), now)     # esempio: una sola competizione
    code = next((c for c in COMPS_Q if any(m["code"] == c for m in day_m)), None)
    matches = [m for m in day_m if m["code"] == code][:10]
    if not matches:
        topic.send("🧪 Prova del bot quote: nessuna partita in arrivo nel calendario"
                   f"{' per «' + esc(query) + '»' if query else ''} (per provare il formato sulle partite gia' "
                   "giocate usa la modalita' «rivedi»).")
        return
    send_legend(st, topic, force=True)
    done = do_riepilogo(st, topic, None, matches, force=True, preview=True)
    for m, names, an, base_at, first in done:
        print(f"  {names['home']} - {names['away']} ({when_text(m['ko'])}): {base_label(base_at, first)} | "
              f"rif. {an['ref']} | colore {an['color']} | pronostico {an['picks']}")
        print(f"     {describe(an)}")
        print(f"     eventi: { {g: {k: (v if k == 'src' else v[1][0]) for k, v in r.items()} for g, r in an['events'].items()} }")
        print(f"     prima {an['a'].get('x')} {an['a'].get('ah')} {an['a'].get('ou')}\n"
              f"     adesso {an['b'].get('x')} {an['b'].get('ah')} {an['b'].get('ou')}")
    if done:
        m, names, an, base_at, first = max(done, key=lambda it: it[2]["forza"])
        if an["shown"]:
            topic.send(f"🧪 <b>ESEMPIO di avviso {RIDOSSO_MINUTES} minuti prima</b> (arriva solo da forza "
                       f"{FORZA_MIN_AVVISO}/10):\n\n" + build_message(m, names, an, base_at, first, "esempio"))
        else:
            topic.send(f"🧪 Nessuna partita di domani ha ancora un movimento da {FORZA_MIN_AVVISO}/10: niente esempio "
                       f"di avviso (il piu' forte e' {an['forza']}/10).")
    try:
        print("Account dopo:", _safe_account(api_get("/account", {}, st, counts=False, force=True)))
    except Exception as e:      # noqa: BLE001
        print(f"[WARN] account non letto: {e}")


def finished_matches(st: dict, days: int = RIVEDI_DAYS) -> list:
    """Partite gia' giocate negli ultimi giorni, con il loro id OddsPapi: dal calendario del bot notizie e, se li'
    non ci sono piu', dall'elenco OddsPapi tenuto nello stato (nomi ricondotti a quelli del calendario)."""
    now = now_utc()
    lo, hi = now - timedelta(days=days), now - timedelta(minutes=RIDOSSO_MINUTES)
    cal = load_json(FIXTURES_FILE, {})
    teams = {t.get("name"): t for t in cal.get("teams", []) if isinstance(t, dict)}
    out, used = [], set()
    for f in cal.get("fixtures", []):
        code, ko = f.get("competition"), parse_time(f.get("kickoff"))
        if code not in LEAGUES_Q or not ko or not (lo <= ko <= hi) or \
                f.get("status") in ("POSTPONED", "CANCELLED", "SUSPENDED", "AWARDED"):
            continue
        m = {"code": code, "home": f.get("home", ""), "away": f.get("away", ""), "ko": ko,
             "home_short": (teams.get(f.get("home")) or {}).get("shortName") or f.get("home", ""),
             "away_short": (teams.get(f.get("away")) or {}).get("shortName") or f.get("away", "")}
        m["fid"] = find_fixture(st, m)
        if m["fid"]:
            used.add(m["fid"])
            out.append(m)
    known = list(HASHTAGS)

    def calendar_name(pid: str, name: str) -> str:
        if fd_team_name(st, pid):
            return fd_team_name(st, pid)
        best = max(known, key=lambda k: _similar(name, k), default=None)
        return best if best and _similar(name, best) >= 0.5 else name

    for fid, rec in st["fixtures"].items():
        ko = parse_time(rec.get("start"))
        if fid in used or rec.get("code") not in LEAGUES_Q or not ko or not (lo <= ko <= hi):
            continue
        p1, p2 = str(rec.get("p1")), str(rec.get("p2"))
        n1, n2 = st["participants"].get(p1, ""), st["participants"].get(p2, "")
        if not n1 or not n2:
            continue
        h, a = calendar_name(p1, n1), calendar_name(p2, n2)
        out.append({"code": rec["code"], "home": h, "away": a, "ko": ko, "home_short": h, "away_short": a, "fid": fid})
    out += cup_matches(st, lo, hi)[0]
    return sorted(out, key=lambda m: m["ko"])


def do_rivedi(st: dict, topic: QuoteTopic, query: str = "") -> None:
    """Rilegge le partite gia' giocate come 40 minuti prima del fischio, con le regole di adesso (storico, gratis).
    Con una squadra (es. "Roma") manda il messaggio di quelle partite; senza, o con una competizione (es. "CL",
    "coppe"), il conto forti/medi/rumore e le RIVEDI_TOP piu' forti come sarebbero arrivate."""
    ensure_markets(st, force=st.get("markets_v") != MARKETS_VERSION)     # prova a mano: mercati nuovi subito
    learn_teams(st)
    matches = filter_matches(finished_matches(st), query)
    team_query = bool(query) and not query_codes(query)
    print(f"Rivedi: {len(matches)} partite da rileggere" + (f" con «{query}»" if query else ""))
    if not matches:
        topic.send(f"🧪 Rivedi: nessuna partita giocata negli ultimi {RIVEDI_DAYS} giorni"
                   f"{' con «' + esc(query) + '»' if query else ''} nell'elenco del bot.")
        return
    results, start = [], time.monotonic()
    for m in matches:
        if time.monotonic() - start > RIVEDI_BUDGET_SECONDS:
            print("Rivedi: tempo finito, mi fermo qui")
            break
        names = team_names(m)
        try:
            R = read_history(st, m["fid"], apertura_time(m["ko"], m["code"]),
                             at=m["ko"] - timedelta(minutes=RIDOSSO_MINUTES), force=True)
        except QuotaExhausted:
            raise
        except Exception as e:      # noqa: BLE001
            print(f"  {names['home']} - {names['away']}: storico non letto ({e})")
            continue
        an = analyze(R, m["ko"])
        save_stats(st, stats_entry(m, an, "rivedi"))
        results.append((m, names, an, R))
        a, b = an["a"], an["b"]
        print(f"  {names['home']} - {names['away']} ({when_text(m['ko'])}): forza {an['forza']} · {describe(an)}\n"
              f"     {an['ref']}: 1X2 {a.get('x')} -> {b.get('x')} | AH {a.get('ah')} -> {b.get('ah')} | gol "
              f"{a.get('ou')} -> {b.get('ou')} | squadre { {g: r.get('src') for g, r in an['events'].items()} } | "
              f"mercati nello storico (tutti, usati) {_HIST_INFO}")
        if len(results) == 1:
            print(f"     id non usati nello storico: {_HIST_UNKNOWN}")
        if team_query and an["ref"] in R["bh"]:
            h = R["bh"][an["ref"]]
            for lab, t in (("apertura", R["base_at"]), ("adesso", R["at"])):
                print(f"     {an['ref']} {lab}: AH {h.ladder(t, 'spreads')}\n"
                      f"     {an['ref']} {lab}: gol {h.ladder(t, 'totals')}")
            for sg in an["sigs"]:
                print(f"     andamento {sg['fam']} ({sg['ref']}): {path_text(R, sg, m['ko'])}")
    if not results:
        topic.send("🧪 Rivedi: storico delle quote non letto (riprova tra poco).")
        return
    send_legend(st, topic)
    if team_query:
        chosen = results
    else:
        forti = sum(1 for r in results if r[2]["forza"] >= FORZA_FORTE)
        medi = sum(1 for r in results if FORZA_MIN_AVVISO <= r[2]["forza"] < FORZA_FORTE)
        chosen = sorted((r for r in results if r[2]["shown"]), key=lambda r: -r[2]["forza"])[:RIVEDI_TOP]
        topic.send(f"🧪 <b>Rivedi{' · ' + esc(query) if query else ''}</b>: {len(results)} partite giocate da "
                   f"{day_text(results[0][0]['ko'])} a "
                   f"{day_text(results[-1][0]['ko'])}, rilette come {RIDOSSO_MINUTES} minuti prima con le regole "
                   f"nuove\nforti ({FORZA_FORTE}-10): <b>{forti}</b> · medie ({FORZA_MIN_AVVISO}-{FORZA_FORTE - 1}): "
                   f"<b>{medi}</b> · rumore (sotto {FORZA_MIN_AVVISO}, niente avviso): "
                   f"<b>{len(results) - forti - medi}</b>"
                   + (f"\n<i>Qui sotto le {len(chosen)} più forti, come sarebbero arrivate.</i>" if chosen else ""))
        time.sleep(SEND_DELAY_GROUP_SECONDS)
    for m, names, an, R in chosen:
        if an["shown"]:
            an = add_sot(st, m["fid"], m, R, an, force=True)
            text = build_message(m, names, an, R["base_at"], R["first"], "formazioni uscite", prefix="🧪 RIVEDI · ")
        else:
            lg = COMPS_Q.get(m["code"], {"flag": ""})
            text = "\n".join(r for r in (
                f"🧪 RIVEDI · {lg['flag']} <b>{match_title(names)}</b> · {m['ko'].astimezone(ROME):%H:%M}",
                f"⚪ Sotto la soglia: forza {an['forza']}/10, l'avviso non sarebbe arrivato",
                fmt_table(names, an["a"], an["b"], an),
                f"<i>{BOOK_LABEL.get(an['ref'], '')} · {base_label(R['base_at'], R['first'])} → "
                f"{when_text(an['at'])}</i>") if r)
        topic.send(text)
        time.sleep(SEND_DELAY_GROUP_SECONDS)
    st["log"].append(f"{now_utc().isoformat(timespec='minutes')} rivedi {query or 'settimana'}: {len(results)} "
                     f"partite lette, {len(chosen)} messaggi")


def cleanup(st: dict) -> None:
    limit = now_utc() - timedelta(days=KEEP_DAYS)
    st["fixtures"] = {k: v for k, v in st["fixtures"].items() if (parse_time(v.get("start")) or now_utc()) > limit}
    keep = (now_utc() - timedelta(days=10)).isoformat()[:16]
    st["done"] = [d for d in st["done"] if d.split("|", 1)[-1] >= keep][-400:]
    st["log"] = st["log"][-60:]
    st["stats"] = st.get("stats", [])[-STATS_KEEP:]


_START = time.monotonic()


def main() -> int:
    global _START, MUTO
    _START = time.monotonic()
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="auto", choices=["auto", "test", "ora", "apertura", "riepilogo", "rivedi"])
    ap.add_argument("--partita", default="", help="prove a mano: squadra (es. Roma) o competizione (es. CL, coppe); "
                                                  "per rivedi vuoto = tutta la settimana")
    ap.add_argument("--muto", action="store_true", help="prove a mano: messaggi nel registro, non nel gruppo")
    args = ap.parse_args()
    MUTO = bool(args.muto) and args.mode != "auto"
    if not API_KEY:
        print("Bot quote: manca il secret ODDSPAPI_API_KEY, non faccio niente")
        return 0
    st = load_qstate()
    cal = calendar_matches(st)
    now = now_utc()
    key = rkey = group = skey = None
    smatches = []
    if args.mode == "auto":
        rkey, group = due_ridosso(st, cal, now)
        key = due_apertura(st, cal, now)
        skey, smatches = due_riepilogo(st, cal, now)
        if not key and not rkey and not skey:
            print("Bot quote: niente da fare adesso")
            return 0
    learn_teams(st)                     # squadre dei 5 campionati (filtro e nomi delle coppe): nessuna chiamata
    cal = calendar_matches(st)
    query = (args.partita or "").strip()
    topic = QuoteTopic(st)
    try:
        sync_calls(st)
        if args.mode == "test":
            do_test(st, topic, cal, query)
        elif args.mode == "apertura":
            do_apertura(st, topic, None, cal, force=True)
        elif args.mode == "ora":
            do_ridosso(st, topic, None, None, filter_matches(cal, query), force=True)
        elif args.mode == "riepilogo":
            do_riepilogo(st, topic, None, next_day_matches(filter_matches(cal, query), now), force=True)
        elif args.mode == "rivedi":
            do_rivedi(st, topic, query)
        else:
            send_legend(st, topic)
            if rkey:                    # prima gli avvisi a ridosso (hanno l'orario piu' stretto)
                print(f"Bot quote: controllo a ridosso ({rkey}): "
                      + ", ".join(f"{m['home_short']}-{m['away_short']}" for m in group["matches"]))
                do_ridosso(st, topic, rkey, group, cal)
            if key:
                print(f"Bot quote: apertura ({key})")
                cal = do_apertura(st, topic, key, cal)
            if skey:
                print(f"Bot quote: riepilogo ({skey}, {len(smatches)} partite)")
                do_riepilogo(st, topic, skey, smatches)
    except QuotaExhausted as e:
        print(f"[ATTENZIONE] {e}")
        note = f"limit:{st['month']}"
        if note not in st["notices"]:
            st["notices"].append(note)
            topic.send(f"⚠️ Bot quote: {esc(str(e))}. Riparto il primo del mese.")
    except Exception as e:      # noqa: BLE001
        print(f"[ERRORE bot quote] {e.__class__.__name__}: {e}")
        st["log"].append(f"{now_utc().isoformat(timespec='minutes')} errore {e.__class__.__name__}: {str(e)[:200]}")
        cleanup(st)
        save_qstate(st)
        return 1
    cleanup(st)
    save_qstate(st)
    return 0


if __name__ == "__main__":
    sys.exit(main())
