# Bot Telegram – Notizie e quote sui 5 campionati

Sistema automatico (gratis) che manda su Telegram, in un gruppo con un argomento
per campionato:
- 🎙 le conferenze stampa e le parole degli allenatori
- 🚑 infortuni, squalifiche, assenze e rientri
- 📋 probabili formazioni, convocati, scelte di formazione
- 👔 esoneri, dimissioni e nuovi allenatori
- le notizie generali di tutte le squadre (niente calciomercato, serie minori,
  giovanili, altri sport, cronache e pagelle delle partite già giocate)
- 📈 gli avvisi sui movimenti delle quote (vedi «Bot quote» più sotto)

Copre: Serie A, Premier League, La Liga, Bundesliga, Ligue 1. Ogni notizia ha
la foto, il titolo e un breve riassunto in italiano, e il pulsante per aprire
l'articolo. Gira da solo nel cloud tramite GitHub Actions, ogni 5 minuti: non
serve tenere niente acceso.

## Notizie divise per campionato e hashtag delle squadre

- **Hashtag**: in fondo a ogni notizia ci sono gli hashtag delle squadre nominate
  nel titolo e, se la notizia è di un tipo riconosciuto, quello del tipo (es.
  `#Inter #Juventus · #Infortuni`). Toccandone uno, Telegram mostra tutte le
  notizie con quell'hashtag: `#Juventus` quelle della squadra (il tipo si legge
  subito nella prima riga di ognuna), `#Infortuni` tutti gli infortuni.
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

## Tipi di notizia, limiti e controlli

- **Tipo della notizia**: il bot lo riconosce dalle parole del titolo e lo
  scrive in alto, accanto al campionato (`🇮🇹 Serie A · 🚑 Infortuni`), e in
  fondo come hashtag. I tipi sono `🎙 #Conferenza` (conferenze stampa e
  dichiarazioni dell'allenatore), `🚑 #Infortuni` (infortuni, squalifiche,
  assenze, rientri), `📋 #Formazioni` (probabili formazioni, convocati,
  ballottaggi) e `👔 #Allenatore` (esoneri, dimissioni, nuovi tecnici). Una
  notizia può averne più d'uno; le notizie generali non ne hanno. Le parole
  che fanno scattare ogni tipo sono in `config.py` (sezione «TIPO DI
  NOTIZIA»), divise per lingua.
- **Limiti per squadra, a finestra mobile**: per ogni squadra passano al
  massimo 2 conferenze ogni 12 ore, 2 notizie su infortuni/formazioni/
  allenatore ogni 6 ore e 1 notizia generale ogni 8 ore. Se la squadra gioca
  entro 36 ore i limiti salgono (3, 3 e 2). La finestra scorre con l'orologio:
  non si azzera a mezzanotte, quindi niente raffica di notte e spazio libero
  la sera. Si cambiano in `config.py` (`TEAM_CAPS`, `MATCH_SOON_HOURS`).
- **Formazioni ufficiali**: escono un'ora prima della partita, quando le
  quote si muovono. Hanno un limite a parte (2 ogni 3 ore per squadra) e non
  vengono scartate come doppioni delle «probabili formazioni» uscite prima:
  passano sempre.
- **Riassunti (Groq, piano gratuito)**: ogni riassunto è una chiamata. Il bot
  conta chiamate e token; superate le 600 chiamate nelle ultime 24 ore
  (`GROQ_GENERAL_DAILY_BUDGET`) le notizie generali italiane escono con il
  testo del sito al posto del riassunto e quelle estere vengono saltate, così
  i riassunti che restano vanno a conferenze, infortuni e formazioni.
- **Foto**: se Telegram non riesce a scaricare la foto dal sito, la scarica il
  bot e gliela carica; solo se non ci riesce nemmeno lui la notizia esce senza
  foto.
- **Pagine senza notizia**: titoli fatti solo dei nomi delle squadre, pagine
  di statistiche, promozioni di scommesse e cronaca delle città che hanno il
  nome di una squadra vengono scartati (`EXCLUDE_TITLE_WORDS` in `config.py`).
- **Avvisi di salute** (nella chat privata col bot, al massimo uno al giorno
  per tipo): il bot è rimasto fermo più di 45 minuti; Google News non risponde
  da un'ora; più di 25 riassunti falliti in un giorno. Si spengono con
  `HEALTH_NOTICES = False` in `config.py`.
- **Registro**: le notizie inviate nelle ultime 48 ore (squadre, tipo, titolo,
  fonte, posizione nel gruppo) e i contatori del giorno stanno in
  `state/state.json` (`log`, `stats`, `stats_hist`).

## Bot quote (argomento «📈 Quote» del gruppo)

Segue le quote dei 5 campionati e delle coppe europee (Champions, Europa e
Conference League) con OddsPapi (piano gratuito, 250 chiamate al mese, secret
`ODDSPAPI_API_KEY`), con le quote di **Pinnacle** (il riferimento).

> Dal 20/11/2026 OddsPapi dà lo storico gratis **solo per le partite finite**
> (per quelle da giocare risponde «Restricted access to historical odds»).
> Per questo il bot legge le quote di **adesso** (una chiamata per orario
> d'inizio) e si costruisce lo storico da sé in `state/quote_live.json`: ogni
> lettura (apertura, ogni orario, riletture delle coppe) lascia i prezzi
> cambiati con la loro ora. Lo storico gratis delle partite finite serve
> ancora per «rivedi» ed «esempio».

- **Apertura**: per ogni partita le quote delle 15:00 di **due giorni prima**
  (mercoledì per il venerdì, giovedì per il sabato, venerdì per la domenica,
  sabato per il lunedì; coppe allo stesso modo), così tutte hanno la stessa
  finestra (45-54 ore). Prima del 21/11/2026 era il venerdì alle 15 per tutto
  il weekend: sulle partite del 6-8 novembre per sabato e domenica cambiava
  poco, ma il venerdì sera aveva solo 6 ore di finestra (movimento mediano di
  Pinnacle 0,2 punti contro 2,7 con 48 ore). Alle 15 il bot legge le quote di
  Pinnacle (una chiamata per i 5 campionati, una per le coppe; se c'è una
  lettura dei 40 minuti da meno di 45 minuti vale quella) e a inizio turno lo
  dice con un messaggio breve. Una partita letta per la prima volta dopo
  l'apertura parte dalla sua prima lettura.
- **Coppe europee** (⭐ Champions, 🟠 Europa e 🟢 Conference League): le
  partite arrivano dall'elenco OddsPapi, letto ogni **domenica alle 15** (scopre
  le partite della settimana ed è l'apertura del martedì), poi lunedì e
  martedì alle 15 (apertura di mercoledì e giovedì). Champions tutte le
  partite; Europa e Conference (dal 21/11/2026) solo quelle con almeno una
  squadra dei 5 campionati (`CUPS_TOP5_ONLY`), come tutte le coppe a luglio e
  agosto (`CUPS_TOP5_MONTHS`). Le squadre dei 5 campionati hanno gli stessi nomi
  italiani e hashtag del campionato: il bot li impara dalle partite di
  campionato, senza chiamate. (La rilettura delle 11 è spenta dal 21/11/2026:
  le letture delle 15 e dei 40 minuti aggiornano già l'elenco.)
- **Riepilogo delle 19**: spento dal 14/11/2026 (`RIEPILOGO_AUTO` in cima a
  `monitor_quote.py`). A mano resta: «Prova bot quote» → riepilogo.
- **Forza del segnale (1-10)** = 2 × ampiezza (1-5: punti di probabilità
  senza margine misurati sulla linea dell'apertura, così un cambio di linea
  "di confine" non conta come un movimento grande; asiatico 3 / 4,5 / 6 / 8 /
  10 punti) + book (+1 con il solo Pinnacle, come i 3 book d'accordo di
  prima, `LIVE_ACC`; sui segnali forti il confronto vero con Sbobet e
  Singbet) + tenuta (ha
  tenuto 0, tornato un po' indietro −1, rientrato −2) + altro mercato che dice
  la stessa cosa (asiatico e 1X2, linea gol e GG o gol di squadra: +1). Da 7
  forte, 4-6 medio (da farsi domande), sotto 4 rumore. Le soglie sono in cima
  a `monitor_quote.py` (`FORZA_MIN_AVVISO`, `FORZA_FORTE`, `LEV_SIDE`,
  `LEV_GOL`, `LEV_GG`).
- **A ridosso**: 40 minuti prima di ogni orario d'inizio (formazioni già
  uscite) legge le quote di adesso di Pinnacle di tutte le partite di
  quell'orario con **una chiamata** (i 5 campionati insieme, o le 3 coppe
  insieme) e confronta adesso con l'apertura.
  Arriva un **avviso** solo se un movimento ha forza 4/10 o più; per
  🟠 Europa e 🟢 Conference League, nelle sere in cui insieme hanno più di 8
  partite, **solo da 6/10** (`CUP_BUSY_MATCHES`, `FORZA_MIN_BUSY`). Gli avvisi
  della stessa ora partono **dal più forte**. Il
  messaggio ha, in quest'ordine: il segnale principale con la forza; una
  **tabella unica**
  apertura/adesso (Pinnacle) con 1X2, asiatico, linea gol, Over 2,5, GG e,
  sotto, **gol attesi** e **corner attesi** di ogni squadra (quanti se ne
  aspetta il mercato: ricavati da linea e quote dei gol e dei corner di
  squadra; se i gol di squadra non sono quotati, da linea gol e 1X2; * = da un
  altro book) e i tiri in porta se quotati;
  il **📊 grafico** della direzione della partita, cioè la quota della
  favorita (o della squadra su cui si muove il mercato) dall'apertura ad
  adesso in 22 barre a tempi uguali (barra alta = quota alta; un punto per
  ogni lettura del bot), con sotto il **🔎 Perché** (vedi sotto; se manca,
  la riga **⏱** quando si è mossa: di colpo o piano piano, con il pezzo più
  grosso e le quote, e cosa è successo dopo le formazioni) e **↩️** se è
  tornata indietro di almeno un quinto (fin dove era arrivata e quando:
  forza −1, oltre metà −2); **Si muovono anche** (linea gol, GG, gol e corner
  attesi che si sono mossi, senza grafico); la **💡 lettura**, il colore da
  mettere nella riga «Mercato» della Direzione generale e il pronostico con la
  quota giusta.
- **🔎 Perché (dal 27/11/2026)**: subito sotto le barre del grafico, in una
  riga: come e quando si è mossa la quota (la scrive il bot dai dati del
  grafico, es. «Salita soprattutto oggi pomeriggio») e il possibile motivo:
  «Possibile motivo: Miranda non ha recuperato (notizia di ieri pomeriggio)».
  La notizia la sceglie Groq (gratis, lo stesso `GROQ_API_KEY` del bot
  notizie) tra quelle delle due squadre delle 48 ore prima (conferenze,
  infortuni, formazioni, allenatore: registro del bot notizie, nessuna
  chiamata OddsPapi), solo se va nello stesso verso del movimento, e la
  riassume in poche parole; tra parentesi quando è uscita, così si vede se è
  arrivata prima del movimento. Se nessuna lo spiega: «Nessuna notizia lo
  spiega: probabile flusso di giocate» (o «guarda le formazioni» se si è
  mossa dopo le formazioni). È un'ipotesi, non una certezza. Con il 🔎 la 💡
  lettura non ripete le domande sul perché. Se Groq non risponde (o manca la
  chiave) al suo posto resta la riga ⏱. Al massimo 10 chiamate per giro. Si
  regola in cima a `monitor_quote.py` (`PERCHE_ON`, `PERCHE_ORE`,
  `PERCHE_PER_SQUADRA`).
- **✅ Niente da segnalare (dal 23/11/2026)**: dopo gli avvisi di ogni orario,
  un messaggio **senza suono** con le partite di quell'orario che non hanno
  avuto l'avviso, una riga ciascuna dalla più mossa: «quote quasi ferme»
  oppure la forza e il mercato che si è mosso (es. «forza 2/10 sulla linea
  gol»); l'ora tra parentesi se diversa da quella del titolo. Se nello stesso
  orario c'erano avvisi o partite non controllate il titolo è «Le altre delle
  …». Usa la stessa lettura dei 40 minuti: **nessuna chiamata in più**. Se le
  partite sono tutte con l'avviso non arriva. Si spegne in cima a
  `monitor_quote.py` (`NIENTE_DA_SEGNALARE`). Nel controllo a mano diventa
  «🔎 Controllo a mano · …: niente da segnalare».
- **📰 Notizie sotto l'avviso: SPENTE dal 27/11/2026** (rendevano tutto più
  pesante da vedere; le notizie adesso servono al 🔎 Perché). Per riaccenderle:
  `NOTIZIE_SOTTO_AVVISO = True`. Com'erano: subito dopo ogni avviso (40 minuti prima e
  ultimi minuti), in risposta, arrivava un messaggio con le notizie delle due
  squadre delle ultime 36 ore: conferenze stampa, infortuni, formazioni e
  allenatore (non le generali), al massimo 4 per squadra, dalla più recente,
  con ora e testata. Toccando il titolo si apre la notizia nell'argomento del
  campionato. Le prende dal registro del bot notizie (`state/state.json`,
  `log`), quindi nessuna chiamata in più. Se non ce ne sono non arriva niente;
  dopo un messaggio degli ultimi minuti arrivano solo le notizie nuove. Si
  regola in cima a `monitor_quote.py` (`NOTIZIE_SOTTO_AVVISO`, `NOTIZIE_ORE`,
  `NOTIZIE_PER_SQUADRA`); il codice è in `notizie_partita.py`.
- **Segnali forti (da 7/10): confronto con Sbobet e Singbet**. Le loro quote
  si leggono a inizio turno (base) e, a 40 minuti, solo per le partite con un
  segnale forte: una chiamata per partita (`/odds`), o due per competizione se
  i forti sono più di due. «3 book su 3» = tutti d'accordo; ogni book che non
  conferma toglie un punto (come prima: un forte può scendere a 5-6). Un book
  senza quote di partenza non conta. Sono chiamate «in più»: saltano se il
  mese è stretto. Sulle 48 partite del 6-8 novembre, quando Pinnacle si
  muoveva, Sbobet e Singbet andavano nella stessa direzione 40 volte su 44.
- **🔁 Altri book (secondo parere, dal 22/11/2026)**: con The Odds API (piano
  gratuito, 500 crediti al mese, secret `ODDS_API_KEY`) il bot legge anche
  Betfair Exchange, Matchbook, Marathonbet e 1xBet sui 5 campionati: la base
  all'apertura (1X2 e linea gol, 1 credito per campionato e per mercato: fino a
  10 book costano come uno) e, a 40 minuti, una lettura solo per i campionati
  con un avviso. Sotto il segnale una riga 🔁: quanti si sono mossi nello stesso
  verso su segno e linea gol; per il GG (letto partita per partita, 1 credito,
  solo per gli avvisi con un segnale GG) quanti sono già alle quote di adesso
  di Pinnacle. Solo informazione: la forza non cambia. Betfair dà solo l'1X2,
  il GG lo danno 1xBet e Matchbook. Circa 300-360 crediti al mese; ne tiene da
  parte 6 per ogni giorno che manca a fine mese. Senza la chiave non fa niente.
  Prova: «Prova bot quote» → `altribook` (circa 16 crediti, nel registro).
- **Ultimi minuti**: da 12 a 3 minuti prima del fischio, **solo se a 40
  minuti è partito un avviso forte** (7/10 o più) e se le chiamate del mese lo
  permettono, il bot rilegge le quote (una chiamata) e scrive: ⚠️
  **ribaltone**, cioè il segnale forte dall'apertura non arriva più a 4/10,
  oppure 🚨 un altro movimento da 7/10 in su nato dopo il controllo dei 40
  minuti. Tabellina «ora del controllo / adesso», come sta dall'apertura e il
  colore aggiornato per la riga «Mercato».
- **Non controllate**: se una partita non è nell'elenco di OddsPapi, se
  Pinnacle adesso non la quota, se manca una quota di partenza (letta per la
  prima volta a 40 minuti) o se le quote non si riescono a leggere entro 12
  minuti dal fischio (al massimo 3 tentativi), il bot lo scrive (prima del ✅
  delle altre). Così ogni partita controllata o no ha sempre un messaggio.
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
- **Consumo**: ogni lettura delle quote di adesso è una chiamata delle 250:
  circa 22 orari d'inizio per weekend di campionato, 6-7 per settimana di
  coppe, le aperture delle 15 (3-4 a settimana), Sbobet e Singbet (2 a inizio
  turno, 1 per segnale forte) e gli ultimi minuti dei segnali forti, più i
  nomi delle squadre nuove e l'elenco dei mercati: **circa 200-210 chiamate al
  mese**. Le chiamate «in più» (Sbobet e Singbet, ultimi minuti) partono solo
  se a fine mese ne restano almeno 6 per ogni giorno che manca
  (`OPTIONAL_PER_DAY`): le letture dei 40 minuti hanno sempre la precedenza.
  Togliere partite di Europa e Conference fa risparmiare poco: si paga per
  orario d'inizio, non per partita. Il piano a pagamento con i 3 book
  (Pinnacle, Sbobet, Singbet, calcio) costa 95 $ al mese (21/11/2026). Il contatore si allinea a quello
  dell'account e non fa mai superare il limite.
- **Come parte**: lo lancia il giro ogni 5 minuti del bot notizie (passo «Bot
  quote» in `monitor-news.yml`); quasi sempre esce subito. Ogni giro lavora al
  massimo 3 minuti: se le partite sono tante, finisce al giro dopo, senza
  doppioni. Prove a mano: Actions → «Prova bot quote» → Run workflow
  (test = prova completa, ora = controllo subito delle prossime partite,
  apertura = aggiorna subito l'elenco, riepilogo = riepilogo subito di domani,
  rivedi = rilegge le partite già giocate negli ultimi 8 giorni come 40 minuti
  prima: con «partita» vuoto il conto forti/medi/rumore e le 3 più forti, con
  una squadra il messaggio di quella partita; perche = prova del 🔎 Perché:
  l'avviso come sarebbe adesso, con le quote dell'ultima lettura del bot
  (nessuna chiamata OddsPapi, una chiamata Groq per partita), per la prossima
  partita della squadra scritta in «partita» o, se vuoto, per le 3 partite più
  mosse dei prossimi 3 giorni; esempio = prova grafica nel
  gruppo con quote vere, la legenda, tre avvisi (un calo che tiene, uno
  tornato indietro e uno solo sui gol), un esempio degli ultimi minuti e la
  riga «Non controllate»; con «partita» = tutto anche apertura
  delle coppe e riepiloghi). «partita» vale anche per test,
  ora e riepilogo, e accetta una competizione: SA, PL, PD, BL1, FL1, CL, EL,
  ECL o «coppe» (con rivedi fa il conto di quella competizione).
- Codice in `monitor_quote.py` (orari, soglie e book in cima al file), stato in
  `state/quote_state.json`, quote lette in `state/quote_live.json`, file per i
  Pace Index in `state/mercato.csv`.

### Bot coppe e Serie B (il bot di tuo fratello)

Stesso codice, profilo diverso (`QUOTE_PROFILE=coppe`, dal 22/11/2026). Gira nel
repository di tuo fratello, con il suo account OddsPapi (la sua chiave nei suoi
segreti) e un bot Telegram suo, nello stesso gruppo, in un argomento suo
(«🏆 Quote coppe e B»). Il modello del flusso da mettere nel suo repository è
`fratello/quote-coppe.yml`: a ogni giro prende il codice da qui, salva lo stato
nel suo repository (`state/`) e una volta al giorno una copia di sicurezza di
DIEZ-News (`copia-diez/`, tutto tranne il registro delle notizie).

- **Partite**: ⭐ Champions, 🟠 Europa e 🟢 Conference League (come qui: Europa e
  Conference solo con squadre dei 5 campionati) e 🇮🇹 **Serie B**, tutte dall'elenco
  OddsPapi e lette insieme con una chiamata. L'elenco si legge sempre la domenica
  e il mercoledì alle 15 (la Serie B del fine settimana).
- **Dove non ci sono i fogli il mercato pesa di più**: avviso da **3/10**,
  confronto con Sbobet e Singbet su **ogni avviso**, e a 40 minuti il
  🕒 **quadro dell'orario**, un messaggio con tutte le partite di quell'orario e le
  quote di adesso con le frecce, anche sotto la soglia (non costa chiamate).
- Nomi delle squadre, squadre dei 5 campionati e mercati li prende senza chiamate
  dallo stato di questo bot (`state/quote_state.json`, solo letto).
- Consumo stimato sul suo account: circa 200-230 chiamate al mese su 250.
- Prova da qui con la tua chiave: «Prova bot quote» con `profilo` = `coppe`
  (sempre muta, stato in una cartella temporanea: non tocca niente).
- Le soglie sono in cima a `monitor_quote.py` (`FORZA_MIN_AVVISO`, `CONFIRM_FROM`,
  `QUADRO_ORARIO`, `CUP_DISCOVERY_DAYS`, `TOPIC_NAME`), divise per profilo.

---

## Come è montato

1. **Bot Telegram**: creato con @BotFather. Il token è nel secret
   `TELEGRAM_BOT_TOKEN`; `TELEGRAM_CHAT_ID` è l'id della chat privata col bot.
2. **Chiavi** (GitHub → Settings → Secrets and variables → Actions). Stanno
   solo lì, mai nel codice:

   | Nome | A cosa serve |
   |---|---|
   | `TELEGRAM_BOT_TOKEN` | il bot Telegram |
   | `TELEGRAM_CHAT_ID` | la chat privata col bot (avvisi di servizio) |
   | `GROQ_API_KEY` | riassunti in italiano (piano gratuito); anche il 🔎 Perché degli avvisi quote |
   | `FOOTBALL_DATA_API_KEY` | calendario e squadre (football-data.org, piano gratuito) |
   | `ODDSPAPI_API_KEY` | quote (OddsPapi, piano gratuito: 250 chiamate al mese) |
   | `ODDS_API_KEY` | altri book, secondo parere (The Odds API, piano gratuito: 500 crediti al mese) |
   | `TELEGRAM_GROUP_ID` | facoltativo: il bot trova il gruppo da solo |

3. **Workflow** (tab Actions del repository):
   - «Monitor notizie squadre»: il giro ogni 5 minuti (prima le quote, poi le
     notizie).
   - «Aggiorna calendario partite e squadre»: 4 volte al giorno.
   - «Prova bot quote»: solo a mano (con `profilo` = `coppe` prova il bot di
     tuo fratello, sempre muta).
   - Il bot di tuo fratello ha il suo flusso nel suo repository (modello in
     `fratello/quote-coppe.yml`, vedi «Bot coppe e Serie B»).
4. **Chi fa partire il giro ogni 5 minuti**: cron-job.org (gratis), con una
   richiesta `POST` a
   `https://api.github.com/repos/10-DIEZ/DIEZ-News/actions/workflows/monitor-news.yml/dispatches`,
   intestazioni `Authorization: Bearer <token GitHub>` e
   `Accept: application/vnd.github+json`, corpo `{"ref":"main"}`. Il token è un
   «fine-grained token» di GitHub con il permesso *Actions: read and write* su
   questo repository. **Se ha una scadenza, quel giorno il giro si ferma**
   (nella cronologia di cron-job.org compare l'errore 401): va rifatto il token
   e incollato di nuovo. L'orario interno di GitHub resta come riserva, ma è
   irregolare (anche ore di ritardo).

## Personalizzazioni facili

Tutto in `config.py`:
- limiti per squadra (`TEAM_CAPS`), età massima delle notizie
  (`NEWS_MAX_AGE_HOURS`), massimo di messaggi per giro (`MAX_MESSAGES_PER_RUN`)
- parole che riconoscono i tipi di notizia e parole escluse
- calciomercato: escluso; per riaverlo `INCLUDE_TRANSFER_NEWS = True`
- nomi, alias e hashtag delle squadre; nomi e colori degli argomenti del gruppo

## Limiti da conoscere

- Le notizie arrivano dai feed RSS delle testate e da ricerche su Google News:
  può scappare qualche articolo poco pertinente o un tipo sbagliato. Si
  corregge aggiungendo o togliendo parole nelle liste di `config.py`.
- Google News a volte blocca le ricerche per qualche giro: il bot se ne
  accorge dopo 6 ricerche fallite, salta il resto del giro e riprova al
  successivo. Le notizie dei feed diretti continuano ad arrivare.
- Piani gratuiti: Groq (riassunti) è l'unico vicino al tetto giornaliero nei
  giorni pieni, per questo c'è la soglia delle 600 chiamate; football-data,
  Telegram, cron-job.org e GitHub Actions (repository pubblico) hanno margine
  ampio; OddsPapi usa circa 200-210 chiamate al mese su 250 (vedi «Consumo»
  nella parte del bot quote).
