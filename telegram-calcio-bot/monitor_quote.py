"""
Bot QUOTE: come si muovono le quote dei 5 campionati e delle coppe europee (OddsPapi, piano gratuito).

COSA FA
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
  medio (da farsi domande), sotto 4 rumore. Per EUROPA e CONFERENCE LEAGUE,
  nelle sere in cui insieme hanno piu' di CUP_BUSY_MATCHES (8) partite, solo da
  FORZA_MIN_BUSY (6/10): forti e medio-forti. Gli avvisi della stessa ora
  partono DAL PIU' FORTE.
- Il messaggio: una tabella apertura/adesso (Pinnacle) con 1X2, asiatico,
  linea gol, Over 2,5, GG e, per ogni squadra, GOL ATTESI e CORNER ATTESI
  (quanti se ne aspetta il mercato: ricavati da linea e quote dei gol/corner di
  squadra; se i gol di squadra non sono quotati, da linea gol e 1X2); il
  grafico della quota in barre (e ↩️ se e' tornata indietro di almeno un quinto
  dal suo punto estremo), QUANDO si e' mossa, "Si muovono anche" (gli altri
  movimenti buoni), LETTURA (cosa puo' voler dire, come domanda), colore per la
  riga "Mercato" della Direzione generale e pronostico dalle quote.
- ULTIMI MINUTI: da 12 a 3 minuti prima del fischio rilegge le partite e scrive
  SOLO per i casi forti: 🚨 un movimento da FORZA_FORTE (7/10) in su nato dopo
  il controllo dei 40 minuti (misurato solo su quel tratto), o ⚠️ RIBALTONE (un
  segnale forte gia' mandato che dall'apertura non arriva piu' a 4/10).
- «NON CONTROLLATE»: se una partita non e' nell'elenco di OddsPapi, o le sue
  quote non si riescono a leggere entro 12 minuti dal fischio, lo scrive. Cosi'
  il silenzio vuol dire davvero "nessun segnale".
- FILE PER IL PACE INDEX: state/mercato.csv, una riga per partita controllata
  (giudizio e colore per la riga Mercato, forza, quote di apertura e di adesso,
  gol e corner attesi). I file Excel lo leggono con Power Query.
- La legenda la manda la prima volta e quando cambia (LEGEND_VERSION).
- Il venerdi' alle 15 (e il martedi', se c'e' il turno infrasettimanale)
  aggiorna l'elenco delle partite e te lo dice con un messaggio breve.
- COPPE (Champions, Europa e Conference League): le partite arrivano
  dall'elenco OddsPapi, letto il LUNEDI' alle 15 (una chiamata, a parte da
  quella dei campionati). Il lunedi' alle 15 e' anche la loro APERTURA (dopo il
  turno di campionato). L'elenco viene RILETTO alle 11 nei giorni con partite
  di coppa nelle 36 ore dopo (martedi', mercoledi', giovedi': 1 chiamata, senza
  messaggi): prende le partite pubblicate dopo il lunedi' e gli orari cambiati.
  Tutte le partite, tranne a luglio e agosto (preliminari): li' solo quelle con
  almeno una squadra dei 5 campionati (CUPS_ONLY_TOP5 / CUPS_TOP5_MONTHS). Le
  squadre dei 5 campionati hanno gli stessi nomi italiani e hashtag del
  campionato.
- Il RIEPILOGO delle 19 (partite di domani) e' SPENTO dal 14/11/2026
  (RIEPILOGO_AUTO); a mano resta: --mode riepilogo.
- Ogni partita controllata lascia i suoi numeri nello stato ("stats"): servono
  a tarare le soglie.
- Tutto nell'argomento "📈 Quote" del gruppo (lo crea il bot).

QUANTO CONSUMA: lo storico delle quote NON conta nelle 250 chiamate al mese
del piano gratuito (verificato con il contatore dell'account il 6/11/2026).
Contano solo gli aggiornamenti dell'elenco partite (venerdi' i campionati,
lunedi' le coppe, a volte il martedi'; le riletture delle coppe: fino a 3 per
settimana di coppe), i nomi delle squadre nuove e l'elenco dei mercati (1 al
mese): 25-40 chiamate al mese. Un contatore (allineato a quello dell'account)
non fa mai superare il limite.

COME PARTE: lo lancia il giro ogni 5 minuti del bot notizie (monitor-news.yml,
avviato da cron-job.org). Quasi sempre controlla l'ora ed esce subito.
Prove a mano: workflow "Prova bot quote".

STATO: state/quote_state.json e state/mercato.csv (solo questi file; lo stato
delle notizie lo legge e basta, per sapere qual e' il gruppo Telegram).

Uso: python monitor_quote.py                   giro normale
     python monitor_quote.py --mode test       prova (diagnostica + messaggio di prova)
     python monitor_quote.py --mode ora        controllo subito delle prossime partite
     python monitor_quote.py --mode apertura   aggiorna subito l'elenco delle partite (campionati e coppe)
     python monitor_quote.py --mode riepilogo  riepilogo subito delle partite di domani
     python monitor_quote.py --mode rivedi [--partita Roma]
                                               rilegge le partite gia' giocate come 40 minuti prima:
                                               con --partita manda quelle partite; senza, il conto
                                               forti/medi/rumore della settimana e le 3 piu' forti
     python monitor_quote.py --mode esempio [--partita tutto]
                                               prova grafica nel gruppo (quote vere): legenda, tre avvisi,
                                               un esempio degli ultimi minuti e la riga «Non controllate»;
                                               con tutto anche apertura delle coppe e riepiloghi
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
PACE_FILE = os.path.join(os.path.dirname(__file__), "state", "mercato.csv")     # letto dai file Excel Pace Index

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
CUP_REREAD_HOUR = 11            # coppe: elenco riletto alle 11 se ci sono partite di coppa nelle prossime...
CUP_REREAD_AHEAD_HOURS = 36     # ...36 ore (martedi', mercoledi' e giovedi' delle settimane di coppa: 1 chiamata)
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
RIEPILOGO_AUTO = False          # riepilogo automatico delle 19 spento (14/11/2026); a mano resta: --mode riepilogo
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
CUP_BUSY_CODES = ("EL", "ECL")  # Europa e Conference League: nei giorni in cui insieme hanno piu' di...
CUP_BUSY_MATCHES = 8            # ...8 partite (fase campionato, spareggi, ottavi)...
FORZA_MIN_BUSY = 6              # ...l'avviso parte solo da 6/10 (forti e medio-forti)
LAST_FROM_MINUTES = 12          # "ultimi minuti": ricontrollo da 12 a 3 minuti prima del fischio. Scrive solo per un
LAST_TO_MINUTES = 3             # movimento forte (da FORZA_FORTE) nato dopo l'avviso, o per un segnale forte sparito
MISSED_MAX_MINUTES = 60         # partite non controllate in tempo: lo dice fino a un'ora dopo il fischio
LEV_SIDE = (3.0, 4.5, 6.0, 8.0, 10.0)   # handicap asiatico (o solo 1X2): punti per l'ampiezza 1-5
LEV_GOL = (3.5, 5.0, 6.5, 8.5, 10.5)    # linea gol: punti dell'Over per l'ampiezza 1-5
LEV_GG = (3.5, 5.0, 6.5, 8.0, 10.0)     # Goal/No Goal: punti del GG per l'ampiezza 1-5
LINE_PTS = 6.0                  # se la linea dell'apertura non c'e' piu': un quarto di linea vale circa 6 punti
MIN_BOOK_PTS = 1.5              # un book "si muove" (conferme, frecce, altro mercato) da 1,5 punti
EVENT_PTS = 3.0                 # corner/gol/tiri di squadra con la linea ferma: freccia da 3 punti dell'Over
EXP_STEP = {"tg": (0.08, 0.18), # gol attesi di una squadra: freccia da 0,08 gol di differenza, doppia da 0,18
            "tc": (0.20, 0.40)} # corner attesi di una squadra: freccia da 0,2 corner, doppia da 0,4
FORMAZIONI_MINUTES = 60         # le formazioni ufficiali escono circa un'ora prima
TENUTA_OK = 0.8                 # tenuta: adesso almeno l'80% del punto piu' alto = ha tenuto (2 punti)...
TENUTA_MEZZA = 0.5              # ...almeno la meta' = e' tornato un po' indietro (1); meno = rientrato (0)

SPARK = "▁▂▃▄▅▆▇█"             # andamento della quota: barra alta = quota alta
SPARK_POINTS = 10               # la quota in 10 tratti uguali dall'apertura ad adesso (11 barre)
SPARK_MIN_PTS = 4.0             # sotto 4 punti di probabilita' di differenza le barre restano quasi piatte

TOPIC_NAME = "📈 Quote"
TOPIC_COLOR = 9367192           # verde
KEEP_DAYS = 8                   # partite finite tenute nello stato una settimana (per "rivedi")
LEGEND_VERSION = 5              # se cambia, la legenda viene rimandata una volta (4 = tabella unica e grafico;
                                # 5 = gol e corner attesi, ultimi minuti, soglia Europa/Conference, niente riepilogo)
APERTURA_TRIES = 3              # elenco partite non letto all'apertura: si riprova al giro dopo, al massimo 3 volte
MARKETS_VERSION = 4             # se cambia, l'elenco dei mercati viene riletto subito (3-4 = corner, gol e tiri di squadra)
STATS_KEEP = 800                # numeri delle partite tenuti per tarare le soglie (40 minuti e ultimi minuti)
PACE_KEEP_DAYS = 10             # file per il Pace Index (mercato.csv): partite degli ultimi 10 giorni
RIVEDI_DAYS = 8                 # "rivedi": partite giocate negli ultimi 8 giorni
RIVEDI_BUDGET_SECONDS = 480     # "rivedi" di tutta la settimana: al massimo 8 minuti di letture
RIVEDI_TOP = 3                  # ...e nel gruppo le 3 partite piu' forti
ESEMPIO_READS = 16              # "esempio": per l'esempio degli ultimi minuti guarda fino a 16 partite giocate
LAST_REVIEW_MINUTES = 8         # prove sulle partite giocate: gli "ultimi minuti" sono le quote di 8 minuti prima
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


def _pois_pmf(lam: float, k: int) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def _over_prob(lam: float, line: float) -> float:
    """Probabilita' (senza margine) dell'Over di una linea se gli eventi sono in media 'lam' (Poisson): linea x,5
    secca; linea intera con rimborso = vince / (vince + perde); quarti (x,25 e x,75) = media delle due linee vicine."""
    q = int(round(line * 4)) % 4
    if q in (1, 3):
        return (_over_prob(lam, line - 0.25) + _over_prob(lam, line + 0.25)) / 2
    k = int(math.floor(line + 1e-9))
    below = sum(_pois_pmf(lam, i) for i in range(k + 1))        # fino a k compreso
    if q == 2:
        return 1.0 - below
    win, lose = 1.0 - below, below - _pois_pmf(lam, k)
    return win / (win + lose) if win + lose > 0 else 0.5


def expected_events(item) -> float | None:
    """Quanti eventi (gol, corner) si aspetta il mercato: la media che spiega una linea Over/Under
    [linea, quota over, quota under] tolto il margine. None se la linea non c'e' o e' troppo sbilanciata."""
    if not item or len(item) < 3 or not item[1] or not item[2] or item[0] <= 0:
        return None
    p = novig([item[1], item[2]])[0]
    if not 0.03 < p < 0.97:
        return None
    lo, hi = 0.01, 40.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if _over_prob(mid, item[0]) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def main_goals(snap: dict) -> tuple | None:
    """Gol attesi di casa e ospite dai mercati della partita (quando i gol di squadra non sono quotati): la somma
    dalla linea gol, la differenza dal 1X2."""
    x, ou = (snap or {}).get("x"), (snap or {}).get("ou")
    mu = expected_events(ou) if x and ou else None
    if not mu:
        return None
    pr = novig(x)
    target = pr[0] - pr[2]

    def gap(d):
        ph = [_pois_pmf((mu + d) / 2, i) for i in range(12)]
        pa = [_pois_pmf((mu - d) / 2, i) for i in range(12)]
        return sum(ph[i] * pa[j] * (1 if i > j else -1) for i in range(12) for j in range(12) if i != j)
    lo, hi = -mu + 0.04, mu - 0.04
    for _ in range(40):
        mid = (lo + hi) / 2
        if gap(mid) < target:
            lo = mid
        else:
            hi = mid
    d = (lo + hi) / 2
    return (mu + d) / 2, (mu - d) / 2


def event_debug(row: dict) -> dict:
    """Per il registro delle prove: da dove arriva una riga di eventi di squadra, linee di adesso e attesi."""
    out = {"src": row.get("src")}
    if row.get("calc"):
        out["calc"] = True
    for side in ("home", "away"):
        item = row.get(side)
        if item:
            out[side] = item[1][0] if item[1] else None
        if side in (row.get("exp") or {}):
            out[f"{side}_att"] = tuple(round(v, 2) for v in row["exp"][side])
    return out


def exp_move(ea: float, eb: float, g: str) -> tuple:
    """Eventi attesi di una squadra da ea a eb: (dir +1 di piu' / -1 di meno / 0, forte?)."""
    step, strong = EXP_STEP[g]
    diff = eb - ea
    return (_sign(diff), abs(diff) >= strong - 1e-9) if abs(diff) >= step - 1e-9 else (0, False)


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
    SOT_BOOK (extra), solo come informazione. {gruppo: {"src": book, "home": (apertura, adesso, dir, forte), ...,
    "exp": {"home": (attesi all'apertura, attesi adesso), ...}}}. Per gol e corner la freccia segue gli ATTESI
    (quanti se ne aspetta il mercato, ricavati da linea e quote). Se i gol di squadra non sono quotati, i gol attesi
    arrivano dai mercati della partita ("calc": non contano come «altro mercato» nella forza)."""
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
            row = {"src": s, "exp": {}}
            for side in ("home", "away"):
                if n.get(side):
                    ea, eb = (expected_events(b0.get(side)), expected_events(n[side])) if g in EXP_STEP else (None, None)
                    if ea is not None and eb is not None:
                        row["exp"][side] = (ea, eb)
                        d, strong = exp_move(ea, eb, g)
                    else:
                        d, strong = event_move(b0.get(side), n[side], g)
                    row[side] = (b0.get(side), n[side], d, strong)
            out[g] = row
            break
    if len((out.get("tg") or {}).get("exp") or {}) < 2:        # gol di squadra non quotati: dai mercati della partita
        for s in BOOKMAKERS:
            ga, gb = main_goals(R["base"].get(s)), main_goals(R["now"].get(s))
            if ga and gb:
                row = {"src": s, "calc": True, "exp": {"home": (ga[0], gb[0]), "away": (ga[1], gb[1])}}
                for i, side in enumerate(("home", "away")):
                    row[side] = (None, None) + exp_move(ga[i], gb[i], "tg")
                out["tg"] = row
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
    evdir = {f"{g}|{side}": row[side][2] for g, row in events.items() for side in ("home", "away")
             if side in row and not row.get("calc")}
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


def _main_rows(names: dict, a: dict, b: dict) -> list:
    """Righe della tabella per i mercati della partita: 1X2, asiatico, linea gol, Over 2,5, GG (apertura, adesso,
    freccia)."""
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
    return rows


EVENT_ROW = {"tc": "Corner", "tg": "Gol", "ts": "Tiri porta"}


def _short_names(names: dict) -> dict:
    """Nomi per le righe della tabella: al massimo 11 lettere e diversi tra le due squadre."""
    out = {}
    for side, other in (("home", "away"), ("away", "home")):
        n = names[side]
        if len(n) > 11:
            first, ofirst = n.split()[0], names[other].split()[0]
            n = first if 4 <= len(first) <= 11 and first != ofirst else n[:10] + "."
        out[side] = n
    return out


EXP_ORDER = ("tg", "tc", "ts")      # nella tabella: prima i gol, poi i corner
EXP_DEC = {"tg": 2, "tc": 1}        # gol attesi con 2 decimali, corner attesi con 1


def fmt_table_one(names: dict, an: dict) -> tuple:
    """TABELLA UNICA (caratteri a larghezza fissa, sta nello schermo del telefono): apertura e adesso del book di
    riferimento per i mercati della partita e, sotto, GOL ATTESI e CORNER ATTESI di ogni squadra: quanti se ne
    aspetta il mercato, ricavati da linea e quote (▲ = di piu', doppia = movimento forte). Dove gli attesi non si
    possono ricavare resta la linea. * = da un altro book. Ritorna (tabella, nota sotto)."""
    a, b = an["a"], an["b"]
    rows, others = _main_rows(names, a, b), []
    sn = _short_names(names)
    for g in EXP_ORDER:
        row = an["events"].get(g) or {}
        if not (row.get("home") or row.get("away")):
            continue
        star = "" if row.get("src") == "pinnacle" else "*"
        if star:
            book = BOOK_LABEL.get(row.get("src"), str(row.get("src")))
            others.append(f"{EVENT_ROW[g].lower()} da {book}" + (", solo informazione" if row.get("src") == SOT_BOOK
                                                                 else ""))
        exp = row.get("exp") or {}
        if exp:
            rows.append((f"{EVENT_ROW[g]} attesi{star}", "", "", ""))
        for side in ("home", "away"):
            item = row.get(side)
            if not item:
                continue
            a0, b0, d, strong = item
            arrow = "" if d == 0 else ("▲" if d > 0 else "▼") * (2 if strong else 1)
            if side in exp:
                rows.append((f" {sn[side]}", fmt_num(exp[side][0], EXP_DEC[g]), fmt_num(exp[side][1], EXP_DEC[g]), arrow))
            elif b0:
                rows.append((f"{EVENT_ROW[g]} {sn[side]}{star}", fmt_goal(a0[0]) if a0 else "—", fmt_goal(b0[0]), arrow))
    if not an["events"].get("tc") and a.get("ct") and b.get("ct"):
        rows.append(("Corner tot.", fmt_goal(a["ct"][0]), fmt_goal(b["ct"][0]), arrow_l(a["ct"][0], b["ct"][0])))
    if not rows:
        return "", ""
    w = max(len(r[0]) for r in rows)
    table = _pre([f"{'':<{w}} {'apert.':>6} {'adesso':>6}"] +
                 [f"{r[0]:<{w}} {r[1]:>6} {r[2]:>6} {r[3]}".rstrip() for r in rows])
    return table, ("* " + "; ".join(others) + " (Pinnacle non li quota)" if others else "")


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
            return f" I corner attesi di {N[team]} salgono."
        if item and item[2] < 0:
            return f" Ma i corner attesi di {N[team]} scendono."
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
        if "pinnacle" not in s["books"]:
            head += " · ⚠️ senza Pinnacle"
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


CHART_POINTS = 21               # avviso: la quota in 21 tratti uguali dall'apertura ad adesso (22 barre)


def spark(pts: list) -> str:
    """Barre dell'andamento di una quota: barra alta = quota alta; sotto SPARK_MIN_PTS punti di probabilita' di
    differenza restano quasi piatte."""
    probs = [1.0 / v for v in pts]
    span = max(max(probs) - min(probs), SPARK_MIN_PTS / 100.0)
    lo = (max(probs) + min(probs) - span) / 2
    return "".join(SPARK[max(0, min(7, int(round((1 - (p - lo) / span) * 7))))] for p in probs)


def _step_text(minutes: float) -> str:
    """Quanto tempo vale una barra, a parole: 'ora', 'ora e mezza', '2 ore', '40 minuti'..."""
    halves = int(round(minutes / 30.0))
    if halves < 2:
        return f"{max(10, int(round(minutes / 10.0)) * 10)} minuti"
    whole, half = divmod(halves, 2)
    if whole == 1:
        return "ora e mezza" if half else "ora"
    return f"{whole} ore" + (" e mezza" if half else "")


def chart_team(an: dict) -> str | None:
    """Squadra del grafico (la direzione della partita): quella del giudizio se c'e' un segnale sul segno (la
    favorita, o quella su cui si muove il mercato se non c'e' favorita), se no la favorita, se no la piu' bassa."""
    if any(s["fam"] == "side" for s in an["shown"]) and an.get("team"):
        return an["team"]
    if an.get("fav"):
        return an["fav"]
    x = an["b"].get("x")
    return ("home" if x[0] <= x[2] else "away") if x else None


def chart_block(an: dict, names: dict, ko: datetime | None) -> list:
    """📊 GRAFICO della direzione della partita: la quota 1X2 della squadra del grafico dall'apertura ad adesso in
    CHART_POINTS+1 barre (barra alta = quota alta; il punto estremo si vede sempre) e ⏱ quando si e' mossa (di
    colpo o piano piano), cosa e' successo dopo le formazioni e ↩️ se e' tornata indietro."""
    R = an.get("R") or {}
    team, h = chart_team(an), (R.get("bh") or {}).get(an["ref"])
    t0, t1 = R.get("base_at"), R.get("at") or an.get("at") or now_utc()
    if not team or not h or not t0 or t1 <= t0:
        return []
    idx = 0 if team == "home" else 2

    def price(t):
        x = h.snapshot(t, {"main"}, {"1x2"}).get("x")
        return x[idx] if x else None
    ts = [t0 + (t1 - t0) * (i / CHART_POINTS) for i in range(CHART_POINTS + 1)]
    pts, last = [], None
    for t in ts:
        v = price(t) or last
        pts.append(v)
        last = v
    first = next((v for v in pts if v), None)
    if not first:
        return []
    pts = [v or first for v in pts]
    side = next((sg for sg in an["shown"] if sg["fam"] == "side"), None)
    falling = an.get("color") not in ("rosso", "rosso_forte") if side else pts[-1] <= pts[0]
    series = [(t, v) for t, v in ((t, price(t)) for t in [t0] + h.change_times({"main"}, t0, t1, {"1x2"})) if v]
    ext, ext_t = None, None
    for t, v in series:
        if ext is None or (v < ext if falling else v > ext):
            ext, ext_t = v, t
    if ext and t0 < ext_t < t1 and (ext < min(pts) - 0.005 if falling else ext > max(pts) + 0.005):
        j = min(range(1, CHART_POINTS), key=lambda i: abs((ts[i] - ext_t).total_seconds()))
        pts[j] = ext                        # il punto estremo cade tra due barre: lo si fa vedere
    step = _step_text((t1 - t0).total_seconds() / 60.0 / CHART_POINTS)
    fav = " (favorita)" if team == an.get("fav") else ""
    out = [f"📊 <b>Quota {esc(names[team])}</b>{fav} {fmt_num(pts[0])} → {fmt_num(pts[-1])} "
           f"<i>({when_text(t0)} → {when_text(t1)}, una barra ogni {step})</i>", spark(pts)]
    parts, verb = [], ""
    q0, qend = 1.0 / pts[0], 1.0 / pts[-1]
    qx = 1.0 / ext if ext else qend
    total = abs(qx - q0)
    lo_p, hi_p = min(v for _, v in series), max(v for _, v in series)
    if total < 0.015 and abs(qend - q0) < 0.015:
        parts.append("quota quasi ferma")
    elif abs(qend - q0) < 0.015:
        parts.append(f"su e giù tra {fmt_num(lo_p)} e {fmt_num(hi_p)}, adesso {fmt_num(pts[-1])} come all'apertura")
    else:
        sgn = 1 if qx > q0 else -1          # probabilita' su = quota giu'
        verb = "giù" if sgn > 0 else "su"
        stimes = [t for t, _ in series]

        def val_at(t):
            return series[max(bisect.bisect_right(stimes, t) - 1, 0)][1]
        best = None                         # il pezzo piu' grosso in 2 ore: (quanto, inizio, fine, da, a)
        for t, v in series:
            v0 = val_at(t - timedelta(hours=2))
            mv = (1.0 / v - 1.0 / v0) * sgn
            if mv > 0 and (best is None or mv > best[0]):
                t_in = next((tt for tt, vv in series if t - timedelta(hours=2) < tt <= t and vv != v0), t)
                best = (mv, t_in, t, v0, v)
        if best:
            _, b0, b1, v0, v1 = best
            piece = (f"{when_text(b0)}" + ("" if b1 - b0 < timedelta(minutes=20) else f"-{b1.astimezone(ROME):%H:%M}")
                     + f" ({fmt_num(v0)} → {fmt_num(v1)})")
            share = best[0] / total
            t20 = next((t for t, v in series if (1.0 / v - q0) * sgn >= 0.2 * total), None)
            t80 = next((t for t, v in series if (1.0 / v - q0) * sgn >= 0.8 * total), None)
            if share >= 0.75 or (t20 and t80 and t80 - t20 <= timedelta(hours=3)):
                parts.append(f"{verb} di colpo {piece}")
            elif share >= 0.4 or not t20 or not t80:
                parts.append(f"{verb} soprattutto {piece}")
            else:
                parts.append(f"{verb} piano piano da {when_text(t20)} a {when_text(t80)}, il pezzo più grosso {piece}")
            if not side and abs(qx - qend) >= 0.2 * total:
                parts.append(f"poi torna a {fmt_num(pts[-1])}")
    if ko:
        t60 = ko - timedelta(minutes=FORMAZIONI_MINUTES)
        p60 = price(t60) if t0 < t60 < t1 else None
        if p60:
            dq = qend - 1.0 / p60
            if abs(dq) < 0.01:
                parts.append("dopo le formazioni ferma")
            else:
                v2 = "giù" if dq > 0 else "su"
                how = "" if not verb else ("ancora " if v2 == verb else "torna ")
                parts.append(f"dopo le formazioni {how}{v2} ({fmt_num(p60)} → {fmt_num(pts[-1])})")
    if side and side.get("ratio", 1.0) < TENUTA_OK and ext and \
            (ext <= min(pts[0], pts[-1]) - 0.01 if falling else ext >= max(pts[0], pts[-1]) + 0.01):
        how = "un po' indietro (forza −1)" if side["ratio"] >= TENUTA_MEZZA else "indietro per più di metà (forza −2)"
        parts.append(f"↩️ era arrivata a {fmt_num(ext)} ({when_text(ext_t)}), poi è tornata {how}")
    if parts:
        out.append("⏱ " + " · ".join(parts))
    return out


def moved_lines(an: dict, names: dict, main: dict | None) -> list:
    """SI MUOVONO ANCHE (senza grafico): gli altri segnali da FORZA_MIN_AVVISO in su (linea gol, GG) e i movimenti
    forti di corner, gol e tiri in porta delle squadre."""
    out, a, b = [], an["a"], an["b"]
    for sg in an["shown"]:
        if sg is main:
            continue
        if sg["fam"] == "gol":
            over = sg["dir"] > 0
            txt = f"{'📈' if over else '📉'} Gol verso l'{'Over' if over else 'Under'} · forza {sg['forza']}/10"
            if a.get("ou") and b.get("ou") and abs(a["ou"][0] - b["ou"][0]) > 1e-9:
                txt += f" · linea {fmt_goal(a['ou'][0])} → {fmt_goal(b['ou'][0])}"
            oa, ob = (a.get("lines") or {}).get("2.5"), (b.get("lines") or {}).get("2.5")
            if oa and ob:
                txt += f" · Over 2,5 {fmt_num(oa[0])} → {fmt_num(ob[0])}"
            out.append(txt)
        elif sg["fam"] == "gg":
            yes, k = sg["dir"] > 0, (0 if sg["dir"] > 0 else 1)
            txt = f"⚽ {'GG' if yes else 'NG'} più probabile · forza {sg['forza']}/10"
            if a.get("gg") and b.get("gg"):
                txt += f" · {'GG' if yes else 'NG'} {fmt_num(a['gg'][k])} → {fmt_num(b['gg'][k])}"
            out.append(txt)
        else:
            out.append(signal_head(an, sg, names))
    icons = {"tc": "🚩 Corner", "tg": "⚽ Gol", "ts": "👟 Tiri in porta"}
    for g in EXP_ORDER:
        row, bits = an["events"].get(g) or {}, []
        exp = row.get("exp") or {}
        for side in ("home", "away"):
            item = row.get(side)
            if item and item[3]:
                a0, b0, d, _ = item
                if side in exp:
                    val = f"{fmt_num(exp[side][0], EXP_DEC[g])} → {fmt_num(exp[side][1], EXP_DEC[g])}"
                else:
                    val = f"{fmt_goal(a0[0])} → {fmt_goal(b0[0])}" if a0 and abs(a0[0] - b0[0]) > 1e-9 else fmt_goal(b0[0])
                bits.append(f"{esc(names[side])} {val} {('▲' if d > 0 else '▼') * 2}")
        if bits:
            out.append(f"{icons[g]}{' attesi' if exp else ''}: " + " · ".join(bits))
    return out


def build_message(m: dict, names: dict, an: dict, base_at: datetime, first: bool, note: str = "formazioni uscite",
                  prefix: str = "") -> str:
    """Avviso a ridosso (una partita): il segnale principale con forza e book d'accordo, la TABELLA UNICA (quote della
    partita, corner e gol delle squadre), il GRAFICO della direzione della partita con gli orari, gli altri movimenti
    buoni, la 💡 lettura, il colore per la riga Mercato e il pronostico con la quota giusta."""
    lg = COMPS_Q.get(m["code"], {"flag": ""})
    main = next((sg for sg in an["shown"] if sg["fam"] == "side"), None) or \
        (max(an["shown"], key=lambda sg: sg["forza"]) if an["shown"] else None)
    top = [f"{prefix}{lg['flag']} <b>{match_title(names)}</b> · {m['ko'].astimezone(ROME):%H:%M}"]
    if main:
        top.append(signal_head(an, main, names))
    table, tnote = fmt_table_one(names, an)
    chart = chart_block(an, names, m["ko"]) or [quando_text(an, names)]
    others = moved_lines(an, names, main)
    end = [lettura(an, names)]
    if an["color"]:
        end.append(f"Mercato: <b>{COLOR_TXT[an['color']]}</b> a {esc(names[an['team']])}")
    end.append(picks_text(an, names))
    end.append(f"<i>{BOOK_LABEL.get(an['ref'], '')} · {base_label(base_at, first)} → adesso ({when_text(an['at'])})"
               f"{', ' + note if note else ''}</i>")
    blocks = [top, [table] + ([f"<i>{esc(tnote)}</i>"] if tnote else []), chart,
              (["<b>Si muovono anche</b>"] + others) if others else [], end]
    return "\n\n".join("\n".join(r for r in bl if r) for bl in blocks if any(bl))


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
    ts = [t0 + (t1 - t0) * (i / SPARK_POINTS) for i in range(SPARK_POINTS + 1)]
    pts, last = [], None
    for t in ts:
        v = price(t) or last
        pts.append(v)
        last = v
    first = next((v for v in pts if v), None)
    if not first:
        return []
    pts = [v or first for v in pts]
    best, best_t = None, None              # punto estremo (piu' bassa se il segnale fa scendere la quota)
    for t in [t0] + h.change_times({"main"}, t0, t1, sp["mtypes"]):
        v = price(t)
        if v and (best is None or (v < best if sp["falling"] else v > best)):
            best, best_t = v, t
    if best and t0 < best_t < t1 and (best < min(pts) - 0.005 if sp["falling"] else best > max(pts) + 0.005):
        j = min(range(1, SPARK_POINTS), key=lambda i: abs((ts[i] - best_t).total_seconds()))
        pts[j] = best                       # il punto estremo cade tra due barre: lo si fa vedere
    out = [f"📊 Andamento quota {sp['label']}: {fmt_num(pts[0])} {spark(pts)} {fmt_num(pts[-1])}"]
    if s.get("ratio", 1.0) < TENUTA_OK:
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
          + (f"• ore {RIEPILOGO_HOUR}: <b>riepilogo</b> delle partite di domani, un messaggio per campionato o coppa\n"
             if RIEPILOGO_AUTO else "") +
          f"• {RIDOSSO_MINUTES} minuti prima della partita (formazioni uscite): solo se un movimento ha "
          f"<b>forza {FORZA_MIN_AVVISO}/10 o più</b>. Per {CUPS_Q['EL']['flag']} Europa e {CUPS_Q['ECL']['flag']} "
          f"Conference League, nelle sere con più di {CUP_BUSY_MATCHES} partite, solo <b>da {FORZA_MIN_BUSY}/10</b>. "
          "Gli avvisi della stessa ora arrivano dal più forte\n"
          f"• circa 10 minuti prima, <b>solo per i casi forti</b>: 🚨 un movimento da {FORZA_FORTE}/10 in su nato "
          f"nell'ultima mezz'ora (dopo il controllo dei {RIDOSSO_MINUTES} minuti) · ⚠️ ribaltone, cioè un segnale "
          "forte che ti avevo mandato e adesso non c'è più\n"
          "• ⚠️ «Non controllate»: se non riesco a leggere le quote di una partita te lo scrivo. Se non scrivo "
          "niente, non c'era nessun segnale\n"
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
          f"<b>Avviso {RIDOSSO_MINUTES} minuti prima</b>\n"
          "In alto il segnale principale, con la forza e quanti book sono d'accordo (⚠️ senza Pinnacle = Pinnacle "
          "non si è mosso)\n"
          "<b>Tabella</b> (Pinnacle, apertura e adesso): 1X2 · AH = handicap asiatico della squadra di casa "
          "(▼ = casa più favorita) · Linea gol (▲ = più gol attesi) · Over 2,5 · GG; sotto, <b>gol attesi</b> e "
          "<b>corner attesi</b> di ogni squadra: quanti se ne aspetta il mercato, ricavati dalle quote (▲ = di più; "
          "* = da un altro book). Sono i numeri da confrontare con il foglio\n"
          "▼ quota scesa = più probabile · ▲ salita · doppia freccia = movimento forte\n"
          "📊 <b>Grafico</b>: la quota della favorita (o della squadra su cui si muove il mercato) dall'apertura ad "
          "adesso, una barra ogni tratto di tempo uguale; barra alta = quota alta (▇▆▄▂▁ = scesa piano piano, "
          "▇▇▇▇▁ = scesa tutta alla fine)\n"
          "⏱ quando si è mossa (di colpo o piano piano) e cosa è successo dopo le formazioni · ↩️ se è tornata "
          "indietro di almeno un quinto: fin dove era arrivata e quando (un po' indietro: forza −1 · più di metà: "
          "forza −2)\n"
          "<b>Si muovono anche</b>: gli altri movimenti buoni (linea gol, GG, gol e corner attesi delle squadre), "
          "senza grafico\n"
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


def due_last(st: dict, cal: list, now: datetime):
    """Gruppo di partite da ricontrollare negli ULTIMI MINUTI (da LAST_FROM_MINUTES a LAST_TO_MINUTES prima)."""
    for g in kickoff_groups(cal):
        key = f"L|{g['first'].isoformat()[:16]}"
        if g["first"] - timedelta(minutes=LAST_FROM_MINUTES) <= now <= g["first"] - timedelta(minutes=LAST_TO_MINUTES) \
                and key not in st["done"]:
            return key, g
    return None, None


def due_missed(st: dict, cal: list, now: datetime):
    """Gruppo con la finestra dei 40 minuti chiusa e qualche partita mai controllata (storico non letto, giro
    saltato): va detto, perche' il silenzio non sembri «nessun segnale»."""
    for g in kickoff_groups(cal):
        latest = g["first"] - timedelta(minutes=RIDOSSO_LATEST_MINUTES)
        key = f"R|{g['first'].isoformat()[:16]}"
        if latest < now <= g["first"] + timedelta(minutes=MISSED_MAX_MINUTES) and key not in st["done"] \
                and any(match_key(m) not in st["done"] for m in g["matches"]):
            return key, g
    return None, None


def due_cups(st: dict, now: datetime) -> str | None:
    """Rilettura dell'elenco delle coppe alle CUP_REREAD_HOUR, nei giorni con partite di coppa nelle prossime
    CUP_REREAD_AHEAD_HOURS ore (non il giorno dell'apertura, che lo legge gia' alle 15): prende le partite che
    Pinnacle ha pubblicato dopo il lunedi' e gli orari cambiati."""
    loc = now.astimezone(ROME)
    if loc.weekday() == CUP_APERTURA_DAY or not (CUP_REREAD_HOUR <= loc.hour < CUP_REREAD_HOUR + APERTURA_WINDOW_HOURS):
        return None
    key = f"C|{loc:%Y-%m-%d}T{CUP_REREAD_HOUR:02d}"
    if key in st["done"]:
        return None
    for rec in st["fixtures"].values():
        t = parse_time(rec.get("start")) if rec.get("code") in CUPS_Q else None
        if t and now < t <= now + timedelta(hours=CUP_REREAD_AHEAD_HOURS):
            return key
    return None


# =====================================================================
# Azioni
# =====================================================================
def apertura_text(st: dict, soon: list, when: datetime, n: int, kind: str) -> str:
    """Messaggio d'apertura: kind 'coppe' (lunedi'), 'quote' (martedi' e venerdi') o 'mano' (elenco a mano)."""
    per = {}
    for m in soon:
        per[m["code"]] = per.get(m["code"], 0) + 1
    detail = " · ".join(f"{COMPS_Q[c]['flag']} {per[c]}" for c in COMPS_Q if c in per)
    last = max(m["ko"] for m in soon)
    if kind == "mano":
        head = (f"📸 <b>Elenco partite aggiornato a mano</b> ({when_text(when)}): {len(soon)} partite nei prossimi "
                f"4 giorni")
    else:
        head = (f"📸 <b>Apertura {'delle coppe' if kind == 'coppe' else 'delle quote'}</b> ({when_text(when)}): "
                f"riferimento fissato per {len(soon)} partite fino a {when_text(last).split()[0]}")
    cups, left = "", cup_matches(st, when, last)[1]
    if left:
        cups = (f"Coppe: solo le partite con almeno una squadra dei 5 campionati"
                f"{'' if CUPS_ONLY_TOP5 else ' (preliminari)'}, {left} lasciate fuori · ")
    busy = sorted({m["ko"].astimezone(ROME).date() for m in soon if alert_floor(m, soon) == FORZA_MIN_BUSY})
    strict = (f" ({CUPS_Q['EL']['flag']} Europa e {CUPS_Q['ECL']['flag']} Conference da {FORZA_MIN_BUSY}/10"
              + (" " + " e ".join(day_text(datetime(d.year, d.month, d.day, 12, tzinfo=ROME)) for d in busy)
                 if len(busy) <= 2 else "") + ")") if busy else ""
    riep = f"Riepilogo alle {RIEPILOGO_HOUR} del giorno prima · " if RIEPILOGO_AUTO else ""
    return (f"{head} · {detail}\n"
            f"<i>{cups}{riep}Avvisi {RIDOSSO_MINUTES} minuti prima da forza {FORZA_MIN_AVVISO}/10{strict}, poi a 10 "
            f"minuti solo i casi forti · elenco OddsPapi {n} partite · chiamate usate {st['calls']}/"
            f"{st.get('limit', MONTH_LIMIT)}</i>")


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
    topic.send(apertura_text(st, soon, now, n, "coppe" if cups_day else "quote" if key else "mano"))
    return cal


def match_key(m: dict) -> str:
    """Chiave di una partita (per non rifarla). Per le coppe con l'id OddsPapi: i nomi possono cambiare quando il bot
    impara quelli italiani dalle partite di campionato."""
    if m["code"] in CUPS_Q and m.get("fid"):
        return f"M|{m['ko'].isoformat()[:16]}|{m['code']}|{m['fid']}"
    return f"M|{m['ko'].isoformat()[:16]}|{m['code']}|{m['home']}"


def stats_entry(m: dict, an: dict, src: str, alert: bool | None = None, floor: int = FORZA_MIN_AVVISO) -> dict:
    """Numeri di una partita controllata (per tarare le soglie): forza e pezzi della forza di ogni segnale, se
    l'avviso e' partito e con quale soglia."""
    return {"k": match_key(m), "src": src, "lg": m["code"], "m": f"{m['home_short']}-{m['away_short']}",
            "f": an["forza"], "sent": bool(an["shown"]) if alert is None else alert, "min": floor,
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


def alert_floor(m: dict, cal: list) -> int:
    """Forza minima perche' parta l'avviso di una partita: FORZA_MIN_AVVISO; FORZA_MIN_BUSY per Europa e Conference
    League nei giorni in cui insieme hanno piu' di CUP_BUSY_MATCHES partite (troppi avvisi alla stessa ora)."""
    if m["code"] in CUP_BUSY_CODES:
        day = m["ko"].astimezone(ROME).date()
        if sum(1 for x in cal if x["code"] in CUP_BUSY_CODES and x["ko"].astimezone(ROME).date() == day) > CUP_BUSY_MATCHES:
            return FORZA_MIN_BUSY
    return FORZA_MIN_AVVISO


# ---------------------------------------------------------------------
# File per il Pace Index: state/mercato.csv (una riga per partita controllata)
# ---------------------------------------------------------------------
PACE_COLUMNS = ("competizione", "data", "ora", "casa", "ospite", "casa_breve", "ospite_breve", "aggiornato", "quando",
                "forza", "avviso", "mercato", "mercato_lato", "segno", "segno_forza", "gol", "gol_forza", "gg",
                "gg_forza", "q1_ap", "qx_ap", "q2_ap", "q1", "qx", "q2", "ah_ap", "ah", "linea_gol_ap", "linea_gol",
                "gol_att_casa_ap", "gol_att_casa", "gol_att_ospite_ap", "gol_att_ospite", "corner_att_casa_ap",
                "corner_att_casa", "corner_att_ospite_ap", "corner_att_ospite", "book", "base")


PACE_RIDOSSO = f"{RIDOSSO_MINUTES} minuti"       # colonna «quando»: controllo dei 40 minuti...
PACE_LAST = "10 minuti"                         # ...o aggiornata negli ultimi minuti (movimento forte o ribaltone)


def _num(v, dec: int = 2) -> str:
    return "" if v is None else f"{v:.{dec}f}"


def pace_row(m: dict, names: dict, an: dict, R: dict, alert: bool, quando: str) -> dict:
    """Riga del file per il Pace Index: giudizio (il colore per la riga Mercato solo se l'avviso e' partito), forza,
    verso dei tre segnali, quote di apertura e di adesso, gol e corner attesi. Numeri con il punto."""
    a, b = an["a"], an["b"]
    loc = m["ko"].astimezone(ROME)
    row = {"competizione": m["code"], "data": f"{loc:%Y-%m-%d}", "ora": f"{loc:%H:%M}", "casa": m["home"],
           "ospite": m["away"], "casa_breve": names["home"], "ospite_breve": names["away"],
           "aggiornato": f"{now_utc().astimezone(ROME):%Y-%m-%d %H:%M}", "quando": quando, "forza": str(an["forza"]),
           "avviso": "SI" if alert else "NO",
           "mercato": COLOR_TXT[an["color"]] if alert and an["color"] else "",
           "mercato_lato": ("casa" if an["team"] == "home" else "ospite") if alert and an["color"] else "",
           "book": BOOK_LABEL.get(an["ref"], an["ref"] or ""), "base": "prima quota" if R.get("first") else "apertura",
           "_ko": m["ko"].isoformat(), "_at": now_utc().isoformat(timespec="seconds"),
           "_heads": {sg["fam"]: signal_head(an, sg, names) for sg in an["shown"]} if alert else {}}
    for fam, col, pos, neg in (("side", "segno", "casa", "ospite"), ("gol", "gol", "Over", "Under"),
                               ("gg", "gg", "GG", "NG")):
        sg = next((x for x in an["sigs"] if x["fam"] == fam), None)
        row[col] = (pos if sg["dir"] > 0 else neg) if sg else ""
        row[f"{col}_forza"] = str(sg["forza"]) if sg else ""
    for i, lab in enumerate(("q1", "qx", "q2")):
        row[f"{lab}_ap"] = _num(a["x"][i]) if a.get("x") else ""
        row[lab] = _num(b["x"][i]) if b.get("x") else ""
    row["ah_ap"], row["ah"] = _num((a.get("ah") or [None])[0]), _num((b.get("ah") or [None])[0])
    row["linea_gol_ap"], row["linea_gol"] = _num((a.get("ou") or [None])[0]), _num((b.get("ou") or [None])[0])
    for g, lab in (("tg", "gol_att"), ("tc", "corner_att")):
        exp = (an["events"].get(g) or {}).get("exp") or {}
        for side, sl in (("home", "casa"), ("away", "ospite")):
            ea, eb = exp.get(side) or (None, None)
            row[f"{lab}_{sl}_ap"], row[f"{lab}_{sl}"] = _num(ea), _num(eb)
    return row


def pace_save(st: dict, m: dict, names: dict, an: dict, R: dict, alert: bool, quando: str) -> None:
    pace = st["pace"] if isinstance(st.get("pace"), dict) else {}
    pace[match_key(m)] = pace_row(m, names, an, R, alert, quando)
    st["pace"] = pace


def write_pace(st: dict) -> None:
    """Scrive state/mercato.csv (separatore ';', numeri con il punto, UTF-8) dalle righe tenute nello stato: il
    file che i Pace Index leggono con Power Query. Lo riscrive solo se cambia."""
    rows = sorted((st.get("pace") or {}).values(), key=lambda r: (r.get("_ko", ""), r.get("competizione", ""),
                                                                 r.get("casa", "")))
    lines = [";".join(PACE_COLUMNS)]
    for r in rows:
        lines.append(";".join(str(r.get(c, "")).replace(";", ",").replace("\n", " ") for c in PACE_COLUMNS))
    text = "\n".join(lines) + "\n"
    try:
        with open(PACE_FILE, encoding="utf-8") as f:
            if f.read() == text:
                return
    except OSError:
        pass
    try:
        os.makedirs(os.path.dirname(PACE_FILE), exist_ok=True)
        with open(PACE_FILE, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    except OSError as e:
        print(f"[WARN] file per il Pace Index non scritto: {e}")


def do_ridosso(st: dict, topic: QuoteTopic, key: str | None, group: dict | None, cal: list, force: bool = False) -> int:
    """Per ogni partita del gruppo: storico (gratis) -> apertura e adesso sui 3 book -> forza dei segnali ->
    avviso se la forza arriva alla soglia della partita (alert_floor). Prima si leggono tutte, poi gli avvisi
    partono DAL PIU' FORTE. Ogni partita viene segnata e salvata appena e' a posto (letta e, se serve, avvisata):
    se il giro si interrompe (o finisce il tempo), il giro dopo riprende dalle mancanti, senza doppioni."""
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
    alerts, notfound = [], []

    def mark(m):
        if not manual:
            st["done"].append(match_key(m))
            save_qstate(st)
    for m in todo:
        if not manual and time.monotonic() - _START > RUN_BUDGET_SECONDS:
            print("Tempo del giro finito: le partite rimaste al prossimo giro (tra 5 minuti)")
            unfinished = True
            break
        names = team_names(m)
        fid = find_fixture(st, m)
        if not fid:
            print(f"  {names['home']} - {names['away']}: non trovata su OddsPapi")
            notfound.append(names)
            mark(m)
            continue
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
        floor = alert_floor(m, cal)
        alert = an["forza"] >= floor
        if alert:
            an = add_sot(st, fid, m, R, an, force=force)
        save_stats(st, stats_entry(m, an, "a mano" if manual else "ridosso", alert, floor))
        pace_save(st, m, names, an, R, alert, "a mano" if manual else PACE_RIDOSSO)
        sig_txt = ", ".join(f"{s['fam']} {s['forza']}" for s in an["sigs"]) or "nessun movimento"
        if alert:
            alerts.append((m, names, an, R, sig_txt))
        else:
            need = f", qui serve {floor}" if floor != FORZA_MIN_AVVISO else ""
            print(f"  {names['home']} - {names['away']}: sotto la soglia ({sig_txt}{need})")
            mark(m)
    for m, names, an, R, sig_txt in sorted(alerts, key=lambda r: -r[2]["forza"]):       # dal piu' forte
        if topic.send(build_message(m, names, an, R["base_at"], R["first"],
                                    "controllo a mano" if manual else "formazioni uscite")):
            sent += 1
            print(f"  {names['home']} - {names['away']}: SEGNALE ({sig_txt}) -> inviato")
            mark(m)
            time.sleep(SEND_DELAY_GROUP_SECONDS)
        else:
            print(f"  {names['home']} - {names['away']}: SEGNALE, ma Telegram non ha accettato: riprovo")
            unfinished = True
    if notfound and not manual:
        topic.send(missed_text(group["first"], notfound, "non sono nell'elenco di OddsPapi"))
    if key and not unfinished:
        st["done"].append(key)
    if manual and sent == 0:
        topic.send(f"🔎 Controllo a mano delle partite di {when_text(group['first'])}: nessun movimento da "
                   f"{FORZA_MIN_AVVISO}/10 in su dall'apertura ({checked} partite lette su {len(todo)}).")
    st["log"].append(f"{now_utc().isoformat(timespec='minutes')} {'a mano' if manual else 'ridosso'} "
                     f"{len(todo)} partite, {checked} lette, {sent} messaggi{' (da finire)' if unfinished else ''}")
    return sent


def missed_text(first: datetime, names_list: list, why: str) -> str:
    return (f"⚠️ <b>Non controllate</b> · partite delle {first.astimezone(ROME):%H:%M}: "
            + ", ".join(match_title(n) for n in names_list)
            + f" ({why}). Per queste il silenzio non vuol dire «nessun segnale».")


def do_missed(st: dict, topic: QuoteTopic, key: str, group: dict) -> None:
    """Finestra dei 40 minuti chiusa con partite mai controllate: una riga per dirlo, poi il gruppo e' chiuso."""
    left = [m for m in group["matches"] if match_key(m) not in st["done"]]
    print("Bot quote: partite non controllate in tempo: " + ", ".join(f"{m['home_short']}-{m['away_short']}" for m in left))
    quiet = f"limit:{st['month']}" in st["notices"]        # chiamate del mese finite: gia' detto, non a ogni partita
    if left and not quiet and not topic.send(missed_text(group["first"], [team_names(m) for m in left],
                                                         "quote non lette in tempo")):
        return                              # Telegram non ha accettato: si riprova al giro dopo
    st["done"] += [match_key(m) for m in left] + [key]
    st["log"].append(f"{now_utc().isoformat(timespec='minutes')} non controllate: {len(left)} partite")


def do_cups(st: dict, key: str, cal: list) -> list:
    """Rilegge l'elenco delle coppe (1 chiamata, senza messaggi): partite pubblicate dopo il lunedi', orari cambiati.
    Se non arriva si riprova al giro dopo, al massimo APERTURA_TRIES volte. Ritorna il calendario aggiornato."""
    before = {fid for fid, rec in st["fixtures"].items() if rec.get("code") in CUPS_Q}
    try:
        refresh_fixtures(st, which="coppe")
    except QuotaExhausted:
        raise
    except Exception as e:      # noqa: BLE001
        tries = st["ap_tries"] = {key: (st.get("ap_tries") or {}).get(key, 0) + 1}
        print(f"[WARN] elenco coppe non riletto ({e}): tentativo {tries[key]} di {APERTURA_TRIES}")
        if tries[key] >= APERTURA_TRIES:
            st["done"].append(key)
        return cal
    st.pop("ap_tries", None)
    st["done"].append(key)
    learn_teams(st)
    new = sum(1 for fid, rec in st["fixtures"].items() if rec.get("code") in CUPS_Q and fid not in before)
    st["log"].append(f"{now_utc().isoformat(timespec='minutes')} coppe rilette: {new} partite nuove")
    return calendar_matches(st)


# ---------------------------------------------------------------------
# Ultimi minuti: solo segnali forti
# ---------------------------------------------------------------------
def rebase(R: dict, t: datetime) -> dict:
    """Lo stesso storico con le quote del momento t come riferimento (per misurare solo l'ultimo tratto)."""
    base = {s: h.snapshot(t) for s, h in R["bh"].items()}
    base = {s: v for s, v in base.items() if has_data(v)}
    return dict(R, base=base, base_at=t, first=False)


def at_time(R: dict, t: datetime) -> dict:
    """Lo stesso storico visto al momento t (per le prove: gli ultimi minuti di una partita gia' giocata)."""
    now = {s: h.snapshot(t) for s, h in R["bh"].items()}
    return dict(R, now={s: v for s, v in now.items() if has_data(v)}, at=t)


def last_review(m: dict, names: dict, an: dict, R: dict, alert: bool):
    """Per le prove sulle partite gia' giocate: cosa avrebbero visto gli ULTIMI MINUTI, cioe' le quote di
    LAST_REVIEW_MINUTES prima del fischio contro quelle del controllo dei 40 minuti (lo storico e' lo stesso: nessuna
    lettura in piu'). Ritorna (analisi dall'apertura, analisi dell'ultimo tratto, storico dell'ultimo tratto, riga
    dei 40 minuti, ribaltone) o None."""
    t40 = m["ko"] - timedelta(minutes=RIDOSSO_MINUTES)
    Rl = at_time(R, m["ko"] - timedelta(minutes=LAST_REVIEW_MINUTES))
    R2 = rebase(Rl, t40)
    if not (Rl["now"] and R2["base"]):
        return None
    anl, an2 = analyze(Rl, m["ko"]), analyze(R2, m["ko"])
    prev = dict(pace_row(m, names, an, R, alert, PACE_RIDOSSO), _at=t40.isoformat())
    return anl, an2, R2, prev, flipped(prev, anl)


def flipped(prev: dict | None, an: dict):
    """RIBALTONE: l'avviso di 40 minuti prima aveva un segnale forte (da FORZA_FORTE) che adesso, dall'apertura, non
    arriva piu' a FORZA_MIN_AVVISO (rientrato, o nel verso opposto). Ritorna (famiglia, verso, forza di prima,
    forza di adesso) o None."""
    if not prev or prev.get("avviso") != "SI" or prev.get("quando") != PACE_RIDOSSO:
        return None
    best = None
    for fam, col, pos in (("side", "segno", "casa"), ("gol", "gol", "Over"), ("gg", "gg", "GG")):
        f0 = int(prev.get(f"{col}_forza") or 0)
        if prev.get(col) and f0 >= FORZA_FORTE and (best is None or f0 > best[2]):
            best = (fam, 1 if prev[col] == pos else -1, f0)
    if not best:
        return None
    fam, d, f0 = best
    cur = next((sg for sg in an["sigs"] if sg["fam"] == fam), None)
    f1 = cur["forza"] if cur and cur["dir"] == d else 0
    return (fam, d, f0, f1) if f1 < FORZA_MIN_AVVISO else None


def _trail(fam: str, d: int, names: dict, snaps: list) -> str:
    """La quota che racconta un segnale in tre momenti: [(etichetta, quote del book), ...]."""
    bits = []
    for lab, sn in snaps:
        sn = sn or {}
        if fam == "side":
            v = fmt_num(sn["x"][0 if d > 0 else 2]) if sn.get("x") else None
        elif fam == "gol":
            v = fmt_goal(sn["ou"][0]) if sn.get("ou") else None
        else:
            v = fmt_num(sn["gg"][0 if d > 0 else 1]) if sn.get("gg") else None
        if v:
            bits.append(f"{lab} {v}")
    what = (f"Quota {esc(names['home' if d > 0 else 'away'])}" if fam == "side" else "Linea gol" if fam == "gol"
            else ("Quota GG" if d > 0 else "Quota NG"))
    return f"{what}: " + " · ".join(bits) if bits else ""


def last_base(prev: dict | None, ko: datetime, now: datetime) -> datetime:
    """Da quando si misura l'ultimo tratto: dal controllo dei 40 minuti di quella partita (se c'e' stato), se no da
    RIDOSSO_MINUTES prima del fischio."""
    t = parse_time(prev.get("_at")) if prev and prev.get("quando") == PACE_RIDOSSO else None
    if t and ko - timedelta(minutes=RIDOSSO_MINUTES + MERGE_MINUTES + 5) <= t < now:
        return t
    return ko - timedelta(minutes=RIDOSSO_MINUTES)


def last_message(m: dict, names: dict, an: dict, an2: dict | None, R2: dict, prev: dict | None, late: bool, flip,
                 prefix: str = "") -> str:
    """Messaggio degli ULTIMI MINUTI: ⚠️ RIBALTONE (un segnale forte gia' mandato non c'e' piu') o 🚨 un movimento
    forte nato dopo il controllo dei 40 minuti; tabellina «ora del controllo / adesso», poi come sta dall'apertura e
    il colore per la riga Mercato."""
    lg = COMPS_Q.get(m["code"], {"flag": ""})
    ref = an["ref"]
    t0 = R2["base_at"]
    hhmm = f"{t0.astimezone(ROME):%H:%M}"
    mins = max(1, round((an["at"] - t0).total_seconds() / 60))
    a0, mid, b = an["a"], (R2["base"].get(ref) or {}), an["b"]
    title = "⚠️ <b>RIBALTONE</b>" if flip else "🚨 <b>ULTIMI MINUTI</b>"
    top = [f"{prefix}{title} · {lg['flag']} <b>{match_title(names)}</b> · {m['ko'].astimezone(ROME):%H:%M}"]
    if flip:
        fam, d, f0, f1 = flip
        was = ((prev or {}).get("_heads") or {}).get(fam) or f"forza {f0}/10"
        top.append(f"Il segnale forte delle {hhmm} non c'è più: era {was}. Adesso "
                   + (f"forza {f1}/10" if f1 else "è rientrato") + ".")
        top.append(_trail(fam, d, names, [("apertura", a0), (hhmm, mid), ("adesso", b)]))
    if late and an2 and an2["shown"]:
        main2 = (next((sg for sg in an2["shown"] if sg["fam"] == "side"), None)
                 or max(an2["shown"], key=lambda sg: sg["forza"]))
        top.append(signal_head(an2, main2, names) + f" <i>(negli ultimi {mins} minuti)</i>")
        top += [signal_head(an2, sg, names) for sg in an2["shown"] if sg is not main2 and sg["forza"] >= FORZA_FORTE]
    rows = _main_rows(names, mid, b)
    table = ""
    if rows:
        w = max(len(r[0]) for r in rows)
        table = _pre([f"{'':<{w}} {hhmm:>6} {'adesso':>6}"] +
                     [f"{r[0]:<{w}} {r[1]:>6} {r[2]:>6} {r[3]}".rstrip() for r in rows])
    end = []
    if an["shown"]:
        end.append("Dall'apertura: " + " · ".join(signal_head(an, sg, names, short=True) for sg in an["shown"]))
    else:
        end.append(f"Dall'apertura: ⚪ nessun segnale (forza {an['forza']}/10)")
    was_color = (prev or {}).get("mercato") if (prev or {}).get("quando") == PACE_RIDOSSO else ""
    if an["color"]:
        now_color = COLOR_TXT[an["color"]]
        end.append(f"Mercato: <b>{now_color}</b> a {esc(names[an['team']])}"
                   + (f" (alle {hhmm} era {was_color})" if was_color and was_color != now_color else ""))
    elif was_color:
        end.append(f"Mercato: <b>nessun colore</b> (alle {hhmm} era {was_color})")
    end.append(f"<i>{BOOK_LABEL.get(ref, '')} · {when_text(t0)} → adesso ({when_text(an['at'])})</i>")
    return "\n\n".join("\n".join(r for r in bl if r) for bl in (top, [table], end) if any(bl))


def do_last(st: dict, topic: QuoteTopic, key: str, group: dict, cal: list) -> int:
    """ULTIMI MINUTI (circa 10 prima del fischio): rilegge le partite del gruppo e scrive SOLO per i casi forti:
    un movimento da FORZA_FORTE in su nato dopo il controllo dei 40 minuti (misurato solo su quel tratto), o un
    segnale forte gia' mandato che non c'e' piu' (ribaltone). Dal piu' forte; niente doppioni; se il tempo finisce
    si riprende al giro dopo, finche' la finestra e' aperta."""
    found, unfinished, checked = [], False, 0
    for m in group["matches"]:
        lk = "L" + match_key(m)
        if lk in st["done"]:
            continue
        if time.monotonic() - _START > RUN_BUDGET_SECONDS:
            print("Ultimi minuti: tempo del giro finito, continuo al prossimo giro")
            unfinished = True
            break
        names = team_names(m)
        fid = find_fixture(st, m)
        if not fid:
            st["done"].append(lk)
            continue
        try:
            R = read_history(st, fid, apertura_time(m["ko"], m["code"]))
            checked += 1
        except QuotaExhausted:
            raise
        except Exception as e:      # noqa: BLE001
            print(f"  {names['home']} - {names['away']}: storico non letto ({e})")
            unfinished = True
            continue
        an = analyze(R, m["ko"])
        prev = (st.get("pace") or {}).get(match_key(m))
        R2 = rebase(R, last_base(prev, m["ko"], now_utc()))
        an2 = analyze(R2, m["ko"]) if R2["base"] else None
        late = bool(an2 and an2["forza"] >= FORZA_FORTE)
        flip = flipped(prev, an)
        print(f"  {names['home']} - {names['away']}: da {when_text(R2['base_at'])} forza {an2['forza'] if an2 else '-'} "
              f"({describe(an2) if an2 else 'niente'}), dall'apertura forza {an['forza']}"
              + (" -> RIBALTONE" if flip else " -> FORTE" if late else ""))
        if an2:
            save_stats(st, dict(stats_entry(m, an2, "ultimi", late or bool(flip), FORZA_FORTE), flip=int(bool(flip))))
        if late or flip:
            found.append((m, names, an, an2, R, R2, prev, late, flip, lk))
        else:
            st["done"].append(lk)
    sent = 0
    for m, names, an, an2, R, R2, prev, late, flip, lk in sorted(found, key=lambda r: -(r[3]["forza"] if r[3] else 0)):
        if topic.send(last_message(m, names, an, an2, R2, prev, late, flip)):
            sent += 1
            st["done"].append(lk)
            pace_save(st, m, names, an, R, an["forza"] >= alert_floor(m, cal), PACE_LAST)
            save_qstate(st)
            time.sleep(SEND_DELAY_GROUP_SECONDS)
        else:
            unfinished = True
    if not unfinished:
        st["done"].append(key)
    st["log"].append(f"{now_utc().isoformat(timespec='minutes')} ultimi minuti {len(group['matches'])} partite, "
                     f"{checked} lette, {sent} messaggi{' (da finire)' if unfinished else ''}")
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
        print(f"     eventi: { {g: event_debug(r) for g, r in an['events'].items()} }")
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
    everything = finished_matches(st)
    matches = filter_matches(everything, query)
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
        floor = alert_floor(m, everything)
        an["alert"] = an["forza"] >= floor
        entry = stats_entry(m, an, "rivedi", an["alert"], floor)
        lr = last_review(m, names, an, R, an["alert"])
        if lr:                              # ultimi minuti: forza dell'ultimo tratto e ribaltone
            an["last"] = (lr[1]["forza"], bool(lr[4]))
            entry["last"] = [lr[1]["forza"], int(bool(lr[4]))]
        save_stats(st, entry)
        results.append((m, names, an, R))
        a, b = an["a"], an["b"]
        print(f"  {names['home']} - {names['away']} ({when_text(m['ko'])}): forza {an['forza']} · {describe(an)}\n"
              f"     {an['ref']}: 1X2 {a.get('x')} -> {b.get('x')} | AH {a.get('ah')} -> {b.get('ah')} | gol "
              f"{a.get('ou')} -> {b.get('ou')} | squadre { {g: r.get('src') for g, r in an['events'].items()} } | "
              f"mercati nello storico (tutti, usati) {_HIST_INFO}")
        if lr:
            print(f"     ultimi minuti (da {RIDOSSO_MINUTES} a {LAST_REVIEW_MINUTES} minuti prima): forza "
                  f"{lr[1]['forza']} · {describe(lr[1])}" + (" · RIBALTONE" if lr[4] else ""))
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
        forti = sum(1 for r in results if r[2]["alert"] and r[2]["forza"] >= FORZA_FORTE)
        medi = sum(1 for r in results if r[2]["alert"] and r[2]["forza"] < FORZA_FORTE)
        chosen = sorted((r for r in results if r[2]["alert"]), key=lambda r: -r[2]["forza"])[:RIVEDI_TOP]
        topic.send(f"🧪 <b>Rivedi{' · ' + esc(query) if query else ''}</b>: {len(results)} partite giocate da "
                   f"{day_text(results[0][0]['ko'])} a "
                   f"{day_text(results[-1][0]['ko'])}, rilette come {RIDOSSO_MINUTES} minuti prima con le regole "
                   f"nuove\nforti ({FORZA_FORTE}-10): <b>{forti}</b> · medie ({FORZA_MIN_AVVISO}-{FORZA_FORTE - 1}): "
                   f"<b>{medi}</b> · sotto la soglia (niente avviso): "
                   f"<b>{len(results) - forti - medi}</b>\n"
                   f"ultimi minuti (tra {RIDOSSO_MINUTES} e {LAST_REVIEW_MINUTES} minuti prima): 🚨 movimenti da "
                   f"{FORZA_FORTE}/10 <b>{sum(1 for r in results if not r[2].get('last', (0, 0))[1] and r[2].get('last', (0, 0))[0] >= FORZA_FORTE)}"
                   f"</b> · ⚠️ ribaltoni <b>{sum(1 for r in results if r[2].get('last', (0, 0))[1])}</b>"
                   + (f"\n<i>Qui sotto le {len(chosen)} più forti, come sarebbero arrivate.</i>" if chosen else ""))
        time.sleep(SEND_DELAY_GROUP_SECONDS)
    for m, names, an, R in chosen:
        if an["alert"]:
            an = add_sot(st, m["fid"], m, R, an, force=True)
            text = build_message(m, names, an, R["base_at"], R["first"], "formazioni uscite", prefix="🧪 RIVEDI · ")
        else:
            lg = COMPS_Q.get(m["code"], {"flag": ""})
            text = "\n".join(r for r in (
                f"🧪 RIVEDI · {lg['flag']} <b>{match_title(names)}</b> · {m['ko'].astimezone(ROME):%H:%M}",
                f"⚪ Sotto la soglia: forza {an['forza']}/10, l'avviso non sarebbe arrivato",
                fmt_table_one(names, an)[0],
                f"<i>{BOOK_LABEL.get(an['ref'], '')} · {base_label(R['base_at'], R['first'])} → "
                f"{when_text(an['at'])}</i>") if r)
        topic.send(text)
        time.sleep(SEND_DELAY_GROUP_SECONDS)
    st["log"].append(f"{now_utc().isoformat(timespec='minutes')} rivedi {query or 'settimana'}: {len(results)} "
                     f"partite lette, {len(chosen)} messaggi")


def do_esempio(st: dict, topic: QuoteTopic, query: str = "") -> None:
    """Prova grafica nel gruppo, con quote vere e nessuna chiamata (solo storico): la legenda e tre avvisi di partite
    gia' giocate, rilette 40 minuti prima: un calo che ha tenuto, uno tornato indietro (↩️) e uno solo sui gol; poi
    un esempio degli ULTIMI MINUTI (il movimento piu' forte tra 40 e 8 minuti prima trovato in quelle partite, o un
    ribaltone), un ribaltone FINTO se non ce n'e' uno vero, e la riga «Non controllate».
    Con query "tutto" anche l'apertura delle coppe, un riepilogo con l'andamento e il riepilogo di una coppa."""
    ensure_markets(st)
    learn_teams(st)
    now, full = now_utc(), norm(query) == "tutto"
    pre = "🧪 <b>ESEMPIO</b> · "

    def send(text):
        topic.send(text)
        time.sleep(SEND_DELAY_GROUP_SECONDS)
    send("🧪 <b>Prova grafica del bot quote</b>: qui sotto " + ("un esempio di ogni messaggio" if full else
         "la legenda, tre avvisi di 40 minuti prima e un esempio degli ultimi minuti") + ", con quote vere di "
         "partite già giocate. Sono solo esempi, non segnali.")
    if not MUTO:
        send_legend(st, topic, force=True)
        time.sleep(SEND_DELAY_GROUP_SECONDS)
    cups = [m for m in calendar_matches(st) if m["code"] in CUPS_Q and m["ko"] > now]
    if full and cups:
        ap = apertura_time(cups[0]["ko"], cups[0]["code"])
        week = [m for m in cups if apertura_time(m["ko"], m["code"]) == ap]
        last = max(m["ko"] for m in week)
        send(pre + apertura_text(st, week, ap, len(week) + cup_matches(st, ap, last)[1], "coppe"))
    played = finished_matches(st)
    played = [m for m in played if m["code"] == "SA"] + [m for m in played if m["code"] != "SA"]
    rows, reads, start = [], [], time.monotonic()
    found, last = {}, None              # last: (ribaltone?, forza dell'ultimo tratto, dati) del caso migliore
    for m in played:
        enough = len(found) == 3 and (not full or len(rows) >= 10)
        if time.monotonic() - start > RIVEDI_BUDGET_SECONDS or \
                (enough and (len(reads) >= ESEMPIO_READS or (last and last[1] >= FORZA_FORTE))):
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
        reads.append((m, names, an, R))
        if m["code"] == "SA" and len(rows) < 10:
            rows.append({"code": m["code"], "ko": m["ko"].isoformat(), "text": riepilogo_row(m, names, an),
                         "base": base_label(R["base_at"], R["first"]) if an["b"] else "", "ref": an["ref"]})
        side = next((sg for sg in an["shown"] if sg["fam"] == "side"), None)
        if side:
            kind = "che ha tenuto" if side["ratio"] >= TENUTA_OK else "tornato indietro"
        else:
            kind = "solo sui gol" if an["shown"] else ""
        if kind and (kind not in found or an["forza"] > found[kind][2]["forza"]):
            found[kind] = (m, names, an, R)
        lr = last_review(m, names, an, R, an["forza"] >= FORZA_MIN_AVVISO)      # 8 minuti prima del fischio
        if lr and (lr[1]["shown"] or lr[4]):
            rank = (bool(lr[4]), lr[1]["forza"])
            if last is None or rank > last[:2]:
                last = (*rank, (m, names) + lr)
    if full and rows:
        days = sorted({m["ko"].astimezone(ROME).date() for m, _, _, _ in reads if m["code"] == "SA"})
        dd = [day_text(datetime(d.year, d.month, d.day, 12, tzinfo=ROME)) for d in days]
        label = ", ".join(dd[:-1]) + " e " + dd[-1] if len(dd) > 1 else dd[0]
        for text in riepilogo_messages(rows, f"{label} (quote di 40 minuti prima)", True):
            send(text)
    if full and cups:
        d0, c0 = cups[0]["ko"].astimezone(ROME).date(), cups[0]["code"]
        do_riepilogo(st, topic, None, [m for m in cups if m["code"] == c0 and m["ko"].astimezone(ROME).date() == d0],
                     force=True, preview=True)
    for kind in ("che ha tenuto", "tornato indietro", "solo sui gol"):
        if kind in found:
            m, names, an, R = found[kind]
            send(build_message(m, names, an, R["base_at"], R["first"], "formazioni uscite",
                               prefix=f"🧪 <b>ESEMPIO di avviso {kind}</b> · "))
    if last:
        m, names, anl, an2, R2, prev, flip = last[2]
        real = bool(flip) or an2["forza"] >= FORZA_FORTE
        note = "" if real else (f" (qui il movimento dell'ultimo tratto è solo {an2['forza']}/10: nella realtà "
                                f"arriva solo da {FORZA_FORTE}/10)")
        send(last_message(m, names, anl, an2, R2, prev, True, flip,
                          prefix=f"🧪 <b>ESEMPIO degli ultimi minuti</b>{note} · "))
    else:
        send("🧪 <b>ESEMPIO degli ultimi minuti</b>: in queste partite tra 40 e 8 minuti prima non si è mosso "
             "niente, quindi non sarebbe arrivato nessun messaggio (è il caso più frequente).")
    if not (last and last[0]):          # nessun ribaltone vero: uno FINTO, per vedere com'e' fatto il messaggio
        strong = next((found[k] for k in ("che ha tenuto", "tornato indietro", "solo sui gol")
                       if k in found and any(sg["forza"] >= FORZA_FORTE for sg in found[k][2]["shown"])), None)
        try:
            if strong:
                m, names, an, R = strong
                t40 = m["ko"] - timedelta(minutes=RIDOSSO_MINUTES)
                Rf = dict(R, now=R["base"], at=m["ko"] - timedelta(minutes=LAST_REVIEW_MINUTES))
                R2 = rebase(Rf, t40)        # finto: «adesso» sono le quote dell'apertura
                anl, an2 = analyze(Rf, m["ko"]), analyze(R2, m["ko"])
                prev = dict(pace_row(m, names, an, R, True, PACE_RIDOSSO), _at=t40.isoformat())
                flip = flipped(prev, anl)
                if flip:
                    send(last_message(m, names, anl, an2, R2, prev, an2["forza"] >= FORZA_FORTE, flip,
                                      prefix="🧪 <b>ESEMPIO FINTO di ribaltone</b> (come sarebbe arrivato se le quote "
                                             "fossero tornate a quelle dell'apertura: non è successo) · "))
        except Exception as e:      # noqa: BLE001
            print(f"  esempio di ribaltone non costruito: {e.__class__.__name__}: {e}")
    if reads:
        m, names = reads[-1][0], reads[-1][1]
        send(pre + missed_text(m["ko"], [names], "quote non lette in tempo"))
    st["log"].append(f"{now_utc().isoformat(timespec='minutes')} esempio{' tutto' if full else ''}: {len(reads)} "
                     f"partite rilette, avvisi {sorted(found)}")


def cleanup(st: dict) -> None:
    limit = now_utc() - timedelta(days=KEEP_DAYS)
    st["fixtures"] = {k: v for k, v in st["fixtures"].items() if (parse_time(v.get("start")) or now_utc()) > limit}
    keep = (now_utc() - timedelta(days=10)).isoformat()[:16]
    st["done"] = [d for d in st["done"] if d.split("|", 1)[-1] >= keep][-800:]
    st["log"] = st["log"][-60:]
    st["stats"] = st.get("stats", [])[-STATS_KEEP:]
    old = (now_utc() - timedelta(days=PACE_KEEP_DAYS)).isoformat()
    st["pace"] = {k: r for k, r in (st.get("pace") or {}).items() if r.get("_ko", "") >= old}


_START = time.monotonic()


def main() -> int:
    global _START, MUTO
    _START = time.monotonic()
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="auto",
                    choices=["auto", "test", "ora", "apertura", "riepilogo", "rivedi", "esempio"])
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
    key = rkey = group = skey = lkey = lgroup = mkey = mgroup = ckey = None
    smatches = []
    if args.mode == "auto":
        rkey, group = due_ridosso(st, cal, now)
        lkey, lgroup = due_last(st, cal, now)
        mkey, mgroup = due_missed(st, cal, now)
        key = due_apertura(st, cal, now)
        ckey = due_cups(st, now)
        skey, smatches = due_riepilogo(st, cal, now) if RIEPILOGO_AUTO else (None, [])
        if not any((key, rkey, skey, lkey, mkey, ckey)):
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
        elif args.mode == "esempio":
            do_esempio(st, topic, query)
        else:
            send_legend(st, topic)
            if lkey:                    # prima gli ultimi minuti (l'orario piu' stretto), poi gli avvisi a ridosso
                print(f"Bot quote: ultimi minuti ({lkey}): "
                      + ", ".join(f"{m['home_short']}-{m['away_short']}" for m in lgroup["matches"]))
                do_last(st, topic, lkey, lgroup, cal)
            if rkey:
                print(f"Bot quote: controllo a ridosso ({rkey}): "
                      + ", ".join(f"{m['home_short']}-{m['away_short']}" for m in group["matches"]))
                do_ridosso(st, topic, rkey, group, cal)
            if mkey:
                do_missed(st, topic, mkey, mgroup)
            if key:
                print(f"Bot quote: apertura ({key})")
                cal = do_apertura(st, topic, key, cal)
            if ckey:
                print(f"Bot quote: rilettura dell'elenco delle coppe ({ckey})")
                cal = do_cups(st, ckey, cal)
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
        write_pace(st)
        return 1
    cleanup(st)
    save_qstate(st)
    write_pace(st)
    return 0


if __name__ == "__main__":
    sys.exit(main())
