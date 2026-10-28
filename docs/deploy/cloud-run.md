# Pubblicazione: Google Cloud Run, Neon, Cloudflare R2 e Netlify

Scelta di ottobre 2026: hosting gratuito, senza server da gestire.

| Parte | Dove | Piano gratuito |
|---|---|---|
| Servizi `auth`, `lead`, `property` e gateway | Google Cloud Run (`europe-west1`) | 2 milioni di richieste e 180.000 vCPU-secondi al mese |
| Database (uno per servizio) | Neon, un progetto con 3 database | 1 GB e 100 ore di calcolo al mese |
| Foto degli immobili | Cloudflare R2 | 10 GB, traffico in uscita gratuito |
| Pannello di amministrazione | Netlify | Sito statico |
| Email (avvisi all'agenzia, codici «password dimenticata») | Gmail dell'agenzia via SMTP | Gratuito |

Google Cloud chiede una carta di credito anche per l'uso gratuito. Lo script di preparazione
crea un avviso di spesa a 1 € al mese. Restano possibili pochi centesimi al mese per i segreti
oltre il sesto e per l'archivio delle immagini oltre 0,5 GB.

## 1. Neon (database)

1. Crea un account su https://neon.com e un progetto nella regione **AWS Europe Central 1
   (Frankfurt)**.
2. Dalla pagina del progetto copia l'indirizzo di connessione (inizia con `postgresql://`).
   Lo script lo trasforma da solo nel formato giusto e crea i database `auth`, `lead` e
   `property`.

## 2. Cloudflare R2 (foto)

1. Su https://dash.cloudflare.com apri **R2** e attivalo (Cloudflare può chiedere una carta
   anche per il piano gratuito).
2. Crea il bucket `property-media`.
3. Nel bucket: **Settings → Public access → R2.dev subdomain → Allow**. L'indirizzo
   `https://pub-….r2.dev` va in `MEDIA_PUBLIC_BASE_URL`.
4. **R2 → Manage API tokens → Create API token**, permesso *Object Read & Write* solo sul
   bucket `property-media`. Tieni da parte *Access Key ID* e *Secret Access Key* (servono allo
   script) e l'indirizzo `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`, che va in
   `S3_ENDPOINT_URL`.

## 3. Gmail dell'agenzia (email)

1. Sull'account `immobiliaretaraborrelli@gmail.com` attiva la verifica in due passaggi.
2. Crea una **password per le app** da https://myaccount.google.com/apppasswords e tienila da
   parte per lo script. Non è la password dell'account.

## 4. Google Cloud

1. Su https://console.cloud.google.com crea un progetto (per esempio `taraborrelli`) e
   collegalo a un account di fatturazione.
2. Apri **Cloud Shell** (icona `>_` in alto a destra) e scrivi:

   ```bash
   gcloud config set project <ID-DEL-PROGETTO>
   git clone https://github.com/BiagioBoccardi/immobiliare-taraborrelli-app.git
   cd immobiliare-taraborrelli-app
   bash infra/cloudrun/setup-gcp.sh
   ```

3. Lo script chiede l'indirizzo di Neon, le chiavi di R2 e la password per le app di Gmail
   senza mostrarle a schermo, e le salva in Secret Manager. Alla fine stampa cinque valori
   `GCP_…`.

## 5. Configurazione e pubblicazione

1. In `infra/cloudrun/config.env` scrivi i cinque valori `GCP_…`, `S3_ENDPOINT_URL` e
   `MEDIA_PUBLIC_BASE_URL`, poi fai il commit sul ramo principale.
2. Su GitHub: **Actions → Deploy → Run workflow**. Il workflow costruisce le immagini,
   aggiorna i database e pubblica i quattro servizi. Nel riepilogo trovi l'**indirizzo
   dell'API** (gateway), per esempio `https://taraborrelli-gateway-….europe-west1.run.app`.

## 6. Pannello su Netlify

1. Su https://app.netlify.com: **Add new site → Import an existing project** e scegli questo
   repository. Le impostazioni di build sono già in `netlify.toml`.
2. In **Site configuration → Environment variables** aggiungi `VITE_API_BASE_URL` con
   l'indirizzo dell'API, poi **Deploys → Trigger deploy**.
3. Aggiungi l'indirizzo del pannello (per esempio `https://taraborrelli-admin.netlify.app`) in
   `config.env`: in fondo a `ALLOWED_ORIGINS` e in `ADMIN_PANEL_URL`. Poi rilancia **Deploy**.

## 7. Primo amministratore

In Cloud Shell, dalla cartella del repository:

```bash
bash infra/cloudrun/create-admin.sh tua-email@example.com "Nome Cognome"
```

La password si scrive nel terminale e non viene salvata da nessuna parte.

## 8. Verifiche dopo la prima pubblicazione

1. Accedi al pannello e carica una foto su un immobile in bozza: controlla che si veda.
2. Invia una richiesta dal modulo del sito: deve comparire in «Richieste proprietari» e deve
   arrivare l'email di avviso.
3. Invia lo stesso modulo molte volte di fila: dopo 5-6 invii deve rispondere «troppe
   richieste» (codice 429). Se succede a tutti i visitatori insieme, il
   limite non sta leggendo l'indirizzo del visitatore: va rivista l'impostazione in
   `infra/cloudrun/gateway/dynamic.yml`.

## Limiti noti

- **Avvio a freddo:** dopo un periodo senza visite il primo accesso impiega qualche secondo.
- **Eventi spenti:** RabbitMQ non è attivo (`EVENTS_ENABLED=false`). Richieste e consensi si
  salvano lo stesso, ma i consensi dei moduli non arrivano al registro di `auth` e la
  cancellazione di un account dall'app non cancella in automatico le sue richieste in `lead`:
  vanno cancellate dal pannello.
- **Indirizzi diretti dei servizi:** ogni servizio ha anche un suo indirizzo `run.app` che non
  passa dal gateway, quindi senza i limiti anti-abuso. Gli endpoint dello staff restano protetti
  dal login.
