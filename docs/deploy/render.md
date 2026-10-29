# Pubblicazione gratuita: Render, Neon, Gmail e Netlify

Scelta di ottobre 2026: costo zero garantito, senza carta di credito. Sui piani gratuiti
usati qui, superare i limiti sospende il servizio invece di addebitare.

| Parte | Dove | Piano gratuito |
|---|---|---|
| Servizi `auth`, `lead`, `property` | Render, regione Frankfurt (`render.yaml`) | 750 ore al mese per tutto l'account; ogni servizio si ferma dopo 15 minuti senza richieste e riparte in circa un minuto |
| Database (uno per servizio) | Neon, un progetto con i database `auth`, `lead`, `property` | 1 GB per progetto e 100 ore di calcolo al mese |
| Email (avvisi all'agenzia, codici «password dimenticata») | Gmail dell'agenzia tramite uno script Google (`infra/email/gmail-sender.gs`), chiamato via HTTPS: Render gratuito blocca l'SMTP | 100 destinatari al giorno |
| Pannello di amministrazione | Netlify (`netlify.toml`) | Sito statico |
| Sito dell'agenzia | Netlify, repository `immobiliare-taraborrelli-fe` | Sito statico |

**Come si parlano.** Pannello e sito chiamano l'API sul proprio indirizzo Netlify, per
esempio `/api/v1/lead/...`, e Netlify inoltra ogni richiesta al servizio giusto su Render
(`scripts/netlify/admin-redirects.sh`). Il gateway Traefik non c'è: sarebbe un quarto
servizio da svegliare. I limiti anti-abuso li applicano i servizi stessi
(`RATE_LIMIT_ENABLED=true`).

**Servizi addormentati.** Netlify aspetta una risposta al massimo 26 secondi, mentre un
servizio di Render si sveglia in circa un minuto. Per questo pannello e sito chiamano
`/health` appena si aprono: il pannello sveglia tutti e tre i servizi, il sito solo `lead`.
Nel frattempo si compila il modulo o si scrive la password. Se una richiesta arriva prima
che il servizio sia pronto, l'utente vede un errore e riprova dopo qualche secondo.

## 1. Neon (database)

1. Su https://neon.com crea un account e un progetto nella regione **AWS Europe Central 1
   (Frankfurt)**.
2. In **Databases** crea tre database: `auth`, `lead` e `property`.
3. Da **Connect** scegli un database alla volta e copia l'indirizzo. Lo incolli in Render
   così com'è: i servizi lo adattano da soli (driver, SSL, collegamento diretto).

## 2. Email (script nella Gmail dell'agenzia)

Le email partono dalla Gmail dell'agenzia tramite uno script Google gratuito: nessun altro
servizio da registrare. Brevo (`EMAIL_BACKEND=brevo`) resta disponibile come alternativa, ma
la registrazione richiede la verifica di un numero di cellulare.

1. Con l'account `immobiliaretaraborrelli@gmail.com` apri https://script.google.com e crea
   un **Nuovo progetto** chiamato `Taraborrelli email`.
2. Cancella il contenuto di `Codice.gs`, incolla quello di `infra/email/gmail-sender.gs` e
   salva.
3. **Impostazioni progetto** (ingranaggio) → **Proprietà script** → **Aggiungi proprietà**:
   nome `TOKEN`, valore una parola segreta lunga (la stessa andrà su Render).
4. Torna all'editor, scegli la funzione `authorize` e premi **Esegui**. Google chiede il
   permesso di inviare email: **Avanzate → Vai a Taraborrelli email → Consenti**. Arriva
   un'email di prova nella stessa casella.
5. **Esegui il deployment → Nuovo deployment → App web**: esegui come **Me**, accesso
   **Chiunque** → **Esegui il deployment**. Copia l'**URL dell'app web**
   (`https://script.google.com/macros/s/…/exec`).

## 3. Render (servizi)

1. Su https://dashboard.render.com: **New → Blueprint**, scegli questo repository e il ramo
   principale. Render legge `render.yaml` e propone i tre servizi.
2. Compila i valori segreti che Render chiede:
   - `DATABASE_URL`: l'indirizzo Neon del database con lo stesso nome del servizio;
   - `JWT_PRIVATE_KEY` (solo `auth`): la chiave privata consegnata a parte, che corrisponde
     alla chiave pubblica scritta in `render.yaml`;
   - `GMAIL_SCRIPT_URL` e `GMAIL_SCRIPT_TOKEN` (`auth` e `lead`): l'URL dell'app web dello
     script e la parola segreta della proprietà `TOKEN`;
   - `INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD` (almeno 10 caratteri) e
     `INITIAL_ADMIN_NAME` (solo `auth`): il primo amministratore del pannello, vedi sotto;
   - `S3_…` (`property`): per ora lasciali vuoti, vedi «Foto degli immobili».
3. **Apply**. Alla fine ogni servizio ha un indirizzo `https://taraborrelli-….onrender.com`.
   Se Render aggiunge un suffisso perché il nome è già preso, annota gli indirizzi: servono
   a Netlify.

## 4. Netlify (pannello)

1. Su https://app.netlify.com: **Add new project → Import an existing project**, scegli
   questo repository e chiama il sito `taraborrelli-admin`. Le impostazioni di build sono in
   `netlify.toml`.
2. Solo se gli indirizzi di Render hanno un suffisso: in **Project configuration →
   Environment variables** imposta `AUTH_URL`, `LEAD_URL` e `PROPERTY_URL`, poi ripubblica.
3. Se il sito ha un indirizzo diverso da `https://taraborrelli-admin.netlify.app`,
   aggiorna `ADMIN_PANEL_URL` del servizio `lead` su Render: serve per il link nelle email.

## 5. Primo amministratore

Render gratuito non ha un terminale, quindi il primo amministratore lo crea `auth` all'avvio
con `INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD` e `INITIAL_ADMIN_NAME`, solo se non
esiste ancora nessun amministratore. Dopo il primo accesso al pannello cancella
`INITIAL_ADMIN_PASSWORD` dalle variabili del servizio `auth` su Render. Gli altri account
dello staff si creano dal pannello, in «Account staff».

## 6. Verifiche

1. Apri il pannello, attendi un minuto e accedi.
2. Invia il modulo del sito: la richiesta compare in «Richieste proprietari» e arriva
   l'email di avviso.
3. Invia lo stesso modulo più di 10 volte in un minuto: le richieste in più ricevono 429.

## Foto degli immobili

Lo spazio per le foto (compatibile S3) è ancora da scegliere. I servizi gratuiti senza carta
hanno dei vincoli: Cloudflare R2 (10 GB) e Backblaze B2 chiedono un metodo di pagamento per
rendere pubbliche le foto, Supabase Storage (1 GB) mette in pausa i progetti inattivi da una
settimana. Finché `S3_…` resta vuoto, il catalogo funziona ma le foto non si possono caricare.

## Limiti noti

- **Ore gratuite:** le 750 ore al mese sono condivise da tutti i servizi gratuiti
  dell'account Render, compreso il vecchio backend del sito (`immobiliare-taraborell-be`),
  che va sospeso. Se finiscono, i servizi restano fermi fino al mese successivo.
- **Eventi spenti:** senza RabbitMQ (`EVENTS_ENABLED=false`) richieste e consensi si
  salvano lo stesso. Però i consensi dei moduli non arrivano al registro di `auth`, e la
  cancellazione di un account dall'app non cancella in automatico le sue richieste in
  `lead`: vanno cancellate dal pannello.
- **Indirizzi diretti:** i servizi rispondono anche sul loro indirizzo `onrender.com`. Chi li
  chiama direttamente può indicare un indirizzo falso e aggirare il limite anti-abuso. Gli
  endpoint dello staff restano comunque protetti dal login.
