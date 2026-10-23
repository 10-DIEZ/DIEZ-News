"""
Funzioni di supporto: invio messaggi Telegram e gestione dello stato
(per non mandare due volte la stessa notifica).
"""

import json
import os
import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, STATE_FILE, FIXTURES_FILE


def send_telegram_photo(photo_url: str, caption: str, button_text: str = "", button_url: str = "") -> bool:
    """
    Invia una foto con didascalia al bot Telegram configurato.
    Se button_text/button_url sono forniti, aggiunge un pulsante cliccabile
    sotto il post (es. "Leggi l'articolo") invece di scrivere il link nel testo.
    Restituisce True se l'invio ha avuto successo, False altrimenti
    (cosi' chi chiama puo' fare un fallback al messaggio di solo testo).
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[ATTENZIONE] Token o chat id Telegram mancanti, foto non inviata.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "HTML",
    }
    if button_text and button_url:
        payload["reply_markup"] = json.dumps({
            "inline_keyboard": [[{"text": button_text, "url": button_url}]]
        })
    try:
        resp = requests.post(url, data=payload, timeout=20)
        if resp.status_code != 200:
            print(f"[ERRORE Telegram sendPhoto] status={resp.status_code} body={resp.text}")
            return False
        return True
    except requests.RequestException as e:
        print(f"[ERRORE Telegram sendPhoto] {e}")
        return False


def send_telegram_message(text: str, disable_preview: bool = False,
                          button_text: str = "", button_url: str = "") -> bool:
    """Invia un messaggio di testo al bot Telegram configurato (con pulsante opzionale).

    disable_preview=False (default) fa mostrare a Telegram l'anteprima
    automatica del link, quando il messaggio contiene un link.
    Restituisce True se l'invio e' riuscito.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[ATTENZIONE] Token o chat id Telegram mancanti, messaggio non inviato:")
        print(text)
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": disable_preview,
    }
    if button_text and button_url:
        payload["reply_markup"] = json.dumps({
            "inline_keyboard": [[{"text": button_text, "url": button_url}]]
        })
    try:
        resp = requests.post(url, data=payload, timeout=15)
        if resp.status_code != 200:
            print(f"[ERRORE Telegram] status={resp.status_code} body={resp.text}")
            return False
        return True
    except requests.RequestException as e:
        print(f"[ERRORE Telegram] {e}")
        return False


def load_state() -> dict:
    """Carica lo stato salvato (id/link gia' notificati)."""
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict) -> None:
    """Salva lo stato aggiornato su disco."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, separators=(",", ":"))


def load_calendar() -> dict:
    """
    Carica il calendario (scritto solo dal workflow calendario):
    {"fixtures": [...partite...], "teams": [...squadre...], "teams_updated": "..."}.
    Se il file non c'e' o e' illeggibile restituisce un calendario vuoto.
    """
    empty = {"fixtures": [], "teams": [], "teams_updated": None}
    if not os.path.exists(FIXTURES_FILE):
        return empty
    try:
        with open(FIXTURES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return empty
        data.setdefault("fixtures", [])
        data.setdefault("teams", [])
        data.setdefault("teams_updated", None)
        return data
    except (json.JSONDecodeError, OSError):
        return empty


def save_calendar(calendar: dict) -> None:
    """Salva il calendario nel file dedicato."""
    os.makedirs(os.path.dirname(FIXTURES_FILE), exist_ok=True)
    with open(FIXTURES_FILE, "w", encoding="utf-8") as f:
        json.dump(calendar, f, ensure_ascii=False, indent=2)
