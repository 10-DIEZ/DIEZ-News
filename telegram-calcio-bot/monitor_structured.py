"""
Recupera il calendario delle partite di OGGI per i 5 campionati seguiti,
usando football-data.org (gratis per sempre per questi campionati,
a differenza di API-Football il cui piano free non copre la stagione
in corso). Il calendario viene salvato nello stato condiviso e usato
da monitor_news.py per cercare in modo mirato formazioni/anteprime.

Da eseguire ~2 volte al giorno (vedi workflow GitHub Actions).
Nota: gli infortuni/squalifiche "ufficiali" non hanno un buon equivalente
gratuito, quindi vengono intercettati dalle notizie generiche (che hanno
gia' l'etichetta "Infortuni / squalifiche") invece che da un'API dedicata.
"""

import requests
from datetime import datetime
from zoneinfo import ZoneInfo

from config import FOOTBALL_DATA_API_KEY, FOOTBALL_DATA_HOST, LEAGUES, THESPORTSDB_LEAGUE_IDS
from utils import load_state, save_state

THESPORTSDB_KEY = "3"  # chiave pubblica di test, gratuita, nessuna registrazione


def fetch_today_fixtures(competition_code: str) -> list:
    """Recupera le partite in programma OGGI (data italiana) per una competizione (football-data.org)."""
    today_it = datetime.now(ZoneInfo("Europe/Rome")).strftime("%Y-%m-%d")
    url = f"{FOOTBALL_DATA_HOST}/competitions/{competition_code}/matches"
    headers = {"X-Auth-Token": FOOTBALL_DATA_API_KEY}
    params = {"dateFrom": today_it, "dateTo": today_it}
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
            if home and away:
                matches.append({"home": home, "away": away})
        return matches
    except requests.RequestException as e:
        print(f"[ERRORE football-data.org] {competition_code}: {e}")
        return []


def fetch_today_cup_fixtures(league_id: str) -> list:
    """
    Recupera le partite di OGGI per Europa League/Conference League via
    TheSportsDB (football-data.org non le copre nel piano gratuito).
    Se il servizio non risponde bene, restituisce lista vuota senza
    bloccare il resto (la ricerca generica di riserva resta comunque attiva).
    """
    today_it = datetime.now(ZoneInfo("Europe/Rome")).strftime("%Y-%m-%d")
    url = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_KEY}/eventsnextleague.php"
    try:
        resp = requests.get(url, params={"id": league_id}, timeout=20)
        if resp.status_code != 200:
            print(f"[ERRORE TheSportsDB] league={league_id}: status={resp.status_code}")
            return []
        events = resp.json().get("events") or []
        matches = []
        for ev in events:
            if ev.get("dateEvent") != today_it:
                continue
            home = ev.get("strHomeTeam")
            away = ev.get("strAwayTeam")
            if home and away:
                matches.append({"home": home, "away": away})
        return matches
    except requests.RequestException as e:
        print(f"[ERRORE TheSportsDB] league={league_id}: {e}")
        return []


def run():
    state = load_state()

    today_fixtures = []
    for league in LEAGUES:
        matches = fetch_today_fixtures(league["fd_code"])
        for m in matches:
            today_fixtures.append({
                "league": league["name"],
                "flag": league["flag"],
                "home": m["home"],
                "away": m["away"],
                "native_lang": league["native_lang"],
                "native_country": league["native_country"],
            })

    cup_flags = {"Europa League": "🟠", "Conference League": "🔵"}
    today_cup_fixtures = []
    for comp_name, league_id in THESPORTSDB_LEAGUE_IDS.items():
        matches = fetch_today_cup_fixtures(league_id)
        for m in matches:
            today_cup_fixtures.append({
                "league": comp_name,
                "flag": cup_flags.get(comp_name, "⚽"),
                "home": m["home"],
                "away": m["away"],
                "native_lang": None,
                "native_country": None,
            })

    state["today_fixtures"] = today_fixtures
    state["today_cup_fixtures"] = today_cup_fixtures
    save_state(state)
    print(f"Calendario di oggi salvato: {len(today_fixtures)} partite campionati + {len(today_cup_fixtures)} coppe.")


if __name__ == "__main__":
    run()
