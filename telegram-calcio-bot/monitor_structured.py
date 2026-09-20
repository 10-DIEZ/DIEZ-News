"""
Recupera il calendario delle partite dei 5 campionati per i prossimi
FIXTURE_LOOKAHEAD_DAYS giorni (non solo oggi), con l'orario esatto di
ogni partita. Serve a far "entrare" ogni partita nella ricerca mirata
con qualche giorno di anticipo (vedi ACTIVE_WINDOW_DAYS in config.py),
invece di scoprirla solo il giorno stesso.

Da eseguire ~2 volte al giorno (vedi workflow GitHub Actions) - il
calendario cambia poco, non serve aggiornarlo piu' spesso.
"""

import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import FIXTURE_LOOKAHEAD_DAYS, FOOTBALL_DATA_API_KEY, FOOTBALL_DATA_HOST, LEAGUES
from utils import load_state, save_state


def fetch_fixtures_window(competition_code: str, days_ahead: int) -> list:
    """Recupera le partite in programma da oggi ai prossimi 'days_ahead' giorni."""
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
            return []
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
        return []


def run():
    state = load_state()

    upcoming_fixtures = []
    for league in LEAGUES:
        matches = fetch_fixtures_window(league["fd_code"], FIXTURE_LOOKAHEAD_DAYS)
        for m in matches:
            upcoming_fixtures.append({
                "league": league["name"],
                "flag": league["flag"],
                "home": m["home"],
                "away": m["away"],
                "kickoff": m["kickoff"],
                "native_lang": league["native_lang"],
                "native_country": league["native_country"],
            })

    state["today_fixtures"] = upcoming_fixtures  # nome storico della chiave, contenuto ora esteso
    state.pop("today_cup_fixtures", None)  # non piu' usato, pulizia
    save_state(state)
    print(f"Calendario salvato: {len(upcoming_fixtures)} partite nei prossimi {FIXTURE_LOOKAHEAD_DAYS} giorni.")


if __name__ == "__main__":
    run()
