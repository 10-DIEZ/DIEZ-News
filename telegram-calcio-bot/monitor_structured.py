"""
Recupera il calendario delle partite dei 5 campionati per i prossimi
FIXTURE_LOOKAHEAD_DAYS giorni (non solo oggi), con l'orario esatto di
ogni partita. Serve a far "entrare" ogni partita nella ricerca mirata
con qualche giorno di anticipo (vedi ACTIVE_WINDOW_DAYS in config.py),
invece di scoprirla solo il giorno stesso.

Il calendario viene salvato in state/fixtures.json (file SEPARATO da
state.json, che e' del workflow notizie): cosi' i due workflow non si
contendono mai lo stesso file quando salvano su GitHub.

Da eseguire ~2 volte al giorno (vedi workflow GitHub Actions) - il
calendario cambia poco, non serve aggiornarlo piu' spesso.
"""

import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from config import FIXTURE_LOOKAHEAD_DAYS, FOOTBALL_DATA_API_KEY, FOOTBALL_DATA_HOST, LEAGUES
from utils import load_fixtures, load_state, save_fixtures


def fetch_fixtures_window(competition_code: str, days_ahead: int):
    """
    Recupera le partite in programma da oggi ai prossimi 'days_ahead' giorni.
    Restituisce None in caso di errore (diverso da lista vuota = nessuna
    partita), cosi' chi chiama puo' tenere il calendario precedente.
    """
    today_it = datetime.now(ZoneInfo("Europe/Rome"))
    date_from = today_it.strftime("%Y-%m-%d")
    date_to = (today_it + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    url = f"{FOOTBALL_DATA_HOST}/competitions/{competition_code}/matches"
    headers = {"X-Auth-Token": FOOTBALL_DATA_API_KEY}
    params = {"dateFrom": date_from, "dateTo": date_to}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=20)
        if resp.status_code != 200:
            print(f"[ERRORE football-data.org] {competition_code}: status={resp.status_code} body={resp.text[:200]}")
            return None
        data = resp.json()
        matches = []
        for m in data.get("matches", []):
            home = m.get("homeTeam", {}).get("name")
            away = m.get("awayTeam", {}).get("name")
            kickoff = m.get("utcDate")  # es. "2026-09-20T15:00:00Z"
            if home and away and kickoff:
                matches.append({"home": home, "away": away, "kickoff": kickoff})
        return matches
    except requests.RequestException as e:
        print(f"[ERRORE football-data.org] {competition_code}: {e}")
        return None


def is_future(kickoff_str: str) -> bool:
    """True se la partita non e' ancora iniziata (le partite gia' giocate non servono piu')."""
    try:
        kickoff = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return True
    return kickoff > datetime.now(timezone.utc)


def run():
    # Calendario precedente: serve se football-data.org non risponde per un
    # campionato, cosi' non perdiamo le sue partite fino al prossimo giro.
    previous = load_fixtures()
    if previous is None:
        previous = load_state().get("today_fixtures", [])

    upcoming_fixtures = []
    for league in LEAGUES:
        matches = fetch_fixtures_window(league["fd_code"], FIXTURE_LOOKAHEAD_DAYS)
        if matches is None:
            kept = [f for f in previous if f.get("league") == league["name"] and is_future(f.get("kickoff", ""))]
            print(f"[WARN] {league['name']}: calendario non aggiornato, tengo le {len(kept)} partite gia' note.")
            upcoming_fixtures.extend(kept)
            continue
        for m in matches:
            if not is_future(m["kickoff"]):
                continue  # gia' giocata o in corso: inutile tenerla
            upcoming_fixtures.append({
                "league": league["name"],
                "flag": league["flag"],
                "home": m["home"],
                "away": m["away"],
                "kickoff": m["kickoff"],
                "native_lang": league["native_lang"],
                "native_country": league["native_country"],
            })

    upcoming_fixtures.sort(key=lambda f: f["kickoff"])
    save_fixtures(upcoming_fixtures)
    print(f"Calendario salvato: {len(upcoming_fixtures)} partite non ancora giocate nei prossimi {FIXTURE_LOOKAHEAD_DAYS} giorni.")


if __name__ == "__main__":
    run()
