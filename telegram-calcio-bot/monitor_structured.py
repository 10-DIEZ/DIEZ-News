"""
Calendario e squadre, da football-data.org.

Salva in state/fixtures.json (file SEPARATO da state.json, che e' del
workflow notizie, cosi' i due workflow non si contendono mai lo stesso file):

- "fixtures": partite dei 5 campionati (e della Champions League) dagli
  ultimi CALENDAR_PAST_DAYS giorni ai prossimi FIXTURE_LOOKAHEAD_DAYS.
  Le partite gia' giocate servono al bot notizie per scartare gli articoli
  su quelle partite arrivati a distanza di giorni.
- "teams": le squadre dei 5 campionati, con l'allenatore (riscaricate al
  massimo una volta ogni TEAMS_REFRESH_HOURS ore).

Da eseguire ~2 volte al giorno (vedi workflow GitHub Actions).
"""

import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

from config import (
    CALENDAR_EXTRA_COMPETITIONS,
    CALENDAR_PAST_DAYS,
    FIXTURE_LOOKAHEAD_DAYS,
    FOOTBALL_DATA_API_KEY,
    FOOTBALL_DATA_HOST,
    LEAGUES,
    TEAMS_REFRESH_HOURS,
)
from utils import load_calendar, save_calendar

# Il piano gratuito di football-data.org ammette 10 richieste al minuto
REQUEST_PAUSE_SECONDS = 6.5

_last_request = [0.0]


def fd_get(path: str, params: dict | None = None):
    """GET su football-data.org con pausa tra le richieste. Restituisce il JSON o None se errore."""
    wait = REQUEST_PAUSE_SECONDS - (time.time() - _last_request[0])
    if wait > 0:
        time.sleep(wait)
    _last_request[0] = time.time()
    url = f"{FOOTBALL_DATA_HOST}{path}"
    try:
        resp = requests.get(url, headers={"X-Auth-Token": FOOTBALL_DATA_API_KEY}, params=params, timeout=25)
        if resp.status_code != 200:
            print(f"[ERRORE football-data.org] {path}: status={resp.status_code} body={resp.text[:200]}")
            return None
        return resp.json()
    except (requests.RequestException, ValueError) as e:
        print(f"[ERRORE football-data.org] {path}: {e}")
        return None


def fetch_matches(competition_code: str):
    """Partite da CALENDAR_PAST_DAYS giorni fa ai prossimi FIXTURE_LOOKAHEAD_DAYS. None se errore."""
    today_it = datetime.now(ZoneInfo("Europe/Rome"))
    params = {
        "dateFrom": (today_it - timedelta(days=CALENDAR_PAST_DAYS)).strftime("%Y-%m-%d"),
        "dateTo": (today_it + timedelta(days=FIXTURE_LOOKAHEAD_DAYS)).strftime("%Y-%m-%d"),
    }
    data = fd_get(f"/competitions/{competition_code}/matches", params)
    if data is None:
        return None
    matches = []
    for m in data.get("matches", []):
        home = (m.get("homeTeam") or {}).get("name")
        away = (m.get("awayTeam") or {}).get("name")
        kickoff = m.get("utcDate")  # es. "2026-09-20T15:00:00Z"
        if home and away and kickoff:
            matches.append({"home": home, "away": away, "kickoff": kickoff, "status": m.get("status", "")})
    return matches


def fetch_teams(competition_code: str):
    """Squadre di un campionato, con allenatore se disponibile. None se errore."""
    data = fd_get(f"/competitions/{competition_code}/teams")
    if data is None:
        return None
    teams = []
    for t in data.get("teams", []):
        if not t.get("name"):
            continue
        coach = t.get("coach") or {}
        teams.append({
            "name": t["name"],
            "shortName": t.get("shortName") or "",
            "tla": t.get("tla") or "",
            "coach": coach.get("name") or "",
            "coach_last": coach.get("lastName") or "",
        })
    return teams


def teams_refresh_due(calendar: dict) -> bool:
    if not calendar.get("teams"):
        return True
    try:
        updated = datetime.fromisoformat(calendar["teams_updated"])
    except (TypeError, ValueError, KeyError):
        return True
    return datetime.now(timezone.utc) - updated > timedelta(hours=TEAMS_REFRESH_HOURS)


def run():
    if not FOOTBALL_DATA_API_KEY:
        print("[ERRORE] FOOTBALL_DATA_API_KEY mancante: calendario non aggiornato.")
        return

    calendar = load_calendar()
    previous_fixtures = calendar.get("fixtures", [])
    now = datetime.now(timezone.utc)
    oldest_kept = now - timedelta(days=CALENDAR_PAST_DAYS)

    def still_relevant(f):
        try:
            return datetime.fromisoformat(f["kickoff"].replace("Z", "+00:00")) >= oldest_kept
        except (KeyError, ValueError, AttributeError):
            return False

    # --- Partite ---
    fixtures = []
    competitions = [(lg["fd_code"], lg["name"], lg["flag"]) for lg in LEAGUES]
    competitions += [(code, code, "") for code in CALENDAR_EXTRA_COMPETITIONS]
    for code, name, flag in competitions:
        matches = fetch_matches(code)
        if matches is None:
            kept = [f for f in previous_fixtures if f.get("competition") == code and still_relevant(f)]
            print(f"[WARN] {name}: calendario non aggiornato, tengo le {len(kept)} partite gia' note.")
            fixtures.extend(kept)
            continue
        for m in matches:
            fixtures.append({
                "competition": code,
                "league": name,
                "flag": flag,
                "home": m["home"],
                "away": m["away"],
                "kickoff": m["kickoff"],
                "status": m["status"],
            })
    fixtures.sort(key=lambda f: f["kickoff"])
    calendar["fixtures"] = fixtures

    # --- Squadre (al massimo una volta al giorno) ---
    if teams_refresh_due(calendar):
        old_by_league = {}
        for t in calendar.get("teams", []):
            old_by_league.setdefault(t.get("league"), []).append(t)
        new_teams = []
        for lg in LEAGUES:
            teams = fetch_teams(lg["fd_code"])
            if not teams:
                kept = old_by_league.get(lg["name"], [])
                print(f"[WARN] {lg['name']}: squadre non aggiornate, tengo le {len(kept)} gia' note.")
                new_teams.extend(kept)
                continue
            for t in teams:
                t["league"] = lg["name"]
            new_teams.extend(teams)
        calendar["teams"] = new_teams
        calendar["teams_updated"] = now.isoformat()
        print(f"Squadre aggiornate: {len(new_teams)}.")

    save_calendar(calendar)
    future = sum(1 for f in fixtures if f["kickoff"] > now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    print(f"Calendario salvato: {len(fixtures)} partite ({future} da giocare, "
          f"{len(fixtures) - future} degli ultimi {CALENDAR_PAST_DAYS} giorni).")


if __name__ == "__main__":
    run()
