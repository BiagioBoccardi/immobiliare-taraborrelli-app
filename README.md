# Immobiliare Taraborrelli — App

Monorepo dell'app mobile, del pannello admin, della pagina pubblica di valutazione e dei
microservizi backend dell'agenzia Immobiliare Taraborrelli (Chieti e Chieti Scalo).

Le istruzioni complete del progetto (architettura, convenzioni, regole di dominio, privacy,
interfaccia) sono in [`CLAUDE.md`](CLAUDE.md).

## Stato

| Componente | Stato |
|---|---|
| `packages/py-common` | Config, log JSON con `request_id`, formato errori unico, paginazione, verifica JWT, eventi versionati e publisher RabbitMQ |
| `services/lead` | Richieste di valutazione (passo 1 + completamento facoltativo), richieste "Voglio vendere" / "Voglio affittare", CRM leggero per lo staff |
| `infra/gateway` | Traefik con CORS e rate limiting sui moduli pubblici |
| Altri servizi e app | Da sviluppare (vedi `CLAUDE.md`, sezione 10) |

## Avvio rapido

```bash
cp .env.example .env
docker compose up -d
# API lead tramite gateway: http://localhost:8000/api/v1/lead/docs
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
