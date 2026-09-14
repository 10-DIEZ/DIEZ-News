"""
Funzioni di supporto: invio messaggi Telegram e gestione dello stato
(per non mandare due volte la stessa notifica).
"""

import json
import os
import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, STATE_FILE


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


def send_telegram_message(text: str, disable_preview: bool = False) -> None:
    """Invia un messaggio al bot Telegram configurato.

    disable_preview=False (default) fa mostrare a Telegram l'anteprima
    automatica del link (immagine + descrizione presa dal sito), quando
    il messaggio contiene un link.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[ATTENZIONE] Token o chat id Telegram mancanti, messaggio non inviato:")
        print(text)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": disable_preview,
    }
    try:
        resp = requests.post(url, data=payload, timeout=15)
        if resp.status_code != 200:
            print(f"[ERRORE Telegram] status={resp.status_code} body={resp.text}")
    except requests.RequestException as e:
        print(f"[ERRORE Telegram] {e}")


def load_state() -> dict:
    """Carica lo stato salvato (id/link gia' notificati)."""
    if not os.path.exists(STATE_FILE):
        return {"injuries_seen": [], "news_seen": []}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"injuries_seen": [], "news_seen": []}


def save_state(state: dict) -> None:
    """Salva lo stato aggiornato su disco."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def trim_list(items: list, max_len: int = 3000) -> list:
    """Tiene la lista degli 'id visti' entro una dimensione ragionevole."""
    if len(items) > max_len:
        return items[-max_len:]
    return items
