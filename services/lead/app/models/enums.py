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
