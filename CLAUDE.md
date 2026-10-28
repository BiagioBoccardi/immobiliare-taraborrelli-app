# CLAUDE.md — App Immobiliare Taraborrelli

## 1. Il progetto

App mobile (Android prima, iOS dopo) per l'agenzia **Immobiliare Taraborrelli** (Chieti e Chieti Scalo), con pannello di amministrazione web e pagina web pubblica di valutazione.

**Obiettivo di business:** acquisire il maggior numero possibile di nuovi incarichi di vendita e affitto. Il destinatario principale è il **proprietario** che vuole vendere o affittare; chi cerca casa viene dopo.

**Metriche che contano:** nuovi proprietari che contattano l'agenzia, appuntamenti fissati, valutazioni effettuate, incarichi acquisiti. Il numero di download non è un indicatore di successo.

Quando una scelta di design è ambigua, vince l'opzione che rende più facile a un proprietario lasciare i propri contatti.

## 2. Stack

| Area | Tecnologia |
|---|---|
| Backend | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic |
| Database | PostgreSQL, un database per servizio |
| Cache e code | Redis (cache, rate limit), RabbitMQ (eventi tra servizi) |
| File e immagini | Storage compatibile S3 (MinIO in locale) |
| App mobile | React Native con Expo, TypeScript, Expo Router, TanStack Query |
| Admin e pagina pubblica | React, Vite, TypeScript |
| Gateway | Traefik |
| Container | Docker, Docker Compose in locale |
| Versionamento | Git, repository unico (monorepo) su GitHub |
| CI | GitHub Actions |
| Tooling Python | uv, ruff, mypy, pytest (con pytest-asyncio, pytest-cov, httpx, testcontainers) |
| Tooling TypeScript | npm workspaces, ESLint, Prettier, Jest, React Native Testing Library |

Non introdurre nuove dipendenze o tecnologie senza chiederlo prima.

## 3. Architettura a microservizi

I client (app, admin, pagina pubblica) parlano solo con il gateway. Ogni servizio possiede i propri dati e nessun servizio legge il database di un altro.

| Servizio | Responsabilità |
|---|---|
| `gateway` | Routing, TLS, rate limiting, CORS |
| `auth` | Utenti, staff dell'agenzia, login, JWT, ruoli, registro dei consensi privacy |
| `property` | Catalogo immobili, ricerca con filtri, mappa, media, immobili venduti, affitti per studenti e lavoratori |
| `lead` | Richieste di valutazione, moduli "voglio vendere" e "voglio affittare", richieste di informazioni, prenotazione visite e appuntamenti, CRM leggero (stato, priorità, promemoria di ricontatto) |
| `engagement` | Preferiti, ricerche salvate, confronto immobili, preferenze di notifica |
| `notification` | Invio push (Expo Push), email, notifiche allo staff |
| `assistant` | Assistente virtuale sul catalogo (fase 3, non implementare prima) |

**Regole di comunicazione**

- Client verso servizi: REST/JSON attraverso il gateway, prefisso `/api/v1/<servizio>/...`.
- Servizio verso servizio: eventi asincroni su RabbitMQ. Chiamate HTTP dirette solo per letture indispensabili, sempre con timeout e gestione dell'errore.
- I servizi verificano il JWT emesso da `auth` tramite chiave pubblica, senza chiamare `auth` a ogni richiesta.
- Nomi degli eventi: `<dominio>.<fatto_al_passato>`, per esempio `property.published`, `property.price_changed`, `lead.valuation_requested`, `lead.visit_requested`, `notification.requested`.
- Ogni evento ha uno schema Pydantic versionato in `packages/py-common`. I consumer devono essere idempotenti.

**Flusso di esempio:** `property` pubblica un immobile ed emette `property.published`; `engagement` confronta l'immobile con le ricerche salvate ed emette `notification.requested` per gli utenti compatibili che hanno dato il consenso; `notification` invia la push.

## 4. Struttura del repository

```
/
├── CLAUDE.md
├── docker-compose.yml
├── apps/
│   ├── mobile/          # App Expo
│   ├── admin/           # Pannello di amministrazione
│   └── web/             # Pagina pubblica di valutazione
├── services/
│   ├── auth/
│   ├── property/
│   ├── lead/
│   ├── engagement/
│   ├── notification/
│   └── assistant/
├── packages/
│   ├── py-common/       # Config, logging, eventi, verifica JWT
│   └── api-client/      # Client TypeScript generato da OpenAPI
├── infra/
│   ├── gateway/         # Traefik per docker compose
│   └── cloudrun/        # Pubblicazione: gateway, script di preparazione, config.env
├── docs/
│   ├── deploy/          # Guida alla pubblicazione (cloud-run.md)
│   └── design/
│       └── reference/   # Immagini di riferimento per il front-end (sezione 13)
│           ├── valutazione/
│           └── home/
└── .github/workflows/
```

**Struttura di ogni servizio**

```
services/<nome>/
├── app/
│   ├── main.py
│   ├── api/             # Router FastAPI, solo validazione e risposta
│   ├── core/            # Configurazione, sicurezza, dipendenze
│   ├── models/          # Modelli SQLAlchemy
│   ├── schemas/         # Schemi Pydantic di input e output
│   ├── services/        # Logica di business
│   ├── repositories/    # Accesso ai dati
│   └── events/          # Publisher e consumer
├── alembic/
├── tests/
├── Dockerfile
└── pyproject.toml
```

## 5. Comandi

```bash
# Tutto lo stack in locale
docker compose up -d
docker compose logs -f <servizio>

# Dentro services/<nome>
uv sync
uv run uvicorn app.main:app --reload
uv run pytest
uv run ruff check . && uv run ruff format .
uv run mypy app
uv run alembic revision --autogenerate -m "descrizione"
uv run alembic upgrade head

# Dentro apps/mobile
npm install
npx expo start
npm run lint
npm run typecheck
npm test

# Dentro apps/admin oppure apps/web
npm install
npm run dev
npm run build
npm run lint
npm test
```

Prima di dichiarare finito un lavoro, esegui lint, type check e test della parte toccata.

## 6. Convenzioni di codice

**Generali**

- Codice, identificatori e commenti in inglese. Testi dell'interfaccia in italiano, centralizzati nei file di traduzione e mai scritti direttamente nei componenti.
- Fornisci sempre file completi e pronti da incollare, non frammenti.
- Nessun segreto nel repository: configurazione da variabili d'ambiente, con un `.env.example` aggiornato per ogni servizio e app.

**Backend**

- Type hints ovunque, `mypy` senza errori.
- I router non contengono logica: chiamano `services/`, che usa `repositories/`.
- Tutto l'I/O è `async`.
- Ogni modifica allo schema passa da una migration Alembic; mai modificare una migration già unita a `main`.
- Errori con formato unico: `{"code": "...", "message": "...", "details": {...}}`.
- Liste sempre paginate.
- Ogni servizio espone `/health` e produce log JSON con `request_id` propagato dal gateway.
- Ogni endpoint nuovo ha almeno un test del caso corretto e uno del caso di errore.

**Mobile e web**

- TypeScript in modalità `strict`, niente `any`.
- Solo componenti funzione e hook.
- Le chiamate di rete passano da `packages/api-client` e TanStack Query, mai `fetch` diretto nei componenti.
- Rigenera `api-client` ogni volta che cambia l'OpenAPI di un servizio.
- Colori, spaziature e tipografia solo dal tema condiviso.

## 7. Test backend con pytest

Ogni servizio ha la propria suite in `services/<nome>/tests/`. Nessuna funzionalità è finita senza i suoi test.

**Strumenti:** `pytest`, `pytest-asyncio` (modalità `auto`), `httpx.AsyncClient` per chiamare l'app FastAPI, `pytest-cov` per la copertura, `testcontainers` per PostgreSQL, Redis e RabbitMQ reali.

**Struttura**

```
services/<nome>/tests/
├── conftest.py          # Fixture condivise: app, client, db_session, utenti, token
├── factories.py         # Funzioni che creano dati di test validi
├── unit/                # Logica in services/, senza database né rete
├── integration/         # Repository e migration su PostgreSQL reale
├── api/                 # Endpoint attraverso httpx.AsyncClient
└── events/              # Publisher e consumer
```

**Tipi di test**

- `unit`: testano `app/services/` con i repository sostituiti da fake. Veloci, senza I/O.
- `integration`: testano `app/repositories/` e le query su un PostgreSQL reale avviato con testcontainers. Mai SQLite al posto di PostgreSQL.
- `api`: testano gli endpoint dall'esterno, compresi codici di stato, formato degli errori, paginazione e permessi.
- `events`: verificano che l'evento emesso rispetti lo schema in `py-common` e che i consumer siano idempotenti (lo stesso evento ricevuto due volte non produce effetti doppi).

**Regole**

- Ogni endpoint ha almeno: caso corretto, input non valido (422), accesso senza token (401), accesso con ruolo sbagliato (403) dove previsto.
- Ogni test è indipendente: il database torna pulito dopo ogni test (transazione annullata con rollback) e i test non dipendono dall'ordine di esecuzione.
- Lo schema del database di test si crea con `alembic upgrade head`, non con `create_all`, così vengono testate anche le migration.
- Gli altri microservizi e i servizi esterni (Expo Push, email, storage) non vengono mai chiamati davvero: si sostituiscono con fake tramite le dipendenze di FastAPI (`app.dependency_overrides`).
- I dati di test si creano con le funzioni di `factories.py`, non copiando dizionari da un test all'altro. Mai dati personali reali.
- Nomi nel formato `test_<cosa>_<condizione>_<risultato>`, per esempio `test_create_valuation_without_phone_returns_422`.
- Struttura di ogni test: preparazione, azione, verifica. Una sola azione per test.
- Marker: `@pytest.mark.integration` per i test che richiedono container, così i test unitari si possono eseguire da soli.
- Quando si corregge un bug, prima si scrive il test che lo riproduce, poi la correzione.
- Le regole di dominio della sezione 11 devono avere test espliciti (per esempio: nessuna notifica a un utente senza consenso).

**Comandi**

```bash
uv run pytest                              # Tutta la suite
uv run pytest -m "not integration"         # Solo i test veloci
uv run pytest tests/api/test_valuations.py # Un singolo file
uv run pytest -k "valuation"               # Per nome
uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=80
```

**Copertura:** soglia minima dell'80% per servizio, verificata dalla CI. La copertura misura cosa manca, non la qualità: un test senza verifiche significative non conta.

## 8. Git e versionamento

- `main` è sempre rilasciabile e protetto: si entra solo con pull request e CI verde.
- Branch: `feat/<descrizione>`, `fix/<descrizione>`, `chore/<descrizione>`.
- Commit in formato Conventional Commits con lo scope del componente: `feat(lead): add valuation request endpoint`.
- Versioni in SemVer, con tag per componente: `mobile-v1.2.0`, `lead-v0.4.1`.
- La versione dell'app sta in `apps/mobile/app.json`; il numero di build è incrementato da EAS.
- Le immagini Docker sono taggate con lo SHA del commit e, al rilascio, con la versione.
- Non fare commit, push o tag senza che venga chiesto.

## 9. Pipeline CI/CD

**CI, a ogni pull request** (solo sui componenti modificati, con filtri sui percorsi):

1. Lint e formattazione
2. Type check
3. Test con pytest e verifica della soglia di copertura (servizi), Jest (app e web)
4. Build dell'immagine Docker (servizi) o build di verifica (app e web)

**CD (ottobre 2026): hosting gratuito.** Backend su Google Cloud Run (`europe-west1`), un servizio per `auth`, `lead`, `property` più il gateway Traefik (`infra/cloudrun/gateway`, stesse regole di `docker-compose.yml`); database su Neon (un progetto, un database per servizio); foto su Cloudflare R2; pannello admin su Netlify (`netlify.toml`). La pubblicazione è manuale: GitHub Actions → **Deploy** (`.github/workflows/deploy.yml`), che costruisce le immagini, esegue le migration e pubblica. GitHub accede a Google Cloud senza chiavi (Workload Identity Federation); i segreti stanno in Secret Manager, la configurazione non segreta in `infra/cloudrun/config.env`. RabbitMQ non è attivo in produzione (`EVENTS_ENABLED=false`). Guida completa: `docs/deploy/cloud-run.md`. Nuove variabili d'ambiente dei servizi vanno aggiunte anche al workflow di deploy.

**Rilascio mobile: da definire.** Previsto EAS Build e EAS Submit verso il Play Store, partendo dal canale di test interno.

## 10. Funzionalità e ordine di sviluppo

Tutte le funzioni qui sotto sono nel perimetro del progetto. L'ordine indica la sequenza di costruzione.

**Fase 1 — Acquisizione proprietari**

- Valutazione "Quanto vale la tua casa?" in due passi: prima i dati essenziali (nome, telefono, comune, tipologia, superficie indicativa, camere, stato, intenzione), poi il completamento facoltativo con foto e dettagli.
- Percorsi "Voglio vendere casa" e "Voglio affittare il mio immobile".
- Grado di intenzione del proprietario: vuole conoscere il valore, pensa di vendere nei prossimi mesi, ha già deciso. Determina la priorità del lead.
- Contatto rapido: WhatsApp, telefono, email.
- Prenotazione di appuntamenti e visite.
- Pannello admin: gestione di immobili, prezzi, foto, disponibilità, lead e promemoria di ricontatto.
- Pagina web pubblica di valutazione, usabile senza installare l'app.
- Catalogo immobili con scheda di dettaglio.

**Fase 2 — Fidelizzazione**

- Ricerca avanzata: operazione, località, prezzo, tipologia, superficie, camere, caratteristiche, classe energetica.
- Ricerca su mappa e "immobili vicino a te".
- Preferiti, ricerche salvate, confronto tra immobili.
- Notifiche push personalizzate e configurabili per categoria.
- Sezione "Immobili venduti".
- Sezione "Affitti per studenti e lavoratori" con filtri per budget, tipo di sistemazione e data di ingresso.
- Area personale con storico di richieste e appuntamenti.
- Sezione servizi dell'agenzia per chi vende e per chi affitta.
- Condivisione degli immobili.

**Fase 3 — Funzioni avanzate**

- Calcolatori: rata del mutuo, spese di acquisto, rendimento lordo e netto. Logica lato client, nessun servizio dedicato.
- Assistente virtuale sul catalogo.
- Tour virtuali a 360° e video.
- Integrazione con un gestionale immobiliare esterno.

## 11. Regole di dominio

Queste regole valgono sempre, anche quando non sono ripetute nella richiesta.

- Una stima automatica non va mai presentata come valutazione professionale. Deve sempre essere indicata come orientativa.
- Una richiesta di valutazione è un lead, non un incarico.
- I moduli per i proprietari devono essere brevi e compilabili da smartphone in pochi secondi. Non aggiungere campi obbligatori senza chiederlo.
- Le notifiche si inviano solo a chi ha dato il consenso, rispettando le categorie scelte dall'utente. Niente notifiche generiche di massa.
- L'app mobile richiede un account per tutte le funzioni: dopo la schermata di benvenuto l'utente accede o si registra (decisione del titolare, ottobre 2026). Le API pubbliche del catalogo e dei moduli restano utilizzabili senza account, perché servono anche al sito web; quando la richiesta arriva da un utente autenticato viene collegata al suo account. Nota: la regola 5.1.1 dell'App Store di Apple vieta di chiedere la registrazione per funzioni che non dipendono da un account; prima della pubblicazione su iOS questa scelta va rivalutata.
- Negli "Immobili venduti" si mostrano solo zona, tipologia e foto autorizzate. Nessun dato personale dei proprietari; testimonianze solo con consenso registrato.
- I calcolatori mostrano sempre che il risultato è indicativo e non è un preventivo.
- L'assistente virtuale risponde solo con dati reali del catalogo. Non inventa immobili, prezzi o disponibilità; se non trova nulla, propone di lasciare i contatti.
- L'agenzia deve poter pubblicare e modificare un immobile dal pannello admin senza intervento dello sviluppatore.

## 12. Privacy e sicurezza

L'app tratta dati personali (nome, telefono, indirizzo dell'immobile, foto), quindi il GDPR si applica a ogni funzione.

- Ogni consenso viene registrato in `auth` con data, versione dell'informativa e finalità. Consenso marketing separato da quello di contatto.
- Nessun dato personale nei log, nei messaggi di errore o negli eventi oltre lo stretto necessario.
- Prevedere esportazione e cancellazione dei dati di un utente in tutti i servizi che li contengono.
- Password con hash Argon2; token di accesso a breve durata con refresh token.
- Tutti gli endpoint di admin richiedono il ruolo staff. Rate limiting sui moduli pubblici.
- Le immagini caricate vengono validate per tipo e dimensione e servite tramite URL firmati quando non sono pubbliche.

## 13. Interfaccia

- Stile elegante, pulito e sobrio: non deve sembrare un portale pubblicitario.
- Colori: blu e celeste del marchio, bianco, grigio chiaro.
- Logo ben visibile nella schermata iniziale. Fotografie grandi e luminose.
- Barra di navigazione inferiore con cinque sezioni: Home, Cerca, Preferiti, Vendi casa, Profilo.
- Nella Home le tre azioni principali sono "Cerca casa", "Vendi casa" e "Contattaci". Non sovraccaricarla.
- Il contatto rapido con l'agenzia è raggiungibile da ogni scheda immobile.

### Riferimenti visivi

Le immagini in `docs/design/reference/` sono il riferimento che il front-end deve rispecchiare. Prima di costruire o modificare una schermata, apri le immagini della sua cartella con lo strumento di lettura e confronta il risultato con esse.

**Come usarle**

- Riprendi layout, gerarchia visiva, flusso tra le schermate e tipo di componenti.
- Non copiare loghi, nomi, marchi, testi o fotografie delle app di riferimento. Al loro posto: logo e nome Immobiliare Taraborrelli, testi in italiano, foto degli immobili dell'agenzia.
- La palette resta quella del marchio (blu, celeste, bianco, grigio chiaro), anche dove i riferimenti usano nero, verde, giallo o rosso.
- Adatta i dati al contesto italiano: euro (formato `120.000 €`), metri quadrati, località di Chieti e dintorni.
- Dove un riferimento contraddice una regola di dominio (sezione 11) o una scelta di questa sezione, vince la regola.

#### 1. «Quanto vale la tua casa?» — `docs/design/reference/valutazione/`

| File | Cosa riprendere |
|---|---|
| `01-stima-e-zona.png` | Schermata d'ingresso con foto a tutta altezza, titolo grande e un solo campo per l'indirizzo. Pagina dei risultati con statistiche della zona in tre colonne, carosello degli immobili venduti in zona, pulsanti "Contattaci" e "Chiama". Stima mostrata come intervallo con icona informativa e benefici della valutazione completa con spunte. |
| `02-wizard-a-passi.png` | Modulo diviso in passi con barra di avanzamento e indicatore "Passo X di N". Una domanda per schermata, scelte grandi con icona (per esempio Casa / Appartamento), pulsante "Avanti" fisso in basso e "Indietro" accanto. |
| `03-domande-intenzione-tempi.png` | Domande a scelta singola con opzioni a tutta larghezza: perché vuoi la valutazione (vendere, affittare, solo curiosità) e quando vuoi vendere (subito, entro 3, 6, 12 mesi, non so). Campo facoltativo per il prezzo atteso con casella "Non so". Il pulsante "Avanti" resta disattivato finché manca una risposta. |
| `04-conferma-dati-immobile.png` | Conferma dei dati dell'immobile con risposta Sì / No, riepilogo con foto, e regolazione dello stato delle singole parti (cucina, bagni, infissi, impianti) con menu a tendina. |
| `05-stima-a-intervallo.png` | Stima su un cursore con valore minimo e massimo, nota che la stima è orientativa e invito a richiedere la valutazione professionale. Calcolo del ricavo netto stimato e scheda dell'agente con foto e tempo medio di risposta. |

Elementi esclusi da questo flusso: la scelta tra più agenzie (c'è una sola agenzia), le valutazioni con stelle degli agenti, i dati sulle scuole.

Il flusso deve rispettare la sezione 11: dati essenziali prima (nome e telefono compresi), dettagli facoltativi dopo; la stima automatica è sempre presentata come orientativa e porta alla richiesta di valutazione professionale gratuita.

#### 2. Schermata Home — `docs/design/reference/home/`

| File | Cosa riprendere |
|---|---|
| `01-onboarding-e-home.png` | Onboarding con foto a tutta altezza e pulsante "Inizia". Home con saluto, località, barra di ricerca con pulsante filtri, carosello orizzontale "In evidenza" con "Vedi tutti", schede immobile con foto, prezzo e località, cuore per i preferiti. Scheda di dettaglio con galleria, icone delle caratteristiche (camere, bagni, posto auto), prezzo e pulsante principale in basso. Barra di navigazione inferiore scura e arrotondata con la voce attiva evidenziata. |
| `02-home-filtri-mappa.png` | Chip di categoria scorrevoli (Tutti, Casa, Appartamento, Villa...). Schede immobile grandi con caratteristiche sovrapposte alla foto. Schermata filtri con selettore Vendita / Affitto, chip per tipologia, istogramma dei prezzi con cursore doppio, località, pulsanti "Azzera" e "Applica". Vista mappa con indicatori e schede scorrevoli in basso. |
| `03-home-vendita-affitto-scheda.png` | Selettore Affitto / Compra in cima alla Home, campo località con pulsante di geolocalizzazione, sezione "Popolari ora". Scheda di dettaglio con foto in alto e contenuto in un pannello arrotondato sovrapposto, riga dell'agente con pulsanti chat e chiamata, due azioni affiancate "Tour 360°" e "Prenota visita". |

Elementi esclusi o da adattare: le stelle di valutazione sugli immobili, le date di inizio e fine soggiorno (sono per affitti brevi), le icone non pertinenti (palestra, piscina come caratteristica standard). La barra di navigazione resta quella a cinque voci definita sopra, e nella Home devono comparire chiaramente le tre azioni principali "Cerca casa", "Vendi casa" e "Contattaci".

## 14. Decisioni aperte

Non dare per scontate queste scelte: chiedi prima di implementare qualcosa che ne dipende.

- Hosting: scelto (sezione 9). Restano da decidere il dominio dell'API (per ora l'indirizzo `run.app` del gateway) e se attivare RabbitMQ in produzione.
  - **Modulo di ricontatto del sito** https://immobiliare-taraborrelli.netlify.app/ (ottobre 2026). Il modulo «Richiedi di essere ricontattato» (nome, cognome, email, telefono, fascia oraria, messaggio) oggi invia a un backend separato su Render (`immobiliare-taraborell-be.onrender.com/api/contacts`) e non chiede il consenso privacy. Lato app è pronto: `lead` ha il tipo «Richiesta di ricontatto» (`POST /api/v1/lead/callback-requests`, consenso privacy obbligatorio), il gateway accetta il dominio del sito (CORS) e applica il rate limiting dei moduli pubblici, e le richieste compaiono nel pannello in «Richieste proprietari». **Da fare dopo la prima pubblicazione:** nel codice del sito (cartella `my-project`) far inviare il modulo all'indirizzo pubblico del gateway, con la casella del consenso privacy e il link all'informativa, poi ripubblicare il sito su Netlify; se il dominio del sito cambia, aggiornarlo in `infra/gateway/dynamic.yml` e in `ALLOWED_ORIGINS` di `infra/cloudrun/config.env`. Il vecchio backend `immobiliare-taraborell-be` (repository separato) espone a chiunque l'elenco delle richieste su `GET /api/contacts`: va spento dopo il passaggio. Alternativa valutata e messa da parte: importare le richieste da Netlify Forms tramite la loro API.
- Account sviluppatore e tempi di pubblicazione su Play Store; pubblicazione su App Store
- Metodo e fonte dati per la stima automatica
- Integrazione con il gestionale immobiliare: l'agenzia usa **Reasoft** (ottobre 2026). Da verificare con l'assistenza Reasoft se offre un'esportazione degli annunci per il sito dell'agenzia (feed XML o API) e in quale formato. Se esiste, `property` importerà periodicamente gli annunci (creazione, aggiornamento, ritiro, foto). Nel frattempo c'è l'importazione da Excel/CSV dal pannello admin (pagina «Importa da Excel»): anteprima con controlli di coerenza, nuovi immobili in bozza, aggiornamento degli esistenti tramite il codice del gestionale; le foto si aggiungono dal pannello, anche in blocco (pagina «Carica foto»: abbinamento tramite il codice del gestionale nel nome della sottocartella o del file). L'elenco immobili esportato da Reasoft è una tabella HTML salvata come `.xls` e non contiene contratto, superficie, titolo e descrizione: il contratto viene dedotto dal prezzo (fino a 5.000 € affitto), la superficie resta vuota nelle bozze ed è obbligatoria per pubblicare. Le colonne Proprietario e Note non vengono mai importate (dati personali). Le intestazioni riconosciute sono in `services/property/app/services/importer.py`.
- WhatsApp tramite semplice link o tramite API Business
- Fornitore di mappe e di email transazionali. Le email (il codice di «password dimenticata», inviato da `auth`, e l'avviso all'agenzia per ogni nuova richiesta, inviato da `lead` agli indirizzi di `STAFF_NOTIFICATION_EMAILS`; quando esisterà `notification` l'avviso si sposta lì) passano da SMTP generico, configurabile con variabili d'ambiente per qualsiasi provider; in locale vengono salvate in `.dev/outbox` invece che spedite.
- Codici colore esatti e file del logo
