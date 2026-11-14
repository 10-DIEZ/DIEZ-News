# Bot Telegram – Notizie sui 5 campionati

Sistema automatico (gratis) che ti manda su Telegram:
- 🩹 Infortuni e 🟥 squalifiche (dati ufficiali, via API-Football)
- 👔 Possibili cambi allenatore (esoneri, dimissioni, nuovi tecnici)
- 🔄 Turnover / probabili formazioni / titolari in dubbio

Copre: Serie A, Premier League, La Liga, Bundesliga, Ligue 1.

Gira da solo nel cloud tramite GitHub Actions, non serve tenere niente acceso.

## Notizie divise per campionato e hashtag delle squadre

- **Hashtag**: in fondo a ogni notizia ci sono gli hashtag delle squadre nominate
  nel titolo (es. `#Inter #Juventus`). Toccandone uno, Telegram mostra tutte le
  notizie di quella squadra.
- **Gruppo con Argomenti**: crea un gruppo Telegram con dentro solo te e il bot,
  attiva gli *Argomenti* nelle impostazioni del gruppo e nomina il bot
  amministratore. Al giro successivo (entro 5 minuti) il bot trova il gruppo da
  solo, crea un argomento per campionato e da lì in poi manda ogni notizia
  nell'argomento del suo campionato. Non serve cambiare nulla su GitHub e non
  bisogna creare gli argomenti a mano.
- Finché il gruppo non è pronto le notizie arrivano nella chat privata col bot;
  se manca qualcosa (Argomenti non attivi, bot non amministratore) il bot te lo
  scrive in privato, una volta sola. Se un argomento viene cancellato lo ricrea;
  se il bot viene tolto dal gruppo, le notizie tornano nella chat privata.
- Nomi e colori degli argomenti, hashtag delle squadre e pause tra un invio e
  l'altro si cambiano in `config.py` (sezioni "GRUPPO CON ARGOMENTI" e
  "HASHTAG DELLE SQUADRE"). La logica del gruppo è in `telegram_group.py`.

## Bot quote (argomento «📈 Quote» del gruppo)

Segue le quote dei 5 campionati e delle coppe europee (Champions, Europa e
Conference League) con OddsPapi (piano gratuito, 250 chiamate al mese, secret
`ODDSPAPI_API_KEY`), sui book Pinnacle (il riferimento), Sbobet e Singbet.

- **Apertura**: le quote del venerdì alle 15:00 per le partite del weekend
  (venerdì-lunedì), del martedì alle 15:00 per i turni infrasettimanali: lo
  stesso momento delle quote d'apertura usate nello studio del foglio Mercato
  del Pace Index. Il bot le legge dallo **storico** delle quote, quindi non
  deve fotografarle: a quell'ora aggiorna solo l'elenco delle partite e lo dice
  con un messaggio breve.
- **Coppe europee** (⭐ Champions, 🟠 Europa e 🟢 Conference League): le
  partite arrivano dall'elenco OddsPapi, letto il **lunedì alle 15** con una
  chiamata a parte; il lunedì alle 15 è anche la loro apertura (dopo il turno
  di campionato). Tutte le partite; a luglio e agosto (preliminari, anche
  80-90 partite il giovedì) solo quelle con almeno una squadra dei 5
  campionati (`CUPS_ONLY_TOP5` e `CUPS_TOP5_MONTHS` in cima a
  `monitor_quote.py`). Le squadre dei 5 campionati hanno gli stessi nomi
  italiani e hashtag del campionato: il bot li impara dalle partite di
  campionato, senza chiamate. L'elenco viene **riletto alle 11** nei giorni con
  partite di coppa nelle 36 ore dopo (martedì, mercoledì, giovedì: una
  chiamata, nessun messaggio): così entrano le partite che Pinnacle pubblica
  dopo il lunedì e gli orari cambiati.
- **Riepilogo delle 19**: spento dal 14/11/2026 (`RIEPILOGO_AUTO` in cima a
  `monitor_quote.py`). A mano resta: «Prova bot quote» → riepilogo.
- **Forza del segnale (1-10)** = 2 × ampiezza (1-5: punti di probabilità
  senza margine misurati sulla linea dell'apertura, così un cambio di linea
  "di confine" non conta come un movimento grande; asiatico 3 / 4,5 / 6 / 8 /
  10 punti) + book (3 su 3 d'accordo +1, 2 su 3 0, uno solo −1) + tenuta (ha
  tenuto 0, tornato un po' indietro −1, rientrato −2) + altro mercato che dice
  la stessa cosa (asiatico e 1X2, linea gol e GG o gol di squadra: +1). Da 7
  forte, 4-6 medio (da farsi domande), sotto 4 rumore. Le soglie sono in cima
  a `monitor_quote.py` (`FORZA_MIN_AVVISO`, `FORZA_FORTE`, `LEV_SIDE`,
  `LEV_GOL`, `LEV_GG`).
- **A ridosso**: 40 minuti prima di ogni orario d'inizio (formazioni già
  uscite) legge lo storico di ogni partita e confronta adesso con l'apertura.
  Arriva un messaggio **solo** se un movimento ha forza 4/10 o più; per
  🟠 Europa e 🟢 Conference League, nelle sere in cui insieme hanno più di 8
  partite, **solo da 6/10** (`CUP_BUSY_MATCHES`, `FORZA_MIN_BUSY`). Gli avvisi
  della stessa ora partono **dal più forte**. Il
  messaggio ha, in quest'ordine: il segnale principale con la forza e quanti
  book sono d'accordo (⚠️ se manca Pinnacle); una **tabella unica**
  apertura/adesso (Pinnacle) con 1X2, asiatico, linea gol, Over 2,5, GG e,
  sotto, **gol attesi** e **corner attesi** di ogni squadra (quanti se ne
  aspetta il mercato: ricavati da linea e quote dei gol e dei corner di
  squadra; se i gol di squadra non sono quotati, da linea gol e 1X2; * = da un
  altro book) e i tiri in porta se quotati;
  il **📊 grafico** della direzione della partita, cioè la quota della
  favorita (o della squadra su cui si muove il mercato) dall'apertura ad
  adesso in 22 barre a tempi uguali (barra alta = quota alta), con sotto **⏱**
  quando si è mossa (di colpo o piano piano, con il pezzo più grosso e le
  quote), cosa è successo dopo le formazioni e **↩️** se è tornata indietro
  di almeno un quinto (fin dove era arrivata e quando: forza −1, oltre metà
  −2); **Si muovono anche** (linea gol, GG, gol e corner attesi che si sono
  mossi, senza grafico); la **💡 lettura**, il colore da mettere
  nella riga «Mercato» della Direzione generale e il pronostico con la quota
  giusta.
- **Ultimi minuti**: da 12 a 3 minuti prima del fischio il bot rilegge le
  partite e scrive **solo per i casi forti**: 🚨 un movimento da 7/10 in su
  nato dopo il controllo dei 40 minuti (misurato solo su quel tratto) oppure
  ⚠️ **ribaltone**, cioè un segnale forte già mandato che dall'apertura non
  arriva più a 4/10. Tabellina «ora del controllo / adesso», come sta
  dall'apertura e il colore aggiornato per la riga «Mercato».
- **Non controllate**: se una partita non è nell'elenco di OddsPapi, o le sue
  quote non si riescono a leggere entro 12 minuti dal fischio, il bot lo
  scrive. Così il silenzio vuol dire davvero «nessun segnale».
- **File per i Pace Index**: `state/mercato.csv`, una riga per partita
  controllata (separatore `;`, numeri con il punto): competizione, data, ora,
  squadre, quando (40 minuti, 10 minuti, a mano), forza, avviso SI/NO, colore
  per la riga «Mercato» e a quale squadra si riferisce, verso e forza di
  segno / gol / GG, quote 1X2, asiatico e linea gol di apertura e di adesso,
  gol e corner attesi di apertura e di adesso. Tiene le partite degli ultimi
  10 giorni. I file Excel lo leggono con Power Query.
- **Pronostico dalle quote**: calo forte → segno secco, calo → doppia chance,
  quota della favorita in salita → doppia chance contro di lei e la sfavorita
  che segna (contro quota), linea gol su/giù → Over/Under, mercato Goal mosso
  → GG/NG. Il bot manda nel gruppo la legenda completa la prima volta e quando
  cambia.
- **Numeri per tarare**: ogni partita controllata lascia la forza e i suoi
  pezzi in `state/quote_state.json` (`stats`).
- **Consumo**: lo storico delle quote non conta nelle 250 chiamate (verificato
  sul contatore dell'account); contano solo gli aggiornamenti dell'elenco
  partite (venerdì i campionati, lunedì le coppe, il martedì se c'è il turno
  infrasettimanale, le riletture delle coppe: fino a 3 per settimana di
  coppe), i nomi delle squadre nuove e l'elenco dei mercati (una
  volta al mese): circa 25-40 chiamate al mese. Il contatore si allinea a
  quello dell'account e non fa mai superare il limite.
- **Come parte**: lo lancia il giro ogni 5 minuti del bot notizie (passo «Bot
  quote» in `monitor-news.yml`); quasi sempre esce subito. Ogni giro lavora al
  massimo 3 minuti: se le partite sono tante, finisce al giro dopo, senza
  doppioni. Prove a mano: Actions → «Prova bot quote» → Run workflow
  (test = prova completa, ora = controllo subito delle prossime partite,
  apertura = aggiorna subito l'elenco, riepilogo = riepilogo subito di domani,
  rivedi = rilegge le partite già giocate negli ultimi 8 giorni come 40 minuti
  prima: con «partita» vuoto il conto forti/medi/rumore e le 3 più forti, con
  una squadra il messaggio di quella partita; esempio = prova grafica nel
  gruppo con quote vere, la legenda, tre avvisi (un calo che tiene, uno
  tornato indietro e uno solo sui gol), un esempio degli ultimi minuti e la
  riga «Non controllate»; con «partita» = tutto anche apertura
  delle coppe e riepiloghi). «partita» vale anche per test,
  ora e riepilogo, e accetta una competizione: SA, PL, PD, BL1, FL1, CL, EL,
  ECL o «coppe» (con rivedi fa il conto di quella competizione).
- Codice in `monitor_quote.py` (orari, soglie e book in cima al file), stato in
  `state/quote_state.json`, file per i Pace Index in `state/mercato.csv`.

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
