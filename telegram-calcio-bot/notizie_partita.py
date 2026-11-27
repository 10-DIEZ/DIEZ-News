"""
Notizie di una partita, per il bot quote (monitor_quote.py).

Il messaggio 📰 con le notizie delle due squadre sotto ogni avviso e' spento dal
27/11/2026 (NOTIZIE_SOTTO_AVVISO in monitor_quote.py); pick() serve ancora al
🔎 Perche' dell'avviso, che passa all'IA le notizie delle due squadre.
Com'era il 📰: conferenze stampa, infortuni, formazioni e allenatore (le
notizie generali no); per ogni notizia ora, tipo, titolo e testata; il titolo
porta al post nell'argomento del campionato.

Le notizie arrivano dal registro del bot notizie (state/state.json, chiave
"log": lo scrive monitor_news.py a ogni invio e tiene le ultime 48 ore).
Qui nessuna chiamata a internet: si legge solo quel file.
"""

import html
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import TYPE_TAGS

ROME = ZoneInfo("Europe/Rome")
DAYS = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]


def _esc(text) -> str:
    return html.escape(str(text or ""), quote=False)


def post_link(group_id, entry: dict) -> str:
    """
    Link al post della notizia nell'argomento del gruppo
    (t.me/c/<gruppo>/<argomento>/<messaggio>); se il post non e' nel gruppo,
    il link all'articolo; "" se non c'e' nessuno dei due.
    """
    gid = str(group_id or "")
    if gid.startswith("-100") and entry.get("m") and entry.get("th"):
        return f"https://t.me/c/{gid[4:]}/{entry['th']}/{entry['m']}"
    url = str(entry.get("u") or "")
    return url if url.startswith("http") else ""


def when(ts: float, ref: datetime) -> str:
    """'19:48' se e' lo stesso giorno di ref (ora italiana), se no 'ven 13:05'."""
    t = datetime.fromtimestamp(ts, timezone.utc).astimezone(ROME)
    if t.date() == ref.astimezone(ROME).date():
        return f"{t:%H:%M}"
    return f"{DAYS[t.weekday()]} {t:%H:%M}"


def pick(entries: list, home: str, away: str, start_ts: float, end_ts: float, per_team: int) -> dict:
    """
    Notizie con un tipo (conferenza, infortuni, formazioni, allenatore) uscite
    tra start_ts (escluso) e end_ts, dalla piu' recente: {squadra: [notizie]}.
    Una notizia va sotto la squadra di cui parla (la prima nominata nel titolo);
    se nomina tutte e due le squadre della partita va sotto quella di casa.
    Le notizie su altre squadre che nominano solo l'avversaria restano fuori.
    """
    out = {home: [], away: []}
    for e in sorted((e for e in entries if isinstance(e, dict)), key=lambda e: -float(e.get("t") or 0)):
        t = float(e.get("t") or 0)
        teams = e.get("tm") or []
        if not (start_ts < t <= end_ts) or not e.get("y") or not teams:
            continue
        if teams[0] in out:
            team = teams[0]
        elif home in teams and away in teams:
            team = home
        else:
            continue
        if len(out[team]) < per_team:
            out[team].append(e)
    return out


def news_line(e: dict, group_id, ref: datetime) -> str:
    """'19:48 📋 <a href=...>Titolo</a> — Testata'"""
    kinds = [t for t in (e.get("y") or []) if t in TYPE_TAGS]
    icon = TYPE_TAGS[kinds[0]][0] if kinds else "📰"
    title = _esc(e.get("tc") or e.get("ti") or "")
    link = post_link(group_id, e)
    if link:
        title = f'<a href="{_esc(link)}">{title}</a>'
    source = f" — {_esc(e['s'])}" if e.get("s") else ""
    return f"{when(float(e.get('t') or 0), ref)} {icon} {title}{source}"


def match_news(news_state: dict, home: str, away: str, labels: dict, now: datetime, hours: float,
               per_team: int, since_ts: float = 0) -> tuple:
    """
    Messaggio 📰 con le notizie delle due squadre (home, away: nomi del
    calendario, come nel registro del bot notizie) delle ultime 'hours' ore,
    al massimo per_team per squadra. labels: {squadra: intestazione} (di solito
    l'hashtag). since_ts: momento del messaggio 📰 precedente della stessa
    partita, se c'e' stato: arrivano solo le notizie uscite dopo.
    Ritorna (testo, momento della notizia piu' recente); ("", 0) se non ce n'e'.
    """
    entries = news_state.get("log") if isinstance(news_state, dict) else None
    if not isinstance(entries, list) or not entries:
        return "", 0
    group_id = ((news_state.get("telegram") or {}).get("group_id"))
    now_ts = now.timestamp()
    start = max(float(since_ts or 0), now_ts - hours * 3600)
    found = pick(entries, home, away, start, now_ts, per_team)
    if not any(found.values()):
        return "", 0
    if since_ts and since_ts > now_ts - hours * 3600:
        head = f"📰 <b>Nuove notizie</b> (dopo le {when(since_ts, now)})"
    else:
        head = f"📰 <b>Notizie delle ultime {hours:g} ore</b>"
    blocks = [head]
    for team in (home, away):
        if found[team]:
            lines = [f"<b>{labels.get(team) or _esc(team)}</b>"]
            lines += [news_line(e, group_id, now) for e in found[team]]
            blocks.append("\n".join(lines))
    latest = max(float(e.get("t") or 0) for items in found.values() for e in items)
    return "\n\n".join(blocks), latest
