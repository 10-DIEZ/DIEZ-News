# Bot Telegram – Notizie sui 5 campionati

Sistema automatico (gratis) che ti manda su Telegram:
- 🩹 Infortuni e 🟥 squalifiche (dati ufficiali, via API-Football)
- 👔 Possibili cambi allenatore (esoneri, dimissioni, nuovi tecnici)
- 🔄 Turnover / probabili formazioni / titolari in dubbio

Copre: Serie A, Premier League, La Liga, Bundesliga, Ligue 1.

Gira da solo nel cloud tramite GitHub Actions, non serve tenere niente acceso.

---

## Passo 1 — Crea il bot Telegram

1. Su Telegram cerca **@BotFather** e avvia una chat.
2. Scrivi `/newbot`, dai un nome e uno username al bot (deve finire per "bot", es. `calcio_alert_bot`).
3. BotFather ti darà un **token** tipo `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`. Salvalo.
4. Scrivi un messaggio qualsiasi al tuo nuovo bot (es. "ciao"), altrimenti non potrà scriverti.
5. Per sapere il tuo **chat_id**, apri questo link nel browser sostituendo `<TOKEN>` con il tuo token:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   Cerca nel risultato JSON il campo `"chat":{"id": ...}` — quel numero è il tuo `TELEGRAM_CHAT_ID`.

## Passo 2 — Crea l'account API-Football (gratis)

1. Vai su https://www.api-football.com/ (o https://dashboard.api-football.com/register) e registrati.
2. Nella tua dashboard trovi la tua **API Key** (piano gratuito: 100 richieste/giorno, più che sufficiente per questo sistema).

## Passo 3 — Crea il repository GitHub

1. Crea un account su https://github.com se non ce l'hai già.
2. Crea un nuovo repository (può essere privato), es. `calcio-alert-bot`.
3. Carica tutti i file di questa cartella nel repository (puoi trascinarli dall'interfaccia web di GitHub, oppure con git).

## Passo 4 — Inserisci le chiavi segrete

Nel repository su GitHub: **Settings → Secrets and variables → Actions → New repository secret**.
Crea questi 3 secret:

| Nome | Valore |
|---|---|
| `TELEGRAM_BOT_TOKEN` | il token avuto da BotFather |
| `TELEGRAM_CHAT_ID` | il chat_id trovato al Passo 1 |
| `API_FOOTBALL_KEY` | la API key di API-Football |

## Passo 5 — Attiva e testa

1. Vai nella tab **Actions** del repository: dovresti vedere i due workflow ("Monitor infortuni e squalifiche" e "Monitor notizie").
2. Selezionane uno e clicca **Run workflow** per testarlo subito (non serve aspettare l'orario schedulato).
3. Se tutto è configurato bene, riceverai i messaggi su Telegram entro un minuto (se ci sono novità da segnalare).

Da qui in poi il sistema gira da solo:
- infortuni/squalifiche: controllo 2 volte al giorno
- notizie allenatori/turnover: controllo ogni 3 ore

---

## Personalizzazioni facili

Apri `config.py` per modificare:
- `SEASON` — se cambia la stagione (es. da 2026 a 2027)
- `COACH_CHANGE_KEYWORDS` / `LINEUP_RUMOR_KEYWORDS` — parole chiave usate per filtrare le notizie
- gli orari dei controlli si cambiano nei file `.github/workflows/*.yml` (campo `cron`, orari in UTC)

## Limiti da conoscere

- Le notizie su "turnover/probabili formazioni" arrivano da ricerche Google News: potranno esserci **falsi positivi** (articoli non del tutto pertinenti) o qualche doppione nei titoli — è normale, il sistema impara a filtrare meglio nel tempo se affiniamo le parole chiave.
- Il piano gratuito API-Football ha 100 richieste/giorno: con 2 esecuzioni al giorno per 5 campionati (10 chiamate) siamo ben sotto il limite, ma se in futuro aggiungi controlli più frequenti tienilo a mente.
- Se un giorno l'API-Football cambia struttura di risposta, lo script `monitor_structured.py` andrà aggiornato di conseguenza — segnalamelo e lo sistemiamo.
