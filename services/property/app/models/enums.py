from enum import StrEnum


class Contract(StrEnum):
    SALE = "sale"
    RENT = "rent"


class PropertyStatus(StrEnum):
    DRAFT = "draft"  # being prepared by the agency, not visible
    PUBLISHED = "published"
    RESERVED = "reserved"  # under offer / proposal accepted: still visible
    SOLD = "sold"
    RENTED = "rented"
    ARCHIVED = "archived"


# Statuses visible in the public catalog.
PUBLIC_STATUSES = frozenset({PropertyStatus.PUBLISHED, PropertyStatus.RESERVED})

# Allowed status changes from the admin panel.
STATUS_TRANSITIONS: dict[PropertyStatus, frozenset[PropertyStatus]] = {
    PropertyStatus.DRAFT: frozenset({PropertyStatus.PUBLISHED, PropertyStatus.ARCHIVED}),
    PropertyStatus.PUBLISHED: frozenset(
        {
            PropertyStatus.DRAFT,
            PropertyStatus.RESERVED,
            PropertyStatus.SOLD,
            PropertyStatus.RENTED,
            PropertyStatus.ARCHIVED,
        }
    ),
    PropertyStatus.RESERVED: frozenset(
        {PropertyStatus.PUBLISHED, PropertyStatus.SOLD, PropertyStatus.RENTED}
    ),
    PropertyStatus.SOLD: frozenset({PropertyStatus.ARCHIVED}),
    PropertyStatus.RENTED: frozenset({PropertyStatus.PUBLISHED, PropertyStatus.ARCHIVED}),
    PropertyStatus.ARCHIVED: frozenset({PropertyStatus.DRAFT}),
}


class PropertyType(StrEnum):
    APARTMENT = "apartment"
    HOUSE = "house"
    VILLA = "villa"
    ATTIC = "attic"
    COMMERCIAL = "commercial"
    LAND = "land"
    GARAGE = "garage"
    OTHER = "other"


class PropertyCondition(StrEnum):
    NEW = "new"
    RENOVATED = "renovated"
    GOOD = "good"
    TO_RENOVATE = "to_renovate"


class EnergyClass(StrEnum):
    A4 = "A4"
    A3 = "A3"
    A2 = "A2"
    A1 = "A1"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"


class Feature(StrEnum):
    ELEVATOR = "elevator"
    PARKING = "parking"
    GARAGE = "garage"
    GARDEN = "garden"
    TERRACE = "terrace"
    BALCONY = "balcony"
    CELLAR = "cellar"
    FURNISHED = "furnished"
    AIR_CONDITIONING = "air_conditioning"
    AUTONOMOUS_HEATING = "autonomous_heating"


class TenantType(StrEnum):
    """Who a rental is meant for ("Affitti per studenti e lavoratori")."""

    STUDENTS = "students"
    WORKERS = "workers"
    FAMILIES = "families"


class Accommodation(StrEnum):
    ENTIRE_PROPERTY = "entire_property"
    SINGLE_ROOM = "single_room"
    SHARED_ROOM = "shared_room"


class SortOrder(StrEnum):
    NEWEST = "newest"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    SURFACE_DESC = "surface_desc"
