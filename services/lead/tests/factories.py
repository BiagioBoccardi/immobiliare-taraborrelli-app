"""Valid test data. Never real personal data."""

import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.enums import (
    LeadKind,
    LeadPriority,
    LeadStatus,
    OwnerIntention,
    PropertyCondition,
    PropertyType,
)
from app.models.lead import Lead
from app.services.tokens import hash_token


def consent_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "privacy_accepted": True,
        "privacy_policy_version": "2026-01",
        "marketing_accepted": False,
    }
    data.update(overrides)
    return data


def valuation_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "full_name": "Mario Rossi",
        "phone": "+39 333 000 0000",
        "municipality": "Chieti",
        "property_type": "apartment",
        "surface_sqm": 95,
        "rooms": 4,
        "condition": "good",
        "intention": "planning",
        "consent": consent_payload(),
    }
    data.update(overrides)
    return data


def owner_request_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "kind": "sell",
        "full_name": "Anna Bianchi",
        "phone": "333 111 2222",
        "municipality": "Chieti Scalo",
        "property_type": "house",
        "intention": "decided",
        "consent": consent_payload(),
    }
    data.update(overrides)
    return data


def callback_request_payload(**overrides: Any) -> dict[str, Any]:
    """The website's "Richiedi di essere ricontattato" form."""
    data: dict[str, Any] = {
        "first_name": "Luca",
        "last_name": "Neri",
        "email": "luca.neri@example.com",
        "phone": "+39 333 444 5555",
        "preferred_time": "morning",
        "message": "Cerco un bilocale a Chieti Scalo.",
        "consent": consent_payload(),
    }
    data.update(overrides)
    return data


def make_lead(
    *,
    token: str | None = None,
    created_at: datetime | None = None,
    **overrides: Any,
) -> Lead:
    now = created_at or datetime.now(UTC)
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "kind": LeadKind.VALUATION,
        "status": LeadStatus.NEW,
        "priority": LeadPriority.MEDIUM,
        "intention": OwnerIntention.PLANNING,
        "full_name": "Mario Rossi",
        "phone": "+393330000000",
        "municipality": "Chieti",
        "property_type": PropertyType.APARTMENT,
        "surface_sqm": 95,
        "rooms": 4,
        "condition": PropertyCondition.GOOD,
        "details": {},
        "completion_token_hash": hash_token(token) if token else None,
        "contact_consent_at": now,
        "privacy_policy_version": "2026-01",
        "marketing_consent": False,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return Lead(**values)


# OMI files in the format of the Agenzia delle Entrate, with fictional values and zones.
OMI_VALUES_HEADER = (
    "Area_territoriale;Regione;Prov;Comune_ISTAT;Comune_cat;Sez;Comune_amm;Comune_descrizione;"
    "Fascia;Zona;LinkZona;Cod_Tip;Descr_Tipologia;Stato;Stato_prev;Compr_min;Compr_max;"
    "Sup_NL_compr;Loc_min;Loc_max;Sup_NL_loc;"
)
# (zone, type, state, prevalent, min, max)
OMI_ROWS: list[tuple[str, str, str, str, str, str]] = [
    ("B1", "Abitazioni civili", "NORMALE", "P", "1100", "1500"),
    ("B1", "Abitazioni civili", "OTTIMO", "", "1500", "2000"),
    ("B1", "Abitazioni di tipo economico", "NORMALE", "", "900", "1200"),
    ("B1", "Ville e Villini", "NORMALE", "", "1300", "1800"),
    ("B1", "Negozi", "NORMALE", "", "1200", "2400"),
    ("D1", "Abitazioni civili", "NORMALE", "P", "800", "1100"),
]
# Squares around Chieti (longitude, latitude): B1 west, D1 east.
OMI_SQUARES = {"B1": (14.15, 42.34, 14.17, 42.36), "D1": (14.17, 42.34, 14.20, 42.36)}


def omi_values_csv(rows: list[tuple[str, str, str, str, str, str]] | None = None) -> bytes:
    lines = ["Quotazioni Immobiliari - Semestre 2026/1 - Provincia di CHIETI", OMI_VALUES_HEADER]
    for zone, kind, state, prevalent, low, high in OMI_ROWS if rows is None else rows:
        lines.append(
            f"CENTRO;ABRUZZO;CH;69022;C632;;C632;CHIETI;Centrale;{zone};CH000{zone};20;"
            f"{kind};{state};{prevalent};{low};{high};L;4,5;6,2;L;"
        )
    return "\r\n".join(lines).encode("cp1252")


def omi_zones_csv() -> bytes:
    lines = [
        "Zone OMI - Semestre 2026/1",
        "Area_territoriale;Regione;Prov;Comune_ISTAT;Comune_cat;Sez;Comune_amm;"
        "Comune_descrizione;Fascia;Zona_Descr;Zona;LinkZona;Cod_tip_prev;Descr_tip_prev;"
        "Stato_prev;Microzona;",
        "CENTRO;ABRUZZO;CH;69022;C632;;C632;CHIETI;Centrale;'CENTRO STORICO';B1;CH000B1;20;"
        "Abitazioni civili;N;1;",
        "CENTRO;ABRUZZO;CH;69022;C632;;C632;CHIETI;Periferica;'SCALO';D1;CH000D1;20;"
        "Abitazioni civili;N;2;",
    ]
    return "\r\n".join(lines).encode("cp1252")


def omi_kml(squares: dict[str, tuple[float, float, float, float]] | None = None) -> bytes:
    placemarks = []
    for zone, (west, south, east, north) in (squares or OMI_SQUARES).items():
        ring = (
            f"{west},{south},0 {east},{south},0 {east},{north},0 {west},{north},0 {west},{south},0"
        )
        placemarks.append(
            f"<Placemark><name>CHIETI - Zona OMI {zone}</name><ExtendedData>"
            '<Data name="LINKZONA"><value></value></Data>'
            '<Data name="CODCOM"><displayName>Codice Comune</displayName><value>C632</value></Data>'
            f'<Data name="CODZONA"><value>{zone}</value></Data></ExtendedData>'
            f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{ring}</coordinates>"
            "</LinearRing></outerBoundaryIs></Polygon></Placemark>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2">'
        "<Document><name>CHIETI (CH) Anno/Semestre 2026/1</name>"
        + "".join(placemarks)
        + "</Document></kml>"
    ).encode()


def omi_kmz() -> bytes:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Provincia di CHIETI 2026-1.kml", "<kml><Document/></kml>")
        archive.writestr("Comuni/Comune di CHIETI 2026-1.kml", omi_kml())
    return buffer.getvalue()
