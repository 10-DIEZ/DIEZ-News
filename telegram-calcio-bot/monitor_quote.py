"""
Bot QUOTE: come si muovono le quote dei 5 campionati (OddsPapi, piano gratuito).

COSA FA
- 40 minuti prima di ogni orario d'inizio (le formazioni ufficiali escono circa
  un'ora prima) legge lo STORICO delle quote di ogni partita su 3 book
  (Pinnacle, Sbobet, Singbet) e confronta:
      APERTURA = le quote del venerdi' alle 15:00 per le partite del weekend
                 (venerdi'-lunedi'), del martedi' alle 15:00 per i turni
                 infrasettimanali: lo stesso momento delle quote di apertura
                 usate nello studio del foglio Mercato del Pace Index;
      ADESSO   = le quote a ridosso, con le formazioni uscite.
- Ti scrive SOLO per le partite con un movimento importante confermato su
  almeno 2 book su 3, con il colore da mettere nella riga "Mercato" della
  Direzione generale (regole del foglio Mercato) e gli hashtag delle squadre.
- Il venerdi' alle 15 (e il martedi', se c'e' il turno infrasettimanale)
  aggiorna l'elenco delle partite e te lo dice con un messaggio breve.
- Tutto nell'argomento "📈 Quote" del gruppo (lo crea il bot).

QUANTO CONSUMA: lo storico delle quote NON conta nelle 250 chiamate al mese
del piano gratuito (verificato con il contatore dell'account il 6/11/2026).
Contano solo gli aggiornamenti dell'elenco partite: 1-4 a settimana. Un
contatore (allineato a quello dell'account) non fa mai superare il limite.

COME PARTE: lo lancia il giro ogni 5 minuti del bot notizie (monitor-news.yml,
avviato da cron-job.org). Quasi sempre controlla l'ora ed esce subito.
Prove a mano: workflow "Prova bot quote".

STATO: state/quote_state.json (solo questo file; lo stato delle notizie lo
legge e basta, per sapere qual e' il gruppo Telegram).

Uso: python monitor_quote.py                 giro normale
     python monitor_quote.py --mode test     prova (diagnostica + messaggio di prova)
     python monitor_quote.py --mode ora      controllo subito delle prossime partite
     python monitor_quote.py --mode apertura aggiorna subito l'elenco delle partite
"""

import argparse
import html
import json
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

# I 3 book confrontati (lo storico ne accetta al massimo 3 per chiamata)
BOOKMAKERS = ["pinnacle", "sbobet", "singbet"]
BOOK_LABEL = {"pinnacle": "Pinnacle", "singbet": "Singbet", "sbobet": "Sbobet", "bet365": "Bet365"}

# Campionati: codice football-data (calendario del bot notizie) -> nome, paese, id OddsPapi di riserva
LEAGUES_Q = {
    "SA": {"name": "Serie A", "flag": "🇮🇹", "country": "italy", "names": ("serie a",), "id": 23},
    "PL": {"name": "Premier League", "flag": "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F",
           "country": "england", "names": ("premier league",), "id": 17},
    "PD": {"name": "La Liga", "flag": "🇪🇸", "country": "spain", "names": ("laliga", "la liga"), "id": 8},
    "BL1": {"name": "Bundesliga", "flag": "🇩🇪", "country": "germany", "names": ("bundesliga",), "id": 35},
    "FL1": {"name": "Ligue 1", "flag": "🇫🇷", "country": "france", "names": ("ligue 1",), "id": 34},
}

APERTURA_DAYS = (1, 4)          # quote di riferimento: martedi' (1) e venerdi' (4)...
APERTURA_HOUR = 15              # ...alle 15:00
APERTURA_WINDOW_HOURS = 3       # giro delle 15 (aggiornamento elenco): va bene fino alle 18
LOOKAHEAD_DAYS = 6              # partite tenute nell'elenco
RIDOSSO_MINUTES = 40            # minuti prima del fischio d'inizio
RIDOSSO_LATEST_MINUTES = 12     # in ritardo si fa fino a 12 minuti prima, poi si salta
MERGE_MINUTES = 15              # orari d'inizio entro 15 minuti: un solo controllo
REFRESH_MIN_HOURS = 6           # elenco partite riletto al massimo ogni 6 ore se manca una partita
HIST_PAUSE = 5.3                # lo storico vuole 5 secondi tra una chiamata e l'altra
MONTH_LIMIT = 250               # chiamate al mese del piano gratuito
MONTH_RESERVE = 12              # tenute da parte per le prove a mano
RUN_BUDGET_SECONDS = 170        # tempo massimo per giro (il giro ogni 5 minuti deve poi controllare le notizie)

AH_HOME_SIGN = 1                # la linea del mercato e' quella della squadra di casa (-0,5 = casa favorita: verificato)
TH_LINE = 0.25                  # linea asiatica o gol: un quarto = movimento importante
TH_PROB = 2.0                   # stessa linea: 2 punti di probabilita' (senza margine)
TH_1X2 = 3.0                    # solo 1X2 (se manca l'asiatico): 3 punti
TH_OU_PROB = 3.0                # linea gol ferma: Over di 3 punti
FAV_GAP = 0.05                  # sotto 5 punti di differenza non c'e' una favorita
STALE_HOURS = 6                 # linea non aggiornata da 6 ore piu' delle altre = tolta dal book

TOPIC_NAME = "📈 Quote"
TOPIC_COLOR = 9367192           # verde
KEEP_DAYS = 3                   # partite finite tenute nello stato per qualche giorno


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
                         ("notices", []), ("log", []), ("refresh_at", "")):
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


def calendar_matches() -> list:
    """Partite dei 5 campionati dal calendario del bot notizie (state/fixtures.json)."""
    cal = load_json(FIXTURES_FILE, {})
    teams = {t.get("name"): t for t in cal.get("teams", []) if isinstance(t, dict)}
    out = []
    for f in cal.get("fixtures", []):
        code = f.get("competition")
        if code not in LEAGUES_Q or f.get("status") in ("FINISHED", "POSTPONED", "CANCELLED", "SUSPENDED", "AWARDED"):
            continue
        ko = parse_time(f.get("kickoff"))
        if not ko:
            continue
        out.append({"code": code, "home": f.get("home", ""), "away": f.get("away", ""), "ko": ko,
                    "home_short": (teams.get(f.get("home")) or {}).get("shortName") or f.get("home", ""),
                    "away_short": (teams.get(f.get("away")) or {}).get("shortName") or f.get("away", "")})
    return sorted(out, key=lambda m: m["ko"])


def apertura_time(ko: datetime) -> datetime:
    """Momento delle quote di riferimento: l'ultimo martedi' o venerdi' alle 15:00 almeno 2 ore prima del fischio."""
    limit = (ko - timedelta(hours=2)).astimezone(ROME)
    for back in range(0, 8):
        d = (limit - timedelta(days=back)).date()
        if d.weekday() in APERTURA_DAYS:
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
    if path == "/historical-odds" and path in _LAST_CALL:      # pausa obbligatoria tra due letture dello storico
        wait = HIST_PAUSE - (time.monotonic() - _LAST_CALL[path])
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
    """Id OddsPapi dei 5 campionati (cercati una volta per nome e paese; se non si trovano, quelli di riserva)."""
    if st["tournaments"] and not force:
        return st["tournaments"]
    try:
        items = as_list(api_get("/tournaments", {"sportId": 10}, st))
    except QuotaExhausted:
        raise
    except Exception as e:      # noqa: BLE001
        print(f"[WARN] elenco campionati non letto ({e}): uso gli id di riserva")
        items = []
    found = {}
    for code, lg in LEAGUES_Q.items():
        best = None
        for t in items:
            name = norm(t.get("tournamentName") or t.get("name"))
            cat = norm(t.get("categoryName") or t.get("categorySlug") or t.get("category"))
            if name in lg["names"] and lg["country"] in cat:
                tid = t.get("tournamentId") or t.get("id")
                if best is None or tid == lg["id"]:
                    best = tid
        found[code] = int(best) if best else lg["id"]
    st["tournaments"] = found
    print("Id OddsPapi dei campionati:", found)
    return found


def ensure_markets(st: dict, force: bool = False) -> dict:
    """Descrizione dei mercati (id -> tipo, linea, periodo), riletta una volta al mese."""
    if st["markets"] and st["markets_month"] == st["month"] and not force:
        return st["markets"]
    last = parse_time(st.get("markets_try"))
    if not force and last and now_utc() - last < timedelta(hours=20):
        return st["markets"]
    st["markets_try"] = now_utc().isoformat(timespec="seconds")
    try:
        items = as_list(api_get("/markets", {"language": "en"}, st))
    except QuotaExhausted:
        raise
    except Exception as e:      # noqa: BLE001
        print(f"[WARN] elenco mercati non letto ({e})")
        return st["markets"]
    meta = {}
    for m in items:
        try:
            if int(m.get("sportId") or 10) != 10 or m.get("playerProp"):
                continue
            mtype = str(m.get("marketType") or "").lower()
            if mtype not in ("1x2", "spreads", "totals"):
                continue
            names = " ".join(norm(o.get("outcomeName")) for o in (m.get("outcomes") or []))
            if mtype == "totals" and ("yes" in names.split() or "no" in names.split()):
                continue            # Goal/No Goal (registrato anche lui come "totals")
            mname = norm(m.get("marketName"))
            if any(w in mname.split() for w in ("corner", "corners", "card", "cards", "booking", "bookings", "team",
                                                "home", "away", "half", "first", "second", "1st", "2nd", "player")):
                continue            # corner, cartellini, gol di una sola squadra, tempi
            order = outcome_order(mtype, m.get("outcomes") or [])
            if not order:
                continue            # non si capisce quale esito e' casa/Over: meglio non usarlo
            meta[str(m["marketId"])] = [mtype, float(m.get("handicap") or 0), str(m.get("period") or "").lower(), order]
        except (KeyError, TypeError, ValueError):
            continue
    if meta:
        st["markets"], st["markets_month"] = meta, st["month"]
    print(f"Mercati letti: {len(meta)} (1X2, handicap asiatico, linea gol)")
    return st["markets"]


_SIDE_NAMES = {"home": ("1", "home", "w1", "team1", "1 ah", "ah1", "h"), "draw": ("x", "draw", "d"),
               "away": ("2", "away", "w2", "team2", "2 ah", "ah2", "a")}


def outcome_order(mtype: str, outcomes: list) -> list | None:
    """Id degli esiti nell'ordine giusto, letto dai NOMI (gli id non sono sempre in ordine):
    1X2 -> [1, X, 2]; handicap -> [casa, ospite]; linea gol -> [Over, Under]."""
    by = {}
    for o in outcomes:
        try:
            oid, name = int(o["outcomeId"]), norm(o.get("outcomeName"))
        except (KeyError, TypeError, ValueError):
            continue
        if mtype == "totals":
            side = "over" if name.startswith("over") else "under" if name.startswith("under") else None
        else:
            side = next((s for s, names in _SIDE_NAMES.items() if name in names), None)
        if side and side not in by:
            by[side] = oid
    want = {"totals": ("over", "under"), "spreads": ("home", "away"), "1x2": ("home", "draw", "away")}[mtype]
    return [by[s] for s in want] if all(s in by for s in want) else None


def ensure_participants(st: dict, ids: set) -> dict:
    """Nomi delle squadre (solo quelle che servono), letti una volta e tenuti nello stato."""
    missing = {str(i) for i in ids if i is not None} - set(st["participants"])
    if not missing:
        return st["participants"]
    last = parse_time(st.get("participants_try"))
    if last and now_utc() - last < timedelta(days=3):
        return st["participants"]   # gia' provato da poco: si usano i nomi del calendario
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


def refresh_fixtures(st: dict, force: bool = False) -> int:
    """Elenco delle partite dei 5 campionati con il loro id OddsPapi: UNA chiamata (Pinnacle)."""
    tour = ensure_tournaments(st)
    code_by_tid = {str(v): k for k, v in tour.items()}
    data = api_get("/odds-by-tournaments", {"tournamentIds": ",".join(str(tour[c]) for c in LEAGUES_Q),
                                            "bookmaker": "pinnacle"}, st, force=force)
    horizon = now_utc() + timedelta(days=LOOKAHEAD_DAYS + 2)
    n = 0
    for fx in as_list(data):
        try:
            fid = str(fx["fixtureId"])
        except (KeyError, TypeError):
            continue
        start = parse_time(fx.get("startTime"))
        if not start or start > horizon:
            continue
        _SNAPSHOT[fid] = fx
        rec = st["fixtures"].setdefault(fid, {})
        rec.update(code=code_by_tid.get(str(fx.get("tournamentId")), rec.get("code", "")),
                   p1=fx.get("participant1Id"), p2=fx.get("participant2Id"), start=start.isoformat())
        n += 1
    st["refresh_at"] = now_utc().isoformat(timespec="seconds")
    ensure_participants(st, {r.get("p1") for r in st["fixtures"].values()} | {r.get("p2") for r in st["fixtures"].values()})
    print(f"Elenco partite aggiornato: {n} partite (chiamate del mese {st['calls']}/{MONTH_LIMIT})")
    return n


# ---------------------------------------------------------------------
# Lettura dello storico: quote di ogni book in un certo momento
# ---------------------------------------------------------------------
def _pick_main(cands: list):
    """Tra le linee (linea, prezzo1, prezzo2, ultimo aggiornamento) sceglie quella principale: la piu' equilibrata
    tra quelle ancora aggiornate (una linea tolta dal book resta nello storico con il suo ultimo prezzo)."""
    if not cands:
        return None
    newest = max(c[3] for c in cands)
    fresh = [c for c in cands if c[3] >= newest - timedelta(hours=STALE_HOURS)]
    best = min(fresh, key=lambda c: abs(1 / c[1] - 1 / c[2]))
    return [best[0], best[1], best[2]]


def _price_at(entries, at):
    """Prezzo in vigore al momento 'at' (None = l'ultimo) da una lista di cambi con createdAt."""
    best = None
    for e in entries or []:
        t = parse_time(e.get("createdAt"))
        if not t or (at is not None and t > at):
            continue
        if best is None or t > best[0]:
            best = (t, e)
    if not best:
        return None, None
    e = best[1]
    if e.get("active") is False:
        return None, best[0]
    try:
        p = float(e.get("price"))
        return (p if p > 1.0 else None), best[0]
    except (TypeError, ValueError):
        return None, best[0]


def _first_time(entries):
    ts = [parse_time(e.get("createdAt")) for e in entries or []]
    ts = [t for t in ts if t]
    return min(ts) if ts else None


def books_at(hist: dict, meta: dict, at) -> dict:
    """Dallo storico: per ogni book 1X2, linea asiatica principale e linea gol principale al momento 'at'."""
    out = {}
    for slug, bk in ((hist or {}).get("bookmakers") or {}).items():
        res = {"x": None, "ah": None, "ou": None}
        ah, ou = [], []
        for mid, m in ((bk or {}).get("markets") or {}).items():
            info = meta.get(str(mid))
            if not info or len(info) < 4:
                continue
            if info[2] not in ("fulltime", "result", ""):
                continue
            outs = (m or {}).get("outcomes") or {}
            prices, times = [], []
            for oid in info[3]:             # esiti nell'ordine giusto (1-X-2, casa-ospite, Over-Under)
                pls = (outs.get(str(oid)) or {}).get("players") or {}
                entries = next(iter(pls.values()), []) if isinstance(pls, dict) and pls else []
                p, t = _price_at(entries, at)
                prices.append(p)
                times.append(t)
            if not all(prices):
                continue
            if info[0] == "1x2":
                if len(prices) == 3 and (res["x"] is None or str(mid) == "101"):
                    res["x"] = prices
            elif len(prices) == 2:
                if info[0] == "spreads":
                    ah.append((AH_HOME_SIGN * info[1], prices[0], prices[1], max(times)))
                elif info[0] == "totals" and info[1] > 0:
                    ou.append((info[1], prices[0], prices[1], max(times)))
        res["ah"], res["ou"] = _pick_main(ah), _pick_main(ou)
        if any(res.values()):
            out[slug] = res
    return out


def opening_time(hist: dict) -> datetime | None:
    """Quando il primo dei book ha pubblicato la partita (il primo prezzo dello storico)."""
    firsts = []
    for bk in ((hist or {}).get("bookmakers") or {}).values():
        m = ((bk or {}).get("markets") or {}).get("101") or {}
        for o in (m.get("outcomes") or {}).values():
            for entries in ((o or {}).get("players") or {}).values():
                t = _first_time(entries)
                if t:
                    firsts.append(t)
    return min(firsts) if firsts else None


_HIST_INFO = {}         # per la prova: mercati trovati nello storico per ogni book (tutti, usati)


def read_history(st: dict, fid: str, ap_at: datetime, force: bool = False):
    """Storico della partita (NON consuma chiamate): quote all'apertura e adesso sui 3 book."""
    meta = ensure_markets(st)
    hist = api_get("/historical-odds", {"fixtureId": fid, "bookmakers": ",".join(BOOKMAKERS)}, st,
                   counts=False, force=force)
    if isinstance(hist, dict) and fid in hist and isinstance(hist[fid], dict):
        hist = hist[fid]
    _HIST_INFO.clear()
    for slug, bk in ((hist or {}).get("bookmakers") or {}).items() if isinstance(hist, dict) else []:
        mk = (bk or {}).get("markets") or {}
        _HIST_INFO[slug] = (len(mk), sum(1 for k in mk if k in meta))
    base = books_at(hist, meta, ap_at)
    now = books_at(hist, meta, None)
    opened = opening_time(hist)
    first = None
    if not base and opened:          # nessuna quota all'apertura (partita pubblicata dopo): si usa la prima
        first = opened + timedelta(minutes=1)
        base = books_at(hist, meta, first)
    return base, now, (first or ap_at), bool(first)


# =====================================================================
# Lettura dei movimenti (regole del foglio Mercato)
# =====================================================================
def novig(prices):
    inv = [1.0 / p for p in prices]
    s = sum(inv)
    return [x / s for x in inv]


def book_move(a: dict, b: dict) -> dict:
    """Movimento di un book da a (apertura) a b (adesso). dir: 'home' / 'away' / None; forza 1 quota, 2 un quarto, 3 mezzo gol."""
    res = {"dir": None, "force": 0, "ou": None}
    if a.get("ah") and b.get("ah"):
        dline = round(b["ah"][0] - a["ah"][0], 2)
        if abs(dline) >= TH_LINE - 1e-9:
            res["dir"] = "home" if dline < 0 else "away"
            res["force"] = 3 if abs(dline) >= 0.5 - 1e-9 else 2
        else:
            dp = (novig(b["ah"][1:])[0] - novig(a["ah"][1:])[0]) * 100
            if abs(dp) >= TH_PROB:
                res["dir"], res["force"] = ("home" if dp > 0 else "away"), 1
    elif a.get("x") and b.get("x"):
        pa, pb = novig(a["x"]), novig(b["x"])
        d1, d2 = (pb[0] - pa[0]) * 100, (pb[2] - pa[2]) * 100
        if max(abs(d1), abs(d2)) >= TH_1X2:
            res["dir"], res["force"] = ("home" if d1 - d2 > 0 else "away"), 1
    if a.get("ou") and b.get("ou"):
        dl = round(b["ou"][0] - a["ou"][0], 2)
        if abs(dl) >= TH_LINE - 1e-9:
            res["ou"] = "over" if dl > 0 else "under"
        else:
            dpo = (novig(b["ou"][1:])[0] - novig(a["ou"][1:])[0]) * 100
            if abs(dpo) >= TH_OU_PROB:
                res["ou"] = "over" if dpo > 0 else "under"
    return res


def read_movement(base: dict, now: dict) -> dict | None:
    """Confronto apertura -> adesso. None se non c'e' niente di importante su almeno 2 book su 3."""
    moves = {s: book_move(base[s], now[s]) for s in BOOKMAKERS if s in base and s in now}
    if not moves:
        return None
    side = None
    for d in ("home", "away"):
        agree = [s for s, m in moves.items() if m["dir"] == d]
        if len(agree) >= 2:
            forces = sorted((moves[s]["force"] for s in agree), reverse=True)
            side = {"dir": d, "books": agree, "force": forces[1]}   # la forza confermata da almeno 2 book
    ou = None
    for d in ("over", "under"):
        agree = [s for s, m in moves.items() if m["ou"] == d]
        if len(agree) >= 2:
            ou = {"dir": d, "books": agree}
    if not side and not ou:
        return None
    fav = None
    for slug in BOOKMAKERS:                 # favorita all'apertura (1X2 senza margine del primo book che ce l'ha)
        x = (base.get(slug) or {}).get("x")
        if x:
            p = novig(x)
            if abs(p[0] - p[2]) >= FAV_GAP:
                fav = "home" if p[0] > p[2] else "away"
            break
    return {"side": side, "ou": ou, "fav": fav, "moves": moves}


def verdict(mv: dict, names: dict) -> str:
    side, fav = mv["side"], mv["fav"]
    if not side:
        return ""
    team = names[side["dir"]]
    why = f"su {len(side['books'])} book su 3"
    if fav is None or side["dir"] == fav:
        if side["force"] >= 2:
            return f"Verde forte a <b>{esc(team)}</b> (linea spostata verso di lei {why})"
        return f"Verde a <b>{esc(team)}</b> (stessa linea, quota scesa {why})"
    fav_team = esc(names[fav])
    if side["force"] >= 3:
        return f"Rosso forte a <b>{fav_team}</b> (linea di mezzo gol contro la favorita {why})"
    if side["force"] == 2:
        return f"Rosso a <b>{fav_team}</b> (linea di un quarto contro la favorita {why}: segnale piu' debole)"
    return f"Rosso a <b>{fav_team}</b> (quota della favorita salita {why})"


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


def find_fixture(st: dict, m: dict) -> str | None:
    """Id OddsPapi della partita del calendario (stesso campionato e orario, nomi simili)."""
    pn = st["participants"]
    cands = []
    for fid, rec in st["fixtures"].items():
        start = parse_time(rec.get("start"))
        if rec.get("code") == m["code"] and start and abs((start - m["ko"]).total_seconds()) <= 25 * 60:
            n1, n2 = pn.get(str(rec.get("p1")), ""), pn.get(str(rec.get("p2")), "")
            score = max(_similar(n1, m["home"]), _similar(n1, m["home_short"])) + \
                max(_similar(n2, m["away"]), _similar(n2, m["away_short"]))
            cands.append((score, fid))
    if not cands:
        return None
    cands.sort(reverse=True)
    if cands[0][0] > 0 or len(cands) == 1:
        return cands[0][1]
    return None


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


def fmt_line(h: float) -> str:
    if abs(h) < 1e-9:
        return "0"
    return ("−" if h < 0 else "+") + fmt_goal(abs(h))


def when_text(t: datetime | None) -> str:
    if not t:
        return "?"
    t = t.astimezone(ROME)
    days = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
    return f"{days[t.weekday()]} {t:%H:%M}"


def build_message(m: dict, names: dict, base: dict, now: dict, mv: dict, base_at: datetime, first: bool) -> str:
    lg = LEAGUES_Q.get(m["code"], {"flag": "", "name": ""})
    rows = [f"{lg['flag']} <b>{esc(lg['name'])} · {esc(names['home'])} – {esc(names['away'])}</b> · "
            f"{m['ko'].astimezone(ROME):%H:%M}"]
    for slug in BOOKMAKERS:
        a, b = base.get(slug), now.get(slug)
        if not a or not b:
            continue
        mark = " ✅" if (mv["side"] and slug in mv["side"]["books"]) else ""
        if a.get("ah") and b.get("ah"):
            rows.append(f"<b>{BOOK_LABEL[slug]}</b>: {esc(names['home'])} {fmt_line(a['ah'][0])} → {fmt_line(b['ah'][0])} "
                        f"({fmt_num(a['ah'][1])} → {fmt_num(b['ah'][1])}){mark}")
        elif a.get("x") and b.get("x"):
            rows.append(f"<b>{BOOK_LABEL[slug]}</b>: 1 {fmt_num(a['x'][0])}→{fmt_num(b['x'][0])} · "
                        f"X {fmt_num(a['x'][1])}→{fmt_num(b['x'][1])} · 2 {fmt_num(a['x'][2])}→{fmt_num(b['x'][2])}{mark}")
    for slug in BOOKMAKERS:                     # 1X2 del primo book che lo ha, con la probabilita' della casa
        a, b = base.get(slug), now.get(slug)
        if a and b and a.get("x") and b.get("x"):
            pa, pb = novig(a["x"]), novig(b["x"])
            rows.append(f"1X2 {BOOK_LABEL[slug]}: 1 {fmt_num(a['x'][0])}→{fmt_num(b['x'][0])} · X {fmt_num(a['x'][1])}→"
                        f"{fmt_num(b['x'][1])} · 2 {fmt_num(a['x'][2])}→{fmt_num(b['x'][2])} "
                        f"(casa {round(pa[0] * 100)}%→{round(pb[0] * 100)}%)")
            break
    if mv["ou"]:
        for slug in BOOKMAKERS:
            a, b = base.get(slug), now.get(slug)
            if a and b and a.get("ou") and b.get("ou"):
                rows.append(f"Gol ({BOOK_LABEL[slug]}): linea {fmt_goal(a['ou'][0])} → {fmt_goal(b['ou'][0])} · "
                            f"Over {fmt_num(a['ou'][1])} → {fmt_num(b['ou'][1])}")
                break
    v = verdict(mv, names)
    if v:
        rows.append(f"➜ {v}")
    if mv["ou"]:
        rows.append(f"➜ Linea gol verso l'<b>{'Over' if mv['ou']['dir'] == 'over' else 'Under'}</b> "
                    f"(su {len(mv['ou']['books'])} book su 3)")
    label = "prima quota" if first else "apertura"
    rows.append(f"<i>{label} {when_text(base_at)} → adesso {when_text(now_utc())} (formazioni uscite)</i>")
    if names["tags"]:
        rows.append(" ".join("#" + t for t in names["tags"]))
    return "\n".join(rows)


# =====================================================================
# Telegram: argomento "Quote"
# =====================================================================
_THREAD_GONE = ("message thread not found", "thread not found", "topic_deleted", "topic deleted",
                "topic_id_invalid", "message_thread_id_invalid")
WELCOME = ("📈 <b>Qui arrivano solo le quote.</b>\n\n"
           "40 minuti prima di ogni partita dei 5 campionati (formazioni uscite) il bot confronta le quote di adesso "
           "con quelle d'<b>apertura</b> (venerdi' alle 15 per il weekend, martedi' alle 15 per i turni infrasettimanali) "
           "su Pinnacle, Sbobet e Singbet.\n\n"
           "Ti scrive SOLO se si sono mosse in modo importante su almeno 2 book su 3, con il colore da mettere nella "
           "riga <b>Mercato</b> della Direzione generale.\n\n"
           "Tocca l'hashtag di una squadra per vedere insieme notizie e quote.")


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
            send_telegram_message(WELCOME, disable_preview=True, chat_id=self.group_id, thread_id=tid)
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
    """Partite che hanno come apertura le 15:00 di oggi (venerdi': weekend; martedi': turno infrasettimanale)."""
    loc = now.astimezone(ROME)
    ap = datetime(loc.year, loc.month, loc.day, APERTURA_HOUR, tzinfo=ROME).astimezone(timezone.utc)
    return [m for m in cal if m["ko"] > now and apertura_time(m["ko"]) == ap]


def due_apertura(st: dict, cal: list, now: datetime) -> str | None:
    loc = now.astimezone(ROME)
    if loc.weekday() not in APERTURA_DAYS or not (APERTURA_HOUR <= loc.hour < APERTURA_HOUR + APERTURA_WINDOW_HOURS):
        return None
    key = f"A|{loc:%Y-%m-%d}T{APERTURA_HOUR:02d}"
    if key in st["done"] or not apertura_matches(cal, now):
        return None             # gia' fatto, o martedi' senza turno infrasettimanale
    return key


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
def do_apertura(st: dict, topic: QuoteTopic, key: str | None, cal: list, force: bool = False) -> None:
    n = refresh_fixtures(st, force=force)
    if key:
        st["done"].append(key)
    now = now_utc()
    soon = apertura_matches(cal, now) if key else [m for m in cal if now < m["ko"] <= now + timedelta(days=4)]
    if not soon:
        return
    per = {}
    for m in soon:
        per[m["code"]] = per.get(m["code"], 0) + 1
    detail = " · ".join(f"{LEAGUES_Q[c]['flag']} {k}" for c, k in per.items())
    last = max(m["ko"] for m in soon)
    head = (f"📸 <b>Apertura</b> ({when_text(now)}): da adesso le quote di riferimento sono queste, per {len(soon)} "
            f"partite fino a {when_text(last).split()[0]}") if key else \
        f"📸 <b>Elenco partite aggiornato a mano</b> ({when_text(now)}): {len(soon)} partite nei prossimi 4 giorni"
    topic.send(f"{head} · {detail}\n"
               f"<i>Ti scrivo 40 minuti prima delle partite solo se le quote si muovono davvero. "
               f"Elenco OddsPapi: {n} partite · chiamate usate questo mese: {st['calls']}/{st.get('limit', MONTH_LIMIT)}.</i>")


def match_key(m: dict) -> str:
    return f"M|{m['ko'].isoformat()[:16]}|{m['code']}|{m['home']}"


def do_ridosso(st: dict, topic: QuoteTopic, key: str | None, group: dict | None, cal: list, force: bool = False) -> int:
    """Per ogni partita del gruppo: storico (gratis) -> apertura e adesso sui 3 book -> messaggio se serve.
    Ogni partita controllata viene segnata e salvata subito: se il giro si interrompe (o finisce il tempo),
    il giro dopo riprende dalle partite mancanti, senza doppioni."""
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
                base, now, base_at, first = read_history(st, fid, apertura_time(m["ko"]), force=force)
                checked += 1
            except QuotaExhausted:
                raise
            except Exception as e:      # noqa: BLE001
                print(f"  {names['home']} - {names['away']}: storico non letto ({e}): riprovo al prossimo giro")
                unfinished = True
                continue
            mv = read_movement(base, now)
            if not mv:
                print(f"  {names['home']} - {names['away']}: niente di importante (book: {sorted(set(base) & set(now))})")
            elif topic.send(build_message(m, names, base, now, mv, base_at, first)):
                sent += 1
                print(f"  {names['home']} - {names['away']}: MOVIMENTO -> inviato")
                time.sleep(SEND_DELAY_GROUP_SECONDS)
            else:
                print(f"  {names['home']} - {names['away']}: MOVIMENTO, ma Telegram non ha accettato: riprovo")
                unfinished = True
                continue
        if not manual:
            st["done"].append(match_key(m))
            save_qstate(st)
    if key and not unfinished:
        st["done"].append(key)
    if manual and sent == 0:
        topic.send(f"🔎 Controllo a mano delle partite di {when_text(group['first'])}: nessun movimento "
                   f"importante dall'apertura ({checked} partite lette su {len(todo)}).")
    st["log"].append(f"{now_utc().isoformat(timespec='minutes')} {'a mano' if manual else 'ridosso'} "
                     f"{len(todo)} partite, {checked} lette, {sent} messaggi{' (da finire)' if unfinished else ''}")
    return sent


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


def do_test(st: dict, topic: QuoteTopic, cal: list) -> None:
    """Prova: cosa permette la chiave e un esempio di lettura sulle prossime partite."""
    print("=== PROVA BOT QUOTE ===")
    try:
        print("Account:", _safe_account(api_get("/account", {}, st, counts=False, force=True)))
    except Exception as e:      # noqa: BLE001
        print(f"[WARN] account non letto: {e}")
    refresh_fixtures(st, force=True)
    meta = ensure_markets(st)
    kinds = {}
    for v in meta.values():
        kinds[v[0]] = kinds.get(v[0], 0) + 1
    print("Mercati usati:", kinds, "| esempi (id: tipo, linea, periodo, esiti in ordine):",
          {k: meta[k] for k in list(meta)[:1] + [k for k in meta if meta[k][0] != "1x2"][:4]})
    groups = kickoff_groups([m for m in cal if m["ko"] > now_utc()])
    sample = []
    for g in groups[:2]:
        for m in g["matches"][:3]:
            names = team_names(m)
            fid = find_fixture(st, m)
            if not fid:
                print(f"  {names['home']} - {names['away']}: non trovata su OddsPapi")
                continue
            base, now, base_at, first = read_history(st, fid, apertura_time(m["ko"]), force=True)
            print(f"  {names['home']} - {names['away']} ({when_text(m['ko'])}, id {fid}): apertura {when_text(base_at)}"
                  f"{' (prima quota)' if first else ''} | mercati nello storico (tutti, usati): {_HIST_INFO}")
            for slug in BOOKMAKERS:
                print(f"     {slug}: apertura {base.get(slug)} | adesso {now.get(slug)}")
            print(f"     pinnacle dall'elenco (linee principali segnate dal book): {snapshot_main(_SNAPSHOT.get(fid), meta)}")
            if len(sample) < 3 and now:
                p = now.get("pinnacle") or next(iter(now.values()))
                bits = []
                if p.get("ah"):
                    bits.append(f"{esc(names['home'])} {fmt_line(p['ah'][0])} ({fmt_num(p['ah'][1])})")
                if p.get("x"):
                    bits.append(f"1X2 {fmt_num(p['x'][0])} · {fmt_num(p['x'][1])} · {fmt_num(p['x'][2])}")
                if p.get("ou"):
                    bits.append(f"gol {fmt_goal(p['ou'][0])} (Over {fmt_num(p['ou'][1])})")
                books = ", ".join(BOOK_LABEL[s] for s in BOOKMAKERS if s in now)
                sample.append(f"{LEAGUES_Q[m['code']]['flag']} <b>{esc(names['home'])} – {esc(names['away'])}</b> "
                              f"{when_text(m['ko'])}: " + " · ".join(bits) + f" <i>({books})</i>")
    try:
        print("Account dopo:", _safe_account(api_get("/account", {}, st, counts=False, force=True)))
    except Exception as e:      # noqa: BLE001
        print(f"[WARN] account non letto: {e}")
    body = ("Quote di adesso delle prossime partite:\n" + "\n".join(sample)) if sample else \
        "⚠️ Nessuna delle prossime partite trovata su OddsPapi: guardo il registro della prova."
    topic.send("🧪 <b>Prova del bot quote riuscita</b>\n"
               f"Chiamate usate questo mese: {st['calls']}/{st.get('limit', MONTH_LIMIT)} (lo storico delle quote non le "
               f"consuma).\n\n" + body)


def cleanup(st: dict) -> None:
    limit = now_utc() - timedelta(days=KEEP_DAYS)
    st["fixtures"] = {k: v for k, v in st["fixtures"].items() if (parse_time(v.get("start")) or now_utc()) > limit}
    keep = (now_utc() - timedelta(days=10)).isoformat()[:16]
    st["done"] = [d for d in st["done"] if d.split("|", 1)[-1] >= keep][-400:]
    st["log"] = st["log"][-60:]


_START = time.monotonic()


def main() -> int:
    global _START
    _START = time.monotonic()
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="auto", choices=["auto", "test", "ora", "apertura"])
    args = ap.parse_args()
    if not API_KEY:
        print("Bot quote: manca il secret ODDSPAPI_API_KEY, non faccio niente")
        return 0
    st = load_qstate()
    cal = calendar_matches()
    now = now_utc()
    key = rkey = group = None
    if args.mode == "auto":
        key = due_apertura(st, cal, now)
        rkey, group = due_ridosso(st, cal, now)
        if not key and not rkey:
            print("Bot quote: niente da fare adesso")
            return 0
    topic = QuoteTopic(st)
    try:
        sync_calls(st)
        if args.mode == "test":
            do_test(st, topic, cal)
        elif args.mode == "apertura":
            do_apertura(st, topic, None, cal, force=True)
        elif args.mode == "ora":
            do_ridosso(st, topic, None, None, cal, force=True)
        else:
            if key:
                print(f"Bot quote: apertura ({key})")
                do_apertura(st, topic, key, cal)
            if rkey:
                print(f"Bot quote: controllo a ridosso ({rkey}): "
                      + ", ".join(f"{m['home_short']}-{m['away_short']}" for m in group["matches"]))
                do_ridosso(st, topic, rkey, group, cal)
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
