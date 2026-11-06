"""
Bot QUOTE: come si muovono le quote dei 5 campionati (OddsPapi, piano gratuito).

COSA FA
- APERTURA: il martedi' e il venerdi' alle 15:00 (ora italiana) fa una foto
  delle quote di tutte le partite dei 5 campionati dei prossimi 4 giorni, su
  3 book (Pinnacle, Singbet, Bet365). E' lo stesso momento delle quote di
  "apertura" usate nello studio del foglio Mercato del Pace Index (quote del
  venerdi' per il weekend, del martedi' per i turni infrasettimanali).
- A RIDOSSO: 40 minuti prima di ogni orario d'inizio (le formazioni ufficiali
  escono circa un'ora prima) rifa' la foto e confronta con l'apertura.
- Ti scrive SOLO per le partite con un movimento importante confermato su
  almeno 2 book su 3, con il colore da mettere nella riga "Mercato" della
  Direzione generale (regole del foglio Mercato) e gli hashtag delle squadre.
- Tutto nell'argomento "Quote" del gruppo (lo crea il bot).

QUANTO CONSUMA: ogni foto e' UNA chiamata (fino a 3 book e tutti e 5 i
campionati insieme). Circa 9 aperture e 85-100 controlli al mese, molto sotto
le 250 del piano gratuito. Un contatore impedisce di superare il limite.

COME PARTE: lo lancia il giro ogni 5 minuti del bot notizie
(monitor-news.yml, avviato da cron-job.org). Quasi sempre controlla l'ora ed
esce subito senza chiamare nessuno. Prove a mano: workflow "Prova bot quote".

STATO: state/quote_state.json (solo questo file; lo stato delle notizie lo
legge e basta, per sapere qual e' il gruppo Telegram).

Uso: python monitor_quote.py                 giro normale
     python monitor_quote.py --mode test     prova completa (diagnostica + messaggio di prova)
     python monitor_quote.py --mode ora      controllo subito delle prossime partite
     python monitor_quote.py --mode apertura foto d'apertura subito
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

from config import FIXTURES_FILE, HASHTAGS, SEND_DELAY_GROUP_SECONDS, STATE_FILE, TELEGRAM_CHAT_ID
from utils import send_telegram_message, telegram_api

# =====================================================================
# IMPOSTAZIONI (tutto quello che si puo' voler regolare)
# =====================================================================
ROME = ZoneInfo("Europe/Rome")
API_BASE = "https://api.oddspapi.io/v4"
API_KEY = os.environ.get("ODDSPAPI_API_KEY", "").strip()
QUOTE_STATE_FILE = os.path.join(os.path.dirname(__file__), "state", "quote_state.json")

# I 3 book (massimo 3 per chiamata). I primi due sono i book "che fanno il prezzo".
BOOKMAKERS = ["pinnacle", "singbet", "bet365"]
SHARP_BOOKS = ("pinnacle", "singbet", "sbobet")
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

APERTURA_DAYS = (1, 4)          # martedi' (1) e venerdi' (4)
APERTURA_HOUR = 15              # alle 15:00
APERTURA_WINDOW_HOURS = 3       # se il giro delle 15 salta, va bene fino alle 18
APERTURA_LOOKAHEAD_DAYS = 4     # partite dei prossimi 4 giorni
RIDOSSO_MINUTES = 40            # minuti prima del fischio d'inizio
RIDOSSO_LATEST_MINUTES = 12     # in ritardo si fa fino a 12 minuti prima, poi si salta
MERGE_MINUTES = 15              # orari d'inizio entro 15 minuti: una sola chiamata
MERGE_MINUTES_SAVING = 60       # ...entro 60 minuti quando il mese e' agli sgoccioli
MONTH_LIMIT = 250               # chiamate al mese del piano gratuito
MONTH_RESERVE = 12              # tenute da parte per le prove a mano
SAVING_FROM = 200               # da qui in poi si risparmia (orari uniti)

AH_HOME_SIGN = 1                # 1: la linea del mercato e' quella della squadra di casa (-0,5 = casa favorita)
TH_LINE = 0.25                  # linea asiatica: un quarto = movimento importante
TH_PROB = 2.0                   # stessa linea: 2 punti di probabilita' (senza margine)
TH_1X2 = 3.0                    # solo 1X2 (se manca l'asiatico): 3 punti
TH_OU_PROB = 3.0                # linea gol ferma: Over di 3 punti
FAV_GAP = 0.05                  # sotto 5 punti di differenza non c'e' una favorita

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
    st.setdefault("version", 1)
    st.setdefault("month", "")
    st.setdefault("calls", 0)
    st.setdefault("fixtures", {})
    st.setdefault("done", [])
    st.setdefault("topic", {})
    st.setdefault("tournaments", {})
    st.setdefault("participants", {})
    st.setdefault("markets", {})
    st.setdefault("markets_month", "")
    st.setdefault("notices", [])
    st.setdefault("log", [])
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


# =====================================================================
# OddsPapi
# =====================================================================
class QuotaExhausted(Exception):
    pass


def api_get(path: str, params: dict, st: dict, counts: bool = True, force: bool = False):
    """Chiamata a OddsPapi. counts=False per le chiamate che non consumano (account)."""
    if not API_KEY:
        raise RuntimeError("manca il secret ODDSPAPI_API_KEY")
    if counts and not force and st["calls"] >= MONTH_LIMIT - MONTH_RESERVE:
        raise QuotaExhausted(f"chiamate del mese finite ({st['calls']}/{MONTH_LIMIT})")
    q = dict(params or {})
    q["apiKey"] = API_KEY
    for attempt in range(3):
        try:
            resp = requests.get(API_BASE + path, params=q, timeout=45)
        except requests.RequestException as e:
            if attempt == 2:
                raise RuntimeError(f"rete: {e.__class__.__name__}")
            time.sleep(3)
            continue
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
            wait = 2.0
            if isinstance(data, dict):
                wait = float(data.get("retryMs") or 0) / 1000.0 or float(data.get("retryAfterSec") or 0) or 2.0
            wait = min(max(wait, 1.0), 12.0)
            print(f"[OddsPapi] troppo veloce, aspetto {wait:.1f}s")
            time.sleep(wait)
            continue
        raise RuntimeError(f"OddsPapi {path}: HTTP {resp.status_code} {text}")
    raise RuntimeError(f"OddsPapi {path}: troppi tentativi")


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
    found = {}
    try:
        items = as_list(api_get("/tournaments", {"sportId": 10}, st))
    except QuotaExhausted:
        raise
    except Exception as e:      # noqa: BLE001
        print(f"[WARN] elenco campionati non letto ({e}): uso gli id di riserva")
        items = []
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
        print(f"Campionato {lg['name']}: id OddsPapi {found[code]}{'' if best else ' (di riserva)'}")
    st["tournaments"] = found
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
            meta[str(m["marketId"])] = [mtype, float(m.get("handicap") or 0), str(m.get("period") or "").lower(),
                                        [int(o["outcomeId"]) for o in (m.get("outcomes") or []) if "outcomeId" in o]]
        except (KeyError, TypeError, ValueError):
            continue
    if meta:
        st["markets"], st["markets_month"] = meta, st["month"]
    print(f"Mercati letti: {len(meta)} (1X2, handicap asiatico, linea gol)")
    return st["markets"]


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
        pairs = []
        for p in as_list(data):
            pid = p.get("participantId") or p.get("id")
            name = p.get("participantName") or p.get("name") or p.get("participantShortName")
            pairs.append((pid, name))
    for pid, name in pairs:
        if str(pid) in missing and name:
            st["participants"][str(pid)] = str(name)
    print(f"Nomi squadre: {len(st['participants'])} in memoria")
    return st["participants"]


def _price(player) -> float | None:
    try:
        p = float(player.get("price"))
        return p if p > 1.0 else None
    except (TypeError, ValueError, AttributeError):
        return None


def _players(outcome) -> dict:
    if not isinstance(outcome, dict):
        return {}
    pl = outcome.get("players")
    if isinstance(pl, dict) and pl:
        return next(iter(pl.values())) if all(isinstance(v, dict) for v in pl.values()) else {}
    return outcome


def _pick_main(cands: list):
    """Tra le linee (linea, prezzo1, prezzo2, mainLine) sceglie quella principale del book."""
    if not cands:
        return None
    flagged = [c for c in cands if c[3]]
    pool = flagged or cands
    best = min(pool, key=lambda c: abs(1 / c[1] - 1 / c[2]))
    return [best[0], best[1], best[2]]


def parse_book(bk: dict, meta: dict) -> dict | None:
    """Quote di un book per una partita: 1X2, linea asiatica principale, linea gol principale."""
    if not isinstance(bk, dict) or bk.get("bookmakerIsActive") is False:
        return None
    markets = bk.get("markets") or {}
    out = {"x": None, "ah": None, "ou": None}
    ah, ou = [], []
    for mid, m in markets.items():
        if not isinstance(m, dict) or m.get("marketActive") is False:
            continue
        outs = m.get("outcomes") or {}
        info = meta.get(str(mid))
        if str(mid) == "101" or (info and info[0] == "1x2" and info[2] in ("fulltime", "result", "")):
            prices = []
            for oid in (sorted(outs, key=lambda k: int(k)) if outs else []):
                pl = _players(outs[oid])
                if pl.get("active") is False:
                    prices = []
                    break
                prices.append(_price(pl))
            if len(prices) == 3 and all(prices) and (out["x"] is None or str(mid) == "101"):
                out["x"] = prices
            continue
        if not info or info[2] not in ("fulltime", "result", ""):
            continue
        keys = sorted(outs, key=lambda k: int(k))
        if len(keys) != 2:
            continue
        p1, p2 = _players(outs[keys[0]]), _players(outs[keys[1]])
        a, b = _price(p1), _price(p2)
        if not a or not b or p1.get("active") is False or p2.get("active") is False:
            continue
        main = bool(p1.get("mainLine") or p2.get("mainLine"))
        if info[0] == "spreads":
            ah.append((AH_HOME_SIGN * info[1], a, b, main))
        elif info[0] == "totals" and info[1] > 0:
            ou.append((info[1], a, b, main))
    out["ah"] = _pick_main(ah)
    out["ou"] = _pick_main(ou)
    return out if any(out.values()) else None


def _fixture_entry(fx: dict, books: dict, code_by_tid: dict, stamp: str) -> dict:
    return {"code": code_by_tid.get(str(fx.get("tournamentId")), ""), "p1": fx.get("participant1Id"),
            "p2": fx.get("participant2Id"), "start": (parse_time(fx.get("startTime")) or now_utc()).isoformat(),
            "books": books, "t": stamp}


def take_snapshot(st: dict, books=None, force: bool = False) -> dict:
    """Quote attuali di tutte le partite dei 5 campionati: UNA chiamata per book
    (il piano gratuito accetta un solo book per chiamata)."""
    books = books or BOOKMAKERS
    tour = ensure_tournaments(st)
    meta = ensure_markets(st)
    code_by_tid = {str(v): k for k, v in tour.items()}
    snap, stamp = {}, now_utc().isoformat(timespec="seconds")
    for slug in books:
        try:
            data = api_get("/odds-by-tournaments", {"tournamentIds": ",".join(str(tour[c]) for c in LEAGUES_Q),
                                                    "bookmaker": slug}, st, force=force)
        except QuotaExhausted:
            raise
        except Exception as e:      # noqa: BLE001
            print(f"[WARN] quote di {slug} non lette: {e}")
            continue
        for fx in as_list(data):
            try:
                fid = str(fx["fixtureId"])
            except (KeyError, TypeError):
                continue
            if fx.get("statusId") not in (None, 0, 1, "0", "1"):
                continue                # gia' iniziata o finita
            entry = snap.setdefault(fid, _fixture_entry(fx, {}, code_by_tid, stamp))
            bk = (fx.get("bookmakerOdds") or {}).get(slug)
            parsed = parse_book(bk, meta) if bk else None
            if parsed:
                entry["books"][slug] = parsed
    print(f"Foto delle quote ({', '.join(books)}): {len(snap)} partite, chiamate del mese {st['calls']}/{MONTH_LIMIT}")
    return snap


def fixture_books(st: dict, fid: str, force: bool = False) -> dict:
    """Quote di adesso di UNA partita su tutti i book (una chiamata): servono a confermare un movimento."""
    meta = ensure_markets(st)
    data = api_get("/odds", {"fixtureId": fid}, st, force=force)
    fx = data if isinstance(data, dict) and "bookmakerOdds" in data else next(iter(as_list(data)), {})
    out = {}
    for slug in BOOKMAKERS:
        bk = (fx.get("bookmakerOdds") or {}).get(slug)
        parsed = parse_book(bk, meta) if bk else None
        if parsed:
            out[slug] = parsed
    return out


def _hist_price(entries, at):
    """Prezzo in vigore al momento 'at' (None = adesso) da una lista di cambi con createdAt."""
    best = None
    for e in entries or []:
        t = parse_time(e.get("createdAt"))
        if not t or (at and t > at):
            continue
        if best is None or t > best[0]:
            best = (t, e)
    if not best or best[1].get("active") is False:
        return None
    try:
        p = float(best[1].get("price"))
        return p if p > 1.0 else None
    except (TypeError, ValueError):
        return None


def historical_books(st: dict, fid: str, at=None, force: bool = False) -> dict:
    """Quote dei 3 book al momento 'at' (None = adesso) dallo storico della partita."""
    meta = ensure_markets(st)
    data = api_get("/historical-odds", {"fixtureId": fid, "bookmakers": ",".join(BOOKMAKERS)}, st, force=force)
    books = (data or {}).get("bookmakers") if isinstance(data, dict) else None
    out = {}
    for slug, bk in (books or {}).items():
        res = {"x": None, "ah": None, "ou": None}
        ah, ou = [], []
        for mid, m in ((bk or {}).get("markets") or {}).items():
            outs = (m or {}).get("outcomes") or {}
            keys = sorted(outs, key=lambda k: int(k))
            prices = []
            for k in keys:
                pls = (outs[k] or {}).get("players") or {}
                entries = next(iter(pls.values()), []) if isinstance(pls, dict) and pls else []
                prices.append(_hist_price(entries, at))
            info = meta.get(str(mid))
            if str(mid) == "101" and len(prices) == 3 and all(prices):
                res["x"] = prices
            elif info and info[2] in ("fulltime", "result", "") and len(prices) == 2 and all(prices):
                if info[0] == "spreads":
                    ah.append((AH_HOME_SIGN * info[1], prices[0], prices[1], False))
                elif info[0] == "totals" and info[1] > 0:
                    ou.append((info[1], prices[0], prices[1], False))
        res["ah"], res["ou"] = _pick_main(ah), _pick_main(ou)
        if any(res.values()):
            out[slug] = res
    return out


def merge_snapshot(st: dict, snap: dict, as_apertura: bool) -> None:
    """Mette la foto nello stato: 'last' per tutte, 'first' se nuova, 'ap' (apertura) se richiesto."""
    horizon = now_utc() + timedelta(days=APERTURA_LOOKAHEAD_DAYS, hours=6)
    for fid, s in snap.items():
        rec = st["fixtures"].setdefault(fid, {})
        rec.update(code=s["code"] or rec.get("code", ""), p1=s["p1"], p2=s["p2"], start=s["start"])
        point = {"t": s["t"], "books": s["books"]}
        if s["books"]:
            rec["last"] = point
            rec.setdefault("first", point)
            start = parse_time(s["start"])
            if as_apertura and start and start <= horizon:
                rec["ap"] = point


def cleanup(st: dict) -> None:
    limit = now_utc() - timedelta(days=KEEP_DAYS)
    st["fixtures"] = {k: v for k, v in st["fixtures"].items() if (parse_time(v.get("start")) or now_utc()) > limit}
    keep = (now_utc() - timedelta(days=10)).isoformat()
    st["done"] = [d for d in st["done"] if d.split("|", 1)[-1] >= keep[:16]][-400:]
    st["log"] = st["log"][-60:]


# =====================================================================
# Lettura dei movimenti (regole del foglio Mercato)
# =====================================================================
def novig(prices):
    inv = [1.0 / p for p in prices]
    s = sum(inv)
    return [x / s for x in inv]


def book_move(a: dict, b: dict) -> dict:
    """Movimento di un book da a (apertura) a b (adesso). dir: 'home' / 'away' / None; forza 1 quota, 2 un quarto, 3 mezzo gol."""
    res = {"dir": None, "force": 0, "ou": None, "dline": None, "dp": None}
    if a.get("ah") and b.get("ah"):
        dline = round(b["ah"][0] - a["ah"][0], 2)
        res["dline"] = dline
        if abs(dline) >= TH_LINE - 1e-9:
            res["dir"] = "home" if dline < 0 else "away"
            res["force"] = 3 if abs(dline) >= 0.5 - 1e-9 else 2
        else:
            dp = (novig(b["ah"][1:])[0] - novig(a["ah"][1:])[0]) * 100
            res["dp"] = dp
            if abs(dp) >= TH_PROB:
                res["dir"], res["force"] = ("home" if dp > 0 else "away"), 1
    elif a.get("x") and b.get("x"):
        pa, pb = novig(a["x"]), novig(b["x"])
        d1, d2 = (pb[0] - pa[0]) * 100, (pb[2] - pa[2]) * 100
        res["dp"] = d1
        if max(abs(d1), abs(d2)) >= TH_1X2:
            res["dir"], res["force"] = ("home" if d1 - d2 > 0 else "away"), 1
    if a.get("ou") and b.get("ou"):
        dl = round(b["ou"][0] - a["ou"][0], 2)
        if abs(dl) >= TH_LINE - 1e-9:
            res["ou"] = ("over" if dl > 0 else "under", dl)
        else:
            dpo = (novig(b["ou"][1:])[0] - novig(a["ou"][1:])[0]) * 100
            if abs(dpo) >= TH_OU_PROB:
                res["ou"] = ("over" if dpo > 0 else "under", dpo)
    return res


def read_movement(rec: dict) -> dict | None:
    """Confronto apertura -> adesso su tutti i book. None se non c'e' niente di importante."""
    base = rec.get("ap") or rec.get("first")
    now = rec.get("last")
    if not base or not now or base is now or base.get("t") == now.get("t"):
        return None
    moves = {}
    for slug in BOOKMAKERS:
        a, b = (base["books"] or {}).get(slug), (now["books"] or {}).get(slug)
        if a and b:
            moves[slug] = book_move(a, b)
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
        agree = [s for s, m in moves.items() if m["ou"] and m["ou"][0] == d]
        if len(agree) >= 2:
            ou = {"dir": d, "books": agree}
    # solo Bet365 si muove e i book "che fanno il prezzo" no
    public = None
    pub = moves.get("bet365")
    if pub and pub["dir"] and not side and not any(moves.get(s, {}).get("dir") == pub["dir"] for s in SHARP_BOOKS):
        public = pub["dir"]
    if not side and not ou:
        return None
    # favorita all'apertura (1X2 senza margine del primo book che ce l'ha)
    fav = None
    for slug in BOOKMAKERS:
        x = (base["books"].get(slug) or {}).get("x")
        if x:
            p = novig(x)
            if abs(p[0] - p[2]) >= FAV_GAP:
                fav = "home" if p[0] > p[2] else "away"
            break
    return {"side": side, "ou": ou, "public": public, "fav": fav, "moves": moves, "base": base, "now": now}


def verdict(mv: dict, names: dict) -> str:
    side, fav = mv["side"], mv["fav"]
    if not side:
        return ""
    team = names[side["dir"]]
    nb = len(side["books"])
    why = f"su {nb} book su 3"
    if fav is None or side["dir"] == fav:
        if side["force"] >= 2:
            return f"Verde forte a <b>{team}</b> (linea spostata verso di lei {why})"
        return f"Verde a <b>{team}</b> (stessa linea, quota scesa {why})"
    fav_team = names[fav]
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


def match_calendar(rec: dict, pnames: dict, cal: list) -> dict | None:
    """Collega la partita di OddsPapi a quella del calendario (stesso campionato e orario, nomi simili)."""
    start = parse_time(rec.get("start"))
    if not start:
        return None
    cands = [m for m in cal if m["code"] == rec.get("code") and abs((m["ko"] - start).total_seconds()) <= 25 * 60]
    if not cands:
        return None
    n1, n2 = pnames.get(str(rec.get("p1")), ""), pnames.get(str(rec.get("p2")), "")
    if len(cands) == 1 and not (n1 and n2):
        return cands[0]
    best, score = None, 0.0
    for m in cands:
        s = _similar(n1, m["home"]) + _similar(n1, m["home_short"]) + _similar(n2, m["away"]) + _similar(n2, m["away_short"])
        if s > score:
            best, score = m, s
    return best if score > 0 else (cands[0] if len(cands) == 1 else None)


def fmt_num(x: float, dec: int = 2) -> str:
    return f"{x:.{dec}f}".replace(".", ",")


def fmt_line(h: float) -> str:
    if abs(h) < 1e-9:
        return "0"
    s = f"{abs(h):.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return ("−" if h < 0 else "+") + s


def team_names(rec: dict, pnames: dict, cal_m: dict | None) -> dict:
    if cal_m:
        home = split_camel(HASHTAGS.get(cal_m["home"], "")) or cal_m["home_short"] or cal_m["home"]
        away = split_camel(HASHTAGS.get(cal_m["away"], "")) or cal_m["away_short"] or cal_m["away"]
        tags = [make_hashtag(HASHTAGS.get(cal_m["home"], "")) or make_hashtag(home),
                make_hashtag(HASHTAGS.get(cal_m["away"], "")) or make_hashtag(away)]
    else:
        home = pnames.get(str(rec.get("p1"))) or "Casa"
        away = pnames.get(str(rec.get("p2"))) or "Ospite"
        tags = [make_hashtag(home), make_hashtag(away)]
    return {"home": home, "away": away, "tags": [t for t in tags if t]}


def book_lines(mv: dict, names: dict) -> list:
    lines = []
    for slug in BOOKMAKERS:
        a, b = (mv["base"]["books"] or {}).get(slug), (mv["now"]["books"] or {}).get(slug)
        if not a or not b:
            continue
        label = BOOK_LABEL.get(slug, slug)
        parts = []
        if a.get("ah") and b.get("ah"):
            parts.append(f"{esc(names['home'])} {fmt_line(a['ah'][0])} → {fmt_line(b['ah'][0])} "
                         f"({fmt_num(a['ah'][1])} → {fmt_num(b['ah'][1])})")
        elif a.get("x") and b.get("x"):
            parts.append(f"1 {fmt_num(a['x'][0])}→{fmt_num(b['x'][0])} · X {fmt_num(a['x'][1])}→{fmt_num(b['x'][1])} · "
                         f"2 {fmt_num(a['x'][2])}→{fmt_num(b['x'][2])}")
        if not parts:
            continue
        mark = " ✅" if (mv["side"] and slug in mv["side"]["books"]) else ""
        lines.append(f"<b>{label}</b>: {' · '.join(parts)}{mark}")
    # 1X2 di Pinnacle (o del primo book che lo ha), sempre utile
    for slug in BOOKMAKERS:
        a, b = (mv["base"]["books"] or {}).get(slug), (mv["now"]["books"] or {}).get(slug)
        if a and b and a.get("x") and b.get("x"):
            pa, pb = novig(a["x"]), novig(b["x"])
            lines.append(f"1X2 {BOOK_LABEL.get(slug, slug)}: 1 {fmt_num(a['x'][0])}→{fmt_num(b['x'][0])} · "
                         f"X {fmt_num(a['x'][1])}→{fmt_num(b['x'][1])} · 2 {fmt_num(a['x'][2])}→{fmt_num(b['x'][2])} "
                         f"(casa {round(pa[0] * 100)}%→{round(pb[0] * 100)}%)")
            break
    if mv["ou"]:
        for slug in BOOKMAKERS:
            a, b = (mv["base"]["books"] or {}).get(slug), (mv["now"]["books"] or {}).get(slug)
            if a and b and a.get("ou") and b.get("ou"):
                lines.append(f"Gol ({BOOK_LABEL.get(slug, slug)}): linea {fmt_num(a['ou'][0], 2).rstrip('0').rstrip(',')} → "
                             f"{fmt_num(b['ou'][0], 2).rstrip('0').rstrip(',')} · Over {fmt_num(a['ou'][1])} → {fmt_num(b['ou'][1])}")
                break
    return lines


def when_text(iso: str) -> str:
    t = parse_time(iso)
    if not t:
        return "?"
    t = t.astimezone(ROME)
    days = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
    return f"{days[t.weekday()]} {t:%H:%M}"


def build_message(rec: dict, mv: dict, names: dict) -> str:
    lg = LEAGUES_Q.get(rec.get("code"), {"flag": "", "name": ""})
    ko = parse_time(rec.get("start"))
    head = (f"{lg['flag']} <b>{esc(lg['name'])} · {esc(names['home'])} – {esc(names['away'])}</b>"
            f"{' · ' + ko.astimezone(ROME).strftime('%H:%M') if ko else ''}")
    rows = [head] + book_lines(mv, names)
    v = verdict(mv, names)
    if v:
        rows.append(f"➜ {v}")
    if mv["ou"]:
        rows.append(f"➜ Linea gol verso l'<b>{'Over' if mv['ou']['dir'] == 'over' else 'Under'}</b> "
                    f"(su {len(mv['ou']['books'])} book su 3)")
    if mv["public"]:
        rows.append(f"⚠️ Bet365 (pubblico) va verso {esc(names[mv['public']])}, Pinnacle e Singbet no: non seguirlo")
    base_label = "apertura" if rec.get("ap") is mv["base"] else "prima foto"
    rows.append(f"<i>{base_label} {when_text(mv['base']['t'])} → adesso {when_text(mv['now']['t'])} (formazioni uscite)</i>")
    if names["tags"]:
        rows.append(" ".join("#" + t for t in names["tags"]))
    return "\n".join(rows)


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
            send_telegram_message(
                "📈 <b>Qui arrivano solo le quote.</b>\n\n"
                "• <b>Apertura</b>: il martedi' e il venerdi' alle 15 il bot fotografa le quote di tutte le partite dei 5 "
                "campionati (Pinnacle, Singbet, Bet365).\n"
                "• <b>A ridosso</b>: 40 minuti prima di ogni partita (formazioni uscite) le riguarda e ti scrive SOLO se "
                "si sono mosse in modo importante su almeno 2 book su 3, con il colore da mettere nella riga "
                "<b>Mercato</b> della Direzione generale.\n\n"
                "Tocca l'hashtag di una squadra per vedere insieme notizie e quote.",
                disable_preview=True, chat_id=self.group_id, thread_id=tid)
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
def kickoff_groups(cal: list, merge_min: int) -> list:
    groups = []
    for m in cal:
        if groups and (m["ko"] - groups[-1]["first"]).total_seconds() <= merge_min * 60:
            groups[-1]["matches"].append(m)
            groups[-1]["last"] = m["ko"]
        else:
            groups.append({"first": m["ko"], "last": m["ko"], "matches": [m]})
    return groups


def due_apertura(st: dict, cal: list, now: datetime) -> str | None:
    loc = now.astimezone(ROME)
    if loc.weekday() not in APERTURA_DAYS or not (APERTURA_HOUR <= loc.hour < APERTURA_HOUR + APERTURA_WINDOW_HOURS):
        return None
    key = f"A|{loc:%Y-%m-%d}T{APERTURA_HOUR:02d}"
    if key in st["done"]:
        return None
    horizon = now + timedelta(days=APERTURA_LOOKAHEAD_DAYS)
    if not any(now < m["ko"] <= horizon for m in cal):
        return None
    return key


def due_ridosso(st: dict, cal: list, now: datetime):
    merge = MERGE_MINUTES_SAVING if st["calls"] >= SAVING_FROM else MERGE_MINUTES
    for g in kickoff_groups([m for m in cal if m["ko"] > now], merge):
        start_at = g["first"] - timedelta(minutes=RIDOSSO_MINUTES)
        latest = g["first"] - timedelta(minutes=RIDOSSO_LATEST_MINUTES)
        key = f"R|{g['first'].isoformat()[:16]}"
        if start_at <= now <= latest and key not in st["done"]:
            return key, g
    return None, None


# =====================================================================
# Azioni
# =====================================================================
def do_apertura(st: dict, topic: QuoteTopic, key: str | None, force: bool = False) -> None:
    snap = take_snapshot(st, force=force)
    merge_snapshot(st, snap, as_apertura=True)
    ids = {s["p1"] for s in snap.values()} | {s["p2"] for s in snap.values()}
    ensure_participants(st, ids)
    if key:
        st["done"].append(key)
    per = {}
    horizon = now_utc() + timedelta(days=APERTURA_LOOKAHEAD_DAYS, hours=6)
    for s in snap.values():
        start = parse_time(s["start"])
        if s["books"] and start and start <= horizon:
            per[s["code"]] = per.get(s["code"], 0) + 1
    if not per:
        print("Apertura: nessuna partita con quote nei prossimi giorni")
        return
    detail = " · ".join(f"{LEAGUES_Q[c]['flag']} {n}" for c, n in per.items() if c in LEAGUES_Q)
    books = sorted({b for s in snap.values() for b in s["books"]})
    topic.send(f"📸 <b>Apertura fatta</b> ({when_text(now_utc().isoformat())}): {sum(per.values())} partite · {detail}\n"
               f"Book: {', '.join(BOOK_LABEL.get(b, b) for b in books)}\n"
               f"<i>Ti scrivo 40 minuti prima delle partite solo se le quote si muovono davvero. "
               f"Chiamate usate questo mese: {st['calls']}/{MONTH_LIMIT}.</i>")


CONFIRM_WITH = "odds"            # conferma sugli altri book: "odds" (quote di adesso della partita) o "historical" (storico)


def confirm_books(st: dict, fid: str, force: bool = False) -> dict:
    if CONFIRM_WITH == "historical":
        return historical_books(st, fid, None, force=force)
    return fixture_books(st, fid, force=force)


def pinnacle_flag(rec: dict, saving: bool) -> bool:
    """Pinnacle si e' mosso abbastanza da valere una chiamata di conferma sugli altri book?"""
    base = rec.get("ap") or rec.get("first")
    now = rec.get("last")
    if not base or not now or base.get("t") == now.get("t"):
        return False
    a, b = (base.get("books") or {}).get("pinnacle"), (now.get("books") or {}).get("pinnacle")
    if not a or not b:
        return False
    m = book_move(a, b)
    if saving:
        return m["force"] >= 2 or bool(m["ou"] and abs(m["ou"][1]) >= TH_LINE and abs(m["ou"][1]) < 1.5)
    return bool(m["dir"] or m["ou"])


def do_ridosso(st: dict, topic: QuoteTopic, key: str | None, group: dict | None, cal: list, force: bool = False) -> int:
    """40 minuti prima: UNA chiamata su Pinnacle per tutte le partite; per quelle in cui Pinnacle si e' mosso,
    UNA chiamata per partita per vedere gli altri book (regola dei 2 book su 3)."""
    snap = take_snapshot(st, books=["pinnacle"], force=force)
    merge_snapshot(st, snap, as_apertura=False)
    if key:
        st["done"].append(key)
    if group:
        lo, hi = group["first"] - timedelta(minutes=5), group["last"] + timedelta(minutes=5)
    else:   # controllo a mano: le prossime partite
        fut = sorted(t for t in (parse_time(v.get("start")) for v in st["fixtures"].values()) if t and t > now_utc())
        if not fut:
            print("Nessuna partita in arrivo")
            return 0
        lo, hi = fut[0] - timedelta(minutes=5), fut[0] + timedelta(minutes=MERGE_MINUTES + 5)
    targets = {fid: rec for fid, rec in st["fixtures"].items()
               if lo <= (parse_time(rec.get("start")) or now_utc()) <= hi}
    pnames = ensure_participants(st, {r.get("p1") for r in targets.values()} | {r.get("p2") for r in targets.values()})
    saving = st["calls"] >= SAVING_FROM
    sent = checked = 0
    for fid, rec in sorted(targets.items(), key=lambda kv: kv[1].get("start", "")):
        names = team_names(rec, pnames, match_calendar(rec, pnames, cal))
        if not pinnacle_flag(rec, saving):
            print(f"  {names['home']} - {names['away']}: Pinnacle fermo")
            continue
        try:
            books = confirm_books(st, fid, force=force)
            checked += 1
        except QuotaExhausted:
            raise
        except Exception as e:      # noqa: BLE001
            print(f"  {names['home']} - {names['away']}: conferma non riuscita ({e})")
            continue
        if books:
            rec["last"] = {"t": now_utc().isoformat(timespec="seconds"), "books": books}
        mv = read_movement(rec)
        if not mv:
            print(f"  {names['home']} - {names['away']}: Pinnacle mosso, gli altri book no")
            continue
        if topic.send(build_message(rec, mv, names)):
            sent += 1
            rec["sent"] = now_utc().isoformat(timespec="seconds")
            time.sleep(SEND_DELAY_GROUP_SECONDS)
        print(f"  {names['home']} - {names['away']}: MOVIMENTO confermato -> inviato")
    st["log"].append(f"{now_utc().isoformat(timespec='minutes')} ridosso {len(targets)} partite, {checked} conferme, "
                     f"{sent} messaggi, chiamate {st['calls']}")
    return sent


def _safe_account(acc) -> str:
    """Dell'account solo numeri e nomi di piano/book (mai email o dati personali: il registro e' pubblico)."""
    nums, books = [], []

    def walk(x, path):
        if isinstance(x, dict):
            for k, v in x.items():
                kl = str(k).lower()
                if kl in ("email", "api_key", "apikey", "name", "first_name", "last_name", "phone", "customer_id"):
                    continue
                if kl == "bookmakers":
                    if isinstance(v, dict):
                        books.extend(list(v.keys()))
                    elif isinstance(v, list):
                        books.extend(str(b.get("slug") if isinstance(b, dict) else b) for b in v)
                    continue
                walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(x, list):
            for i, v in enumerate(x[:3]):
                walk(v, f"{path}[{i}]")
        elif isinstance(x, bool) or x is None:
            return
        elif isinstance(x, (int, float)):
            nums.append(f"{path}={x}")
        elif isinstance(x, str) and any(w in path.lower() for w in ("plan", "tier", "segment", "package", "limit")):
            nums.append(f"{path}={x[:40]}")
    walk(acc, "")
    ours = [b for b in books if any(k in b for k in ("pinnacle", "singbet", "sbobet", "bet365"))]
    return f"numeri: {nums[:25]} | book nell'abbonamento: {len(books)} (nostri: {ours[:12]})"


def do_test(st: dict, topic: QuoteTopic, cal: list) -> None:
    """Prova: cosa permette la chiave gratuita e quanto consuma ogni tipo di chiamata."""
    print("=== PROVA BOT QUOTE ===")

    def account(label):
        try:
            print(f"Account {label}: {_safe_account(api_get('/account', {}, st, counts=False, force=True))}")
        except Exception as e:      # noqa: BLE001
            print(f"[WARN] account non letto: {e}")

    account("all'inizio")
    ensure_tournaments(st)
    ensure_markets(st)
    snap = take_snapshot(st, books=["pinnacle"], force=True)
    merge_snapshot(st, snap, as_apertura=False)
    cnt = {}
    for v in snap.values():
        b = v["books"].get("pinnacle") or {}
        c = cnt.setdefault(v["code"], [0, 0, 0, 0])
        c[0] += 1
        c[1] += 1 if b.get("x") else 0
        c[2] += 1 if b.get("ah") else 0
        c[3] += 1 if b.get("ou") else 0
    print("Pinnacle per campionato [partite, 1X2, asiatico, gol]:", cnt)
    agree = disagree = 0
    for v in snap.values():
        b = v["books"].get("pinnacle")
        if b and b.get("x") and b.get("ah") and abs(b["ah"][0]) >= 0.25:
            ok = (b["x"][0] < b["x"][2]) == (b["ah"][0] < 0)
            agree, disagree = agree + ok, disagree + (not ok)
    print(f"Segno della linea asiatica: d'accordo con l'1X2 {agree}, al contrario {disagree}")
    account("dopo 1 chiamata per campionati")
    upcoming = sorted(((parse_time(v["start"]), fid) for fid, v in snap.items() if parse_time(v["start"]) and
                       parse_time(v["start"]) > now_utc()), key=lambda x: x[0])
    sample_fid = upcoming[0][1] if upcoming else None
    odds_books = {}
    if sample_fid:
        try:
            data = api_get("/odds", {"fixtureId": sample_fid}, st, force=True)
            fx = data if isinstance(data, dict) and "bookmakerOdds" in data else next(iter(as_list(data)), {})
            slugs = sorted((fx.get("bookmakerOdds") or {}).keys())
            print(f"/odds di una partita: {len(slugs)} book, i nostri: {[x for x in slugs if x in BOOKMAKERS]}")
            odds_books = {}
            meta = ensure_markets(st)
            for slug in BOOKMAKERS:
                bk = (fx.get("bookmakerOdds") or {}).get(slug)
                pb = parse_book(bk, meta) if bk else None
                if pb:
                    odds_books[slug] = pb
            print("  quote lette:", {k: {kk: vv for kk, vv in v.items() if vv} for k, v in odds_books.items()})
        except Exception as e:      # noqa: BLE001
            print(f"[WARN] /odds non riuscito: {e}")
        account("dopo /odds")
        try:
            hb = historical_books(st, sample_fid, None, force=True)
            print("Storico: book con dati:", sorted(hb), {k: {kk: vv for kk, vv in v.items() if vv} for k, v in hb.items()})
        except Exception as e:      # noqa: BLE001
            print(f"[WARN] storico non riuscito: {e}")
        account("dopo storico")
    ids = {v["p1"] for v in snap.values()} | {v["p2"] for v in snap.values()}
    pnames = ensure_participants(st, ids)
    sample = ""
    if sample_fid:
        rec = st["fixtures"][sample_fid]
        names = team_names(rec, pnames, match_calendar(rec, pnames, cal))
        lg = LEAGUES_Q.get(rec.get("code"), {"flag": "", "name": ""})
        rows = [f"{lg['flag']} <b>{esc(names['home'])} – {esc(names['away'])}</b> · {when_text(rec['start'])}"]
        src = odds_books or {"pinnacle": rec["last"]["books"].get("pinnacle")}
        for slug in BOOKMAKERS:
            b = src.get(slug)
            if not b:
                rows.append(f"<b>{BOOK_LABEL.get(slug, slug)}</b>: nessuna quota")
                continue
            bits = []
            if b.get("ah"):
                bits.append(f"{esc(names['home'])} {fmt_line(b['ah'][0])} ({fmt_num(b['ah'][1])} / {fmt_num(b['ah'][2])})")
            if b.get("x"):
                bits.append(f"1X2 {fmt_num(b['x'][0])} · {fmt_num(b['x'][1])} · {fmt_num(b['x'][2])}")
            if b.get("ou"):
                bits.append(f"gol {fmt_num(b['ou'][0], 2).rstrip('0').rstrip(',')} (Over {fmt_num(b['ou'][1])})")
            rows.append(f"<b>{BOOK_LABEL.get(slug, slug)}</b>: " + " · ".join(bits))
        sample = "\n".join(rows)
    topic.send("🧪 <b>Prova del bot quote</b>\n"
               f"Partite con quote Pinnacle: {len(snap)} · chiamate usate questo mese: {st['calls']}/{MONTH_LIMIT}\n\n"
               + (f"Esempio, quote di adesso:\n{sample}" if sample else ""))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="auto", choices=["auto", "test", "ora", "apertura"])
    args = ap.parse_args()
    if not API_KEY:
        print("Bot quote: manca il secret ODDSPAPI_API_KEY, non faccio niente")
        return 0
    st = load_qstate()
    cal = calendar_matches()
    now = now_utc()
    topic = QuoteTopic(st)
    try:
        if args.mode == "test":
            do_test(st, topic, cal)
        elif args.mode == "apertura":
            do_apertura(st, topic, None, force=True)
        elif args.mode == "ora":
            do_ridosso(st, topic, None, None, cal, force=True)
        else:
            key = due_apertura(st, cal, now)
            if key:
                print(f"Bot quote: apertura ({key})")
                do_apertura(st, topic, key)
            rkey, group = due_ridosso(st, cal, now)
            if rkey:
                names = ", ".join(f"{m['home_short']}-{m['away_short']}" for m in group["matches"])
                print(f"Bot quote: controllo a ridosso ({rkey}): {names}")
                do_ridosso(st, topic, rkey, group, cal)
            if not key and not rkey:
                print("Bot quote: niente da fare adesso")
                return 0
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
