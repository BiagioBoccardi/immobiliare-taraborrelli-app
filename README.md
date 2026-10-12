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
| `services/lead` | Richieste di valutazione (passo 1 + completamento facoltativo), richieste "Voglio vendere" / "Voglio affittare", CRM leggero per lo staff |
| `infra/gateway` | Traefik con CORS e rate limiting sui moduli pubblici |
| Altri servizi e app | Da sviluppare (vedi `CLAUDE.md`, sezione 10) |

## Avvio rapido

```bash
cp .env.example .env
infra/scripts/generate-jwt-keys.sh        # coppia di chiavi JWT per lo sviluppo locale
docker compose up -d
# Primo amministratore (la password viene chiesta dal terminale):
docker compose exec auth python -m app.cli create-admin --email admin@example.com --name "Nome Cognome"
# Documentazione API tramite gateway: http://localhost:8000/api/v1/auth/docs e /api/v1/lead/docs
```

Sviluppo di un singolo servizio:

```bash
cd services/lead
uv sync
uv run pytest -m "not integration"   # test veloci
uv run pytest                        # tutta la suite (richiede Docker)
```

## API del servizio lead

| Metodo | Percorso | Accesso |
|---|---|---|
| `POST` | `/api/v1/lead/valuations` | Pubblico — passo 1 della valutazione, restituisce un `completion_token` monouso |
| `PUT` | `/api/v1/lead/valuations/{id}/details` | Pubblico con header `X-Completion-Token` — dettagli facoltativi (entro 7 giorni) |
| `POST` | `/api/v1/lead/owner-requests` | Pubblico — "Voglio vendere casa" / "Voglio affittare il mio immobile" |
| `GET` | `/api/v1/lead/leads` | Staff — lista paginata con filtri `kind`, `status`, `priority`, `due_for_contact` |
| `GET` / `PATCH` / `DELETE` | `/api/v1/lead/leads/{id}` | Staff — dettaglio, aggiornamento CRM, cancellazione (GDPR) |

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
