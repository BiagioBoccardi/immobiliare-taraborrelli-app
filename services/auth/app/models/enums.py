from enum import StrEnum


class ConsentPurpose(StrEnum):
    CONTACT = "contact"  # being contacted about one's own requests
    MARKETING = "marketing"  # commercial communications, separate from contact
    PUSH_NOTIFICATIONS = "push_notifications"


class ConsentSubject(StrEnum):
    USER = "user"  # registered user of the app
    LEAD = "lead"  # owner who filled in a form without an account


class ConsentSource(StrEnum):
    APP = "app"
    WEB = "web"
    LEAD_FORM = "lead_form"
