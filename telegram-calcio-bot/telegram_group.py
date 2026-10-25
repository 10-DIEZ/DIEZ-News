"""
Dove mandare le notizie: gruppo con un argomento per campionato, oppure
(finche' il gruppo non c'e') la chat privata col bot, come prima.

COME SI COLLEGA IL GRUPPO (da solo)
A ogni giro il bot legge gli aggiornamenti di Telegram (getUpdates). Quando
vede che e' stato aggiunto a un gruppo, e che a farlo sei stato proprio tu
(il tuo id e' TELEGRAM_CHAT_ID, cioe' la chat privata), controlla che:
  - il gruppo abbia gli Argomenti attivi
  - lui sia amministratore con il permesso di gestire gli argomenti
poi crea un argomento per campionato (config.TOPICS), ne salva gli indirizzi
nello stato (state.json, chiave "telegram") e da quel momento manda ogni
notizia nell'argomento del suo campionato. Se manca qualcosa te lo scrive
UNA volta nella chat privata, cosi' sai cosa sistemare.

Se un gruppo lo aggiunge qualcun altro, il bot lo ignora.

COSE CHE SI SISTEMANO DA SOLE
- argomento cancellato per sbaglio -> il bot lo ricrea
- bot tolto dal gruppo / gruppo cancellato -> le notizie tornano nella chat
  privata (con un avviso); per tornare al gruppo basta riaggiungere il bot
- gruppo "normale" trasformato in supergruppo attivando gli Argomenti (Telegram
  gli cambia l'id) -> il bot segue il nuovo id
"""

import html
from datetime import datetime, timezone

from config import (
    LEAGUES,
    SEND_DELAY_GROUP_SECONDS,
    SEND_DELAY_PRIVATE_SECONDS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_GROUP_ID,
    TOPICS,
)
from utils import TgResult, send_telegram_message, send_telegram_photo, telegram_api

# Errori di Telegram che vogliono dire "quell'argomento non esiste piu'"
_THREAD_GONE = ("message thread not found", "thread not found", "topic_deleted", "topic deleted",
                "topic_id_invalid", "message_thread_id_invalid")
# Errori che vogliono dire "nel gruppo non posso piu' scrivere"
_GROUP_GONE = ("bot was kicked", "bot is not a member", "chat not found", "group chat was deactivated",
               "chat_write_forbidden", "not enough rights", "have no rights to send", "chat_admin_required",
               "group chat was upgraded", "peer_id_invalid", "channel_private")

MAX_UPDATE_PAGES = 5


def _as_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _esc(text) -> str:
    return html.escape(str(text or ""), quote=False)


class Destination:
    """Sa dove va ogni notizia e la manda (con le riparazioni automatiche)."""

    def __init__(self, state: dict):
        self.cfg = state.setdefault("telegram", {})
        for key, default in (("offset", 0), ("group_id", None), ("group_title", ""), ("ready", False),
                             ("topics", {}), ("notice", ""), ("linked_at", None)):
            self.cfg.setdefault(key, default)
        chat = _as_int(TELEGRAM_CHAT_ID)
        # TELEGRAM_CHAT_ID e' la chat privata col bot = il tuo id utente (numero positivo).
        # Se fosse gia' l'id di un gruppo (numero negativo) lo usiamo come gruppo fisso.
        self.owner_id = chat if chat and chat > 0 else None
        self.private_chat = chat if self.owner_id else None
        self.fixed_group = _as_int(TELEGRAM_GROUP_ID) or (chat if chat and chat < 0 else None)
        self.bot_id = _as_int(TELEGRAM_BOT_TOKEN.split(":", 1)[0]) if TELEGRAM_BOT_TOKEN else None
        self.verify = False
        self._recreated = set()
        self._lost_ids = set()

    # ------------------------------------------------------------------
    # Stato del collegamento
    # ------------------------------------------------------------------

    @property
    def in_group(self) -> bool:
        return bool(self.cfg["ready"] and self.cfg["group_id"])

    @property
    def send_delay(self) -> float:
        return SEND_DELAY_GROUP_SECONDS if self.in_group else SEND_DELAY_PRIVATE_SECONDS

    def describe(self) -> str:
        if self.in_group:
            return f"gruppo «{self.cfg['group_title']}» ({len(self.cfg['topics'])} argomenti)"
        if self.cfg["group_id"]:
            return f"chat privata (gruppo «{self.cfg['group_title']}» trovato ma non ancora pronto)"
        return "chat privata"

    def prepare(self) -> None:
        """Da chiamare una volta all'inizio del giro: legge le novita' e, se serve, prepara il gruppo."""
        if not TELEGRAM_BOT_TOKEN:
            return
        if self.fixed_group and self.cfg["group_id"] != self.fixed_group:
            self._set_group(self.fixed_group, "")
        self._read_updates()
        if self.cfg["group_id"] and (not self.cfg["ready"] or self.verify):
            self._setup_group()
        print(f"Destinazione notizie: {self.describe()}")

    def _set_group(self, group_id: int, title: str) -> None:
        if group_id != self.cfg["group_id"]:
            self.cfg.update(group_id=group_id, group_title=title or "", ready=False, topics={})
        elif title:
            self.cfg["group_title"] = title
        self.verify = True

    def _read_updates(self) -> None:
        for _ in range(MAX_UPDATE_PAGES):
            res = telegram_api("getUpdates", {"offset": self.cfg["offset"], "timeout": 0, "limit": 100},
                               log_errors=False)
            if not res:
                if res.error_code == 409:
                    print("[WARN] Telegram: c'e' un webhook attivo, non posso leggere gli aggiornamenti "
                          "(il gruppo non si collega da solo: usa il secret TELEGRAM_GROUP_ID)")
                elif res.error_code or res.description:
                    print(f"[WARN] Telegram getUpdates: {res.error_code} {res.description}")
                return
            updates = res.result or []
            for u in updates:
                self.cfg["offset"] = max(self.cfg["offset"], int(u.get("update_id", 0)) + 1)
                try:
                    self._handle_update(u)
                except (KeyError, TypeError, AttributeError, ValueError) as e:
                    print(f"[WARN] aggiornamento Telegram non letto: {e}")
            if len(updates) < 100:
                return

    def _handle_update(self, u: dict) -> None:
        member = u.get("my_chat_member")
        if member:
            chat = member.get("chat") or {}
            if chat.get("type") not in ("group", "supergroup"):
                return
            group_id = chat.get("id")
            status = (member.get("new_chat_member") or {}).get("status")
            added_by = (member.get("from") or {}).get("id")
            if status in ("left", "kicked"):
                if group_id == self.cfg["group_id"]:
                    self._lost_group("mi hanno tolto dal gruppo")
                return
            if status not in ("administrator", "member", "restricted"):
                return
            if group_id == self.cfg["group_id"]:
                self.verify = True          # cambiati i permessi del bot: ricontrollo
                if chat.get("title"):
                    self.cfg["group_title"] = chat["title"]
            elif not self.fixed_group and self.owner_id and added_by == self.owner_id:
                print(f"Trovato un gruppo a cui mi hai aggiunto: «{chat.get('title', '')}» ({group_id})")
                self._set_group(group_id, chat.get("title", ""))
            return
        # gruppo "normale" diventato supergruppo: Telegram lo segnala sia nel
        # vecchio gruppo (migrate_to_chat_id) sia nel nuovo (migrate_from_chat_id)
        message = u.get("message") or {}
        chat = message.get("chat") or {}
        old_id = new_id = None
        if message.get("migrate_to_chat_id"):
            old_id, new_id = chat.get("id"), message["migrate_to_chat_id"]
        elif message.get("migrate_from_chat_id"):
            old_id, new_id = message["migrate_from_chat_id"], chat.get("id")
        if new_id and new_id != self.cfg["group_id"] and \
                (old_id == self.cfg["group_id"] or old_id in self._lost_ids):
            print(f"Il gruppo e' diventato un supergruppo: nuovo id {new_id}")
            self._set_group(new_id, self.cfg["group_title"] or chat.get("title", ""))

    def _setup_group(self) -> None:
        group_id = self.cfg["group_id"]
        res = telegram_api("getChat", {"chat_id": group_id}, log_errors=False)
        if not res and res.migrate_to:
            print(f"Il gruppo e' diventato un supergruppo: nuovo id {res.migrate_to}")
            self._set_group(res.migrate_to, self.cfg["group_title"])
            group_id = self.cfg["group_id"]
            res = telegram_api("getChat", {"chat_id": group_id}, log_errors=False)
        if not res:
            if res.error_code in (400, 403):
                print(f"[WARN] gruppo {group_id} non raggiungibile ({res.description}): resto sulla chat privata")
                self._lost_group("non riesco piu' ad accedere al gruppo")
            else:
                print(f"[WARN] controllo del gruppo non riuscito ({res.error_code} {res.description}), "
                      f"riprovo al prossimo giro")
            return
        chat = res.result or {}
        title = chat.get("title") or self.cfg["group_title"]
        self.cfg["group_title"] = title

        if chat.get("type") != "supergroup" or not chat.get("is_forum"):
            self._waiting("no_topics",
                          f"👋 Ho trovato il gruppo «{_esc(title)}».\n\n"
                          f"Manca un passo: nelle impostazioni del gruppo attiva gli <b>Argomenti</b>. "
                          f"Appena li attivi creo io un argomento per ogni campionato.")
            return
        res = telegram_api("getChatMember", {"chat_id": group_id, "user_id": self.bot_id}, log_errors=False)
        if not res:
            print(f"[WARN] non riesco a leggere i miei permessi nel gruppo ({res.error_code} {res.description})")
            return
        me = res.result or {}
        if me.get("status") != "administrator":
            self._waiting("not_admin",
                          f"👋 Sono nel gruppo «{_esc(title)}», ma non sono amministratore.\n\n"
                          f"Nominami <b>amministratore</b> (con il permesso di gestire gli argomenti) "
                          f"e creo io un argomento per ogni campionato.")
            return
        if not me.get("can_manage_topics"):
            self._waiting("no_manage_topics",
                          f"👋 Sono amministratore del gruppo «{_esc(title)}», ma mi manca il permesso "
                          f"di <b>gestire gli argomenti</b>.\n\nAttivalo nei miei permessi da "
                          f"amministratore e creo io un argomento per ogni campionato.")
            return

        for lg in LEAGUES:
            if not self.cfg["topics"].get(lg["name"]) and not self._create_topic(lg["name"]):
                print(f"[WARN] argomento {lg['name']} non creato: riprovo al prossimo giro "
                      f"(intanto le notizie restano nella chat privata)")
                return
        was_ready = self.cfg["ready"]
        self.cfg["ready"] = True
        self.verify = False
        if not was_ready:
            self.cfg["linked_at"] = datetime.now(timezone.utc).isoformat()
            self._announce_linked()

    def _create_topic(self, league: str):
        info = TOPICS.get(league) or {}
        payload = {"chat_id": self.cfg["group_id"], "name": info.get("name") or league}
        if info.get("color"):
            payload["icon_color"] = info["color"]
        res = telegram_api("createForumTopic", payload)
        if not res and info.get("color") and "icon" in (res.description or "").lower():
            payload.pop("icon_color")
            res = telegram_api("createForumTopic", payload)
        thread_id = res.result.get("message_thread_id") if res and isinstance(res.result, dict) else None
        if not thread_id:
            return None
        self.cfg["topics"][league] = thread_id
        print(f"Creato l'argomento «{payload['name']}» (id {thread_id})")
        return thread_id

    def _waiting(self, reason: str, text: str) -> None:
        """Gruppo trovato ma non ancora pronto: avviso in privato, una volta sola per ogni problema."""
        self.cfg["ready"] = False
        print(f"Gruppo Telegram non ancora pronto: {reason}")
        key = f"{reason}:{self.cfg['group_id']}"
        if self.private_chat and self.cfg.get("notice") != key:
            if send_telegram_message(text, disable_preview=True, chat_id=self.private_chat):
                self.cfg["notice"] = key

    def _lost_group(self, reason: str) -> None:
        title, was_ready = self.cfg["group_title"], self.cfg["ready"]
        if self.cfg["group_id"]:
            self._lost_ids.add(self.cfg["group_id"])
        self.cfg.update(group_id=None, group_title="", ready=False, topics={})
        self.verify = False
        if was_ready and self.private_chat:
            send_telegram_message(
                f"⚠️ Non riesco piu' a scrivere nel gruppo «{_esc(title)}» ({_esc(reason)}).\n\n"
                f"Intanto ti mando di nuovo le notizie qui. Per tornare al gruppo, aggiungimi di nuovo "
                f"come amministratore.", disable_preview=True, chat_id=self.private_chat)
            self.cfg["notice"] = "lost"

    def _announce_linked(self) -> None:
        group_id, title = self.cfg["group_id"], self.cfg["group_title"]
        names = "\n".join(f"• {_esc((TOPICS.get(lg['name']) or {}).get('name') or lg['name'])}" for lg in LEAGUES)
        send_telegram_message(
            f"✅ <b>Gruppo collegato!</b>\n\nDa ora le notizie arrivano qui, ognuna nell'argomento del "
            f"suo campionato:\n{names}\n\nPer vedere tutte le notizie di una squadra tocca il suo hashtag "
            f"in fondo a un post (es. #Inter), oppure cercalo con la lente.",
            disable_preview=True, chat_id=group_id)
        if self.private_chat:
            send_telegram_message(
                f"📢 Da ora le notizie arrivano nel gruppo «{_esc(title)}», divise per campionato.\n\n"
                f"Qui ti scrivo solo se c'e' qualche problema con il gruppo.",
                disable_preview=True, chat_id=self.private_chat)
        self.cfg["notice"] = f"linked:{group_id}"
        print(f"Gruppo «{title}» collegato: da ora le notizie vanno negli argomenti")

    # ------------------------------------------------------------------
    # Invio
    # ------------------------------------------------------------------

    def _target(self, league: str):
        if self.in_group:
            thread_id = self.cfg["topics"].get(league)
            if thread_id:
                return self.cfg["group_id"], thread_id
        return None, None   # None = chat privata (TELEGRAM_CHAT_ID)

    @staticmethod
    def _is_hard_group_error(res: TgResult) -> bool:
        """Errori per cui nel gruppo non passa nulla (ne' foto ne' testo)."""
        desc = (res.description or "").lower()
        return bool(res.migrate_to) or res.error_code == 403 or any(k in desc for k in _THREAD_GONE) or \
            any(k in desc for k in ("bot was kicked", "bot is not a member", "chat not found",
                                    "group chat was deactivated", "group chat was upgraded"))

    def _send_once(self, chat_id, thread_id, caption, photo_url, button_text, button_url) -> TgResult:
        if photo_url:
            res = send_telegram_photo(photo_url, caption, button_text, button_url,
                                      chat_id=chat_id, thread_id=thread_id)
            # se il problema e' il gruppo (non la foto) e' inutile riprovare col testo
            if res or (thread_id and self._is_hard_group_error(res)):
                return res
        return send_telegram_message(caption, disable_preview=True, button_text=button_text,
                                     button_url=button_url, chat_id=chat_id, thread_id=thread_id)

    def send(self, league: str, caption: str, photo_url: str = "",
             button_text: str = "", button_url: str = "") -> bool:
        """
        Manda la notizia (foto con didascalia, o solo testo se la foto non va)
        nell'argomento del suo campionato, o nella chat privata. True se e' arrivata.
        """
        for _ in range(3):
            chat_id, thread_id = self._target(league)
            res = self._send_once(chat_id, thread_id, caption, photo_url, button_text, button_url)
            if res:
                return True
            if not thread_id:
                return False   # chat privata: come sempre, si riprova al prossimo giro
            desc = (res.description or "").lower()
            if res.migrate_to:
                self._set_group(res.migrate_to, self.cfg["group_title"])
                self._setup_group()
                continue
            if any(k in desc for k in _THREAD_GONE) and league not in self._recreated:
                print(f"[WARN] l'argomento di {league} non esiste piu': lo ricreo")
                self._recreated.add(league)
                self.cfg["topics"].pop(league, None)
                if not self._create_topic(league):
                    self.cfg["ready"] = False   # riprovo a sistemare il gruppo al prossimo giro
                continue
            if res.error_code == 403 or any(k in desc for k in _GROUP_GONE):
                self._lost_group("mi hanno tolto dal gruppo o non ho piu' i permessi")
                continue
            return False   # altro errore (rete, limiti...): si riprova al prossimo giro
        return False
