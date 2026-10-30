from enum import StrEnum


class LeadKind(StrEnum):
    VALUATION = "valuation"
    SELL = "sell"
    RENT = "rent"
    CALLBACK = "callback"  # "Richiedi di essere ricontattato" on the agency's website


class LeadStatus(StrEnum):
    NEW = "new"
    CONTACTED = "contacted"
    APPOINTMENT_SCHEDULED = "appointment_scheduled"
    MANDATE_ACQUIRED = "mandate_acquired"
    LOST = "lost"


class LeadPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class OwnerIntention(StrEnum):
    """How determined the owner is. Drives the lead priority."""

    KNOW_VALUE = "know_value"  # only wants to know the value
    PLANNING = "planning"  # thinking about selling/renting in the next months
    DECIDED = "decided"  # has already decided


class PropertyType(StrEnum):
    APARTMENT = "apartment"
    HOUSE = "house"
    VILLA = "villa"
    ATTIC = "attic"
    COMMERCIAL = "commercial"
    LAND = "land"
    OTHER = "other"


class PreferredTime(StrEnum):
    """When the person asking to be called back prefers to receive the call."""

    MORNING = "morning"  # 9:00 - 12:00
    AFTERNOON = "afternoon"  # 12:00 - 17:00
    EVENING = "evening"  # 17:00 - 20:00
    ANY = "any"


class PropertyCondition(StrEnum):
    NEW = "new"
    RENOVATED = "renovated"
    GOOD = "good"
    TO_RENOVATE = "to_renovate"


class CadastralCategory(StrEnum):
    """Cadastral category of a home (A/1 ... A/8), as written in the deed or the "visura"."""

    A1 = "A1"  # signorile
    A2 = "A2"  # civile
    A3 = "A3"  # economica
    A4 = "A4"  # popolare
    A5 = "A5"  # ultrapopolare
    A6 = "A6"  # rurale
    A7 = "A7"  # villino
    A8 = "A8"  # villa
    UNKNOWN = "unknown"


class BuildingWorks(StrEnum):
    """Renovation works on the building (or the detached house) in the last ten years."""

    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class OmiType(StrEnum):
    """Residential building types of the OMI quotations (Agenzia delle Entrate)."""

    LUXURY = "luxury"  # Abitazioni signorili
    CIVIL = "civil"  # Abitazioni civili
    ECONOMIC = "economic"  # Abitazioni di tipo economico
    VILLA = "villa"  # Ville e villini


class OmiState(StrEnum):
    """Maintenance state the OMI quotation refers to."""

    EXCELLENT = "excellent"  # OTTIMO
    NORMAL = "normal"  # NORMALE
    POOR = "poor"  # SCADENTE
