"""Texts of the emails sent to users, in Italian."""

from py_common.email import Email


def password_reset_email(to: str, full_name: str, code: str, minutes: int) -> Email:
    first_name = full_name.split()[0] if full_name.split() else ""
    text = (
        f"Ciao {first_name},\n\n"
        "abbiamo ricevuto una richiesta per reimpostare la password del tuo account "
        "Immobiliare Taraborrelli.\n\n"
        f"Il tuo codice è: {code}\n\n"
        f"Inseriscilo nell'app o nel pannello entro {minutes} minuti. "
        "Il codice si può usare una sola volta.\n\n"
        "Se non hai chiesto tu di cambiare la password, ignora questa email: "
        "la tua password resta quella di prima.\n\n"
        "Immobiliare Taraborrelli\nChieti e Chieti Scalo\n"
    )
    return Email(to=to, subject="Il tuo codice per reimpostare la password", text=text)
