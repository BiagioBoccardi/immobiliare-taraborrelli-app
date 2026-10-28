# Immobiliare Taraborrelli — App

Monorepo dell'app mobile, del pannello admin, della pagina pubblica di valutazione e dei
microservizi backend dell'agenzia Immobiliare Taraborrelli (Chieti e Chieti Scalo).

Le istruzioni complete del progetto (architettura, convenzioni, regole di dominio, privacy,
interfaccia) sono in [`CLAUDE.md`](CLAUDE.md).

## Stato

| Componente | Stato |
|---|---|
| `packages/py-common` | Config, log JSON con `request_id`, formato errori unico, paginazione, verifica JWT, eventi versionati, publisher e consumer RabbitMQ |
| `services/auth` | Registrazione, login, JWT (RS256) con refresh token a rotazione, ruoli, gestione account staff, registro dei consensi privacy, esportazione e cancellazione GDPR |
| `services/property` | Catalogo con ricerca e filtri (anche mappa e affitti per studenti e lavoratori), scheda immobile, immobili venduti, gestione da admin con stati e foto su storage S3 |
| `services/lead` | Richieste di valutazione (passo 1 + completamento facoltativo), richieste "Voglio vendere" / "Voglio affittare", CRM leggero per lo staff |
| `infra/gateway` | Traefik con CORS e rate limiting sui moduli pubblici |
| `packages/api-client` | Client TypeScript con tipi generati dall'OpenAPI dei servizi, rinnovo automatico della sessione |
| `packages/theme` | Colori, spaziature e tipografia condivisi da admin, pagina web e app |
| `apps/mobile` | App Expo: onboarding, Home con «Cerca casa», «Vendi casa», «Contattaci», catalogo con filtri, scheda immobile con contatto rapido, preferiti senza registrazione, richiesta «vendi o affitta» |
| `apps/admin` | Pannello di amministrazione: riepilogo, richieste dei proprietari (CRM), immobili con foto e stati, account staff |
| Altri servizi e app | Da sviluppare (vedi `CLAUDE.md`, sezione 10) |

## Provare il pannello di amministrazione

Requisiti: Docker, [uv](https://docs.astral.sh/uv/), Node.js 20+, Python 3 e openssl (su Windows usare WSL2).

```bash
scripts/dev-local.sh up     # avvia tutto in circa 20 secondi (la prima volta di più)
# pannello: http://localhost:5173 — admin@taraborrelli.test / Admin-di-prova-1
# app (anteprima nel browser): http://localhost:8081
scripts/dev-local.sh logs   # log dei servizi
scripts/dev-local.sh down   # ferma tutto (i dati restano per il prossimo avvio)
scripts/dev-local.sh reset  # ferma tutto ed elimina tutti i dati di prova
```

Lo script avvia PostgreSQL in Docker, i servizi auth, lead e property, un piccolo archivio
compatibile S3 per le foto (`scripts/dev-s3.py`), il pannello e l'app mobile in anteprima nel
browser. Il database sta in un volume Docker e le foto nella cartella `.dev/media`:
immobili importati, foto caricate e utenti restano dopo `down`, un riavvio del PC o un
`git pull`. Il primo avvio (o il primo dopo `reset`) crea un amministratore di prova, un utente
dell'app, due richieste di esempio e cinque immobili di esempio (inventati, con foto
segnaposto). Le porte usate sono 5173, 8081, 8001-8003, 9100 e 55432.

## Avvio rapido

```bash
cp .env.example .env
infra/scripts/generate-jwt-keys.sh        # coppia di chiavi JWT per lo sviluppo locale
docker compose up -d
# Primo amministratore (la password viene chiesta dal terminale):
docker compose exec auth python -m app.cli create-admin --email admin@example.com --name "Nome Cognome"
# Documentazione API tramite gateway: http://localhost:8000/api/v1/<auth|lead|property>/docs
```

Sviluppo di un singolo servizio:

```bash
cd services/lead
uv sync
uv run pytest -m "not integration"   # test veloci
uv run pytest                        # tutta la suite (richiede Docker)
```

## Front-end

```bash
npm install                      # dalla radice: installa tutti i workspace
npm run dev --workspace @taraborrelli/admin   # pannello su http://localhost:5173
npm run lint && npm run typecheck && npm test
npm run generate:api             # rigenera il client dopo ogni modifica alle API (richiede uv)
```

In sviluppo il pannello inoltra `/api` al gateway (`docker compose`, porta 8000). Lo staff accede
con le credenziali create da un amministratore; il primo amministratore si crea con il comando
`create-admin` del servizio auth. I colori del marchio e il logo sono provvisori finché l'agenzia
non fornisce quelli definitivi.

## API del servizio lead

| Metodo | Percorso | Accesso |
|---|---|---|
| `POST` | `/api/v1/lead/valuations` | Pubblico — passo 1 della valutazione, restituisce un `completion_token` monouso |
| `PUT` | `/api/v1/lead/valuations/{id}/details` | Pubblico con header `X-Completion-Token` — dettagli facoltativi (entro 7 giorni) |
| `POST` | `/api/v1/lead/owner-requests` | Pubblico — "Voglio vendere casa" / "Voglio affittare il mio immobile" |
| `POST` | `/api/v1/lead/callback-requests` | Pubblico — "Richiedi di essere ricontattato" dal sito dell'agenzia: nome, cognome, email, telefono, fascia oraria (`morning`, `afternoon`, `evening`, `any`), messaggio facoltativo e consenso privacy obbligatorio |
| `GET` | `/api/v1/lead/leads` | Staff — lista paginata con filtri `kind`, `status`, `priority`, `due_for_contact` |
| `GET` / `PATCH` / `DELETE` | `/api/v1/lead/leads/{id}` | Staff — dettaglio, aggiornamento CRM, cancellazione (GDPR) |

Le richieste di ricontatto non descrivono un immobile (comune, tipologia e intenzione restano
vuoti), hanno priorità media e risultano subito «da ricontattare», perché il sito promette una
chiamata entro il giorno lavorativo successivo.

La priorità del lead deriva dal grado di intenzione del proprietario: `know_value` → bassa,
`planning` → media, `decided` → alta. Lo staff può modificarla.

## API del servizio auth

| Metodo | Percorso | Accesso |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Pubblico — account utente con consenso privacy (e marketing facoltativo) |
| `POST` | `/api/v1/auth/login` | Pubblico — restituisce access token (15 minuti) e refresh token (30 giorni) |
| `POST` | `/api/v1/auth/refresh` | Pubblico — ruota il refresh token; il riuso di un token già usato revoca la sessione |
| `POST` | `/api/v1/auth/logout` | Pubblico — revoca la sessione del refresh token |
| `GET` | `/api/v1/auth/public-key` | Pubblico — chiave pubblica PEM per verificare i token |
| `GET` / `DELETE` | `/api/v1/auth/me` | Utente — profilo, cancellazione dell'account (GDPR) |
| `GET` | `/api/v1/auth/me/export` | Utente — esportazione dei dati (GDPR) |
| `GET` / `POST` | `/api/v1/auth/me/consents` | Utente — stato e modifica dei consensi (contatto, marketing, notifiche push) |
| `GET` | `/api/v1/auth/users` | Admin — lista paginata degli account |
| `POST` | `/api/v1/auth/users/staff` | Admin — crea un account staff o admin |
| `PATCH` | `/api/v1/auth/users/{id}` | Admin — ruolo, attivazione, nome (resta sempre almeno un admin attivo) |

I consensi dati nei moduli del servizio lead arrivano al registro tramite l'evento
`lead.consent_given`; la cancellazione di un account emette `auth.user_deleted`, che gli altri
servizi useranno per cancellare i dati collegati.

## API del servizio property

| Metodo | Percorso | Accesso |
|---|---|---|
| `GET` | `/api/v1/property/properties` | Pubblico — ricerca paginata (vedi filtri sotto) |
| `GET` | `/api/v1/property/properties/{id}` | Pubblico — scheda dell'immobile pubblicato |
| `GET` | `/api/v1/property/sold` | Pubblico — "Immobili venduti": solo zona, tipologia e foto autorizzate |
| `GET` / `POST` | `/api/v1/property/admin/properties` | Staff — lista (filtri `status`, `contract`, `q`) e creazione in bozza |
| `GET` / `PATCH` / `DELETE` | `/api/v1/property/admin/properties/{id}` | Staff — dettaglio con indirizzo, modifica, cancellazione (solo bozze e archiviati) |
| `POST` | `/api/v1/property/admin/properties/{id}/status` | Staff — cambio di stato |
| `POST` | `/api/v1/property/admin/properties/{id}/photos` | Staff — caricamento foto (JPEG, PNG, WebP, max 10 MB, max 40) |
| `PATCH` / `DELETE` | `/api/v1/property/admin/properties/{id}/photos/{photo_id}` | Staff — didascalia, autorizzazione per i venduti, eliminazione |
| `PUT` | `/api/v1/property/admin/properties/{id}/photos/order` | Staff — ordine delle foto (la prima è la copertina) |
| `PUT` / `DELETE` | `/api/v1/property/admin/properties/{id}/model-3d` | Staff — modello 3D dell'immobile (`.glb`, max 10 MB; un nuovo caricamento sostituisce il precedente) |

**Modello 3D:** la scheda pubblica restituisce `three_d_model` (URL e dimensione) quando c'è un
modello; l'app mostra il pulsante «Vedi in 3D». Nel browser il visore è `@google/model-viewer`
(caricato solo quando si apre il modello); sul telefono lo stesso componente gira in una WebView
e viene scaricato da jsDelivr, alla stessa versione del pacchetto. Lo storage dei file deve
permettere la lettura cross-origin (CORS) dei `.glb`: in locale lo fa già `scripts/dev-s3.py`.

**Stanze 3D dalle foto:** ogni foto può avere la sua stanza 3D (`photos[].three_d_url`, caricata
con `PUT /admin/properties/{id}/photos/{photo_id}/model-3d`); l'app mostra il pulsante «3D» sulla
foto e la schermata «Vista 3D», con la nota che la ricostruzione è indicativa. Le stanze si creano
in blocco con `scripts/rooms-3d.py`: per ogni foto un modello di profondità per interni e un
riconoscitore di mobili (entrambi Apache-2.0, scaricati da GitHub in `~/.cache/taraborrelli`)
ricavano dimensioni della stanza, colori, mobili, armadi lungo le pareti e finestre;
`scripts/room-builder.mjs` costruisce la stanza con three.js (pavimento, pareti, mobili come
oggetti, lato verso chi guarda aperto) e la esporta in `.glb`. Le foto che non mostrano una stanza
(esterni, balconi) restano senza 3D.

```bash
uv run --no-project --with onnxruntime --with numpy --with pillow scripts/rooms-3d.py --replace
```

**Filtri di ricerca:** `contract`, `property_type` (ripetibile), `municipality`, `zone`,
`price_min`/`price_max`, `surface_min`/`surface_max`, `rooms_min`, `bedrooms_min`,
`bathrooms_min`, `feature` (ripetibile, tutte richieste), `energy_class` (ripetibile), `featured`,
`tenant_type`, `accommodation`, `available_by`, area della mappa
(`min_lat`, `max_lat`, `min_lng`, `max_lng`), `sort` (`newest`, `price_asc`, `price_desc`,
`surface_desc`).

**Stati:** `draft` → `published` ⇄ `reserved` → `sold` / `rented` → `archived`. Sono visibili al
pubblico solo `published` e `reserved`; per pubblicare serve almeno una foto. L'indirizzo resta
visibile solo allo staff e le coordinate pubbliche sono arrotondate a circa 100 metri, salvo che
l'agenzia scelga di mostrare la posizione esatta.

**Eventi:** `property.published`, `property.price_changed`, `property.unpublished`.
