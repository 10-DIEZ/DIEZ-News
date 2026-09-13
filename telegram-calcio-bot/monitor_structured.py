"""
Controlla infortuni e squalifiche (dati ufficiali) per i 5 campionati
tramite API-Football, e manda su Telegram solo le novità.

Da eseguire ~2 volte al giorno (vedi workflow GitHub Actions).
Consumo: 1 chiamata API per campionato = 5 chiamate a esecuzione.
"""

import requests

from config import API_FOOTBALL_HOST, API_FOOTBALL_KEY, LEAGUES, SEASON
from utils import load_state, save_state, send_telegram_message, trim_list


def fetch_injuries(league_id: int) -> list:
    """Recupera la lista infortuni/squalifiche per un campionato (stagione corrente)."""
    url = f"{API_FOOTBALL_HOST}/injuries"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    params = {"league": league_id, "season": SEASON}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json().get("response", [])
    except requests.RequestException as e:
        print(f"[ERRORE API-Football] league={league_id}: {e}")
        return []


def format_entry(entry: dict, league_name: str) -> tuple:
    """
    Trasforma una riga della risposta API-Football in (id_univoco, testo_messaggio).
    Struttura tipica di 'entry': player{}, team{}, fixture{}, player.reason
    """
    player = entry.get("player", {})
    team = entry.get("team", {})
    fixture = entry.get("fixture", {})

    player_name = player.get("name", "Giocatore sconosciuto")
    reason = player.get("reason", "Motivo non specificato")
    team_name = team.get("name", "Squadra sconosciuta")
    fixture_date = fixture.get("date", "")

    uid = f"{league_name}|{player_name}|{team_name}|{reason}|{fixture_date}"

    tipo = "🟥 Squalifica" if "suspend" in reason.lower() else "🩹 Infortunio/Assenza"
    testo = (
        f"{tipo} — <b>{league_name}</b>\n"
        f"{player_name} ({team_name})\n"
        f"Motivo: {reason}"
    )
    return uid, testo


def run():
    state = load_state()
    seen = set(state.get("injuries_seen", []))
    new_seen = list(seen)
    any_new = False

    for league in LEAGUES:
        entries = fetch_injuries(league["id"])
        for entry in entries:
            uid, testo = format_entry(entry, league["name"])
            if uid in seen:
                continue
            send_telegram_message(testo)
            new_seen.append(uid)
            seen.add(uid)
            any_new = True

    if any_new:
        state["injuries_seen"] = trim_list(new_seen)
        save_state(state)
        print("Stato aggiornato con nuove voci infortuni/squalifiche.")
    else:
        print("Nessuna novità su infortuni/squalifiche.")


if __name__ == "__main__":
    run()
