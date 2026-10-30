"""Texts of the emails sent to the agency, in Italian."""

from py_common.email import Email

from app.models.enums import LeadKind, OwnerIntention, PreferredTime, PropertyType
from app.models.lead import Lead

_KIND = {
    LeadKind.VALUATION: "Richiesta di valutazione",
    LeadKind.SELL: "Vuole vendere",
    LeadKind.RENT: "Vuole affittare",
    LeadKind.CALLBACK: "Richiesta di ricontatto",
}
_SOURCE = {
    LeadKind.VALUATION: "app o sito",
    LeadKind.SELL: "app o sito",
    LeadKind.RENT: "app o sito",
    LeadKind.CALLBACK: "sito web",
}
_TIME = {
    PreferredTime.MORNING: "Mattina (9:00 - 12:00)",
    PreferredTime.AFTERNOON: "Pomeriggio (12:00 - 17:00)",
    PreferredTime.EVENING: "Sera (17:00 - 20:00)",
    PreferredTime.ANY: "Qualsiasi orario",
}
_INTENTION = {
    OwnerIntention.KNOW_VALUE: "Vuole conoscere il valore",
    OwnerIntention.PLANNING: "Pensa di vendere nei prossimi mesi",
    OwnerIntention.DECIDED: "Ha già deciso",
}
_PROPERTY_TYPE = {
    PropertyType.APARTMENT: "Appartamento",
    PropertyType.HOUSE: "Casa indipendente",
    PropertyType.VILLA: "Villa",
    PropertyType.ATTIC: "Attico",
    PropertyType.COMMERCIAL: "Locale commerciale",
    PropertyType.LAND: "Terreno",
    PropertyType.OTHER: "Altro",
}


def new_lead_email(to: str, lead: Lead, admin_link: str) -> Email:
    kind = _KIND[lead.kind]
    lines = [
        f"Nuova richiesta ricevuta ({_SOURCE[lead.kind]}).",
        "",
        f"Tipo: {kind}",
        f"Nome: {lead.full_name}",
        f"Telefono: {lead.phone}",
    ]
    if lead.email:
        lines.append(f"Email: {lead.email}")
    preferred = lead.details.get("preferred_time")
    if isinstance(preferred, str) and preferred in PreferredTime._value2member_map_:
        lines.append(f"Quando richiamare: {_TIME[PreferredTime(preferred)]}")
    if lead.municipality:
        lines.append(f"Comune: {lead.municipality}")
    if lead.property_type:
        lines.append(f"Tipologia: {_PROPERTY_TYPE[lead.property_type]}")
    if lead.intention:
        lines.append(f"Intenzione: {_INTENTION[lead.intention]}")
    if lead.message:
        lines += ["", "Messaggio:", lead.message]
    if admin_link:
        lines += ["", f"Apri la richiesta nel pannello: {admin_link}"]
    lines += ["", "Immobiliare Taraborrelli - avviso automatico"]
    return Email(to=to, subject=f"{kind} - {lead.full_name}", text="\n".join(lines) + "\n")
