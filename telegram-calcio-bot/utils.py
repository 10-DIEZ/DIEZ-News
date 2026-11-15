"""
Funzioni di supporto: chiamate a Telegram e gestione dello stato
(per non mandare due volte la stessa notifica).

Dove mandare ogni notizia (chat privata o argomento del gruppo) lo decide
telegram_group.py: qui ci sono solo le chiamate "di base".
"""

import json
import os
import time

import requests

from config import FIXTURES_FILE, STATE_FILE, TELEGRAM_API_BASE, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


class TgResult:
    """Esito di una chiamata a Telegram: vale True se e' andata a buon fine."""

    __slots__ = ("ok", "result", "error_code", "description", "retry_after", "migrate_to")

    def __init__(self, ok=False, result=None, error_code=0, description="", retry_after=0, migrate_to=None):
        self.ok = ok
        self.result = result
        self.error_code = error_code
        self.description = description
        self.retry_after = retry_after
        self.migrate_to = migrate_to

    def __bool__(self):
        return self.ok

    def __repr__(self):
        if self.ok:
            return "TgResult(ok)"
        return f"TgResult(errore {self.error_code}: {self.description})"


def telegram_api(method: str, payload: dict | None = None, timeout: int = 20, log_errors: bool = True,
                 files: dict | None = None) -> TgResult:
    """
    Chiama un metodo delle Bot API di Telegram.
    Se Telegram chiede di rallentare (errore 429) e l'attesa e' breve,
    aspetta e riprova una volta da solo.
    files: file da caricare (es. {"photo": ("foto.jpg", dati, "image/jpeg")}).
    """
    if not TELEGRAM_BOT_TOKEN:
        return TgResult(description="token Telegram mancante")
    url = f"{TELEGRAM_API_BASE}/bot{TELEGRAM_BOT_TOKEN}/{method}"
    res = TgResult()
    for attempt in range(2):
        try:
            resp = requests.post(url, data=payload or {}, files=files, timeout=timeout)
        except requests.RequestException as e:
            res = TgResult(description=f"rete: {e.__class__.__name__}")
            break
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if resp.status_code == 200 and data.get("ok"):
            return TgResult(ok=True, result=data.get("result"))
        params = data.get("parameters") or {}
        res = TgResult(
            error_code=data.get("error_code") or resp.status_code,
            description=data.get("description") or resp.text[:200],
            retry_after=int(params.get("retry_after") or 0),
            migrate_to=params.get("migrate_to_chat_id"),
        )
        if res.error_code == 429 and attempt == 0 and 0 < res.retry_after <= 25:
            time.sleep(res.retry_after + 0.5)
            continue
        break
    if log_errors:
        print(f"[ERRORE Telegram {method}] {res.error_code} {res.description}")
    return res


def _with_button(payload: dict, button_text: str, button_url: str) -> dict:
    if button_text and button_url:
        payload["reply_markup"] = json.dumps({
            "inline_keyboard": [[{"text": button_text, "url": button_url}]]
        })
    return payload


def send_telegram_photo(photo_url: str, caption: str, button_text: str = "", button_url: str = "",
                        chat_id=None, thread_id=None) -> TgResult:
    """
    Invia una foto con didascalia. Se button_text/button_url sono forniti,
    aggiunge un pulsante cliccabile sotto il post (es. "Leggi l'articolo").
    chat_id/thread_id: dove mandarla (di default la chat privata col bot;
    thread_id = argomento del gruppo). Il risultato vale False se l'invio non
    e' riuscito, cosi' chi chiama puo' ripiegare sul messaggio di solo testo.
    """
    target = chat_id or TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not target:
        print("[ATTENZIONE] Token o chat id Telegram mancanti, foto non inviata.")
        return TgResult(description="token o chat id mancanti")
    payload = {"chat_id": target, "photo": photo_url, "caption": caption, "parse_mode": "HTML"}
    if thread_id:
        payload["message_thread_id"] = thread_id
    return telegram_api("sendPhoto", _with_button(payload, button_text, button_url), timeout=25)


# Errori con cui Telegram dice "non sono riuscito a scaricare la foto da quel sito"
_PHOTO_FETCH_ERRORS = ("failed to get http url content", "wrong file identifier", "wrong type of the web page",
                       "webpage_media_empty", "webpage_curl_failed", "wrong remote file identifier")
_PHOTO_MAX_BYTES = 9 * 1024 * 1024
_PHOTO_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "image/jpeg,image/png,image/*;q=0.8,*/*;q=0.5",    # niente avif: Telegram non lo accetta
}


def is_photo_fetch_error(res: TgResult) -> bool:
    """True se Telegram ha rifiutato la foto perche' non e' riuscito a scaricarla dal sito."""
    desc = (res.description or "").lower()
    return res.error_code == 400 and any(k in desc for k in _PHOTO_FETCH_ERRORS)


def send_telegram_photo_upload(photo_url: str, caption: str, button_text: str = "", button_url: str = "",
                               chat_id=None, thread_id=None) -> TgResult:
    """
    Come send_telegram_photo, ma la foto la scarica il bot e la carica su
    Telegram (serve quando Telegram non riesce a prenderla dal sito: alcuni
    siti lo bloccano). Se non si riesce a scaricarla il risultato vale False.
    """
    target = chat_id or TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not target:
        return TgResult(description="token o chat id mancanti")
    try:
        resp = requests.get(photo_url, headers=_PHOTO_HEADERS, timeout=10)
    except requests.RequestException as e:
        return TgResult(description=f"foto non scaricata: {e.__class__.__name__}")
    ctype = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
    data = resp.content or b""
    if resp.status_code != 200 or not ctype.startswith("image/") or ctype in ("image/avif", "image/svg+xml") \
            or not 1024 <= len(data) <= _PHOTO_MAX_BYTES:
        return TgResult(description=f"foto non scaricata: stato {resp.status_code}, tipo {ctype or '?'}, "
                                    f"{len(data)} byte")
    ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}.get(ctype, "jpg")
    payload = {"chat_id": target, "caption": caption, "parse_mode": "HTML"}
    if thread_id:
        payload["message_thread_id"] = thread_id
    return telegram_api("sendPhoto", _with_button(payload, button_text, button_url), timeout=40,
                        files={"photo": (f"foto.{ext}", data, ctype)})


def send_telegram_message(text: str, disable_preview: bool = False, button_text: str = "",
                          button_url: str = "", chat_id=None, thread_id=None) -> TgResult:
    """
    Invia un messaggio di testo (con pulsante opzionale).
    disable_preview=False (default) fa mostrare a Telegram l'anteprima
    automatica del link, quando il messaggio contiene un link.
    """
    target = chat_id or TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not target:
        print("[ATTENZIONE] Token o chat id Telegram mancanti, messaggio non inviato:")
        print(text)
        return TgResult(description="token o chat id mancanti")
    payload = {"chat_id": target, "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": "true" if disable_preview else "false"}
    if thread_id:
        payload["message_thread_id"] = thread_id
    return telegram_api("sendMessage", _with_button(payload, button_text, button_url), timeout=20)


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
