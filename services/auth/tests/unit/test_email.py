from app.services.email_templates import password_reset_email


def test_password_reset_email_is_in_italian_with_code_and_validity() -> None:
    email = password_reset_email("anna@example.test", "Anna Bianchi", "654321", 15)

    assert email.subject == "Il tuo codice per reimpostare la password"
    assert "654321" in email.text
    assert "15 minuti" in email.text
    assert "ignora questa email" in email.text
